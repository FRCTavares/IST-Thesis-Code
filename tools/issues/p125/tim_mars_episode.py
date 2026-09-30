#!/usr/bin/env python3
"""Apply the canonical TIM-MARS runtime to one frozen GT episode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from controller_output_adapter import NO_OUTPUT, from_tim_mars, observation_maps  # noqa: E402
from target_reid_episode import track_message  # noqa: E402


def tim_mars_authority_maps(
    *,
    tracker_frames: Sequence[dict[str, Any]],
    initialization: Any,
    runtime_factory: Callable[[int], Any],
    image_for_frame: Callable[[dict[str, Any]], Any],
) -> tuple[dict[int, tuple[float, float, float, float] | None], dict[int, int | None]]:
    """Select on confirmed ByteTrack frame and retain only control-valid output."""
    if not tracker_frames:
        raise ValueError("TIM-MARS requires source frames")
    indices = [int(frame["normalized_frame_index"]) for frame in tracker_frames]
    if indices != sorted(set(indices)):
        raise ValueError("TIM-MARS source frames must be ordered and unique")
    if not initialization.success:
        return observation_maps((index, NO_OUTPUT) for index in indices)
    confirmation = initialization.initialization_frame_index
    selected_id = initialization.initial_tracker_identity
    if confirmation is None or selected_id is None or selected_id <= 0:
        raise ValueError("successful initialization lacks confirmation frame or ID")
    if confirmation not in indices:
        raise ValueError("confirmation frame is absent from tracker replay")
    runtime = runtime_factory(int(selected_id))
    observations = []
    for frame, index in zip(tracker_frames, indices, strict=True):
        if index < confirmation:
            observations.append((index, NO_OUTPUT))
            continue
        image = image_for_frame(frame)
        if image is None:
            raise ValueError(f"missing TIM-MARS source image at frame {index}")
        stamp_ns = int(frame["logical_frame_stamp_ns"])
        if not runtime.add_image(stamp_ns, image):
            raise ValueError(f"TIM-MARS rejected source image at frame {index}")
        result = runtime.process_tracks(track_message(frame))
        observations.append((index, from_tim_mars(result)))
    return observation_maps(observations)
