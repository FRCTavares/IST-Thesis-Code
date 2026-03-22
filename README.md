# Thesis Workspace

ROS 2 + Hailo runtime for person detection, tracking, target selection, and control-reference publication.

## Quick Links

- [RUNBOOK.md](RUNBOOK.md): command recipes and frozen operational procedures.
- [Written Logs/](Written%20Logs/): weekly plans, daily logs, and thesis notes.

## Current Frozen Baseline (Baseline B)

- Inference client queue size: 4
- Inference client workers: 3
- Queue behavior: bounded blocking queue with timeout wakeup (no busy-wait sleep loop)
- Comparison rule: change one variable at a time

Current controlled A/B experiment:

- A: camera publishes 1920x1080, inference client resizes to 640x640
- B: camera publishes 640x640, inference client skips resize
- Keep all other settings frozen

## System Overview

Pipeline (live mode):

1. Camera node publishes /camera/image_raw (and /camera/fps).
2. Inference client sends frames over ZMQ REQ/REP to container service.
3. Inference client publishes /detections and /timing.
4. Tracker consumes /detections and publishes /tracks and /timing_tracker.
5. Target selector consumes /tracks and publishes /target and /timing_target.
6. Control node consumes /target and publishes /control_ref/cmd_vel (optionally mirrored to MAVROS).
7. Dashboard bridge exposes telemetry over WebSocket (and optional MJPEG stream via web_video_server).

## Repository Map

### Hand-edited source

| Path | Purpose |
| --- | --- |
| ros2_ws/src/thesis_bringup/ | Launch files and utility nodes (camera, control, dashboard, synthetic perturbation nodes) |
| ros2_ws/src/thesis_inference_client/ | ZMQ ROS client that publishes detections/timing |
| ros2_ws/src/thesis_tracker/ | Unified tracker node (SORT, OC-SORT, ByteTrack backends) |
| ros2_ws/src/thesis_target_selector/ | Target selection logic and target timing |
| ros2_ws/src/thesis_msgs/ | Custom ROS message types (Timing, Track2D, Track2DArray, TargetState) |
| infer_service/ | Hailo container inference service (file mode + ROS REQ/REP mode) |
| tools/ | Runtime helpers and offline analysis scripts |
| tools/camera/ | Camera-specific utility scripts |

### Documentation

| Path | Purpose |
| --- | --- |
| RUNBOOK.md | Operational recipes |
| Written Logs/docs/ | Supporting docs (checklists, commands, integration notes) |
| Written Logs/W*/ | Weekly and daily execution logs |

## Important Note About Git-Ignored Folders

Some directories are intentionally ignored and may not appear in a fresh clone or in your current working directory until you run the pipeline.

Ignored/generated paths include:

- ros2_ws/build/
- ros2_ws/install/
- ros2_ws/log/
- bags/
- reports/
- figures/
- log/
- hailo-rpi5-examples/
- infer_service/opt/

Why this matters:

- Missing bags/, reports/, figures/, or log/ is expected before first run.
- Analysis scripts create output directories on demand.
- ros2_ws/install/ appears only after colcon build.

Optional bootstrap command if you want the directory skeleton visible now:

```bash
mkdir -p bags/raw bags/eval bags/live_camera bags/tmp reports/timing reports/tracking figures/timing figures/tracking log
```

## Workspace Setup

### Environment

```bash
export THESIS_ROOT=/home/francisco/Desktop/Thesis-Code
export ROS_DOMAIN_ID=42
```

### Build ROS workspace

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_bringup thesis_inference_client thesis_tracker thesis_target_selector thesis_msgs
source install/setup.bash
```

## Main Runtime Entry Points

### Preferred live startup

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

Useful flags:

- --tracker sort|ocsort|bytetrack
- --camera-width N --camera-height N
- --infer-queue-size N --infer-workers N
- --no-tracker --no-target --no-control --no-dashboard --no-web-video
- --control-mavros
- --rosbag

### Inference service mode switch

The container service in infer_service/detection_zmq.py selects mode with HAILO_FRAME_SOURCE:

- HAILO_FRAME_SOURCE=ros: ZMQ REQ/REP service on tcp://0.0.0.0:5556
- HAILO_FRAME_SOURCE=file: local file playback pipeline

## Launch Files That Actually Exist

In ros2_ws/src/thesis_bringup/launch/:

- camera_bringup.launch.py
- first_ros2_slice.launch.py
- eval_replay.launch.py
- eval_replay_occluded.launch.py
- eval_replay_ambiguous.launch.py

Notes:

- live.launch.py and replay.launch.py are not present in the current tree.
- Use tools/start_live_stack.sh for live operation.

## ROS Interfaces (Current)

| Topic | Type | Producer | Consumer |
| --- | --- | --- | --- |
| /camera/image_raw | sensor_msgs/Image | camera_capture_node | inference_client_node |
| /camera/dashboard | sensor_msgs/Image | camera_capture_node (or dashboard_resize_node) | web_video_server |
| /camera/fps | std_msgs/Float32 | camera_capture_node | dashboard_bridge_node |
| /detections | vision_msgs/Detection2DArray | inference_client_node | tracker_node |
| /tracks | thesis_msgs/Track2DArray | tracker_node | target_selector_node, dashboard_bridge_node |
| /target | thesis_msgs/TargetState | target_selector_node | control_ref_node, dashboard_bridge_node |
| /timing | thesis_msgs/Timing | inference_client_node | tracker_node, target_selector_node, dashboard_bridge_node |
| /timing_tracker | thesis_msgs/Timing | tracker_node | bag/analysis |
| /timing_target | thesis_msgs/Timing | target_selector_node | bag/analysis |
| /control_ref/cmd_vel | geometry_msgs/TwistStamped | control_ref_node | bag/control integration |

## Bag Naming Conventions

### Raw bags

Format:

```text
YYYY-MM-DD__slice__<tag>
```

### Eval bags

Format:

```text
YYYY-MM-DD__eval__<rawbag>__<tracker>
```

### Live camera bags

Format:

```text
YYYY-MM-DD__<session_description>
```

## Common Operations

### Eval replay

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<raw_bag_name> \
  tracker:=sort
```

### Record lean live session

```bash
cd $THESIS_ROOT/bags/live_camera
ros2 bag record --storage mcap \
  /camera/fps /detections /timing /target
```

### Analyse timing

```bash
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/raw/<bag_name>
```

Outputs:

- reports/timing/`<bag>`__timing.md
- figures/timing/`<bag>`/

### Analyse tracking

```bash
python3 tools/analyse_bag_tracking.py $THESIS_ROOT/bags/eval/<eval_bag_name>
```

Outputs:

- reports/tracking/<eval_bag_name>/summary.md
- reports/tracking/<eval_bag_name>/target_lock_timeseries.png
- reports/tracking/<eval_bag_name>/track_ms_cdf.png
- reports/tracking/<eval_bag_name>/reacq_hist.png

## Operational Guidance

### Lean operational mode (default for field/live validation)

- Record: /camera/fps, /detections, /timing, /target
- Avoid long-running debug subscribers that add load
- Keep tracker profiling outputs out of normal field captures unless needed

### Profiling mode

- Include /tracks and /timing_tracker when characterizing tracker behavior
- Use on controlled runs, not baseline operational sessions

## Known Drift To Watch

- RUNBOOK currently references tools/stop_live_stack.sh, which is not present in tools/.
- README should be treated as accurate for repository structure and runtime entry points as of this revision.
