# Architecture

Last reviewed: 2026-10-13

## Purpose

One-page map of the live system: what each ROS 2 node does, which topic carries
what, and which topic may command the aircraft. Algorithm detail lives in
[algorithm/](algorithm/README.md); package-level contracts live in each package
README.

## Dataflow

```
perception_camera_node        CSI camera + in-process Hailo YOLOv8s
  -> /detections, /timing, /camera/fps, /camera/dashboard
tracker_node                  ByteTrack (SORT / OC-SORT / DeepSORT selectable)
  -> /tracks, /timing_tracker
dashboard_bridge_node         HTTP/WebSocket bridge to the dashboard
  -> raw /target (telemetry + selection mirror only)
  -> /target_memory_mars/select, /target_memory_mars/clear
target_memory_mars_node       TIM-MARS identity memory
  -> /target_memory_mars        <- the ONLY controller-authoritative target
  -> /target_memory_mars/status, /timing_target
control_ref_node              target -> body-frame velocity reference
  -> /control_ref/cmd_vel, /control_ref/diagnostics
  -> optional MAVROS setpoint mirror (--control-mavros)
```

## Rules that must not be broken

1. `/target_memory_mars` is the only target the controller consumes. Raw
   `/target`, tracker output and detector candidates never acquire motion
   authority.
2. `control_ref_node` publishes zero velocity on a stale, lost or missing target.
3. TIM-MARS prefers *no target* to a *wrong target*.
4. The dashboard is a command surface into TIM-MARS, never the identity
   authority.
5. `/camera/image_raw` is off by default (~26 MiB/s of DDS traffic at 640x480);
   recording modes that need it switch it on.

## Packages

| Package | Type | Owns |
| --- | --- | --- |
| `thesis_msgs` | ament_cmake | Custom interfaces (`Timing`, `Track2DArray`, `TargetState`, ...) |
| `thesis_tracker` | ament_python | `tracker_node` and the SORT / OC-SORT / ByteTrack / DeepSORT backends |
| `thesis_bringup` | ament_python | Perception, TIM-MARS, control, dashboard bridge, MAVROS monitor, configs, launch files |

See [ros2_ws/README.md](../ros2_ws/README.md) for node and executable tables.

## Configuration

| File | Purpose |
| --- | --- |
| `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml` | TIM-MARS parameters; the launcher passes it with `--params-file`, no threshold is duplicated on the command line |
| `ros2_ws/src/thesis_bringup/config/tracker_*.yaml` | Per-tracker parameters |
| `ros2_ws/src/thesis_bringup/config/mavros_pixhawk.yaml` | MAVROS / Pixhawk link |
| `tools/lib/live_defaults.sh` | Launcher defaults (resolution, FPS, recording thresholds) |

## Timing

Three timing topics (`/timing`, `/timing_tracker`, `/timing_target`) follow
schema v4 and three separate clock domains; see
[RUNTIME_METRICS.md](RUNTIME_METRICS.md). Coordinate and image-time handling:
[algorithm/coordinate_image_time_contract.md](algorithm/coordinate_image_time_contract.md);
controller-facing freshness:
[algorithm/output_freshness_contract.md](algorithm/output_freshness_contract.md).

## Control and flight link

`control_ref_node` outputs a body-frame velocity reference; the state-aware
policy is in [control/](control/README.md). MAVROS mirroring is opt-in
(`--control-mavros`) and flight use follows [flight/](flight/README.md).
