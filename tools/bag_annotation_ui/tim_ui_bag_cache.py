#!/usr/bin/env python3
"""ROS bag loading and message parsing for the TIM-MARS annotation UI.

This module converts rosbag topics into the lightweight cache structure used by
the UI renderer. It intentionally does not import FastAPI and does not mutate
the backend's global CACHE object.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import rosbag2_py
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

from tim_ui_drawing import xywh_to_xyxy


def msg_time_ns(msg, bag_time_ns: int) -> int:
    """Prefer ROS header stamp for cross-topic synchronization.

    Rosbag storage time can differ between image, tracks, raw target, and TIM
    target. For visual overlays, header time is the correct matching clock when
    available.
    """
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None) if header is not None else None
    if stamp is None:
        return int(bag_time_ns)

    sec = int(getattr(stamp, "sec", 0))
    nanosec = int(getattr(stamp, "nanosec", 0))
    t = sec * 1_000_000_000 + nanosec
    return t if t > 0 else int(bag_time_ns)


def track_box(track):
    tid = int(getattr(track, "id", 0))

    if all(hasattr(track, a) for a in ("cx", "cy", "w", "h")):
        return tid, xywh_to_xyxy(float(track.cx), float(track.cy), float(track.w), float(track.h))

    if all(hasattr(track, a) for a in ("x", "y", "w", "h")):
        return tid, xywh_to_xyxy(float(track.x), float(track.y), float(track.w), float(track.h))

    return None


def target_box(msg):
    tid = int(getattr(msg, "id", 0))
    cx = float(getattr(msg, "cx", 0.0))
    cy = float(getattr(msg, "cy", 0.0))
    w = float(getattr(msg, "w", 0.0))
    h = float(getattr(msg, "h", 0.0))
    score = float(getattr(msg, "score", 0.0))
    quality = float(getattr(msg, "quality", 0.0))

    if tid <= 0 or w <= 0 or h <= 0:
        return None

    # Raw /target commonly has score > 0. TIM /target_memory_mars may carry
    # score=0 while quality is valid, so do not reject solely on score.
    if score <= 0 and quality <= 0:
        return None

    return {
        "id": tid,
        "box": xywh_to_xyxy(cx, cy, w, h),
        "score": score,
        "quality": quality,
    }


def detection_boxes(msg):
    out = []

    for det in getattr(msg, "detections", []):
        score = 0.0
        label = "det"

        results = getattr(det, "results", [])
        if results:
            hyp = getattr(results[0], "hypothesis", None)
            if hyp is not None:
                score = float(getattr(hyp, "score", 0.0))
                label = str(getattr(hyp, "class_id", "det"))

        bbox = getattr(det, "bbox", None)
        if bbox is None:
            continue

        center = getattr(bbox, "center", None)
        if center is None:
            continue

        pos = getattr(center, "position", center)
        cx = float(getattr(pos, "x", 0.0))
        cy = float(getattr(pos, "y", 0.0))
        w = float(getattr(bbox, "size_x", 0.0))
        h = float(getattr(bbox, "size_y", 0.0))

        if w <= 0 or h <= 0:
            continue

        out.append({
            "box": xywh_to_xyxy(cx, cy, w, h),
            "score": score,
            "label": label,
        })

    return out


def load_annotations(path: str | None):
    if not path:
        return []

    p = Path(path)
    if not p.exists():
        return []

    rows = []
    with p.open(newline="") as f:
        for r in csv.DictReader(f):
            label = r.get("target_label", "")
            if label not in {"CORRECT_TARGET", "black_shirt"}:
                continue

            visible = str(r.get("target_visible", "")).lower() == "true"
            tid_raw = r.get("correct_target_track_id", "")

            rows.append({
                "start_s": float(r["start_s"]),
                "end_s": float(r["end_s"]),
                "visible": visible,
                "correct_id": int(tid_raw) if tid_raw else None,
            })
    return rows


def ref_id_at(t_rel: float, annotations):
    for r in annotations:
        if r["start_s"] <= t_rel < r["end_s"]:
            return r["correct_id"] if r["visible"] else None
    return None


def nearest_by_time(rows, t, max_dt_ns: int | None = 250_000_000):
    """Return row closest to t, optionally rejecting large time mismatches."""
    if not rows:
        return None

    best_data = None
    best_dt = None

    for ts, data in rows:
        dt = abs(int(ts) - int(t))
        if best_dt is None or dt < best_dt:
            best_dt = dt
            best_data = data
        elif ts > t and best_dt is not None:
            # Rows are sorted; once we pass t and get worse, stop early.
            break

    if best_dt is not None and max_dt_ns is not None and best_dt > max_dt_ns:
        return None

    return best_data


def load_bag_cache(bag_path: str, ann_path: str | None) -> dict[str, Any]:
    bag = Path(bag_path)
    if not (bag / "metadata.yaml").exists():
        raise RuntimeError(f"Invalid bag path: {bag}")

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    msg_types = {topic: get_message(tp) for topic, tp in topic_types.items()}
    bridge = CvBridge()

    images = []
    detections_rows = []
    tracks_rows = []
    raw_rows = []
    tim_rows = []

    while reader.has_next():
        topic, data, t = reader.read_next()

        if topic in ("/camera/image_raw", "/camera/dashboard"):
            msg = deserialize_message(data, msg_types[topic])
            img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            images.append((msg_time_ns(msg, t), img))

        elif topic == "/detections":
            msg = deserialize_message(data, msg_types[topic])
            detections_rows.append((msg_time_ns(msg, t), detection_boxes(msg)))

        elif topic == "/tracks":
            msg = deserialize_message(data, msg_types[topic])
            tracks = []
            for tr in msg.tracks:
                tb = track_box(tr)
                if tb:
                    tracks.append(tb)
            tracks_rows.append((msg_time_ns(msg, t), tracks))

        elif topic == "/target":
            msg = deserialize_message(data, msg_types[topic])
            raw_rows.append((msg_time_ns(msg, t), target_box(msg)))

        elif topic == "/target_memory_mars":
            msg = deserialize_message(data, msg_types[topic])
            tim_rows.append((msg_time_ns(msg, t), target_box(msg)))

    if not images:
        raise RuntimeError("No /camera/image_raw or /camera/dashboard frames found in this bag.")

    images.sort(key=lambda r: r[0])
    detections_rows.sort(key=lambda r: r[0])
    tracks_rows.sort(key=lambda r: r[0])
    raw_rows.sort(key=lambda r: r[0])
    tim_rows.sort(key=lambda r: r[0])

    return {
        "bag": str(bag),
        "ann": ann_path or "",
        "images": images,
        "detections": detections_rows,
        "tracks": tracks_rows,
        "raw": raw_rows,
        "tim": tim_rows,
        "annotations": load_annotations(ann_path),
        "loaded_at": time.time(),
        "topic_counts": {
            "images": len(images),
            "detections": len(detections_rows),
            "tracks": len(tracks_rows),
            "raw": len(raw_rows),
            "tim": len(tim_rows),
        },
    }
