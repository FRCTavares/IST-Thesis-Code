# Repository Deep Dive

This document explains what this repository is for, how its parts interact, and how to reason about the folder layout.

Use this file for understanding.
Use `RUNBOOK.md` for commands.
Use `README.md` for fast onboarding and path selection.

## 1) System objective

The repository implements an experimental ROS 2 pipeline that converts live camera frames into actionable target state for dashboard/control, while preserving repeatability through bag replay and offline analysis.

Primary goals:

1. Real-time perception to target-state pipeline.
2. Deterministic and measurable timing behavior.
3. Reproducible experiment workflow (record -> replay -> analyze).
4. Operational dashboard visibility for human-in-the-loop work.

## 2) End-to-end data flow

### Live path (target hardware)

1. Camera publishes image frames and fps telemetry in ROS 2.
2. Inference client consumes ROS images and sends frames over ZMQ to detector service.
3. Detector service (container-side) returns detections to inference client.
4. Tracker converts detections into tracks (SORT / OC-SORT / ByteTrack modes).
5. Target selector chooses the active target.
6. Control and dashboard bridge consume target/tracking streams.
7. Web video and websocket/api endpoints serve the dashboard.

Conceptual chain:

`camera -> /camera/image_raw -> inference_client (ZMQ req/rep) -> /detections -> tracker -> /tracks -> target_selector -> /target -> control/dashboard`

### Replay path (evaluation)

1. Replay launch feeds recorded raw bags.
2. Nodes process data under controlled tracker settings.
3. Eval output is written as eval bags and analyzed offline.

Conceptual chain:

`bags/raw -> eval_replay.launch.py -> /timing + /tracks + /target -> bags/eval -> analysis scripts -> reports`

## 3) Component responsibilities

### ROS packages (`ros2_ws/src`)

- `thesis_bringup`
  - Launch composition, dashboard bridge, control node.
  - Owns most orchestration entrypoints for replay/live command surfaces.
- `thesis_inference_client`
  - Bridge between ROS images and detector service via ZMQ.
  - Emits detections and timing signals for instrumentation.
- `thesis_tracker`
  - Tracking backend abstraction (sort/ocsort/bytetrack) and track publication.
- `thesis_target_selector`
  - Chooses target from tracks and exposes target state for downstream use.
- `thesis_msgs`
  - Shared message interfaces used across nodes.

### Inference service (`infer_service`)

- `detection_zmq.py`
  - Detector server process expected to run inside Hailo container environment.
- `zmq_pub.py`
  - Utility publisher/helper for ZMQ-facing workflows.

Boundary rule:
- ROS graph remains on host side.
- Detector inference runtime is externalized behind ZMQ service boundary.

### Frontend (`user-interface`)

- React/TypeScript dashboard consuming:
  - Video stream endpoint.
  - Telemetry websocket endpoint.
  - Control API endpoint.
- Supports backend, mock, and offline data modes for development/operation.

### Tooling (`tools`)

- Runtime orchestration:
  - `start_live_stack.sh`
  - `start_ui_stack.sh`
- Offline analysis:
  - `analyse_bag_timing.py`
  - `analyse_bag_tracking.py`
  - `timing_contract.py`
  - `validate_canonical_metrics.py`
  - `check_live_timing_invariants.py`
  - `collect_live_timing_stats.py`

## 4) Repository folder taxonomy

Root-level purpose map:

- `ros2_ws/`
  - ROS workspace (`src`, `build`, `install`, `log`) for runtime and development.
- `infer_service/`
  - Detector service and profiling artifacts for inference boundary.
- `user-interface/`
  - Dashboard app and frontend build configuration.
- `tools/`
  - Operational scripts and analysis utilities.
- `bags/`
  - Experiment data organized by lifecycle stage:
    - `bags/live_camera/`: lean operational recordings.
    - `bags/raw/`: replay source bags for evaluation.
    - `bags/eval/`: replay outputs and evaluation artifacts.
- `reports/`
  - Analysis outputs (comparison/tracking reports).
- `docs/`
  - Supplemental documentation (non-root).
- `Written Logs/`
  - Weekly and daily engineering logs.
- `deprecated/`
  - Archived/legacy experiments not in active operational path.
- `hailo-rpi5-examples/`
  - Upstream/vendor-side resources and examples.

## 5) External dependency model

The live Hailo path relies on an external compose environment at:

- `~/pi-ai-kit-ubuntu`

Why this is external:

1. It packages hardware-specific runtime environment and service dependencies.
2. It keeps this repository focused on ROS orchestration and experiment logic.
3. It provides a stable container boundary for detector service.

Expected contract with this repo:

1. Container can run detector service process.
2. Service binds req/rep endpoint expected by inference client (default tcp://0.0.0.0:5556 inside container, host consumed as tcp://127.0.0.1:5556 in common local setup).
3. Hailo runtime dependencies are available inside container virtual environment.

## 6) Bag lifecycle and naming intent

### `bags/live_camera`

Use for operational sessions where low overhead matters.

Recommended naming:

- `YYYY-MM-DD__session_description`

Typical topics:

- `/camera/fps`
- `/detections`
- `/timing`
- `/target`

### `bags/raw`

Use for high-signal replay inputs and profiling.

Typical topics:

- `/detections`
- `/timing`
- `/tracks`
- `/target`
- `/timing_tracker`

### `bags/eval`

Use for replay outputs tied to tracker mode/config sweeps.

Naming often encodes:

1. replay date,
2. source run name,
3. tracker or parameter variant,
4. repetition id.

## 7) Operational interfaces and ports

Common endpoints:

- Detector service req/rep: `:5556`
- Web video server: `:8080`
- Control API: `:8090`
- Dashboard websocket: `:8765`
- Frontend dev server: `:5173` (default)

## 8) Why this structure works

The repository separates concerns by execution boundary:

1. ROS-time critical orchestration and decision nodes stay in `ros2_ws`.
2. Hardware-specific inference runtime is isolated in container service.
3. Human-facing visualization is independent in `user-interface`.
4. Analysis and validation remain scriptable/offline in `tools` and `reports`.

This split supports both live operation and repeatable scientific evaluation.

## 9) Reading order for new contributors

1. `README.md`
2. `REPO_DEEP_DIVE.md`
3. `RUNBOOK.md`

Then inspect package-level sources only for the subsystem you modify.

## 10) Current assumptions and drift warning

Validated against repository state on 2026-04-08.

If entrypoint scripts, topic names, or ports change, update all three root docs together:

1. `README.md`
2. `REPO_DEEP_DIVE.md`
3. `RUNBOOK.md`
