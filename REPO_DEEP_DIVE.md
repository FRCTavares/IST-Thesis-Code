# Repository Deep Dive

This document explains what this repository is for, how its parts interact, and how to reason about the folder layout.

Use this file for architecture understanding.
Use `RUNBOOK.md` for commands.
Use `README.md` for onboarding and path selection.

## 1) System objective

The repository implements an experimental ROS 2 pipeline that converts live camera frames into actionable target state for dashboard/control, while preserving repeatability through bag replay and offline analysis.

Primary goals:

1. Real-time perception to target-state pipeline.
2. Deterministic and measurable timing behavior.
3. Reproducible experiment workflow (record -> replay -> analyze).
4. Operational dashboard visibility for human-in-the-loop work.

## 2) Deployment shapes and data flow

Live runtime supports two perception shapes.

### Shape S (default): single-process perception

1. Camera publishes `/camera/image_raw`.
2. `perception_pipeline_node` subscribes directly and performs preprocessing + Hailo inference in-process.
3. Node publishes `/detections` and `/timing`.
4. Tracker publishes candidate tracks; `dashboard_bridge_node` owns explicit target publication for control and dashboard consumers.

Conceptual chain:

`camera -> /camera/image_raw -> perception_pipeline_node -> /detections -> tracker -> /tracks -> dashboard_bridge_node -> /target -> control/dashboard`

### Shape Z (rollback): legacy ZMQ path

1. Camera publishes `/camera/image_raw`.
2. `inference_client_node` sends frames over ZMQ req/rep to container `detection_zmq.py` service.
3. Inference client publishes `/detections` and `/timing`.
4. Downstream target publication still flows through `dashboard_bridge_node`.

Conceptual chain:

`camera -> /camera/image_raw -> inference_client_node (ZMQ req/rep) -> detection_zmq -> /detections -> tracker -> /tracks -> dashboard_bridge_node -> /target`

### Replay path (evaluation)

1. `eval_replay.launch.py` plays a recorded bag.
2. Tracker + `dashboard_bridge_node` process replayed messages.
3. Replay output is recorded to `bags/eval` for offline analysis.

Conceptual chain:

`bags/raw -> eval_replay.launch.py -> /tracks + /target + /timing_tracker + /timing_target -> bags/eval -> analysis scripts -> reports`

Replay/eval note:

- Target selection is now strictly user-driven through `dashboard_bridge_node`.
- `POST /api/target` is the only supported way to select a target.
- There is no automatic target-selection fallback in replay or evaluation flows.
- When no target is explicitly selected, `/target` publishes the empty target state.

## 3) Component responsibilities

### ROS packages (`ros2_ws/src`)

- `thesis_bringup`
  - Launch composition and primary runtime nodes.
  - Owns `camera_capture_node`, `perception_pipeline_node`, `dashboard_bridge_node`, `control_ref_node`, and launch entrypoints.
- `thesis_inference_client`
  - Legacy bridge from ROS image topic to container detector service via ZMQ.
  - Used only in `--perception-mode legacy`.
- `thesis_tracker`
  - Tracking backend abstraction (`sort`, `ocsort`, `bytetrack`) and `/tracks` publication.
- `thesis_msgs`
  - Shared message contracts (`Timing`, track/target messages).

### Inference service (`infer_service`)

- `detection_zmq.py`
  - Legacy detector service process (container-side).
- `zmq_pub.py`
  - Utility helper for ZMQ-facing workflows.
- `opt/tappas_runtime_3_31`
  - Optional local runtime assets used by single-process mode when available.

### Frontend (`user-interface`)

- React/TypeScript dashboard consuming:
  - MJPEG video stream (`:8080` by default)
  - telemetry WebSocket (`:8765`)
  - control API (`:8090`)
- Supports `backend`, `mock`, and `offline` data modes.

### Tooling (`tools`)

- Runtime orchestration:
  - `start_live_stack.sh`
  - `start_ui_stack.sh`
- Analysis/validation:
  - `analyse_bag_timing.py`
  - `analyse_bag_tracking.py`
  - `collect_live_timing_stats.py`
  - `check_live_timing_invariants.py`
  - `validate_canonical_metrics.py`
  - `decide_queue_buffer_default.py`
  - `timing_contract.py`

### Startup orchestration contract (`tools/start_live_stack.sh`)

`start_live_stack.sh` is the operational contract for live sessions and is organized as deterministic phases:

- Host preflight: stale-process cleanup, camera media graph checks, and stream probe.
- Environment setup: ROS overlay sourcing + run-scoped log routing.
- Perception readiness by mode:
  - `legacy`: compose container + `detection_zmq.py` req/rep readiness (`:5556`).
  - `single-process`: host `perception_pipeline_node` startup (optional local tappas runtime assets).
- Downstream graph startup: tracker/dashboard/control/web video.
- Runtime shell loop with `status`, `clear`, `stop` commands.

Notable reliability behavior:

- Camera startup has bounded retries for known TEVS failure signatures.
- Single-process mode is fail-fast on host Hailo init unless stub fallback is explicitly enabled.
- Per-run logs are split by process under `ros2_ws/log/live_stack/<run-id>/`.

## 4) Repository folder taxonomy

Root-level purpose map:

- `ros2_ws/`
  - ROS workspace (`src`, `build`, `install`, `log`) for runtime and development.
- `infer_service/`
  - Legacy detector service and runtime resources.
- `user-interface/`
  - Dashboard app and frontend build configuration.
- `tools/`
  - Operational scripts and analysis utilities.
- `bags/`
  - Experiment data:
    - `bags/live_camera/`: lean operational recordings.
    - `bags/raw/`: replay source bags.
    - `bags/eval/`: replay outputs and artifacts.
- `reports/`
  - Analysis outputs (timing/tracking/compare).
- `Written Logs/`
  - Weekly and daily engineering logs.
- `deprecated/`
  - Archived experiments not in active path (legacy scripts, historical traces, superseded artifacts).
- `deprecated/hailo-rpi5-examples/`
  - Upstream/vendor resources.

## 5) External dependency model

The legacy container path depends on a compose environment at:

- `$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu` (primary)
- `~/pi-ai-kit-ubuntu` (legacy fallback)

Contract for legacy mode:

1. Container starts and runs `detection_zmq.py`.
2. Service binds req/rep endpoint expected by inference client (`tcp://0.0.0.0:5556` inside container).
3. Hailo runtime dependencies exist in the container venv.

Single-process mode does not require per-frame ZMQ transport, but can still consume local runtime assets under `infer_service/opt/tappas_runtime_3_31` when present.

## 6) Timing contract and analysis model

Canonical timing fields are defined in `tools/timing_contract.py`.

- `/timing`: `pre_ms`, `container_queue_ms`, `zmq_roundtrip_ms`, `infer_ms`, `e2e_det_ms`, `pub_dt_ms`
- `/timing_tracker`: `track_ms`
- `/timing_target`: `e2e_target_ms`

Canonical timing vocabulary used across runtime, analysis, and docs:

- `e2e_det_ms`: camera callback seen -> detection publish completion.
- `pub_dt_ms`: detection publish cadence interval.
- `det_out_fps`: detection output rate derived from `/detections` callback cadence.
- `camera_input_fps`: camera publish FPS from `/camera/fps`.
- `container_queue_ms`: pre-infer wait before inference starts.
- `infer_ms`: inference compute stage runtime.
- `track_ms`: tracker compute stage runtime.
- `e2e_target_ms`: camera callback seen -> target publish completion.
- `/timing_target` remains meaningful even when no target is selected because the bridge still publishes explicit empty-target outputs.

Clock-domain clarity:

- `src_stamp_ns` belongs to source/sensor time domain and is not guaranteed comparable to host monotonic timing.
- `pub_dt_ms`, `det_out_fps`, and `camera_input_fps` are cadence-derived metrics, not direct stage timers.

Full old-to-new field mapping, producer/consumer matrix, and deprecation plan: `TIMING_FIELD_AUDIT.md`.

Analysis pipeline:

1. Live sampling: `tools/collect_live_timing_stats.py`
2. Invariant checks: `tools/check_live_timing_invariants.py`
3. Schema/key checks: `tools/validate_canonical_metrics.py`
4. Queue-buffer decision gate: `tools/decide_queue_buffer_default.py`
5. Offline bag analytics: `tools/analyse_bag_timing.py` and `tools/analyse_bag_tracking.py`

## 7) Operational interfaces and ports

Common endpoints:

- Legacy detector req/rep: `:5556` (legacy mode only)
- Web video server: `:8080`
- Control API: `:8090`
- Dashboard WebSocket: `:8765`
- Frontend dev server: `:5173` (default)

### Failure domains and first evidence

When live runtime fails, check evidence in this order:

1. `ros2_ws/log/live_stack/latest/` process logs (`camera.log`, `perception_pipeline.log`, `inference.log`, etc.).
2. Kernel camera state (`journalctl -k -b`) for CSI/I2C faults.
3. ROS graph/transport checks (`ros2 node list`, `ros2 topic list`, port checks).

This sequence reduces false debugging paths by separating camera-driver faults from graph-level faults.

## 8) Why this structure works

The repository separates concerns by responsibility rather than a single rigid deployment boundary:

1. ROS-critical orchestration and runtime nodes stay in `ros2_ws`.
2. Single-process mode minimizes inference transport latency for live operation.
3. Legacy container mode remains available as rollback path.
4. UI remains independently runnable in `user-interface`.
5. Analysis/validation stays scriptable and reproducible in `tools` + `reports`.

This supports both day-to-day live operation and controlled scientific evaluation.

## 9) Reading order for contributors

1. `README.md`
2. `RUNBOOK.md`
3. `REPO_DEEP_DIVE.md`
4. `LIVE_STACK_CAMERA_RECOVERY.md` (hardware incidents)
5. `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md` (performance context)

Then inspect package-level source files for the subsystem you modify.

## 10) Drift warning and update policy

Validated against repository state on 2026-04-15.

If startup flags, topic names, ports, or timing contracts change, update these root docs together:

1. `README.md`
2. `RUNBOOK.md`
3. `REPO_DEEP_DIVE.md`

If camera diagnostics or migration gates change materially, update these as well:

1. `LIVE_STACK_CAMERA_RECOVERY.md`
2. `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md`
