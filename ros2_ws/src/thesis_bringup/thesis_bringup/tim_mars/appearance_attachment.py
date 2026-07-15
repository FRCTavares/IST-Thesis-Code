"""Runtime appearance attachment for TIM-MARS candidates.

This module attaches optional MARS ReID embeddings to CandidateTrack objects
before they enter the selected-target memory state machine. It owns image-age
checks, crop scheduling, embedding-cache reuse, and attachment diagnostics.

It does not decide whether a candidate is the selected target. Acceptance,
rejection, publication suppression, and recovery decisions remain in
target_memory.py and the policy helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from thesis_bringup.tim_mars.target_memory import CandidateTrack


class AppearanceEncoder(Protocol):
    def encode(self, image_bgr: Any, boxes: list[tuple[float, float, float, float]]) -> list[Any | None]:
        ...


@dataclass
class AppearanceAttachmentConfig:
    enabled: bool
    max_image_age_ms: float
    compute_min_interval_ms: float
    cache_ttl_ms: float


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


@dataclass
class AppearanceAttachmentState:
    last_mars_compute_ns: int = 0
    last_mars_image_seq: int = -1
    cache_by_track_id: dict[int, Any] = field(default_factory=dict)
    cache_seen_ns: dict[int, int] = field(default_factory=dict)


@dataclass
class AppearanceAttachmentDiagnostics:
    candidates: int = 0
    features_valid: int = 0
    image_age_ms: float | None = None
    skip_reason: str = "disabled"
    cache_size: int = 0
    warning: str | None = None


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
        raise ValueError('candidate frame width must be positive')

    if candidate_frame_height <= 0.0:
        raise ValueError('candidate frame height must be positive')

    if image_width <= 0 or image_height <= 0:
        raise ValueError('appearance image dimensions must be positive')

    scale_x = float(image_width) / float(candidate_frame_width)
    scale_y = float(image_height) / float(candidate_frame_height)

    x1, y1, x2, y2 = bbox
    return (
        float(x1) * scale_x,
        float(y1) * scale_y,
        float(x2) * scale_x,
        float(y2) * scale_y,
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
        return AppearanceAttachmentResult(data.candidates, state, diagnostics)

    if not data.candidates:
        diagnostics.skip_reason = "no_candidates"
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(data.candidates, state, diagnostics)

    if data.latest_image_bgr is None or data.latest_image_seen_ns is None:
        diagnostics.skip_reason = "no_image"
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    age_ms = float(data.now_ns - data.latest_image_seen_ns) / 1e6
    diagnostics.image_age_ms = age_ms

    if age_ms > config.max_image_age_ms:
        diagnostics.skip_reason = "stale_image"
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    if data.mars_backend is None:
        diagnostics.skip_reason = "no_mars_backend"
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    elapsed_ms = float(data.now_ns - state.last_mars_compute_ns) / 1e6
    image_already_encoded = state.last_mars_image_seq == data.latest_image_seq
    interval_too_short = (
        state.last_mars_compute_ns > 0
        and elapsed_ms < config.compute_min_interval_ms
    )

    if image_already_encoded or interval_too_short:
        diagnostics.skip_reason = (
            "cached_same_image" if image_already_encoded else "cached_interval"
        )
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    try:
        image_height, image_width = data.latest_image_bgr.shape[:2]
        boxes = [
            map_bbox_to_appearance_image(
                candidate.bbox,
                candidate_frame_width=data.candidate_frame_width,
                candidate_frame_height=data.candidate_frame_height,
                image_width=int(image_width),
                image_height=int(image_height),
            )
            for candidate in data.candidates
        ]
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        diagnostics.skip_reason = 'invalid_image_geometry'
        diagnostics.warning = str(exc)
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    try:
        appearances = data.mars_backend.encode(
            data.latest_image_bgr,
            boxes,
        )
    except Exception as exc:
        diagnostics.skip_reason = f"mars_error:{type(exc).__name__}"
        diagnostics.warning = str(exc)
        enriched, valid = attach_cached_appearance_features(
            candidates=data.candidates,
            state=state,
            now_ns=data.now_ns,
            cache_ttl_ms=config.cache_ttl_ms,
        )
        diagnostics.features_valid = valid
        diagnostics.cache_size = len(state.cache_by_track_id)
        return AppearanceAttachmentResult(enriched, state, diagnostics)

    state.last_mars_compute_ns = data.now_ns
    state.last_mars_image_seq = data.latest_image_seq

    encoded_valid = 0
    for candidate, appearance in zip(data.candidates, appearances):
        if appearance is None:
            continue
        encoded_valid += 1
        track_id = int(candidate.track_id)
        state.cache_by_track_id[track_id] = appearance
        state.cache_seen_ns[track_id] = data.now_ns

    enriched, cached_valid = attach_cached_appearance_features(
        candidates=data.candidates,
        state=state,
        now_ns=data.now_ns,
        cache_ttl_ms=config.cache_ttl_ms,
    )

    diagnostics.skip_reason = "ok"
    diagnostics.features_valid = max(encoded_valid, cached_valid)
    diagnostics.cache_size = len(state.cache_by_track_id)

    return AppearanceAttachmentResult(enriched, state, diagnostics)


def attach_cached_appearance_features(
    *,
    candidates: list[CandidateTrack],
    state: AppearanceAttachmentState,
    now_ns: int,
    cache_ttl_ms: float,
) -> tuple[list[CandidateTrack], int]:
    enriched: list[CandidateTrack] = []
    valid_features = 0

    active_track_ids = {int(candidate.track_id) for candidate in candidates}

    for track_id in list(state.cache_by_track_id.keys()):
        if track_id not in active_track_ids:
            state.cache_by_track_id.pop(track_id, None)
            state.cache_seen_ns.pop(track_id, None)

    for candidate in candidates:
        track_id = int(candidate.track_id)
        appearance = state.cache_by_track_id.get(track_id)
        seen_ns = state.cache_seen_ns.get(track_id)

        if appearance is not None and seen_ns is not None:
            cache_age_ms = float(now_ns - seen_ns) / 1e6
            if cache_age_ms <= cache_ttl_ms:
                valid_features += 1
            else:
                appearance = None
                state.cache_by_track_id.pop(track_id, None)
                state.cache_seen_ns.pop(track_id, None)

        enriched.append(
            CandidateTrack(
                track_id=candidate.track_id,
                bbox=candidate.bbox,
                score=candidate.score,
                age=candidate.age,
                last_seen=candidate.last_seen,
                appearance=appearance,
            )
        )

    return enriched, valid_features
