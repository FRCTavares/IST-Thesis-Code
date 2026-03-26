# Thesis workspace

## System architecture

This repository currently uses a ROS-native bridge architecture with a future backend extraction path:

- ROS perception and control stack in `ros2_ws/`
- Dashboard bridge node in `ros2_ws/src/thesis_bringup/` (WebSocket + control API)
- Video stream via `web_video_server`
- Frontend dashboard in `user-interface/`
- Backend placeholder in `backend/` for future service decoupling

Active data flow:

`Drone -> ROS Topics -> Dashboard Bridge + Video Server -> Dashboard`

## Quick reference

- **[RUNBOOK.md](RUNBOOK.md)** — Quick command recipes for core operations
- **[Written Logs/](Written%20Logs/)** — Weekly planning, daily logs, and useful commands

## Getting started

### 1) Frontend only (no ROS, no hardware)

```bash
cd user-interface
npm install
VITE_DASHBOARD_DATA_MODE=mock npm run dev
```

### 2) Live stack (ROS + camera + inference)

```bash
./tools/start_live_stack.sh
```

### 3) Replay and evaluate

Use the replay and analysis workflows in [RUNBOOK.md](RUNBOOK.md).

## Prerequisites

- ROS 2 Jazzy
- Python 3.10+
- Node.js 18+
- `colcon` (`pip install colcon-common-extensions`)
- Docker (for inference container workflows)
- Camera + Hailo setup for live runs

### Current frozen live baseline

- Inference queue size: `4`
- Inference worker threads: `3`
- Client queue behavior: blocking bounded queue (`queue.Queue`) with timeout wakeup
- Comparison rule: change one variable at a time (no multi-change tuning jumps)

Current next controlled experiment:

- Image-path
- A: `1920x1080` camera publish + client resize to `640x640`
- B: direct `640x640` camera publish + no client resize
- Keep all other settings fixed (see throughput workflow in [RUNBOOK.md](RUNBOOK.md))

### Live system status

- Dashboard MJPEG stream now uses sensor-data QoS compatibility (`qos_profile=sensor_data`) to avoid RELIABILITY mismatches with `/camera/dashboard` publishers.
- Dashboard box normalization is tied to the inference frame basis (`640x640`) via dashboard bridge `img_w/img_h`, matching detection bbox coordinates from the inference client.
- Dashboard model switching is now live through `POST /api/model` served by `dashboard_bridge_node` on port `8090`.
- If dashboard stream or overlays look wrong after updates, restart the full live stack so bridge/video nodes pick up the latest parameters.

---

## Folder map

### Source code (edited by hand)

| Path | Contents |
|---|---|
| `ros2_ws/src/thesis_bringup/` | Launch files for live and replay modes |
| `ros2_ws/src/thesis_inference_client/` | ZMQ client node for receiving detections |
| `ros2_ws/src/thesis_tracker/` | Multi-object tracker node (SORT, OC-SORT, ByteTrack) |
| `ros2_ws/src/thesis_target_selector/` | Target selection and lock FSM |
| `ros2_ws/src/thesis_msgs/` | Custom ROS 2 message definitions |
| `backend/` | Placeholder for future backend extraction from the current ROS-native bridge |
| `user-interface/` | React + TypeScript + Vite dashboard frontend |
| `infer_service/` | ZMQ inference service (runs in Hailo Docker container) |
| `tools/` | Analysis scripts: `analyse_bag_timing.py`, `analyse_bag_tracking.py` |
| `tools/camera/` | Camera-specific utilities and scripts |

### Documentation

| Path | Contents |
|---|---|
| `RUNBOOK.md` | Command recipes for record, replay, analyse, build |
| `Written Logs/` | Weekly plans, daily logs, thesis planning notes |
| `Written Logs/Other/` | Camera integration docs, useful commands |

### Recorded data (generated — do not edit by hand)

| Path | Contents |
|---|---|
| `bags/raw/` | Raw recorded bags from live runs (detections, timing) |
| `bags/eval/` | Eval bags from replay (tracks, target, timing_tracker) |
| `bags/live_camera/` | Camera validation and live perception test runs |
| `bags/tmp/` | Scratch space; safe to delete |

### Analysis outputs (generated)

| Path | Contents |
|---|---|
| `reports/timing/` | Timing analysis reports (latency, FPS) |
| `reports/tracking/` | Tracking analysis reports (MOT metrics, ID switches) |
| `reports/compare/` | Cross-tracker comparison reports |
| `reports/system/` | System performance and validation reports |
| `figures/timing/` | Timing plots (latency distributions, FPS over time) |
| `figures/tracking/` | Tracking plots (trajectories, pixel error) |
| `figures/compare/` | Cross-tracker comparison plots |

### Build artifacts (generated)

| Path | Contents |
|---|---|
| `ros2_ws/build/` | ROS 2 build output |
| `ros2_ws/install/` | ROS 2 install space (source this for overlays) |
| `ros2_ws/log/` | ROS 2 build logs |
| `build/` | Additional build artifacts |
| `install/` | Additional install artifacts |
| `log/` | System and build logs |

### External dependencies

| Path | Contents |
|---|---|
| `hailo-rpi5-examples/` | Hailo AI inference examples and setup scripts |

---

## Workspace setup

### Environment variables

```bash
# From repository root:
export THESIS_ROOT="$(pwd)"
export ROS_DOMAIN_ID=42  # Isolate from other ROS 2 systems
```

### ROS 2 workspace overlay

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

---

## Bag naming conventions

Use the canonical naming workflow in [RUNBOOK.md](RUNBOOK.md).

---

## Common commands

### Run dashboard frontend

```bash
cd $THESIS_ROOT/user-interface
npm install
npm run dev
```

Default behavior without env overrides is backend mode (`VITE_DASHBOARD_DATA_MODE=backend`).
For standalone frontend development, run with `VITE_DASHBOARD_DATA_MODE=mock`.

### Record a raw bag (file replay)

```bash
cd $THESIS_ROOT/bags/raw
ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker
# Then rename:
mv rosbag2_<timestamp> YYYY-MM-DD__slice__<tag>
```

### Record a live camera session (lean operational mode)

```bash
cd $THESIS_ROOT/bags/live_camera
ros2 bag record --storage mcap \
  --topics /camera/fps /detections /timing /target
# Then rename:
mv rosbag2_<timestamp> YYYY-MM-DD__<session_description>
```

For profiling sessions only, `/tracks` and `/timing_tracker` may be added explicitly.

### Run eval replay (records to `bags/eval/`)

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<YYYY-MM-DD__slice__tag> \
  tracker:=sort
# Available trackers: sort, ocsort, bytetrack
```

### Analyse timing

```bash
python3 tools/analyse_bag_timing.py \
  $THESIS_ROOT/bags/raw/<YYYY-MM-DD__slice__tag>
# Output: reports/timing/<bag>__timing.md  +  figures/timing/<bag>/
```

### Analyse tracking

```bash
python3 tools/analyse_bag_tracking.py \
  $THESIS_ROOT/bags/eval/<YYYY-MM-DD__eval__rawbag__tracker>
# Output: reports/tracking/<evalbag>/summary.md  +  3 PNG plots
```

### Rebuild ROS 2 workspace

```bash
cd $THESIS_ROOT/ros2_ws
colcon build --packages-select thesis_bringup thesis_tracker thesis_msgs \
  thesis_target_selector thesis_inference_client
source install/setup.bash
```

### Clean build

```bash
cd $THESIS_ROOT/ros2_ws
rm -rf build/ install/ log/
colcon build
source install/setup.bash
```

---

## Key ROS 2 topics

| Topic | Message Type | Description |
|---|---|---|
| `/detections` | `thesis_msgs/DetectionArray` | Person detections from inference service |
| `/tracks` | `thesis_msgs/TrackArray` | Multi-object tracker output |
| `/target` | `thesis_msgs/Target` | Selected target for control |
| `/timing` | `thesis_msgs/TimingArray` | End-to-end timing measurements |
| `/timing_tracker` | `thesis_msgs/TimingArray` | Per-track timing, profiling mode only, disabled in lean live runs |
| `/camera/fps` | `std_msgs/Float32` | Live camera frame rate |

---

## Operational modes

### Lean operational mode

Use for indoor validation, outdoor runs, and any real-time live session.

**Topics to record:**

- `/camera/fps`
- `/detections`
- `/timing`
- `/target`

**Do not record:**

- `/tracks`
- `/timing_tracker`

**Do not run long-lived debug subscribers** such as:

- `ros2 topic hz /detections`
- `ros2 topic hz /tracks`
- `ros2 topic hz /target`

### Profiling mode

Use only for bottleneck analysis and tracker runtime inspection.

**May record:**

- `/tracks`
- `/timing_tracker`

This mode is not the default field mode.

---

## Launch file modes

### Live perception

Preferred for now: use the frozen manual startup sequence from [RUNBOOK.md](RUNBOOK.md).
Use `live.launch.py` only if it is confirmed to match the frozen lean operational configuration.

### File replay (detections from bag)

```bash
ros2 launch thesis_bringup replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name>
```

### Eval replay (replay + record tracks for analysis)

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name> \
  tracker:=sort
```

---

## Deprecated review

### Moved to deprecated (2026-03-26)

- `infer_service/OLD/` -> `deprecated/infer_service/OLD/`
- `user-interface/vite.config.js` -> `deprecated/user-interface/vite.config.js`
- `user-interface/tailwind.config.js` -> `deprecated/user-interface/tailwind.config.js`
- `user-interface/vite.config.d.ts` -> `deprecated/user-interface/vite.config.d.ts`
- `user-interface/tailwind.config.d.ts` -> `deprecated/user-interface/tailwind.config.d.ts`

### Medium-confidence candidates (verify before moving)

- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/video_file_publisher_node.py`
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_resize_node.py`
- `ros2_ws/src/thesis_bringup/launch/first_ros2_slice.launch.py`

Suggested verification before moving medium-confidence files:

```bash
rg -n "video_file_publisher_node|dashboard_resize_node|first_ros2_slice" .
```
