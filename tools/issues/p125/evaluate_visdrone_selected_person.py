#!/usr/bin/env python3
"""Frame-level physical-person attribution for the Issue #125 protocol.

This module has no detector or tracker dependency. It classifies an already
supplied controller-facing box against official person ground truth.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

BBox = tuple[float, float, float, float]

CORRECT = "correct"
WRONG_PERSON = "wrong_person"
IDENTITY_UNRESOLVED = "identity_unresolved"
LOST_SUPPRESSED = "lost_suppressed"
REFERENCE_UNAVAILABLE = "reference_unavailable_or_target_not_annotated"
PRIMARY_BUCKETS = (CORRECT, WRONG_PERSON, IDENTITY_UNRESOLVED, LOST_SUPPRESSED)


@dataclass(frozen=True)
class AttributionConfig:
    person_iou_threshold: float = 0.30
    unique_iou_margin: float = 0.10
    ambiguous_region_output_coverage: float = 0.50

    def __post_init__(self) -> None:
        for name, value in (
            ("person_iou_threshold", self.person_iou_threshold),
            ("unique_iou_margin", self.unique_iou_margin),
            ("ambiguous_region_output_coverage", self.ambiguous_region_output_coverage),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class FrameAttribution:
    bucket: str
    matched_identity: int | None
    target_iou: float | None
    best_other_iou: float | None
    reason: str


def _area(box: BBox) -> float:
    if not all(math.isfinite(value) for value in box):
        raise ValueError("box coordinates must be finite")
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        raise ValueError("box must have positive area")
    return (x2 - x1) * (y2 - y1)


def _intersection(a: BBox, b: BBox) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[3], b[3]) - max(a[1], b[1])
    )


def _iou(a: BBox, b: BBox) -> float:
    area_a, area_b = _area(a), _area(b)
    overlap = _intersection(a, b)
    return overlap / (area_a + area_b - overlap)


def classify_frame(
    *,
    target_bbox: BBox | None,
    target_identity: int,
    other_people: Sequence[tuple[int, BBox]],
    ambiguous_regions: Sequence[BBox],
    output_bbox: BBox | None,
    config: AttributionConfig,
) -> FrameAttribution:
    """Classify one source frame; missing target GT never proves absence."""
    if target_identity <= 0:
        raise ValueError("target identity must be positive")
    if target_bbox is None:
        return FrameAttribution(
            REFERENCE_UNAVAILABLE, None, None, None, "target_has_no_gt_row"
        )
    _area(target_bbox)
    seen = {target_identity}
    for identity, bbox in other_people:
        if identity <= 0 or identity in seen:
            raise ValueError("other-person identities must be positive and unique")
        seen.add(identity)
        _area(bbox)
    for region in ambiguous_regions:
        _area(region)
    if output_bbox is None:
        return FrameAttribution(
            LOST_SUPPRESSED, None, None, None, "no_valid_controller_output"
        )
    output_area = _area(output_bbox)
    target_iou = _iou(output_bbox, target_bbox)
    other_scores = [
        (_iou(output_bbox, bbox), identity)
        for identity, bbox in other_people
    ]
    best_other_iou = max((score for score, _ in other_scores), default=0.0)
    if any(
        _intersection(output_bbox, region) / output_area
        >= config.ambiguous_region_output_coverage
        for region in ambiguous_regions
    ):
        return FrameAttribution(
            IDENTITY_UNRESOLVED, None, target_iou, best_other_iou,
            "ambiguous_region_overlap",
        )
    ranked = sorted(
        [(target_iou, target_identity), *other_scores],
        key=lambda item: (-item[0], item[1]),
    )
    best_iou, best_identity = ranked[0]
    second_iou = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_iou < config.person_iou_threshold:
        return FrameAttribution(
            IDENTITY_UNRESOLVED, None, target_iou, best_other_iou,
            "no_person_iou_above_threshold",
        )
    if best_iou - second_iou < config.unique_iou_margin:
        return FrameAttribution(
            IDENTITY_UNRESOLVED, None, target_iou, best_other_iou,
            "person_attribution_not_unique",
        )
    if best_identity == target_identity:
        return FrameAttribution(
            CORRECT, target_identity, target_iou, best_other_iou,
            "unique_target_match",
        )
    return FrameAttribution(
        WRONG_PERSON, best_identity, target_iou, best_other_iou,
        "unique_other_person_match",
    )


def summarize_target_present(
    attributions: Sequence[FrameAttribution],
) -> dict[str, object]:
    """Reconcile the four primary buckets, excluding reference gaps."""
    counts = {name: 0 for name in PRIMARY_BUCKETS}
    reference_gaps = 0
    for attribution in attributions:
        if attribution.bucket == REFERENCE_UNAVAILABLE:
            reference_gaps += 1
        elif attribution.bucket in counts:
            counts[attribution.bucket] += 1
        else:
            raise ValueError(f"unknown bucket {attribution.bucket!r}")
    total = sum(counts.values())
    return {
        "target_present_scored_frames": total,
        "reference_gap_frames": reference_gaps,
        "counts": counts,
        "fractions": {
            name: counts[name] / total if total else None
            for name in PRIMARY_BUCKETS
        },
    }


def evaluate_episode(
    *,
    split: str,
    sequence_name: str,
    dataset_identity: int,
    selection_frame_index: int,
    source_frame_indices: Sequence[int],
    gt_rows: Sequence[Any],
    output_bboxes_by_frame: dict[int, BBox | None],
    config: AttributionConfig,
) -> dict[str, object]:
    """Score one selected GT identity through its final valid observation.

    `gt_rows` uses the established VisDrone annotation adapter fields:
    normalized_frame_index, identity, bbox_xyxy, class_id, and
    include_as_person_candidate. The output map is an already generated
    architecture stream; this function never chooses or changes that stream.
    """
    if not split or not sequence_name or dataset_identity <= 0:
        raise ValueError("split, sequence and positive identity are required")
    if selection_frame_index < 0:
        raise ValueError("selection frame must be non-negative")
    frames = list(source_frame_indices)
    if not frames or frames != sorted(set(frames)):
        raise ValueError("source frame indices must be sorted and unique")
    if selection_frame_index not in frames:
        raise ValueError("selection frame has no source image")
    frame_set = set(frames)
    if set(output_bboxes_by_frame) - frame_set:
        raise ValueError("output stream contains a frame outside the source images")

    person_by_frame: dict[int, list[Any]] = {}
    ambiguous_by_frame: dict[int, list[BBox]] = {}
    for row in gt_rows:
        frame = int(row.normalized_frame_index)
        if frame not in frame_set:
            raise ValueError("GT annotation frame has no source image")
        if bool(row.include_as_person_candidate):
            person_by_frame.setdefault(frame, []).append(row)
        elif int(row.class_id) in (0, 2):
            ambiguous_by_frame.setdefault(frame, []).append(row.bbox_xyxy)

    target_frames = sorted(
        frame
        for frame, rows in person_by_frame.items()
        if frame >= selection_frame_index
        and any(int(row.identity) == dataset_identity for row in rows)
    )
    if not target_frames or target_frames[0] != selection_frame_index:
        raise ValueError("selection frame lacks valid target GT")
    last_target_frame = target_frames[-1]
    outcomes: list[FrameAttribution] = []
    frame_records: list[dict[str, object]] = []
    for frame in frames:
        if frame < selection_frame_index or frame > last_target_frame:
            continue
        people = person_by_frame.get(frame, [])
        target_rows = [
            row for row in people if int(row.identity) == dataset_identity
        ]
        if len(target_rows) > 1:
            raise ValueError("duplicate target GT identity in frame")
        target_bbox = target_rows[0].bbox_xyxy if target_rows else None
        others = [
            (int(row.identity), row.bbox_xyxy)
            for row in people
            if int(row.identity) != dataset_identity
        ]
        attribution = classify_frame(
            target_bbox=target_bbox,
            target_identity=dataset_identity,
            other_people=others,
            ambiguous_regions=ambiguous_by_frame.get(frame, ()),
            output_bbox=output_bboxes_by_frame.get(frame),
            config=config,
        )
        outcomes.append(attribution)
        frame_records.append({
            "normalized_frame_index": frame,
            **asdict(attribution),
        })
    summary = summarize_target_present(outcomes)
    if summary["target_present_scored_frames"] != len(target_frames):
        raise ValueError("target-present denominator does not match target GT")
    return {
        "split": split,
        "sequence_name": sequence_name,
        "dataset_identity": dataset_identity,
        "selection_frame_index": selection_frame_index,
        "last_target_observation_frame_index": last_target_frame,
        "scoring": summary,
        "events": derive_events(frame_records),
        "frames": frame_records,
    }


def derive_events(frame_records: Sequence[dict[str, object]]) -> dict[str, object]:
    """Derive source-frame events without interpreting GT gaps as absence."""
    if not frame_records:
        raise ValueError("event derivation requires frame records")
    frames = [int(record["normalized_frame_index"]) for record in frame_records]
    if frames != sorted(set(frames)):
        raise ValueError("event frames must be sorted and unique")
    wrong_events: list[dict[str, int]] = []
    lost_runs: list[dict[str, int]] = []
    reappearances: list[dict[str, int | None]] = []
    correct_to_wrong = 0

    active_wrong: dict[str, int] | None = None
    active_lost: dict[str, int] | None = None
    gap_start: int | None = None
    recovery_pending: dict[str, int | None] | None = None
    previous_frame: int | None = None
    previous_bucket: str | None = None

    for record in frame_records:
        frame = int(record["normalized_frame_index"])
        bucket = str(record["bucket"])
        if bucket not in (*PRIMARY_BUCKETS, REFERENCE_UNAVAILABLE):
            raise ValueError(f"unknown event bucket {bucket!r}")
        adjacent = previous_frame is not None and frame == previous_frame + 1
        if not adjacent:
            active_wrong = None
            active_lost = None
            if gap_start is not None:
                gap_start = None
            recovery_pending = None

        if bucket == REFERENCE_UNAVAILABLE:
            if gap_start is None:
                gap_start = frame
            active_wrong = None
            active_lost = None
        else:
            if gap_start is not None:
                recovery_pending = {
                    "reference_gap_start_frame_index": gap_start,
                    "first_reappearance_frame_index": frame,
                    "first_correct_frame_index": None,
                    "frames_to_correct_reacquisition": None,
                }
                reappearances.append(recovery_pending)
                gap_start = None
            if bucket == CORRECT and recovery_pending is not None:
                recovery_pending["first_correct_frame_index"] = frame
                recovery_pending["frames_to_correct_reacquisition"] = (
                    frame - int(recovery_pending["first_reappearance_frame_index"])
                )
                recovery_pending = None

            if bucket == WRONG_PERSON:
                identity = record["matched_identity"]
                if identity is None:
                    raise ValueError("wrong-person frame lacks physical identity")
                if adjacent and previous_bucket == CORRECT:
                    correct_to_wrong += 1
                if (
                    active_wrong is None
                    or active_wrong["matched_identity"] != int(identity)
                    or not adjacent
                ):
                    active_wrong = {
                        "start_frame_index": frame,
                        "end_frame_index": frame,
                        "matched_identity": int(identity),
                    }
                    wrong_events.append(active_wrong)
                else:
                    active_wrong["end_frame_index"] = frame
            else:
                active_wrong = None

            if bucket == LOST_SUPPRESSED:
                if active_lost is None or not adjacent:
                    active_lost = {
                        "start_frame_index": frame,
                        "end_frame_index": frame,
                        "length_frames": 1,
                    }
                    lost_runs.append(active_lost)
                else:
                    active_lost["end_frame_index"] = frame
                    active_lost["length_frames"] += 1
            else:
                active_lost = None

        previous_frame = frame
        previous_bucket = bucket

    return {
        "wrong_person_events": wrong_events,
        "wrong_person_event_count": len(wrong_events),
        "correct_to_wrong_handover_count": correct_to_wrong,
        "lost_runs": lost_runs,
        "reference_gap_reappearances": reappearances,
        "reference_gap_reappearance_count": len(reappearances),
        "successful_correct_reacquisition_count": sum(
            event["first_correct_frame_index"] is not None
            for event in reappearances
        ),
    }
