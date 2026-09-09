# tools/bag_annotation_ui

Last reviewed: 2026-09-09

## Purpose

Local, thesis-specific FastAPI UI to inspect TIM-MARS replay bags, review
selected-target behaviour, and manually create or edit annotation CSVs. It
knows this repository's bag layout, annotation folders and evaluators.

## Contents

| Path | Role |
| --- | --- |
| `tim_clean_ui.py` | Entrypoint — starts the annotation/review server. |
| `static/` | Single-page browser UI (HTML/CSS/JS) served by the entrypoint. |
| `tim_ui_backend.py` | API routes, replay jobs, exports, download guards. |
| `tim_ui_bag_cache.py` | Loads rosbag2 data into the render cache. |
| `tim_ui_renderers.py`, `tim_ui_drawing.py` | Frame / comparison / contact-sheet rendering; pure OpenCV drawing helpers. |
| `tim_ui_annotations.py` | Annotation CSV validate / normalise / load / save. |
| `tim_ui_discovery.py` | Finds curated bags and annotation CSVs in known folders. |
| `tim_ui_evaluation.py` | Runs the `tools/analysis/` correctness evaluators from the UI. |
| `tim_ui_physical_reference.py`, `tim_ui_physical_reference_v2.py` | Physical-target reference workspaces (v2 current). |

## Rules

- Annotation choices stay manual — never auto-generate final annotation CSVs.
  Assisted proposals are review aids only and are never saved automatically.
- Launch with the `thesis_env` interpreter (FastAPI is not in system Python);
  the modules are deliberately not marked executable:
  `thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host <ip> --port 8888`
- Discovery prefers current curated folders under `bags/` and
  `docs/data/annotations/`.
- For standalone (non-UI) video, use `tools/bag/`.

## See also

- `docs/design/tim_tooling_index.md` — annotation/review path authority
- `docs/issues/p1-10-physical-reference-annotation-plan.md` — physical-reference
  method and the CVAT bridge (`tools/analysis/cvat_physical_reference.py`)
