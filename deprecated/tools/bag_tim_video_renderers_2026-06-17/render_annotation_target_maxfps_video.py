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


def as_int(v, default=0) -> int:
    try:
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def as_float(v, default=0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def detect_storage_id(bag_path: Path) -> str:
    metadata = bag_path / "metadata.yaml"
    if metadata.exists():
        text = metadata.read_text(errors="ignore")
        if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
            return "mcap"
        if "storage_identifier: sqlite3" in text or "storage_id: sqlite3" in text:
            return "sqlite3"
    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"
    return "sqlite3"


def image_msg_to_bgr(msg: Any) -> np.ndarray:
    enc = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)

    if enc not in {"bgr8", "rgb8"}:
        raise RuntimeError(f"unsupported image encoding: {msg.encoding}")

    expected = h * step
    img = np.frombuffer(msg.data, dtype=np.uint8)[:expected].reshape((h, step // 3, 3))[:, :w, :]
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
        return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0

    return None


def extract_tracks(msg: Any) -> dict[int, tuple[float, float, float, float]]:
    out = {}
    for tr in safe_get(msg, ["tracks"], []):
        tid = as_int(safe_get(tr, ["id", "track_id", "target_id"], 0))
        box = get_bbox_xyxy(tr)
        if tid > 0 and box is not None:
            out[tid] = box
    return out


def map_box_to_image(box, img_w: int, img_h: int, coord_w: float, coord_h: float):
    x1, y1, x2, y2 = box

    scale = min(coord_w / float(img_w), coord_h / float(img_h))
    new_w = float(img_w) * scale
    new_h = float(img_h) * scale
    pad_x = 0.5 * (coord_w - new_w)
    pad_y = 0.5 * (coord_h - new_h)

    x1 = (x1 - pad_x) / scale
    x2 = (x2 - pad_x) / scale
    y1 = (y1 - pad_y) / scale
    y2 = (y2 - pad_y) / scale

    xi1 = max(0, min(img_w - 1, int(round(x1))))
    yi1 = max(0, min(img_h - 1, int(round(y1))))
    xi2 = max(0, min(img_w - 1, int(round(x2))))
    yi2 = max(0, min(img_h - 1, int(round(y2))))

    if xi2 <= xi1 or yi2 <= yi1:
        return None
    return xi1, yi1, xi2, yi2


def load_annotation(path: Path):
    rows = []
    with path.open("r", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "start_s": as_float(r.get("start_s")),
                "end_s": as_float(r.get("end_s")),
                "target_visible": str(r.get("target_visible", "")).strip().lower() in {"1", "true", "yes", "y"},
                "correct_id": as_int(r.get("correct_target_track_id"), 0),
                "event_type": str(r.get("event_type", "")),
            })
    return rows


def annotation_at(rows, t_s: float):
    for r in rows:
        if r["start_s"] <= t_s < r["end_s"]:
            if not r["target_visible"]:
                return 0, "not_visible"
            if r["correct_id"] <= 0:
                return 0, r["event_type"] or "uncertain"
            return r["correct_id"], r["event_type"] or "annotated"
    return 0, "no_annotation"


def draw_panel(img, title: str, reason: str, t_s: float, target_id: int, box):
    out = img.copy()

    cv2.putText(out, title, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(out, title, (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 1, cv2.LINE_AA)

    status = f"t={t_s:6.2f}s id={target_id} {reason}"
    cv2.putText(out, status, (20, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(out, status, (20, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 1, cv2.LINE_AA)

    if target_id > 0 and box is not None:
        x1, y1, x2, y2 = box
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 3)
        cv2.putText(out, f"TARGET {target_id}", (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2, cv2.LINE_AA)
    else:
        cv2.putText(out, "NO REFERENCE BOX", (20, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--image-topic", default="/camera/image_raw")
    p.add_argument("--tracks-topic", default="/tracks")
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--output-size", default="640x360")
    p.add_argument("--track-coord-w", type=float, default=640.0)
    p.add_argument("--track-coord-h", type=float, default=640.0)
    args = p.parse_args()

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    out_w, out_h = [int(x) for x in args.output_size.lower().split("x")]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    ann = load_annotation(args.annotation)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(args.bag), storage_id=detect_storage_id(args.bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    missing = [t for t in [args.image_topic, args.tracks_topic] if t not in topic_types]
    if missing:
        raise RuntimeError(f"missing topics: {missing}. Available: {sorted(topic_types)}")

    msg_types = {topic: get_message(type_name) for topic, type_name in topic_types.items()}

    writer = None
    latest_img = None
    latest_tracks = {}
    first_ns = None
    rendered = 0

    while reader.has_next():
        topic, raw, stamp_ns = reader.read_next()

        if first_ns is None:
            first_ns = int(stamp_ns)

        t_s = (int(stamp_ns) - first_ns) / 1e9

        msg = deserialize_message(raw, msg_types[topic])

        if topic == args.tracks_topic:
            latest_tracks = extract_tracks(msg)

        elif topic == args.image_topic:
            latest_img = image_msg_to_bgr(msg)

            if writer is None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(args.output), fourcc, args.fps, (out_w, out_h))
                if not writer.isOpened():
                    raise RuntimeError(f"could not open writer: {args.output}")

            target_id, reason = annotation_at(ann, t_s)
            box = None

            if target_id > 0 and target_id in latest_tracks:
                mapped = map_box_to_image(
                    latest_tracks[target_id],
                    latest_img.shape[1],
                    latest_img.shape[0],
                    args.track_coord_w,
                    args.track_coord_h,
                )
                box = mapped

            panel = draw_panel(latest_img, args.title, reason, t_s, target_id, box)
            panel = cv2.resize(panel, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
            writer.write(panel)

            rendered += 1

            if rendered % 250 == 0:
                print(f"[info] rendered {rendered} image frames")

    if writer is not None:
        writer.release()

    print(f"[ok] rendered_image_frames={rendered}")
    print(f"[ok] output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
