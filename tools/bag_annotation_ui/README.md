# TIM-MARS Bag Annotation UI

This folder contains the local tools used to inspect TIM-MARS replay bags,
review selected-target behavior, create/edit annotation CSVs manually, and
render visual validation videos.

The UI is intentionally local and thesis-specific. It knows about the current
repository bag layout, annotation folders, replay scripts, and evaluation
helpers.

## Main entrypoint

| Tool | Status | Purpose |
| --- | --- | --- |
| `tim_clean_ui.py` | Main entrypoint | Starts the FastAPI annotation/review UI. |
| `static/tim_clean_ui.html` | Frontend asset | Single-page browser UI served by `tim_clean_ui.py`. |

## Backend modules

| Module | Purpose |
| --- | --- |
| `tim_ui_backend.py` | FastAPI API routes, replay jobs, exports, and download guards. |
| `tim_ui_bag_cache.py` | Loads rosbag2 data into the lightweight cache used by renderers. |
| `tim_ui_renderers.py` | Renders frames, comparison views, contact sheets, and MP4 exports. |
| `tim_ui_drawing.py` | Pure OpenCV drawing and coordinate helpers. |
| `tim_ui_annotations.py` | Annotation CSV validation, normalization, loading, and saving. |
| `tim_ui_discovery.py` | Discovers curated bags and annotation CSVs in known repo folders. |
| `tim_ui_evaluation.py` | Runs target and bbox correctness evaluators from the UI. |

## Video helpers

| Tool | Purpose |
| --- | --- |
| `render_all_tracks_id_video.py` | Renders an all-track-ID overlay video for manual tracker review. |
| `video.py` | Renders single-stream and paired visual validation videos from bags and annotations. |

## Annotation policy

The UI helps the user create and edit annotation files, but annotation choices
must remain manual. Do not generate final annotation CSVs automatically.

## Typical launch command

Use the project-standard annotation UI command from the repository root after
sourcing ROS:

` .venv-tim-ui/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888`

## Repository paths

The discovery helper prioritizes current curated folders:

- `bags/reference`
- `bags/replay`
- `bags/review`
- `bags/annotation_inputs`
- `bags/source`
- `docs/data/annotations`

Legacy fallback paths may still appear for older local data, but final thesis
work should prefer the current folders above.

## Evaluation from the UI

The UI evaluation action calls the same analysis scripts used outside the UI:

- `tools/analysis/evaluate_tim_target_correctness.py`
- `tools/analysis/evaluate_tim_target_bbox_correctness.py`

This keeps UI-triggered reports consistent with command-line reports.
