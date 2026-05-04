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


def letterbox_bgr_to_rgb_square(bgr: np.ndarray, size: int):
    h0, w0 = bgr.shape[:2]
    scale = min(size / w0, size / h0)
    new_w = int(round(w0 * scale))
    new_h = int(round(h0 * scale))

    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((size, size, 3), dtype=np.uint8)

    pad_x = (size - new_w) // 2
    pad_y = (size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(rgb), scale, pad_x, pad_y


def det_to_original_xyxy(det: dict, orig_w: int, orig_h: int, size: int, scale: float, pad_x: int, pad_y: int):
    x = float(det["x"]) * size
    y = float(det["y"]) * size
    w = float(det["w"]) * size
    h = float(det["h"]) * size

    x1 = (x - pad_x) / scale
    y1 = (y - pad_y) / scale
    x2 = (x + w - pad_x) / scale
    y2 = (y + h - pad_y) / scale

    x1 = max(0, min(orig_w - 1, int(round(x1))))
    y1 = max(0, min(orig_h - 1, int(round(y1))))
    x2 = max(0, min(orig_w - 1, int(round(x2))))
    y2 = max(0, min(orig_h - 1, int(round(y2))))

    return x1, y1, x2, y2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--image",
        default=(
            "data/datasets/external/visdrone2019-mot/extracted/"
            "VisDrone2019-MOT-val/sequences/uav0000086_00000_v/0000001.jpg"
        ),
    )
    ap.add_argument("--hef", default="models/hef/yolov6n.hef")
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--score", type=float, default=0.25)
    ap.add_argument("--out", default="artifacts/reports/dataset_checks/hailo_visdrone_yolov6n_preview.jpg")
    args = ap.parse_args()

    image_path = Path(args.image)
    hef_path = Path(args.hef)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    orig_h, orig_w = bgr.shape[:2]
    rgb, scale, pad_x, pad_y = letterbox_bgr_to_rgb_square(bgr, args.size)

    engine = HailoDirectInferenceEngine(
        hef_path=str(hef_path),
        infer_timeout_ms=1000,
        label_filter="person",
    )

    try:
        result = engine.infer(rgb, 1, 1, 0, 1000)
    finally:
        engine.close()

    dets = result.get("detections", []) if result else []
    kept = [d for d in dets if float(d.get("score", 0.0)) >= args.score]

    vis = bgr.copy()

    for d in kept:
        x1, y1, x2, y2 = det_to_original_xyxy(
            d, orig_w=orig_w, orig_h=orig_h,
            size=args.size, scale=scale, pad_x=pad_x, pad_y=pad_y,
        )

        score = float(d.get("score", 0.0))
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(
            vis,
            f"{score:.2f}",
            (x1, max(15, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(out_path), vis)

    print(f"[ok] image: {image_path}")
    print(f"[ok] original size: {orig_w}x{orig_h}")
    print(f"[ok] letterbox scale={scale:.6f} pad_x={pad_x} pad_y={pad_y}")
    print(f"[ok] raw detections: {len(dets)}")
    print(f"[ok] kept detections score>={args.score}: {len(kept)}")
    print(f"[ok] wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
