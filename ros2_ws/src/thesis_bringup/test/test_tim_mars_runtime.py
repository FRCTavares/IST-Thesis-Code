"""Tests for the shared ROS-free TIM-MARS runtime."""

from types import SimpleNamespace

import numpy as np

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


def track(track_id, *, cx=50.0, cy=50.0, w=20.0, h=40.0):
    return SimpleNamespace(
        id=track_id,
        cx=cx,
        cy=cy,
        w=w,
        h=h,
        score=0.9,
    )


def tracks_message(
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


def runtime_config(
    *,
    appearance_enabled=False,
    selected_track_id=1,
):
    return TimMarsRuntimeConfig(
        memory=TargetMemoryConfig(
            image_width=100.0,
            image_height=100.0,
            appearance_enabled=appearance_enabled,
        ),
        appearance=AppearanceAttachmentConfig(
            enabled=appearance_enabled,
            max_image_age_ms=250.0,
            compute_min_interval_ms=250.0,
            cache_ttl_ms=750.0,
        ),
        image_width=100.0,
        image_height=100.0,
        selected_track_id=selected_track_id,
        image_buffer_size=16,
    )


class FakeBackend:
    def encode(self, image_bgr, boxes):
        marker = float(image_bgr[0, 0, 0])
        return [
            np.array([marker, float(index + 1)], dtype=np.float32)
            for index, _ in enumerate(boxes)
        ]


def test_image_insertion_order_does_not_change_causal_selection():
    image_100 = np.full((10, 10, 3), 100, dtype=np.uint8)
    image_200 = np.full((10, 10, 3), 200, dtype=np.uint8)
    image_300 = np.full((10, 10, 3), 300, dtype=np.uint8)

    first = TimMarsRuntime(runtime_config())
    first.replace_images(
        [
            (100, image_100),
            (200, image_200),
            (300, image_300),
        ]
    )

    second = TimMarsRuntime(runtime_config())
    second.replace_images(
        [
            (300, image_300),
            (100, image_100),
            (200, image_200),
        ]
    )

    assert first.select_causal_image(250).stamp_ns == 200
    assert second.select_causal_image(250).stamp_ns == 200


def test_future_image_is_not_selected():
    runtime = TimMarsRuntime(runtime_config())
    runtime.add_image(
        200,
        np.zeros((10, 10, 3), dtype=np.uint8),
    )

    assert runtime.select_causal_image(150) is None


def test_equal_timestamp_image_is_selected():
    runtime = TimMarsRuntime(runtime_config())
    runtime.add_image(
        200,
        np.zeros((10, 10, 3), dtype=np.uint8),
    )

    selected = runtime.select_causal_image(200)

    assert selected is not None
    assert selected.stamp_ns == 200


def test_process_tracks_selects_requested_visible_target():
    runtime = TimMarsRuntime(runtime_config(selected_track_id=7))

    result = runtime.process_tracks(
        tracks_message(
            frame_id=10,
            timestamp_ns=1_000_000_000,
            tracks=[track(7)],
        )
    )

    assert result.output.target_track_id == 7
    assert result.output.reason == "operator_select"
    assert result.diagnostics.track_timestamp_ns == 1_000_000_000
    assert result.diagnostics.selected_image_timestamp_ns is None
    assert result.diagnostics.image_track_offset_ms is None
    assert result.diagnostics.appearance_warning is None
    assert result.diagnostics.appearance_update_cooldown_remaining == 0
    assert result.diagnostics.candidate_track_ids == (7,)


def test_complete_image_set_produces_same_result_regardless_ingestion_order():
    image_100 = np.full((100, 100, 3), 100, dtype=np.uint8)
    image_200 = np.full((100, 100, 3), 200, dtype=np.uint8)

    first = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=FakeBackend(),
    )
    first.replace_images(
        [
            (100_000_000, image_100),
            (200_000_000, image_200),
        ]
    )

    second = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=FakeBackend(),
    )
    second.replace_images(
        [
            (200_000_000, image_200),
            (100_000_000, image_100),
        ]
    )

    message = tracks_message(
        frame_id=1,
        timestamp_ns=200_000_000,
        tracks=[track(1)],
    )

    first_result = first.process_tracks(message)
    second_result = second.process_tracks(message)

    assert first_result.output.target_track_id == 1
    assert second_result.output.target_track_id == 1
    assert (
        first_result.diagnostics.selected_image_timestamp_ns
        == second_result.diagnostics.selected_image_timestamp_ns
        == 200_000_000
    )
    assert (
        first_result.diagnostics.image_track_offset_ms
        == second_result.diagnostics.image_track_offset_ms
        == 0.0
    )
    assert np.array_equal(
        first_result.candidates[0].appearance,
        second_result.candidates[0].appearance,
    )


def test_invalid_track_timestamp_disables_current_image_attachment():
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=FakeBackend(),
    )
    runtime.add_image(
        100,
        np.zeros((100, 100, 3), dtype=np.uint8),
    )

    message = SimpleNamespace(
        frame_id=1,
        src_stamp_ns=0,
        header=SimpleNamespace(
            stamp=stamp(0),
        ),
        tracks=[track(1)],
    )

    result = runtime.process_tracks(message)

    assert result.diagnostics.track_timestamp_ns is None
    assert result.diagnostics.selected_image_timestamp_ns is None
    assert (
        result.diagnostics.appearance_skip_reason
        == "invalid_track_timestamp"
    )


def test_live_add_image_remains_bounded_to_configured_buffer_size():
    runtime = TimMarsRuntime(runtime_config())

    for stamp_ns in range(1, 25):
        runtime.add_image(
            stamp_ns,
            np.full((2, 2, 3), stamp_ns, dtype=np.uint8),
        )

    assert len(runtime._images) == 16
    assert runtime._images[0].stamp_ns == 9
    assert runtime._images[-1].stamp_ns == 24
    assert runtime.select_causal_image(8) is None
    assert runtime.select_causal_image(20).stamp_ns == 20


def test_replace_images_preserves_complete_offline_timeline():
    runtime = TimMarsRuntime(runtime_config())

    runtime.replace_images(
        [
            (
                stamp_ns,
                np.full((2, 2, 3), stamp_ns, dtype=np.uint8),
            )
            for stamp_ns in range(1, 101)
        ]
    )

    assert len(runtime._images) == 100
    assert runtime._images[0].stamp_ns == 1
    assert runtime._images[-1].stamp_ns == 100
    assert runtime.select_causal_image(20).stamp_ns == 20
    assert runtime.select_causal_image(64).stamp_ns == 64


def test_replace_images_sorts_deduplicates_and_discards_invalid_timestamps():
    runtime = TimMarsRuntime(runtime_config())

    runtime.replace_images(
        [
            (300, "image-300"),
            (0, "invalid-zero"),
            (-1, "invalid-negative"),
            (100, "image-100"),
            (200, "image-200-old"),
            (200, "image-200-new"),
        ]
    )

    assert [frame.stamp_ns for frame in runtime._images] == [
        100,
        200,
        300,
    ]
    assert runtime.select_causal_image(200).image_bgr == "image-200-new"


def test_delayed_causal_image_is_selected_and_reports_exact_offset():
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=FakeBackend(),
    )
    runtime.replace_images(
        [
            (
                800_000_000,
                np.full((100, 100, 3), 80, dtype=np.uint8),
            ),
            (
                900_000_000,
                np.full((100, 100, 3), 90, dtype=np.uint8),
            ),
        ]
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=10,
            timestamp_ns=1_000_000_000,
            tracks=[track(1)],
        )
    )

    assert result.diagnostics.track_timestamp_ns == 1_000_000_000
    assert result.diagnostics.selected_image_timestamp_ns == 900_000_000
    assert result.diagnostics.image_track_offset_ms == 100.0
    assert result.diagnostics.appearance_skip_reason == "ok"
    assert result.diagnostics.appearance_features_valid == 1
    assert result.candidates[0].appearance is not None
    assert result.candidates[0].appearance[0] == 90.0


def test_stale_causal_image_is_reported_but_not_freshly_encoded():
    backend = FakeBackend()
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=backend,
    )
    runtime.replace_images(
        [
            (
                700_000_000,
                np.full((100, 100, 3), 70, dtype=np.uint8),
            ),
        ]
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=11,
            timestamp_ns=1_000_000_000,
            tracks=[track(1)],
        )
    )

    assert result.diagnostics.track_timestamp_ns == 1_000_000_000
    assert result.diagnostics.selected_image_timestamp_ns == 700_000_000
    assert result.diagnostics.image_track_offset_ms == 300.0
    assert result.diagnostics.appearance_skip_reason == "stale_image"
    assert result.diagnostics.appearance_features_valid == 0
    assert result.candidates[0].appearance is None
    assert runtime.appearance_state.last_mars_compute_ns == 0
    assert runtime.appearance_state.last_mars_image_seq == -1
    assert runtime.appearance_state.cache_by_track_id == {}


def test_runtime_diagnostics_use_public_memory_cooldown_property():
    runtime = TimMarsRuntime(runtime_config(selected_track_id=7))

    result = runtime.process_tracks(
        tracks_message(
            frame_id=10,
            timestamp_ns=1_000_000_000,
            tracks=[track(7)],
        )
    )

    assert (
        result.diagnostics.appearance_update_cooldown_remaining
        == runtime.memory.appearance_update_cooldown_frames_remaining
    )
