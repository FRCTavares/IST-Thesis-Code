#!/usr/bin/env python3
"""End-to-end Issue #30 report for one captured external sequence.

Pipeline:
1. resolve the frozen physical target's live tracker identity from the
   captured detector/ByteTrack candidate bag
   (resolve_external_candidate_stream.py);
2. if resolution failed, record an initialization-failure report and stop --
   there is no valid raw or TIM-MARS run to score;
3. otherwise, deterministically generate the paired raw-versus-TIM-MARS
   streams from that one candidate stream
   (tools/experiments/run_deterministic_tim_replay.py, unmodified, the same
   tool already proven in Slice 15);
4. read the sequence's own official ground truth for the frozen physical
   identity across the evaluation frame range;
5. classify every evaluation frame for both the raw and TIM-MARS streams
   (evaluate_external_frame_outcomes.py);
6. write one deterministic JSON report with both streams' outcome counts,
   the wrong-person/lost distinction, and full provenance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
EXPERIMENTS_DIR = ROOT / "tools" / "experiments"
sys.path.insert(0, str(ANALYSIS_DIR))

from evaluate_external_frame_outcomes import (  # noqa: E402
    OtherPerson,
    SystemOutput,
    classify_sequence,
    summarize,
)
from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    TrackerCandidateObservation,
)
from external_tracking_dataset import (  # noqa: E402
    SequenceGeometry,
    parse_dancetrack_annotations,
    parse_visdrone_annotations,
)
from resolve_external_candidate_stream import (  # noqa: E402
    DEFAULT_MANIFEST,
    annotation_path_for,
    ensure_uncompressed_bag,
    load_manifest_entry,
    load_tracker_candidates,
    open_bag_reader,
    resolve,
)


def load_all_annotations(entry: dict[str, Any]):
    geometry = SequenceGeometry(
        image_width=entry["image"]["width"],
        image_height=entry["image"]["height"],
        frame_rate=entry["frame_contract"]["frame_rate"],
        source_index_base=entry["frame_contract"]["source_index_base"],
    )
    path = annotation_path_for(entry)

    if entry["dataset"] == "dancetrack":
        return parse_dancetrack_annotations(
            path,
            sequence_name=entry["sequence_name"],
            split=entry["split"],
            geometry=geometry,
        )

    return parse_visdrone_annotations(
        path,
        sequence_name=entry["sequence_name"],
        split=entry["split"],
        geometry=geometry,
    )


def read_target_stream(
    bag_path: Path,
    *,
    topic: str,
    frame_rate_hz: float,
    start_time_ns: int = 0,
) -> dict[int, SystemOutput]:
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from thesis_msgs.msg import TargetState

    period_ns = round(1_000_000_000 / frame_rate_hz)

    reader = open_bag_reader(bag_path)
    reader.set_filter(rosbag2_py.StorageFilter(topics=[topic]))

    outputs: dict[int, SystemOutput] = {}

    while reader.has_next():
        _topic, data, _bag_ts = reader.read_next()
        message = deserialize_message(data, TargetState)

        frame_index = round(
            (int(message.src_stamp_ns) - start_time_ns) / period_ns
        )

        if message.id == 0:
            outputs[frame_index] = SystemOutput(
                normalized_frame_index=frame_index,
                tracker_identity=None,
                bbox_xyxy=None,
            )
            continue

        half_w = message.w / 2.0
        half_h = message.h / 2.0
        outputs[frame_index] = SystemOutput(
            normalized_frame_index=frame_index,
            tracker_identity=int(message.id),
            bbox_xyxy=(
                message.cx - half_w,
                message.cy - half_h,
                message.cx + half_w,
                message.cy + half_h,
            ),
        )

    return outputs


def run_deterministic_replay(
    *,
    capture_bag: Path,
    output_bag: Path,
    selected_track_id: int,
    image_width: int,
    image_height: int,
    repo_root: Path,
) -> None:
    """Run the deterministic TIM-MARS replay for one sequence.

    ``image_width``/``image_height`` must be the sequence's own frozen
    source resolution (``manifest entry["image"]["width"/"height"]``), not
    left to ``run_deterministic_tim_replay.py``'s 640x640 default. That
    default matches the ROS 2 field sequences it was built for, but external
    sequences (e.g. VisDrone at 1904x1071) are a different source
    resolution; omitting these flags made TIM-MARS clip candidate boxes to
    640x640, normalize geometry against the wrong image diagonal, and
    rescale appearance crops incorrectly, while the raw baseline was
    unaffected because it copies boxes through unchanged. This produced a
    false wrong-person signal for TIM-MARS on `uav0000339_00001_v` (7
    frames) that was not a genuine tracking failure -- see Slice 22.
    """

    config_path = (
        repo_root
        / "ros2_ws"
        / "install"
        / "thesis_bringup"
        / "share"
        / "thesis_bringup"
        / "config"
        / "tim_mars_canonical.yaml"
    )
    model_path = repo_root / "models" / "reid" / "mars-small128.pb"

    if output_bag.exists():
        import shutil

        shutil.rmtree(output_bag)

    subprocess.run(
        [
            sys.executable,
            str(EXPERIMENTS_DIR / "run_deterministic_tim_replay.py"),
            str(capture_bag),
            str(output_bag),
            "--config",
            str(config_path),
            "--model",
            str(model_path),
            "--selected-track-id",
            str(selected_track_id),
            "--image-topic",
            "/camera/image_raw",
            "--tracks-topic",
            "/tracks",
            "--raw-target-topic",
            "/target",
            "--raw-target-mode",
            "selected_id",
            "--image-width",
            str(image_width),
            "--image-height",
            str(image_height),
            "--overwrite",
            "--compact-output",
        ],
        cwd=repo_root,
        check=True,
    )


def build_report(
    *,
    sequence_id: str,
    capture_bag: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = ROOT,
    replay_output_root: Optional[Path] = None,
) -> dict[str, Any]:
    entry = load_manifest_entry(manifest_path, sequence_id=sequence_id)

    import shutil

    uncompressed_bag = ensure_uncompressed_bag(capture_bag)
    created_temp_copy = uncompressed_bag != Path(capture_bag)
    candidates_by_frame: dict[
        int, list[TrackerCandidateObservation]
    ] = {}

    try:
        resolution = resolve(
            sequence_id=sequence_id,
            capture_bag=uncompressed_bag,
            manifest_path=manifest_path,
        )

        if not resolution["success"]:
            return {
                "sequence_id": sequence_id,
                "status": "initialization_failure",
                "resolution": resolution,
            }

        frame_rate = entry["frame_contract"]["frame_rate"]

        # Read while the (possibly temporary, decompressed) capture bag
        # still exists, before the finally block below removes it. This
        # is the same recorded ByteTrack /tracks stream resolve() already
        # read to confirm the frozen physical target's tracker identity
        # (Slice 17); grouping it by frame here lets the frame classifier
        # distinguish candidate-absence/ambiguity/safe-suppression from a
        # missing output, instead of the placeholder empty dict used
        # before this fix, which made every "no output" frame look like
        # candidate absence and made safe-suppression unreachable.
        for candidate in load_tracker_candidates(
            uncompressed_bag, frame_rate_hz=frame_rate
        ):
            candidates_by_frame.setdefault(
                candidate.normalized_frame_index, []
            ).append(candidate)

        replay_output_root = replay_output_root or (
            repo_root
            / "bags"
            / "replay"
            / "p030_broader_sequences_external_replay_2026_08_07"
        )
        replay_output_root.mkdir(parents=True, exist_ok=True)
        replay_bag = replay_output_root / entry["sequence_name"]

        run_deterministic_replay(
            capture_bag=uncompressed_bag,
            output_bag=replay_bag,
            selected_track_id=resolution["initial_tracker_identity"],
            image_width=entry["image"]["width"],
            image_height=entry["image"]["height"],
            repo_root=repo_root,
        )
    finally:
        if created_temp_copy and uncompressed_bag.exists():
            shutil.rmtree(uncompressed_bag)

    raw_outputs = read_target_stream(
        replay_bag, topic="/target", frame_rate_hz=frame_rate
    )
    tim_outputs = read_target_stream(
        replay_bag,
        topic="/target_memory_mars",
        frame_rate_hz=frame_rate,
    )

    all_rows = load_all_annotations(entry)
    dataset_identity = entry["target"]["dataset_identity"]

    target_by_frame = {
        row.normalized_frame_index: row
        for row in all_rows
        if row.identity == dataset_identity
        and row.include_as_person_candidate
    }

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

    return {
        "sequence_id": sequence_id,
        "status": "evaluated",
        "resolution": resolution,
        "replay_bag": str(replay_bag),
        "evaluation_frame_range": [start, end],
        "raw": summarize(raw_outcomes),
        "tim_mars": summarize(tim_outcomes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence_id")
    parser.add_argument("capture_bag", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    report = build_report(
        sequence_id=arguments.sequence_id,
        capture_bag=arguments.capture_bag,
        manifest_path=arguments.manifest,
    )

    rendered = json.dumps(report, indent=2, default=str)

    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)

    return 0 if report["status"] == "evaluated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
