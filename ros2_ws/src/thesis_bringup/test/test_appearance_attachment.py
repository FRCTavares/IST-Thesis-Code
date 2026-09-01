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
    values = {
        "enabled": True,
        "max_image_age_ms": 250.0,
        "compute_min_interval_ms": 250.0,
        "cache_ttl_ms": 750.0,
    }
    values.update(overrides)
    return AppearanceAttachmentConfig(**values)


def data(candidates, **overrides):
    values = {
        "candidates": candidates,
        "now_ns": 1_000_000_000,
        "latest_image_bgr": np.zeros(
            (640, 640, 3),
            dtype=np.uint8,
        ),
        "latest_image_seen_ns": 999_900_000,
        "latest_image_seq": 3,
        "mars_backend": None,
        "candidate_frame_width": 640.0,
        "candidate_frame_height": 640.0,
    }
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
    assert result.diagnostics.cache_lookups == 2
    assert result.diagnostics.cache_hits == 1
    assert result.diagnostics.cache_misses == 1
    assert result.diagnostics.cache_expired == 0
    assert result.diagnostics.cache_invalidated == 0
    assert result.diagnostics.cache_lookups == (
        result.diagnostics.cache_hits
        + result.diagnostics.cache_misses
        + result.diagnostics.cache_expired
        + result.diagnostics.cache_invalidated
    )


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
    candidates = [
        tr(1, bbox=(10, 20, 30, 60)),
        tr(2, bbox=(100, 20, 120, 60)),
        tr(3, bbox=(200, 20, 220, 60)),
    ]

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(candidates, mars_backend=backend),
    )

    assert result.diagnostics.skip_reason == "ok"
    assert result.diagnostics.features_valid == 2
    assert result.diagnostics.cache_size == 2

    # Tracks 1 and 3 received fresh embeddings. They must not be counted
    # as cache reuse merely because the fresh embeddings were just written.
    assert result.diagnostics.cache_lookups == 1
    assert result.diagnostics.cache_hits == 0
    assert result.diagnostics.cache_misses == 1
    assert result.diagnostics.cache_expired == 0
    assert result.diagnostics.cache_invalidated == 0
    assert result.diagnostics.cache_lookups == (
        result.diagnostics.cache_hits
        + result.diagnostics.cache_misses
        + result.diagnostics.cache_expired
        + result.diagnostics.cache_invalidated
    )
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
    assert result.diagnostics.cache_lookups == 1
    assert result.diagnostics.cache_hits == 1
    assert result.diagnostics.cache_misses == 0
    assert result.diagnostics.cache_expired == 0
    assert result.diagnostics.cache_invalidated == 0
    assert result.diagnostics.cache_lookups == (
        result.diagnostics.cache_hits
        + result.diagnostics.cache_misses
        + result.diagnostics.cache_expired
        + result.diagnostics.cache_invalidated
    )


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
    assert result.diagnostics.cache_lookups == 1
    assert result.diagnostics.cache_hits == 0
    assert result.diagnostics.cache_misses == 0
    assert result.diagnostics.cache_expired == 1
    assert result.diagnostics.cache_invalidated == 0
    assert result.diagnostics.cache_lookups == (
        result.diagnostics.cache_hits
        + result.diagnostics.cache_misses
        + result.diagnostics.cache_expired
        + result.diagnostics.cache_invalidated
    )


def test_cache_without_valid_age_metadata_is_invalidated():
    state = AppearanceAttachmentState(
        cache_by_track_id={1: "legacy-feature"},
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

    assert result.candidates[0].appearance is None
    assert result.diagnostics.cache_lookups == 1
    assert result.diagnostics.cache_hits == 0
    assert result.diagnostics.cache_misses == 0
    assert result.diagnostics.cache_expired == 0
    assert result.diagnostics.cache_invalidated == 1
    assert result.diagnostics.cache_lookups == (
        result.diagnostics.cache_hits
        + result.diagnostics.cache_misses
        + result.diagnostics.cache_expired
        + result.diagnostics.cache_invalidated
    )
    assert state.cache_by_track_id == {}


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


def test_encoding_filter_preserves_sparse_output_alignment():
    backend = FakeMarsBackend(["clean-feature"])
    candidates = [
        tr(
            1,
            bbox=(10.0, 10.0, 18.0, 30.0),
        ),
        tr(
            2,
            bbox=(100.0, 100.0, 140.0, 180.0),
        ),
    ]

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(
            candidates,
            mars_backend=backend,
        ),
    )

    assert backend.calls[0][1] == [
        (100.0, 100.0, 140.0, 180.0),
    ]
    assert result.candidates[0].appearance is None
    assert not (
        result.candidates[0]
        .appearance_crop_quality
        .encoding_eligible
    )
    assert not (
        result.candidates[0]
        .appearance_memory_update_eligible
    )

    assert (
        result.candidates[1].appearance
        == "clean-feature"
    )
    assert (
        result.candidates[1]
        .appearance_crop_quality
        .encoding_eligible
    )
    assert (
        result.candidates[1]
        .appearance_memory_update_eligible
    )
    assert result.diagnostics.encoding_rejected == 1
    assert set(result.state.cache_by_track_id) == {2}


def test_overlap_allows_scoring_but_not_persistence():
    backend = FakeMarsBackend(
        ["feature-1", "feature-2"]
    )
    candidates = [
        tr(
            1,
            bbox=(100.0, 100.0, 160.0, 240.0),
        ),
        tr(
            2,
            bbox=(125.0, 100.0, 185.0, 240.0),
        ),
    ]

    result = attach_appearance_features(
        config=cfg(),
        state=AppearanceAttachmentState(),
        data=data(
            candidates,
            mars_backend=backend,
        ),
    )

    assert [
        candidate.appearance
        for candidate in result.candidates
    ] == [
        "feature-1",
        "feature-2",
    ]
    assert all(
        candidate
        .appearance_crop_quality
        .encoding_eligible
        for candidate in result.candidates
    )
    assert all(
        not candidate
        .appearance_memory_update_eligible
        for candidate in result.candidates
    )
    assert result.state.cache_by_track_id == {}
    assert result.diagnostics.encoding_rejected == 0
    assert result.diagnostics.memory_update_ineligible == 2


def test_cached_clean_feature_is_ineligible_during_group_risk():
    state = AppearanceAttachmentState()
    backend = FakeMarsBackend(["feature-1"])

    first = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data(
            [
                tr(
                    1,
                    bbox=(
                        100.0,
                        100.0,
                        160.0,
                        240.0,
                    ),
                )
            ],
            mars_backend=backend,
        ),
    )

    assert (
        first.candidates[0]
        .appearance_memory_update_eligible
    )

    second = attach_appearance_features(
        config=cfg(),
        state=state,
        data=data(
            [
                tr(
                    1,
                    bbox=(
                        100.0,
                        100.0,
                        160.0,
                        240.0,
                    ),
                ),
                tr(
                    2,
                    bbox=(
                        125.0,
                        100.0,
                        185.0,
                        240.0,
                    ),
                ),
            ],
            now_ns=1_100_000_000,
            latest_image_seq=3,
            mars_backend=backend,
        ),
    )

    assert (
        second.diagnostics.skip_reason
        == "cached_same_image"
    )
    assert (
        second.candidates[0].appearance
        == "feature-1"
    )
    assert not (
        second.candidates[0]
        .appearance_crop_quality
        .memory_update_eligible
    )
    assert not (
        second.candidates[0]
        .appearance_memory_update_eligible
    )
    assert len(backend.calls) == 1


def test_reports_synchronous_cpu_backend_workload_without_policy_changes():
    first_feature = np.ones(128, dtype=np.float32)
    backend = FakeMarsBackend([first_feature, None])

    result = attach_appearance_features(
        config=cfg(compute_min_interval_ms=0.0),
        state=AppearanceAttachmentState(),
        data=data(
            [
                tr(1, bbox=(10, 20, 40, 100)),
                tr(2, bbox=(200, 180, 250, 320)),
            ],
            mars_backend=backend,
        ),
    )

    diagnostics = result.diagnostics

    assert len(backend.calls) == 1
    assert diagnostics.candidates == 2
    assert diagnostics.encoding_eligible == 2
    assert diagnostics.backend_calls == 1
    assert diagnostics.backend_requested == 2
    assert diagnostics.backend_returned == 2
    assert diagnostics.backend_valid == 1
    assert diagnostics.backend_wall_ms >= 0.0
    assert diagnostics.skip_reason == "ok"
    assert diagnostics.features_valid == 1

    assert result.candidates[0].appearance is first_feature
    assert result.candidates[1].appearance is None


def test_request_mask_restricts_encoding_without_subsetting_candidates():
    candidates = [
        tr(1, bbox=(10.0, 20.0, 40.0, 100.0)),
        tr(2, bbox=(200.0, 180.0, 250.0, 320.0)),
    ]
    backend = FakeMarsBackend(["feature-2"])

    result = attach_appearance_features(
        config=cfg(compute_min_interval_ms=0.0),
        state=AppearanceAttachmentState(),
        data=data(
            candidates,
            mars_backend=backend,
            requested_candidate_indices=(1,),
            frame_id=1,
        ),
    )

    assert result.diagnostics.candidates == 2
    assert result.diagnostics.encoding_eligible == 2
    assert result.diagnostics.request_candidates == 1
    assert result.diagnostics.request_encoding_eligible == 1
    assert result.diagnostics.backend_requested == 1

    assert backend.calls[0][1] == [
        (200.0, 180.0, 250.0, 320.0),
    ]
    assert result.candidates[0].appearance is None
    assert result.candidates[1].appearance == "feature-2"


def test_request_mask_preserves_visible_nonrequested_cache_lifecycle():
    candidates = [
        tr(1, bbox=(10.0, 20.0, 40.0, 100.0)),
        tr(2, bbox=(200.0, 180.0, 250.0, 320.0)),
    ]
    state = AppearanceAttachmentState()

    first = attach_appearance_features(
        config=cfg(compute_min_interval_ms=0.0),
        state=state,
        data=data(
            candidates,
            now_ns=1_000_000_000,
            latest_image_seen_ns=999_900_000,
            latest_image_seq=1,
            mars_backend=FakeMarsBackend(
                ["feature-1", "feature-2"]
            ),
            requested_candidate_indices=None,
            frame_id=1,
        ),
    )

    assert set(first.state.cache_by_track_id) == {1, 2}

    second_backend = FakeMarsBackend(["feature-2-new"])
    second = attach_appearance_features(
        config=cfg(compute_min_interval_ms=0.0),
        state=state,
        data=data(
            candidates,
            # Keep the non-requested track inside the configured
            # 750 ms cache TTL. This test isolates request-mask lifecycle
            # behaviour rather than ordinary cache expiry.
            now_ns=1_500_000_000,
            latest_image_seen_ns=1_499_900_000,
            latest_image_seq=2,
            mars_backend=second_backend,
            requested_candidate_indices=(1,),
            frame_id=2,
        ),
    )

    assert set(second.state.cache_by_track_id) == {1, 2}
    assert second.candidates[0].appearance == "feature-1"
    assert second.candidates[1].appearance == "feature-2-new"
    assert (
        second.diagnostics.embedding_age_ms_by_track_id[1]
        == pytest.approx(500.0)
    )
    assert second_backend.calls[0][1] == [
        (200.0, 180.0, 250.0, 320.0),
    ]


def test_empty_request_mask_skips_backend_but_keeps_quality_accounting():
    backend = FakeMarsBackend(["unexpected"])

    result = attach_appearance_features(
        config=cfg(compute_min_interval_ms=0.0),
        state=AppearanceAttachmentState(),
        data=data(
            [tr(1, bbox=(10.0, 20.0, 40.0, 100.0))],
            mars_backend=backend,
            requested_candidate_indices=(),
            frame_id=1,
        ),
    )

    assert result.diagnostics.encoding_eligible == 1
    assert result.diagnostics.request_candidates == 0
    assert result.diagnostics.request_encoding_eligible == 0
    assert result.diagnostics.backend_calls == 0
    assert result.diagnostics.backend_requested == 0
    assert result.diagnostics.skip_reason == (
        "no_policy_requested_candidates"
    )
    assert backend.calls == []


@pytest.mark.parametrize(
    "requested_indices",
    [
        (0, 0),
        (-1,),
        (2,),
    ],
)
def test_invalid_request_mask_is_rejected(requested_indices):
    with pytest.raises(ValueError, match="request mask"):
        attach_appearance_features(
            config=cfg(),
            state=AppearanceAttachmentState(),
            data=data(
                [tr(1), tr(2)],
                requested_candidate_indices=requested_indices,
            ),
        )


@pytest.mark.parametrize(
    ("image_size", "expected"),
    [
        ((640, 360), (320.0, 180.0, 640.0, 360.0)),
        ((1280, 720), (640.0, 360.0, 1280.0, 720.0)),
        ((1920, 1080), (960.0, 540.0, 1920.0, 1080.0)),
    ],
)
def test_p064_master_bbox_maps_to_requested_appearance_resolution(
    image_size,
    expected,
):
    mapped = map_bbox_to_appearance_image(
        (960.0, 540.0, 1920.0, 1080.0),
        candidate_frame_width=1920.0,
        candidate_frame_height=1080.0,
        image_width=image_size[0],
        image_height=image_size[1],
    )

    assert mapped == pytest.approx(expected)


@pytest.mark.parametrize(
    ("bbox", "expected_width", "expected_height"),
    [
        ((-30.0, 100.0, 300.0, 500.0), 200.0, 266.6666667),
        ((1620.0, 100.0, 1950.0, 500.0), 200.0, 266.6666667),
        ((100.0, -30.0, 500.0, 300.0), 266.6666667, 200.0),
        ((100.0, 780.0, 500.0, 1110.0), 266.6666667, 200.0),
    ],
)
def test_p064_mapped_crop_clips_at_every_appearance_boundary(
    bbox,
    expected_width,
    expected_height,
):
    from thesis_bringup.tim_mars.crop_quality import (
        CropQualityThresholds,
        measure_crop_qualities,
    )

    mapped = map_bbox_to_appearance_image(
        bbox,
        candidate_frame_width=1920.0,
        candidate_frame_height=1080.0,
        image_width=1280,
        image_height=720,
    )
    quality = measure_crop_qualities(
        [mapped],
        image_width=1280,
        image_height=720,
        thresholds=CropQualityThresholds(
            min_width_px=0.0,
            min_height_px=0.0,
            max_clipping_fraction=1.0,
            min_aspect_ratio=0.0,
            max_aspect_ratio=10.0,
        ),
    )[0]

    assert quality.crop_width_px == pytest.approx(expected_width)
    assert quality.crop_height_px == pytest.approx(expected_height)
    assert quality.clipping_fraction > 0.0
