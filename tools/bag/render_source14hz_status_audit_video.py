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


def extract_selected_id(msg: Any) -> int:
    # Handles common custom target messages and std_msgs-style messages.
    for name in [
        "target_id",
        "track_id",
        "selected_track_id",
        "id",
        "data",
        "selected_id",
        "memory_track_id",
    ]:
        if hasattr(msg, name):
            return as_int(getattr(msg, name), 0)

    # Fallback for nested target fields.
    for nested_name in ["target", "track", "selected_target"]:
        if hasattr(msg, nested_name):
            nested = getattr(msg, nested_name)
            for name in ["target_id", "track_id", "id", "data"]:
                if hasattr(nested, name):
                    return as_int(getattr(nested, name), 0)

    return 0


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


def annotation_at(rows, eval_t_s: float):
    for r in rows:
        if r["start_s"] <= eval_t_s < r["end_s"]:
            return r
    return {
        "target_visible": False,
        "correct_id": 0,
        "event_type": "no_annotation",
    }


def classify_status(ann_row: dict, selected_id: int):
    visible = bool(ann_row["target_visible"])
    correct_id = int(ann_row["correct_id"])
    event_type = str(ann_row.get("event_type", "")).strip().lower()

    # Evaluation has not started yet. The selected target has not been chosen by the operator.
    if "no_target_selected" in event_type or "pre" in event_type:
        return "NO SELECTION", (160, 160, 160)

    # Evaluation interval where the target is not visible.
    if not visible:
        return "NOT VISIBLE", (160, 160, 160)

    # Visible target but annotation does not define a reliable correct ID.
    if correct_id <= 0:
        return "UNCERTAIN", (160, 160, 160)

    # After selection, missing output is a lost target.
    if selected_id <= 0:
        return "LOST", (0, 220, 255)

    # After selection, output equal to annotation is correct.
    if selected_id == correct_id:
        return "CORRECT", (0, 210, 0)

    # After selection, any different valid output is wrong.
    return "WRONG", (0, 0, 255)


def read_eval_events(eval_bag: Path, tracks_topic: str, selected_topic: str):
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(eval_bag), storage_id=detect_storage_id(eval_bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}

    if tracks_topic not in topic_types:
        raise RuntimeError(f"missing {tracks_topic} in {eval_bag}")

    if selected_topic not in topic_types:
        raise RuntimeError(f"missing {selected_topic} in {eval_bag}")

    tracks_type = get_message(topic_types[tracks_topic])
    selected_type = get_message(topic_types[selected_topic])

    track_events = []
    selected_events = []

    first_ns = None

    while reader.has_next():
        topic, raw, stamp_ns = reader.read_next()
        if first_ns is None:
            first_ns = int(stamp_ns)

        t_s = (int(stamp_ns) - first_ns) / 1e9

        if topic == tracks_topic:
            msg = deserialize_message(raw, tracks_type)
            track_events.append((t_s, extract_tracks(msg)))

        elif topic == selected_topic:
            msg = deserialize_message(raw, selected_type)
            selected_events.append((t_s, extract_selected_id(msg)))

    return track_events, selected_events


def latest_at(events, idx, t_s):
    while idx + 1 < len(events) and events[idx + 1][0] <= t_s:
        idx += 1
    if not events:
        return idx, None
    return idx, events[idx][1]


def draw_panel(img, title, status, colour, source_t_s, eval_t_s, selected_id, correct_id, selected_box, correct_box):
    out = img.copy()

    # Header background.
    cv2.rectangle(out, (0, 0), (out.shape[1], 118), (0, 0, 0), -1)

    cv2.putText(out, title, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

    cv2.putText(out, status, (18, 78), cv2.FONT_HERSHEY_SIMPLEX, 1.15, colour, 3, cv2.LINE_AA)

    info = f"selected={selected_id} correct={correct_id} source_t={source_t_s:5.2f}s eval_t={eval_t_s:6.2f}s"
    cv2.putText(out, info, (18, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 230, 230), 1, cv2.LINE_AA)

    # Correct reference box, thin cyan.
    if correct_box is not None:
        x1, y1, x2, y2 = correct_box
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(out, f"REF {correct_id}", (x1, max(135, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 0), 2, cv2.LINE_AA)

    # Method selected box, thick status colour.
    if selected_box is not None:
        x1, y1, x2, y2 = selected_box
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 4)
        cv2.putText(out, f"OUT {selected_id}", (x1, min(out.shape[0] - 12, y2 + 22)), cv2.FONT_HERSHEY_SIMPLEX, 0.58, colour, 2, cv2.LINE_AA)

    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-bag", type=Path, required=True)
    p.add_argument("--eval-bag", type=Path, required=True)
    p.add_argument("--annotation", type=Path, required=True)
    p.add_argument("--selected-topic", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--image-topic", default="/camera/image_raw")
    p.add_argument("--tracks-topic", default="/tracks")
    p.add_argument("--fps", type=float, default=14.35)
    p.add_argument("--output-size", default="640x360")
    p.add_argument("--eval-time-scale", type=float, default=2.0)
    p.add_argument("--track-coord-w", type=float, default=640.0)
    p.add_argument("--track-coord-h", type=float, default=640.0)
    args = p.parse_args()

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    out_w, out_h = [int(x) for x in args.output_size.lower().split("x")]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    ann = load_annotation(args.annotation)
    track_events, selected_events = read_eval_events(args.eval_bag, args.tracks_topic, args.selected_topic)

    track_idx = 0
    selected_idx = 0
    latest_tracks = {}
    latest_selected = 0

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(args.source_bag), storage_id=detect_storage_id(args.source_bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if args.image_topic not in topic_types:
        raise RuntimeError(f"missing {args.image_topic} in source bag")

    image_type = get_message(topic_types[args.image_topic])

    writer = cv2.VideoWriter(
        str(args.output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (out_w, out_h),
    )
    if not writer.isOpened():
        raise RuntimeError(f"could not open writer: {args.output}")

    first_ns = None
    rendered = 0

    while reader.has_next():
        topic, raw, stamp_ns = reader.read_next()
        if first_ns is None:
            first_ns = int(stamp_ns)

        if topic != args.image_topic:
            continue

        source_t_s = (int(stamp_ns) - first_ns) / 1e9
        eval_t_s = source_t_s * args.eval_time_scale

        track_idx, tracks_val = latest_at(track_events, track_idx, eval_t_s)
        if tracks_val is not None:
            latest_tracks = tracks_val

        selected_idx, selected_val = latest_at(selected_events, selected_idx, eval_t_s)
        if selected_val is not None:
            latest_selected = int(selected_val)

        ann_row = annotation_at(ann, eval_t_s)
        correct_id = int(ann_row["correct_id"])
        target_visible = bool(ann_row["target_visible"])
        status, colour = classify_status(ann_row, latest_selected)

        img = image_msg_to_bgr(deserialize_message(raw, image_type))

        selected_box = None
        if target_visible and latest_selected > 0 and latest_selected in latest_tracks:
            selected_box = map_box_to_image(
                latest_tracks[latest_selected],
                img.shape[1],
                img.shape[0],
                args.track_coord_w,
                args.track_coord_h,
            )

        correct_box = None
        if correct_id > 0 and correct_id in latest_tracks:
            correct_box = map_box_to_image(
                latest_tracks[correct_id],
                img.shape[1],
                img.shape[0],
                args.track_coord_w,
                args.track_coord_h,
            )

        panel = draw_panel(
            img,
            args.title,
            status,
            colour,
            source_t_s,
            eval_t_s,
            latest_selected,
            correct_id,
            selected_box,
            correct_box,
        )
        panel = cv2.resize(panel, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        writer.write(panel)
        rendered += 1

        if rendered % 250 == 0:
            print(f"[info] rendered {rendered} source frames")

    writer.release()
    print(f"[ok] rendered_source_frames={rendered}")
    print(f"[ok] output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
