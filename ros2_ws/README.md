# ros2_ws

Last reviewed: 2026-09-09

## Purpose

The ROS 2 implementation of the TIM-MARS system: message contracts, the tracker,
and the runtime composition (perception, TIM-MARS, control, dashboard, MAVROS
monitoring).

Distro: ROS 2 Jazzy. `ROS_DOMAIN_ID=42`.

This README covers the workspace and package boundaries. Day-to-day operation
lives in `docs/OPERATIONS.md` and `tools/README.md`; the TIM-MARS
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

See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the node and topic map.

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
- **Retained experimental path:** `camera_capture_node`
  publishing `/camera/image_raw` + `perception_pipeline_node` running the
  detector and an asynchronous Hailo RepVGG appearance-embedding worker. Built
  for the embedded-ReID comparison; still executable and tested, and
  `PerceptionPipelineNode` is also the base class of `perception_camera_node`.
  It is not a co-equal live runtime.

## Configuration and launch

`src/thesis_bringup/config/`: `tim_mars_canonical.yaml` (canonical TIM-MARS
parameters), `tracker_{sort,ocsort,bytetrack,deepsort}.yaml`,
`mavros_pixhawk.yaml`.

`src/thesis_bringup/launch/`: `camera_bringup.launch.py` (the modular-path
camera side), `eval_replay.launch.py` (bag playback + `tracker_node` +
`dashboard_bridge_node` for inspecting a recorded run).

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
- Operational procedures live in `docs/OPERATIONS.md` and `tools/README.md`,
  not here.
- `build/`, `install/`, and `log/` are generated and never committed.
- Changing a message, topic or canonical parameter file affects recorded
  bags and the launcher; update `tools/` and `docs/` in the same change.

## See also

- `tools/README.md` — build, live operation, host and flight tools
- `docs/RUNTIME_METRICS.md` — Timing schema v4 vocabulary
- `docs/CONTRIBUTING.md` — checks and change rules
- `docs/debug/` — Hailo, camera, and host recovery procedures
