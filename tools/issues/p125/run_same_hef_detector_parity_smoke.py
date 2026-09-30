#!/usr/bin/env python3
"""Compare fixed VisDrone frames through cache and live-node detector paths."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/issues/p125"))
sys.path.insert(0, str(ROOT / "ros2_ws/src/thesis_bringup"))

from shared_detector_cache import (  # noqa: E402
    prepare_source_image,
    read_committed_frozen_inputs,
    source_pixel_detections,
)
from write_shared_detector_cache import write_cache_once  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def published_records(message) -> list[dict[str, object]]:
    records = []
    for detection in message.detections:
        centre = detection.bbox.center.position
        width, height = detection.bbox.size_x, detection.bbox.size_y
        if len(detection.results) != 1:
            raise ValueError("live node published detection without one hypothesis")
        hypothesis = detection.results[0].hypothesis
        records.append({
            "bbox_xyxy": [
                centre.x - width / 2, centre.y - height / 2,
                centre.x + width / 2, centre.y + height / 2,
            ],
            "score": float(hypothesis.score),
            "label": str(hypothesis.class_id),
        })
    return records


def compare_records(cache, live, *, box_tolerance=1e-5, score_tolerance=1e-6):
    if len(cache) != len(live):
        raise ValueError(f"detector count differs: cache={len(cache)} live={len(live)}")
    for index, (left, right) in enumerate(zip(cache, live, strict=True)):
        if right["label"].lower() != "person":
            raise ValueError(f"live non-person result {index}")
        if not np.allclose(left["bbox_xyxy"], right["bbox_xyxy"], rtol=0, atol=box_tolerance):
            raise ValueError(f"source box differs at detection {index}")
        if abs(float(left["score"]) - float(right["score"])) > score_tolerance:
            raise ValueError(f"detector score differs at detection {index}")


def main() -> int:
    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json",
        manifest_path=ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json",
    )
    protocol = frozen["protocol"]
    detector = protocol["shared_detector_draft"]
    split = "val"
    sequence = "uav0000086_00000_v"
    source_frames = (1, 2, 3)
    inventory = [entry for entry in frozen["manifest"]["sequence_inventory"]
                 if entry["split"] == split and entry["sequence_name"] == sequence]
    if len(inventory) != 1 or inventory[0]["first_source_frame"] > 1:
        raise ValueError("fixed smoke sequence absent from frozen manifest")
    model_relative = "models/hef/yolov8s.hef"
    model_path = ROOT / model_relative
    model_sha = sha256_file(model_path)
    if model_sha != protocol["pre_result_implementation_hashes_draft"][model_relative]:
        raise ValueError("detector HEF differs from frozen hash")
    if detector["input_width"] != 640 or detector["input_height"] != 640:
        raise ValueError("unexpected frozen detector dimensions")
    log_dir = ROOT / "ros2_ws/log/hailort"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HAILORT_LOGGER_PATH"] = str(log_dir)

    from sensor_msgs.msg import Image
    from thesis_bringup.perception.inference_engines import HailoDirectInferenceEngine
    from thesis_bringup.perception.perception_pipeline_node import PerceptionPipelineNode
    from thesis_bringup.perception.pipeline_types import RawFrame

    class QuietLogger:
        def info(self, *_args):
            return None

    node = SimpleNamespace(
        img_w=640, img_h=640, label="person",
        min_score=float(detector["minimum_score"]),
        _preprocess_log_lock=threading.Lock(),
        _logged_encoding=None, _logged_own_data=False,
        get_logger=lambda: QuietLogger(),
    )
    engine = HailoDirectInferenceEngine(
        hef_path=str(model_path),
        infer_timeout_ms=int(detector["infer_timeout_ms"]),
        label_filter="person",
    )
    frame_reports = []
    try:
        for source_number in source_frames:
            image_path = (ROOT / "data/datasets/external/visdrone_mot" / split /
                          "sequences" / sequence / f"{source_number:07d}.jpg")
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"unreadable fixed smoke image: {image_path}")
            source_h, source_w = image.shape[:2]
            if (source_w, source_h) != (inventory[0]["image_width"], inventory[0]["image_height"]):
                raise ValueError("fixed smoke image dimensions differ from frozen inventory")
            cache_rgb, cache_transform = prepare_source_image(image)
            message = Image()
            message.height = source_h
            message.width = source_w
            message.encoding = "bgr8"
            message.step = source_w * 3
            message.data = image.tobytes()
            stamp_ns = source_number * int(detector["logical_frame_tick_ns"])
            message.header.stamp.sec = stamp_ns // 1_000_000_000
            message.header.stamp.nanosec = stamp_ns % 1_000_000_000
            raw = RawFrame(
                seq=source_number, frame_id=source_number,
                src_stamp_ns=stamp_ns,
                stamp_sec=message.header.stamp.sec,
                stamp_nanosec=message.header.stamp.nanosec,
                t_cam_msg_seen_ns=1,
                image_msg=message,
            )
            prepared = PerceptionPipelineNode._prepare_frame(
                node, raw,
                resize_buf=np.empty((640, 640, 3), dtype=np.uint8),
                rgb_buf=np.empty((640, 640, 3), dtype=np.uint8),
            )
            if prepared is None or not np.array_equal(cache_rgb, prepared.infer_img):
                raise ValueError("cache and live-node preprocessing differ")
            if cache_transform != prepared.transform:
                raise ValueError("cache and live-node coordinate transforms differ")
            cache_result = engine.infer(cache_rgb, source_number, source_number, stamp_ns,
                                        int(detector["infer_timeout_ms"]))
            node_result = engine.infer(prepared.infer_img, source_number, source_number, stamp_ns,
                                       int(detector["infer_timeout_ms"]))
            if cache_result is None or node_result is None:
                raise RuntimeError("fixed smoke detector inference timed out")
            cache_detections = source_pixel_detections(
                cache_result["detections"], transform=cache_transform,
                minimum_score=float(detector["minimum_score"]),
            )
            live_message = PerceptionPipelineNode._build_detection_array(
                node, prepared, node_result,
            )
            live_detections = published_records(live_message)
            compare_records(cache_detections, live_detections)
            frame_reports.append({
                "source_frame_number": source_number,
                "source_image_sha256": sha256_file(image_path),
                "detection_count": len(cache_detections),
                "cache_detections": cache_detections,
                "live_detections": live_detections,
            })
    finally:
        engine.close()
    if not any(frame["detection_count"] for frame in frame_reports):
        raise ValueError("fixed smoke has no person detections to compare")
    document = {
        "schema": "p125_same_hef_detector_parity_smoke_v1",
        "freeze_commit": frozen["freeze_commit"],
        "protocol_sha256": frozen["protocol_sha256"],
        "manifest_sha256": frozen["manifest_sha256"],
        "detector_hef_sha256": model_sha,
        "split": split, "sequence_name": sequence,
        "box_absolute_tolerance_px": 1e-5,
        "score_absolute_tolerance": 1e-6,
        "frames": frame_reports,
        "status": "passed",
    }
    out = ROOT / "artifacts/reports/p125_detector_parity_smoke/val/uav0000086_00000_v_frames_1_2_3.json"
    digest = write_cache_once(out, document)
    print(json.dumps({"output": str(out), "sha256": digest,
                      "frame_detection_counts": [f["detection_count"] for f in frame_reports]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
