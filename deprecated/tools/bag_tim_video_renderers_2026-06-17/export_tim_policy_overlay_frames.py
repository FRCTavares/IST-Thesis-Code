#!/usr/bin/env python3
"""
Export TIM policy overlay review frames directly from a ROS 2 bag.

This is like render_tim_policy_overlay_video.py, but writes JPG frames at a fixed
time step so they are easier to inspect in Finder/Preview.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np


BBox = Tuple[int, int, int, int]


def f(v, d=0.0) -> float:
    try:
        if v in ("", None):
            return d
        return float(v)
    except Exception:
        return d


def i(v, d=0) -> int:
    try:
        if v in ("", None):
            return d
        return int(float(v))
    except Exception:
        return d


def detect_storage_id(bag_path: Path) -> str:
    metadata_path = bag_path / "metadata.yaml"
    if metadata_path.exists():
        text = metadata_path.read_text(errors="ignore")
        if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
            return "mcap"
        if "storage_identifier: sqlite3" in text or "storage_id: sqlite3" in text:
            return "sqlite3"
    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"
    return "sqlite3"


def import_rosbag_tools():
    try:
        from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except Exception as exc:
        raise RuntimeError(
            "Could not import ROS 2 bag tools. Source ROS first:\n"
            "  source /opt/ros/jazzy/setup.bash\n"
            "  source \"$THESIS_ROOT/ros2_ws/install/setup.bash\""
        ) from exc

    return SequentialReader, StorageOptions, ConverterOptions, deserialize_message, get_message


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


def safe_get(obj: Any, names: list[str], default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def get_track_id(track: Any) -> int:
    return i(safe_get(track, ["id", "track_id", "target_id"], 0), 0)


def map_track_box_to_image(
    box: tuple[float, float, float, float],
    *,
    img_w: int,
    img_h: int,
    track_coord_w: float,
    track_coord_h: float,
    letterbox_to_image: bool,
) -> Optional[BBox]:
    x1, y1, x2, y2 = box

    if letterbox_to_image:
        scale = min(track_coord_w / float(img_w), track_coord_h / float(img_h))
        new_w = float(img_w) * scale
        new_h = float(img_h) * scale
        pad_x = 0.5 * (track_coord_w - new_w)
        pad_y = 0.5 * (track_coord_h - new_h)

        x1 = (x1 - pad_x) / scale
        x2 = (x2 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        y2 = (y2 - pad_y) / scale
    else:
        sx = float(img_w) / max(1e-6, float(track_coord_w))
        sy = float(img_h) / max(1e-6, float(track_coord_h))
        x1 *= sx
        x2 *= sx
        y1 *= sy
        y2 *= sy

    xi1 = int(max(0, min(img_w - 1, round(x1))))
    yi1 = int(max(0, min(img_h - 1, round(y1))))
    xi2 = int(max(0, min(img_w - 1, round(x2))))
    yi2 = int(max(0, min(img_h - 1, round(y2))))

    if xi2 <= xi1 or yi2 <= yi1:
        return None
    return xi1, yi1, xi2, yi2


def get_track_bbox(
    track: Any,
    img_w: int,
    img_h: int,
    track_coord_w: float,
    track_coord_h: float,
    letterbox_to_image: bool,
) -> Optional[BBox]:
    cx = safe_get(track, ["cx", "center_x", "bbox_cx"], None)
    cy = safe_get(track, ["cy", "center_y", "bbox_cy"], None)
    bw = safe_get(track, ["w", "width", "bbox_w"], None)
    bh = safe_get(track, ["h", "height", "bbox_h"], None)

    if cx is not None and cy is not None and bw is not None and bh is not None:
        cx = f(cx)
        cy = f(cy)
        bw = f(bw)
        bh = f(bh)

        if 0 <= cx <= 1.5 and 0 <= cy <= 1.5 and 0 <= bw <= 1.5 and 0 <= bh <= 1.5:
            cx *= track_coord_w
            bw *= track_coord_w
            cy *= track_coord_h
            bh *= track_coord_h

        raw_box = (
            cx - 0.5 * bw,
            cy - 0.5 * bh,
            cx + 0.5 * bw,
            cy + 0.5 * bh,
        )
        return map_track_box_to_image(
            raw_box,
            img_w=img_w,
            img_h=img_h,
            track_coord_w=track_coord_w,
            track_coord_h=track_coord_h,
            letterbox_to_image=letterbox_to_image,
        )

    if hasattr(track, "bbox"):
        return get_track_bbox(
            getattr(track, "bbox"),
            img_w,
            img_h,
            track_coord_w,
            track_coord_h,
            letterbox_to_image,
        )

    return None


def load_timeline(path: Path) -> list[dict]:
    rows = []
    with path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        for r in reader:
            rows.append({
                "t": f(r.get("t")),
                "raw_selected": i(r.get("raw_selected")),
                "selected_after_policy": i(r.get("selected_after_policy")),
                "label_raw": str(r.get("label_raw", "")),
                "label_policy": str(r.get("label_policy", "")),
                "selected_similarity": r.get("selected_similarity", ""),
                "reacquired": str(r.get("reacquired", "false")),
                "suppressed": str(r.get("suppressed", "false")),
            })
    rows.sort(key=lambda r: r["t"])
    return rows


def timeline_at(rows: list[dict], t: float, max_dt: float) -> Optional[dict]:
    if not rows:
        return None
    best = min(rows, key=lambda r: abs(r["t"] - t))
    if abs(best["t"] - t) > max_dt:
        return None
    return best


def draw_box(img, box: BBox, colour, label: str, thickness=2):
    x1, y1, x2, y2 = box
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, thickness)
    if label:
        y = max(16, y1 - 6)
        cv2.putText(img, label, (x1, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2, cv2.LINE_AA)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--timeline", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--image-topic", default="/camera/dashboard")
    p.add_argument("--tracks-topic", default="/tracks")
    p.add_argument("--every-s", type=float, default=0.5)
    p.add_argument("--start-s", type=float, default=0.0)
    p.add_argument("--end-s", type=float, default=0.0)
    p.add_argument("--max-timeline-dt", type=float, default=0.12)
    p.add_argument("--track-coord-w", type=float, default=640.0)
    p.add_argument("--track-coord-h", type=float, default=640.0)
    p.add_argument("--track-letterbox-to-image", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    timeline = load_timeline(args.timeline)

    SequentialReader, StorageOptions, ConverterOptions, deserialize_message, get_message = import_rosbag_tools()

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(args.bag), storage_id=detect_storage_id(args.bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {m.name: m.type for m in reader.get_all_topics_and_types()}
    missing = [t for t in [args.image_topic, args.tracks_topic] if t not in topic_types]
    if missing:
        raise SystemExit(f"Bag missing topics {missing}. Available: {sorted(topic_types)}")

    image_type = get_message(topic_types[args.image_topic])
    tracks_type = get_message(topic_types[args.tracks_topic])

    first_t_ns = None
    latest_tracks: dict[int, BBox] = {}
    latest_shape = (640, 640)
    next_save_t = args.start_s
    saved = 0

    while reader.has_next():
        topic, data, t_ns = reader.read_next()

        if first_t_ns is None:
            first_t_ns = int(t_ns)
        t_s = (int(t_ns) - first_t_ns) / 1e9

        if args.end_s > 0 and t_s > args.end_s:
            break

        if topic == args.tracks_topic:
            msg = deserialize_message(data, tracks_type)
            img_w, img_h = latest_shape

            latest_tracks = {}
            for tr in list(getattr(msg, "tracks", [])):
                tid = get_track_id(tr)
                box = get_track_bbox(
                    tr,
                    img_w,
                    img_h,
                    track_coord_w=args.track_coord_w,
                    track_coord_h=args.track_coord_h,
                    letterbox_to_image=args.track_letterbox_to_image,
                )
                if tid > 0 and box is not None:
                    latest_tracks[tid] = box

        elif topic == args.image_topic:
            if t_s + 1e-9 < args.start_s:
                continue
            if t_s + 1e-9 < next_save_t:
                continue

            msg = deserialize_message(data, image_type)
            img = image_msg_to_bgr(msg)
            img_h, img_w = img.shape[:2]
            latest_shape = (img_w, img_h)

            tl = timeline_at(timeline, t_s, args.max_timeline_dt)

            for tid, box in latest_tracks.items():
                draw_box(img, box, (160, 160, 160), f"ID {tid}", thickness=1)

            if tl is not None:
                raw_id = int(tl["raw_selected"])
                pol_id = int(tl["selected_after_policy"])

                if raw_id > 0 and raw_id in latest_tracks:
                    draw_box(img, latest_tracks[raw_id], (0, 165, 255), f"RAW {raw_id}", thickness=2)

                if pol_id > 0 and pol_id in latest_tracks:
                    draw_box(img, latest_tracks[pol_id], (0, 255, 0), f"V2E {pol_id}", thickness=3)

                status = (
                    f"t={t_s:.2f}s raw={raw_id}:{tl['label_raw']} "
                    f"v2e={pol_id}:{tl['label_policy']} "
                    f"sim={tl['selected_similarity']} "
                    f"sup={tl['suppressed']} reacq={tl['reacquired']}"
                )
            else:
                status = f"t={t_s:.2f}s no timeline match"

            cv2.rectangle(img, (0, 0), (img_w, 34), (0, 0, 0), -1)
            cv2.putText(img, status, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            out = args.output_dir / f"frame_{saved:05d}__bag_t_{t_s:08.3f}s.jpg"
            cv2.imwrite(str(out), img)
            saved += 1
            next_save_t += args.every_s

            if saved % 50 == 0:
                print(f"[info] saved={saved}")

    print(f"[ok] saved={saved}")
    print(f"[ok] output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
