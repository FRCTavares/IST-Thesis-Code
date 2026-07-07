#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from tim_ui_discovery import discover_annotations, discover_bags
from tim_ui_drawing import (
    draw_dashed_model_box,
    draw_model_box,
    xywh_to_xyxy,
)
from typing import Any

import cv2
import numpy as np
import rosbag2_py
from cv_bridge import CvBridge
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from pydantic import BaseModel
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import uvicorn


ROOT = Path.cwd()
CACHE: dict[str, Any] = {}
JOB: dict[str, Any] = {
    "running": False,
    "log": "",
    "last_output_bag": "",
}


app = FastAPI(title="TIM-MARS Bag Annotation UI")


def bag_has_topic(bag: Path, topic_name: str) -> bool:
    try:
        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
            rosbag2_py.ConverterOptions(
                input_serialization_format="cdr",
                output_serialization_format="cdr",
            ),
        )
        return any(t.name == topic_name for t in reader.get_all_topics_and_types())
    except Exception:
        return False


def find_metadata_bags(base: Path) -> list[str]:
    return discover_bags(base)


def find_annotations(base: Path) -> list[str]:
    return discover_annotations(base)


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


def no_store_jpeg_response(data: bytes) -> Response:
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

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


def load_bag_to_cache(bag_path: str, ann_path: str | None):
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

    CACHE.clear()
    CACHE.update({
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
    })


def render_frame(idx: int, draw_detections: bool, draw_tracks: bool, draw_raw: bool, draw_tim: bool, only_ids: str):
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    images = CACHE["images"]
    idx = max(0, min(len(images) - 1, idx))
    t, img = images[idx]

    first_t = images[0][0]
    t_rel = (t - first_t) / 1e9

    frame = img.copy()
    detections = nearest_by_time(CACHE["detections"], t) or []
    tracks = nearest_by_time(CACHE["tracks"], t) or []
    raw = nearest_by_time(CACHE["raw"], t)
    tim = nearest_by_time(CACHE["tim"], t)
    ref_id = ref_id_at(t_rel, CACHE["annotations"])

    only = set()
    if only_ids.strip():
        only = {int(x.strip()) for x in only_ids.split(",") if x.strip()}

    if draw_detections:
        for det in detections:
            label = f"DET {det['score']:.2f}" if det["score"] > 0 else "DET"
            draw_model_box(frame, det["box"], label, (0, 165, 255), 1)

    if draw_tracks or only or ref_id is not None:
        for tid, box in tracks:
            if only and tid not in only:
                continue
            if not draw_tracks and not only and ref_id is not None and tid != ref_id:
                continue

            colour = (220, 220, 160)
            label = f"T{tid}"

            if ref_id is not None and tid == ref_id:
                colour = (0, 255, 255)
                label = f"REF id={tid}"

            draw_model_box(frame, box, label, colour, 1)

    if draw_raw and raw:
        draw_model_box(
            frame,
            raw["box"],
            f"RAW id={raw['id']} s={raw['score']:.2f}",
            (255, 120, 40),
            3,
        )

    if draw_tim and tim:
        draw_model_box(
            frame,
            tim["box"],
            f"TIM id={tim['id']} q={tim['quality']:.2f}",
            (80, 255, 80),
            4,
        )

    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 44), (0, 0, 0), -1)
    frame[:] = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

    header = f"frame {idx}/{len(images)-1}    t={t_rel:.2f}s"
    if ref_id is not None:
        header += f"    REF id={ref_id}"

    cv2.putText(
        frame,
        header,
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        (245, 245, 245),
        2,
        cv2.LINE_AA,
    )

    return frame


def _clean_frame_base(idx: int):
    images = CACHE["images"]
    idx = max(0, min(len(images) - 1, idx))

    t, img = images[idx]
    first_t = images[0][0]
    t_rel = (t - first_t) / 1e9

    tracks = nearest_by_time(CACHE["tracks"], t) or []
    raw = nearest_by_time(CACHE["raw"], t)
    tim = nearest_by_time(CACHE["tim"], t)
    ref_id = ref_id_at(t_rel, CACHE["annotations"])

    return img, tracks, raw, tim, ref_id


def _draw_clean_output(frame, tracks, target, ref_id, draw_reference: bool):
    """No text. Dashed white reference; green correct output; red wrong output."""
    if draw_reference and ref_id is not None:
        for tid, box in tracks:
            if int(tid) == int(ref_id):
                draw_dashed_model_box(frame, box, (245, 245, 245), thickness=3)
                break

    if target:
        if ref_id is not None and int(target.get("id", -1)) == int(ref_id):
            colour = (0, 210, 0)      # correct: green
        else:
            colour = (0, 0, 230)      # wrong: red

        draw_model_box(frame, target["box"], "", colour, 4)

    return frame


def render_frame_clean(idx: int, draw_raw: bool, draw_tim: bool, draw_reference: bool):
    """Single-panel clean renderer."""
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    target = raw if draw_raw else tim if draw_tim else None
    return _draw_clean_output(frame, tracks, target, ref_id, draw_reference)


def render_frame_clean_comparison(idx: int, draw_reference: bool):
    """Side-by-side paper renderer.

    Left panel: RAW selected target.
    Right panel: TIM-MARS selected target.
    No text is drawn in the video.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)

    left = img.copy()
    right = img.copy()

    left = _draw_clean_output(left, tracks, raw, ref_id, draw_reference)
    right = _draw_clean_output(right, tracks, tim, ref_id, draw_reference)

    separator = np.zeros((left.shape[0], 8, 3), dtype=left.dtype)
    return np.hstack([left, separator, right])


def render_frame_paper_overlay(idx: int, draw_reference: bool):
    """Single-panel paper renderer.

    Dashed white: annotated/reference target.
    Red: RAW selected target.
    Blue: TIM-MARS selected target.
    No text is drawn in the video.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    if draw_reference and ref_id is not None:
        for tid, box in tracks:
            if int(tid) == int(ref_id):
                draw_dashed_model_box(frame, box, (245, 245, 245), thickness=3)
                break

    if raw:
        draw_model_box(frame, raw["box"], "", (0, 0, 230), 4)

    if tim:
        draw_model_box(frame, tim["box"], "", (230, 80, 0), 4)

    return frame


def _paper_time_label(idx: int) -> str:
    images = CACHE.get("images", [])
    if not images:
        return f"frame {idx}"
    idx = max(0, min(len(images) - 1, int(idx)))
    t0 = images[0][0]
    t = images[idx][0]
    t_rel = float(t - t0) / 1e9
    return f"frame {idx} | t={t_rel:.2f}s"


def _reference_box_from_tracks(tracks, ref_id):
    if ref_id is None:
        return None
    for tid, box in tracks:
        if int(tid) == int(ref_id):
            return box
    return None


def _draw_paper_status_label(frame, text: str) -> None:
    h, w = frame.shape[:2]
    pad = max(8, int(round(w * 0.012)))
    font_scale = max(0.55, min(1.0, w / 900.0))
    thickness = max(1, int(round(w / 450.0)))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    x1, y1 = pad, pad
    x2 = min(w - 1, x1 + tw + 2 * pad)
    y2 = min(h - 1, y1 + th + 2 * pad)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (15, 15, 15), -1)
    cv2.putText(
        frame,
        text,
        (x1 + pad, y2 - pad),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (245, 245, 245),
        thickness,
        cv2.LINE_AA,
    )


def _draw_paper_panel_frame(
    idx: int,
    mode: str,
    draw_reference: bool = True,
    label_mode: str = "time",
):
    """Draw one paper panel with no text.

    RAW row:
      - blue box for RAW selected-target output when not wrong;
      - red box when RAW output is wrong.

    TIM row:
      - green box for correct TIM-MARS output;
      - red box only if TIM-MARS publishes a wrong target;
      - no box when TIM-MARS suppresses output.

    The dashed white manual/reference box is drawn last, but thinner when it
    overlaps the output box so the output colour remains visible.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    ref_box = _reference_box_from_tracks(tracks, ref_id)
    target = raw if mode == "raw" else tim

    target_is_correct = (
        target is not None
        and ref_id is not None
        and int(target.get("id", -1)) == int(ref_id)
    )

    if target:
        if mode == "raw":
            # RAW is always drawn. Red means wrong; blue means normal/correct raw output.
            colour = (0, 0, 230) if not target_is_correct else (230, 110, 0)
            draw_model_box(frame, target["box"], "", colour, 4)
        else:
            # TIM is drawn only when it publishes. Green means correct; red means wrong.
            colour = (0, 210, 0) if target_is_correct else (0, 0, 230)
            draw_model_box(frame, target["box"], "", colour, 4)

    if draw_reference and ref_box is not None:
        # If reference and output overlap, use a thinner dashed reference so the
        # coloured output box remains visible.
        ref_thickness = 2 if target is not None else 3
        draw_dashed_model_box(frame, ref_box, (245, 245, 245), thickness=ref_thickness)

    boxes = []
    if ref_box is not None:
        boxes.append(ref_box)
    if target:
        boxes.append(target["box"])

    # For paper contact sheets, crop only around the relevant selected-target
    # evidence: manual reference plus RAW/TIM output. Including every tracker
    # box makes dense-group scenes too wide and prevents useful cropping.
    return frame, boxes, ""


def _draw_paper_overlay_frame(idx: int, draw_reference: bool = True, label_mode: str = "time"):
    """Backward-compatible single-panel overlay renderer."""
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    img, tracks, raw, tim, ref_id = _clean_frame_base(idx)
    frame = img.copy()

    ref_box = _reference_box_from_tracks(tracks, ref_id)

    if raw:
        draw_model_box(frame, raw["box"], "", (0, 0, 230), 4)

    if tim:
        draw_model_box(frame, tim["box"], "", (0, 210, 0), 4)

    if draw_reference and ref_box is not None:
        draw_dashed_model_box(frame, ref_box, (245, 245, 245), thickness=3)

    label = _paper_time_label(idx) if label_mode == "time" else f"frame {idx}"
    _draw_paper_status_label(frame, label)

    boxes = []
    if ref_box is not None:
        boxes.append(ref_box)
    if raw:
        boxes.append(raw["box"])
    if tim:
        boxes.append(tim["box"])
    for _, box in tracks:
        boxes.append(box)

    return frame, boxes


def _crop_to_model_boxes(frame, boxes, pad_px: int):
    if not boxes:
        return frame

    h, w = frame.shape[:2]
    xs = []
    ys = []

    for box in boxes:
        try:
            x1, y1, x2, y2 = model_box_to_image_box(box, frame.shape)
        except Exception:
            continue
        xs.extend([x1, x2])
        ys.extend([y1, y2])

    if not xs or not ys:
        return frame

    x1 = max(0, int(min(xs) - pad_px))
    y1 = max(0, int(min(ys) - pad_px))
    x2 = min(w, int(max(xs) + pad_px))
    y2 = min(h, int(max(ys) + pad_px))

    if x2 <= x1 or y2 <= y1:
        return frame

    return frame[y1:y2, x1:x2].copy()


def _shared_crop_rect(all_boxes, image_shape, pad_px: int, aspect: float = 1.55):
    """Compute one shared balanced crop rectangle.

    The crop is shared by all panels. It is centred on the union of the
    reference/output boxes and expanded to a fixed aspect ratio. This avoids
    per-panel crop changes while preventing dense scenes from keeping the
    whole field.
    """
    h, w = image_shape[:2]
    xs = []
    ys = []

    for box in all_boxes:
        try:
            x1, y1, x2, y2 = model_box_to_image_box(box, image_shape)
        except Exception:
            continue
        xs.extend([x1, x2])
        ys.extend([y1, y2])

    if not xs or not ys:
        return (0, 0, w, h)

    raw_x1 = max(0, int(min(xs)))
    raw_y1 = max(0, int(min(ys)))
    raw_x2 = min(w, int(max(xs)))
    raw_y2 = min(h, int(max(ys)))

    if raw_x2 <= raw_x1 or raw_y2 <= raw_y1:
        return (0, 0, w, h)

    cx = (raw_x1 + raw_x2) / 2.0
    cy = (raw_y1 + raw_y2) / 2.0

    box_w = raw_x2 - raw_x1
    box_h = raw_y2 - raw_y1

    # Balanced context: expand both dimensions from the object union, instead
    # of letting one axis dominate. This is the "crop horizontally and
    # vertically together" behaviour needed for paper figures.
    target_w = max(box_w + 2 * pad_px, int(round((box_h + 2 * pad_px) * aspect)))
    target_h = max(box_h + 2 * pad_px, int(round(target_w / aspect)))

    # Do not let the crop become the full court unless unavoidable.
    target_w = min(target_w, int(round(w * 0.72)))
    target_h = min(target_h, int(round(h * 0.72)))

    # Re-enforce aspect after clipping requested dimensions.
    if target_w / max(1, target_h) > aspect:
        target_w = int(round(target_h * aspect))
    else:
        target_h = int(round(target_w / aspect))

    x1 = int(round(cx - target_w / 2))
    x2 = int(round(cx + target_w / 2))
    y1 = int(round(cy - target_h / 2))
    y2 = int(round(cy + target_h / 2))

    # Shift inside image while preserving crop size when possible.
    if x1 < 0:
        x2 -= x1
        x1 = 0
    if y1 < 0:
        y2 -= y1
        y1 = 0
    if x2 > w:
        shift = x2 - w
        x1 -= shift
        x2 = w
    if y2 > h:
        shift = y2 - h
        y1 -= shift
        y2 = h

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return (0, 0, w, h)

    return (x1, y1, x2, y2)


def _apply_crop_rect(frame, rect):
    x1, y1, x2, y2 = rect
    return frame[y1:y2, x1:x2].copy()




def _trim_black_letterbox(frame, threshold: int = 12):
    """Remove black letterbox bands from top/bottom after crop."""
    if frame.size == 0:
        return frame

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    row_mean = gray.mean(axis=1)
    valid = np.where(row_mean > threshold)[0]

    if len(valid) == 0:
        return frame

    y1 = int(valid[0])
    y2 = int(valid[-1]) + 1

    if y2 <= y1:
        return frame

    return frame[y1:y2, :].copy()



def _add_paper_caption_band(panel, text: str):
    """No-op for final paper figures: keep panels image-only."""
    return panel



def _fit_panel_to_size(frame, panel_width: int, panel_height: int):
    """Fit image into a fixed panel without distortion.

    This prevents the paper contact sheet from becoming vertically stretched.
    """
    h, w = frame.shape[:2]
    panel_width = max(120, int(panel_width))
    panel_height = max(80, int(panel_height))

    if w <= 0 or h <= 0:
        return np.full((panel_height, panel_width, 3), 255, dtype=np.uint8)

    scale = min(panel_width / float(w), panel_height / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    out = np.full((panel_height, panel_width, 3), 255, dtype=np.uint8)
    x0 = (panel_width - new_w) // 2
    y0 = (panel_height - new_h) // 2
    out[y0:y0 + new_h, x0:x0 + new_w] = resized
    return out



def _resize_panel(frame, panel_width: int):
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return frame
    panel_width = max(120, int(panel_width))
    scale = panel_width / float(w)
    panel_height = max(1, int(round(h * scale)))
    return cv2.resize(frame, (panel_width, panel_height), interpolation=cv2.INTER_AREA)


def _pad_panel_to_size(panel, width: int, height: int):
    h, w = panel.shape[:2]
    out = np.full((height, width, 3), 255, dtype=np.uint8)
    out[:h, :w] = panel[:min(h, height), :min(w, width)]
    return out


def render_paper_contact_sheet(
    frame_indices,
    out_path: str,
    cols: int = 4,
    crop: bool = True,
    crop_pad: int = 80,
    panel_width: int = 520,
    draw_reference: bool = True,
    label_mode: str = "time",
):
    """Render a paper contact sheet as two rows.

    Top row: RAW selected-target output.
    Bottom row: TIM-MARS selected-target output.
    Columns correspond to the same frame indices, so each column is a direct
    RAW-vs-TIM comparison at one moment.

    A single shared crop rectangle is computed across all selected frames so
    every panel has identical dimensions and spatial context.
    """
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    images = CACHE.get("images", [])
    if not images:
        raise RuntimeError("No images loaded.")

    clean_indices = []
    for item in frame_indices:
        try:
            idx = int(str(item).strip())
        except Exception:
            continue
        clean_indices.append(max(0, min(len(images) - 1, idx)))

    if not clean_indices:
        raise RuntimeError("No valid frame indices were provided.")

    cols = max(1, int(cols))
    if cols < len(clean_indices):
        cols = len(clean_indices)

    # First render all panels and collect all boxes for one shared crop.
    rendered = {
        "raw": [],
        "tim": [],
    }
    all_boxes = []

    for mode in ("raw", "tim"):
        for idx in clean_indices:
            frame, boxes, label = _draw_paper_panel_frame(
                idx,
                mode=mode,
                draw_reference=draw_reference,
                label_mode=label_mode,
            )
            rendered[mode].append((frame, boxes, label))
            all_boxes.extend(boxes)

    shared_rect = None
    if crop:
        # Use the first rendered frame shape. All frames are from the same image stream.
        first_frame = rendered["raw"][0][0]
        shared_rect = _shared_crop_rect(all_boxes, first_frame.shape, int(crop_pad))

    rows = []
    for mode in ("raw", "tim"):
        panels = []
        for frame, _boxes, label in rendered[mode]:
            if crop and shared_rect is not None:
                frame = _apply_crop_rect(frame, shared_rect)
            frame = _trim_black_letterbox(frame)
            panel = _resize_panel(frame, int(panel_width))
            panel = _add_paper_caption_band(panel, label)
            panels.append(panel)

        # Enforce identical cell size inside the row.
        cell_w = max(p.shape[1] for p in panels)
        cell_h = max(p.shape[0] for p in panels)
        padded = [_pad_panel_to_size(p, cell_w, cell_h) for p in panels]

        gap = 10
        sep = np.full((cell_h, gap, 3), 255, dtype=np.uint8)
        pieces = []
        for c, panel in enumerate(padded):
            if c > 0:
                pieces.append(sep)
            pieces.append(panel)
        rows.append(np.hstack(pieces))

    # Enforce both rows to the same width.
    max_row_w = max(row.shape[1] for row in rows)
    fixed_rows = []
    for row in rows:
        if row.shape[1] < max_row_w:
            pad = np.full((row.shape[0], max_row_w - row.shape[1], 3), 255, dtype=np.uint8)
            row = np.hstack([row, pad])
        fixed_rows.append(row)

    gap = 14
    vsep = np.full((gap, max_row_w, 3), 255, dtype=np.uint8)
    sheet = np.vstack([fixed_rows[0], vsep, fixed_rows[1]])

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ok = cv2.imwrite(str(out), sheet)
    if not ok:
        raise RuntimeError(f"Failed to write contact sheet: {out}")

    return str(out)


class ReplayRequest(BaseModel):
    bag: str
    target_id: int = 1
    tracker: str = "bytetrack"
    tim_mode: str = "mars"
    rate: float = 1.0
    tim_preset: str = "legacy"

    absence_recovery_enabled: bool = False
    absence_after_missed_frames: int = 6
    absence_min_total: float = 0.45
    absence_min_distance: float = 0.25
    absence_min_scale: float = 0.35
    absence_min_similarity: float = 0.65
    absence_appearance_margin: float = 0.20
    absence_confirm_frames: int = 3

    rank_aware_reacquisition_enabled: bool = True
    rank_aware_confirm_frames: int = 1
    rank_aware_lost_min_total: float = 0.40
    rank_aware_lost_min_geom: float = 0.10
    rank_aware_lost_min_app: float = 0.05
    rank_aware_lost_app_margin: float = 0.03

    appearance_update_cooldown_frames: int = 0


class ExportRequest(BaseModel):
    out: str = "reports/visual_audit/tim_audit_export.mp4"
    draw_detections: bool = False
    draw_tracks: bool = True
    draw_raw: bool = True
    draw_tim: bool = True
    only_ids: str = ""
    fps: float = 20.0
    clean: bool = False
    draw_reference: bool = True
    comparison: bool = False
    paper_overlay: bool = False


class ContactSheetRequest(BaseModel):
    out: str = "figures/paper_contact_sheet.jpg"
    frames: str = ""
    cols: int = 3
    crop: bool = True
    crop_pad: int = 80
    panel_width: int = 520
    draw_reference: bool = True
    label_mode: str = "time"


def run_replay_job(req: ReplayRequest):
    global JOB

    env = os.environ.copy()
    env.update({
        "TIM_STARTUP_SELECTED_ONLY": "true",

        # Keep UI-generated bags separate from official eval_matrix outputs.
        "TIM_REPLAY_OUT_ROOT": str(ROOT / "bags/replay/ui_replays"),
        "TIM_REPLAY_LOG_ROOT": str(ROOT / "ros2_ws/log/ui_replays"),
        "TIM_REPLAY_REPORT_ROOT": str(ROOT / "reports/ui_replays"),

        "MARS_ABSENCE_RECOVERY_ENABLED": str(req.absence_recovery_enabled).lower(),
        "MARS_ABSENCE_AFTER_MISSED_FRAMES": str(req.absence_after_missed_frames),
        "MARS_ABSENCE_MIN_TOTAL": str(req.absence_min_total),
        "MARS_ABSENCE_MIN_DISTANCE": str(req.absence_min_distance),
        "MARS_ABSENCE_MIN_SCALE": str(req.absence_min_scale),
        "MARS_ABSENCE_MIN_SIMILARITY": str(req.absence_min_similarity),
        "MARS_ABSENCE_APPEARANCE_MARGIN": str(req.absence_appearance_margin),
        "MARS_ABSENCE_CONFIRM_FRAMES": str(req.absence_confirm_frames),

        "MARS_RANK_AWARE_REACQUISITION_ENABLED": str(req.rank_aware_reacquisition_enabled).lower(),
        "MARS_RANK_AWARE_CONFIRM_FRAMES": str(req.rank_aware_confirm_frames),
        "MARS_RANK_AWARE_LOST_MIN_TOTAL": str(req.rank_aware_lost_min_total),
        "MARS_RANK_AWARE_LOST_MIN_GEOM": str(req.rank_aware_lost_min_geom),
        "MARS_RANK_AWARE_LOST_MIN_APP": str(req.rank_aware_lost_min_app),
        "MARS_RANK_AWARE_LOST_APP_MARGIN": str(req.rank_aware_lost_app_margin),

        "MARS_APPEARANCE_UPDATE_COOLDOWN_FRAMES": str(req.appearance_update_cooldown_frames),
        "MARS_TIM_PRESET": str(req.tim_preset),
    })

    cmd = [
        "./tools/experiments/run_one_clean_tim_replay.sh",
        req.bag,
        str(req.target_id),
        req.tracker,
        req.tim_mode,
        str(req.rate),
        "90",
    ]

    JOB["running"] = True
    JOB["log"] = "Running:\n" + " ".join(cmd) + "\n\n"
    JOB["last_output_bag"] = ""

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        JOB["log"] += proc.stdout

        for line in proc.stdout.splitlines():
            if line.startswith("[ok] eval bag:"):
                JOB["last_output_bag"] = line.split(":", 1)[1].strip()

        JOB["log"] += f"\n\nExit code: {proc.returncode}\n"

    except Exception as e:
        JOB["log"] += f"\n[error] {e}\n"

    finally:
        JOB["running"] = False


@app.get("/api/list")
def api_list():
    bags = list(find_metadata_bags(ROOT))
    favs = []

    # Explicitly include UI aliases. The generic metadata scan can miss
    # symlinked bag directories, but these aliases are intentional UI shortcuts
    # for annotation and paper-video bags.
    existing = set(bags)
    alias_root = ROOT / "bags" / "annotation_inputs"
    aliases = []
    aliases.extend(sorted(alias_root.glob("ANNOTATE__*")))
    aliases.extend(sorted(alias_root.glob("VIDEO__*")))
    aliases.extend(sorted(alias_root.glob("VIEW__*")))

    for alias in aliases:
        resolved = alias.resolve()
        if not (resolved / "metadata.yaml").exists():
            continue

        rel = str(alias.relative_to(ROOT))
        if rel not in existing:
            bags.insert(0, rel)
            existing.add(rel)

    return {
        "bags": bags,
        "favourites": favs,
        "annotations": find_annotations(ROOT),
    }


@app.post("/api/load")
def api_load(payload: dict[str, str]):
    try:
        bag = str(payload.get("bag", "")).strip()
        ann = str(payload.get("ann", "")).strip() or None

        load_bag_to_cache(bag, ann)

        images = CACHE.get("images", [])
        duration_s = 0.0
        if len(images) >= 2:
            dt = float(images[-1][0] - images[0][0])
            duration_s = dt / 1e9 if dt > 1e6 else dt

        return {
            "ok": True,
            "frames": len(images),
            "duration_s": duration_s,
            "bag": CACHE.get("bag", bag),
            "ann": CACHE.get("ann", ann or ""),
            "topic_counts": {
                "images": len(CACHE.get("images", [])),
                "detections": len(CACHE.get("detections", [])),
                "tracks": len(CACHE.get("tracks", [])),
                "raw": len(CACHE.get("raw", [])),
                "tim": len(CACHE.get("tim", [])),
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/frame.jpg")
def frame_jpg(
    idx: int = 0,
    draw_detections: int = 0,
    draw_tracks: int = 1,
    draw_raw: int = 1,
    draw_tim: int = 1,
    only_ids: str = "",
    clean: int = 0,
    draw_reference: int = 1,
    comparison: int = 0,
    paper_overlay: int = 0,
):
    from fastapi import Response
    import cv2

    if bool(clean) and bool(paper_overlay):
        img = render_frame_paper_overlay(idx=idx, draw_reference=bool(draw_reference))
    elif bool(clean) and bool(comparison):
        img = render_frame_clean_comparison(idx=idx, draw_reference=bool(draw_reference))
    elif bool(clean):
        img = render_frame_clean(
            idx=idx,
            draw_raw=bool(draw_raw),
            draw_tim=bool(draw_tim),
            draw_reference=bool(draw_reference),
        )
    else:
        img = render_frame(
            idx=idx,
            draw_detections=bool(draw_detections),
            draw_tracks=bool(draw_tracks),
            draw_raw=bool(draw_raw),
            draw_tim=bool(draw_tim),
            only_ids=only_ids,
        )

    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        return Response(content=b"", media_type="image/jpeg", status_code=500)

    return no_store_jpeg_response(buf.tobytes())



@app.post("/api/export_contact_sheet")
def api_export_contact_sheet(payload: dict):
    try:
        req = ContactSheetRequest(**payload)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        out = Path(req.out)
        if not out.is_absolute():
            out = ROOT / out

        out = out.resolve()
        root = ROOT.resolve()
        try:
            out.relative_to(root)
        except ValueError:
            return {"ok": False, "error": f"Output must stay inside repository: {out}"}

        if out.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            return {"ok": False, "error": "Output must be .jpg, .jpeg, or .png"}

        frames = [
            item.strip()
            for item in str(req.frames).replace(";", ",").split(",")
            if item.strip()
        ]

        result = render_paper_contact_sheet(
            frame_indices=frames,
            out_path=str(out),
            cols=req.cols,
            crop=req.crop,
            crop_pad=req.crop_pad,
            panel_width=req.panel_width,
            draw_reference=req.draw_reference,
            label_mode=req.label_mode,
        )

        rel = str(Path(result).resolve().relative_to(root))
        return {
            "ok": True,
            "path": rel,
            "download_url": "/api/download_image?path=" + rel,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/download_image")
def api_download_image(path: str):
    root = ROOT.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()

    try:
        p.relative_to(root)
    except ValueError:
        return JSONResponse({"ok": False, "error": "Path outside repository"}, status_code=400)

    if not p.exists():
        return JSONResponse({"ok": False, "error": f"File not found: {p}"}, status_code=404)

    suffix = p.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        return JSONResponse({"ok": False, "error": "Only image downloads are allowed"}, status_code=400)

    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    return FileResponse(str(p), media_type=media_type, filename=p.name)


@app.post("/api/export_mp4")
def api_export_mp4(payload: dict):
    try:
        req = ExportRequest(**payload)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        out = Path(req.out)
        if not out.is_absolute():
            out = ROOT / out

        # Keep exports inside the repository to avoid accidental writes elsewhere.
        out = out.resolve()
        root = ROOT.resolve()
        try:
            out.relative_to(root)
        except ValueError:
            return {"ok": False, "error": f"Output must stay inside repository: {out}"}

        result = export_mp4(
            out_path=str(out),
            draw_detections=req.draw_detections,
            draw_tracks=req.draw_tracks,
            draw_raw=req.draw_raw,
            draw_tim=req.draw_tim,
            only_ids=req.only_ids,
            fps=req.fps,
            clean=req.clean,
            draw_reference=req.draw_reference,
            comparison=req.comparison,
            paper_overlay=req.paper_overlay,
        )

        rel = str(Path(result).resolve().relative_to(root))
        return {
            "ok": True,
            "path": rel,
            "download_url": "/api/download_video?path=" + rel,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/download_video")
def api_download_video(path: str):
    root = ROOT.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()

    try:
        p.relative_to(root)
    except ValueError:
        return JSONResponse({"ok": False, "error": "Path outside repository"}, status_code=400)

    if not p.exists():
        return JSONResponse({"ok": False, "error": f"File not found: {p}"}, status_code=404)

    if p.suffix.lower() != ".mp4":
        return JSONResponse({"ok": False, "error": "Only .mp4 downloads are allowed"}, status_code=400)

    return FileResponse(
        str(p),
        media_type="video/mp4",
        filename=p.name,
    )


@app.post("/api/replay")
def api_replay(payload: dict):
    import threading

    try:
        req = ReplayRequest(**payload)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if JOB.get("running"):
        return {"ok": False, "error": "Replay job already running"}

    th = threading.Thread(target=run_replay_job, args=(req,), daemon=True)
    th.start()

    return {"ok": True}


@app.get("/api/job")
def api_job():
    return JOB


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
