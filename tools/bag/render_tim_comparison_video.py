#!/usr/bin/env python3
"""Render one paired raw-target versus TIM-MARS comparison video.

This module renders single-stream and paired raw-vs-TIM videos from rosbag2
data, annotations, and selected-target outputs. It is used for visual
inspection and paper/thesis validation videos.

It is separate from the interactive FastAPI annotation UI.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np


GREEN = (0, 210, 0)
RED = (0, 0, 255)
YELLOW = (0, 220, 255)
GREY = (160, 160, 160)
WHITE = (255, 255, 255)
HEADER_HEIGHT = 112


@dataclass
class Ann:
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_id: int
    event_type: str


def die(msg: str) -> None:
    raise SystemExit(f"[error] {msg}")


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


def as_bool(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def storage_id(bag: Path) -> str:
    meta = bag / "metadata.yaml"
    if meta.exists():
        txt = meta.read_text(errors="ignore")
        if "storage_identifier: mcap" in txt or "storage_id: mcap" in txt:
            return "mcap"
        if "storage_identifier: sqlite3" in txt or "storage_id: sqlite3" in txt:
            return "sqlite3"
    if list(bag.glob("*.mcap")):
        return "mcap"
    if list(bag.glob("*.db3")):
        return "sqlite3"
    return "sqlite3"


def open_reader(bag: Path):
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions

    r = SequentialReader()
    r.open(
        StorageOptions(uri=str(bag), storage_id=storage_id(bag)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )
    return r


def topic_types(bag: Path) -> dict[str, str]:
    r = open_reader(bag)
    return {t.name: t.type for t in r.get_all_topics_and_types()}


def header_ns(msg: Any) -> Optional[int]:
    h = getattr(msg, "header", None)
    if h is None:
        return None
    stamp = getattr(h, "stamp", None)
    if stamp is None:
        return None
    try:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    except Exception:
        return None


def load_annotations(path: Path) -> list[Ann]:
    out: list[Ann] = []
    with path.open("r", newline="") as f:
        for r in csv.DictReader(f):
            out.append(
                Ann(
                    start_s=float(r["start_s"]),
                    end_s=float(r["end_s"]),
                    target_label=str(r["target_label"]).strip(),
                    target_visible=as_bool(r["target_visible"]),
                    correct_id=as_int(r["correct_target_track_id"]),
                    event_type=str(r["event_type"]).strip(),
                )
            )
    out.sort(key=lambda x: x.start_s)
    return out


def ann_at(rows: list[Ann], t_s: float) -> Optional[Ann]:
    for r in rows:
        if r.start_s <= t_s < r.end_s:
            return r
    return None


def visible_duration(rows: list[Ann]) -> float:
    total = 0.0
    for r in rows:
        label = r.target_label.upper()
        if r.target_visible and label not in {"NO_TARGET_SELECTED", "TARGET_NOT_VISIBLE"}:
            total += max(0.0, r.end_s - r.start_s)
    return total


def classify(ann: Optional[Ann], selected_id: int):
    if ann is None:
        return "NO ANNOTATION", GREY, 0, "grey"

    label = ann.target_label.upper()
    event = ann.event_type.lower()

    if label == "NO_TARGET_SELECTED" or "no_target_selected" in event or "pre" in event:
        return "NO SELECTION", GREY, ann.correct_id, "grey"

    if (not ann.target_visible) or label == "TARGET_NOT_VISIBLE":
        return "ANNOTATION: TARGET ABSENT", GREY, 0, "grey"

    if ann.correct_id <= 0:
        return "UNCERTAIN", GREY, ann.correct_id, "grey"

    if selected_id <= 0:
        return "LOST", YELLOW, ann.correct_id, "lost"

    if selected_id == ann.correct_id:
        return "CORRECT", GREEN, ann.correct_id, "correct"

    return "WRONG", RED, ann.correct_id, "wrong"


def image_to_bgr(msg: Any) -> np.ndarray:
    enc = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)
    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)

    if enc in {"bgr8", "rgb8"}:
        row_bytes = w * 3
        img = data.reshape((h, step))[:, :row_bytes].reshape((h, w, 3))
        if enc == "rgb8":
            img = img[:, :, ::-1]
        return np.ascontiguousarray(img.copy())

    if enc in {"bgra8", "rgba8"}:
        row_bytes = w * 4
        img = data.reshape((h, step))[:, :row_bytes].reshape((h, w, 4))
        if enc == "rgba8":
            return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    if enc in {"mono8", "8uc1"}:
        img = data.reshape((h, step))[:, :w].reshape((h, w))
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    raise RuntimeError(f"unsupported image encoding: {msg.encoding}")


def first_image_dimensions(bag: Path, topic_name: str, message_type: str):
    """Return the recorded camera dimensions without assuming an aspect ratio."""
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    msg_type = get_message(message_type)
    reader = open_reader(bag)
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic != topic_name:
            continue
        image = image_to_bgr(deserialize_message(raw, msg_type))
        height, width = image.shape[:2]
        return width, height
    die(f"no images on {topic_name} in {bag}")


def bbox_xyxy(obj: Any):
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
        cx, cy, w, h = as_float(cx), as_float(cy), as_float(w), as_float(h)
        return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0

    return None


def extract_tracks(msg: Any) -> dict[int, tuple[float, float, float, float]]:
    out = {}
    for tr in safe_get(msg, ["tracks"], []):
        tid = as_int(safe_get(tr, ["id", "track_id", "target_id"], 0))
        box = bbox_xyxy(tr)
        if tid > 0 and box is not None:
            out[tid] = box
    return out


def selected_id(msg: Any) -> int:
    for name in [
        "target_track_id",
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

    for nested_name in ["target", "track", "selected_target"]:
        nested = getattr(msg, nested_name, None)
        if nested is None:
            continue
        for name in ["target_track_id", "target_id", "track_id", "id", "data"]:
            if hasattr(nested, name):
                return as_int(getattr(nested, name), 0)

    return 0


def track_boxes_are_source_pixels(msg: Any) -> bool:
    frame_id = str(safe_get(safe_get(msg, ["header"], None), ["frame_id"], ""))
    return frame_id.startswith("tim_mars_source_pixels_resize_v1;")


def map_box(
    box,
    img_w: int,
    img_h: int,
    source_pixels: bool,
    coord_w: float = 640.0,
    coord_h: float = 640.0,
):
    """Map a track box according to the contract recorded in its header."""
    x1, y1, x2, y2 = box

    if not source_pixels:
        x_scale = float(img_w) / coord_w
        y_scale = float(img_h) / coord_h
        x1 *= x_scale
        x2 *= x_scale
        y1 *= y_scale
        y2 *= y_scale

    xi1 = max(0, min(img_w - 1, int(round(x1))))
    yi1 = max(0, min(img_h - 1, int(round(y1))))
    xi2 = max(0, min(img_w - 1, int(round(x2))))
    yi2 = max(0, min(img_h - 1, int(round(y2))))

    if xi2 <= xi1 or yi2 <= yi1:
        return None
    return xi1, yi1, xi2, yi2


def choose_image_topic(types: dict[str, str], requested: str) -> str:
    if requested != "auto":
        if requested not in types:
            die(f"missing image topic {requested}. Available: {sorted(types)}")
        return requested

    for t in ["/camera/image_raw", "/camera/dashboard"]:
        if t in types:
            return t

    die(f"no camera image topic found. Available: {sorted(types)}")


def first_header_for_topic(bag: Path, topic_name: str) -> int:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    types = topic_types(bag)
    if topic_name not in types:
        die(f"missing {topic_name} in {bag}")

    msg_type = get_message(types[topic_name])
    reader = open_reader(bag)

    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic != topic_name:
            continue
        msg = deserialize_message(raw, msg_type)
        t = header_ns(msg)
        if t is not None:
            return t

    die(f"no header-stamped samples on {topic_name} in {bag}")


def read_events(bag: Path, t0_ns: int, tracks_topic: str, output_topic: str):
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    types = topic_types(bag)
    for t in [tracks_topic, output_topic]:
        if t not in types:
            die(f"missing {t} in {bag}")

    tracks_type = get_message(types[tracks_topic])
    output_type = get_message(types[output_topic])

    track_events = []
    output_events = []

    reader = open_reader(bag)

    while reader.has_next():
        topic, raw, _ = reader.read_next()

        if topic == tracks_topic:
            msg = deserialize_message(raw, tracks_type)
            t = header_ns(msg)
            if t is not None:
                track_events.append(
                    (
                        (t - t0_ns) * 1e-9,
                        (extract_tracks(msg), track_boxes_are_source_pixels(msg)),
                    )
                )

        elif topic == output_topic:
            msg = deserialize_message(raw, output_type)
            t = header_ns(msg)
            if t is not None:
                output_events.append(((t - t0_ns) * 1e-9, selected_id(msg)))

    return track_events, output_events


def latest_sample_at(events, idx: int, t_s: float):
    if not events:
        return idx, None, None
    while idx + 1 < len(events) and events[idx + 1][0] <= t_s:
        idx += 1
    if events[idx][0] > t_s:
        return idx, None, None
    return idx, events[idx][0], events[idx][1]


def draw_text_box(img, text: str, x: int, y: int, colour):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.52
    thickness = 1
    tw, th = cv2.getTextSize(text, font, scale, thickness)[0]
    y0 = max(0, y - th - 7)
    x0 = max(0, x)
    cv2.rectangle(img, (x0, y0), (min(img.shape[1] - 1, x0 + tw + 8), y0 + th + 10), colour, -1)
    cv2.putText(img, text, (x0 + 4, y0 + th + 2), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)


def draw_dashed_line(
    img,
    start: tuple[int, int],
    end: tuple[int, int],
    colour=WHITE,
    thickness: int = 2,
    dash_px: int = 12,
    gap_px: int = 7,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = max(abs(x2 - x1), abs(y2 - y1))
    if length <= 0:
        return
    step = dash_px + gap_px
    for offset in range(0, length + 1, step):
        finish = min(length, offset + dash_px)
        sx = int(round(x1 + (x2 - x1) * offset / length))
        sy = int(round(y1 + (y2 - y1) * offset / length))
        ex = int(round(x1 + (x2 - x1) * finish / length))
        ey = int(round(y1 + (y2 - y1) * finish / length))
        cv2.line(img, (sx, sy), (ex, ey), colour, thickness, cv2.LINE_AA)


def draw_dashed_rectangle(img, box, colour=WHITE, thickness: int = 2) -> None:
    x1, y1, x2, y2 = box
    draw_dashed_line(img, (x1, y1), (x2, y1), colour, thickness)
    draw_dashed_line(img, (x2, y1), (x2, y2), colour, thickness)
    draw_dashed_line(img, (x2, y2), (x1, y2), colour, thickness)
    draw_dashed_line(img, (x1, y2), (x1, y1), colour, thickness)


def put_text_fit(
    img,
    text: str,
    origin: tuple[int, int],
    max_width: int,
    scale: float,
    colour,
    thickness: int,
    minimum_scale: float = 0.38,
) -> float:
    """Draw one line without allowing it to spill outside its panel."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    fitted = scale
    while fitted > minimum_scale:
        width = cv2.getTextSize(text, font, fitted, thickness)[0][0]
        if width <= max_width:
            break
        fitted = max(minimum_scale, fitted - 0.02)
    cv2.putText(img, text, origin, font, fitted, colour, thickness, cv2.LINE_AA)
    return fitted


def status_for_display(status: str) -> str:
    """Keep the presentation label compact without changing classification data."""
    if status == "ANNOTATION: TARGET ABSENT":
        return "TARGET ABSENT"
    return status


def letterbox_image(img, width: int, height: int):
    """Fit the complete camera image into a viewport without cropping or distortion."""
    source_h, source_w = img.shape[:2]
    scale = min(width / float(source_w), height / float(source_h))
    resized_w = max(1, int(round(source_w * scale)))
    resized_h = max(1, int(round(source_h * scale)))
    resized = cv2.resize(img, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    pad_x = (width - resized_w) // 2
    pad_y = (height - resized_h) // 2
    viewport = np.zeros((height, width, 3), dtype=np.uint8)
    viewport[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized
    return viewport, scale, pad_x, pad_y


def transform_box(box, scale: float, pad_x: int, pad_y: int):
    if box is None:
        return None
    x1, y1, x2, y2 = box
    return (
        int(round(x1 * scale + pad_x)),
        int(round(y1 * scale + pad_y)),
        int(round(x2 * scale + pad_x)),
        int(round(y2 * scale + pad_y)),
    )


def draw_panel(
    img,
    title,
    status,
    colour,
    t_s,
    out_id,
    ref_id,
    out_box,
    ref_box,
    event_type,
    output_age_s,
    header_height=HEADER_HEIGHT,
):
    camera_h, w = img.shape[:2]
    h = header_height + camera_h
    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[header_height:, :] = img

    put_text_fit(out, title, (16, 30), w - 32, 0.72, WHITE, 2, 0.52)
    cv2.putText(
        out,
        status_for_display(status),
        (16, 64),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        colour,
        3,
        cv2.LINE_AA,
    )
    age_text = "none" if output_age_s is None else f"{output_age_s:.2f}s"
    put_text_fit(
        out,
        f"t={t_s:.2f}s | out={out_id} | age={age_text} | ref={ref_id}",
        (292, 62),
        w - 308,
        0.48,
        (230, 230, 230),
        1,
        0.40,
    )
    detail = f"event={event_type or 'unlabelled'}"
    if ref_id > 0 and ref_box is None:
        detail += f" | annotation ref {ref_id} not present in /tracks"
    else:
        detail += " | solid: output | dashed white: annotation ref"
    put_text_fit(
        out,
        detail,
        (16, 93),
        w - 32,
        0.47,
        WHITE,
        1,
        0.40,
    )

    if out_box is not None:
        x1, y1, x2, y2 = out_box
        y1 += header_height
        y2 += header_height
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 4)
        draw_text_box(out, f"OUT {out_id}", x1, min(h - 12, y2 + 26), colour)

    if ref_box is not None:
        x1, y1, x2, y2 = ref_box
        y1 += header_height
        y2 += header_height
        shifted_ref_box = (x1, y1, x2, y2)
        draw_dashed_rectangle(out, shifted_ref_box, WHITE, 2)
        draw_text_box(
            out,
            f"ANNOTATION REF {ref_id}",
            x1,
            max(header_height + 22, y1 - 4),
            WHITE,
        )

    return out


def render_panel(args) -> dict:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    ann = load_annotations(args.annotation)
    types = topic_types(args.bag)
    image_topic = choose_image_topic(types, args.image_topic)

    t0_ns = args.t0_ns
    track_events, output_events = read_events(args.bag, t0_ns, args.tracks_topic, args.output_topic)

    ann_start = min(x.start_s for x in ann) if ann else 0.0
    ann_end = max(x.end_s for x in ann) if ann else 0.0
    render_start = max(ann_start, args.start_s if args.start_s is not None else ann_start)
    render_end = min(ann_end, args.end_s if args.end_s is not None else ann_end)
    if render_end <= render_start:
        die(f"invalid render window: {render_start:.3f}..{render_end:.3f}s")
    render_duration = max(0.001, render_end - render_start)

    # If FPS is not explicitly set, encode sparse recorded image frames so that
    # playback duration matches the official header-time annotation window.
    # This avoids compressing a 67.6 s evaluation into ~40 s just because the
    # recorded image topic is below 15 Hz.
    fps = args.fps if args.fps > 0 else args.default_fps

    source_w, source_h = first_image_dimensions(
        args.bag, image_topic, types[image_topic]
    )
    out_w = args.output_width
    camera_h = max(2, int(round(out_w * source_h / float(source_w))))
    if camera_h % 2:
        camera_h += 1
    out_h = args.header_height + camera_h

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    image_type = get_message(types[image_topic])
    reader = open_reader(args.bag)

    writer = cv2.VideoWriter(
        str(args.output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (out_w, out_h),
    )
    if not writer.isOpened():
        die(f"could not open writer: {args.output}")

    track_idx = 0
    output_idx = 0
    latest_tracks = {}
    latest_tracks_source_pixels = False
    latest_output_id = 0

    counts = {"correct": 0, "wrong": 0, "lost": 0, "grey": 0}
    rendered = 0
    first_t = None
    last_t = None

    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic != image_topic:
            continue

        msg = deserialize_message(raw, image_type)
        t = header_ns(msg)
        if t is None:
            continue

        t_s = (t - t0_ns) * 1e-9
        if t_s < render_start:
            continue
        if t_s > render_end:
            break

        a = ann_at(ann, t_s)

        if args.visible_only:
            if a is None:
                continue
            if not a.target_visible:
                continue
            if a.target_label.upper() in {"NO_TARGET_SELECTED", "TARGET_NOT_VISIBLE"}:
                continue

        track_idx, track_t, tv = latest_sample_at(track_events, track_idx, t_s)
        if tv is not None and t_s - track_t <= args.max_track_age_s:
            latest_tracks, latest_tracks_source_pixels = tv
        elif track_t is None or t_s - track_t > args.max_track_age_s:
            latest_tracks = {}
            latest_tracks_source_pixels = False

        output_idx, output_t, ov = latest_sample_at(output_events, output_idx, t_s)
        output_age_s = None if output_t is None else max(0.0, t_s - output_t)
        if ov is not None and output_age_s <= args.max_output_age_s:
            latest_output_id = int(ov)
        else:
            latest_output_id = 0

        status, colour, ref_id, bucket = classify(a, latest_output_id)

        img = image_to_bgr(msg)

        out_box = None
        if latest_output_id > 0 and latest_output_id in latest_tracks:
            out_box = map_box(
                latest_tracks[latest_output_id],
                img.shape[1],
                img.shape[0],
                latest_tracks_source_pixels,
                args.track_coord_w,
                args.track_coord_h,
            )

        ref_box = None
        if ref_id > 0 and ref_id in latest_tracks:
            ref_box = map_box(
                latest_tracks[ref_id],
                img.shape[1],
                img.shape[0],
                latest_tracks_source_pixels,
                args.track_coord_w,
                args.track_coord_h,
            )

        camera, camera_scale, camera_pad_x, camera_pad_y = letterbox_image(
            img, out_w, camera_h
        )
        frame = draw_panel(
            camera,
            args.title,
            status,
            colour,
            t_s,
            latest_output_id,
            ref_id,
            transform_box(out_box, camera_scale, camera_pad_x, camera_pad_y),
            transform_box(ref_box, camera_scale, camera_pad_x, camera_pad_y),
            a.event_type if a is not None else "no_annotation",
            output_age_s,
            args.header_height,
        )
        writer.write(frame)

        rendered += 1
        counts[bucket] = counts.get(bucket, 0) + 1
        first_t = t_s if first_t is None else first_t
        last_t = t_s

        if rendered % 250 == 0:
            print(f"[info] {args.title}: {rendered} frames")

        if args.max_frames > 0 and rendered >= args.max_frames:
            break

    writer.release()

    if args.max_frames > 0 and first_t is not None and last_t is not None:
        render_duration = max(
            1.0 / args.default_fps,
            last_t - first_t + 1.0 / args.default_fps,
        )

    if args.fps <= 0 and rendered > 0:
        fps = rendered / render_duration

        # Re-encode the just-written panel with the duration-correct FPS.
        # OpenCV VideoWriter cannot change FPS after opening, so use ffmpeg
        # to reinterpret the frame rate without changing frame content.
        tmp_output = args.output.with_suffix(".duration_tmp.mp4")
        args.output.replace(tmp_output)
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-r",
                f"{fps:.9f}",
                "-i",
                str(tmp_output),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(args.output),
            ],
            check=True,
        )
        tmp_output.unlink(missing_ok=True)

    d = {
        "bag": str(args.bag),
        "annotation": str(args.annotation),
        "output_topic": args.output_topic,
        "tracks_topic": args.tracks_topic,
        "image_topic": image_topic,
        "title": args.title,
        "timebase": "header",
        "fps": fps,
        "frame_count": rendered,
        "video_duration_s": rendered / fps if fps > 0 else 0.0,
        "first_render_header_s": first_t,
        "last_render_header_s": last_t,
        "visible_annotation_duration_s": visible_duration(ann),
        "render_start_s": render_start,
        "render_end_s": render_end,
        "max_output_age_s": args.max_output_age_s,
        "max_track_age_s": args.max_track_age_s,
        "source_image_size": f"{source_w}x{source_h}",
        "camera_viewport_size": f"{out_w}x{camera_h}",
        "panel_size": f"{out_w}x{out_h}",
        "counts": counts,
        "output": str(args.output),
    }

    args.summary.write_text(json.dumps(d, indent=2) + "\n")

    print(f"[ok] panel={args.output}")
    print(f"[ok] frames={rendered} fps={fps:.3f} duration={d['video_duration_s']:.3f}s counts={counts}")
    return d


def join_pair(left: Path, right: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(left),
        "-i",
        str(right),
        "-filter_complex",
        "[0:v]fps=15,setpts=PTS-STARTPTS[v0];[1:v]fps=15,setpts=PTS-STARTPTS[v1];[v0][v1]hstack=inputs=2[v]",
        "-map",
        "[v]",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    print(f"[ok] pair={out}")


def panel_namespace(**kwargs):
    values = {
        "image_topic": "auto",
        "tracks_topic": "/tracks",
        "fps": 0.0,
        "default_fps": 15.0,
        "output_width": 960,
        "header_height": HEADER_HEIGHT,
        "track_coord_w": 640.0,
        "track_coord_h": 640.0,
        "visible_only": False,
        "max_frames": 0,
        "max_output_age_s": 1.0,
        "max_track_age_s": 1.0,
        "start_s": None,
        "end_s": None,
    }
    values.update(kwargs)
    return argparse.Namespace(**values)


def render_pair(
    name: str,
    bag: Path,
    annotation: Path,
    raw_title: str,
    tim_title: str,
    output: Path,
    image_topic: str,
    start_s: Optional[float],
    end_s: Optional[float],
    max_frames: int,
    max_output_age_s: float,
    max_track_age_s: float,
):
    out_dir = output.parent
    final_name = output.name
    tmp = out_dir / "_tmp_panels"
    tmp.mkdir(parents=True, exist_ok=True)

    raw_panel = tmp / f"{name}_raw_panel.mp4"
    tim_panel = tmp / f"{name}_tim_mars_panel.mp4"
    raw_summary = tmp / f"{name}_raw_panel.json"
    tim_summary = tmp / f"{name}_tim_mars_panel.json"

    types = topic_types(bag)
    selected_image_topic = choose_image_topic(types, image_topic)
    t0_ns = first_header_for_topic(bag, selected_image_topic)
    common = {
        "bag": bag,
        "annotation": annotation,
        "image_topic": selected_image_topic,
        "t0_ns": t0_ns,
        "start_s": start_s,
        "end_s": end_s,
        "max_frames": max_frames,
        "max_output_age_s": max_output_age_s,
        "max_track_age_s": max_track_age_s,
    }

    raw = render_panel(
        panel_namespace(
            output_topic="/target",
            output=raw_panel,
            summary=raw_summary,
            title=raw_title,
            **common,
        )
    )

    tim = render_panel(
        panel_namespace(
            output_topic="/target_memory_mars",
            output=tim_panel,
            summary=tim_summary,
            title=tim_title,
            **common,
        )
    )

    final = out_dir / final_name
    join_pair(raw_panel, tim_panel, final)
    raw_panel.unlink(missing_ok=True)
    tim_panel.unlink(missing_ok=True)

    return {
        "name": name,
        "final_video": str(final),
        "raw": raw,
        "tim_mars": tim,
    }


def write_summary(output: Path, summaries: list[dict]) -> None:
    out_json = output.with_suffix(".json")
    out_md = output.with_suffix(".md")

    out_json.write_text(json.dumps(summaries, indent=2) + "\n")

    lines = [
        "# TIM-MARS comparison video",
        "",
        "Timebase: ROS message header time.",
        "",
        "| Tracker | Panel | Frames | FPS | Video duration [s] | Visible annotation [s] | Correct | Wrong | Lost | Grey |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        for panel_name, key in [("Raw", "raw"), ("TIM-MARS", "tim_mars")]:
            d = s[key]
            c = d["counts"]
            lines.append(
                f"| {s['name']} | {panel_name} | "
                f"{d['frame_count']} | {d['fps']:.3f} | {d['video_duration_s']:.3f} | "
                f"{d['visible_annotation_duration_s']:.3f} | "
                f"{c.get('correct', 0)} | {c.get('wrong', 0)} | {c.get('lost', 0)} | {c.get('grey', 0)} |"
            )

    lines.append("")
    lines.append("Generated videos:")
    for s in summaries:
        lines.append(f"- `{s['final_video']}`")

    out_md.write_text("\n".join(lines) + "\n")
    print(f"[ok] summary={out_md}")
    print(f"[ok] summary={out_json}")


def render_comparison(args) -> int:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in args.output.stem
    ).strip("_")

    s = render_pair(
        name=safe_name,
        bag=args.bag,
        annotation=args.annotation,
        raw_title=(
            f"{args.sequence_label} | RAW [/target] | {args.tracker_label}"
        ),
        tim_title=(
            f"{args.sequence_label} | TIM-MARS [/target_memory_mars] | "
            f"{args.tracker_label}"
        ),
        output=args.output,
        image_topic=args.image_topic,
        start_s=args.start_s,
        end_s=args.end_s,
        max_frames=args.max_frames,
        max_output_age_s=args.max_output_age_s,
        max_track_age_s=args.max_track_age_s,
    )
    write_summary(args.output, [s])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Render one header-time raw-target versus TIM-MARS comparison."
        )
    )
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotation", type=Path, required=True)
    p.add_argument("--sequence-label", required=True)
    p.add_argument("--tracker-label", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--image-topic", default="auto")
    p.add_argument("--start-s", type=float)
    p.add_argument("--end-s", type=float)
    p.add_argument("--max-frames", type=int, default=0)
    p.add_argument("--max-output-age-s", type=float, default=1.0)
    p.add_argument("--max-track-age-s", type=float, default=1.0)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return render_comparison(args)


if __name__ == "__main__":
    raise SystemExit(main())
