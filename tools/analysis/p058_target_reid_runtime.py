"""ROS-free runtime adapter for the Issue #58 Target-ReID baseline.

This adapter owns only the neutral mechanics required to apply the frozen
post-MOT Target-ReID decision rule to timestamped tracker observations:

- deterministic causal image selection;
- the same MARS-small128 extractor used by TIM-MARS;
- tracker-box conversion into pixel-space xyxy;
- immutable operator-anchor bootstrap;
- stateless per-frame Target-ReID selection.

It deliberately does not instantiate TimMarsRuntime or TargetIdentityMemory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from thesis_bringup.tim_mars.mars_reid_backend import MarsReIdBackend
from thesis_tracker.backends.deepsort_core_backend import CausalImageBuffer

from p058_target_reid_baseline import (
    TargetReIdCandidate,
    TargetReIdDecision,
    select_target_reid_candidate,
)


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class TargetReIdRuntimeResult:
    """One deterministic Target-ReID update."""

    decision: TargetReIdDecision
    anchor_ready: bool
    selected_image_timestamp_ns: int | None
    image_age_ms: float | None
    candidate_count: int
    embeddings_valid: int


class TargetReIdRuntime:
    """Minimal stateful runtime for the simple Target-ReID baseline."""

    def __init__(
        self,
        *,
        model_path: str,
        selected_track_id: int,
        threshold: float,
        image_width: float,
        image_height: float,
        tracks_are_normalized: bool = False,
        max_image_age_ms: float = 250.0,
        image_buffer_size: int = 64,
        batch_size: int = 32,
        mars_backend: Any | None = None,
    ) -> None:
        self.selected_track_id = int(selected_track_id)
        if self.selected_track_id <= 0:
            raise ValueError("selected_track_id must be positive")

        self.threshold = float(threshold)
        if not np.isfinite(self.threshold):
            raise ValueError("threshold must be finite")

        self.image_width = float(image_width)
        self.image_height = float(image_height)

        if self.image_width <= 0.0 or self.image_height <= 0.0:
            raise ValueError("image dimensions must be positive")

        self.tracks_are_normalized = bool(tracks_are_normalized)
        self.max_image_age_ns = int(
            max(0.0, float(max_image_age_ms)) * 1_000_000.0
        )

        self._images = CausalImageBuffer(
            max_size=max(1, int(image_buffer_size))
        )

        self._mars = (
            mars_backend
            if mars_backend is not None
            else MarsReIdBackend(
                model_path,
                batch_size=max(1, int(batch_size)),
            )
        )

        self._anchor: np.ndarray | None = None

    @property
    def anchor_ready(self) -> bool:
        return self._anchor is not None

    @staticmethod
    def stamp_to_ns(stamp: Any) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    @classmethod
    def track_time_ns(cls, tracks_msg: Any) -> int:
        header = getattr(tracks_msg, "header", None)
        stamp = getattr(header, "stamp", None)

        if stamp is not None:
            header_ns = cls.stamp_to_ns(stamp)
            if header_ns > 0:
                return header_ns

        source_ns = int(getattr(tracks_msg, "src_stamp_ns", 0))
        if source_ns > 0:
            return source_ns

        return 0

    def add_image(self, stamp_ns: int, image_bgr: Any) -> bool:
        return self._images.add(int(stamp_ns), image_bgr)

    def _track_bbox_xyxy(self, track: Any) -> BBox:
        cx = float(track.cx)
        cy = float(track.cy)
        width = float(track.w)
        height = float(track.h)

        if self.tracks_are_normalized:
            cx *= self.image_width
            width *= self.image_width
            cy *= self.image_height
            height *= self.image_height

        x1 = max(0.0, min(self.image_width, cx - 0.5 * width))
        y1 = max(0.0, min(self.image_height, cy - 0.5 * height))
        x2 = max(0.0, min(self.image_width, cx + 0.5 * width))
        y2 = max(0.0, min(self.image_height, cy + 0.5 * height))

        return x1, y1, x2, y2

    def _lost_result(
        self,
        *,
        anchor_ready: bool,
        selected_image_timestamp_ns: int | None,
        image_age_ms: float | None,
        candidate_count: int,
        embeddings_valid: int,
    ) -> TargetReIdRuntimeResult:
        decision = select_target_reid_candidate(
            anchor=self._anchor,
            candidates=(),
            threshold=self.threshold,
        )

        return TargetReIdRuntimeResult(
            decision=decision,
            anchor_ready=anchor_ready,
            selected_image_timestamp_ns=selected_image_timestamp_ns,
            image_age_ms=image_age_ms,
            candidate_count=candidate_count,
            embeddings_valid=embeddings_valid,
        )

    def process_tracks(self, tracks_msg: Any) -> TargetReIdRuntimeResult:
        track_timestamp_ns = self.track_time_ns(tracks_msg)
        tracks = tuple(getattr(tracks_msg, "tracks", ()))

        if track_timestamp_ns <= 0:
            return self._lost_result(
                anchor_ready=self.anchor_ready,
                selected_image_timestamp_ns=None,
                image_age_ms=None,
                candidate_count=len(tracks),
                embeddings_valid=0,
            )

        image = self._images.select(
            track_timestamp_ns,
            self.max_image_age_ns,
        )

        if image is None:
            return self._lost_result(
                anchor_ready=self.anchor_ready,
                selected_image_timestamp_ns=None,
                image_age_ms=None,
                candidate_count=len(tracks),
                embeddings_valid=0,
            )

        image_age_ms = (
            float(track_timestamp_ns - image.stamp_ns) / 1_000_000.0
        )

        boxes = [
            self._track_bbox_xyxy(track)
            for track in tracks
        ]

        embeddings: Sequence[Any | None] = self._mars.encode(
            image.image_bgr,
            boxes,
        )

        candidates = tuple(
            TargetReIdCandidate(
                track_id=int(track.id),
                bbox_xyxy=box,
                appearance=embedding,
            )
            for track, box, embedding in zip(
                tracks,
                boxes,
                embeddings,
                strict=True,
            )
        )

        embeddings_valid = sum(
            candidate.appearance is not None
            for candidate in candidates
        )

        if self._anchor is None:
            for candidate in candidates:
                if (
                    candidate.track_id == self.selected_track_id
                    and candidate.appearance is not None
                ):
                    anchor = np.asarray(
                        candidate.appearance,
                        dtype=np.float32,
                    ).copy()

                    norm = float(np.linalg.norm(anchor))
                    if (
                        anchor.ndim == 1
                        and anchor.size > 0
                        and np.all(np.isfinite(anchor))
                        and norm > 1e-12
                    ):
                        self._anchor = anchor / norm
                    break

            # Initialization never publishes controller-facing output.
            return self._lost_result(
                anchor_ready=self.anchor_ready,
                selected_image_timestamp_ns=image.stamp_ns,
                image_age_ms=image_age_ms,
                candidate_count=len(candidates),
                embeddings_valid=embeddings_valid,
            )

        decision = select_target_reid_candidate(
            anchor=self._anchor,
            candidates=candidates,
            threshold=self.threshold,
        )

        return TargetReIdRuntimeResult(
            decision=decision,
            anchor_ready=True,
            selected_image_timestamp_ns=image.stamp_ns,
            image_age_ms=image_age_ms,
            candidate_count=len(candidates),
            embeddings_valid=embeddings_valid,
        )
