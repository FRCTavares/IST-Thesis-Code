#!/usr/bin/env python3
"""Deterministic target-candidate analysis for external sequences.

This module computes objective annotation-derived facts. It does not inspect
TIM-MARS outcomes and does not freeze a benchmark sequence automatically.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from external_tracking_dataset import ExternalObjectAnnotation


BBoxXYXY = tuple[float, float, float, float]


@dataclass(frozen=True)
class SelectionPolicy:
    minimum_visible_frames: int = 30
    minimum_consecutive_frames: int = 5
    initialization_window_frames: int = 10
    minimum_initialization_height_px: float = 40.0
    minimum_visibility: Optional[float] = 0.40
    maximum_initialization_occlusion: Optional[int] = 1
    border_margin_px: float = 2.0
    competition_iou_threshold: float = 0.05
    close_centre_distance_norm: float = 0.15

    def __post_init__(self) -> None:
        if self.minimum_visible_frames <= 0:
            raise ValueError("minimum_visible_frames must be positive")
        if self.minimum_consecutive_frames <= 0:
            raise ValueError("minimum_consecutive_frames must be positive")
        if self.initialization_window_frames <= 0:
            raise ValueError(
                "initialization_window_frames must be positive"
            )
        if (
            not math.isfinite(self.minimum_initialization_height_px)
            or self.minimum_initialization_height_px <= 0.0
        ):
            raise ValueError(
                "minimum_initialization_height_px must be finite and positive"
            )
        if (
            self.minimum_visibility is not None
            and not 0.0 <= self.minimum_visibility <= 1.0
        ):
            raise ValueError("minimum_visibility must be in [0, 1]")
        if (
            self.maximum_initialization_occlusion is not None
            and self.maximum_initialization_occlusion < 0
        ):
            raise ValueError(
                "maximum_initialization_occlusion must be non-negative"
            )
        if not math.isfinite(self.border_margin_px):
            raise ValueError("border_margin_px must be finite")
        if self.border_margin_px < 0.0:
            raise ValueError("border_margin_px must be non-negative")
        if not 0.0 <= self.competition_iou_threshold <= 1.0:
            raise ValueError(
                "competition_iou_threshold must be in [0, 1]"
            )
        if self.close_centre_distance_norm < 0.0:
            raise ValueError(
                "close_centre_distance_norm must be non-negative"
            )


@dataclass(frozen=True)
class TargetCandidateAnalysis:
    identity: int
    first_frame_index: int
    last_frame_index: int
    visible_frame_count: int
    visible_span_frames: int
    longest_consecutive_run: int
    median_height_px: float
    minimum_height_px: float
    median_visibility: Optional[float]
    maximum_occlusion: Optional[int]
    border_touch_frames: int
    competing_person_frames: int
    overlapping_person_frames: int
    close_person_frames: int
    initialization_start_frame: Optional[int]
    initialization_end_frame_inclusive: Optional[int]
    initialization_eligible: bool
    eligible: bool
    exclusion_reasons: tuple[str, ...]


def _bbox_iou(a: BBoxXYXY, b: BBoxXYXY) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    intersection = (
        max(0.0, ix2 - ix1)
        * max(0.0, iy2 - iy1)
    )
    if intersection <= 0.0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection

    if union <= 0.0:
        return 0.0

    return intersection / union


def _centre_distance_norm(
    a: BBoxXYXY,
    b: BBoxXYXY,
    *,
    image_width: int,
    image_height: int,
) -> float:
    acx = (a[0] + a[2]) / 2.0
    acy = (a[1] + a[3]) / 2.0
    bcx = (b[0] + b[2]) / 2.0
    bcy = (b[1] + b[3]) / 2.0

    diagonal = math.hypot(image_width, image_height)
    if diagonal <= 0.0:
        raise ValueError("image diagonal must be positive")

    return math.hypot(acx - bcx, acy - bcy) / diagonal


def _longest_consecutive_run(frame_indices: Sequence[int]) -> int:
    if not frame_indices:
        return 0

    longest = 1
    current = 1

    for previous, current_frame in zip(
        frame_indices,
        frame_indices[1:],
    ):
        if current_frame == previous + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)

    return longest


def _touches_border(
    row: ExternalObjectAnnotation,
    margin: float,
) -> bool:
    x1, y1, x2, y2 = row.bbox_xyxy
    return (
        x1 <= margin
        or y1 <= margin
        or x2 >= row.image_width - margin
        or y2 >= row.image_height - margin
    )


def _initialization_window(
    rows: Sequence[ExternalObjectAnnotation],
    policy: SelectionPolicy,
) -> tuple[Optional[int], Optional[int]]:
    required = policy.initialization_window_frames

    run_start: Optional[int] = None
    previous_frame: Optional[int] = None
    run_length = 0

    for row in rows:
        quality_ok = (
            row.height >= policy.minimum_initialization_height_px
        )

        if (
            policy.minimum_visibility is not None
            and row.visibility is not None
            and row.visibility < policy.minimum_visibility
        ):
            quality_ok = False

        if (
            policy.maximum_initialization_occlusion is not None
            and row.occlusion is not None
            and row.occlusion
            > policy.maximum_initialization_occlusion
        ):
            quality_ok = False

        if not quality_ok:
            run_start = None
            previous_frame = None
            run_length = 0
            continue

        frame = row.normalized_frame_index

        if previous_frame is not None and frame == previous_frame + 1:
            run_length += 1
        else:
            run_start = frame
            run_length = 1

        previous_frame = frame

        if run_length >= required:
            assert run_start is not None
            return run_start, frame

    return None, None


def analyse_target_candidates(
    annotations: Iterable[ExternalObjectAnnotation],
    *,
    policy: SelectionPolicy,
) -> list[TargetCandidateAnalysis]:
    included = [
        row
        for row in annotations
        if row.include_as_person_candidate
    ]

    if not included:
        return []

    sequence_keys = {
        (
            row.dataset,
            row.sequence_name,
            row.split,
            row.image_width,
            row.image_height,
        )
        for row in included
    }

    if len(sequence_keys) != 1:
        raise ValueError(
            "annotations must belong to exactly one sequence geometry"
        )

    rows_by_frame: dict[int, list[ExternalObjectAnnotation]] = {}
    rows_by_identity: dict[int, list[ExternalObjectAnnotation]] = {}

    for row in included:
        rows_by_frame.setdefault(
            row.normalized_frame_index,
            [],
        ).append(row)
        rows_by_identity.setdefault(row.identity, []).append(row)

    results: list[TargetCandidateAnalysis] = []

    for identity in sorted(rows_by_identity):
        target_rows = sorted(
            rows_by_identity[identity],
            key=lambda row: (
                row.normalized_frame_index,
                row.source_line_number,
            ),
        )

        frame_indices = [
            row.normalized_frame_index
            for row in target_rows
        ]
        heights = [row.height for row in target_rows]
        visibility_values = [
            row.visibility
            for row in target_rows
            if row.visibility is not None
        ]
        occlusion_values = [
            row.occlusion
            for row in target_rows
            if row.occlusion is not None
        ]

        border_touch_frames = sum(
            _touches_border(row, policy.border_margin_px)
            for row in target_rows
        )

        competing_person_frames = 0
        overlapping_person_frames = 0
        close_person_frames = 0

        for target_row in target_rows:
            competitors = [
                row
                for row in rows_by_frame[
                    target_row.normalized_frame_index
                ]
                if row.identity != identity
            ]

            if competitors:
                competing_person_frames += 1

            if any(
                _bbox_iou(
                    target_row.bbox_xyxy,
                    competitor.bbox_xyxy,
                )
                >= policy.competition_iou_threshold
                for competitor in competitors
            ):
                overlapping_person_frames += 1

            if any(
                _centre_distance_norm(
                    target_row.bbox_xyxy,
                    competitor.bbox_xyxy,
                    image_width=target_row.image_width,
                    image_height=target_row.image_height,
                )
                <= policy.close_centre_distance_norm
                for competitor in competitors
            ):
                close_person_frames += 1

        initialization_start, initialization_end = (
            _initialization_window(target_rows, policy)
        )
        initialization_eligible = (
            initialization_start is not None
            and initialization_end is not None
        )

        visible_count = len(frame_indices)
        longest_run = _longest_consecutive_run(frame_indices)

        exclusion_reasons: list[str] = []

        if visible_count < policy.minimum_visible_frames:
            exclusion_reasons.append("insufficient_visible_frames")

        if longest_run < policy.minimum_consecutive_frames:
            exclusion_reasons.append(
                "insufficient_consecutive_visibility"
            )

        if not initialization_eligible:
            exclusion_reasons.append(
                "no_clean_initialization_window"
            )

        results.append(
            TargetCandidateAnalysis(
                identity=identity,
                first_frame_index=frame_indices[0],
                last_frame_index=frame_indices[-1],
                visible_frame_count=visible_count,
                visible_span_frames=(
                    frame_indices[-1] - frame_indices[0] + 1
                ),
                longest_consecutive_run=longest_run,
                median_height_px=float(statistics.median(heights)),
                minimum_height_px=min(heights),
                median_visibility=(
                    float(statistics.median(visibility_values))
                    if visibility_values
                    else None
                ),
                maximum_occlusion=(
                    max(occlusion_values)
                    if occlusion_values
                    else None
                ),
                border_touch_frames=border_touch_frames,
                competing_person_frames=competing_person_frames,
                overlapping_person_frames=overlapping_person_frames,
                close_person_frames=close_person_frames,
                initialization_start_frame=initialization_start,
                initialization_end_frame_inclusive=initialization_end,
                initialization_eligible=initialization_eligible,
                eligible=not exclusion_reasons,
                exclusion_reasons=tuple(exclusion_reasons),
            )
        )

    return sorted(
        results,
        key=lambda item: (
            not item.eligible,
            -item.visible_frame_count,
            -item.longest_consecutive_run,
            -item.competing_person_frames,
            item.border_touch_frames,
            item.identity,
        ),
    )
