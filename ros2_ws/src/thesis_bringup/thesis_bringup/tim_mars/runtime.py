"""Shared ROS-free processing runtime for TIM-MARS.

This module owns the deterministic conversion of tracker messages into
CandidateTrack objects, causal image selection, appearance attachment, and
TargetIdentityMemory updates.

It contains no subscriptions, publishers, timers, sleeps, or wall-clock
synchronisation. The ROS node and deterministic offline replay runner should
both delegate their algorithmic processing to this runtime.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field, replace
from typing import Any, Optional, Sequence

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
    AppearanceAttachmentInput,
    AppearanceAttachmentState,
    AppearanceEncoder,
    attach_appearance_features,
    reset_appearance_lifecycle,
)
from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
)
from thesis_bringup.tim_mars.target_memory import (
    BBox,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetMemoryOutput,
    TargetState,
)


@dataclass(frozen=True)
class TimMarsRuntimeConfig:
    """Configuration required by the shared TIM-MARS processing runtime."""

    memory: TargetMemoryConfig
    appearance: AppearanceAttachmentConfig
    image_width: float
    image_height: float
    tracks_are_normalized: bool = False
    selected_track_id: int = 0
    auto_select_largest: bool = False
    image_buffer_size: int = 64


@dataclass(frozen=True)
class AppearanceFrame:
    """Timestamped appearance image."""

    stamp_ns: int
    image_bgr: Any


@dataclass(frozen=True)
class TimMarsRuntimeDiagnostics:
    """Frame-level evidence correspondence and appearance diagnostics."""

    track_timestamp_ns: Optional[int]
    selected_image_timestamp_ns: Optional[int]
    image_track_offset_ms: Optional[float]
    appearance_candidates: int
    appearance_features_valid: int
    appearance_skip_reason: str
    appearance_warning: Optional[str]
    appearance_cache_size: int
    appearance_embedding_age_ms_by_track_id: dict[int, float]
    appearance_crop_quality_by_track_id: dict[
        int,
        AppearanceCropQuality,
    ]
    appearance_encoding_rejected: int
    appearance_memory_update_ineligible: int
    appearance_update_cooldown_remaining: int
    candidate_track_ids: tuple[int, ...]


@dataclass(frozen=True)
class TimMarsRuntimeResult:
    """One deterministic TIM-MARS update result."""

    output: TargetMemoryOutput
    candidates: tuple[CandidateTrack, ...]
    diagnostics: TimMarsRuntimeDiagnostics


@dataclass
class TimMarsRuntime:
    """ROS-free stateful TIM-MARS processor."""

    config: TimMarsRuntimeConfig
    mars_backend: AppearanceEncoder | None = None
    memory: TargetIdentityMemory = field(init=False)
    appearance_state: AppearanceAttachmentState = field(
        default_factory=AppearanceAttachmentState,
        init=False,
    )
    pending_select_id: Optional[int] = field(init=False)
    _images: list[AppearanceFrame] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.memory = TargetIdentityMemory(self.config.memory)
        selected_id = int(self.config.selected_track_id)
        self.pending_select_id = selected_id if selected_id > 0 else None

    @staticmethod
    def stamp_to_ns(stamp: Any) -> int:
        """Convert a ROS-style sec/nanosec timestamp to integer nanoseconds."""
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    @classmethod
    def track_time_ns(cls, tracks_msg: Any) -> Optional[int]:
        """Resolve the trustworthy timestamp of a tracker message."""
        header = getattr(tracks_msg, "header", None)
        stamp = getattr(header, "stamp", None)

        if stamp is not None:
            header_ns = cls.stamp_to_ns(stamp)
            if header_ns > 0:
                return header_ns

        source_ns = int(getattr(tracks_msg, "src_stamp_ns", 0))
        if source_ns > 0:
            return source_ns

        return None

    def add_image(self, stamp_ns: int, image_bgr: Any) -> bool:
        """Insert or replace a timestamped image in deterministic stamp order."""
        stamp_ns = int(stamp_ns)
        if stamp_ns <= 0:
            return False

        stamps = [frame.stamp_ns for frame in self._images]
        index = bisect_right(stamps, stamp_ns)

        if index > 0 and self._images[index - 1].stamp_ns == stamp_ns:
            self._images[index - 1] = AppearanceFrame(stamp_ns, image_bgr)
        else:
            self._images.insert(index, AppearanceFrame(stamp_ns, image_bgr))

        max_size = max(1, int(self.config.image_buffer_size))
        if len(self._images) > max_size:
            self._images = self._images[-max_size:]

        return True

    def replace_images(
        self,
        images: Sequence[tuple[int, Any]],
    ) -> None:
        """Replace images with a complete deterministic offline timeline.

        Unlike add_image(), this method does not apply the live buffer-size
        limit. It is intended for offline replay where every causal image must
        remain available for the complete track-message timeline.

        Duplicate timestamps are resolved deterministically using the final
        supplied value for that timestamp. Invalid timestamps are discarded.
        """
        images_by_stamp: dict[int, Any] = {}

        for stamp_ns, image_bgr in images:
            stamp_ns = int(stamp_ns)
            if stamp_ns <= 0:
                continue

            images_by_stamp[stamp_ns] = image_bgr

        self._images = [
            AppearanceFrame(stamp_ns, images_by_stamp[stamp_ns])
            for stamp_ns in sorted(images_by_stamp)
        ]

    def select_causal_image(
        self,
        track_timestamp_ns: int,
    ) -> Optional[AppearanceFrame]:
        """Select the latest image whose timestamp is not after the tracks."""
        if not self._images:
            return None

        stamps = [frame.stamp_ns for frame in self._images]
        index = bisect_right(stamps, int(track_timestamp_ns)) - 1

        if index < 0:
            return None

        return self._images[index]

    def request_selection(self, track_id: int) -> None:
        """Request selection of a tracker ID when it next becomes visible."""
        track_id = int(track_id)

        if track_id <= 0:
            self.clear()
            return

        self.pending_select_id = track_id

    def clear(self) -> TargetMemoryOutput:
        """Clear target memory and pending selection state."""
        self.pending_select_id = None
        return self.memory.clear()

    def candidate_from_track(self, track: Any) -> CandidateTrack:
        """Convert a tracker message object to the pure CandidateTrack type."""
        cx = float(track.cx)
        cy = float(track.cy)
        width = float(track.w)
        height = float(track.h)

        if self.config.tracks_are_normalized:
            cx *= self.config.image_width
            width *= self.config.image_width
            cy *= self.config.image_height
            height *= self.config.image_height

        unclipped_bbox = (
            cx - 0.5 * width,
            cy - 0.5 * height,
            cx + 0.5 * width,
            cy + 0.5 * height,
        )
        bbox = self.clip_bbox(unclipped_bbox)

        return CandidateTrack(
            track_id=int(track.id),
            bbox=bbox,
            score=float(track.score),
            unclipped_bbox=unclipped_bbox,
        )

    def process_tracks(self, tracks_msg: Any) -> TimMarsRuntimeResult:
        """Process one tracker message using deterministic causal evidence."""
        track_frame_id = int(
            getattr(tracks_msg, "frame_id", 0)
        )

        candidates = [
            self.candidate_from_track(track)
            for track in tracks_msg.tracks
        ]
        track_timestamp_ns = self.track_time_ns(tracks_msg)
        selected_image = (
            self.select_causal_image(track_timestamp_ns)
            if track_timestamp_ns is not None
            else None
        )

        candidates, appearance_diagnostics = self._attach_appearance(
            candidates=candidates,
            track_timestamp_ns=track_timestamp_ns,
            selected_image=selected_image,
            frame_id=track_frame_id,
        )

        selected_candidate = None
        if self.pending_select_id is not None:
            selected_candidate = self.find_candidate(
                candidates,
                self.pending_select_id,
            )

        if selected_candidate is not None:
            output = self.memory.select(selected_candidate)
            self.pending_select_id = None
        elif (
            self.pending_select_id is not None
            and self.memory.state == TargetState.NO_TARGET
        ):
            output = self.memory.update([])
            output.reason = (
                "pending_selection_track_not_visible:"
                f"{self.pending_select_id}"
            )
        elif (
            self.memory.state == TargetState.NO_TARGET
            and self.config.auto_select_largest
            and candidates
        ):
            largest = max(
                candidates,
                key=lambda candidate: self.bbox_area(candidate.bbox),
            )
            output = self.memory.select(largest)
        else:
            output = self.memory.update(candidates)

        selected_image_ns = (
            selected_image.stamp_ns
            if selected_image is not None
            else None
        )
        offset_ms = (
            float(track_timestamp_ns - selected_image_ns) / 1e6
            if (
                track_timestamp_ns is not None
                and selected_image_ns is not None
            )
            else None
        )

        self._enrich_positive_memory_bootstrap_event(
            output=output,
            candidates=candidates,
            frame_id=track_frame_id,
            track_timestamp_ns=track_timestamp_ns,
            selected_image_timestamp_ns=selected_image_ns,
            image_track_offset_ms=offset_ms,
        )

        diagnostics = TimMarsRuntimeDiagnostics(
            track_timestamp_ns=track_timestamp_ns,
            selected_image_timestamp_ns=selected_image_ns,
            image_track_offset_ms=offset_ms,
            appearance_candidates=appearance_diagnostics.candidates,
            appearance_features_valid=(
                appearance_diagnostics.features_valid
            ),
            appearance_skip_reason=appearance_diagnostics.skip_reason,
            appearance_warning=appearance_diagnostics.warning,
            appearance_cache_size=len(
                self.appearance_state.cache_by_track_id
            ),
            appearance_embedding_age_ms_by_track_id=dict(
                appearance_diagnostics.embedding_age_ms_by_track_id
            ),
            appearance_crop_quality_by_track_id=dict(
                appearance_diagnostics.crop_quality_by_track_id
            ),
            appearance_encoding_rejected=int(
                appearance_diagnostics.encoding_rejected
            ),
            appearance_memory_update_ineligible=int(
                appearance_diagnostics.memory_update_ineligible
            ),
            appearance_update_cooldown_remaining=(
                self.memory.appearance_update_cooldown_frames_remaining
            ),
            candidate_track_ids=tuple(
                int(candidate.track_id)
                for candidate in candidates
            ),
        )

        return TimMarsRuntimeResult(
            output=output,
            candidates=tuple(candidates),
            diagnostics=diagnostics,
        )

    def _enrich_positive_memory_bootstrap_event(
        self,
        *,
        output: TargetMemoryOutput,
        candidates: Sequence[CandidateTrack],
        frame_id: int,
        track_timestamp_ns: Optional[int],
        selected_image_timestamp_ns: Optional[int],
        image_track_offset_ms: Optional[float],
    ) -> None:
        """Attach accepted-frame and embedding-source correspondence."""
        event = getattr(
            output,
            "positive_memory_bootstrap_event",
            None,
        )
        if event is None:
            return

        candidate = self.find_candidate(
            candidates,
            event.track_id,
        )
        provenance = (
            candidate.appearance_provenance
            if candidate is not None
            else None
        )

        resolved_frame_id = int(frame_id)
        output.positive_memory_bootstrap_event = replace(
            event,
            frame_id=(
                resolved_frame_id
                if resolved_frame_id > 0
                else None
            ),
            track_timestamp_ns=(
                int(track_timestamp_ns)
                if track_timestamp_ns is not None
                else None
            ),
            selected_image_timestamp_ns=(
                int(selected_image_timestamp_ns)
                if selected_image_timestamp_ns is not None
                else None
            ),
            image_track_offset_ms=(
                float(image_track_offset_ms)
                if image_track_offset_ms is not None
                else None
            ),
            appearance_source_frame_id=(
                provenance.source_frame_id
                if provenance is not None
                else None
            ),
            appearance_source_image_timestamp_ns=(
                provenance.source_image_timestamp_ns
                if provenance is not None
                else None
            ),
            appearance_embedded_ns=(
                provenance.embedded_ns
                if provenance is not None
                else None
            ),
            appearance_embedding_age_ms=(
                provenance.embedding_age_ms
                if provenance is not None
                else None
            ),
            appearance_frame_generation=(
                provenance.frame_generation
                if provenance is not None
                else None
            ),
            appearance_track_generation=(
                provenance.track_generation
                if provenance is not None
                else None
            ),
            appearance_source_bbox=(
                provenance.source_bbox
                if provenance is not None
                else None
            ),
            appearance_source_crop_quality=(
                provenance.source_crop_quality
                if provenance is not None
                else None
            ),
        )

    def _attach_appearance(
        self,
        *,
        candidates: list[CandidateTrack],
        track_timestamp_ns: Optional[int],
        selected_image: Optional[AppearanceFrame],
        frame_id: int,
    ):
        if track_timestamp_ns is None:
            reset_appearance_lifecycle(
                self.appearance_state
            )
            from thesis_bringup.tim_mars.appearance_attachment import (
                AppearanceAttachmentDiagnostics,
            )

            return (
                candidates,
                AppearanceAttachmentDiagnostics(
                    candidates=len(candidates),
                    features_valid=0,
                    image_age_ms=None,
                    skip_reason="invalid_track_timestamp",
                    cache_size=len(
                        self.appearance_state.cache_by_track_id
                    ),
                    embedding_age_ms_by_track_id={},
                ),
            )

        result = attach_appearance_features(
            config=self.config.appearance,
            state=self.appearance_state,
            data=AppearanceAttachmentInput(
                candidates=candidates,
                now_ns=track_timestamp_ns,
                latest_image_bgr=(
                    selected_image.image_bgr
                    if selected_image is not None
                    else None
                ),
                latest_image_seen_ns=(
                    selected_image.stamp_ns
                    if selected_image is not None
                    else None
                ),
                latest_image_seq=(
                    selected_image.stamp_ns
                    if selected_image is not None
                    else -1
                ),
                mars_backend=self.mars_backend,
                candidate_frame_width=self.config.image_width,
                candidate_frame_height=self.config.image_height,
                frame_id=frame_id,
            ),
        )

        self.appearance_state = result.state
        return result.candidates, result.diagnostics

    def clip_bbox(self, bbox: BBox) -> BBox:
        """Clip a bbox to the configured candidate coordinate frame."""
        x1, y1, x2, y2 = bbox

        return (
            max(0.0, min(self.config.image_width, x1)),
            max(0.0, min(self.config.image_height, y1)),
            max(0.0, min(self.config.image_width, x2)),
            max(0.0, min(self.config.image_height, y2)),
        )

    @staticmethod
    def bbox_area(bbox: BBox) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @staticmethod
    def find_candidate(
        candidates: Sequence[CandidateTrack],
        track_id: int,
    ) -> Optional[CandidateTrack]:
        for candidate in candidates:
            if int(candidate.track_id) == int(track_id):
                return candidate

        return None
