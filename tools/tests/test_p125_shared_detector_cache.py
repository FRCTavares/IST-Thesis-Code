"""Synthetic production-preprocessing and detector-cache contract checks."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

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


def test_invalid_source_image_and_detector_values_are_rejected():
    with pytest.raises(ValueError, match="HWC uint8 BGR"):
        MODULE.prepare_source_image(np.zeros((4, 5), dtype=np.uint8))
    transform = MODULE.ImageTransform.direct_resize(10, 10, 10, 10)
    with pytest.raises(ValueError, match="finite"):
        MODULE.source_pixel_detections([
            {"x": 0, "y": 0, "w": 1, "h": 1,
             "score": float("nan"), "class_id": 0},
        ], transform=transform)
