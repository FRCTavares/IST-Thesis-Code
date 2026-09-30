#!/usr/bin/env python3
"""Resolve frozen GT identity to one temporary tracker ID per episode.

The tracker has already processed the complete source sequence without GT.
GT enters only this post-tracker initialization and scoring boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "analysis"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    InitializationResult,
    PhysicalTargetObservation,
    TrackerCandidateObservation,
    initialize_frozen_target,
)
from controller_output_adapter import (  # noqa: E402
    ControllerObservation,
    NO_OUTPUT,
    from_raw_tracker,
    observation_maps,
)


def resolve_initialization(
    *,
    episode: dict[str, Any],
    gt_rows: Sequence[Any],
    tracker_frames: Sequence[dict[str, Any]],
    minimum_match_iou: float = 0.5,
    minimum_match_margin: float = 0.1,
    confirmation_frames: int = 2,
) -> InitializationResult:
    """Apply the existing unique-IoU confirmation rule to one GT episode."""
    identity = int(episode["dataset_identity"])
    start = int(episode["selection_frame_index"])
    end = int(episode["initialization_end_frame_inclusive"])
    if identity <= 0 or start < 0 or end < start:
        raise ValueError("invalid frozen episode initialization window")
    replay_by_frame = {
        int(frame["normalized_frame_index"]): frame for frame in tracker_frames
    }
    if len(replay_by_frame) != len(tracker_frames):
        raise ValueError("duplicate tracker source frame")
    if start not in replay_by_frame or end not in replay_by_frame:
        raise ValueError("initialization endpoint lacks tracker source frame")
    targets = [
        PhysicalTargetObservation(
            normalized_frame_index=int(row.normalized_frame_index),
            dataset_identity=identity,
            bbox_xyxy=tuple(row.bbox_xyxy),
        )
        for row in gt_rows
        if int(row.identity) == identity
        and bool(row.include_as_person_candidate)
        and start <= int(row.normalized_frame_index) <= end
    ]
    if not any(target.normalized_frame_index == start for target in targets):
        raise ValueError("frozen selection frame lacks target GT")
    candidates = [
        TrackerCandidateObservation(
            normalized_frame_index=int(frame["normalized_frame_index"]),
            tracker_identity=int(track["track_id"]),
            bbox_xyxy=tuple(track["bbox_xyxy"]),
            score=float(track["score"]),
        )
        for frame in tracker_frames
        if start <= int(frame["normalized_frame_index"]) <= end
        for track in frame["tracks"]
    ]
    return initialize_frozen_target(
        dataset_identity=identity,
        target_observations=targets,
        tracker_candidates=candidates,
        config=InitializationConfig(
            start_frame_index=start,
            end_frame_index_inclusive=end,
            minimum_iou=minimum_match_iou,
            minimum_margin=minimum_match_margin,
            confirmation_frames=confirmation_frames,
        ),
    )


def raw_authority_maps(
    *,
    tracker_frames: Sequence[dict[str, Any]],
    initialization: InitializationResult,
) -> tuple[dict[int, tuple[float, float, float, float] | None], dict[int, int | None]]:
    """Suppress authority before confirmation and retain failed initialization."""
    observations: list[tuple[int, ControllerObservation]] = []
    for frame in tracker_frames:
        frame_index = int(frame["normalized_frame_index"])
        if (
            not initialization.success
            or initialization.initialization_frame_index is None
            or initialization.initial_tracker_identity is None
            or frame_index < initialization.initialization_frame_index
        ):
            observation = NO_OUTPUT
        else:
            tracks = [
                SimpleNamespace(
                    track_id=int(track["track_id"]),
                    bbox_xyxy=tuple(track["bbox_xyxy"]),
                )
                for track in frame["tracks"]
            ]
            observation = from_raw_tracker(
                tracks,
                selected_track_id=int(initialization.initial_tracker_identity),
            )
        observations.append((frame_index, observation))
    return observation_maps(observations)
