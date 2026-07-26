"""Runtime provenance tests for positive-memory bootstrap."""

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
from thesis_bringup.tim_mars.types import (
    TargetMemoryConfig,
)


class _Backend:
    def __init__(self):
        self.calls = []

    def encode(self, image_bgr, boxes):
        self.calls.append((image_bgr, tuple(boxes)))
        return [
            np.asarray(
                [1.0, 0.0, 0.0],
                dtype=np.float32,
            )
            for _ in boxes
        ]


def _stamp(timestamp_ns):
    return SimpleNamespace(
        sec=int(timestamp_ns // 1_000_000_000),
        nanosec=int(timestamp_ns % 1_000_000_000),
    )


def _tracks_message(
    *,
    frame_id,
    timestamp_ns,
    x_offset=0.0,
):
    return SimpleNamespace(
        frame_id=int(frame_id),
        src_stamp_ns=0,
        header=SimpleNamespace(
            stamp=_stamp(timestamp_ns),
        ),
        tracks=[
            SimpleNamespace(
                id=5,
                cx=130.0 + float(x_offset),
                cy=170.0,
                w=60.0,
                h=140.0,
                score=0.95,
            ),
        ],
    )


def _runtime():
    return TimMarsRuntime(
        TimMarsRuntimeConfig(
            memory=TargetMemoryConfig(
                image_width=640,
                image_height=480,
                appearance_enabled=True,
                appearance_protected_memory_enabled=True,
                appearance_conservative_enabled=False,
                hard_negative_memory_enabled=False,
            ),
            appearance=AppearanceAttachmentConfig(
                enabled=True,
                compute_min_interval_ms=0.0,
                max_image_age_ms=1_000.0,
                cache_ttl_ms=1_000.0,
            ),
            image_width=640.0,
            image_height=480.0,
        ),
        mars_backend=_Backend(),
    )


def test_cached_embedding_source_is_recorded_at_operator_bootstrap():
    """Record accepted-frame and original embedding-source evidence."""
    runtime = _runtime()

    source_image_timestamp_ns = 1_980_000_000
    source_track_timestamp_ns = 2_000_000_000
    accepted_track_timestamp_ns = 2_050_000_000

    runtime.add_image(
        source_image_timestamp_ns,
        np.zeros((480, 640, 3), dtype=np.uint8),
    )

    source_result = runtime.process_tracks(
        _tracks_message(
            frame_id=40,
            timestamp_ns=source_track_timestamp_ns,
        )
    )

    assert (
        source_result.output
        .positive_memory_bootstrap_event
        is None
    )
    assert len(runtime.mars_backend.calls) == 1

    runtime.request_selection(5)

    accepted_result = runtime.process_tracks(
        _tracks_message(
            frame_id=41,
            timestamp_ns=accepted_track_timestamp_ns,
            x_offset=2.0,
        )
    )

    assert len(runtime.mars_backend.calls) == 1
    assert (
        accepted_result.diagnostics.appearance_skip_reason
        == 'cached_same_image'
    )

    event = (
        accepted_result.output
        .positive_memory_bootstrap_event
    )

    assert event is not None
    assert event.action == 'operator_anchor_initialised'
    assert event.track_id == 5

    assert event.frame_id == 41
    assert (
        event.track_timestamp_ns
        == accepted_track_timestamp_ns
    )
    assert (
        event.selected_image_timestamp_ns
        == source_image_timestamp_ns
    )
    assert event.image_track_offset_ms == pytest.approx(70.0)

    assert event.appearance_source_frame_id == 40
    assert (
        event.appearance_source_image_timestamp_ns
        == source_image_timestamp_ns
    )
    assert (
        event.appearance_embedded_ns
        == source_track_timestamp_ns
    )
    assert (
        event.appearance_embedding_age_ms
        == pytest.approx(50.0)
    )
    assert event.appearance_frame_generation == 1
    assert event.appearance_track_generation == 1

    assert event.accepted_bbox == (
        102.0,
        100.0,
        162.0,
        240.0,
    )
    assert event.appearance_source_bbox == (
        100.0,
        100.0,
        160.0,
        240.0,
    )

    assert event.accepted_crop_quality is not None
    assert (
        event.accepted_crop_quality
        .memory_update_eligible
    )
    assert (
        event.appearance_source_crop_quality
        is not None
    )
    assert (
        event.appearance_source_crop_quality
        .memory_update_eligible
    )
