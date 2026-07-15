"""Tests for TIM-MARS runtime appearance attachment."""

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
    AppearanceAttachmentInput,
    AppearanceAttachmentState,
    attach_appearance_features,
    map_bbox_to_appearance_image,
)
from thesis_bringup.tim_mars.target_memory import CandidateTrack


def tr(track_id, bbox=(10, 20, 30, 60), score=0.9):
    return CandidateTrack(track_id=track_id, bbox=bbox, score=score)


class FakeMarsBackend:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def encode(self, image_bgr, boxes):
        self.calls.append((image_bgr, boxes))
        if isinstance(self.outputs, Exception):
            raise self.outputs
        return self.outputs


def cfg(**overrides):
    values = dict(
        enabled=True,
        max_image_age_ms=250.0,
        compute_min_interval_ms=250.0,
        cache_ttl_ms=750.0,
    )
    values.update(overrides)
    return AppearanceAttachmentConfig(**values)


def data(candidates, **overrides):
    values = dict(
        candidates=candidates,
        now_ns=1_000_000_000,
        latest_image_bgr=np.zeros(
            (640, 640, 3),
            dtype=np.uint8,
        ),
        latest_image_seen_ns=999_900_000,
        latest_image_seq=3,
        mars_backend=None,
        candidate_frame_width=640.0,
        candidate_frame_height=640.0,
    )
    values.update(overrides)
    return AppearanceAttachmentInput(**values)


def test_disabled_returns_original_candidates_without_cache_work():
    candidates = [tr(1)]
    state = AppearanceAttachmentState()

    result = attach_appearance_features(
        config=cfg(enabled=False),
        state=state,
        data=data(candidates),
    )

    assert result.candidates is candidates
    assert result.diagnostics.skip_reason == "disabled"
    assert result.diagnostics.candidates == 1
    assert result.diagnostics.features_valid == 0


def test_no_candidates_skips_cleanly():
    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data([]),
    )

    assert result.candidates == []
    assert result.diagnostics.skip_reason == "no_candidates"
    assert result.diagnostics.candidates == 0


def test_no_image_attaches_valid_cached_features():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "feat-1"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data(
            [tr(1), tr(2)],
            latest_image_bgr=None,
            latest_image_seen_ns=None,
        ),
    )

    assert result.diagnostics.skip_reason == "no_image"
    assert result.diagnostics.features_valid == 1
    assert result.candidates[0].appearance == "feat-1"
    assert result.candidates[1].appearance is None


def test_stale_image_uses_cache_and_reports_age():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "feat-1"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(max_image_age_ms=50.0),
        state=state,
        data=data([tr(1)], latest_image_seen_ns=900_000_000),
    )

    assert result.diagnostics.skip_reason == "stale_image"
    assert result.diagnostics.image_age_ms == pytest.approx(100.0)
    assert result.candidates[0].appearance == "feat-1"


def test_no_mars_backend_uses_cache():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "feat-1"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data([tr(1)], mars_backend=None),
    )

    assert result.diagnostics.skip_reason == "no_mars_backend"
    assert result.candidates[0].appearance == "feat-1"


def test_successful_mars_encode_updates_cache_and_attaches_features():
    backend = FakeMarsBackend(["feat-1", None, "feat-3"])
    candidates = [tr(1), tr(2), tr(3)]

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(candidates, mars_backend=backend),
    )

    assert result.diagnostics.skip_reason == "ok"
    assert result.diagnostics.features_valid == 2
    assert result.diagnostics.cache_size == 2
    assert result.candidates[0].appearance == "feat-1"
    assert result.candidates[1].appearance is None
    assert result.candidates[2].appearance == "feat-3"
    assert len(backend.calls) == 1
    assert backend.calls[0][1] == [
        candidate.bbox
        for candidate in candidates
    ]


def test_bbox_mapping_preserves_identity_frame():
    """Keep boxes unchanged when candidate and image frames match."""
    bbox = (10.0, 20.0, 30.0, 60.0)

    mapped = map_bbox_to_appearance_image(
        bbox,
        candidate_frame_width=640.0,
        candidate_frame_height=640.0,
        image_width=640,
        image_height=640,
    )

    assert mapped == pytest.approx(bbox)


def test_bbox_mapping_scales_640_square_to_640_by_480():
    """Scale inference-frame vertical coordinates into the image frame."""
    mapped = map_bbox_to_appearance_image(
        (100.0, 160.0, 300.0, 480.0),
        candidate_frame_width=640.0,
        candidate_frame_height=640.0,
        image_width=640,
        image_height=480,
    )

    assert mapped == pytest.approx(
        (100.0, 120.0, 300.0, 360.0),
    )


def test_mars_receives_mapped_boxes_but_candidates_keep_geometry():
    """Map only MARS crop boxes while preserving candidate geometry."""
    backend = FakeMarsBackend(['feat-1'])
    candidate = tr(
        1,
        bbox=(100.0, 160.0, 300.0, 480.0),
    )
    image = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(
            [candidate],
            latest_image_bgr=image,
            mars_backend=backend,
        ),
    )

    assert backend.calls[0][1] == pytest.approx(
        [(100.0, 120.0, 300.0, 360.0)],
    )
    assert result.candidates[0].bbox == candidate.bbox
    assert result.candidates[0].appearance == 'feat-1'


def test_invalid_candidate_frame_geometry_skips_encoding():
    """Reject invalid frame geometry without calling the encoder."""
    backend = FakeMarsBackend(['feat-1'])

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(
            [tr(1)],
            mars_backend=backend,
            candidate_frame_height=0.0,
        ),
    )

    assert result.diagnostics.skip_reason == (
        'invalid_image_geometry'
    )
    assert result.diagnostics.features_valid == 0
    assert result.candidates[0].appearance is None
    assert backend.calls == []


def test_same_image_uses_cache_without_reencoding():
    backend = FakeMarsBackend(["new-feat"])
    state = AppearanceAttachmentState(
        last_mars_compute_ns=900_000_000,
        last_mars_image_seq=3,
        cache_by_track_id={1: "cached-feat"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data([tr(1)], mars_backend=backend, latest_image_seq=3),
    )

    assert result.diagnostics.skip_reason == "cached_same_image"
    assert result.candidates[0].appearance == "cached-feat"
    assert backend.calls == []


def test_compute_interval_uses_cache_without_reencoding():
    backend = FakeMarsBackend(["new-feat"])
    state = AppearanceAttachmentState(
        last_mars_compute_ns=900_000_000,
        last_mars_image_seq=2,
        cache_by_track_id={1: "cached-feat"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(compute_min_interval_ms=250.0),
        state=state,
        data=data([tr(1)], mars_backend=backend, latest_image_seq=3),
    )

    assert result.diagnostics.skip_reason == "cached_interval"
    assert result.candidates[0].appearance == "cached-feat"
    assert backend.calls == []


def test_mars_error_uses_cache_and_reports_error_type():
    backend = FakeMarsBackend(RuntimeError("boom"))
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "cached-feat"},
        cache_seen_ns={1: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data([tr(1)], mars_backend=backend),
    )

    assert result.diagnostics.skip_reason == "mars_error:RuntimeError"
    assert result.diagnostics.warning == "boom"
    assert result.candidates[0].appearance == "cached-feat"


def test_expired_cache_is_removed():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "old-feat"},
        cache_seen_ns={1: 0},
    )

    result = attach_appearance_features(
        config=cfg(cache_ttl_ms=100.0),
        state=state,
        data=data(
            [tr(1)],
            latest_image_bgr=None,
            latest_image_seen_ns=None,
        ),
    )

    assert result.diagnostics.skip_reason == "no_image"
    assert result.diagnostics.features_valid == 0
    assert result.candidates[0].appearance is None
    assert state.cache_by_track_id == {}
    assert state.cache_seen_ns == {}


def test_inactive_track_cache_is_pruned():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "feat-1", 99: "stale-active-miss"},
        cache_seen_ns={1: 900_000_000, 99: 900_000_000},
    )

    result = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data(
            [tr(1)],
            latest_image_bgr=None,
            latest_image_seen_ns=None,
        ),
    )

    assert result.candidates[0].appearance == "feat-1"
    assert state.cache_by_track_id == {1: "feat-1"}
    assert state.cache_seen_ns == {1: 900_000_000}
