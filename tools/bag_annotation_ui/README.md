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

## Video export

Tracker-ID views and MP4 exports are built into the maintained UI renderer.
For a standalone overlay or paired raw-versus-TIM video, use the explicit
renderers under `tools/bag/`.

## Annotation policy

The UI helps the user create and edit annotation files, but annotation choices
must remain manual. Do not generate final annotation CSVs automatically.

The Issue #25 `Physical reference v2` workspace displays the evaluator's
effective interpolated reference during normal playback. It can precompute
frame-by-frame, bidirectional sparse-optical-flow proposals between compatible
explicit human anchors, cache them in server/session memory, group conservative
review regions, and recursively suggest efficient intermediate anchors. A
short-range paused-frame proposal remains available as a fallback. Yellow
proposals preserve human-established `phys_dNNN` correspondence, stop on
insufficient evidence, and are never accepted or saved automatically.
IoU/centre/scale disagreement and deterministic flow-confidence categories
prioritise human review only; they are not evaluation criteria. The current
Seq01 path uses no detector. An optional anonymous-box geometry matcher accepts
coordinates only and refuses ambiguous matches; no detector/tracker identity,
RAW/TIM target output, or TIM-MARS output constructs the physical reference.

For M4B production annotation, CVAT is now preferred over further expansion of
this custom UI. `tools/analysis/cvat_physical_reference.py` exports exact
ordered source frames and timestamps, then fail-closed converts human-reviewed
CVAT rectangle annotations back to frozen v2. Ordered PNG tasks use **CVAT for
images 1.1**; CVAT may expand track interpolation into one `<image><box>` per
frame, while native `<track>` CVAT 1.1 remains supported. `physical_ref`,
never numeric CVAT IDs or drawing order, defines identity; source times come
from `frame_manifest.json`, never nominal FPS, and human review remains
authoritative. If a sequence has no prior human v2 bbox evidence, the bridge's
`prepare --preparation-config` mode produces a seedless task and leaves the
semantic sidecar empty so conversion fails until the annotator explicitly
records reviewed state/context/role intervals; tracker boxes are never used as
identity seeds. This UI remains the fallback,
schema/debug viewer, effective-reference inspector, and final visual validation
instrument; its assisted-propagation implementation is intentionally retained.

## Typical launch command

Use the project-standard annotation UI command from the repository root after
sourcing ROS:

`thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888`

Use the explicit `thesis_env` interpreter: the UI depends on FastAPI and other
packages intentionally absent from the system Python environment. The module is
therefore not marked as a standalone executable.

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
