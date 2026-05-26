#!/usr/bin/env python3
"""
Offline descriptor audit for TIM-V2E.

This evaluates whether a lightweight crop descriptor separates the annotated
selected target from distractors during exact annotated intervals.

Important:
- Offline only.
- Does not modify live TIM.
- Requires exact bag/annotation pairing.
- Uses /camera/dashboard and /tracks by default.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


BBox = Tuple[float, float, float, float]


@dataclass
class AnnotationInterval:
    bag_name: str
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int
    distractor_track_ids: List[int]
    event_type: str
    notes: str


@dataclass
class AliasInterval:
    start_s: float
    end_s: float
    primary_correct_id: int
    alias_correct_ids: List[int]
    reason: str


@dataclass
class TrackRow:
    t: float
    frame_id: int
    track_id: int
    bbox: BBox
    score: float


@dataclass
class ImageRow:
    t: float
    image_bgr: np.ndarray


@dataclass
class DescriptorRow:
    t: float
    frame_id: int
    track_id: int
    role: str
    event_type: str
    descriptor_valid: bool
    skip_reason: str
    similarity_to_memory: float
    bbox_h: float


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except Exception:
        return default


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_id_list(value: Any) -> List[int]:
    text = str(value or "").strip()
    if not text:
        return []
    out: List[int] = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        tid = as_int(part, 0)
        if tid > 0:
            out.append(tid)
    return out


def load_annotations(path: Path) -> List[AnnotationInterval]:
    rows: List[AnnotationInterval] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "bag_name",
            "start_s",
            "end_s",
            "target_label",
            "target_visible",
            "correct_target_track_id",
            "distractor_track_ids",
            "event_type",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Annotation CSV missing columns: {sorted(missing)}")

        for r in reader:
            rows.append(
                AnnotationInterval(
                    bag_name=str(r["bag_name"]).strip(),
                    start_s=as_float(r["start_s"]),
                    end_s=as_float(r["end_s"]),
                    target_label=str(r["target_label"]).strip(),
                    target_visible=as_bool(r["target_visible"]),
                    correct_target_track_id=as_int(r["correct_target_track_id"], 0),
                    distractor_track_ids=parse_id_list(r["distractor_track_ids"]),
                    event_type=str(r["event_type"]).strip(),
                    notes=str(r["notes"]).strip(),
                )
            )
    rows.sort(key=lambda x: x.start_s)
    return rows


def load_aliases(path: Optional[Path]) -> List[AliasInterval]:
    if path is None or not path.exists():
        return []

    rows: List[AliasInterval] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"start_s", "end_s", "primary_correct_id", "alias_correct_ids", "reason"}
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
                    reason=str(r["reason"]).strip(),
                )
            )
    rows.sort(key=lambda x: x.start_s)
    return rows


def alias_ids_at(t: float, aliases: List[AliasInterval], correct_id: int) -> set[int]:
    ids = {correct_id} if correct_id > 0 else set()
    for a in aliases:
        if a.start_s <= t < a.end_s and a.primary_correct_id == correct_id:
            ids.update(a.alias_correct_ids)
    return ids


def annotation_for_time(t: float, annotations: List[AnnotationInterval]) -> Optional[AnnotationInterval]:
    for ann in annotations:
        if ann.start_s <= t < ann.end_s:
            return ann
    return None


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
        # Avoid cv2 dependency just for channel swap.
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
    # Common thesis Track2D shape: normalised cx/cy/w/h.
    cx = safe_get(track, ["cx", "center_x", "bbox_cx"], None)
    cy = safe_get(track, ["cy", "center_y", "bbox_cy"], None)
    bw = safe_get(track, ["w", "width", "bbox_w"], None)
    bh = safe_get(track, ["h", "height", "bbox_h"], None)

    if cx is not None and cy is not None and bw is not None and bh is not None:
        cx_f = as_float(cx)
        cy_f = as_float(cy)
        bw_f = as_float(bw)
        bh_f = as_float(bh)

        # If normalised, map to pixels.
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

    # Some messages may expose bbox object.
    if hasattr(track, "bbox"):
        b = getattr(track, "bbox")
        out = get_track_bbox(b, img_w, img_h)
        if out is not None:
            return out

    return None


def read_bag_images_and_tracks(
    bag_path: Path,
    image_topic: str,
    tracks_topic: str,
) -> Tuple[List[ImageRow], List[List[TrackRow]]]:
    (
        SequentialReader,
        StorageOptions,
        ConverterOptions,
        deserialize_message,
        get_message,
    ) = import_rosbag_tools()

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag_path), storage_id=detect_storage_id(bag_path)),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {
        topic_metadata.name: topic_metadata.type
        for topic_metadata in reader.get_all_topics_and_types()
    }

    missing = [t for t in [image_topic, tracks_topic] if t not in topic_types]
    if missing:
        raise SystemExit(
            f"Bag missing required topic(s): {missing}\n"
            f"Available topics: {sorted(topic_types.keys())}"
        )

    image_type = get_message(topic_types[image_topic])
    tracks_type = get_message(topic_types[tracks_topic])

    images: List[ImageRow] = []
    track_msgs: List[List[TrackRow]] = []
    first_t_ns: Optional[int] = None
    latest_img_shape: Optional[Tuple[int, int]] = None

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
                print(f"[warn] skipped image at t={t_s:.3f}: {exc}")
                continue
            latest_img_shape = (int(img.shape[1]), int(img.shape[0]))
            images.append(ImageRow(t=t_s, image_bgr=img))

        elif topic == tracks_topic:
            msg = deserialize_message(data, tracks_type)

            # Prefer latest image shape. Fallback to 640x640.
            if latest_img_shape is None:
                img_w, img_h = 640, 640
            else:
                img_w, img_h = latest_img_shape

            tracks = list(getattr(msg, "tracks", []))
            frame_id = as_int(getattr(msg, "frame_id", 0), 0)
            rows: List[TrackRow] = []
            for tr in tracks:
                tid = get_track_id(tr)
                bbox = get_track_bbox(tr, img_w=img_w, img_h=img_h)
                if tid <= 0 or bbox is None:
                    continue
                rows.append(
                    TrackRow(
                        t=t_s,
                        frame_id=frame_id,
                        track_id=tid,
                        bbox=bbox,
                        score=get_track_score(tr),
                    )
                )
            if rows:
                track_msgs.append(rows)

    return images, track_msgs


def nearest_image(images: List[ImageRow], t: float, max_dt: float) -> Tuple[Optional[np.ndarray], float]:
    if not images:
        return None, float("inf")

    # Linear scan is fine for current bag sizes. Keep simple.
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
) -> Tuple[int, int, int, int]:
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


def compute_descriptor(
    image_bgr: np.ndarray,
    bbox: BBox,
    descriptor: str,
    min_bbox_h: float,
    pad_x_frac: float,
    pad_y_frac: float,
) -> Tuple[Optional[np.ndarray], str, float]:
    try:
        import cv2
    except Exception as exc:
        raise RuntimeError("cv2 is required for descriptor extraction") from exc

    img_h, img_w = image_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    bbox_h = float(y2 - y1)

    if bbox_h < min_bbox_h:
        return None, "tiny_bbox", bbox_h

    xi1, yi1, xi2, yi2 = expand_and_clip_bbox(bbox, img_w, img_h, pad_x_frac, pad_y_frac)
    if xi2 <= xi1 or yi2 <= yi1:
        return None, "empty_crop", bbox_h

    crop = image_bgr[yi1:yi2, xi1:xi2]
    if crop.size == 0:
        return None, "empty_crop", bbox_h

    crop = cv2.resize(crop, (64, 128), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    upper = hsv[:70, :, :]
    lower = hsv[58:, :, :]

    # 16D hue-only baseline: 8 hue bins upper + 8 hue bins lower.
    hist_u, _ = np.histogram(upper[:, :, 0], bins=8, range=(0, 180), density=False)
    hist_l, _ = np.histogram(lower[:, :, 0], bins=8, range=(0, 180), density=False)
    hsv16 = np.concatenate([hist_u.astype(np.float32), hist_l.astype(np.float32)])

    if descriptor == "hsv16":
        feat = hsv16

    elif descriptor == "hsv_grad16":
        # 8D colour + 8D coarse texture/shape.
        # Colour: 4 hue bins upper + 4 hue bins lower.
        hist_u4, _ = np.histogram(upper[:, :, 0], bins=4, range=(0, 180), density=False)
        hist_l4, _ = np.histogram(lower[:, :, 0], bins=4, range=(0, 180), density=False)
        colour8 = np.concatenate([hist_u4.astype(np.float32), hist_l4.astype(np.float32)])

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        ang = cv2.phase(gx, gy, angleInDegrees=True)

        # Unsigned orientation: [0, 180).
        ang = np.mod(ang, 180.0)
        grad8, _ = np.histogram(
            ang,
            bins=8,
            range=(0, 180),
            weights=mag,
            density=False,
        )

        # Normalise colour and gradient blocks separately, then concatenate.
        colour8 = colour8.astype(np.float32)
        grad8 = grad8.astype(np.float32)
        c_norm = float(np.linalg.norm(colour8))
        g_norm = float(np.linalg.norm(grad8))
        if c_norm > 1e-8:
            colour8 /= c_norm
        if g_norm > 1e-8:
            grad8 /= g_norm
        feat = np.concatenate([colour8, grad8]).astype(np.float32)

    else:
        return None, f"unknown_descriptor_{descriptor}", bbox_h

    norm = float(np.linalg.norm(feat))
    if norm <= 1e-8:
        return None, "zero_descriptor", bbox_h
    feat = feat.astype(np.float32) / norm
    return feat, "", bbox_h


def cosine(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    if a is None or b is None:
        return float("nan")
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return float("nan")
    return float(np.dot(a, b) / denom)


def mean_descriptor(descs: List[np.ndarray]) -> Optional[np.ndarray]:
    if not descs:
        return None
    m = np.mean(np.stack(descs, axis=0), axis=0)
    norm = float(np.linalg.norm(m))
    if norm <= 1e-8:
        return None
    return m / norm


def percentile(values: List[float], q: float) -> float:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return float("nan")
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    frac = pos - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def fmt(x: float) -> str:
    if not math.isfinite(x):
        return "nan"
    return f"{x:.3f}"


def build_memory_descriptor(
    images: List[ImageRow],
    track_msgs: List[List[TrackRow]],
    annotations: List[AnnotationInterval],
    aliases: List[AliasInterval],
    template_event_types: set[str],
    descriptor: str,
    max_image_dt: float,
    min_bbox_h: float,
    pad_x_frac: float,
    pad_y_frac: float,
) -> Tuple[Optional[np.ndarray], int]:
    descs: List[np.ndarray] = []

    for rows in track_msgs:
        t = rows[0].t
        ann = annotation_for_time(t, annotations)
        if ann is None:
            continue
        if not ann.target_visible or ann.correct_target_track_id <= 0:
            continue
        if ann.event_type not in template_event_types:
            continue

        correct_ids = alias_ids_at(t, aliases, ann.correct_target_track_id)
        image, _dt = nearest_image(images, t, max_dt=max_image_dt)
        if image is None:
            continue

        for tr in rows:
            if tr.track_id not in correct_ids:
                continue
            feat, reason, _bbox_h = compute_descriptor(
                image,
                tr.bbox,
                descriptor=descriptor,
                min_bbox_h=min_bbox_h,
                pad_x_frac=pad_x_frac,
                pad_y_frac=pad_y_frac,
            )
            if feat is not None:
                descs.append(feat)

    return mean_descriptor(descs), len(descs)


def evaluate_descriptors(
    images: List[ImageRow],
    track_msgs: List[List[TrackRow]],
    annotations: List[AnnotationInterval],
    aliases: List[AliasInterval],
    memory: Optional[np.ndarray],
    descriptor: str,
    max_image_dt: float,
    min_bbox_h: float,
    pad_x_frac: float,
    pad_y_frac: float,
) -> List[DescriptorRow]:
    out: List[DescriptorRow] = []

    for rows in track_msgs:
        t = rows[0].t
        ann = annotation_for_time(t, annotations)
        if ann is None:
            continue
        if ann.target_label == "NO_TARGET_SELECTED":
            continue

        correct_ids = alias_ids_at(t, aliases, ann.correct_target_track_id)
        distractor_ids = set(ann.distractor_track_ids)

        image, image_dt = nearest_image(images, t, max_dt=max_image_dt)
        for tr in rows:
            if tr.track_id in correct_ids:
                role = "correct"
            elif tr.track_id in distractor_ids:
                role = "distractor"
            else:
                role = "other"

            if image is None:
                out.append(
                    DescriptorRow(
                        t=t,
                        frame_id=tr.frame_id,
                        track_id=tr.track_id,
                        role=role,
                        event_type=ann.event_type,
                        descriptor_valid=False,
                        skip_reason=f"no_near_image_dt_{image_dt:.3f}",
                        similarity_to_memory=float("nan"),
                        bbox_h=float(tr.bbox[3] - tr.bbox[1]),
                    )
                )
                continue

            feat, reason, bbox_h = compute_descriptor(
                image,
                tr.bbox,
                descriptor=descriptor,
                min_bbox_h=min_bbox_h,
                pad_x_frac=pad_x_frac,
                pad_y_frac=pad_y_frac,
            )
            sim = cosine(memory, feat)

            out.append(
                DescriptorRow(
                    t=t,
                    frame_id=tr.frame_id,
                    track_id=tr.track_id,
                    role=role,
                    event_type=ann.event_type,
                    descriptor_valid=feat is not None and memory is not None and math.isfinite(sim),
                    skip_reason=reason,
                    similarity_to_memory=sim,
                    bbox_h=bbox_h,
                )
            )

    return out


def write_descriptor_rows(path: Path, rows: List[DescriptorRow]) -> None:
    with path.open("w", newline="") as f:
        fieldnames = [
            "t",
            "frame_id",
            "track_id",
            "role",
            "event_type",
            "descriptor_valid",
            "skip_reason",
            "similarity_to_memory",
            "bbox_h",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "t": f"{r.t:.6f}",
                    "frame_id": r.frame_id,
                    "track_id": r.track_id,
                    "role": r.role,
                    "event_type": r.event_type,
                    "descriptor_valid": str(r.descriptor_valid).lower(),
                    "skip_reason": r.skip_reason,
                    "similarity_to_memory": f"{r.similarity_to_memory:.6f}" if math.isfinite(r.similarity_to_memory) else "",
                    "bbox_h": f"{r.bbox_h:.3f}",
                }
            )


def summarise(rows: List[DescriptorRow], memory_count: int, descriptor: str) -> str:
    valid = [r for r in rows if r.descriptor_valid]
    correct = [r.similarity_to_memory for r in valid if r.role == "correct"]
    distractor = [r.similarity_to_memory for r in valid if r.role == "distractor"]
    other = [r.similarity_to_memory for r in valid if r.role == "other"]

    by_event: Dict[str, List[DescriptorRow]] = {}
    for r in valid:
        by_event.setdefault(r.event_type, []).append(r)

    lines: List[str] = []
    lines.append("# TIM-V2E descriptor audit")
    lines.append("")
    lines.append("## Descriptor")
    lines.append("")
    lines.append(f"- Descriptor: `{descriptor}`")
    lines.append("- Memory: mean descriptor from clean/correct visible intervals")
    lines.append(f"- Memory samples: {memory_count}")
    lines.append("")
    lines.append("## Global similarity")
    lines.append("")
    lines.append("| Role | N | Mean | P50 | P95 |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, vals in [
        ("correct", correct),
        ("distractor", distractor),
        ("other", other),
    ]:
        lines.append(
            f"| {name} | {len(vals)} | {fmt(statistics.mean(vals) if vals else float('nan'))} | "
            f"{fmt(percentile(vals, 0.50))} | {fmt(percentile(vals, 0.95))} |"
        )

    lines.append("")
    lines.append("## Event-level separation")
    lines.append("")
    lines.append("| Event | correct_N | distractor_N | correct_mean | distractor_mean | gap |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for event in sorted(by_event):
        ev = by_event[event]
        c = [r.similarity_to_memory for r in ev if r.role == "correct"]
        d = [r.similarity_to_memory for r in ev if r.role == "distractor"]
        c_mean = statistics.mean(c) if c else float("nan")
        d_mean = statistics.mean(d) if d else float("nan")
        gap = c_mean - d_mean if math.isfinite(c_mean) and math.isfinite(d_mean) else float("nan")
        lines.append(f"| {event} | {len(c)} | {len(d)} | {fmt(c_mean)} | {fmt(d_mean)} | {fmt(gap)} |")

    lines.append("")
    lines.append("## Interpretation rule")
    lines.append("")
    lines.append("Useful signal if correct similarity is consistently above distractor similarity during hard re-entry/crossing windows.")
    lines.append("Weak signal if event-level gaps are near zero or negative.")
    lines.append("")

    invalid = [r for r in rows if not r.descriptor_valid]
    if invalid:
        reason_counts: Dict[str, int] = {}
        for r in invalid:
            reason_counts[r.skip_reason or "invalid"] = reason_counts.get(r.skip_reason or "invalid", 0) + 1

        lines.append("## Invalid descriptor reasons")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|---|---:|")
        for reason, count in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--aliases", type=Path, default=None)
    p.add_argument("--all-scores-csv", type=Path, default=None, help="Accepted for run metadata; not required by descriptor audit yet.")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--descriptor", choices=["hsv16", "hsv_grad16"], default="hsv16")
    p.add_argument("--image-topic", default="/camera/dashboard")
    p.add_argument("--tracks-topic", default="/tracks")
    p.add_argument("--max-image-dt", type=float, default=0.08)
    p.add_argument("--min-bbox-h", type=float, default=24.0)
    p.add_argument("--pad-x-frac", type=float, default=0.10)
    p.add_argument("--pad-y-frac", type=float, default=0.05)
    p.add_argument(
        "--template-event-types",
        default="clean_tracking,correct_tracking",
        help="Comma-separated event_type values used to build selected-target memory.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    annotations = load_annotations(args.annotations)
    aliases = load_aliases(args.aliases)
    template_event_types = {x.strip() for x in args.template_event_types.split(",") if x.strip()}

    print(f"[info] bag={args.bag}")
    print(f"[info] annotations={args.annotations}")
    print(f"[info] aliases={args.aliases if args.aliases else 'none'}")
    print(f"[info] image_topic={args.image_topic} tracks_topic={args.tracks_topic}")

    images, track_msgs = read_bag_images_and_tracks(
        bag_path=args.bag,
        image_topic=args.image_topic,
        tracks_topic=args.tracks_topic,
    )

    print(f"[info] images={len(images)} track_msgs={len(track_msgs)}")

    memory, memory_count = build_memory_descriptor(
        images=images,
        track_msgs=track_msgs,
        annotations=annotations,
        aliases=aliases,
        template_event_types=template_event_types,
        descriptor=args.descriptor,
        max_image_dt=args.max_image_dt,
        min_bbox_h=args.min_bbox_h,
        pad_x_frac=args.pad_x_frac,
        pad_y_frac=args.pad_y_frac,
    )

    if memory is None:
        raise SystemExit(
            "No memory descriptor could be built. "
            "Check template event types, selected ID, image topic, bbox extraction, and min bbox height."
        )

    rows = evaluate_descriptors(
        images=images,
        track_msgs=track_msgs,
        annotations=annotations,
        aliases=aliases,
        memory=memory,
        descriptor=args.descriptor,
        max_image_dt=args.max_image_dt,
        min_bbox_h=args.min_bbox_h,
        pad_x_frac=args.pad_x_frac,
        pad_y_frac=args.pad_y_frac,
    )

    desc_csv = args.output_dir / "descriptor_scores.csv"
    summary_md = args.output_dir / "summary.md"

    write_descriptor_rows(desc_csv, rows)
    summary_md.write_text(summarise(rows, memory_count, args.descriptor), encoding="utf-8")

    print(f"[ok] wrote {desc_csv}")
    print(f"[ok] wrote {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
