#!/usr/bin/env python3
"""Map one frozen physical target to its initialization tracker identity.

The physical target is defined by dataset ground truth before TIM-MARS outcome
review. Tracker identities are temporary candidate labels and never redefine
which person is being evaluated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


BBoxXYXY = tuple[float, float, float, float]


@dataclass(frozen=True)
class PhysicalTargetObservation:
    normalized_frame_index: int
    dataset_identity: int | str
    bbox_xyxy: BBoxXYXY


@dataclass(frozen=True)
class TrackerCandidateObservation:
    normalized_frame_index: int
    tracker_identity: int
    bbox_xyxy: BBoxXYXY
    score: float


@dataclass(frozen=True)
class InitializationConfig:
    start_frame_index: int
    end_frame_index_inclusive: int
    minimum_iou: float = 0.50
    minimum_margin: float = 0.10
    confirmation_frames: int = 2

    def __post_init__(self) -> None:
        if self.start_frame_index < 0:
            raise ValueError("start_frame_index must be non-negative")
        if self.end_frame_index_inclusive < self.start_frame_index:
            raise ValueError(
                "end_frame_index_inclusive must not precede start"
            )
        if not 0.0 <= self.minimum_iou <= 1.0:
            raise ValueError("minimum_iou must be in [0, 1]")
        if not 0.0 <= self.minimum_margin <= 1.0:
            raise ValueError("minimum_margin must be in [0, 1]")
        if self.confirmation_frames <= 0:
            raise ValueError("confirmation_frames must be positive")


@dataclass(frozen=True)
class FrameMatch:
    normalized_frame_index: int
    tracker_identity: Optional[int]
    best_iou: Optional[float]
    second_iou: Optional[float]
    margin: Optional[float]
    accepted: bool
    reason: str


@dataclass(frozen=True)
class InitializationResult:
    dataset_identity: int | str
    initial_tracker_identity: Optional[int]
    initialization_frame_index: Optional[int]
    confirmed_frames: int
    success: bool
    reason: str
    frame_matches: tuple[FrameMatch, ...]


def bbox_iou(a: BBoxXYXY, b: BBoxXYXY) -> float:
    if not all(math.isfinite(value) for value in (*a, *b)):
        raise ValueError("bbox coordinates must be finite")

    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    if ax2 <= ax1 or ay2 <= ay1:
        raise ValueError("first bbox must have positive area")
    if bx2 <= bx1 or by2 <= by1:
        raise ValueError("second bbox must have positive area")

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

    return min(1.0, max(0.0, intersection / union))


def _group_candidates(
    candidates: Iterable[TrackerCandidateObservation],
) -> dict[int, list[TrackerCandidateObservation]]:
    grouped: dict[int, list[TrackerCandidateObservation]] = {}

    for candidate in candidates:
        if candidate.normalized_frame_index < 0:
            raise ValueError("candidate frame index must be non-negative")
        if candidate.tracker_identity <= 0:
            raise ValueError("tracker_identity must be positive")
        if not math.isfinite(candidate.score):
            raise ValueError("candidate score must be finite")

        grouped.setdefault(
            candidate.normalized_frame_index,
            [],
        ).append(candidate)

    for frame_candidates in grouped.values():
        frame_candidates.sort(
            key=lambda item: item.tracker_identity
        )

    return grouped


def match_frame(
    target: PhysicalTargetObservation,
    candidates: Sequence[TrackerCandidateObservation],
    config: InitializationConfig,
) -> FrameMatch:
    scored = sorted(
        (
            (
                bbox_iou(target.bbox_xyxy, candidate.bbox_xyxy),
                candidate,
            )
            for candidate in candidates
        ),
        key=lambda item: (
            -item[0],
            -item[1].score,
            item[1].tracker_identity,
        ),
    )

    if not scored:
        return FrameMatch(
            normalized_frame_index=target.normalized_frame_index,
            tracker_identity=None,
            best_iou=None,
            second_iou=None,
            margin=None,
            accepted=False,
            reason="no_tracker_candidates",
        )

    best_iou, best_candidate = scored[0]
    second_iou = scored[1][0] if len(scored) > 1 else None
    margin = (
        best_iou - second_iou
        if second_iou is not None
        else best_iou
    )

    if best_iou < config.minimum_iou:
        reason = "best_iou_below_threshold"
        accepted = False
    elif margin < config.minimum_margin:
        reason = "ambiguous_candidate_margin"
        accepted = False
    else:
        reason = "unique_spatial_match"
        accepted = True

    return FrameMatch(
        normalized_frame_index=target.normalized_frame_index,
        tracker_identity=best_candidate.tracker_identity,
        best_iou=best_iou,
        second_iou=second_iou,
        margin=margin,
        accepted=accepted,
        reason=reason,
    )


def initialize_frozen_target(
    *,
    dataset_identity: int | str,
    target_observations: Iterable[PhysicalTargetObservation],
    tracker_candidates: Iterable[TrackerCandidateObservation],
    config: InitializationConfig,
) -> InitializationResult:
    targets_by_frame: dict[int, PhysicalTargetObservation] = {}

    for target in target_observations:
        if target.dataset_identity != dataset_identity:
            continue
        if target.normalized_frame_index in targets_by_frame:
            raise ValueError(
                "duplicate physical-target observation for frame "
                f"{target.normalized_frame_index}"
            )
        targets_by_frame[target.normalized_frame_index] = target

    candidates_by_frame = _group_candidates(tracker_candidates)

    frame_matches: list[FrameMatch] = []
    active_tracker_identity: Optional[int] = None
    confirmation_count = 0

    for frame_index in range(
        config.start_frame_index,
        config.end_frame_index_inclusive + 1,
    ):
        target = targets_by_frame.get(frame_index)

        if target is None:
            frame_matches.append(
                FrameMatch(
                    normalized_frame_index=frame_index,
                    tracker_identity=None,
                    best_iou=None,
                    second_iou=None,
                    margin=None,
                    accepted=False,
                    reason="physical_target_not_visible",
                )
            )
            active_tracker_identity = None
            confirmation_count = 0
            continue

        match = match_frame(
            target,
            candidates_by_frame.get(frame_index, ()),
            config,
        )
        frame_matches.append(match)

        if not match.accepted:
            active_tracker_identity = None
            confirmation_count = 0
            continue

        if match.tracker_identity == active_tracker_identity:
            confirmation_count += 1
        else:
            active_tracker_identity = match.tracker_identity
            confirmation_count = 1

        if confirmation_count >= config.confirmation_frames:
            return InitializationResult(
                dataset_identity=dataset_identity,
                initial_tracker_identity=active_tracker_identity,
                initialization_frame_index=frame_index,
                confirmed_frames=confirmation_count,
                success=True,
                reason="frozen_target_tracker_match_confirmed",
                frame_matches=tuple(frame_matches),
            )

    return InitializationResult(
        dataset_identity=dataset_identity,
        initial_tracker_identity=None,
        initialization_frame_index=None,
        confirmed_frames=0,
        success=False,
        reason="no_confirmed_initial_tracker_match",
        frame_matches=tuple(frame_matches),
    )
