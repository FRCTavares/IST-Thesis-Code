#!/usr/bin/env python3
"""Entrypoint for the TIM-MARS clean annotation and review UI.

This FastAPI application serves the HTML frontend, mounts the shared backend
API routes, and exposes lightweight endpoints for annotation discovery,
annotation editing, and evaluation triggering.

Run this file directly when opening the local annotation UI.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import argparse
import json
from pathlib import Path
from tim_ui_discovery import discover_annotations as shared_discover_annotations, discover_bags as shared_discover_bags
from tim_ui_evaluation import run_ui_evaluation
from tim_ui_annotations import (
    ANNOTATION_EVENT_TYPES,
    ANNOTATION_FIELDS,
    load_annotation_rows,
    save_annotation_rows,
)
from tim_ui_physical_reference import (
    PhysicalReferenceUIError,
    discover_physical_references,
    image_topic_hint,
    load_physical_reference_for_ui,
    resolve_coordinate_convention,
    save_physical_reference_for_ui,
)
from physical_target_reference import (  # noqa: E402  (path set up by tim_ui_physical_reference)
    CONTRACT_VERSION as PHYSICAL_REFERENCE_CONTRACT_VERSION,
    PhysicalReferenceValidationError,
)
import uvicorn

# Import the backend API routes used by the clean annotation UI.
import tim_ui_backend as backend

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
HTML_PATH = STATIC_DIR / "tim_clean_ui.html"

app = FastAPI(title="TIM-MARS Clean UI")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

for route in backend.app.routes:
    if getattr(route, "path", "").startswith("/api/") or getattr(route, "path", "") == "/frame.jpg":
        app.router.routes.append(route)


@app.post("/api/evaluate")
async def evaluate_api(request: Request):
    payload = await request.json()
    status_code, data = run_ui_evaluation(
        bag=str(payload.get("bag", "")).strip(),
        ann=str(payload.get("ann", "")).strip(),
        repo_root=REPO_ROOT,
    )

    if status_code != 200:
        return JSONResponse(data, status_code=status_code)

    return data



@app.post("/api/annotation/load")
async def annotation_load_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    if not path_text:
        return {"ok": False, "error": "No annotation path provided."}

    try:
        rel, rows = load_annotation_rows(path_text, REPO_ROOT)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        "path": str(rel),
        "rows": rows,
        "fields": ANNOTATION_FIELDS,
        "event_types": ANNOTATION_EVENT_TYPES,
    }


@app.post("/api/annotation/save")
async def annotation_save_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    rows = payload.get("rows", [])

    if not path_text:
        return {"ok": False, "error": "No output annotation path provided."}
    if not isinstance(rows, list):
        return {"ok": False, "error": "Rows must be a list."}

    try:
        rel, normalised = save_annotation_rows(path_text, rows, REPO_ROOT)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        "path": str(rel),
        "rows": len(normalised),
        "message": f"Saved {len(normalised)} annotation intervals to {rel}",
    }



@app.get("/api/physical_reference/list")
def physical_reference_list_api():
    return {
        "paths": discover_physical_references(REPO_ROOT),
        "contract_version": PHYSICAL_REFERENCE_CONTRACT_VERSION,
    }


@app.post("/api/physical_reference/load")
async def physical_reference_load_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    if not path_text:
        return {"ok": False, "error": "No physical-reference path provided."}

    try:
        data = load_physical_reference_for_ui(path_text, REPO_ROOT)
    except (
        PhysicalReferenceUIError,
        PhysicalReferenceValidationError,
        FileNotFoundError,
    ) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {"ok": True, **data}


@app.post("/api/physical_reference/save")
async def physical_reference_save_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    artifact = payload.get("artifact")

    if not path_text:
        return {"ok": False, "error": "No output physical-reference path provided."}
    if not isinstance(artifact, dict):
        return {"ok": False, "error": "artifact must be an object."}

    try:
        result = save_physical_reference_for_ui(path_text, artifact, REPO_ROOT)
    except (PhysicalReferenceUIError, PhysicalReferenceValidationError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        **result,
        "message": f"Saved {result['sample_count']} physical-reference samples to {result['path']}",
    }


@app.post("/api/physical_reference/image_topic_hint")
async def physical_reference_image_topic_hint_api(request: Request):
    payload = await request.json()
    bag_text = str(payload.get("bag", "")).strip()
    if not bag_text:
        return {"ok": False, "error": "No bag path provided."}

    bag_path = REPO_ROOT / bag_text
    return {"ok": True, "topic": image_topic_hint(bag_path)}


@app.post("/api/physical_reference/resolve_coordinate_convention")
async def physical_reference_resolve_coordinate_convention_api(request: Request):
    payload = await request.json()
    bag_text = str(payload.get("bag", "")).strip()
    if not bag_text:
        return {"ok": False, "error": "No bag path provided."}

    bag_path = REPO_ROOT / bag_text
    resolved = resolve_coordinate_convention(str(bag_path))
    return {"ok": True, "resolved": resolved}


@app.get("/")
def root():
    return RedirectResponse(url="/clean")

@app.get("/clean", response_class=HTMLResponse)
def clean_ui():
    bags = shared_discover_bags(REPO_ROOT)
    annotations = shared_discover_annotations(REPO_ROOT)
    bags_json = json.dumps(bags)
    annotations_json = json.dumps(annotations)

    template_path = Path(__file__).with_name("static") / "tim_clean_ui.html"
    html = template_path.read_text()
    html = html.replace("__BAGS_JSON__", bags_json)
    html = html.replace("__ANNOTATIONS_JSON__", annotations_json)
    return HTMLResponse(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
