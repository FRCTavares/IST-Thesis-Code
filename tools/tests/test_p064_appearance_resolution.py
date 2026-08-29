"""Focused Issue #64 controlled-appearance contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from thesis_msgs.msg import Track2D, Track2DArray

from tools.experiments.p064_appearance_contract import (
    ImageFrameRecord,
    aspect_ratio,
    candidate_stream_digest,
    classify_resize,
    image_stream_digest,
    load_variant_provenance,
    parse_resolution,
    timestamp_digest,
    validate_candidate_digest,
    validate_exact_correspondence,
    validate_resize_evidence,
    validate_track_timestamps,
    validate_variant_streams,
)


PREPARER_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "prepare_p064_appearance_variants.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_p064", PREPARER_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARER)


def record(timestamp_ns, width=1920, height=1080, token="a"):
    return ImageFrameRecord(
        timestamp_ns=timestamp_ns,
        width=width,
        height=height,
        encoding="bgr8",
        step=width * 3,
        data_sha256=hashlib.sha256(token.encode()).hexdigest(),
    )


def track_message(track_id=7, cx=100.0):
    message = Track2DArray()
    message.header.stamp.sec = 1
    message.header.stamp.nanosec = 2
    message.header.frame_id = "camera"
    message.frame_id = 3
    message.src_stamp_ns = 1_000_000_002
    message.t_cam_msg_seen_ns = 10
    message.t_track_cb_start_ns = 11
    message.t_track_cb_end_ns = 12
    track = Track2D()
    track.id = track_id
    track.cx = cx
    track.cy = 200.0
    track.w = 30.0
    track.h = 60.0
    track.score = 0.75
    track.label = "person"
    message.tracks = [track]
    return message


def test_exact_timestamp_correspondence_ignores_storage_order():
    master = [record(30, token="c"), record(10), record(20, token="b")]
    appearance = [
        record(20, 1280, 720, "y"),
        record(30, 1280, 720, "z"),
        record(10, 1280, 720, "x"),
    ]

    master_ordered, appearance_ordered = validate_exact_correspondence(
        master, appearance
    )

    assert [item.timestamp_ns for item in master_ordered] == [10, 20, 30]
    assert [item.timestamp_ns for item in appearance_ordered] == [10, 20, 30]
    assert timestamp_digest(master) == timestamp_digest(appearance)


@pytest.mark.parametrize(
    "appearance",
    [
        [record(10, 1280, 720), record(20, 1280, 720)],
        [
            record(10, 1280, 720),
            record(20, 1280, 720),
            record(40, 1280, 720),
        ],
    ],
)
def test_missing_or_future_only_timestamp_fails(appearance):
    master = [record(10), record(20), record(30)]
    with pytest.raises(ValueError, match="timestamps|frame-count"):
        validate_exact_correspondence(master, appearance)


def test_duplicate_appearance_timestamp_is_ambiguous():
    with pytest.raises(ValueError, match="duplicate/ambiguous"):
        validate_exact_correspondence(
            [record(10), record(20, token="b")],
            [
                record(10, 1280, 720),
                record(10, 1280, 720, "duplicate"),
            ],
        )


def test_frame_count_mismatch_fails():
    with pytest.raises(ValueError, match="frame-count"):
        validate_exact_correspondence(
            [record(10), record(20, token="b")],
            [record(10, 1280, 720)],
        )


def test_image_digest_includes_pixels_and_resolution():
    first = [record(10)]
    changed_pixels = [record(10, token="changed")]
    changed_size = [record(10, 1280, 720)]
    assert image_stream_digest(first) != image_stream_digest(changed_pixels)
    assert image_stream_digest(first) != image_stream_digest(changed_size)


def test_candidate_digest_is_stable_and_detects_geometry_and_order():
    first = track_message(7, 100.0)
    second = track_message(8, 300.0)
    baseline = candidate_stream_digest(
        [(1_000_000_002, 100, first), (1_000_000_002, 101, second)]
    )
    equal = candidate_stream_digest(
        [
            (1_000_000_002, 100, track_message(7, 100.0)),
            (1_000_000_002, 101, track_message(8, 300.0)),
        ]
    )
    changed = candidate_stream_digest(
        [
            (1_000_000_002, 100, track_message(7, 101.0)),
            (1_000_000_002, 101, track_message(8, 300.0)),
        ]
    )
    reordered = candidate_stream_digest(
        [(1_000_000_002, 101, second), (1_000_000_002, 100, first)]
    )

    assert baseline == equal
    assert baseline != changed
    assert baseline != reordered
    validate_candidate_digest(baseline, equal)
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_candidate_digest(baseline, changed)


def test_candidate_digest_rejects_invalid_expected_sha():
    with pytest.raises(ValueError, match="not SHA-256"):
        validate_candidate_digest("0" * 64, "not-a-sha")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("640x480", (640, 480)),
        ("640x360", (640, 360)),
        ("1280x720", (1280, 720)),
        ("1920x1080", (1920, 1080)),
    ],
)
def test_required_resolutions_parse(value, expected):
    assert parse_resolution(value) == expected


def test_resize_class_and_aspect_ratio_provenance():
    assert classify_resize(1920, 1080, 1280, 720) == "downsample"
    assert classify_resize(1920, 1080, 1920, 1080) == "same_size"
    assert classify_resize(640, 480, 1280, 720) == "upsample_control"
    assert aspect_ratio(640, 480) == pytest.approx(4 / 3)
    assert aspect_ratio(1280, 720) == pytest.approx(16 / 9)


def test_complete_fov_resize_preserves_all_corner_regions():
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:2, :2] = (10, 20, 30)
    image[:2, 2:] = (40, 50, 60)
    image[2:, :2] = (70, 80, 90)
    image[2:, 2:] = (100, 110, 120)

    resized = PREPARER.resize_complete_fov(
        image,
        output_width=2,
        output_height=2,
        resampling="area",
    )

    assert resized.tolist() == [
        [[10, 20, 30], [40, 50, 60]],
        [[70, 80, 90], [100, 110, 120]],
    ]


def test_wrong_variant_schema_fails_closed(tmp_path):
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        load_variant_provenance(path)


def variant_payload(master, appearance):
    return {
        "master": {
            "image_stream_sha256": image_stream_digest(master),
            "timestamp_sha256": timestamp_digest(master),
            "frame_count": len(master),
            "width": master[0].width,
            "height": master[0].height,
        },
        "output": {
            "image_stream_sha256": image_stream_digest(appearance),
            "timestamp_sha256": timestamp_digest(appearance),
            "frame_count": len(appearance),
            "width": appearance[0].width,
            "height": appearance[0].height,
        },
    }


def test_variant_provenance_accepts_exact_master_and_output():
    master = [record(10), record(20, token="b")]
    appearance = [
        record(10, 1280, 720, "x"),
        record(20, 1280, 720, "y"),
    ]
    validate_variant_streams(
        variant_payload(master, appearance),
        master,
        appearance,
    )


def test_wrong_master_provenance_fails():
    master = [record(10), record(20, token="b")]
    appearance = [
        record(10, 1280, 720, "x"),
        record(20, 1280, 720, "y"),
    ]
    payload = variant_payload(master, appearance)
    payload["master"]["image_stream_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="master image stream"):
        validate_variant_streams(payload, master, appearance)


def test_candidate_timestamps_require_exact_master_frames():
    master = [record(10), record(20, token="b")]
    validate_track_timestamps([10, 20], master)
    with pytest.raises(ValueError, match="no exact master image"):
        validate_track_timestamps([30], master)
    with pytest.raises(ValueError, match="non-positive"):
        validate_track_timestamps([0], master)
    with pytest.raises(ValueError, match="duplicate/ambiguous"):
        validate_track_timestamps([10, 10], master)


def test_upsampling_is_rejected_unless_explicit_control():
    with pytest.raises(ValueError, match="not higher-resolution evidence"):
        validate_resize_evidence(
            640,
            480,
            1280,
            720,
            allow_upsample_control=False,
        )
    assert (
        validate_resize_evidence(
            640,
            480,
            1280,
            720,
            allow_upsample_control=True,
        )
        == "upsample_control"
    )
