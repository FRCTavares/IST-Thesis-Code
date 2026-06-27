# ros2_ws Workspace README

This document describes only the ROS 2 workspace under ros2_ws.
It is intended to be the local source of truth for packages, nodes, topics, launch files, configs, and day-to-day commands inside this workspace.

## 1. Workspace layout

Top-level folders:

- src: ROS 2 packages and source code
- build: colcon build artifacts
- install: colcon install artifacts and setup files
- log: build and runtime logs

Source packages in src:

- thesis_bringup
- thesis_tracker
- thesis_msgs
- thesis_inference_client

## 2. Packages and responsibilities

### thesis_bringup

Purpose:

- Runtime composition and core application nodes for perception-to-target workflow.
- Houses the TIM implementation and node wrapper.

Main paths:

- thesis_bringup/nodes
- launch
- config
- test

Console entry points:

- perception_camera_node
- perception_pipeline_node
- video_file_publisher_node
- dashboard_bridge_node
- control_ref_node
- mavros_imu_monitor_node
- target_memory_mars_node

### thesis_tracker

Purpose:

- Multi-backend tracker node and tracking backends.

Main paths:

- thesis_tracker/tracker_node.py
- thesis_tracker/backends

Tracker backends implemented:

- sort_backend
- ocsort_backend
- bytetrack_backend
- deepsort_core_backend

Console entry points:

- tracker_node
- thesis_tracker_node (legacy compatibility alias)

### thesis_msgs

Purpose:

- Shared message contracts between perception, tracking, target memory, and control.

Message definitions:

- msg/Track2D.msg
- msg/Track2DArray.msg
- msg/TargetState.msg
- msg/Timing.msg

### thesis_inference_client

Purpose:

- Legacy inference-client path for detector service connectivity.

Console entry points:

- detector_node
- inference_client_node

Notes:

- This package remains in the workspace for compatibility and historical flows.
- Current primary runtime path may use integrated perception nodes in thesis_bringup.

## 3. Core dataflow inside ros2_ws

Typical runtime chain:

1. Perception publishes detections and timing.
2. Tracker subscribes to detections and publishes tracks.
3. Dashboard bridge publishes raw selected target.
4. TIM node consumes tracks plus selection context and publishes memory-filtered target and diagnostics.
5. Control node consumes a target topic and publishes velocity reference.

Primary topics involved:

- /detections
- /tracks
- /target
- /target_memory_mars
- /target_memory_mars/status
- /timing
- /timing_tracker
- /timing_target

## 4. TIM implementation map

TIM core logic:

- src/thesis_bringup/thesis_bringup/target_memory.py

TIM ROS node wrapper:

- src/thesis_bringup/thesis_bringup/nodes/target_memory_mars_node.py

Appearance utilities:

- src/thesis_bringup/thesis_bringup/appearance_memory.py
- src/thesis_bringup/thesis_bringup/mars_reid_backend.py

Tests directly covering TIM:

- src/thesis_bringup/test/test_target_memory_synthetic.py
- src/thesis_bringup/test/test_target_memory_appearance.py
- src/thesis_bringup/test/test_target_memory_rank_aware_reacquisition.py

## 5. Node catalog (thesis_bringup)

### perception_camera_node

- Integrated camera capture + perception path.
- Publishes detection and timing telemetry for downstream nodes.

### perception_pipeline_node

- Alternate perception pipeline node variant.

### video_file_publisher_node

- Publishes frames from video sources into ROS topics for replay/experiments.

### dashboard_bridge_node

- Bridges runtime state to websocket/API for dashboard use.
- Publishes raw selected target on /target.
- Publishes timing_target metrics.

### target_memory_mars_node

- TIM ROS wrapper.
- Consumes tracks and optional appearance image stream.
- Accepts select/clear commands.
- Publishes filtered target and JSON diagnostics.

### control_ref_node

- Consumes a target topic and computes control reference commands.
- Publishes /control_ref/cmd_vel and optional MAVROS mirror output.

### mavros_imu_monitor_node

- MAVROS IMU monitoring helper node.

## 6. Tracker configuration files

Available tracker config YAMLs:

- src/thesis_bringup/config/tracker_sort.yaml
- src/thesis_bringup/config/tracker_ocsort.yaml
- src/thesis_bringup/config/tracker_bytetrack.yaml
- src/thesis_bringup/config/tracker_deepsort.yaml

MAVROS config:

- src/thesis_bringup/config/mavros_pixhawk.yaml

## 7. Launch files

### eval_replay.launch.py

Path:

- src/thesis_bringup/launch/eval_replay.launch.py

Purpose:

- Replays a bag.
- Starts tracker and dashboard bridge.
- Records evaluation output topics.

Arguments:

- bag
- tracker
- out_root
- rate
- run_date

### camera_bringup.launch.py

Path:

- src/thesis_bringup/launch/camera_bringup.launch.py

Purpose:

- Camera capture bringup with configurable device, resolution, fps, dashboard stream, and sensor controls.

## 8. Message contracts summary

### Track2D

- id, cx, cy, w, h, score, label

### Track2DArray

- header and frame-level timing metadata
- tracks array

### TargetState

- header and frame-level timing metadata
- id and bbox geometry
- score and quality

### Timing

- Rich stage timestamps and derived timing metrics across perception, tracker, and target callbacks
- Includes canonical metrics and legacy compatibility fields

## 9. Build and environment

From the workspace root ros2_ws:

Build:

```bash
colcon build --symlink-install
```

Source environment:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

Optional clean build folders:

```bash
rm -rf build install log
colcon build --symlink-install
```

## 10. Testing

Run all tests:

```bash
colcon test
colcon test-result --verbose
```

Run specific TIM tests quickly:

```bash
pytest src/thesis_bringup/test/test_target_memory_synthetic.py
pytest src/thesis_bringup/test/test_target_memory_appearance.py
pytest src/thesis_bringup/test/test_target_memory_rank_aware_reacquisition.py
```

## 11. Common run commands

Run tracker node:

```bash
ros2 run thesis_tracker tracker_node
```

Run dashboard bridge:

```bash
ros2 run thesis_bringup dashboard_bridge_node
```

Run TIM node:

```bash
ros2 run thesis_bringup target_memory_mars_node
```

Run control reference node:

```bash
ros2 run thesis_bringup control_ref_node
```

Replay evaluation launch:

```bash
ros2 launch thesis_bringup eval_replay.launch.py bag:=<bag_path> tracker:=bytetrack
```

## 12. Troubleshooting checklist (ros2_ws scope)

1. Verify environment sourcing:
   - source /opt/ros/jazzy/setup.bash
   - source ros2_ws/install/setup.bash
2. Verify package discovery:
   - ros2 pkg list | rg thesis_
3. Verify node graph:
   - ros2 node list
4. Verify expected topics:
   - ros2 topic list | rg 'target|tracks|timing|detections'
5. Check runtime logs:
   - ros2_ws/log
6. If build artifacts are stale, clean build/install/log and rebuild.

## 13. Maintenance notes

- Keep this README scoped to ros2_ws only.
- Update this file when adding/removing packages, nodes, launch files, messages, or tracker configs inside ros2_ws.
- For root-level scripts and non-ROS workspace tooling, document outside this README.
