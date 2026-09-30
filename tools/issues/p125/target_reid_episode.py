#!/usr/bin/env python3
"""Apply the existing Target-ReID runtime to one frozen GT episode."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from controller_output_adapter import NO_OUTPUT, from_target_reid, observation_maps  # noqa: E402

def track_message(frame: dict[str, Any]) -> SimpleNamespace:
    """Present recorded pixel-space ByteTrack boxes to the ROS-free runtime."""
    stamp_ns = int(frame["logical_frame_stamp_ns"])
    if stamp_ns <= 0:
        raise ValueError("Target-ReID requires a positive logical source stamp")
    tracks = []
    for track in frame["tracks"]:
        x1, y1, x2, y2 = (float(value) for value in track["bbox_xyxy"])
        tracks.append(SimpleNamespace(
            id=int(track["track_id"]),
            score=float(track["score"]),
            cx=(x1 + x2) / 2,
            cy=(y1 + y2) / 2,
            w=x2 - x1,
            h=y2 - y1,
        ))
    return SimpleNamespace(
        frame_id=int(frame["source_frame_number"]),
        src_stamp_ns=stamp_ns,
        tracks=tracks,
    )


def target_reid_authority_maps(
    *,
    tracker_frames: Sequence[dict[str, Any]],
    initialization: Any,
    runtime_factory: Callable[[int], Any],
    image_for_frame: Callable[[dict[str, Any]], Any],
) -> tuple[dict[int, tuple[float, float, float, float] | None], dict[int, int | None], int | None]:
    """Bootstrap on confirmation, then score only published decisions.

    The initialization frame is consumed by the baseline as an appearance
    anchor and never publishes controller output. Failed initialization keeps
    every frame as explicit no-output without opening images or a runtime.
    """
    if not tracker_frames:
        raise ValueError("Target-ReID requires source frames")
    source_indices = [int(frame["normalized_frame_index"]) for frame in tracker_frames]
    if len(source_indices) != len(set(source_indices)) or source_indices != sorted(source_indices):
        raise ValueError("Target-ReID source frames must be ordered and unique")
    observations = []
    if not initialization.success:
        return (*observation_maps((index, NO_OUTPUT) for index in source_indices), None)
    confirmation = initialization.initialization_frame_index
    selected_id = initialization.initial_tracker_identity
    if confirmation is None or selected_id is None or selected_id <= 0:
        raise ValueError("successful initialization lacks confirmation frame or ID")
    if confirmation not in source_indices:
        raise ValueError("confirmation frame is absent from tracker replay")
    runtime = runtime_factory(int(selected_id))
    bootstrap_frame = None
    for frame, index in zip(tracker_frames, source_indices, strict=True):
        if index < confirmation:
            observations.append((index, NO_OUTPUT))
            continue
        image = image_for_frame(frame)
        if image is None:
            raise ValueError(f"missing Target-ReID source image at frame {index}")
        stamp_ns = int(frame["logical_frame_stamp_ns"])
        if not runtime.add_image(stamp_ns, image):
            raise ValueError(f"Target-ReID rejected source image at frame {index}")
        result = runtime.process_tracks(track_message(frame))
        observation = from_target_reid(result)
        if index == confirmation:
            if observation != NO_OUTPUT:
                raise ValueError("Target-ReID published on its anchor bootstrap frame")
            if not result.anchor_ready:
                return (*observation_maps((source, NO_OUTPUT) for source in source_indices), None)
            bootstrap_frame = index
        observations.append((index, observation))
    boxes, identities = observation_maps(observations)
    return boxes, identities, bootstrap_frame
