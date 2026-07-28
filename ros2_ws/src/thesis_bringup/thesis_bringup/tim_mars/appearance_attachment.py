"""Runtime appearance attachment for TIM-MARS candidates.

This module attaches optional MARS ReID embeddings to CandidateTrack objects
before they enter the selected-target memory state machine. It owns image-age
checks, crop scheduling, identity-safe embedding-cache reuse, and attachment
diagnostics.

It does not decide whether a candidate is the selected target. Acceptance,
rejection, publication suppression, and recovery decisions remain in
target_memory.py and the policy helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import hypot
from time import perf_counter_ns
from typing import Any, Protocol

from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
    CropQualityThresholds,
    measure_crop_qualities,
)
from thesis_bringup.tim_mars.target_memory import BBox, CandidateTrack
from thesis_bringup.tim_mars.types import (
    AppearanceObservationProvenance,
)


class AppearanceEncoder(Protocol):
    def encode(
        self,
        image_bgr: Any,
        boxes: list[tuple[float, float, float, float]],
    ) -> list[Any | None]:
        ...


@dataclass
class AppearanceAttachmentConfig:
    enabled: bool
    max_image_age_ms: float
    compute_min_interval_ms: float
    cache_ttl_ms: float
    cache_max_centre_distance_norm: float = 0.25
    cache_min_scale_ratio: float = 0.25
    crop_quality: CropQualityThresholds = field(
        default_factory=CropQualityThresholds
    )


@dataclass
class AppearanceAttachmentInput:
    candidates: list[CandidateTrack]
    now_ns: int
    latest_image_bgr: Any | None
    latest_image_seen_ns: int | None
    latest_image_seq: int
    mars_backend: AppearanceEncoder | None
    candidate_frame_width: float
    candidate_frame_height: float
    frame_id: int | None = None


@dataclass(frozen=True)
class AppearanceCacheEntry:
    """One embedding tied to a specific observed tracker instance."""

    appearance: Any
    embedded_ns: int
    source_frame_id: int
    frame_generation: int
    track_generation: int
    source_bbox: BBox
    crop_quality: AppearanceCropQuality
    source_image_timestamp_ns: int | None = None


@dataclass
class AppearanceAttachmentState:
    last_mars_compute_ns: int = 0
    last_mars_image_seq: int = -1

    cache_by_track_id: dict[
        int,
        AppearanceCacheEntry | Any,
    ] = field(default_factory=dict)

    # Retained for compatibility with older direct unit-test setup. Structured
    # production entries use AppearanceCacheEntry.embedded_ns as source of truth.
    cache_seen_ns: dict[int, int] = field(default_factory=dict)

    frame_generation: int = 0
    last_frame_id: int | None = None
    track_generation_by_id: dict[int, int] = field(default_factory=dict)
    last_bbox_by_track_id: dict[int, BBox] = field(default_factory=dict)


@dataclass
class AppearanceAttachmentDiagnostics:
    candidates: int = 0
    features_valid: int = 0
    image_age_ms: float | None = None
    skip_reason: str = "disabled"
    cache_size: int = 0
    warning: str | None = None
    embedding_age_ms_by_track_id: dict[int, float] = field(
        default_factory=dict
    )
    crop_quality_by_track_id: dict[
        int,
        AppearanceCropQuality,
    ] = field(default_factory=dict)
    encoding_rejected: int = 0
    memory_update_ineligible: int = 0

    # Baseline synchronous embedding workload. These diagnostics measure the
    # existing CPU path without changing crop selection or identity policy.
    encoding_eligible: int = 0
    backend_calls: int = 0
    backend_requested: int = 0
    backend_returned: int = 0
    backend_valid: int = 0
    backend_wall_ms: float = 0.0


@dataclass
class AppearanceAttachmentResult:
    candidates: list[CandidateTrack]
    state: AppearanceAttachmentState
    diagnostics: AppearanceAttachmentDiagnostics


def map_bbox_to_appearance_image(
    bbox: tuple[float, float, float, float],
    *,
    candidate_frame_width: float,
    candidate_frame_height: float,
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    """Map a candidate-frame bbox into the appearance-image frame."""
    if candidate_frame_width <= 0.0:
        raise ValueError("candidate frame width must be positive")

    if candidate_frame_height <= 0.0:
        raise ValueError("candidate frame height must be positive")

    if image_width <= 0 or image_height <= 0:
        raise ValueError("appearance image dimensions must be positive")

    scale_x = float(image_width) / float(candidate_frame_width)
    scale_y = float(image_height) / float(candidate_frame_height)

    x1, y1, x2, y2 = bbox
    return (
        float(x1) * scale_x,
        float(y1) * scale_y,
        float(x2) * scale_x,
        float(y2) * scale_y,
    )


def reset_appearance_lifecycle(
    state: AppearanceAttachmentState,
) -> None:
    """Terminate all observed tracker instances and cached ownership.

    Encoder scheduling markers are intentionally preserved. A lifecycle reset
    must not cause the same previously encoded image to be immediately encoded
    again as if it were new evidence.
    """
    state.frame_generation += 1
    state.last_frame_id = None
    state.track_generation_by_id.clear()
    state.last_bbox_by_track_id.clear()
    state.cache_by_track_id.clear()
    state.cache_seen_ns.clear()


def _bbox_area(bbox: BBox) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _bbox_continuity_is_plausible(
    previous: BBox,
    current: BBox,
    *,
    image_width: float,
    image_height: float,
    max_centre_distance_norm: float,
    min_scale_ratio: float,
) -> bool:
    previous_cx = 0.5 * (previous[0] + previous[2])
    previous_cy = 0.5 * (previous[1] + previous[3])
    current_cx = 0.5 * (current[0] + current[2])
    current_cy = 0.5 * (current[1] + current[3])

    diagonal = hypot(float(image_width), float(image_height))
    if diagonal <= 0.0:
        return False

    centre_distance_norm = hypot(
        current_cx - previous_cx,
        current_cy - previous_cy,
    ) / diagonal

    previous_area = _bbox_area(previous)
    current_area = _bbox_area(current)

    if previous_area <= 0.0 or current_area <= 0.0:
        return False

    scale_ratio = min(previous_area, current_area) / max(
        previous_area,
        current_area,
    )

    return (
        centre_distance_norm
        <= max(0.0, float(max_centre_distance_norm))
        and scale_ratio
        >= max(0.0, min(1.0, float(min_scale_ratio)))
    )


def reconcile_appearance_track_lifecycle(
    *,
    config: AppearanceAttachmentConfig,
    state: AppearanceAttachmentState,
    candidates: list[CandidateTrack],
    frame_id: int,
    image_width: float,
    image_height: float,
) -> None:
    """Update tracker-instance generations before cache lookup or encoding."""
    frame_id = int(frame_id)

    if frame_id <= 0:
        reset_appearance_lifecycle(state)
        return

    if state.last_frame_id is None:
        if state.frame_generation <= 0:
            state.frame_generation = 1
    elif frame_id < state.last_frame_id:
        reset_appearance_lifecycle(state)

    state.last_frame_id = frame_id

    active_track_ids = {
        int(candidate.track_id)
        for candidate in candidates
    }

    for track_id in list(state.last_bbox_by_track_id):
        if track_id in active_track_ids:
            continue

        state.last_bbox_by_track_id.pop(track_id, None)
        state.cache_by_track_id.pop(track_id, None)
        state.cache_seen_ns.pop(track_id, None)

    for candidate in candidates:
        track_id = int(candidate.track_id)
        previous_bbox = state.last_bbox_by_track_id.get(track_id)

        starts_new_generation = previous_bbox is None

        if previous_bbox is not None:
            starts_new_generation = not _bbox_continuity_is_plausible(
                previous_bbox,
                candidate.bbox,
                image_width=image_width,
                image_height=image_height,
                max_centre_distance_norm=(
                    config.cache_max_centre_distance_norm
                ),
                min_scale_ratio=config.cache_min_scale_ratio,
            )

        if starts_new_generation:
            state.track_generation_by_id[track_id] = (
                state.track_generation_by_id.get(track_id, 0)
                + 1
            )
            state.cache_by_track_id.pop(track_id, None)
            state.cache_seen_ns.pop(track_id, None)

        state.last_bbox_by_track_id[track_id] = candidate.bbox


def _result_with_cached_features(
    *,
    config: AppearanceAttachmentConfig,
    state: AppearanceAttachmentState,
    data: AppearanceAttachmentInput,
    diagnostics: AppearanceAttachmentDiagnostics,
    crop_quality_by_track_id: dict[
        int,
        AppearanceCropQuality,
    ] | None = None,
) -> AppearanceAttachmentResult:
    enriched, valid, ages = attach_cached_appearance_features(
        candidates=data.candidates,
        state=state,
        now_ns=data.now_ns,
        cache_ttl_ms=config.cache_ttl_ms,
        crop_quality_by_track_id=crop_quality_by_track_id,
    )

    diagnostics.features_valid = valid
    diagnostics.cache_size = len(state.cache_by_track_id)
    diagnostics.embedding_age_ms_by_track_id = ages

    if crop_quality_by_track_id is not None:
        diagnostics.crop_quality_by_track_id = dict(
            crop_quality_by_track_id
        )
        diagnostics.encoding_rejected = sum(
            not quality.encoding_eligible
            for quality in crop_quality_by_track_id.values()
        )
        diagnostics.memory_update_ineligible = sum(
            not quality.memory_update_eligible
            for quality in crop_quality_by_track_id.values()
        )

    return AppearanceAttachmentResult(
        enriched,
        state,
        diagnostics,
    )


def attach_appearance_features(
    *,
    config: AppearanceAttachmentConfig,
    state: AppearanceAttachmentState,
    data: AppearanceAttachmentInput,
) -> AppearanceAttachmentResult:
    diagnostics = AppearanceAttachmentDiagnostics(
        candidates=len(data.candidates),
        features_valid=0,
        image_age_ms=None,
        skip_reason="disabled",
        cache_size=len(state.cache_by_track_id),
    )

    if not config.enabled:
        return AppearanceAttachmentResult(
            data.candidates,
            state,
            diagnostics,
        )

    if data.frame_id is not None:
        reconcile_appearance_track_lifecycle(
            config=config,
            state=state,
            candidates=data.candidates,
            frame_id=data.frame_id,
            image_width=data.candidate_frame_width,
            image_height=data.candidate_frame_height,
        )

    if not data.candidates:
        diagnostics.skip_reason = "no_candidates"
        diagnostics.cache_size = len(state.cache_by_track_id)

        return AppearanceAttachmentResult(
            data.candidates,
            state,
            diagnostics,
        )

    if (
        data.latest_image_bgr is None
        or data.latest_image_seen_ns is None
    ):
        diagnostics.skip_reason = "no_image"

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
        )

    try:
        image_height, image_width = (
            data.latest_image_bgr.shape[:2]
        )

        mapped_boxes = [
            map_bbox_to_appearance_image(
                (
                    candidate.unclipped_bbox
                    if candidate.unclipped_bbox is not None
                    else candidate.bbox
                ),
                candidate_frame_width=(
                    data.candidate_frame_width
                ),
                candidate_frame_height=(
                    data.candidate_frame_height
                ),
                image_width=int(image_width),
                image_height=int(image_height),
            )
            for candidate in data.candidates
        ]

        crop_qualities = measure_crop_qualities(
            mapped_boxes,
            image_width=int(image_width),
            image_height=int(image_height),
            thresholds=config.crop_quality,
        )
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        diagnostics.skip_reason = "invalid_image_geometry"
        diagnostics.warning = str(exc)

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
        )

    crop_quality_by_track_id = {
        int(candidate.track_id): quality
        for candidate, quality in zip(
            data.candidates,
            crop_qualities,
        )
    }

    diagnostics.crop_quality_by_track_id = dict(
        crop_quality_by_track_id
    )
    diagnostics.encoding_rejected = sum(
        not quality.encoding_eligible
        for quality in crop_qualities
    )
    diagnostics.memory_update_ineligible = sum(
        not quality.memory_update_eligible
        for quality in crop_qualities
    )

    age_ms = float(
        data.now_ns - data.latest_image_seen_ns
    ) / 1e6
    diagnostics.image_age_ms = age_ms

    if age_ms > config.max_image_age_ms:
        diagnostics.skip_reason = "stale_image"

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
            crop_quality_by_track_id=(
                crop_quality_by_track_id
            ),
        )

    if data.mars_backend is None:
        diagnostics.skip_reason = "no_mars_backend"

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
            crop_quality_by_track_id=(
                crop_quality_by_track_id
            ),
        )

    elapsed_ms = float(
        data.now_ns - state.last_mars_compute_ns
    ) / 1e6

    image_already_encoded = (
        state.last_mars_image_seq
        == data.latest_image_seq
    )

    interval_too_short = (
        state.last_mars_compute_ns > 0
        and elapsed_ms < config.compute_min_interval_ms
    )

    if image_already_encoded or interval_too_short:
        diagnostics.skip_reason = (
            "cached_same_image"
            if image_already_encoded
            else "cached_interval"
        )

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
            crop_quality_by_track_id=(
                crop_quality_by_track_id
            ),
        )

    encoding_indices = [
        index
        for index, quality in enumerate(crop_qualities)
        if quality.encoding_eligible
    ]
    diagnostics.encoding_eligible = len(encoding_indices)

    if not encoding_indices:
        state.last_mars_compute_ns = data.now_ns
        state.last_mars_image_seq = data.latest_image_seq
        diagnostics.skip_reason = (
            "no_encoding_eligible_crops"
        )

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
            crop_quality_by_track_id=(
                crop_quality_by_track_id
            ),
        )

    encoding_boxes = [
        mapped_boxes[index]
        for index in encoding_indices
    ]

    diagnostics.backend_calls = 1
    diagnostics.backend_requested = len(encoding_boxes)
    encode_started_ns = perf_counter_ns()

    try:
        encoded = data.mars_backend.encode(
            data.latest_image_bgr,
            encoding_boxes,
        )

        diagnostics.backend_returned = len(encoded)
        diagnostics.backend_valid = sum(
            feature is not None
            for feature in encoded
        )

        if len(encoded) != len(encoding_indices):
            raise ValueError(
                "appearance encoder returned "
                f"{len(encoded)} features for "
                f"{len(encoding_indices)} boxes"
            )
    except Exception as exc:
        diagnostics.skip_reason = (
            f"mars_error:{type(exc).__name__}"
        )
        diagnostics.warning = str(exc)

        return _result_with_cached_features(
            config=config,
            state=state,
            data=data,
            diagnostics=diagnostics,
            crop_quality_by_track_id=(
                crop_quality_by_track_id
            ),
        )

    finally:
        diagnostics.backend_wall_ms = (
            float(perf_counter_ns() - encode_started_ns) / 1e6
        )

    state.last_mars_compute_ns = data.now_ns
    state.last_mars_image_seq = data.latest_image_seq

    fresh_appearance_by_track_id: dict[int, Any] = {}

    for candidate_index, appearance in zip(
        encoding_indices,
        encoded,
    ):
        if appearance is None:
            continue

        candidate = data.candidates[candidate_index]
        quality = crop_qualities[candidate_index]
        track_id = int(candidate.track_id)

        fresh_appearance_by_track_id[track_id] = appearance

        if not quality.memory_update_eligible:
            continue

        state.cache_by_track_id[track_id] = AppearanceCacheEntry(
            appearance=appearance,
            embedded_ns=int(data.now_ns),
            source_frame_id=int(
                data.frame_id
                if data.frame_id is not None
                else -1
            ),
            frame_generation=int(
                state.frame_generation
            ),
            track_generation=int(
                state.track_generation_by_id.get(
                    track_id,
                    0,
                )
            ),
            source_bbox=candidate.bbox,
            crop_quality=quality,
            source_image_timestamp_ns=(
                int(data.latest_image_seen_ns)
                if data.latest_image_seen_ns is not None
                else None
            ),
        )
        state.cache_seen_ns[track_id] = int(
            data.now_ns
        )

    enriched, _, ages = attach_cached_appearance_features(
        candidates=data.candidates,
        state=state,
        now_ns=data.now_ns,
        cache_ttl_ms=config.cache_ttl_ms,
        crop_quality_by_track_id=(
            crop_quality_by_track_id
        ),
    )

    final_candidates: list[CandidateTrack] = []

    for candidate in enriched:
        track_id = int(candidate.track_id)
        fresh = fresh_appearance_by_track_id.get(track_id)

        if fresh is None:
            final_candidates.append(candidate)
            continue

        quality = crop_quality_by_track_id[track_id]
        ages[track_id] = 0.0

        final_candidates.append(
            replace(
                candidate,
                appearance=fresh,
                appearance_crop_quality=quality,
                appearance_memory_update_eligible=(
                    quality.memory_update_eligible
                ),
            )
        )

    diagnostics.skip_reason = "ok"
    diagnostics.features_valid = sum(
        candidate.appearance is not None
        for candidate in final_candidates
    )
    diagnostics.cache_size = len(
        state.cache_by_track_id
    )
    diagnostics.embedding_age_ms_by_track_id = ages

    return AppearanceAttachmentResult(
        final_candidates,
        state,
        diagnostics,
    )


def attach_cached_appearance_features(
    *,
    candidates: list[CandidateTrack],
    state: AppearanceAttachmentState,
    now_ns: int,
    cache_ttl_ms: float,
    crop_quality_by_track_id: dict[
        int,
        AppearanceCropQuality,
    ] | None = None,
) -> tuple[
    list[CandidateTrack],
    int,
    dict[int, float],
]:
    enriched: list[CandidateTrack] = []
    valid_features = 0
    embedding_ages: dict[int, float] = {}

    active_track_ids = {
        int(candidate.track_id)
        for candidate in candidates
    }

    for track_id in list(
        state.cache_by_track_id.keys()
    ):
        if track_id in active_track_ids:
            continue

        state.cache_by_track_id.pop(
            track_id,
            None,
        )
        state.cache_seen_ns.pop(
            track_id,
            None,
        )

    for candidate in candidates:
        track_id = int(candidate.track_id)
        cached = state.cache_by_track_id.get(
            track_id
        )
        current_quality = (
            crop_quality_by_track_id.get(track_id)
            if crop_quality_by_track_id is not None
            else None
        )

        appearance = None
        source_quality = None
        cache_age_ms = None
        cache_valid = False

        if isinstance(
            cached,
            AppearanceCacheEntry,
        ):
            cache_age_ms = float(
                int(now_ns) - cached.embedded_ns
            ) / 1e6

            cache_valid = (
                0.0
                <= cache_age_ms
                <= float(cache_ttl_ms)
                and cached.frame_generation
                == state.frame_generation
                and cached.track_generation
                == state.track_generation_by_id.get(
                    track_id,
                    0,
                )
            )

            if cache_valid:
                appearance = cached.appearance
                source_quality = cached.crop_quality

        elif cached is not None:
            seen_ns = state.cache_seen_ns.get(
                track_id
            )

            if (
                state.frame_generation <= 0
                and seen_ns is not None
            ):
                cache_age_ms = float(
                    int(now_ns) - int(seen_ns)
                ) / 1e6

                cache_valid = (
                    0.0
                    <= cache_age_ms
                    <= float(cache_ttl_ms)
                )

                if cache_valid:
                    appearance = cached

        if cache_valid and cache_age_ms is not None:
            valid_features += 1
            embedding_ages[track_id] = cache_age_ms
        elif cached is not None:
            state.cache_by_track_id.pop(
                track_id,
                None,
            )
            state.cache_seen_ns.pop(
                track_id,
                None,
            )

        effective_quality = (
            current_quality
            if current_quality is not None
            else source_quality
        )

        source_memory_eligible = (
            source_quality.memory_update_eligible
            if source_quality is not None
            else cache_valid
        )
        current_memory_eligible = (
            current_quality is not None
            and current_quality.memory_update_eligible
        )

        appearance_provenance = None
        if (
            cache_valid
            and isinstance(cached, AppearanceCacheEntry)
            and cache_age_ms is not None
        ):
            source_frame_id = int(cached.source_frame_id)
            appearance_provenance = (
                AppearanceObservationProvenance(
                    source_frame_id=(
                        source_frame_id
                        if source_frame_id >= 0
                        else None
                    ),
                    source_image_timestamp_ns=(
                        cached.source_image_timestamp_ns
                    ),
                    embedded_ns=int(cached.embedded_ns),
                    embedding_age_ms=float(cache_age_ms),
                    frame_generation=int(
                        cached.frame_generation
                    ),
                    track_generation=int(
                        cached.track_generation
                    ),
                    source_bbox=cached.source_bbox,
                    source_crop_quality=(
                        cached.crop_quality
                    ),
                )
            )

        enriched.append(
            replace(
                candidate,
                appearance=appearance,
                appearance_provenance=(
                    appearance_provenance
                ),
                appearance_crop_quality=(
                    effective_quality
                ),
                appearance_memory_update_eligible=bool(
                    cache_valid
                    and appearance is not None
                    and source_memory_eligible
                    and current_memory_eligible
                ),
            )
        )

    return (
        enriched,
        valid_features,
        embedding_ages,
    )
