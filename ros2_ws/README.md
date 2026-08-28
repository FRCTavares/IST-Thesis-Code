# ros2_ws workspace

Local source of truth for the ROS 2 workspace under `ros2_ws/`: packages, nodes,
topics, message contracts, launch files, and workspace-scoped commands.

Distro: ROS 2 Jazzy. `ROS_DOMAIN_ID=42`. Workspace root: `ros2_ws/`.

For day-to-day operational commands (live stack, recording, replay analysis) see
the repository root `README.md`. For the TIM-MARS algorithm and its canonical
configuration see
`src/thesis_bringup/thesis_bringup/tim_mars/README.md`.

## 1. Layout

```
ros2_ws/
  src/
    thesis_msgs/      custom message package (ament_cmake)
    thesis_tracker/   multi-backend tracker node (ament_python)
    thesis_bringup/   perception, TIM-MARS, control, dashboard, mavros (ament_python)
  build/  install/  log/   colcon outputs (git-ignored)
```

There are three source packages. There is no `thesis_inference_client` package
and no `src/*/nodes/` layout outside `thesis_tracker`; earlier revisions that
used those are historical.

## 2. Packages

### thesis_msgs

Custom interfaces shared across perception, tracking, target memory, and the
asynchronous appearance-embedding transport. Built with `rosidl` from
`msg/*.msg` (see `CMakeLists.txt`).

| Message | Purpose |
| --- | --- |
| `Track2D` | one tracked box: `id, cx, cy, w, h, score, label` |
| `Track2DArray` | header, frame/timestamp metadata, `Track2D[] tracks` |
| `TargetState` | selected-target box + score/quality + callback timestamps |
| `Timing` | schema v3 per-stage timestamps and derived latency/cadence metrics, plus deprecated compatibility fields (removal plan in `tools/timing_contract.py`; vocabulary in root `README.md` section 5.1) |
| `AppearanceEmbeddingRequest` | causal request id, full backend/embedding-space contract, host-monotonic submit/deadline, source observation and identity provenance, source bbox (xyxy), owned BGR8 crop |
| `AppearanceEmbeddingResult` | request id, echoed backend contract, start/complete timestamps, `succeeded` flag, `embedding[]`, `error` |

### thesis_tracker

Multi-object tracker node with selectable appearance-free and appearance-based
backends.

- Node: `thesis_tracker/nodes/tracker_node.py` (console script `tracker_node`).
- Backends: `sort_backend`, `ocsort_backend`, `bytetrack_backend`,
  `deepsort_core_backend` under `thesis_tracker/backends/`.
- Shared Kalman/association core: `thesis_tracker/core/sort_tracker.py`.

Subscribes `/detections` (`vision_msgs/Detection2DArray`), `/timing`
(`thesis_msgs/Timing`), and `/camera/image_raw` (only consumed by
appearance-based backends). Publishes `/tracks` (`thesis_msgs/Track2DArray`)
and `/timing_tracker`.

Node parameter defaults: `tracker_type=sort`, `min_score=0.35`. The per-backend
YAML files in `thesis_bringup/config/` override these; the live-stack default is
ByteTrack. The former `thesis_tracker_node` compatibility executable has been
removed.

### thesis_bringup

Runtime composition and application nodes.

Console scripts (`setup.py`):

| Executable | Module | Role |
| --- | --- | --- |
| `perception_camera_node` | `perception/perception_camera_node.py` | integrated camera + Hailo detector (canonical live path) |
| `perception_pipeline_node` | `perception/perception_pipeline_node.py` | image-topic perception pipeline + asynchronous Hailo RepVGG appearance worker |
| `camera_capture_node` | `camera/camera_capture_node.py` | standalone host camera acquisition publishing `/camera/image_raw` |
| `video_file_publisher_node` | `camera/video_file_publisher_node.py` | publishes `/camera/image_raw` from a local video file for replay/dev |
| `tracker_node` (in `thesis_tracker`) | — | see above |
| `dashboard_bridge_node` | `dashboard/dashboard_bridge_node.py` | telemetry/HTTP/WebSocket bridge; publishes raw `/target` and selection commands |
| `target_memory_mars_node` | `tim_mars/target_memory_mars_node.py` | TIM-MARS selected-target identity validation |
| `control_ref_node` | `control/control_ref_node.py` | selected target -> body-frame velocity reference |
| `mavros_imu_monitor_node` | `mavros/mavros_imu_monitor_node.py` | Pixhawk/MAVROS IMU liveness check for ground validation |

## 3. Two perception paths

The workspace contains two detector front ends. Neither supersedes the other.

### Integrated path (canonical live following)

`perception_camera_node` subclasses `PerceptionPipelineNode` and adds in-process
camera capture. It keeps the colour frame inside the perception process and
publishes only compact semantic outputs (`/detections`, `/timing`,
`/camera/fps`, `/camera/dashboard`). It deliberately does **not** publish the
full-rate `/camera/image_raw` DDS stream unless explicitly asked to (Issue #54);
no tracker/TIM/dashboard consumer needs it in this mode.

This is the path started by `tools/start_live_stack.sh` (integrated mode) and is
the frozen runtime used for the selected-person-following evidence.

### Modular camera -> pipeline path (raw image + embedded appearance offload)

`camera_capture_node` publishes `/camera/image_raw` (plus `/camera/dashboard`,
`/camera/fps`). `perception_pipeline_node` subscribes to that image topic, runs
the Hailo detector, publishes `/detections` and `/timing`, and additionally
hosts the asynchronous appearance-embedding worker:

- subscribes `AppearanceEmbeddingRequest` on `/appearance/reid/request`;
- runs the Hailo RepVGG person-ReID HEF;
- publishes `AppearanceEmbeddingResult` on `/appearance/reid/result`;
- publishes worker status on `/perception/reid/status`.

`camera_bringup.launch.py` brings up the camera side of this path.
`video_file_publisher_node` is an alternative `/camera/image_raw` source.

This path carries the embedded-deployment evidence for extending Hailo
acceleration from detection to appearance-embedding inference. It is exercised by
the `tools/experiments/run_p044_*` load, contention, soak, and fault matrices
(Issue #44, closed). It is not the default live-following runtime because the
frozen flight profile avoids the full-rate raw-image transport.

## 4. TIM-MARS in this workspace

- Pure algorithm: `src/thesis_bringup/thesis_bringup/tim_mars/target_memory.py`
  (`TargetIdentityMemory`).
- ROS node: `src/thesis_bringup/thesis_bringup/tim_mars/target_memory_mars_node.py`.
- Canonical configuration:
  `src/thesis_bringup/config/tim_mars_canonical.yaml` (loaded via
  `--params-file`; launchers override only runtime-specific values).
- Module map and design contract:
  `src/thesis_bringup/thesis_bringup/tim_mars/README.md`.

Appearance evidence in the canonical algorithm is computed **in process** by the
CPU MARS `mars-small128` backend (`tim_mars/mars_reid_backend.py` +
`tim_mars/appearance_attachment.py`), cropping from the appearance-image topic
(`appearance_image_topic`, default `/camera/dashboard`).

The node can also consume embeddings from the cross-process Hailo RepVGG worker
described in section 3 (`appearance_async_reid_enabled`, default **false**;
request/result topics `/appearance/reid/request` and `/appearance/reid/result`).
This transport is disabled in the canonical algorithm and is used only for
Issue #44 contention and latency measurement.

`target_memory_mars_node` subscribes:

- `/tracks` (`thesis_msgs/Track2DArray`);
- `/target_memory_mars/select` (`std_msgs/UInt32`) and
  `/target_memory_mars/clear` (`std_msgs/Empty`);
- optionally the mirrored raw selection on `/target` (`thesis_msgs/TargetState`);
- optionally an appearance image and the async ReID result stream.

and publishes:

- `/target_memory_mars` (`thesis_msgs/TargetState`);
- `/target_memory_mars/status` (`std_msgs/String`, JSON diagnostics).

## 5. Runtime dataflow and controller authority

```
perception_camera_node
  -> /detections (vision_msgs/Detection2DArray), /timing (thesis_msgs/Timing)
  -> /camera/fps, /camera/dashboard
tracker_node
  -> /tracks (thesis_msgs/Track2DArray), /timing_tracker
dashboard_bridge_node
  -> /target (raw selected target, telemetry only), /timing_target
  -> /target_memory_mars/select, /target_memory_mars/clear
target_memory_mars_node
  -> /target_memory_mars (thesis_msgs/TargetState), /target_memory_mars/status
control_ref_node   (configured target_topic:=/target_memory_mars)
  -> /control_ref/cmd_vel (geometry_msgs/TwistStamped), optional MAVROS mirror
```

`/target_memory_mars` is the only controller-authoritative selected-target
output. Raw `/target` published by `dashboard_bridge_node` is telemetry and
selection-mirror plumbing.

`control_ref_node` is topic-agnostic: its own default `target_topic` is `/target`
for isolated bench sign-checks, but `tools/start_live_stack.sh` starts it with
`-p target_topic:=/target_memory_mars`, so raw `/target` cannot drive control in
the live stack. `control_ref_node` publishes zero velocity on a stale, lost, or
missing target.

## 6. Configuration files

`src/thesis_bringup/config/`:

- `tim_mars_canonical.yaml` — canonical TIM-MARS algorithm parameters.
- `tracker_sort.yaml`, `tracker_ocsort.yaml`, `tracker_bytetrack.yaml`,
  `tracker_deepsort.yaml` — per-backend tracker parameters.
- `mavros_pixhawk.yaml` — MAVROS/Pixhawk parameters.

## 7. Launch files

`src/thesis_bringup/launch/`:

### `camera_bringup.launch.py`

Brings up `camera_capture_node` with configurable device, media graph,
resolution, fps, dashboard stream, and opt-in sensor controls. Default capture
resolution 1280x720.

### `eval_replay.launch.py`

Plays a bag and runs `tracker_node` + `dashboard_bridge_node`, recording
`/tracks`, `/target`, `/timing_tracker`, `/timing_target` to
`bags/eval/<run_date>__eval__<bag>__<tracker>`. Arguments: `bag`,
`tracker` (default `sort`), `out_root`, `rate` (default `1.0`), `run_date`.
Deterministic TIM-MARS replay for evaluation is driven by
`tools/experiments/run_deterministic_tim_replay.py`, not by this launch file.

## 8. Build

Preferred (writes colcon logs under `ros2_ws/log/`):

```bash
tools/thesis_build.sh
tools/thesis_build.sh --packages-select thesis_bringup
```

Equivalent manual build from `ros2_ws/`:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## 9. Testing

```bash
# from ros2_ws/
colcon test
colcon test-result --verbose
```

Fast TIM-MARS checks:

```bash
pytest src/thesis_bringup/test/test_target_memory_synthetic.py
pytest src/thesis_bringup/test/test_target_memory_appearance.py
pytest src/thesis_bringup/test/test_target_memory_rank_aware_reacquisition.py
```

Repository-level tooling contracts live under `tools/tests/`.

## 10. Common commands

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=42

ros2 run thesis_tracker tracker_node
ros2 run thesis_bringup dashboard_bridge_node
ros2 run thesis_bringup target_memory_mars_node --ros-args --params-file src/thesis_bringup/config/tim_mars_canonical.yaml
ros2 run thesis_bringup control_ref_node
ros2 launch thesis_bringup eval_replay.launch.py bag:=<bag_path> tracker:=bytetrack
```

## 11. Troubleshooting (workspace scope)

1. Environment: source `/opt/ros/jazzy/setup.bash` then `install/setup.bash`;
   confirm `ROS_DOMAIN_ID` matches across terminals.
2. Package discovery: `ros2 pkg list | rg thesis_`.
3. Node graph: `ros2 node list`.
4. Topics: `ros2 topic list | rg 'detections|tracks|timing|target'`.
5. Logs: `ros2_ws/log/`.
6. Stale build artifacts: rebuild with `tools/thesis_build.sh`.

## 12. Maintenance

- Keep this README scoped to `ros2_ws/`. Operational and analysis commands live
  in the repository root `README.md`; algorithm detail lives in the TIM-MARS
  module README.
- Update this file when packages, console scripts, message contracts, launch
  files, or tracker configs change.
- `build/`, `install/`, and `log/` are generated and git-ignored.
