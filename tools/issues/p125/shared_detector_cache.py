#!/usr/bin/env python3
"""Production-parity frame conversion and cache contract for Issue #125.

This module has no Hailo engine or architecture runner. It accepts detector
results only after a separately committed protocol freeze.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "thesis_bringup"))

from thesis_bringup.perception.pipeline_utils import clamp01  # noqa: E402
from thesis_bringup.perception.preprocessing import (  # noqa: E402
    ImageTransform,
    preprocess_image_message,
)


def read_committed_frozen_inputs(
    *,
    repository_root: Path,
    protocol_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    """Require both frozen files to match one committed freeze checkpoint."""
    root = repository_root.resolve()
    documents: dict[str, object] = {}
    freeze_commits: set[str] = set()
    for name, supplied_path in (
        ("protocol", protocol_path),
        ("manifest", manifest_path),
    ):
        path = supplied_path.resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{name} is outside the repository") from exc
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=root,
        )
        current = path.read_bytes()
        if current != committed:
            raise ValueError(f"{name} does not match committed HEAD")
        document = json.loads(current)
        if document.get("status") != "frozen":
            raise ValueError(f"{name} is not frozen")
        freeze_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", relative.as_posix()],
            cwd=root,
            text=True,
        ).strip()
        if len(freeze_commit) != 40:
            raise ValueError(f"{name} has no freeze commit")
        freeze_commits.add(freeze_commit)
        documents[name] = document
        documents[f"{name}_sha256"] = hashlib.sha256(current).hexdigest()
    if len(freeze_commits) != 1:
        raise ValueError("protocol and manifest were not frozen in one commit")
    documents["freeze_commit"] = freeze_commits.pop()
    return documents


def prepare_source_image(
    image_bgr: np.ndarray,
    *,
    inference_width: int = 640,
    inference_height: int = 640,
) -> tuple[np.ndarray, ImageTransform]:
    """Use the production direct-resize and BGR-to-RGB preprocessing path."""
    if image_bgr.dtype != np.uint8 or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("source image must be HWC uint8 BGR")
    source = np.ascontiguousarray(image_bgr)
    source_height, source_width = source.shape[:2]
    msg = SimpleNamespace(
        height=source_height,
        width=source_width,
        encoding="bgr8",
        step=source_width * 3,
        data=source.tobytes(),
    )
    resize = np.empty((inference_height, inference_width, 3), dtype=np.uint8)
    rgb = np.empty_like(resize)
    prepared, level, reason = preprocess_image_message(
        msg,
        inference_width,
        inference_height,
        resize,
        rgb,
        lambda: 1,
        "p125_shared_detector_cache",
        pre_start_ns=1,
    )
    if prepared is None:
        raise ValueError(f"production preprocessing failed ({level}): {reason}")
    return np.ascontiguousarray(prepared.infer_img).copy(), prepared.transform


def source_pixel_detections(
    raw_detections: Sequence[dict[str, Any]],
    *,
    transform: ImageTransform,
    minimum_score: float = 0.35,
) -> list[dict[str, object]]:
    """Apply the production person/score/box mapping to decoded Hailo rows."""
    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("minimum score must be in [0, 1]")
    accepted: list[dict[str, object]] = []
    for detection in raw_detections:
        score = float(detection.get("score", 0.0))
        if not math.isfinite(score):
            raise ValueError("detector score must be finite")
        if score < minimum_score:
            continue
        label = str(detection.get("label", "")).strip()
        if label:
            if label.lower() != "person":
                continue
        elif int(detection.get("class_id", -1)) != 0:
            continue
        if not all(key in detection for key in ("x", "y", "w", "h")):
            raise ValueError("decoded Hailo detection lacks normalized xywh")
        values = [
            float(detection[key]) for key in ("x", "y", "w", "h")
        ]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("detector box coordinates must be finite")
        x, y, width, height = (clamp01(value) for value in values)
        inference_box = (
            x * transform.inference_width,
            y * transform.inference_height,
            (x + width) * transform.inference_width,
            (y + height) * transform.inference_height,
        )
        source_box = transform.inference_xyxy_to_source(inference_box)
        if source_box[2] <= source_box[0] or source_box[3] <= source_box[1]:
            continue
        accepted.append({
            "bbox_xyxy": list(source_box),
            "score": score,
            "class_id": 0,
        })
    return accepted


def build_sequence_cache(
    *,
    protocol_status: str,
    protocol_sha256: str,
    split: str,
    sequence_name: str,
    expected_source_frame_numbers: Sequence[int],
    frame_detections: Sequence[tuple[int, Sequence[dict[str, object]]]],
) -> dict[str, object]:
    """Reconcile every image frame; never synthesize a missing detector result."""
    if protocol_status != "frozen":
        raise ValueError("detector cache requires a committed frozen protocol")
    if len(protocol_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in protocol_sha256
    ):
        raise ValueError("protocol SHA-256 must be lowercase hexadecimal")
    if split not in ("train", "val") or not sequence_name:
        raise ValueError("invalid VisDrone split or sequence")
    expected = list(expected_source_frame_numbers)
    if not expected or expected != sorted(set(expected)) or expected[0] <= 0:
        raise ValueError("source frame numbers must be positive, sorted and unique")
    records = list(frame_detections)
    actual = [frame for frame, _ in records]
    if actual != expected:
        raise ValueError("detector results do not cover the exact source frame domain")
    return {
        "schema": "p125_shared_detector_sequence_cache_v1",
        "protocol_sha256": protocol_sha256,
        "split": split,
        "sequence_name": sequence_name,
        "source_frame_count": len(expected),
        "frames": [
            {
                "source_frame_number": frame,
                "normalized_frame_index": frame - 1,
                "detections": list(detections),
            }
            for frame, detections in records
        ],
    }
