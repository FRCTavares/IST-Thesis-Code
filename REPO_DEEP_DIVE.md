# Repository Deep Dive

Last reviewed: 2026-05-26

This document explains what this repository is for, how its parts interact, and how to reason about the folder layout.

Use this file for architecture understanding.
Use `RUNBOOK.md` for commands.
Use `README.md` for onboarding and path selection.

## 1) System objective

The repository implements an experimental ROS 2 pipeline that converts live camera frames into actionable target state for dashboard/control, with an active focus on selected-target identity maintenance through TIM, while preserving repeatability through bag replay and offline analysis.

Primary goals:

1. Real-time perception to target-state pipeline.
2. Selected-target identity maintenance under occlusion, hard crossings, detector misses, tracker ID switches, and distractors.
3. Deterministic and measurable timing behavior.
4. Reproducible experiment workflow (record -> replay -> analyse).
5. Operational dashboard visibility for human-in-the-loop work.

## 2) Deployment shapes and data flow

Live runtime now supports one active perception shape. The old external detector path is kept only as historical context.

### Shape I (default): integrated camera perception

1. `perception_camera_node` captures frames directly from the camera.
2. The same node performs preprocessing and Hailo inference in-process.
3. The node publishes `/detections`, `/timing`, and `/camera/dashboard`.
4. `tracker_node` publishes `/tracks`.
5. `dashboard_bridge_node` owns explicit target publication for dashboard and control consumers.
6. `target_memory_mars_node` publishes `/target_memory_mars`.
7. `control_ref_node` publishes `/control_ref/cmd_vel`.

Runtime shape:

    perception_camera_node
        -> /detections + /timing + /camera/dashboard
        -> tracker_node
        -> /tracks
        -> dashboard_bridge_node
        -> /target
        -> target_memory_mars_node
        -> /target_memory_mars
        -> control_ref_node

Default live command:

    ./tools/start_live_stack.sh

Recording command:

    ./tools/start_live_stack.sh --record --tag <name>

Validated 2026-06-17 full-stack recording result:

- `/detections`: 29.92 Hz
- `/tracks`: 29.91 Hz
- `/target`: 29.89 Hz
- `/target_memory_mars`: 29.34 Hz
- `/control_ref/cmd_vel`: 29.91 Hz
- thermal status: `throttled=0x0`

### Removed path: external detector perception

The removed ZMQ/container perception path was removed from the active runtime after the 2026-06-04 cleanup.

It is no longer a rollback path. The supported live path is:

`perception_camera_node -> /detections + /timing + /camera/dashboard -> tracker -> /tracks -> dashboard_bridge_node -> /target`

### Replay path (evaluation)

1. `eval_replay.launch.py` plays a recorded bag.
2. Tracker + `dashboard_bridge_node` process replayed messages.
3. Replay outputs are recorded to `artifacts/bags/eval/` for offline analysis.

Conceptual chain:

`artifacts/bags/live_camera -> eval_replay.launch.py -> /tracks + /target + /timing_tracker + /timing_target -> artifacts/bags/eval -> analysis scripts -> reports`

Replay/eval note:

- Target selection is now strictly user-driven through `dashboard_bridge_node`.
- `POST /api/target` is the only supported way to select a target.
- There is no automatic target-selection fallback in replay or evaluation flows.
- When no target is explicitly selected, `/target` publishes the empty target state.

### TIM path

TIM is a selected-target memory layer, not a replacement for global multi-object tracking.

Its role is to decide whether the current tracker output still corresponds to the operator-selected target. It must be conservative when identity evidence is ambiguous.

Important output topics:

- `/target`: raw selected tracker target from the dashboard bridge.
- `/target_memory_mars`: TIM-filtered selected target, used only when TIM is valid and control-safe.
- `/target_memory_mars/status`: TIM diagnostics, including state, scores, reasons, and validity flags.

Core evaluation principle:

- correct selected target is good,
- wrong selected target is dangerous,
- lost target is safer than wrong target when identity is uncertain.

## 3) Component responsibilities

### ROS packages (`ros2_ws/src`)

- `thesis_bringup`
  - Launch composition and primary runtime nodes.
  - Owns `perception_camera_node`, `dashboard_bridge_node`, `target_memory_mars_node`, `control_ref_node`, and launch entrypoints.
- `thesis_inference_client`
  - Historical bridge package for the removed ZMQ/container path.
  - Not part of the active live runtime.
- `thesis_tracker`
  - Tracking backend abstraction (`sort`, `ocsort`, `bytetrack`, `deepsort`) and `/tracks` publication.
  - DeepSORT uses the MARS ReID model when configured with `models/reid/mars-small128.pb`.
- `thesis_msgs`
  - Shared message contracts (`Timing`, track/target messages).

### Inference service (`infer_service`)

- Historical ZMQ-facing helpers are retained only where still useful for offline/debug workflows.
- `opt/tappas_runtime_3_31`
  - Optional local runtime assets used by the integrated camera path when available.

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
  - Deprecated on 2026-06-17 during tool cleanup.
  - Historical validation helpers were removed because they were not part of the current official evaluation path.
  - `timing_contract.py`

### Startup orchestration contract (`tools/start_live_stack.sh`)

`start_live_stack.sh` is the operational contract for live sessions and is organized as deterministic phases:

- Host preflight: stale-process cleanup, camera media graph checks, and an optional stream probe only when requested.
- Environment setup: ROS overlay sourcing + run-scoped log routing.
- Perception readiness:
  - Host `perception_camera_node` startup using the integrated camera path.
  - Optional local TAPPAS runtime assets are used when present.
- Downstream graph startup: tracker, dashboard bridge, web video, and control.
- Runtime shell loop with `status`, `ids`, `target <id>`, `clear-target`, `clear`, and `stop` commands.

### Tracker baselines and TIM framing

The active tracker baselines are:

- SORT
- OCSORT
- ByteTrack
- DeepSORT MARS

DeepSORT MARS is the current strong appearance-based baseline. It performs full multi-object tracking with learned ReID features. TIM instead targets a narrower selected-target problem: maintaining the operator-selected person while avoiding wrong-target output.

This distinction matters for claims:

- TIM should not be presented as a generic DeepSORT replacement.
- TIM should be evaluated as a lightweight selected-target memory layer.
- The fair comparison is selected-target correctness, wrong-target duration, lost duration, target-not-visible intervals, and runtime cost.

Notable reliability behavior:

- Camera startup has bounded retries for known TEVS failure signatures.
- Integrated-camera mode is fail-fast on host Hailo init unless stub fallback is explicitly enabled.
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
- `artifacts/bags/live_camera/`
  - Live recordings produced by the live stack.
- `artifacts/bags/eval/`
  - Replay outputs and evaluation artifacts.
- `artifacts/reports/`
  - Archived historical analysis outputs.
- `reports/`
  - Current default output root for timing and tracking analyses.
- `figures/`
  - Current default figure output root for timing analyses.
- `docs/Daily-Logs/`
  - Weekly and daily engineering logs.
- `deprecated/`
  - Archived experiments not in active path (removed scripts, historical traces, superseded artifacts).
- `hailo-rpi5-examples/` is expected outside the active repo, usually under `$HOME/hailo-rpi5-examples`.
  - Upstream/vendor resources.

### Key locations and model artifacts

- `models/hef/` — compiled Hailo engine files used by integrated camera inference when present.
- `models/reid/` — re-identification models used by tracker evaluation flows.
- `artifacts/bags/live_camera/` - source recordings from live sessions.
- `artifacts/bags/eval/` - replay outputs and derived artifacts used by analysis scripts.

If you need to add new model artifacts, prefer a clear subfolder under `models/` and add a short README describing provenance and expected runtime (device/format).

## 5) External dependency model

The active runtime no longer depends on the removed compose/container path.

Current runtime contract:

1. `tools/start_live_stack.sh` starts the integrated camera perception path.
2. `perception_camera_node` runs camera capture, Hailo inference, `/detections`, `/timing`, and `/camera/dashboard`.
3. ROS nodes publish detections, tracks, target memory, dashboard video, timing, and optional bag recordings.
4. Hailo example resources, when needed by setup scripts, are expected outside the active repository, usually under `$HOME/hailo-rpi5-examples`.

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

- `src_stamp_ns` belongs to source or sensor time and is not guaranteed comparable to host monotonic timing.
- `pub_dt_ms`, `det_out_fps`, and `camera_input_fps` are cadence-derived metrics, not direct stage timers.

Full old-to-new field mapping, producer/consumer matrix, and deprecation plan: `TIMING_FIELD_AUDIT.md`.

Analysis pipeline:

1. Live sampling: `tools/analysis/collect_live_timing_stats.py`
2. Invariant checks: `tools/analysis/check_live_timing_invariants.py`
3. Schema/key checks are now covered by the active official evaluation scripts.
4. Queue-buffer policy is documented in the current live-stack configuration instead of a standalone validation helper.
5. Offline bag analytics: `tools/analysis/analyse_bag_timing.py` and `tools/analysis/analyse_bag_tracking.py`

Default output locations:

- Timing reports: `reports/timing/`
- Timing figures: `figures/timing/`
- Tracking reports: `reports/tracking/`

## 6.1) Selected-target correctness evaluation

TIM evaluation uses interval annotations to classify the output stream over time.

Core categories:

- correct output: system publishes the selected visual target,
- wrong output: system publishes a distractor,
- lost output: selected target is visible but system publishes no valid target,
- target not visible: selected target cannot be reliably identified in the frame.

Current hard re-entry comparison:

| Method | Correct duration [s] | Wrong duration [s] | Lost duration [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw OCSORT `/target` | 66.400 | 40.450 | 21.200 | 0.519 | 0.316 | 0.166 |
| OCSORT + TIM `/target_memory_mars` | 91.350 | 35.550 | 1.150 | 0.713 | 0.278 | 0.009 |
| Raw DeepSORT MARS `/target` | 87.600 | 9.150 | 31.350 | 0.684 | 0.071 | 0.245 |

Interpretation:

- OCSORT + TIM improves continuity and correct duration but still has too much wrong-target duration.
- DeepSORT MARS is not perfectly identity-stable, but it is much safer against wrong-target output.
- TIM Final should reduce wrong-target duration towards DeepSORT MARS while keeping runtime cost closer to OCSORT/TIM.

## 7) Operational interfaces and ports

Common endpoints:

- Web video server: `:8080`
- Control API: `:8090`
- Dashboard WebSocket: `:8765`
- Frontend dev server: `:5173` (default)

### Failure domains and first evidence

When live runtime fails, check evidence in this order:

1. `ros2_ws/log/live_stack/latest/` process logs such as `camera.log`, `perception_camera.log`, and `inference.log`.
2. Kernel camera state (`journalctl -k -b`) for CSI or I2C faults.
3. ROS graph and transport checks (`ros2 node list`, `ros2 topic list`, port checks).

This sequence reduces false debugging paths by separating camera-driver faults from graph-level faults.

## 8) Why this structure works

The repository separates concerns by responsibility rather than a single rigid deployment boundary:

1. ROS-critical orchestration and runtime nodes stay in `ros2_ws`.
2. Integrated-camera mode minimizes inference transport latency for live operation.
3. Removed removed runtime paths are kept out of the operational workflow.
4. UI remains independently runnable in `user-interface`.
5. Analysis and validation stay scriptable and reproducible in `tools` plus the report roots.

This supports both day-to-day live operation and controlled scientific evaluation.

## 9) Reading order for contributors

1. `README.md`
2. `RUNBOOK.md`
3. `REPO_DEEP_DIVE.md`
4. `LIVE_STACK_CAMERA_RECOVERY.md` (hardware incidents)

Then inspect package-level source files for the subsystem you modify.

## 10) Drift warning and update policy

Validated against repository state on 2026-05-04.

If startup flags, topic names, ports, tracker baselines, TIM topics, evaluation metrics, or timing contracts change, update these root docs together:

1. `README.md`
2. `RUNBOOK.md`
3. `REPO_DEEP_DIVE.md`

If camera diagnostics or migration gates change materially, update these as well:

1. `LIVE_STACK_CAMERA_RECOVERY.md`

Contributing checklist (quick):

1. Run the relevant live-start script locally and confirm the affected topics are published.
2. Update `README.md` and `REPO_DEEP_DIVE.md` with any changed flags, ports, or topic names.
3. Add a small runnable example for UI changes under `user-interface/` and ensure `npm ci` passes.
