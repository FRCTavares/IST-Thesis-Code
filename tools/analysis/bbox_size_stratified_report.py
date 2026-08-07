#!/usr/bin/env python3
"""Bbox-height-stratified reporting for Issue #30's external sequences.

Answers a bounded, specific question: does selected-target performance
degrade as the physical target becomes smaller in the image, and does
TIM-MARS change the balance between correct publication, wrong-person
publication, and conservative suppression across those size regimes? This
is an evaluation/reporting addition only -- it reuses the existing, already
tested resolve/candidate-stream/classification building blocks unmodified
(``resolve_external_candidate_stream``, ``run_external_sequence_report``,
``evaluate_external_frame_outcomes``, ``external_target_initialization``)
and reads already-generated replay bags; it does not rerun any capture or
replay, and does not change TIM-MARS thresholds, detector settings,
ByteTrack settings, or sequence selection.

Scope: the 3 retained VisDrone-MOT sequences
(``visdrone_mot_val_uav0000117_02622_v``,
``visdrone_mot_val_uav0000137_00458_v``,
``visdrone_mot_val_uav0000339_00001_v``), the only sequences in the primary
Issue #30 scope with a per-frame, multi-person ground-truth bounding-box
annotation. The 4 ROS 2 development sequences do not have this contract --
they only have live detector/tracker output plus each sequence's own
official ``correct_target_track_id`` annotation for the single physical
target, not dense per-frame boxes for every person, so there is no
defensible way to build the same size stratification for them without
inventing pseudo-annotations. This module deliberately does not attempt
that. DanceTrack and ``uav0000268_05773_v`` remain excluded from this
analysis exactly as they are excluded from the primary benchmark (Slice
25); nothing here reintroduces them.

Bin edges (``<70px, 70-89px, 90-109px, 110-129px, >=130px``) were chosen
after inspecting the actual pooled target-height distribution across all
three sequences (66-132 px, median ~83 px). The originally proposed
``<20/20-39/40-79/80-159/>=160`` scheme would put 100% of frames from every
sequence into a single bin (80-159px) -- none of these sequences contain a
GT-visible frame with a target height below 66px or at/above 133px -- so it
was replaced with a data-driven scheme covering the observed range with
non-empty bins in every case (pooled: 33 / 443 / 245 / 120 / 16 frames).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from evaluate_external_frame_outcomes import (  # noqa: E402
    FrameOutcome,
    OtherPerson,
    classify_sequence,
    summarize,
)
from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    PhysicalTargetObservation,
    match_frame,
)
from resolve_external_candidate_stream import (  # noqa: E402
    DEFAULT_MANIFEST,
    ensure_uncompressed_bag,
    load_manifest_entry,
    load_tracker_candidates,
    resolve,
)
from run_external_sequence_report import (  # noqa: E402
    load_all_annotations,
    read_target_stream,
)

# (label, min_px_inclusive, max_px_exclusive)
DEFAULT_BINS: list[tuple[str, float, float]] = [
    ("<70px", 0.0, 70.0),
    ("70-89px", 70.0, 90.0),
    ("90-109px", 90.0, 110.0),
    ("110-129px", 110.0, 130.0),
    (">=130px", 130.0, float("inf")),
]

SEQUENCE_IDS: list[str] = [
    "visdrone_mot_val_uav0000117_02622_v",
    "visdrone_mot_val_uav0000137_00458_v",
    "visdrone_mot_val_uav0000339_00001_v",
]

FULL_PIPELINE_CAPTURE_ROOT = (
    ROOT / "bags" / "replay" / "p030_broader_sequences_external_2026_08_07"
)
FULL_PIPELINE_REPLAY_ROOT = (
    ROOT
    / "bags"
    / "replay"
    / "p030_broader_sequences_external_replay_2026_08_07"
)
ORACLE_CAPTURE_ROOT = (
    ROOT / "bags" / "replay" / "p030_broader_sequences_oracle_2026_08_07"
)
ORACLE_REPLAY_ROOT = (
    ROOT
    / "bags"
    / "replay"
    / "p030_broader_sequences_oracle_replay_2026_08_07"
)

ROS2_STRATIFICATION_NOTE = (
    "bbox-size stratification applies only to the external frame-taxonomy "
    "VisDrone-MOT sequences. The 4 ROS 2 development sequences do not have "
    "a per-frame, multi-person ground-truth bounding-box annotation "
    "(only live detector/tracker output plus a single official "
    "correct_target_track_id per sequence), so there is no defensible "
    "frame-level GT bbox mapping to stratify by; no pseudo-annotation was "
    "invented to fill this table."
)


def bin_bounds_json(bins: list[tuple[str, float, float]]) -> list[dict]:
    return [
        {
            "label": label,
            "min_px_inclusive": lo,
            "max_px_exclusive": (hi if hi != float("inf") else None),
        }
        for label, lo, hi in bins
    ]


def assign_bin(height_px: float, bins: list[tuple[str, float, float]]) -> str:
    for label, lo, hi in bins:
        if lo <= height_px < hi:
            return label
    raise ValueError(f"height {height_px} not covered by any bin")


def load_target_rows_in_range(entry: dict[str, Any]) -> dict[int, Any]:
    dataset_identity = entry["target"]["dataset_identity"]
    start = entry["frame_contract"]["normalized_start_index"]
    end = entry["frame_contract"]["normalized_end_index_inclusive"]
    rows = load_all_annotations(entry)
    return {
        row.normalized_frame_index: row
        for row in rows
        if row.identity == dataset_identity
        and row.include_as_person_candidate
        and start <= row.normalized_frame_index <= end
    }


def size_distribution(
    target_by_frame: dict[int, Any],
    bins: list[tuple[str, float, float]],
    image_height: int,
) -> dict[str, Any]:
    counts = {label: 0 for label, _, _ in bins}
    heights_norm_sum = {label: 0.0 for label, _, _ in bins}
    for row in target_by_frame.values():
        height_px = row.bbox_xyxy[3] - row.bbox_xyxy[1]
        label = assign_bin(height_px, bins)
        counts[label] += 1
        heights_norm_sum[label] += height_px / image_height

    total = len(target_by_frame)
    return {
        "gt_visible_frames": total,
        "counts_by_bin": counts,
        "fraction_by_bin": {
            label: (count / total if total else None)
            for label, count in counts.items()
        },
        "mean_normalized_height_by_bin": {
            label: (
                heights_norm_sum[label] / counts[label]
                if counts[label]
                else None
            )
            for label in counts
        },
    }


def candidate_presence_by_bin(
    entry: dict[str, Any],
    target_by_frame: dict[int, Any],
    candidates_by_frame: dict[int, list],
    bins: list[tuple[str, float, float]],
) -> dict[str, Any]:
    match_config = InitializationConfig(
        start_frame_index=entry["frame_contract"]["normalized_start_index"],
        end_frame_index_inclusive=entry["frame_contract"][
            "normalized_end_index_inclusive"
        ],
        minimum_iou=entry["target"]["minimum_match_iou"],
        minimum_margin=entry["target"]["minimum_match_margin"],
        confirmation_frames=entry["target"]["confirmation_frames"],
    )

    per_bin = {
        label: {"frames": 0, "with_candidate": 0} for label, _, _ in bins
    }
    for frame_index, row in target_by_frame.items():
        height_px = row.bbox_xyxy[3] - row.bbox_xyxy[1]
        label = assign_bin(height_px, bins)
        target_obs = PhysicalTargetObservation(
            normalized_frame_index=frame_index,
            dataset_identity=row.identity,
            bbox_xyxy=row.bbox_xyxy,
        )
        match = match_frame(
            target_obs, candidates_by_frame.get(frame_index, []), match_config
        )
        per_bin[label]["frames"] += 1
        if match.accepted:
            per_bin[label]["with_candidate"] += 1

    for label, stats in per_bin.items():
        frames = stats["frames"]
        stats["fraction_with_candidate"] = (
            stats["with_candidate"] / frames if frames else None
        )
    return per_bin


def bucket_outcomes_by_bin(
    outcomes: list[FrameOutcome],
    target_by_frame: dict[int, Any],
    bins: list[tuple[str, float, float]],
) -> dict[str, list[FrameOutcome]]:
    by_bin: dict[str, list[FrameOutcome]] = {
        label: [] for label, _, _ in bins
    }
    for outcome in outcomes:
        row = target_by_frame.get(outcome.normalized_frame_index)
        if row is None:
            # No GT box at this frame (physical-absence outcomes): not a
            # target-size question, excluded from size stratification.
            continue
        height_px = row.bbox_xyxy[3] - row.bbox_xyxy[1]
        by_bin[assign_bin(height_px, bins)].append(outcome)
    return by_bin


def load_candidates_by_frame(
    capture_bag: Path, frame_rate_hz: float
) -> dict[int, list]:
    uncompressed_bag = ensure_uncompressed_bag(capture_bag)
    created_temp_copy = uncompressed_bag != Path(capture_bag)
    try:
        candidates_by_frame: dict[int, list] = {}
        for candidate in load_tracker_candidates(
            uncompressed_bag, frame_rate_hz=frame_rate_hz
        ):
            candidates_by_frame.setdefault(
                candidate.normalized_frame_index, []
            ).append(candidate)
        return candidates_by_frame
    finally:
        if created_temp_copy and uncompressed_bag.exists():
            shutil.rmtree(uncompressed_bag)


def resolve_success(
    sequence_id: str, capture_bag: Path, manifest_path: Path
) -> dict[str, Any]:
    uncompressed_bag = ensure_uncompressed_bag(capture_bag)
    created_temp_copy = uncompressed_bag != Path(capture_bag)
    try:
        return resolve(
            sequence_id=sequence_id,
            capture_bag=uncompressed_bag,
            manifest_path=manifest_path,
        )
    finally:
        if created_temp_copy and uncompressed_bag.exists():
            shutil.rmtree(uncompressed_bag)


def sequence_bin_report(
    *,
    sequence_id: str,
    capture_root: Path,
    replay_root: Path,
    bins: list[tuple[str, float, float]],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    entry = load_manifest_entry(manifest_path, sequence_id=sequence_id)
    frame_rate = entry["frame_contract"]["frame_rate"]

    target_by_frame = load_target_rows_in_range(entry)
    distribution = size_distribution(
        target_by_frame, bins, entry["image"]["height"]
    )

    capture_bag = capture_root / entry["sequence_name"]
    candidates_by_frame = load_candidates_by_frame(capture_bag, frame_rate)
    candidate_presence = candidate_presence_by_bin(
        entry, target_by_frame, candidates_by_frame, bins
    )

    resolution = resolve_success(sequence_id, capture_bag, manifest_path)

    result: dict[str, Any] = {
        "sequence_id": sequence_id,
        "size_distribution": distribution,
        "candidate_presence_by_bin": candidate_presence,
    }

    if not resolution["success"]:
        result["status"] = "initialization_failure"
        result["resolution"] = resolution
        result["raw_by_bin"] = None
        result["tim_by_bin"] = None
        result["_raw_outcomes_by_bin"] = None
        result["_tim_outcomes_by_bin"] = None
        return result

    replay_bag = replay_root / entry["sequence_name"]
    raw_outputs = read_target_stream(
        replay_bag, topic="/target", frame_rate_hz=frame_rate
    )
    tim_outputs = read_target_stream(
        replay_bag, topic="/target_memory_mars", frame_rate_hz=frame_rate
    )

    all_rows = load_all_annotations(entry)
    dataset_identity = entry["target"]["dataset_identity"]
    other_people_by_frame: dict[int, list[OtherPerson]] = {}
    for row in all_rows:
        if row.identity == dataset_identity:
            continue
        if not row.include_as_person_candidate:
            continue
        other_people_by_frame.setdefault(
            row.normalized_frame_index, []
        ).append(
            OtherPerson(
                normalized_frame_index=row.normalized_frame_index,
                dataset_identity=row.identity,
                bbox_xyxy=row.bbox_xyxy,
            )
        )

    start = entry["frame_contract"]["normalized_start_index"]
    end = entry["frame_contract"]["normalized_end_index_inclusive"]
    frame_indices = list(range(start, end + 1))
    match_config = InitializationConfig(
        start_frame_index=start,
        end_frame_index_inclusive=end,
        minimum_iou=entry["target"]["minimum_match_iou"],
        minimum_margin=entry["target"]["minimum_match_margin"],
        confirmation_frames=entry["target"]["confirmation_frames"],
    )

    raw_outcomes = classify_sequence(
        frame_indices=frame_indices,
        target_by_frame=target_by_frame,
        candidates_by_frame=candidates_by_frame,
        other_people_by_frame=other_people_by_frame,
        outputs_by_frame=raw_outputs,
        match_config=match_config,
    )
    tim_outcomes = classify_sequence(
        frame_indices=frame_indices,
        target_by_frame=target_by_frame,
        candidates_by_frame=candidates_by_frame,
        other_people_by_frame=other_people_by_frame,
        outputs_by_frame=tim_outputs,
        match_config=match_config,
    )

    raw_outcomes_by_bin = bucket_outcomes_by_bin(
        raw_outcomes, target_by_frame, bins
    )
    tim_outcomes_by_bin = bucket_outcomes_by_bin(
        tim_outcomes, target_by_frame, bins
    )

    result["status"] = "evaluated"
    result["raw_by_bin"] = {
        label: summarize(outs) for label, outs in raw_outcomes_by_bin.items()
    }
    result["tim_by_bin"] = {
        label: summarize(outs) for label, outs in tim_outcomes_by_bin.items()
    }
    # Kept private (leading underscore, stripped before JSON output) so the
    # aggregate step can pool raw FrameOutcome objects across sequences
    # instead of re-deriving fractions from already-summarized per-sequence
    # dicts.
    result["_raw_outcomes_by_bin"] = raw_outcomes_by_bin
    result["_tim_outcomes_by_bin"] = tim_outcomes_by_bin
    return result


def aggregate_across_sequences(
    per_sequence: dict[str, dict[str, Any]],
    bins: list[tuple[str, float, float]],
    *,
    stream_key: str,
) -> dict[str, Any]:
    pooled: dict[str, list[FrameOutcome]] = {label: [] for label, _, _ in bins}
    for report in per_sequence.values():
        by_bin = report.get(stream_key)
        if not by_bin:
            continue
        for label, outcomes in by_bin.items():
            pooled[label].extend(outcomes)
    return {label: summarize(outs) for label, outs in pooled.items()}


def strip_private_fields(report: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if not k.startswith("_")}


def build_bbox_size_report(
    bins: list[tuple[str, float, float]] = DEFAULT_BINS,
) -> dict[str, Any]:
    full_pipeline = {
        seq_id: sequence_bin_report(
            sequence_id=seq_id,
            capture_root=FULL_PIPELINE_CAPTURE_ROOT,
            replay_root=FULL_PIPELINE_REPLAY_ROOT,
            bins=bins,
        )
        for seq_id in SEQUENCE_IDS
    }
    oracle = {
        seq_id: sequence_bin_report(
            sequence_id=seq_id,
            capture_root=ORACLE_CAPTURE_ROOT,
            replay_root=ORACLE_REPLAY_ROOT,
            bins=bins,
        )
        for seq_id in SEQUENCE_IDS
    }

    full_pipeline_raw_agg = aggregate_across_sequences(
        full_pipeline, bins, stream_key="_raw_outcomes_by_bin"
    )
    full_pipeline_tim_agg = aggregate_across_sequences(
        full_pipeline, bins, stream_key="_tim_outcomes_by_bin"
    )
    oracle_raw_agg = aggregate_across_sequences(
        oracle, bins, stream_key="_raw_outcomes_by_bin"
    )
    oracle_tim_agg = aggregate_across_sequences(
        oracle, bins, stream_key="_tim_outcomes_by_bin"
    )

    return {
        "bins": bin_bounds_json(bins),
        "primary_target_size_measure": "ground_truth_target_bbox_height_px",
        "sequence_scope": SEQUENCE_IDS,
        "ros2_stratification_note": ROS2_STRATIFICATION_NOTE,
        "full_pipeline": {
            seq_id: strip_private_fields(report)
            for seq_id, report in full_pipeline.items()
        },
        "full_pipeline_aggregate_by_bin": {
            "raw": full_pipeline_raw_agg,
            "tim_mars": full_pipeline_tim_agg,
            "note": (
                "Only uav0000339_00001_v contributed evaluated outcomes; "
                "uav0000117_02622_v and uav0000137_00458_v are "
                "initialization_failure and contribute no raw/TIM outcome "
                "data to this aggregate, only to the size distribution and "
                "candidate-presence tables above."
            ),
        },
        "oracle_candidate": {
            seq_id: strip_private_fields(report)
            for seq_id, report in oracle.items()
        },
        "oracle_candidate_aggregate_by_bin": {
            "raw": oracle_raw_agg,
            "tim_mars": oracle_tim_agg,
            "note": (
                "All 3 sequences initialize successfully in oracle mode "
                "and contribute outcome data to this aggregate. Raw is "
                "100% correct by oracle-mode construction (see Slice 26), "
                "not a tracking-performance baseline."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    report = build_bbox_size_report()
    rendered = json.dumps(report, indent=2, default=str)

    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
