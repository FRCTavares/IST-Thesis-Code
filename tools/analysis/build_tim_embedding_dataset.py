#!/usr/bin/env python3
"""
Build labelled crop dataset for TIM-V2E learned embedding.

Offline only.

Inputs:
- ROS 2 bag with image topic and /tracks
- target correctness annotations
- optional target_id_aliases.csv

Output:
- crops/*.png
- samples.csv

Labels:
- correct: annotated selected target or alias
- distractor: annotated distractor IDs
- other: visible track not listed as correct/distractor
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import numpy as np


BBox = Tuple[float, float, float, float]


@dataclass
class AnnotationInterval:
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int
    distractor_track_ids: list[int]
    event_type: str


@dataclass
class AliasInterval:
    start_s: float
    end_s: float
    primary_correct_id: int
    alias_correct_ids: list[int]


@dataclass
class ImageRow:
    t: float
    image_bgr: np.ndarray


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def as_int(v: Any, default: int = 0) -> int:
    try:
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def as_bool(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def parse_id_list(v: Any) -> list[int]:
    text = str(v or "").strip()
    if not text:
        return []
    out = []
    for part in text.replace(";", ",").split(","):
        tid = as_int(part.strip(), 0)
        if tid > 0:
            out.append(tid)
    return out


def load_annotations(path: Path) -> list[AnnotationInterval]:
    rows: list[AnnotationInterval] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "start_s",
            "end_s",
            "target_label",
            "target_visible",
            "correct_target_track_id",
            "distractor_track_ids",
            "event_type",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Annotation CSV missing columns: {sorted(missing)}")

        for r in reader:
            rows.append(
                AnnotationInterval(
                    start_s=as_float(r["start_s"]),
                    end_s=as_float(r["end_s"]),
                    target_label=str(r["target_label"]).strip(),
                    target_visible=as_bool(r["target_visible"]),
                    correct_target_track_id=as_int(r["correct_target_track_id"], 0),
                    distractor_track_ids=parse_id_list(r["distractor_track_ids"]),
                    event_type=str(r["event_type"]).strip(),
                )
            )
    rows.sort(key=lambda x: x.start_s)
    return rows


def load_aliases(path: Optional[Path]) -> list[AliasInterval]:
    if path is None or not path.exists():
        return []

    rows: list[AliasInterval] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"start_s", "end_s", "primary_correct_id", "alias_correct_ids"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Alias CSV missing columns: {sorted(missing)}")

        for r in reader:
            rows.append(
                AliasInterval(
                    start_s=as_float(r["start_s"]),
                    end_s=as_float(r["end_s"]),
                    primary_correct_id=as_int(r["primary_correct_id"], 0),
                    alias_correct_ids=parse_id_list(r["alias_correct_ids"]),
                )
            )
    rows.sort(key=lambda x: x.start_s)
    return rows


def annotation_for_time(t: float, annotations: list[AnnotationInterval]) -> Optional[AnnotationInterval]:
    for ann in annotations:
        if ann.start_s <= t < ann.end_s:
            return ann
    return None


def correct_ids_at(t: float, correct_id: int, aliases: list[AliasInterval]) -> set[int]:
    ids = {correct_id} if correct_id > 0 else set()
    for a in aliases:
        if a.start_s <= t < a.end_s and a.primary_correct_id == correct_id:
            ids.update(a.alias_correct_ids)
    return ids


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
    encoding = str(msg.encoding).lower()
    h = int(msg.height)
    w = int(msg.width)
    step = int(msg.step)

    if encoding not in {"bgr8", "rgb8"}:
        raise RuntimeError(f"Unsupported image encoding: {msg.encoding}")

    expected_step = w * 3
    if step != expected_step:
        raise RuntimeError(f"Unsupported image step={step}, expected={expected_step}")

    expected_bytes = h * step
    if len(msg.data) < expected_bytes:
        raise RuntimeError(f"Image data too small: got={len(msg.data)}, expected={expected_bytes}")

    img = np.frombuffer(msg.data, dtype=np.uint8)[:expected_bytes].reshape((h, w, 3))
    if encoding == "rgb8":
        img = img[:, :, ::-1]
    return np.ascontiguousarray(img.copy())


def safe_get(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def get_track_id(track: Any) -> int:
    return as_int(safe_get(track, ["id", "track_id", "target_id"], 0), 0)


def get_track_score(track: Any) -> float:
    return as_float(safe_get(track, ["score", "confidence"], 0.0), 0.0)


def get_track_bbox(track: Any, img_w: int, img_h: int) -> Optional[BBox]:
    cx = safe_get(track, ["cx", "center_x", "bbox_cx"], None)
    cy = safe_get(track, ["cy", "center_y", "bbox_cy"], None)
    bw = safe_get(track, ["w", "width", "bbox_w"], None)
    bh = safe_get(track, ["h", "height", "bbox_h"], None)

    if cx is not None and cy is not None and bw is not None and bh is not None:
        cx_f = as_float(cx)
        cy_f = as_float(cy)
        bw_f = as_float(bw)
        bh_f = as_float(bh)

        if 0.0 <= cx_f <= 1.5 and 0.0 <= cy_f <= 1.5 and 0.0 <= bw_f <= 1.5 and 0.0 <= bh_f <= 1.5:
            cx_f *= img_w
            bw_f *= img_w
            cy_f *= img_h
            bh_f *= img_h

        return (
            cx_f - 0.5 * bw_f,
            cy_f - 0.5 * bh_f,
            cx_f + 0.5 * bw_f,
            cy_f + 0.5 * bh_f,
        )

    if hasattr(track, "bbox"):
        return get_track_bbox(getattr(track, "bbox"), img_w, img_h)

    return None


def nearest_image(images: list[ImageRow], t: float, max_dt: float) -> tuple[Optional[np.ndarray], float]:
    if not images:
        return None, float("inf")
    best = min(images, key=lambda r: abs(r.t - t))
    dt = abs(best.t - t)
    if dt > max_dt:
        return None, dt
    return best.image_bgr, dt


def expand_and_clip_bbox(
    bbox: BBox,
    img_w: int,
    img_h: int,
    pad_x_frac: float,
    pad_y_frac: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)

    x1 -= pad_x_frac * w
    x2 += pad_x_frac * w
    y1 -= pad_y_frac * h
    y2 += pad_y_frac * h

    xi1 = max(0, min(img_w - 1, int(math.floor(x1))))
    yi1 = max(0, min(img_h - 1, int(math.floor(y1))))
    xi2 = max(0, min(img_w, int(math.ceil(x2))))
    yi2 = max(0, min(img_h, int(math.ceil(y2))))

    return xi1, yi1, xi2, yi2


def read_bag_and_export(
    *,
    bag_path: Path,
    image_topic: str,
    tracks_topic: str,
    annotations: list[AnnotationInterval],
    aliases: list[AliasInterval],
    output_dir: Path,
    max_image_dt: float,
    min_bbox_h: float,
    pad_x_frac: float,
    pad_y_frac: float,
    crop_w: int,
    crop_h: int,
    include_other: bool,
    max_per_role_event: int,
) -> int:
    import cv2

    SequentialReader, StorageOptions, ConverterOptions, deserialize_message, get_message = import_rosbag_tools()

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag_path), storage_id=detect_storage_id(bag_path)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {m.name: m.type for m in reader.get_all_topics_and_types()}
    missing = [t for t in [image_topic, tracks_topic] if t not in topic_types]
    if missing:
        raise SystemExit(f"Bag missing required topic(s): {missing}. Available topics: {sorted(topic_types)}")

    image_type = get_message(topic_types[image_topic])
    tracks_type = get_message(topic_types[tracks_topic])

    crops_dir = output_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    samples_path = output_dir / "samples.csv"

    first_t_ns: Optional[int] = None
    latest_img_shape: Optional[tuple[int, int]] = None
    images: list[ImageRow] = []
    rows_out: list[dict[str, Any]] = []
    counts: dict[tuple[str, str], int] = {}

    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        if first_t_ns is None:
            first_t_ns = int(t_ns)
        t_s = (int(t_ns) - first_t_ns) / 1e9

        if topic == image_topic:
            msg = deserialize_message(data, image_type)
            try:
                img = image_msg_to_bgr(msg)
            except Exception as exc:
                print(f"[warn] skipped image t={t_s:.3f}: {exc}")
                continue
            latest_img_shape = (int(img.shape[1]), int(img.shape[0]))
            images.append(ImageRow(t=t_s, image_bgr=img))

            # Keep memory bounded. Only nearest recent image is needed.
            if len(images) > 200:
                images = images[-200:]

        elif topic == tracks_topic:
            if latest_img_shape is None:
                img_w, img_h = 640, 640
            else:
                img_w, img_h = latest_img_shape

            ann = annotation_for_time(t_s, annotations)
            if ann is None:
                continue
            if ann.target_label == "NO_TARGET_SELECTED":
                continue

            image, image_dt = nearest_image(images, t_s, max_dt=max_image_dt)
            if image is None:
                continue

            msg = deserialize_message(data, tracks_type)
            frame_id = as_int(getattr(msg, "frame_id", 0), 0)
            tracks = list(getattr(msg, "tracks", []))

            correct_ids = correct_ids_at(t_s, ann.correct_target_track_id, aliases)
            distractor_ids = set(ann.distractor_track_ids)

            for tr in tracks:
                tid = get_track_id(tr)
                if tid <= 0:
                    continue

                bbox = get_track_bbox(tr, img_w=img_w, img_h=img_h)
                if bbox is None:
                    continue

                x1, y1, x2, y2 = bbox
                bbox_h = float(y2 - y1)
                if bbox_h < min_bbox_h:
                    continue

                if tid in correct_ids:
                    role = "correct"
                    identity_label = "selected_target"
                elif tid in distractor_ids:
                    role = "distractor"
                    identity_label = f"distractor_{tid}"
                else:
                    if not include_other:
                        continue
                    role = "other"
                    identity_label = f"other_{tid}"

                key = (role, ann.event_type)
                if max_per_role_event > 0 and counts.get(key, 0) >= max_per_role_event:
                    continue
                counts[key] = counts.get(key, 0) + 1

                xi1, yi1, xi2, yi2 = expand_and_clip_bbox(
                    bbox,
                    img_w=img_w,
                    img_h=img_h,
                    pad_x_frac=pad_x_frac,
                    pad_y_frac=pad_y_frac,
                )
                if xi2 <= xi1 or yi2 <= yi1:
                    continue

                crop = image[yi1:yi2, xi1:xi2]
                if crop.size == 0:
                    continue

                crop = cv2.resize(crop, (crop_w, crop_h), interpolation=cv2.INTER_AREA)

                fname = f"frame{frame_id:06d}_t{t_s:08.3f}_id{tid:04d}_{role}_{ann.event_type}.png"
                rel_path = Path("crops") / fname
                abs_path = output_dir / rel_path
                ok = cv2.imwrite(str(abs_path), crop)
                if not ok:
                    raise RuntimeError(f"Failed to write crop: {abs_path}")

                rows_out.append(
                    {
                        "crop_path": str(rel_path),
                        "t": f"{t_s:.6f}",
                        "frame_id": frame_id,
                        "track_id": tid,
                        "role": role,
                        "identity_label": identity_label,
                        "event_type": ann.event_type,
                        "target_visible": str(ann.target_visible).lower(),
                        "bbox_x1": f"{x1:.3f}",
                        "bbox_y1": f"{y1:.3f}",
                        "bbox_x2": f"{x2:.3f}",
                        "bbox_y2": f"{y2:.3f}",
                        "bbox_h": f"{bbox_h:.3f}",
                        "score": f"{get_track_score(tr):.6f}",
                        "image_dt": f"{image_dt:.6f}",
                    }
                )

    with samples_path.open("w", newline="") as f:
        fieldnames = [
            "crop_path",
            "t",
            "frame_id",
            "track_id",
            "role",
            "identity_label",
            "event_type",
            "target_visible",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
            "bbox_h",
            "score",
            "image_dt",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    summary_path = output_dir / "summary.md"
    role_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    for r in rows_out:
        role_counts[str(r["role"])] = role_counts.get(str(r["role"]), 0) + 1
        event_counts[str(r["event_type"])] = event_counts.get(str(r["event_type"]), 0) + 1

    lines = [
        "# TIM-V2E embedding crop dataset",
        "",
        f"- Bag: `{bag_path}`",
        f"- Image topic: `{image_topic}`",
        f"- Tracks topic: `{tracks_topic}`",
        f"- Samples: {len(rows_out)}",
        f"- Crop size: {crop_w}x{crop_h}",
        f"- Min bbox height: {min_bbox_h}",
        "",
        "## Role counts",
        "",
        "| Role | Count |",
        "|---|---:|",
    ]
    for k, v in sorted(role_counts.items()):
        lines.append(f"| {k} | {v} |")

    lines.extend(["", "## Event counts", "", "| Event | Count |", "|---|---:|"])
    for k, v in sorted(event_counts.items()):
        lines.append(f"| {k} | {v} |")

    lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[ok] wrote {samples_path}")
    print(f"[ok] wrote {summary_path}")
    print(f"[ok] crops={len(rows_out)}")
    return len(rows_out)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--aliases", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--image-topic", default="/camera/dashboard")
    p.add_argument("--tracks-topic", default="/tracks")
    p.add_argument("--max-image-dt", type=float, default=0.08)
    p.add_argument("--min-bbox-h", type=float, default=24.0)
    p.add_argument("--pad-x-frac", type=float, default=0.10)
    p.add_argument("--pad-y-frac", type=float, default=0.05)
    p.add_argument("--crop-w", type=int, default=64)
    p.add_argument("--crop-h", type=int, default=128)
    p.add_argument("--include-other", action="store_true")
    p.add_argument("--max-per-role-event", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    annotations = load_annotations(args.annotations)
    aliases = load_aliases(args.aliases)

    n = read_bag_and_export(
        bag_path=args.bag,
        image_topic=args.image_topic,
        tracks_topic=args.tracks_topic,
        annotations=annotations,
        aliases=aliases,
        output_dir=args.output_dir,
        max_image_dt=args.max_image_dt,
        min_bbox_h=args.min_bbox_h,
        pad_x_frac=args.pad_x_frac,
        pad_y_frac=args.pad_y_frac,
        crop_w=args.crop_w,
        crop_h=args.crop_h,
        include_other=args.include_other,
        max_per_role_event=args.max_per_role_event,
    )

    if n <= 0:
        raise SystemExit("No crops exported. Check image topic, annotations, target IDs, and min bbox height.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
