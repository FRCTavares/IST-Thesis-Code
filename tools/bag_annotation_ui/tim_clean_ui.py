#!/usr/bin/env python3
"""Entrypoint for the TIM-MARS clean annotation and review UI.

This FastAPI application serves the HTML frontend, mounts the shared backend
API routes, and exposes lightweight endpoints for annotation discovery,
annotation editing, and evaluation triggering.

Run this file directly when opening the local annotation UI.
"""

import asyncio

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
from tim_ui_physical_reference_v2 import (
    build_effective_reference_previews,
    generate_sequence_proposals,
    load_physical_reference_v2_for_ui,
    next_person_ref,
    propose_geometry_with_optical_flow,
    save_physical_reference_v2_for_ui,
    sequence_proposal_cache_key,
)
from physical_target_reference import (  # noqa: E402  (path set up by tim_ui_physical_reference)
    CONTRACT_VERSION as PHYSICAL_REFERENCE_CONTRACT_VERSION,
    PhysicalReferenceValidationError,
)
from physical_target_reference_v2 import (  # noqa: E402  (path set up by tim_ui_physical_reference_v2)
    CONTRACT_VERSION as PHYSICAL_REFERENCE_V2_CONTRACT_VERSION,
    SCHEMA_VERSION as PHYSICAL_REFERENCE_V2_SCHEMA_VERSION,
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


# --- v2 (tim_physical_target_bbox_v2) routes --------------------------------
#
# Additive alongside the v1 routes above, not a replacement -- v1's own
# routes remain reachable and untouched. New physical-reference artifacts
# created through the normal UI workflow use these v2 routes exclusively.
# Discovery (/api/physical_reference/list), the coordinate-convention
# resolver, and the image-topic hint above are schema-version-independent
# (they inspect the bag or the filesystem, not an artifact's own schema
# version) and are reused as-is -- not duplicated here.


@app.get("/api/physical_reference_v2/info")
def physical_reference_v2_info_api():
    return {
        "contract_version": PHYSICAL_REFERENCE_V2_CONTRACT_VERSION,
        "schema_version": PHYSICAL_REFERENCE_V2_SCHEMA_VERSION,
    }


@app.post("/api/physical_reference_v2/load")
async def physical_reference_v2_load_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    if not path_text:
        return {"ok": False, "error": "No physical-reference path provided."}

    try:
        data = load_physical_reference_v2_for_ui(path_text, REPO_ROOT)
    except (
        PhysicalReferenceUIError,
        PhysicalReferenceValidationError,
        FileNotFoundError,
    ) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {"ok": True, **data}


@app.post("/api/physical_reference_v2/save")
async def physical_reference_v2_save_api(request: Request):
    payload = await request.json()
    path_text = str(payload.get("path", "")).strip()
    artifact = payload.get("artifact")

    if not path_text:
        return {"ok": False, "error": "No output physical-reference path provided."}
    if not isinstance(artifact, dict):
        return {"ok": False, "error": "artifact must be an object."}

    try:
        result = save_physical_reference_v2_for_ui(path_text, artifact, REPO_ROOT)
    except (PhysicalReferenceUIError, PhysicalReferenceValidationError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        **result,
        "message": f"Saved {result['sample_count']} physical-reference samples to {result['path']}",
    }


@app.post("/api/physical_reference_v2/next_person_ref")
async def physical_reference_v2_next_person_ref_api(request: Request):
    payload = await request.json()
    known_refs = payload.get("known_refs")
    if not isinstance(known_refs, list):
        return {"ok": False, "error": "known_refs must be a list."}

    return {"ok": True, "person_ref": next_person_ref([str(r) for r in known_refs])}


@app.post("/api/physical_reference_v2/preview")
async def physical_reference_v2_preview_api(request: Request):
    """Resolve a read-only frame batch with the canonical v2 evaluator."""

    payload = await request.json()
    artifact = payload.get("artifact")
    times_s = payload.get("times_s")
    if not isinstance(artifact, dict):
        return JSONResponse(
            {"ok": False, "error": "artifact must be an object."}, status_code=400
        )
    if not isinstance(times_s, list):
        return JSONResponse(
            {"ok": False, "error": "times_s must be a list."}, status_code=400
        )

    try:
        previews = build_effective_reference_previews(
            artifact, [float(value) for value in times_s]
        )
    except (TypeError, ValueError, PhysicalReferenceValidationError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {"ok": True, "previews": previews}


PHYSICAL_REFERENCE_SEQUENCE_CACHE: dict[str, dict] = {}
PHYSICAL_REFERENCE_SEQUENCE_JOB: dict = {
    "state": "idle",
    "progress": 0.0,
    "completed_steps": 0,
    "total_steps": 0,
    "cache_key": None,
    "result": None,
    "error": None,
}


def _sequence_job_progress(completed: int, total: int) -> None:
    PHYSICAL_REFERENCE_SEQUENCE_JOB["completed_steps"] = int(completed)
    PHYSICAL_REFERENCE_SEQUENCE_JOB["total_steps"] = int(total)
    PHYSICAL_REFERENCE_SEQUENCE_JOB["progress"] = min(
        1.0, float(completed) / max(1, int(total))
    )


async def _run_physical_reference_sequence_job(
    *, cache_key: str, images: list, times_s: list[float], artifact: dict
) -> None:
    try:
        result = await asyncio.to_thread(
            generate_sequence_proposals,
            images=images,
            times_s=times_s,
            artifact_payload=artifact,
            # The loaded curated source supplies images only. Detector refinement
            # remains an optional anonymous-box helper and is not silently fed
            # tracker/RAW/TIM output here.
            anonymous_detections_by_frame=None,
            progress_callback=_sequence_job_progress,
        )
        PHYSICAL_REFERENCE_SEQUENCE_CACHE[cache_key] = result
        PHYSICAL_REFERENCE_SEQUENCE_JOB.update(
            state="complete", progress=1.0, result=result, error=None
        )
    except Exception as exc:
        PHYSICAL_REFERENCE_SEQUENCE_JOB.update(
            state="error", result=None, error=str(exc)
        )


@app.post("/api/physical_reference_v2/sequence_proposals/start")
async def physical_reference_v2_sequence_proposals_start_api(request: Request):
    """Start or reuse ephemeral full-sequence image-only proposals."""

    payload = await request.json()
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        return JSONResponse(
            {"ok": False, "error": "artifact must be an object."}, status_code=400
        )
    if PHYSICAL_REFERENCE_SEQUENCE_JOB.get("state") == "running":
        return JSONResponse(
            {"ok": False, "error": "Sequence proposal generation is already running."},
            status_code=409,
        )
    cached_images = list(backend.CACHE.get("images", []))
    images = [image for _timestamp, image in cached_images]
    if not images:
        return JSONResponse(
            {"ok": False, "error": "No source frames are loaded."}, status_code=400
        )
    first_timestamp = cached_images[0][0]
    times_s = [float((timestamp - first_timestamp) / 1e9) for timestamp, _ in cached_images]
    cache_key = sequence_proposal_cache_key(artifact, times_s, len(images))
    if not bool(payload.get("refresh")) and cache_key in PHYSICAL_REFERENCE_SEQUENCE_CACHE:
        result = PHYSICAL_REFERENCE_SEQUENCE_CACHE[cache_key]
        PHYSICAL_REFERENCE_SEQUENCE_JOB.update(
            state="complete",
            progress=1.0,
            completed_steps=1,
            total_steps=1,
            cache_key=cache_key,
            result=result,
            error=None,
        )
        return {"ok": True, "state": "complete", "cached": True}

    PHYSICAL_REFERENCE_SEQUENCE_JOB.update(
        state="running",
        progress=0.0,
        completed_steps=0,
        total_steps=0,
        cache_key=cache_key,
        result=None,
        error=None,
    )
    asyncio.create_task(
        _run_physical_reference_sequence_job(
            cache_key=cache_key,
            images=images,
            times_s=times_s,
            artifact=artifact,
        )
    )
    return {"ok": True, "state": "running", "cached": False}


@app.get("/api/physical_reference_v2/sequence_proposals/status")
def physical_reference_v2_sequence_proposals_status_api():
    return {"ok": True, **PHYSICAL_REFERENCE_SEQUENCE_JOB}


@app.post("/api/physical_reference_v2/sequence_proposals/clear")
def physical_reference_v2_sequence_proposals_clear_api():
    if PHYSICAL_REFERENCE_SEQUENCE_JOB.get("state") == "running":
        return JSONResponse(
            {"ok": False, "error": "Cannot clear proposals while generation is running."},
            status_code=409,
        )
    PHYSICAL_REFERENCE_SEQUENCE_CACHE.clear()
    PHYSICAL_REFERENCE_SEQUENCE_JOB.update(
        state="idle",
        progress=0.0,
        completed_steps=0,
        total_steps=0,
        cache_key=None,
        result=None,
        error=None,
    )
    return {"ok": True, "state": "idle"}


@app.post("/api/physical_reference_v2/propose")
async def physical_reference_v2_propose_api(request: Request):
    """Generate an ephemeral image-only bbox proposal from a human anchor."""

    payload = await request.json()
    images = [image for _timestamp, image in backend.CACHE.get("images", [])]
    try:
        proposal = await asyncio.to_thread(
            propose_geometry_with_optical_flow,
            images=images,
            anchor_frame_index=int(payload.get("anchor_frame_index")),
            target_frame_index=int(payload.get("target_frame_index")),
            target_bbox_xyxy=payload.get("target_bbox_xyxy"),
            distractors=payload.get("distractors") or [],
        )
    except (TypeError, ValueError, PhysicalReferenceUIError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return {
        "ok": True,
        "proposal": proposal,
        "message": (
            "Image-only proposal generated. It is not accepted reference "
            "geometry and has not modified or saved any artifact."
        ),
    }


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
