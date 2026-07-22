#!/usr/bin/env python3
"""Backend API routes for the TIM-MARS annotation UI.

This module owns FastAPI endpoints for bag loading, frame rendering, replay
jobs, image/video export, and download guards. It delegates bag parsing,
drawing, rendering, discovery, and evaluation to smaller helper modules.

It is imported by tim_clean_ui.py and is not normally run directly.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import threading
from pathlib import Path

import cv2
from tim_ui_discovery import discover_annotations, discover_bags
from tim_ui_renderers import (
    CACHE,
    export_mp4,
    render_frame,
    render_frame_clean,
    render_frame_clean_comparison,
    render_frame_paper_overlay,
    render_paper_contact_sheet,
)
from tim_ui_bag_cache import load_bag_cache
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from pydantic import BaseModel
import uvicorn


ROOT = Path.cwd()
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

        CACHE.clear()
        CACHE.update(load_bag_cache(bag, ann))

        images = CACHE.get("images", [])

        frame_times_s = []
        duration_s = 0.0

        if images:
            first_t = images[0][0]
            frame_times_s = [float((t - first_t) / 1e9) for t, _img in images]

            if len(images) >= 2:
                duration_s = float(frame_times_s[-1])

        return {
            "ok": True,
            "frames": len(images),
            "frame_times_s": frame_times_s,
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

@app.get("/api/cache_state")
def api_cache_state():
    """Return current in-memory UI cache state.

    This lets the browser restore the loaded viewer after a page refresh without
    forcing a new /api/load call, as long as the FastAPI process is still alive.
    """
    images = CACHE.get("images", [])
    return {
        "ok": bool(images),
        "frames": len(images),
        "duration": CACHE.get("duration", 0.0),
        "bag": str(CACHE.get("bag", "")),
        "annotation": str(CACHE.get("annotation", "")),
        "cache_token": CACHE.get("cache_token", 0),
        "stats": CACHE.get("stats", {}),
    }

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
