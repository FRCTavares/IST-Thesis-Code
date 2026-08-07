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
    appearance_request_policy="all_candidates",
    auto_select_largest=False,
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
        appearance_request_policy=(
            appearance_request_policy
        ),
        selected_track_id=selected_track_id,
        auto_select_largest=auto_select_largest,
        image_buffer_size=16,
    )


class FakeBackend:
    def __init__(self):
        self.calls = []

    def encode(self, image_bgr, boxes):
        self.calls.append(list(boxes))
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


def test_streaming_add_image_matches_bulk_replace_images():
    # Regression coverage for the deterministic-replay memory fix
    # (Slice 23): run_deterministic_tim_replay.py used to preload every
    # decoded image into one Python list before calling replace_images()
    # once, which exhausted memory on long/high-resolution external
    # sequences. It now streams images into the runtime one at a time via
    # add_image() (the same bounded, live-mode-safe method the real ROS
    # node uses), releasing each sorted track event for processing only
    # once every image at or before its timestamp has been added.
    #
    # This proves the two approaches select identical causal images for
    # every query in a representative timeline: a gap between images, a
    # duplicate timestamp (last-write-wins per replace_images'
    # documented contract), a query before the first image, a query
    # exactly on an image timestamp, a query strictly between two images,
    # and a query after the last image.
    image_stamps = [100, 100, 250, 250, 400, 900, 900, 1500]
    images = [
        (stamp_ns, np.full((4, 4, 3), index, dtype=np.uint8))
        for index, stamp_ns in enumerate(image_stamps)
    ]

    query_timestamps = [50, 100, 175, 250, 300, 899, 900, 901, 5000]

    bulk = TimMarsRuntime(runtime_config())
    bulk.replace_images(images)
    bulk_selection = [
        (
            frame.stamp_ns
            if (frame := bulk.select_causal_image(query))
            else None
        )
        for query in query_timestamps
    ]

    streaming = TimMarsRuntime(runtime_config())
    sorted_unique_images = sorted(
        dict(images).items()
    )
    streaming_selection = []

    image_index = 0
    for query in query_timestamps:
        while (
            image_index < len(sorted_unique_images)
            and sorted_unique_images[image_index][0] <= query
        ):
            stamp_ns, image = sorted_unique_images[image_index]
            streaming.add_image(stamp_ns, image)
            image_index += 1

        frame = streaming.select_causal_image(query)
        streaming_selection.append(
            frame.stamp_ns if frame else None
        )

    assert streaming_selection == bulk_selection
    assert bulk_selection == [
        None,  # before any image
        100,  # exactly on the (deduplicated, last-write-wins) first image
        100,  # strictly between images, gap included
        250,  # exactly on the deduplicated second image
        250,  # strictly between images
        400,  # just before the 900 duplicate pair
        900,  # exactly on the deduplicated third image
        900,  # strictly after 900, before 1500
        1500,  # after the last image
    ]


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
    assert result.output.hard_negative_current_frame_id == 10
    assert result.candidates[0].tracker_frame_id == 10
    assert (
        result.candidates[0].tracker_timestamp_ns
        == 1_000_000_000
    )
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


def test_runtime_reports_synchronous_cpu_backend_workload_diagnostics():
    backend = FakeBackend()
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=backend,
    )
    runtime.add_image(
        900_000_000,
        np.full((100, 100, 3), 90, dtype=np.uint8),
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=12,
            timestamp_ns=1_000_000_000,
            tracks=[track(1)],
        )
    )

    diagnostics = result.diagnostics

    assert diagnostics.appearance_skip_reason == "ok"
    assert diagnostics.appearance_encoding_eligible == 1
    assert diagnostics.appearance_backend_calls == 1
    assert diagnostics.appearance_backend_requested == 1
    assert diagnostics.appearance_backend_returned == 1
    assert diagnostics.appearance_backend_valid == 1
    assert diagnostics.appearance_backend_wall_ms >= 0.0
    assert diagnostics.appearance_features_valid == 1


def test_runtime_all_candidates_default_preserves_multi_crop_workload():
    backend = FakeBackend()
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
        ),
        mars_backend=backend,
    )
    runtime.add_image(
        900_000_000,
        np.full((100, 100, 3), 90, dtype=np.uint8),
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=1,
            timestamp_ns=1_000_000_000,
            tracks=[
                track(1, cx=40.0, cy=50.0),
                track(2, cx=75.0, cy=50.0),
            ],
        )
    )

    diagnostics = result.diagnostics

    assert diagnostics.appearance_request_policy == "all_candidates"
    assert diagnostics.appearance_request_reason == "all_candidates"
    assert diagnostics.appearance_request_candidates == 2
    assert diagnostics.appearance_request_track_ids == (1, 2)
    assert diagnostics.appearance_encoding_eligible == 2
    assert diagnostics.appearance_request_encoding_eligible == 2
    assert diagnostics.appearance_backend_requested == 2
    assert len(backend.calls) == 1
    assert len(backend.calls[0]) == 2


def test_runtime_geometry_winner_encodes_only_selected_geometry_candidate():
    backend = FakeBackend()
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=1,
            appearance_request_policy="geometry_winner",
        ),
        mars_backend=backend,
    )

    runtime.add_image(
        900_000_000,
        np.full((100, 100, 3), 90, dtype=np.uint8),
    )

    first = runtime.process_tracks(
        tracks_message(
            frame_id=1,
            timestamp_ns=1_000_000_000,
            tracks=[
                track(1, cx=50.0, cy=50.0),
                track(2, cx=85.0, cy=75.0),
            ],
        )
    )

    assert first.output.target_track_id == 1
    assert first.diagnostics.appearance_request_reason == (
        "pending_operator_selection"
    )
    assert first.diagnostics.appearance_request_track_ids == (1,)
    assert first.diagnostics.appearance_backend_requested == 1

    runtime.add_image(
        1_900_000_000,
        np.full((100, 100, 3), 91, dtype=np.uint8),
    )

    second = runtime.process_tracks(
        tracks_message(
            frame_id=2,
            timestamp_ns=2_000_000_000,
            tracks=[
                track(1, cx=90.0, cy=80.0),
                track(2, cx=51.0, cy=50.0),
            ],
        )
    )

    diagnostics = second.diagnostics

    assert diagnostics.appearance_candidates == 2
    assert diagnostics.appearance_request_policy == "geometry_winner"
    assert diagnostics.appearance_request_reason == "geometry_winner"
    assert diagnostics.appearance_request_candidates == 1
    assert diagnostics.appearance_request_track_ids == (2,)
    assert diagnostics.appearance_encoding_eligible == 2
    assert diagnostics.appearance_request_encoding_eligible == 1
    assert diagnostics.appearance_backend_requested == 1
    assert len(backend.calls) == 2
    assert backend.calls[-1] == [
        (41.0, 30.0, 61.0, 70.0),
    ]


def test_runtime_geometry_winner_can_request_no_fresh_encoding():
    backend = FakeBackend()
    runtime = TimMarsRuntime(
        runtime_config(
            appearance_enabled=True,
            selected_track_id=0,
            appearance_request_policy="geometry_winner",
        ),
        mars_backend=backend,
    )
    runtime.add_image(
        900_000_000,
        np.full((100, 100, 3), 90, dtype=np.uint8),
    )

    result = runtime.process_tracks(
        tracks_message(
            frame_id=1,
            timestamp_ns=1_000_000_000,
            tracks=[track(7)],
        )
    )

    diagnostics = result.diagnostics

    assert diagnostics.appearance_request_reason == "no_selected_target"
    assert diagnostics.appearance_request_candidates == 0
    assert diagnostics.appearance_request_track_ids == ()
    assert diagnostics.appearance_encoding_eligible == 1
    assert diagnostics.appearance_request_encoding_eligible == 0
    assert diagnostics.appearance_backend_calls == 0
    assert diagnostics.appearance_backend_requested == 0
    assert diagnostics.appearance_skip_reason == (
        "no_policy_requested_candidates"
    )
    assert backend.calls == []
