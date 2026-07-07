#!/usr/bin/env python3
"""Render a tracker-ID overlay video from a ROS 2 bag.

This support tool reads image and /tracks topics from a rosbag2 bag and writes
a video where every visible track is labeled by tracker ID. It is useful for
manual review before annotation or when checking tracker fragmentation.

It does not create annotation CSVs and does not compute correctness metrics.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def detect_storage_id(bag_path: Path) -> str:
    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"
    return "mcap"


def image_msg_to_bgr(msg: Any) -> np.ndarray:
    enc = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)

    if enc not in {"bgr8", "rgb8"}:
        raise RuntimeError(f"Unsupported image encoding: {msg.encoding}")

    expected = h * step
    img = np.frombuffer(msg.data, dtype=np.uint8)[:expected].reshape((h, step // 3, 3))[:, :w, :]
    if enc == "rgb8":
        img = img[:, :, ::-1]
    return np.ascontiguousarray(img.copy())


def stamp_s(msg: Any, fallback_ns: int) -> float:
    try:
        return float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9
    except Exception:
        return fallback_ns * 1e-9


def get_track_id(track: Any) -> int:
    for name in ("id", "track_id", "target_id"):
        if hasattr(track, name):
            return int(getattr(track, name))
    return 0


def get_track_box(track: Any):
    # Common thesis Track2D style: x, y, w, h as centre x/y plus width/height.
    if all(hasattr(track, n) for n in ("x", "y", "w", "h")):
        cx, cy, bw, bh = float(track.x), float(track.y), float(track.w), float(track.h)
        return cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0

    if all(hasattr(track, n) for n in ("cx", "cy", "w", "h")):
        cx, cy, bw, bh = float(track.cx), float(track.cy), float(track.w), float(track.h)
        return cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0

    if all(hasattr(track, n) for n in ("xmin", "ymin", "xmax", "ymax")):
        return float(track.xmin), float(track.ymin), float(track.xmax), float(track.ymax)

    return None


def map_box_to_image(box, img_w, img_h, coord_w, coord_h):
    x1, y1, x2, y2 = box
    sx = img_w / float(coord_w)
    sy = img_h / float(coord_h)

    x1 = int(round(x1 * sx))
    x2 = int(round(x2 * sx))
    y1 = int(round(y1 * sy))
    y2 = int(round(y2 * sy))

    x1 = max(0, min(img_w - 1, x1))
    x2 = max(0, min(img_w - 1, x2))
    y1 = max(0, min(img_h - 1, y1))
    y2 = max(0, min(img_h - 1, y2))

    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def nearest_before(samples, t, max_dt):
    best = None
    for ts, value in samples:
        if ts <= t:
            best = (ts, value)
        else:
            break
    if best is None:
        return None
    if abs(t - best[0]) > max_dt:
        return None
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--image-topic", default="/camera/image_raw")
    ap.add_argument("--tracks-topic", default="/tracks")
    ap.add_argument("--fps", type=float, default=14.35)
    ap.add_argument("--coord-w", type=float, default=640.0)
    ap.add_argument("--coord-h", type=float, default=640.0)
    ap.add_argument("--max-track-dt", type=float, default=0.25)
    ap.add_argument("--output-size", default="")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    bag = Path(args.bag)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag), storage_id=detect_storage_id(bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if args.image_topic not in topic_types:
        raise RuntimeError(f"Missing image topic {args.image_topic}. Available: {sorted(topic_types)}")
    if args.tracks_topic not in topic_types:
        raise RuntimeError(f"Missing tracks topic {args.tracks_topic}. Available: {sorted(topic_types)}")

    image_type = get_message(topic_types[args.image_topic])
    tracks_type = get_message(topic_types[args.tracks_topic])

    images = []
    tracks = []
    first_t = None

    while reader.has_next():
        topic, data, t_ns = reader.read_next()

        if topic == args.image_topic:
            msg = deserialize_message(data, image_type)
            t = stamp_s(msg, t_ns)
            if first_t is None:
                first_t = t
            images.append((t - first_t, image_msg_to_bgr(msg)))

        elif topic == args.tracks_topic:
            msg = deserialize_message(data, tracks_type)
            t = stamp_s(msg, t_ns)
            if first_t is None:
                first_t = t
            tracks.append((t - first_t, list(getattr(msg, "tracks", []))))

    if not images:
        raise RuntimeError("No images found.")
    if not tracks:
        raise RuntimeError("No tracks found.")

    h, w = images[0][1].shape[:2]
    if args.output_size:
        ow, oh = [int(x) for x in args.output_size.lower().split("x")]
    else:
        ow, oh = w, h

    writer = cv2.VideoWriter(
        str(out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (ow, oh),
    )

    count = 0
    for t, frame in images:
        img = frame.copy()
        if (w, h) != (ow, oh):
            img = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_LINEAR)

        scale_x = ow / float(w)
        scale_y = oh / float(h)

        tr_sample = nearest_before(tracks, t, args.max_track_dt)
        current_tracks = tr_sample[1] if tr_sample else []

        cv2.rectangle(img, (0, 0), (ow, 46), (0, 0, 0), -1)
        cv2.putText(
            img,
            f"Pure OCSORT /tracks | t={t:.2f}s | tracks={len(current_tracks)}",
            (14, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
        )

        for tr in current_tracks:
            tid = get_track_id(tr)
            box = get_track_box(tr)
            if box is None:
                continue

            mapped = map_box_to_image(box, w, h, args.coord_w, args.coord_h)
            if mapped is None:
                continue

            x1, y1, x2, y2 = mapped
            x1 = int(round(x1 * scale_x))
            x2 = int(round(x2 * scale_x))
            y1 = int(round(y1 * scale_y))
            y2 = int(round(y2 * scale_y))

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 3)
            label = f"ID {tid}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
            y_text = max(50, y1 - 8)
            cv2.rectangle(img, (x1, y_text - th - 8), (x1 + tw + 8, y_text + 4), (0, 0, 0), -1)
            cv2.putText(img, label, (x1 + 4, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2)

        writer.write(img)
        count += 1
        if args.max_frames and count >= args.max_frames:
            break

    writer.release()
    print(f"Wrote: {out}")
    print(f"Frames: {count}")


if __name__ == "__main__":
    main()
