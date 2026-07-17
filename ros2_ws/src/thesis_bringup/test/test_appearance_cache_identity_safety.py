"""Identity-safety contract for TIM-MARS appearance caching.

A cached embedding belongs to one continuously observed tracker instance.
Tracker ID and TTL alone are not sufficient evidence of physical identity.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
)
from thesis_bringup.tim_mars.runtime import (
    TimMarsRuntime,
    TimMarsRuntimeConfig,
)
from thesis_bringup.tim_mars.target_memory import TargetMemoryConfig


def stamp(ns):
    return SimpleNamespace(
        sec=ns // 1_000_000_000,
        nanosec=ns % 1_000_000_000,
    )


def track(
    track_id,
    *,
    cx=50.0,
    cy=50.0,
    w=20.0,
    h=40.0,
):
    return SimpleNamespace(
        id=track_id,
        cx=cx,
        cy=cy,
        w=w,
        h=h,
        score=0.9,
    )


def tracks_message(
    *,
    frame_id,
    timestamp_ns,
    tracks,
):
    return SimpleNamespace(
        frame_id=frame_id,
        src_stamp_ns=0,
        header=SimpleNamespace(
            stamp=stamp(timestamp_ns),
        ),
        tracks=list(tracks),
    )


def runtime_config():
    return TimMarsRuntimeConfig(
        memory=TargetMemoryConfig(
            image_width=100.0,
            image_height=100.0,
            appearance_enabled=True,
        ),
        appearance=AppearanceAttachmentConfig(
            enabled=True,
            max_image_age_ms=250.0,
            compute_min_interval_ms=250.0,
            cache_ttl_ms=750.0,
        ),
        image_width=100.0,
        image_height=100.0,
        selected_track_id=0,
        image_buffer_size=16,
    )


class MarkerBackend:
    def __init__(self):
        self.calls = []

    def encode(self, image_bgr, boxes):
        self.calls.append(
            (
                image_bgr,
                list(boxes),
            )
        )
        marker = float(image_bgr[0, 0, 0])
        return [
            np.array(
                [
                    marker,
                    float(index + 1),
                ],
                dtype=np.float32,
            )
            for index, _ in enumerate(boxes)
        ]


def make_runtime():
    return TimMarsRuntime(
        runtime_config(),
        mars_backend=MarkerBackend(),
    )


def seed_embedding(
    runtime,
    *,
    frame_id=10,
    timestamp_ns=1_000_000_000,
    candidate=None,
):
    candidate = candidate or track(7)

    runtime.add_image(
        timestamp_ns,
        np.full(
            (100, 100, 3),
            50,
            dtype=np.uint8,
        ),
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=frame_id,
            timestamp_ns=timestamp_ns,
            tracks=[candidate],
        )
    )

    assert result.diagnostics.appearance_skip_reason == "ok"
    assert result.candidates[0].appearance is not None

    return result.candidates[0].appearance.copy()


def test_cache_entry_records_source_frame_generation_and_bbox():
    runtime = make_runtime()

    seed_embedding(runtime)

    entry = runtime.appearance_state.cache_by_track_id[7]

    assert entry.source_frame_id == 10
    assert entry.frame_generation >= 1
    assert entry.track_generation >= 1
    assert entry.source_bbox == pytest.approx(
        (
            40.0,
            30.0,
            60.0,
            70.0,
        )
    )


def test_continuous_plausible_same_id_reuses_cached_embedding():
    runtime = make_runtime()
    expected = seed_embedding(runtime)

    result = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_100_000_000,
            tracks=[
                track(
                    7,
                    cx=52.0,
                    cy=51.0,
                )
            ],
        )
    )

    assert result.diagnostics.appearance_skip_reason == "cached_same_image"
    assert np.array_equal(
        result.candidates[0].appearance,
        expected,
    )

    entry = runtime.appearance_state.cache_by_track_id[7]
    assert entry.track_generation >= 1


def test_embedding_age_is_reported_for_each_cached_candidate():
    runtime = make_runtime()
    seed_embedding(runtime)

    result = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_100_000_000,
            tracks=[track(7)],
        )
    )

    ages = result.diagnostics.appearance_embedding_age_ms_by_track_id

    assert set(ages) == {7}
    assert ages[7] == pytest.approx(100.0)


def test_observed_absence_then_reused_id_gets_no_old_embedding():
    runtime = make_runtime()
    seed_embedding(runtime)

    runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_100_000_000,
            tracks=[],
        )
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=12,
            timestamp_ns=1_200_000_000,
            tracks=[track(7)],
        )
    )

    assert result.candidates[0].appearance is None


def test_implausible_centre_jump_invalidates_cached_embedding():
    runtime = make_runtime()
    seed_embedding(runtime)

    result = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_100_000_000,
            tracks=[
                track(
                    7,
                    cx=90.0,
                    cy=80.0,
                    w=10.0,
                    h=20.0,
                )
            ],
        )
    )

    assert result.candidates[0].appearance is None


def test_implausible_scale_jump_invalidates_cached_embedding():
    runtime = make_runtime()
    seed_embedding(runtime)

    result = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_100_000_000,
            tracks=[
                track(
                    7,
                    cx=50.0,
                    cy=50.0,
                    w=90.0,
                    h=90.0,
                )
            ],
        )
    )

    assert result.candidates[0].appearance is None


def test_nonmonotonic_frame_id_starts_new_track_generation():
    runtime = make_runtime()
    seed_embedding(runtime)

    result = runtime.process_tracks(
        tracks_message(
            frame_id=1,
            timestamp_ns=1_100_000_000,
            tracks=[track(7)],
        )
    )

    assert result.candidates[0].appearance is None


def test_invalid_track_timestamp_terminates_cache_continuity():
    runtime = make_runtime()
    seed_embedding(runtime)

    invalid = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=0,
            tracks=[track(7)],
        )
    )

    assert invalid.diagnostics.track_timestamp_ns is None
    assert (
        invalid.diagnostics.appearance_skip_reason
        == "invalid_track_timestamp"
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=12,
            timestamp_ns=1_200_000_000,
            tracks=[track(7)],
        )
    )

    assert result.candidates[0].appearance is None
