"""Synthetic production-preprocessing and detector-cache contract checks."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues" / "p125" / "shared_detector_cache.py"
)
SPEC = importlib.util.spec_from_file_location("p125_shared_detector_cache", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_preparation_matches_direct_resize_and_bgr_to_rgb():
    source = np.zeros((3, 5, 3), dtype=np.uint8)
    source[:, :, 0] = 13
    source[:, :, 1] = 44
    source[:, :, 2] = 210
    prepared, transform = MODULE.prepare_source_image(
        source, inference_width=10, inference_height=6
    )
    expected = cv2.cvtColor(
        cv2.resize(source, (10, 6), interpolation=cv2.INTER_LINEAR),
        cv2.COLOR_BGR2RGB,
    )
    assert np.array_equal(prepared, expected)
    assert transform.contract == "tim_mars_source_pixels_resize_v1"
    assert transform.inference_xyxy_to_source((2, 2, 8, 4)) == (1, 1, 4, 2)


def test_detection_mapping_applies_score_label_and_source_coordinates():
    transform = MODULE.ImageTransform.direct_resize(1280, 720, 640, 640)
    detections = MODULE.source_pixel_detections([
        {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5,
         "score": 0.35, "label": "person", "class_id": 0},
        {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1,
         "score": 0.34, "label": "person", "class_id": 0},
        {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1,
         "score": 0.9, "label": "car", "class_id": 2},
    ], transform=transform)
    assert detections == [{
        "bbox_xyxy": [320.0, 180.0, 960.0, 540.0],
        "score": 0.35,
        "class_id": 0,
    }]


def test_live_detection_publication_matches_cache_mapping_on_synthetic_rows():
    pytest.importorskip("rclpy")
    from thesis_bringup.perception.perception_pipeline_node import PerceptionPipelineNode

    source = np.zeros((7, 11, 3), dtype=np.uint8)
    _, transform = MODULE.prepare_source_image(
        source, inference_width=640, inference_height=640
    )
    rows = [
        {"x": 0.15, "y": 0.20, "w": 0.25, "h": 0.30,
         "score": 0.35, "label": "person", "class_id": 0},
        {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1,
         "score": 0.34, "label": "person", "class_id": 0},
        {"x": 0.6, "y": 0.6, "w": 0.2, "h": 0.2,
         "score": 0.9, "label": "car", "class_id": 2},
    ]
    expected = MODULE.source_pixel_detections(
        rows, transform=transform, minimum_score=0.35
    )
    live = PerceptionPipelineNode._build_detection_array(
        SimpleNamespace(min_score=0.35, label="person", img_w=640, img_h=640),
        SimpleNamespace(transform=transform, frame_id=1,
                        t_cam_msg_seen_ns=1, stamp_sec=0, stamp_nanosec=1),
        {"detections": rows},
    )
    assert len(live.detections) == len(expected) == 1
    detection = live.detections[0]
    centre = detection.bbox.center.position
    width, height = detection.bbox.size_x, detection.bbox.size_y
    published_box = (
        centre.x - width / 2, centre.y - height / 2,
        centre.x + width / 2, centre.y + height / 2,
    )
    assert published_box == pytest.approx(expected[0]["bbox_xyxy"])
    assert detection.results[0].hypothesis.class_id == "person"
    assert detection.results[0].hypothesis.score == expected[0]["score"]


def test_cache_requires_freeze_and_exact_frame_coverage():
    kwargs = dict(
        protocol_sha256="a" * 64,
        split="train",
        sequence_name="synthetic",
        expected_source_frame_numbers=[1, 2, 3],
        frame_detections=[(1, []), (2, []), (3, [])],
    )
    with pytest.raises(ValueError, match="frozen protocol"):
        MODULE.build_sequence_cache(protocol_status="draft_not_frozen", **kwargs)
    document = MODULE.build_sequence_cache(protocol_status="frozen", **kwargs)
    assert document["source_frame_count"] == 3
    assert [frame["normalized_frame_index"] for frame in document["frames"]] == [0, 1, 2]
    with pytest.raises(ValueError, match="exact source frame domain"):
        MODULE.build_sequence_cache(
            protocol_status="frozen",
            **{**kwargs, "frame_detections": [(1, []), (3, [])]},
        )


def test_frozen_inputs_require_same_committed_checkpoint(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Benchmark Test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "benchmark@example.invalid"], check=True)
    protocol = tmp_path / "protocol.json"
    manifest = tmp_path / "manifest.json"
    protocol.write_text(json.dumps({"status": "frozen"}))
    manifest.write_text(json.dumps({"status": "frozen"}))
    subprocess.run(["git", "-C", str(tmp_path), "add", "protocol.json", "manifest.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "freeze"], check=True)
    kwargs = dict(repository_root=tmp_path, protocol_path=protocol, manifest_path=manifest)
    result = MODULE.read_committed_frozen_inputs(**kwargs)
    assert len(result["freeze_commit"]) == 40
    manifest.write_text(json.dumps({"status": "draft_not_frozen"}))
    with pytest.raises(ValueError, match="committed HEAD"):
        MODULE.read_committed_frozen_inputs(**kwargs)


def test_frozen_inputs_reject_separate_commits(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Benchmark Test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "benchmark@example.invalid"], check=True)
    protocol = tmp_path / "protocol.json"
    manifest = tmp_path / "manifest.json"
    protocol.write_text(json.dumps({"status": "frozen"}))
    subprocess.run(["git", "-C", str(tmp_path), "add", "protocol.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "protocol"], check=True)
    manifest.write_text(json.dumps({"status": "frozen"}))
    subprocess.run(["git", "-C", str(tmp_path), "add", "manifest.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "manifest"], check=True)
    with pytest.raises(ValueError, match="one commit"):
        MODULE.read_committed_frozen_inputs(
            repository_root=tmp_path,
            protocol_path=protocol,
            manifest_path=manifest,
        )


def test_one_sequence_writer_uses_each_image_once_and_rejects_timeout(tmp_path):
    writer_path = MODULE_PATH.with_name("write_shared_detector_cache.py")
    writer_spec = importlib.util.spec_from_file_location("p125_cache_writer", writer_path)
    assert writer_spec is not None and writer_spec.loader is not None
    writer = importlib.util.module_from_spec(writer_spec)
    sys.modules[writer_spec.name] = writer
    writer_spec.loader.exec_module(writer)
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    for frame in (1, 2):
        image = np.full((4, 6, 3), frame, dtype=np.uint8)
        assert cv2.imwrite(str(image_dir / f"{frame:07d}.jpg"), image)
    paths = writer.image_paths_by_source_frame(image_dir)

    class FakeEngine:
        def __init__(self):
            self.calls = []

        def infer(self, rgb, source_frame, frame_index, source_stamp_ns, timeout_ms):
            self.calls.append((source_frame, frame_index, rgb.shape, timeout_ms))
            return {"detections": []}

    engine = FakeEngine()
    result = writer.generate_sequence_cache(
        image_paths=paths,
        engine=engine,
        protocol_sha256="b" * 64,
        split="val",
        sequence_name="synthetic",
        inference_width=8,
        inference_height=8,
        minimum_score=0.35,
        infer_timeout_ms=300,
    )
    assert result["source_frame_count"] == 2
    assert engine.calls == [(1, 0, (8, 8, 3), 300), (2, 1, (8, 8, 3), 300)]
    output = tmp_path / "cache.json"
    digest = writer.write_cache_once(output, result)
    assert digest == writer.write_cache_once(output, result)
    with pytest.raises(ValueError, match="differs"):
        writer.write_cache_once(output, {**result, "source_frame_count": 3})

    class TimeoutEngine:
        def infer(self, *args):
            return None

    with pytest.raises(RuntimeError, match="timeout"):
        writer.generate_sequence_cache(
            image_paths=paths,
            engine=TimeoutEngine(),
            protocol_sha256="b" * 64,
            split="val",
            sequence_name="synthetic",
            inference_width=8,
            inference_height=8,
            minimum_score=0.35,
            infer_timeout_ms=300,
        )


def test_invalid_source_image_and_detector_values_are_rejected():
    with pytest.raises(ValueError, match="HWC uint8 BGR"):
        MODULE.prepare_source_image(np.zeros((4, 5), dtype=np.uint8))
    transform = MODULE.ImageTransform.direct_resize(10, 10, 10, 10)
    with pytest.raises(ValueError, match="finite"):
        MODULE.source_pixel_detections([
            {"x": 0, "y": 0, "w": 1, "h": 1,
             "score": float("nan"), "class_id": 0},
        ], transform=transform)
