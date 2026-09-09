# ros2_ws

Last reviewed: 2026-09-09

## Purpose

The ROS 2 implementation of the thesis system: message contracts, the tracker,
and the runtime composition (perception, TIM-MARS, control, dashboard, MAVROS
monitoring).

Distro: ROS 2 Jazzy. `ROS_DOMAIN_ID=42`.

This README covers the workspace and package boundaries. Day-to-day operation
lives in the repository `README.md` and `tools/README.md`; the TIM-MARS
algorithm lives in
`src/thesis_bringup/thesis_bringup/tim_mars/README.md`.

## Packages

| Package | Build type | Owns | Docs |
| --- | --- | --- | --- |
| `thesis_msgs` | ament_cmake | Custom ROS interfaces shared by the tracker, the runtime nodes, and the repository tooling. | `src/thesis_msgs/README.md` |
| `thesis_tracker` | ament_python | `tracker_node` and its SORT / OC-SORT / ByteTrack / DeepSORT backends. | `src/thesis_tracker/README.md` |
| `thesis_bringup` | ament_python | Runtime nodes (perception, TIM-MARS, control, dashboard, MAVROS support), plus the canonical configs and launch files. | `src/thesis_bringup/README.md` |

`src/` is tracked. `build/`, `install/`, and `log/` are colcon-generated and
git-ignored; `ros2_ws/log/` is the approved location for build and runtime logs.

## Canonical live dataflow

```
perception_camera_node       integrated camera + in-process Hailo YOLOv8s
  -> /detections (vision_msgs/Detection2DArray)
  -> /timing (thesis_msgs/Timing, schema v4)
  -> /camera/fps, /camera/dashboard
tracker_node                 ByteTrack (config/tracker_bytetrack.yaml)
  -> /tracks (thesis_msgs/Track2DArray), /timing_tracker
dashboard_bridge_node
  -> /target (raw selected target — telemetry / selection-mirror only)
  -> /target_memory_mars/select, /target_memory_mars/clear
target_memory_mars_node      TIM-MARS (config/tim_mars_canonical.yaml)
  -> /target_memory_mars (thesis_msgs/TargetState)   <- only controller authority
  -> /target_memory_mars/status, /timing_target
control_ref_node             target_topic default /target_memory_mars
  -> /control_ref/cmd_vel (geometry_msgs/TwistStamped); optional MAVROS mirror
```

`/target_memory_mars` is the only controller-authoritative selected target. Raw
`/target` is dashboard telemetry and selection-mirror plumbing and never
commands aircraft motion. `control_ref_node` publishes zero velocity on a
stale, lost, or missing target.

`/camera/image_raw` is off by default in the integrated live profile because
the perception / tracker / TIM-MARS / dashboard / controller path does not
consume it. It is auto-enabled by raw-recording workflows (`--record-raw`,
`--record-dataset`, `--source-record`) or forced explicitly via the camera
raw-publication option.

## Runtime variants

- **Canonical live runtime:** the integrated `perception_camera_node` path
  above, started by `tools/start_live_stack.sh`.
- **Retained experimental / reproduction path:** `camera_capture_node`
  publishing `/camera/image_raw` + `perception_pipeline_node` running the
  detector and an asynchronous Hailo RepVGG appearance-embedding worker. Built
  for the Issue #44 embedded-ReID comparison; still executable and tested, and
  `PerceptionPipelineNode` is also the base class of `perception_camera_node`.
  It is not a co-equal live runtime.

## Configuration and launch

`src/thesis_bringup/config/`: `tim_mars_canonical.yaml` (canonical TIM-MARS
parameters), `tracker_{sort,ocsort,bytetrack,deepsort}.yaml`,
`mavros_pixhawk.yaml`.

`src/thesis_bringup/launch/`: `camera_bringup.launch.py` (the modular-path
camera side), `eval_replay.launch.py` (bag playback + `tracker_node` +
`dashboard_bridge_node` for tracker evaluation). Deterministic TIM-MARS replay
is driven by `tools/experiments/run_deterministic_tim_replay.py`, not by a
launch file.

## Build and test

```bash
tools/thesis_build.sh                                   # whole workspace
tools/thesis_build.sh --packages-select thesis_bringup  # one package
```

Low-level workspace tests: `colcon test && colcon test-result --verbose` from
`ros2_ws/`. Repository tooling contracts live under `tools/tests/`.

## Rules

- Package-level ROS contracts belong in the package-root READMEs; this file
  stays at workspace scope.
- Operational and analysis procedures live in the repository `README.md` and
  `tools/README.md`, not here.
- `build/`, `install/`, and `log/` are generated and never committed.
- Configuration, message, algorithm, and evaluation paths referenced by a
  prospective or frozen evidence contract must not be changed or moved outside
  the corresponding protocol — see
  `docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`.

## See also

- `tools/README.md` — build, live operation, experiments
- `docs/RUNTIME_METRICS.md` — Timing schema v4 vocabulary
- `docs/design/tim_tooling_index.md` — replay / evaluation path authority
- `docs/debug/` — Hailo, camera, and host recovery procedures
