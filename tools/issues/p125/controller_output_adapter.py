#!/usr/bin/env python3
"""Normalize existing controller-facing outputs for the Issue #125 scorer.

The adapters accept already computed runtime results. They do not execute
detectors, trackers, Target-ReID, or TIM-MARS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class ControllerObservation:
    bbox_xyxy: BBox | None
    tracker_identity: int | None

    def __post_init__(self) -> None:
        if self.bbox_xyxy is None:
            if self.tracker_identity is not None:
                raise ValueError("tracker identity requires a published box")
            return
        if len(self.bbox_xyxy) != 4:
            raise ValueError("published box must have four coordinates")
        x1, y1, x2, y2 = self.bbox_xyxy
        if not all(math.isfinite(float(value)) for value in self.bbox_xyxy):
            raise ValueError("published box coordinates must be finite")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("published box must have positive area")
        if self.tracker_identity is None or self.tracker_identity <= 0:
            raise ValueError("published box requires a positive tracker identity")


NO_OUTPUT = ControllerObservation(None, None)


def from_raw_tracker(
    tracks: Sequence[Any], *, selected_track_id: int
) -> ControllerObservation:
    """Use only the operator-initialized identity from a tracker backend."""
    if selected_track_id <= 0:
        raise ValueError("selected track identity must be positive")
    selected = [
        track for track in tracks
        if int(track.track_id) == selected_track_id
    ]
    if len(selected) > 1:
        raise ValueError("duplicate selected tracker identity in one frame")
    if not selected:
        return NO_OUTPUT
    track = selected[0]
    return ControllerObservation(tuple(track.bbox_xyxy), selected_track_id)


def from_target_reid(result: Any) -> ControllerObservation:
    """Use the published decision from TargetReIdRuntimeResult."""
    decision = result.decision
    candidate = decision.selected_candidate
    if not decision.published:
        if candidate is not None:
            raise ValueError("unpublished Target-ReID decision has a candidate")
        return NO_OUTPUT
    if candidate is None:
        raise ValueError("published Target-ReID decision lacks a candidate")
    return ControllerObservation(
        tuple(candidate.bbox_xyxy), int(candidate.track_id)
    )


def from_tim_mars(result: Any) -> ControllerObservation:
    """Use only the control-valid published target, never candidate belief."""
    output = result.output
    if not output.control_valid:
        return NO_OUTPUT
    if output.bbox is None or output.target_track_id is None:
        raise ValueError("control-valid TIM-MARS output lacks target geometry or ID")
    return ControllerObservation(
        tuple(output.bbox), int(output.target_track_id)
    )


def observation_maps(
    observations: Iterable[tuple[int, ControllerObservation]],
) -> tuple[dict[int, BBox | None], dict[int, int | None]]:
    """Build the scorer's two maps without filling absent source frames."""
    boxes: dict[int, BBox | None] = {}
    identities: dict[int, int | None] = {}
    for frame, observation in observations:
        if not isinstance(frame, int) or frame < 0:
            raise ValueError("normalized source frame must be non-negative integer")
        if frame in boxes:
            raise ValueError(f"duplicate output for source frame {frame}")
        boxes[frame] = observation.bbox_xyxy
        identities[frame] = observation.tracker_identity
    return boxes, identities
