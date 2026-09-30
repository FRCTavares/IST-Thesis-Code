#!/usr/bin/env python3
"""Frame-level physical-person attribution for the Issue #125 protocol.

This module has no detector or tracker dependency. It classifies an already
supplied controller-facing box against official person ground truth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

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
