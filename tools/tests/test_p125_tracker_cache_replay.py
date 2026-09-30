"""Synthetic shared-cache tracker replay checks for Issue #125."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import cv2
import numpy as np

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues" / "p125" / "replay_shared_detector_cache.py"
)
SPEC = importlib.util.spec_from_file_location("p125_tracker_cache_replay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BOX = [1.0, 2.0, 11.0, 12.0]


def cache_document():
    return {
        "schema": "p125_shared_detector_sequence_cache_v1",
        "protocol_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "freeze_commit": "c" * 40,
        "detector_hef_sha256": "d" * 64,
        "split": "val",
        "sequence_name": "synthetic",
        "source_frame_count": 2,
        "frames": [
            {"source_frame_number": 1, "normalized_frame_index": 0,
             "detections": [
                 {"bbox_xyxy": BOX, "score": 0.35, "class_id": 0},
                 {"bbox_xyxy": BOX, "score": 0.6, "class_id": 0},
             ]},
            {"source_frame_number": 2, "normalized_frame_index": 1,
             "detections": []},
        ],
    }


def validate(cache):
    return MODULE.validate_sequence_cache(
        cache,
        protocol_sha256="a" * 64,
        manifest_sha256="b" * 64,
        freeze_commit="c" * 40,
        expected_split="val",
        expected_sequence="synthetic",
        expected_source_frame_numbers=[1, 2],
        detector_hef_sha256="d" * 64,
        detector_minimum_score=0.35,
    )


def test_exact_cache_provenance_and_frame_domain_required():
    frames = validate(cache_document())
    assert len(frames) == 2
    changed = cache_document()
    changed["manifest_sha256"] = "x" * 64
    with pytest.raises(ValueError, match="manifest_sha256"):
        validate(changed)
    changed = cache_document()
    changed["frames"][1]["source_frame_number"] = 1
    with pytest.raises(ValueError, match="mapping|domain"):
        validate(changed)


def test_replay_uses_tracker_specific_score_and_one_logical_tick_per_frame():
    frames = validate(cache_document())

    class FakeBackend:
        def __init__(self):
            self.calls = []

        def update(self, boxes, scores, timestamp):
            self.calls.append((boxes, scores, timestamp))
            return [SimpleNamespace(track_id=7, bbox_xyxy=BOX, score=0.6)]

    backend = FakeBackend()
    before = []
    replay = MODULE.replay_backend(
        frames=frames,
        backend=backend,
        minimum_score=0.5,
        before_frame=lambda frame, stamp: before.append((frame, stamp)),
    )
    assert backend.calls == [
        ([(1.0, 2.0, 11.0, 12.0)], [0.6], 1_000_000_000),
        ([], [], 2_000_000_000),
    ]
    assert before == [(1, 1_000_000_000), (2, 2_000_000_000)]
    assert replay[0]["tracks"][0]["track_id"] == 7
    assert replay[1]["normalized_frame_index"] == 1



def test_deepsort_image_callback_uses_matching_bgr_frame_and_logical_stamp(tmp_path, monkeypatch):
    writer_path = MODULE_PATH.with_name("write_raw_tracker_replay.py")
    writer_spec = importlib.util.spec_from_file_location("p125_raw_tracker_writer", writer_path)
    assert writer_spec is not None and writer_spec.loader is not None
    writer = importlib.util.module_from_spec(writer_spec)
    sys.modules[writer_spec.name] = writer
    writer_spec.loader.exec_module(writer)

    class FakeImage:
        def __init__(self):
            self.header = SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=0))

    sensor_msgs = ModuleType("sensor_msgs")
    sensor_msgs_msg = ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.Image = FakeImage
    sensor_msgs.msg = sensor_msgs_msg
    monkeypatch.setitem(sys.modules, "sensor_msgs", sensor_msgs)
    monkeypatch.setitem(sys.modules, "sensor_msgs.msg", sensor_msgs_msg)

    path = tmp_path / "0000001.png"
    source_image = np.full((3, 4, 3), (10, 20, 30), dtype=np.uint8)
    assert cv2.imwrite(str(path), source_image)

    class FakeBackend:
        def __init__(self):
            self.images = []

        def update_latest_image(self, message):
            self.images.append(message)

    backend = FakeBackend()
    callback = writer.make_deepsort_image_callback(
        backend=backend, image_paths={1: path}
    )
    callback(1, MODULE.LOGICAL_FRAME_TICK_NS)
    message = backend.images[0]
    assert (message.header.stamp.sec, message.header.stamp.nanosec) == (1, 0)
    assert (message.width, message.height, message.step, message.encoding) == (
        4, 3, 12, "bgr8"
    )
    assert bytes(message.data) == source_image.tobytes()



def test_duplicate_tracker_output_is_rejected():
    class DuplicateBackend:
        def update(self, boxes, scores, timestamp):
            track = SimpleNamespace(track_id=7, bbox_xyxy=BOX, score=0.6)
            return [track, track]

    with pytest.raises(ValueError, match="invalid tracker output"):
        MODULE.replay_backend(
            frames=validate(cache_document()),
            backend=DuplicateBackend(),
            minimum_score=0.35,
        )
