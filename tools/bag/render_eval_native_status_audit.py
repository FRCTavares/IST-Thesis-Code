#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def safe_get(obj: Any, names: list[str], default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def as_int(v, default=0):
    try:
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def as_float(v, default=0.0):
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def detect_storage_id(bag_path: Path) -> str:
    text = (bag_path / "metadata.yaml").read_text(errors="ignore")
    if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
        return "mcap"
    return "sqlite3"


def image_msg_to_bgr(msg: Any):
    enc = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)
    img = np.frombuffer(msg.data, dtype=np.uint8)[: h * step].reshape((h, step // 3, 3))[:, :w, :]
    if enc == "rgb8":
        img = img[:, :, ::-1]
    return np.ascontiguousarray(img.copy())


def get_bbox_xyxy(obj: Any):
    x1 = safe_get(obj, ["x1", "xmin", "left"])
    y1 = safe_get(obj, ["y1", "ymin", "top"])
    x2 = safe_get(obj, ["x2", "xmax", "right"])
    y2 = safe_get(obj, ["y2", "ymax", "bottom"])
    if None not in (x1, y1, x2, y2):
        return as_float(x1), as_float(y1), as_float(x2), as_float(y2)

    cx = safe_get(obj, ["cx", "center_x", "bbox_cx", "target_bbox_cx"])
    cy = safe_get(obj, ["cy", "center_y", "bbox_cy", "target_bbox_cy"])
    w = safe_get(obj, ["w", "width", "bbox_w", "target_bbox_w"])
    h = safe_get(obj, ["h", "height", "bbox_h", "target_bbox_h"])
    if None not in (cx, cy, w, h):
        cx = as_float(cx)
        cy = as_float(cy)
        w = as_float(w)
        h = as_float(h)
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2

    return None


def extract_tracks(msg):
    out = {}
    for tr in safe_get(msg, ["tracks"], []):
        tid = as_int(safe_get(tr, ["id", "track_id", "target_id"], 0))
        box = get_bbox_xyxy(tr)
        if tid > 0 and box is not None:
            out[tid] = box
    return out


def extract_selected_id(msg):
    for name in ["target_id", "track_id", "selected_track_id", "id", "data", "selected_id", "memory_track_id"]:
        if hasattr(msg, name):
            return as_int(getattr(msg, name), 0)
    return 0


def load_annotations(path):
    rows = []
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def annotation_at(rows, t):
    for r in rows:
        if float(r["start_s"]) <= t < float(r["end_s"]):
            return r
    return None


def classify(row, selected_id):
    if row is None:
        return "NO ANNOTATION", (160, 160, 160), 0

    event = row.get("event_type", "").lower()
    visible = row.get("target_visible", "").lower() == "true"
    correct_id = as_int(row.get("correct_target_track_id"), 0)

    if "no_target_selected" in event or "pre" in event:
        return "NO SELECTION", (160, 160, 160), correct_id
    if not visible:
        return "NOT VISIBLE", (160, 160, 160), correct_id
    if correct_id <= 0:
        return "UNCERTAIN", (160, 160, 160), correct_id
    if selected_id <= 0:
        return "LOST", (0, 220, 255), correct_id
    if selected_id == correct_id:
        return "CORRECT", (0, 210, 0), correct_id
    return "WRONG", (0, 0, 255), correct_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotation", type=Path, required=True)
    p.add_argument("--selected-topic", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--start-s", type=float, default=65.0)
    p.add_argument("--end-s", type=float, default=90.0)
    p.add_argument("--fps", type=float, default=5.0)
    args = p.parse_args()

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    rows = load_annotations(args.annotation)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(args.bag), storage_id=detect_storage_id(args.bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    image_type = get_message(types["/camera/image_raw"])
    tracks_type = get_message(types["/tracks"])
    selected_type = get_message(types[args.selected_topic])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (1280, 720))

    first_ns = None
    latest_tracks = {}
    latest_selected = 0
    written = 0

    while reader.has_next():
        topic, raw, stamp_ns = reader.read_next()
        if first_ns is None:
            first_ns = int(stamp_ns)
        t = (int(stamp_ns) - first_ns) / 1e9

        if topic == "/tracks":
            latest_tracks = extract_tracks(deserialize_message(raw, tracks_type))

        elif topic == args.selected_topic:
            latest_selected = extract_selected_id(deserialize_message(raw, selected_type))

        elif topic == "/camera/image_raw" and args.start_s <= t <= args.end_s:
            img = image_msg_to_bgr(deserialize_message(raw, image_type))
            img = cv2.resize(img, (1280, 720))

            row = annotation_at(rows, t)
            status, colour, correct_id = classify(row, latest_selected)

            cv2.rectangle(img, (0, 0), (1280, 125), (0, 0, 0), -1)
            cv2.putText(img, args.title, (24, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255,255,255), 2, cv2.LINE_AA)
            cv2.putText(img, status, (24, 82), cv2.FONT_HERSHEY_SIMPLEX, 1.25, colour, 3, cv2.LINE_AA)
            cv2.putText(img, f"t={t:.2f}s selected={latest_selected} correct={correct_id}", (24, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230,230,230), 2, cv2.LINE_AA)

            sx = 1280 / 640
            sy = 720 / 640

            for tid, box in latest_tracks.items():
                x1, y1, x2, y2 = box
                x1, y1, x2, y2 = int(x1*sx), int(y1*sy), int(x2*sx), int(y2*sy)

                c = (140, 140, 140)
                thickness = 2
                label = f"ID {tid}"

                if tid == correct_id:
                    c = (255, 255, 0)
                    thickness = 3
                    label = f"REF {tid}"

                if tid == latest_selected and latest_selected > 0:
                    c = colour
                    thickness = 5
                    label = f"OUT {tid}"

                cv2.rectangle(img, (x1,y1), (x2,y2), c, thickness)
                cv2.putText(img, label, (x1, max(145, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, c, 2, cv2.LINE_AA)

            writer.write(img)
            written += 1

    writer.release()
    print(f"[ok] wrote {written} frames")
    print(args.output)


if __name__ == "__main__":
    main()
