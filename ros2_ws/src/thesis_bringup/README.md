# thesis_bringup

Last reviewed: 2026-09-09

## Purpose

The runtime composition package: perception, TIM-MARS selected-target
validation, control, dashboard telemetry, and MAVROS monitoring, plus the
canonical configs and launch files. ament_python; depends on `thesis_msgs` and
`thesis_tracker`.

## Console scripts

### Canonical live runtime

| Executable | Module | Role |
| --- | --- | --- |
| `perception_camera_node` | `perception/` | Integrated camera capture + in-process Hailo YOLOv8s detection. |
| `target_memory_mars_node` | `tim_mars/` | TIM-MARS selected-target identity validation; the only controller-facing target authority. Publishes `/timing_target`. |
| `dashboard_bridge_node` | `dashboard/` | Telemetry HTTP/WebSocket bridge; publishes raw `/target` and the `/target_memory_mars` select/clear commands. |
| `control_ref_node` | `control/` | Selected target to body-frame velocity reference. `target_topic` defaults to `/target_memory_mars`. |

The canonical tracker (`tracker_node`, ByteTrack) belongs to `thesis_tracker`.

### Retained experimental / support

| Executable | Module | Role |
| --- | --- | --- |
| `perception_pipeline_node` | `perception/` | Modular image-topic perception + asynchronous Hailo RepVGG appearance-embedding worker (Issue #44). Base class of `perception_camera_node`. |
| `camera_capture_node` | `camera/` | Standalone `/camera/image_raw` publisher for the modular path (`camera_bringup.launch.py`) and high-resolution capture. |

### Support / development

| Executable | Module | Role |
| --- | --- | --- |
| `video_file_publisher_node` | `camera/` | Publishes `/camera/image_raw` from a local video file for replay/dev. |
| `mavros_imu_monitor_node` | `mavros/` | Pixhawk/MAVROS IMU liveness/status check for ground validation. It reports state only and does not command the aircraft. |

## Domains

| Module | Contents |
| --- | --- |
| `camera/` | Camera acquisition and video-file publishing nodes. |
| `perception/` | Preprocessing, Hailo runtime, the two perception nodes, and the ReID request executor. |
| `dashboard/` | Dashboard / WebSocket bridge, model catalogue, system metrics. |
| `tim_mars/` | The TIM-MARS algorithm, appearance memory, and the MARS ReID backend — see `thesis_bringup/tim_mars/README.md`. |
| `control/` | Target-to-control reference node and the state-aware control policy. |
| `mavros/` | MAVROS monitoring helper. |

## Config and launch

`config/`: `tim_mars_canonical.yaml` (canonical TIM-MARS parameters),
`tracker_*.yaml` (per-backend tracker parameters, consumed by `thesis_tracker`),
`mavros_pixhawk.yaml`.

`launch/`: `camera_bringup.launch.py` (modular-path camera side),
`eval_replay.launch.py` (bag playback + tracker + dashboard for tracker
evaluation).

## Rules

- `/target_memory_mars` is the only controller authority; raw `/target` never
  drives control.
- Detailed TIM-MARS behaviour belongs in `thesis_bringup/tim_mars/README.md`,
  not this package README.
- Configuration, message, and algorithm paths referenced by a prospective or
  frozen evidence contract must not be changed or moved outside the
  corresponding protocol — see
  `docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`.

## See also

- `thesis_bringup/tim_mars/README.md` — algorithm and canonical configuration
- `thesis_bringup/README.md` — internal Python layout
- `docs/RUNTIME_METRICS.md`, `docs/design/tim_tooling_index.md`
