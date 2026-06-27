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
from typing import Any

import cv2
import numpy as np
import rosbag2_py
from cv_bridge import CvBridge
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
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

FAV_PATH = Path("tools/visualization/.tim_audit_favourites.json")


def load_favourites() -> list[str]:
    try:
        if FAV_PATH.exists():
            data = json.loads(FAV_PATH.read_text())
            if isinstance(data, list):
                return [str(x) for x in data]
    except Exception:
        pass
    return []


def save_favourites(items: list[str]) -> None:
    FAV_PATH.parent.mkdir(parents=True, exist_ok=True)
    unique = sorted(dict.fromkeys(str(x) for x in items if str(x).strip()))
    FAV_PATH.write_text(json.dumps(unique, indent=2) + "\n")


app = FastAPI(title="TIM-MARS Simple Audit UI")


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
    roots = [
        base / "artifacts/bags/derived/ui_replays",
        base / "artifacts/bags/derived/eval_matrix",
        base / "artifacts/bags/derived/conservative_safety_eval",
        base / "artifacts/bags/live_camera",
        base / "artifacts/bags/datasets",
        base / "artifacts/bags/source_video",
    ]
    out = []
    for r in roots:
        if not r.exists():
            continue
        for m in r.rglob("metadata.yaml"):
            bag = m.parent
            if bag_has_topic(bag, "/camera/image_raw") or bag_has_topic(bag, "/camera/dashboard"):
                out.append(str(bag))
    return sorted(out)


def find_annotations(base: Path) -> list[str]:
    root = base / "docs/data/annotations"
    if not root.exists():
        return []
    return sorted(str(p) for p in root.rglob("*.csv"))


def xywh_to_xyxy(cx, cy, w, h):
    return (
        int(round(cx - w / 2)),
        int(round(cy - h / 2)),
        int(round(cx + w / 2)),
        int(round(cy + h / 2)),
    )


def model_box_to_image_box(box, img_shape, model_w=640.0, model_h=640.0):
    """Map detector/tracker/TIM boxes from square model space to image space.

    The perception stack uses 640x640 model coordinates. Camera frames in the
    audit UI can be 640x480. In that case the original image was letterboxed
    into the square model input, so y coordinates must be unpadded before
    drawing.
    """
    img_h, img_w = img_shape[:2]
    if img_w <= 0 or img_h <= 0:
        return box

    scale = min(model_w / float(img_w), model_h / float(img_h))
    if scale <= 0:
        return box

    resized_w = float(img_w) * scale
    resized_h = float(img_h) * scale
    pad_x = (model_w - resized_w) / 2.0
    pad_y = (model_h - resized_h) / 2.0

    x1, y1, x2, y2 = [float(v) for v in box]

    x1 = (x1 - pad_x) / scale
    x2 = (x2 - pad_x) / scale
    y1 = (y1 - pad_y) / scale
    y2 = (y2 - pad_y) / scale

    return (
        int(round(x1)),
        int(round(y1)),
        int(round(x2)),
        int(round(y2)),
    )


def draw_model_box(img, box, label, colour, thickness=2):
    draw_box(
        img,
        model_box_to_image_box(box, img.shape),
        label,
        colour,
        thickness,
    )


def draw_box(img, box, label, colour, thickness=2):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return

    # Draw a subtle dark outline first so coloured boxes remain visible
    # on bright court lines and shadows.
    cv2.rectangle(img, (x1, y1), (x2, y2), (10, 10, 10), thickness + 2)
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, thickness)

    if label:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.58
        label_th = 2
        (tw, th), base = cv2.getTextSize(label, font, scale, label_th)

        pad_x = 5
        pad_y = 4
        label_x1 = x1
        label_y2 = max(th + 2 * pad_y + 2, y1 - 4)
        label_y1 = max(0, label_y2 - th - 2 * pad_y)
        label_x2 = min(w - 1, label_x1 + tw + 2 * pad_x)

        # Filled dark label background.
        cv2.rectangle(img, (label_x1, label_y1), (label_x2, label_y2), (15, 15, 15), -1)
        cv2.rectangle(img, (label_x1, label_y1), (label_x2, label_y2), colour, 1)

        cv2.putText(
            img,
            label,
            (label_x1 + pad_x, label_y2 - pad_y),
            font,
            scale,
            colour,
            label_th,
            cv2.LINE_AA,
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

    if tid <= 0 or w <= 0 or h <= 0 or score <= 0:
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


def nearest_before(rows, t):
    best = None
    for ts, data in rows:
        if ts <= t:
            best = data
        else:
            break
    return best


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
            images.append((t, img))

        elif topic == "/detections":
            msg = deserialize_message(data, msg_types[topic])
            detections_rows.append((t, detection_boxes(msg)))

        elif topic == "/tracks":
            msg = deserialize_message(data, msg_types[topic])
            tracks = []
            for tr in msg.tracks:
                tb = track_box(tr)
                if tb:
                    tracks.append(tb)
            tracks_rows.append((t, tracks))

        elif topic == "/target":
            msg = deserialize_message(data, msg_types[topic])
            raw_rows.append((t, target_box(msg)))

        elif topic == "/target_memory_mars":
            msg = deserialize_message(data, msg_types[topic])
            tim_rows.append((t, target_box(msg)))

    if not images:
        raise RuntimeError("No /camera/image_raw or /camera/dashboard frames found in this bag.")

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
    detections = nearest_before(CACHE["detections"], t) or []
    tracks = nearest_before(CACHE["tracks"], t) or []
    raw = nearest_before(CACHE["raw"], t)
    tim = nearest_before(CACHE["tim"], t)
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


def export_mp4(out_path: str, draw_detections: bool, draw_tracks: bool, draw_raw: bool, draw_tim: bool, only_ids: str, fps: float):
    if not CACHE:
        raise RuntimeError("No bag loaded.")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    first = render_frame(0, draw_detections, draw_tracks, draw_raw, draw_tim, only_ids)
    h, w = first.shape[:2]

    writer = cv2.VideoWriter(
        str(out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )

    for idx in range(len(CACHE["images"])):
        frame = render_frame(idx, draw_detections, draw_tracks, draw_raw, draw_tim, only_ids)
        writer.write(frame)

    writer.release()
    return str(out)


class ReplayRequest(BaseModel):
    bag: str
    target_id: int = 1
    tracker: str = "bytetrack"
    tim_mode: str = "mars"
    rate: float = 1.0

    absence_recovery_enabled: bool = True
    absence_after_missed_frames: int = 4
    absence_min_total: float = 0.60
    absence_min_distance: float = 0.35
    absence_min_scale: float = 0.45
    absence_min_similarity: float = 0.70
    absence_appearance_margin: float = 0.25
    absence_confirm_frames: int = 4

    rank_aware_reacquisition_enabled: bool = True
    rank_aware_confirm_frames: int = 4
    rank_aware_lost_min_total: float = 0.60
    rank_aware_lost_min_geom: float = 0.25
    rank_aware_lost_min_app: float = 0.10
    rank_aware_lost_app_margin: float = 0.10

    appearance_update_cooldown_frames: int = 8


class ExportRequest(BaseModel):
    out: str = "reports/visual_audit/tim_audit_export.mp4"
    draw_detections: bool = False
    draw_tracks: bool = True
    draw_raw: bool = True
    draw_tim: bool = True
    only_ids: str = ""
    fps: float = 20.0


def run_replay_job(req: ReplayRequest):
    global JOB

    env = os.environ.copy()
    env.update({
        "TIM_STARTUP_SELECTED_ONLY": "true",

        # Keep UI-generated bags separate from official eval_matrix outputs.
        "TIM_REPLAY_OUT_ROOT": str(ROOT / "artifacts/bags/derived/ui_replays"),
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
    bags = find_metadata_bags(ROOT)
    favs = [x for x in load_favourites() if x in bags]

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
):
    from fastapi import Response
    import cv2

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

    return Response(content=buf.tobytes(), media_type="image/jpeg")


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


@app.post("/api/favourites/add")
def api_favourites_add(payload: dict[str, str]):
    bag = str(payload.get("bag", "")).strip()
    favs = load_favourites()

    if bag and bag not in favs:
        favs.append(bag)

    save_favourites(favs)
    return {"ok": True, "favourites": load_favourites()}


@app.post("/api/favourites/remove")
def api_favourites_remove(payload: dict[str, str]):
    bag = str(payload.get("bag", "")).strip()
    favs = [x for x in load_favourites() if x != bag]
    save_favourites(favs)
    return {"ok": True, "favourites": favs}


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>TIM-MARS Audit UI</title>
  <style>

    #bag, #ann {
      width: min(1000px, 92vw);
      max-width: 1000px;
      font-size: 15px;
    }
    #selectedBagPath {
      display: block;
      max-width: min(1000px, 92vw);
      overflow-wrap: anywhere;
      color: #aaa;
      margin-top: 6px;
    }

    body {
      font-family: Arial, sans-serif;
      margin: 18px;
      background: #111;
      color: #eee;
      font-size: 18px;
    }
    h2 { font-size: 28px; margin: 0 0 16px 0; }
    h3 { font-size: 22px; margin: 0 0 12px 0; }
    select, input, button {
      margin: 6px;
      padding: 10px 12px;
      font-size: 17px;
      border-radius: 4px;
    }
    button {
      cursor: pointer;
      font-weight: 600;
    }
    input[type=number] { width: 110px; }
    input[type=text] { width: 160px; }
    .row {
      margin: 12px 0;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
    }
    .panel {
      border: 1px solid #444;
      padding: 16px;
      margin: 14px 0;
      border-radius: 8px;
      background: #151515;
    }
     #frameLabel {
      font-size: 20px;
      font-weight: 700;
      min-width: 220px;
      display: inline-block;
    }
    #viewerPanel {
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    #viewerPanel h3 {
      align-self: stretch;
    }
    #viewerMeta {
      align-self: stretch;
    }
    .viewer-controls {
      width: min(1100px, 92vw);
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
    }
    .viewer-controls .row {
      justify-content: center;
    }
    #frameSlider {
      width: 100%;
      height: 32px;
    }
    .video-wrap {
      width: min(1100px, 92vw);
      display: flex;
      justify-content: center;
      margin-top: 12px;
    }
    .video-box {
      position: relative;
      width: 100%;
      background: #000;
      border: 2px solid #555;
    }
    #frameImg {
      width: 100%;
      height: auto;
      display: block;
      background: #222;
      image-rendering: auto;
      cursor: pointer;
    }
    .video-controls {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      background: linear-gradient(to top, rgba(0,0,0,0.88), rgba(0,0,0,0.28), rgba(0,0,0,0));
      color: white;
      opacity: 0.96;
    }
    .video-play {
      width: 44px;
      height: 38px;
      border: none;
      border-radius: 4px;
      background: rgba(255,255,255,0.16);
      color: white;
      font-size: 20px;
      cursor: pointer;
    }
    .video-time {
      min-width: 120px;
      font-size: 16px;
      font-weight: 700;
      text-align: center;
    }
    #videoProgress {
      flex: 1;
      height: 22px;
      accent-color: #2d6cdf;
      cursor: pointer;
    }
    pre {
      background: #000;
      color: #ddd;
      padding: 14px;
      max-height: 320px;
      overflow: auto;
      font-size: 15px;
    }
    label {
      margin-right: 14px;
      font-size: 18px;
    }
    .primary {
      background: #2d6cdf;
      color: white;
      border: none;
    }
    .danger {
      background: #8a2d2d;
      color: white;
      border: none;
    }
    .preset {
      background: #333;
      color: white;
      border: 1px solid #666;
    }
    .viewer-options {
      width: min(1100px, 92vw);
      margin-top: 14px;
      background: #181818;
      border: 1px solid #444;
      border-radius: 8px;
      padding: 10px 14px;
    }
    .viewer-options summary {
      cursor: pointer;
      font-size: 18px;
      font-weight: 700;
      color: #ddd;
      padding: 6px 0;
    }
    .viewer-options[open] {
      padding-bottom: 16px;
    }
  </style>
</head>
<body>
  <h2>TIM-MARS Simple Audit UI</h2>

  <div class="panel">
    <h3>1. Load bag</h3>
    <div id="bagSelectorBody">
    <div class="row">
      filter bags <input id="bagFilter" type="text" placeholder="hard, bytetrack, source, seq04..." oninput="renderBagList()" style="width: 360px">
      <button onclick="refreshLists()">Refresh</button>
      <button onclick="toggleFavouritesOnly()" id="favOnlyBtn">Show favourites only</button>
    </div>
    <div class="row">
      <select id="bag" style="width: min(1100px, 90vw)" onchange="showSelectedBagPath()"></select>
    </div>
    <div class="row">
      <select id="ann" style="width: min(1100px, 90vw)"></select>
    </div>
    <div class="row" style="font-size: 15px; color: #bbb;">
      selected bag: <span id="selectedBagPath"></span>
    </div>
    <button onclick="loadBag()">Load selected bag</button>
    <button onclick="addFavourite()">★ Add favourite</button>
    <button onclick="removeFavourite()">Remove favourite</button>
    <button onclick="toggleBagPanel()" id="bagPanelToggle" style="display:none;">Show bag selector</button>
    <span id="loadStatus"></span>

    </div>
    <div id="loadedSummary" style="display:none; margin-top: 12px; padding: 12px; background:#202020; border:1px solid #444; border-radius:6px;">
      <b>Loaded:</b> <span id="loadedScenario"></span><br>
      <span id="loadedMeta"></span>
    </div>
  </div>

  <div class="panel" id="viewerPanel">
    <h3>2. Viewer</h3>

    <div id="viewerMeta" style="margin-bottom: 14px; padding: 12px; background:#202020; border:1px solid #444; border-radius:6px; font-size:18px;">
      Load a bag to see detector, tracker, TIM mode, target, frame count, and duration.
    </div>

    <!-- Hidden compatibility controls used by existing JavaScript. -->
    <input type="range" id="frameSlider" min="0" max="0" value="0" oninput="updateFrame()" style="display:none;">
    <span id="frameLabel" style="display:none;">0</span>
    <button onclick="togglePlay()" id="playBtn" style="display:none;">▶ Play</button>

    <div class="video-wrap">
      <div class="video-box">
        <img id="frameImg" src="" onclick="togglePlay()">
        <div class="video-controls">
          <button class="video-play" id="videoPlayBtn" onclick="togglePlay()">▶</button>
          <span class="video-time" id="videoTimeLabel">0:00 / 0:00</span>
          <input type="range" id="videoProgress" min="0" max="0" value="0" oninput="seekVideoProgress()">
        </div>
      </div>
    </div>

    <details class="viewer-options">
      <summary>Viewer options</summary>

      <div class="row">
        <button onclick="prevFrame()">⟵ Prev</button>
        <button onclick="nextFrame()">Next ⟶</button>
        jump to time <input id="jumpTime" type="number" value="0" step="0.1">
        <button onclick="jumpToTime()">Jump</button>
        <button onclick="preloadFrames()" class="primary">Preload current overlay</button>
        <button onclick="clearFrameCache()">Clear preload</button>
        <span id="preloadStatus">not preloaded</span>
      </div>

      <div class="row">
        <label><input type="checkbox" id="drawDetections" onchange="updateFrame()"> detections</label>
        <label><input type="checkbox" id="drawTracks" checked onchange="updateFrame()"> tracks</label>
        <label><input type="checkbox" id="drawRaw" checked onchange="updateFrame()"> raw target</label>
        <label><input type="checkbox" id="drawTim" checked onchange="updateFrame()"> TIM target</label>
        only IDs: <input id="onlyIds" value="" placeholder="1,42" oninput="updateFrame()">
      </div>

      <div class="row">
        <button class="preset" onclick="imageOnly()">Image only</button>
        <button class="preset" onclick="detectionsOnly()">Detections only</button>
        <button class="preset" onclick="tracksOnly()">Tracks only</button>
        <button class="preset" onclick="runTimForLoadedBag()">Run TIM-MARS on this bag</button>
        <button class="preset" onclick="timOnly()">TIM only</button>
        <button class="preset" onclick="rawTimOnly()">Raw + TIM</button>
        <button class="preset" onclick="allOverlays()">All overlays</button>
      </div>
    </details>
  </div>

  <div class="panel">
    <details>
      <summary style="font-size:22px; font-weight:700; cursor:pointer;">3. Advanced: Run TIM replay with settings</summary>
    <div class="row">
      target <input id="targetId" type="number" value="1">
      tracker
      <select id="tracker">
        <option>bytetrack</option>
        <option>ocsort</option>
        <option>deepsort</option>
      </select>
      rate <input id="rate" type="number" step="0.1" value="1.0">
    </div>

    <div class="row">
      absence min total <input id="absenceMinTotal" type="number" step="0.01" value="0.60">
      distance <input id="absenceMinDistance" type="number" step="0.01" value="0.35">
      scale <input id="absenceMinScale" type="number" step="0.01" value="0.45">
      similarity <input id="absenceMinSimilarity" type="number" step="0.01" value="0.70">
      margin <input id="absenceMargin" type="number" step="0.01" value="0.25">
      confirm <input id="absenceConfirm" type="number" value="4">
    </div>

    <div class="row">
      rank total <input id="rankTotal" type="number" step="0.01" value="0.60">
      geom <input id="rankGeom" type="number" step="0.01" value="0.25">
      app <input id="rankApp" type="number" step="0.01" value="0.10">
      app margin <input id="rankMargin" type="number" step="0.01" value="0.10">
      confirm <input id="rankConfirm" type="number" value="4">
    </div>

    <button onclick="runReplay()">Run TIM replay</button>
    <button onclick="checkJob()">Refresh job log</button>
    <button onclick="loadLastOutput()">Load last output bag</button>
    <pre id="jobLog"></pre>
  </div>

    </details>
  </div>

  <div class="panel">
    <details>
      <summary style="font-size:22px; font-weight:700; cursor:pointer;">4. Export MP4</summary>
    output <input id="mp4Out" style="width:60%" value="reports/visual_audit/tim_audit_export.mp4">
    fps <input id="mp4Fps" type="number" value="20">
    <button onclick="exportMp4()">Export MP4 from current loaded bag</button>
    <span id="exportStatus"></span>
    </details>
  </div>




<script>
let emergencyLoadedFrames = 0;
let emergencyLoadedDuration = 0.0;

function emergencyBagInfo(path) {
  const name = (path || "").split("/").pop() || "";
  const lower = path.toLowerCase();

  let prefix = "bag";
  if (lower.includes("/artifacts/bags/derived/ui_replays/")) prefix = "ui";
  else if (lower.includes("/artifacts/bags/datasets/")) prefix = "dataset";
  else if (lower.includes("/artifacts/bags/derived/conservative_safety_eval/")) prefix = "safe";
  else if (lower.includes("/artifacts/bags/derived/eval_matrix/")) prefix = "eval";
  else if (lower.includes("/artifacts/bags/live_camera/")) prefix = "live";
  else if (lower.includes("/artifacts/bags/source_video/")) prefix = "source";

  let scenario = name;
  if (lower.includes("hard_reentry") || lower.includes("hard-reentry")) scenario = "hard re-entry / ID switch";
  else if (lower.includes("two_person_no_crossing")) scenario = "two-person no crossing";
  else if (lower.includes("seq01")) scenario = "seq01 clean four-person";
  else if (lower.includes("seq02")) scenario = "seq02 target re-entry";
  else if (lower.includes("seq03")) scenario = "seq03 crossing ambiguity";
  else if (lower.includes("seq04")) scenario = "seq04 occlusion / no exit";

  let tracker = "";
  if (lower.includes("tracker_bytetrack")) tracker = "ByteTrack";
  else if (lower.includes("tracker_ocsort")) tracker = "OCSORT";
  else if (lower.includes("tracker_deepsort")) tracker = "DeepSORT";

  let tim = "";
  if (lower.includes("tim_mars")) tim = "TIM-MARS";
  else if (lower.includes("tim_off")) tim = "TIM off";

  let target = "";
  const m = name.match(/target_([0-9]+)/);
  if (m) target = "target " + m[1];

  let revision = "";
  const r = name.match(/__r([0-9]+)$/);
  if (r) revision = "r" + r[1];

  const parts = ["[" + prefix + "]", scenario];
  if (tracker) parts.push(tracker);
  if (tim) parts.push(tim);
  if (target) parts.push(target);
  if (revision) parts.push(revision);

  return parts.join(" | ");
}

function emergencyFormatTime(seconds) {
  seconds = Math.max(0, seconds || 0);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function emergencySelectedBag() {
  const bagSelect = document.getElementById("bag");
  return bagSelect ? bagSelect.value : "";
}

function emergencySelectedAnn() {
  const annSelect = document.getElementById("ann");
  return annSelect ? annSelect.value : "";
}

function updateFrame() {
  const idx = parseInt(document.getElementById("progress").value || "0");
  const t = loadedFrames > 1 ? idx / (loadedFrames - 1) * loadedDuration : 0;
  document.getElementById("time").innerText = fmt(t) + " / " + fmt(loadedDuration);

  const common = new URLSearchParams();
  common.set("idx", String(idx));
  common.set("draw_detections", document.getElementById("det").checked ? "1" : "0");
  common.set("draw_tracks", document.getElementById("tracks").checked ? "1" : "0");
  common.set("only_ids", document.getElementById("ids").value || "");
  common.set("ts", String(Date.now()));

  const rawQ = new URLSearchParams(common);
  rawQ.set("draw_raw", "1");
  rawQ.set("draw_tim", "0");

  const timQ = new URLSearchParams(common);
  timQ.set("draw_raw", "0");
  timQ.set("draw_tim", "1");

  document.getElementById("rawFrame").src = "/frame.jpg?" + rawQ.toString();
  document.getElementById("timFrame").src = "/frame.jpg?" + timQ.toString();
}

function seek() { updateFrame(); }

function togglePlay() {
  if (playing) {
    playing = false;
    clearTimeout(timer);
    document.getElementById("playBtn").innerText = "▶";
    return;
  }
  playing = true;
  document.getElementById("playBtn").innerText = "⏸";
  step();
}

function step() {
  if (!playing) return;
  const p = document.getElementById("progress");
  let v = parseInt(p.value || "0");
  if (v >= loadedFrames - 1) v = 0;
  else v += 1;
  p.value = v;
  updateFrame();
  const delay = loadedFrames > 1 ? Math.max(20, Math.min(200, loadedDuration * 1000 / loadedFrames)) : 75;
  timer = setTimeout(step, delay);
}

function presetImage() {
  det.checked = false; tracks.checked = false; raw.checked = false; tim.checked = false; updateFrame();
}
function presetTracks() {
  det.checked = false; tracks.checked = true; raw.checked = false; tim.checked = false; updateFrame();
}
function presetRawTim() {
  det.checked = false; tracks.checked = false; raw.checked = true; tim.checked = true; updateFrame();
}
function presetAll() {
  det.checked = true; tracks.checked = true; raw.checked = true; tim.checked = true; updateFrame();
}

async function runTim() {
  const b = loadedBag || document.getElementById("bag").value;
  if (!b) return alert("Select and load a bag first.");
  document.getElementById("log").innerText = "Starting TIM-MARS replay...";
  const payload = {
    bag: b,
    target_id: parseInt(document.getElementById("targetId").value || "1"),
    tracker: document.getElementById("tracker").value,
    tim_mode: "mars",
    rate: parseFloat(document.getElementById("rate").value || "1.0"),
    absence_min_total: 0.60,
    absence_min_distance: 0.35,
    absence_min_scale: 0.45,
    absence_min_similarity: 0.70,
    absence_appearance_margin: 0.25,
    absence_confirm_frames: 4,
    rank_aware_lost_min_total: 0.60,
    rank_aware_lost_min_geom: 0.25,
    rank_aware_lost_min_app: 0.10,
    rank_aware_lost_app_margin: 0.10,
    rank_aware_confirm_frames: 4
  };
  const res = await fetch("/api/replay", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) {
    document.getElementById("log").innerText = JSON.stringify(data, null, 2);
    return;
  }
  pollJob();
}

async function pollJob() {
  const res = await fetch("/api/job?ts=" + Date.now());
  const data = await res.json();
  document.getElementById("log").innerText = data.log || "";
  if (data.running) {
    setTimeout(pollJob, 1500);
    return;
  }
  if (data.last_output_bag) {
    await loadList();
    await loadBag(data.last_output_bag);
  }
}

async function loadLast() {
  const res = await fetch("/api/job?ts=" + Date.now());
  const data = await res.json();
  if (data.last_output_bag) loadBag(data.last_output_bag);
  else alert("No last output bag.");
}

window.addEventListener("load", loadList);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
