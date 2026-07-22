"""Test DeepSORT causal image selection and coordinate-contract parsing."""

from __future__ import annotations

import numpy as np

from thesis_tracker.backends.deepsort_core_backend import CausalImageBuffer
from thesis_tracker.nodes.tracker_node import _parse_frame_id


def _image(value: int) -> np.ndarray:
    return np.full((2, 3, 3), value, dtype=np.uint8)


def test_causal_buffer_handles_out_of_order_and_future_images():
    buffer = CausalImageBuffer(max_size=8)
    buffer.add(300, _image(3))
    buffer.add(100, _image(1))
    buffer.add(200, _image(2))

    selected = buffer.select(track_stamp_ns=250, max_age_ns=100)

    assert selected is not None
    assert selected.stamp_ns == 200
    assert int(selected.image_bgr[0, 0, 0]) == 2
    assert buffer.select(track_stamp_ns=50, max_age_ns=1000) is None


def test_causal_buffer_replaces_duplicate_timestamps_deterministically():
    buffer = CausalImageBuffer(max_size=8)
    buffer.add(200, _image(2))
    buffer.add(200, _image(9))

    selected = buffer.select(track_stamp_ns=200, max_age_ns=0)

    assert selected is not None
    assert int(selected.image_bgr[0, 0, 0]) == 9


def test_causal_buffer_rejects_missing_invalid_and_stale_images():
    buffer = CausalImageBuffer(max_size=2)

    assert not buffer.add(0, _image(0))
    assert buffer.select(track_stamp_ns=100, max_age_ns=100) is None

    buffer.add(100, _image(1))
    assert buffer.select(track_stamp_ns=500, max_age_ns=399) is None
    assert buffer.select(track_stamp_ns=0, max_age_ns=1000) is None


def test_causal_buffer_is_bounded_by_timestamp_order():
    buffer = CausalImageBuffer(max_size=2)
    buffer.add(300, _image(3))
    buffer.add(100, _image(1))
    buffer.add(200, _image(2))

    assert buffer.select(track_stamp_ns=150, max_age_ns=1000) is None
    selected = buffer.select(track_stamp_ns=250, max_age_ns=1000)
    assert selected is not None
    assert selected.stamp_ns == 200


def test_tracker_parses_legacy_and_versioned_frame_ids():
    versioned = (
        "tim_mars_source_pixels_resize_v1;frame=42;source=640x480;"
        "inference=640x640;scale=1,1.33333333;pad=0,0"
    )

    assert _parse_frame_id("frame_41") == 41
    assert _parse_frame_id(versioned) == 42
    assert _parse_frame_id("camera") == 0
