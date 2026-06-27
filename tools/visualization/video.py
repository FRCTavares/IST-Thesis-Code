#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np


GREEN = (0, 210, 0)
RED = (0, 0, 255)
YELLOW = (0, 220, 255)
GREY = (160, 160, 160)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)


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
        return "NOT VISIBLE", GREY, ann.correct_id, "grey"

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


def map_box(box, img_w: int, img_h: int, coord_w: float, coord_h: float):
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
                track_events.append(((t - t0_ns) * 1e-9, extract_tracks(msg)))

        elif topic == output_topic:
            msg = deserialize_message(raw, output_type)
            t = header_ns(msg)
            if t is not None:
                output_events.append(((t - t0_ns) * 1e-9, selected_id(msg)))

    return track_events, output_events


def latest_at(events, idx: int, t_s: float):
    if not events:
        return idx, None
    while idx + 1 < len(events) and events[idx + 1][0] <= t_s:
        idx += 1
    if events[idx][0] > t_s:
        return idx, None
    return idx, events[idx][1]


def infer_fps(bag: Path, image_topic: str, t0_ns: int, default: float) -> float:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    types = topic_types(bag)
    msg_type = get_message(types[image_topic])
    reader = open_reader(bag)
    times = []

    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic != image_topic:
            continue
        msg = deserialize_message(raw, msg_type)
        t = header_ns(msg)
        if t is not None:
            ts = (t - t0_ns) * 1e-9
            if ts >= 0:
                times.append(ts)

    if len(times) < 4:
        return default

    dts = [b - a for a, b in zip(times[:-1], times[1:])]
    dts = [dt for dt in dts if 0.001 <= dt <= 1.0]
    if not dts:
        return default

    return max(1.0, min(60.0, 1.0 / statistics.median(dts)))


def draw_text_box(img, text: str, x: int, y: int, colour):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.52
    thickness = 1
    tw, th = cv2.getTextSize(text, font, scale, thickness)[0]
    y0 = max(0, y - th - 7)
    x0 = max(0, x)
    cv2.rectangle(img, (x0, y0), (min(img.shape[1] - 1, x0 + tw + 8), y0 + th + 10), colour, -1)
    cv2.putText(img, text, (x0 + 4, y0 + th + 2), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)


def draw_panel(img, title, status, colour, t_s, out_id, ref_id, out_box, ref_box):
    out = img.copy()
    h, w = out.shape[:2]

    cv2.rectangle(out, (0, 0), (w, 88), (0, 0, 0), -1)
    cv2.putText(out, title, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.72, WHITE, 2, cv2.LINE_AA)
    cv2.putText(out, status, (16, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.95, colour, 3, cv2.LINE_AA)
    cv2.putText(
        out,
        f"header t={t_s:.2f}s  output={out_id}  reference={ref_id}",
        (260, 64),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (230, 230, 230),
        2,
        cv2.LINE_AA,
    )

    if ref_box is not None:
        x1, y1, x2, y2 = ref_box
        cv2.rectangle(out, (x1, y1), (x2, y2), CYAN, 2)
        draw_text_box(out, f"REF {ref_id}", x1, max(96, y1 - 4), CYAN)

    if out_box is not None:
        x1, y1, x2, y2 = out_box
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 4)
        draw_text_box(out, f"OUT {out_id}", x1, min(h - 12, y2 + 26), colour)

    return out


def render_panel(args) -> dict:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    ann = load_annotations(args.annotation)
    types = topic_types(args.bag)
    image_topic = choose_image_topic(types, args.image_topic)

    t0_ns = first_header_for_topic(args.bag, args.output_topic)
    track_events, output_events = read_events(args.bag, t0_ns, args.tracks_topic, args.output_topic)

    ann_start = min(x.start_s for x in ann) if ann else 0.0
    ann_end = max(x.end_s for x in ann) if ann else 0.0
    ann_duration = max(0.001, ann_end - ann_start)

    # If FPS is not explicitly set, encode sparse recorded image frames so that
    # playback duration matches the official header-time annotation window.
    # This avoids compressing a 67.6 s evaluation into ~40 s just because the
    # recorded image topic is below 15 Hz.
    fps = args.fps if args.fps > 0 else args.default_fps

    out_w, out_h = [int(x) for x in args.output_size.lower().split("x")]

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
        if ann:
            if t_s < ann_start or t_s > ann_end:
                continue

        a = ann_at(ann, t_s)

        if args.visible_only:
            if a is None:
                continue
            if not a.target_visible:
                continue
            if a.target_label.upper() in {"NO_TARGET_SELECTED", "TARGET_NOT_VISIBLE"}:
                continue

        track_idx, tv = latest_at(track_events, track_idx, t_s)
        if tv is not None:
            latest_tracks = tv

        output_idx, ov = latest_at(output_events, output_idx, t_s)
        if ov is not None:
            latest_output_id = int(ov)

        status, colour, ref_id, bucket = classify(a, latest_output_id)

        img = image_to_bgr(msg)

        out_box = None
        if latest_output_id > 0 and latest_output_id in latest_tracks:
            out_box = map_box(
                latest_tracks[latest_output_id],
                img.shape[1],
                img.shape[0],
                args.track_coord_w,
                args.track_coord_h,
            )

        ref_box = None
        if ref_id > 0 and ref_id in latest_tracks:
            ref_box = map_box(
                latest_tracks[ref_id],
                img.shape[1],
                img.shape[0],
                args.track_coord_w,
                args.track_coord_h,
            )

        frame = draw_panel(img, args.title, status, colour, t_s, latest_output_id, ref_id, out_box, ref_box)
        frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
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

    if args.fps <= 0 and rendered > 0:
        fps = rendered / ann_duration

        # Re-encode the just-written panel with the duration-correct FPS.
        # OpenCV VideoWriter cannot change FPS after opening, so use ffmpeg
        # to reinterpret the frame rate without changing frame content.
        tmp_output = args.output.with_suffix(".duration_tmp.mp4")
        args.output.replace(tmp_output)
        subprocess.run(
            [
                "ffmpeg",
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
        "-y",
        "-i",
        str(left),
        "-i",
        str(right),
        "-filter_complex",
        "[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];[v0][v1]hstack=inputs=2[v]",
        "-map",
        "[v]",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    print(f"[ok] pair={out}")


def panel_namespace(**kwargs):
    return argparse.Namespace(
        image_topic="auto",
        tracks_topic="/tracks",
        fps=0.0,
        default_fps=15.0,
        output_size="960x540",
        track_coord_w=640.0,
        track_coord_h=640.0,
        visible_only=False,
        max_frames=0,
        **kwargs,
    )


def render_pair(
    name: str,
    raw_bag: Path,
    tim_bag: Path,
    annotation: Path,
    raw_title: str,
    tim_title: str,
    out_dir: Path,
    final_name: str,
):
    tmp = out_dir / "_tmp_panels"
    tmp.mkdir(parents=True, exist_ok=True)

    raw_panel = tmp / f"{name}_raw_panel.mp4"
    tim_panel = tmp / f"{name}_tim_mars_panel.mp4"
    raw_summary = tmp / f"{name}_raw_panel.json"
    tim_summary = tmp / f"{name}_tim_mars_panel.json"

    raw = render_panel(
        panel_namespace(
            bag=raw_bag,
            annotation=annotation,
            output_topic="/target",
            output=raw_panel,
            summary=raw_summary,
            title=raw_title,
        )
    )

    tim = render_panel(
        panel_namespace(
            bag=tim_bag,
            annotation=annotation,
            output_topic="/target_memory_mars",
            output=tim_panel,
            summary=tim_summary,
            title=tim_title,
        )
    )

    final = out_dir / final_name
    join_pair(raw_panel, tim_panel, final)

    return {
        "name": name,
        "final_video": str(final),
        "raw": raw,
        "tim_mars": tim,
    }


def write_batch_summary(out_dir: Path, summaries: list[dict]) -> None:
    out_json = out_dir / "summary.json"
    out_md = out_dir / "summary.md"

    out_json.write_text(json.dumps(summaries, indent=2) + "\n")

    lines = [
        "# Header-time visual validation videos",
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


def cmd_tim_header_all(args) -> int:
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base = Path("artifacts/bags/derived/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1")

    summaries = [
        render_pair(
            name="ByteTrack",
            raw_bag=Path(str(base) + "__tracker_bytetrack__tim_off__target_1__r2"),
            tim_bag=Path(str(base) + "__tracker_bytetrack__tim_mars__target_1__r4"),
            annotation=Path("docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv"),
            raw_title="ByteTrack Raw /target",
            tim_title="ByteTrack + TIM-MARS /target_memory_mars",
            out_dir=out_dir,
            final_name="bytetrack_raw_vs_tim_mars_header_time.mp4",
        ),
        render_pair(
            name="OCSORT",
            raw_bag=Path(str(base) + "__tracker_ocsort__tim_off__target_1"),
            tim_bag=Path(str(base) + "__tracker_ocsort__tim_mars__target_1__r1"),
            annotation=Path("docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv"),
            raw_title="OCSORT Raw /target",
            tim_title="OCSORT + TIM-MARS /target_memory_mars",
            out_dir=out_dir,
            final_name="ocsort_raw_vs_tim_mars_header_time.mp4",
        ),
        render_pair(
            name="DeepSORT-MARS",
            raw_bag=Path(str(base) + "__tracker_deepsort__tim_off__target_1"),
            tim_bag=Path(str(base) + "__tracker_deepsort__tim_mars__target_1"),
            annotation=Path("docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv"),
            raw_title="DeepSORT-MARS Raw /target",
            tim_title="DeepSORT-MARS + TIM-MARS /target_memory_mars",
            out_dir=out_dir,
            final_name="deepsort_mars_raw_vs_tim_mars_header_time.mp4",
        ),
    ]

    write_batch_summary(out_dir, summaries)
    return 0


def cmd_tim_header_pair(args) -> int:
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    s = render_pair(
        name=args.name,
        raw_bag=args.raw_bag,
        tim_bag=args.tim_bag,
        annotation=args.annotation,
        raw_title=args.raw_title,
        tim_title=args.tim_title,
        out_dir=out_dir,
        final_name=args.output_name,
    )
    write_batch_summary(out_dir, [s])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Canonical thesis video renderer.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("tim-header-all", help="Render all official raw-vs-TIM-MARS header-time validation videos.")
    p_all.add_argument("--out-dir", type=Path, default=Path("reports/visual_validation_header_time_2026-06-17"))
    p_all.set_defaults(func=cmd_tim_header_all)

    p_pair = sub.add_parser("tim-header-pair", help="Render one raw-vs-TIM-MARS header-time validation video.")
    p_pair.add_argument("--name", required=True)
    p_pair.add_argument("--raw-bag", type=Path, required=True)
    p_pair.add_argument("--tim-bag", type=Path, required=True)
    p_pair.add_argument("--annotation", type=Path, required=True)
    p_pair.add_argument("--raw-title", required=True)
    p_pair.add_argument("--tim-title", required=True)
    p_pair.add_argument("--output-name", required=True)
    p_pair.add_argument("--out-dir", type=Path, default=Path("reports/visual_validation_header_time_2026-06-17"))
    p_pair.set_defaults(func=cmd_tim_header_pair)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
