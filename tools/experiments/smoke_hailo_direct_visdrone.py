#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_bringup"))
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_inference_client"))

from thesis_bringup.nodes.perception_pipeline_node import HailoDirectInferenceEngine


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--image",
        default=(
            "datasets/external/visdrone2019-mot/extracted/"
            "VisDrone2019-MOT-val/sequences/uav0000086_00000_v/0000001.jpg"
        ),
    )
    ap.add_argument("--hef", default="models/hef/yolov6n.hef")
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--score", type=float, default=0.25)
    args = ap.parse_args()

    image_path = Path(args.image)
    hef_path = Path(args.hef)

    if not image_path.exists():
        raise FileNotFoundError(image_path)
    if not hef_path.exists():
        raise FileNotFoundError(hef_path)

    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    resized = cv2.resize(bgr, (args.size, args.size), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)

    engine = HailoDirectInferenceEngine(
        hef_path=str(hef_path),
        infer_timeout_ms=1000,
        label_filter="person",
    )

    try:
        result = engine.infer(
            rgb,
            1,
            1,
            0,
            1000,
        )
    finally:
        engine.close()

    dets = result.get("detections", []) if result else []
    timing = result.get("timing", {}) if result else {}

    print(f"[ok] image: {image_path}")
    print(f"[ok] hef: {hef_path}")
    print(f"[ok] detections: {len(dets)}")
    print(f"[ok] timing keys: {sorted(timing.keys())}")

    for i, d in enumerate(dets[:20]):
        print(f"det[{i}]: {d}")

    person_like = [
        d for d in dets
        if float(d.get("score", d.get("confidence", 0.0))) >= args.score
    ]
    print(f"[ok] detections above score {args.score}: {len(person_like)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
