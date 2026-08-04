"""Pure staging of causally identified appearance request crops.

This module converts already-selected TIM-MARS candidate observations into
owned immutable BGR crops. It performs no ROS publication, queueing, Hailo
inference, embedding-cache update, or target-memory decision.

Frame and track generations are supplied by AppearanceAttachmentState, which
remains the single lifecycle authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from thesis_bringup.tim_mars.appearance_attachment import (
    map_bbox_to_appearance_image,
)
from thesis_bringup.tim_mars.appearance_memory import extract_crop
from thesis_bringup.tim_mars.target_memory import (
    BBox,
    CandidateTrack,
)


@dataclass(frozen=True)
class AppearanceRequestCrop:
    """One immutable candidate crop with complete source provenance."""

    source_frame_id: int
    track_timestamp_ns: int
    source_image_timestamp_ns: int
    source_image_seq: int

    frame_generation: int
    candidate_index: int
    track_id: int
    track_generation: int

    source_bbox: BBox
    crop_bgr: Any = field(
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if int(self.source_frame_id) <= 0:
            raise ValueError(
                "source_frame_id must be positive"
            )

        if int(self.track_timestamp_ns) <= 0:
            raise ValueError(
                "track_timestamp_ns must be positive"
            )

        if int(self.source_image_timestamp_ns) <= 0:
            raise ValueError(
                "source_image_timestamp_ns must be positive"
            )

        if (
            int(self.source_image_timestamp_ns)
            > int(self.track_timestamp_ns)
        ):
            raise ValueError(
                "source image must not be newer than tracks"
            )

        if int(self.source_image_seq) < 0:
            raise ValueError(
                "source_image_seq must be non-negative"
            )

        if int(self.frame_generation) <= 0:
            raise ValueError(
                "frame_generation must be positive"
            )

        if int(self.candidate_index) < 0:
            raise ValueError(
                "candidate_index must be non-negative"
            )

        if int(self.track_id) <= 0:
            raise ValueError(
                "track_id must be positive"
            )

        if int(self.track_generation) <= 0:
            raise ValueError(
                "track_generation must be positive"
            )

        bbox = tuple(
            float(value)
            for value in self.source_bbox
        )

        if len(bbox) != 4:
            raise ValueError(
                "source_bbox must contain four values"
            )

        if not np.all(np.isfinite(bbox)):
            raise ValueError(
                "source_bbox must be finite"
            )

        crop = np.asarray(self.crop_bgr)

        if crop.dtype != np.uint8:
            raise ValueError(
                "request crop must have dtype uint8"
            )

        if crop.ndim != 3 or crop.shape[2] != 3:
            raise ValueError(
                "request crop must be a three-channel image"
            )

        if crop.shape[0] <= 0 or crop.shape[1] <= 0:
            raise ValueError(
                "request crop must have positive dimensions"
            )

        owned = np.ascontiguousarray(
            crop.copy(),
            dtype=np.uint8,
        )
        owned.setflags(write=False)

        object.__setattr__(
            self,
            "source_bbox",
            bbox,
        )
        object.__setattr__(
            self,
            "crop_bgr",
            owned,
        )


def _resolved_requested_indices(
    *,
    candidate_count: int,
    requested_candidate_indices: Sequence[int],
) -> tuple[int, ...]:
    indices = tuple(
        int(index)
        for index in requested_candidate_indices
    )

    if len(set(indices)) != len(indices):
        raise ValueError(
            "request crop indices contain duplicates"
        )

    invalid = tuple(
        index
        for index in indices
        if index < 0 or index >= int(candidate_count)
    )

    if invalid:
        raise ValueError(
            "request crop indices are out of range: "
            + ", ".join(str(index) for index in invalid)
        )

    return indices


def build_appearance_request_crops(
    *,
    candidates: Sequence[CandidateTrack],
    requested_candidate_indices: Sequence[int],
    crop_quality_by_track_id: Mapping[int, Any],
    image_bgr: Any,
    candidate_frame_width: float,
    candidate_frame_height: float,
    source_frame_id: int,
    track_timestamp_ns: int,
    source_image_timestamp_ns: int,
    source_image_seq: int,
    frame_generation: int,
    track_generation_by_id: Mapping[int, int],
) -> tuple[AppearanceRequestCrop, ...]:
    """Build owned crops for requested and encoding-eligible candidates."""
    candidate_tuple = tuple(candidates)
    indices = _resolved_requested_indices(
        candidate_count=len(candidate_tuple),
        requested_candidate_indices=(
            requested_candidate_indices
        ),
    )

    image = np.asarray(image_bgr)

    if (
        image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
    ):
        raise ValueError(
            "appearance source image must be uint8 BGR"
        )

    image_height = int(image.shape[0])
    image_width = int(image.shape[1])

    if image_height <= 0 or image_width <= 0:
        raise ValueError(
            "appearance source image must be non-empty"
        )

    staged: list[AppearanceRequestCrop] = []

    for candidate_index in indices:
        candidate = candidate_tuple[candidate_index]
        track_id = int(candidate.track_id)

        quality = crop_quality_by_track_id.get(
            track_id
        )

        if (
            quality is None
            or not bool(
                getattr(
                    quality,
                    "encoding_eligible",
                    False,
                )
            )
        ):
            continue

        track_generation = int(
            track_generation_by_id.get(
                track_id,
                0,
            )
        )

        if track_generation <= 0:
            raise ValueError(
                "requested candidate has no active "
                f"track generation: {track_id}"
            )

        candidate_bbox = (
            candidate.unclipped_bbox
            if candidate.unclipped_bbox is not None
            else candidate.bbox
        )

        mapped_bbox = map_bbox_to_appearance_image(
            candidate_bbox,
            candidate_frame_width=(
                float(candidate_frame_width)
            ),
            candidate_frame_height=(
                float(candidate_frame_height)
            ),
            image_width=image_width,
            image_height=image_height,
        )

        crop = extract_crop(
            image,
            mapped_bbox,
            min_height=1.0,
        )

        if crop is None:
            raise ValueError(
                "encoding-eligible candidate produced "
                f"no crop: index={candidate_index}, "
                f"track_id={track_id}"
            )

        staged.append(
            AppearanceRequestCrop(
                source_frame_id=int(source_frame_id),
                track_timestamp_ns=int(
                    track_timestamp_ns
                ),
                source_image_timestamp_ns=int(
                    source_image_timestamp_ns
                ),
                source_image_seq=int(source_image_seq),
                frame_generation=int(
                    frame_generation
                ),
                candidate_index=int(
                    candidate_index
                ),
                track_id=track_id,
                track_generation=track_generation,
                source_bbox=mapped_bbox,
                crop_bgr=crop,
            )
        )

    return tuple(staged)


__all__ = [
    "AppearanceRequestCrop",
    "build_appearance_request_crops",
]
