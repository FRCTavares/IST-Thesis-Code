#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def hsv_hist(crop: np.ndarray, h_bins: int = 16, s_bins: int = 8) -> np.ndarray | None:
    if crop is None or crop.size == 0:
        return None

    h, w = crop.shape[:2]
    if h < 10 or w < 5:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [h_bins, s_bins], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten().astype(np.float32)

    norm = float(np.linalg.norm(hist))
    if norm <= 1e-9:
        return None

    return hist / norm


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def clamp_box(x1, y1, x2, y2, w, h):
    x1 = int(max(0, min(w - 1, round(x1))))
    y1 = int(max(0, min(h - 1, round(y1))))
    x2 = int(max(0, min(w, round(x2))))
    y2 = int(max(0, min(h, round(y2))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def get_track_bbox(track: Any):
    """
    Flexible bbox extraction for thesis_msgs/Track2D variants.
    """
    # Common direct fields.
    direct_sets = [
        ("x1", "y1", "x2", "y2"),
        ("xmin", "ymin", "xmax", "ymax"),
        ("left", "top", "right", "bottom"),
    ]
    for names in direct_sets:
        if all(hasattr(track, n) for n in names):
            return tuple(float(getattr(track, n)) for n in names)

    # cx, cy, w, h.
    if all(hasattr(track, n) for n in ("cx", "cy", "w", "h")):
        cx = float(track.cx)
        cy = float(track.cy)
        bw = float(track.w)
        bh = float(track.h)
        return cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2

    # bbox object.
    if hasattr(track, "bbox"):
        b = track.bbox
        for names in direct_sets:
            if all(hasattr(b, n) for n in names):
                return tuple(float(getattr(b, n)) for n in names)
        if all(hasattr(b, n) for n in ("cx", "cy", "w", "h")):
            cx = float(b.cx)
            cy = float(b.cy)
            bw = float(b.w)
            bh = float(b.h)
            return cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2

    # geometry fields used by TargetState-like messages.
    if all(hasattr(track, n) for n in ("bbox_cx", "bbox_cy", "bbox_w", "bbox_h")):
        cx = float(track.bbox_cx)
        cy = float(track.bbox_cy)
        bw = float(track.bbox_w)
        bh = float(track.bbox_h)
        return cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2

    return None


def get_track_id(track: Any) -> int:
    for name in ("id", "track_id"):
        if hasattr(track, name):
            return int(getattr(track, name))
    return 0


def load_bag_messages(bag: Path):
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag), storage_id="mcap"),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if "/camera/dashboard" not in topic_types:
        raise SystemExit("Missing /camera/dashboard")
    if "/tracks" not in topic_types:
        raise SystemExit("Missing /tracks")

    image_type = get_message(topic_types["/camera/dashboard"])
    tracks_type = get_message(topic_types["/tracks"])

    bridge = CvBridge()

    images = []
    tracks_msgs = []

    t0 = None

    while reader.has_next():
        topic, data, stamp_ns = reader.read_next()
        if t0 is None:
            t0 = stamp_ns

        t = (stamp_ns - t0) / 1e9

        if topic == "/camera/dashboard":
            msg = deserialize_message(data, image_type)
            try:
                img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            except Exception:
                continue
            images.append((t, img))

        elif topic == "/tracks":
            msg = deserialize_message(data, tracks_type)
            tracks_msgs.append((t, msg))

    return images, tracks_msgs


def nearest_image(images, t, max_dt=0.08):
    if not images:
        return None, None

    # Simple linear search is okay for these bag sizes.
    best = None
    best_dt = 999.0

    for it, img in images:
        dt = abs(it - t)
        if dt < best_dt:
            best_dt = dt
            best = img

    if best is None or best_dt > max_dt:
        return None, None

    return best, best_dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--template-start-s", type=float, default=20.40)
    ap.add_argument("--template-end-s", type=float, default=35.71)
    ap.add_argument("--template-track-id", type=int, default=1)
    ap.add_argument("--max-image-dt", type=float, default=0.08)
    args = ap.parse_args()

    images, tracks_msgs = load_bag_messages(args.bag)
    print(f"[info] images={len(images)} tracks_msgs={len(tracks_msgs)}")

    template_hists = []
    rows = []

    for t, msg in tracks_msgs:
        img, img_dt = nearest_image(images, t, max_dt=args.max_image_dt)
        if img is None:
            continue

        ih, iw = img.shape[:2]

        tracks = getattr(msg, "tracks", [])
        for tr in tracks:
            tid = get_track_id(tr)
            bbox = get_track_bbox(tr)
            if tid <= 0 or bbox is None:
                continue

            box = clamp_box(*bbox, iw, ih)
            if box is None:
                continue

            x1, y1, x2, y2 = box
            crop = img[y1:y2, x1:x2]
            hist = hsv_hist(crop)
            if hist is None:
                continue

            if args.template_start_s <= t <= args.template_end_s and tid == args.template_track_id:
                template_hists.append(hist)

            rows.append(
                {
                    "t": t,
                    "track_id": tid,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "img_dt": img_dt,
                    "hist": hist,
                }
            )

    if not template_hists:
        raise SystemExit("No template histograms collected. Check bbox extraction, times, and track ID.")

    template = np.mean(np.stack(template_hists, axis=0), axis=0)
    template = template / (np.linalg.norm(template) + 1e-9)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", newline="") as f:
        fieldnames = [
            "t",
            "track_id",
            "x1",
            "y1",
            "x2",
            "y2",
            "img_dt",
            "frozen_hsv_similarity",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            sim = cosine(template, r["hist"])
            w.writerow(
                {
                    "t": f"{r['t']:.9f}",
                    "track_id": r["track_id"],
                    "x1": r["x1"],
                    "y1": r["y1"],
                    "x2": r["x2"],
                    "y2": r["y2"],
                    "img_dt": f"{r['img_dt']:.6f}",
                    "frozen_hsv_similarity": f"{sim:.6f}",
                }
            )

    print(f"[ok] template_hists={len(template_hists)}")
    print(f"[ok] rows={len(rows)}")
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
