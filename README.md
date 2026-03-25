# Thesis workspace

## System architecture

This repository now contains three clearly separated layers:

- ROS perception and control stack in `ros2_ws/`
- Backend bridge (planned) in `backend/`
- Frontend dashboard in `user-interface/`

Data flow:

`Drone -> ROS -> Backend -> Dashboard`

## Quick reference

- **[RUNBOOK.md](RUNBOOK.md)** — Quick command recipes for core operations
- **[Written Logs/](Written%20Logs/)** — Weekly planning, daily logs, and useful commands

Temporary one-off experiment assets are not part of the core thesis pipeline and are intentionally excluded from this documentation/workflow.

### Current frozen live baseline (Baseline B)

- Inference queue size: `4`
- Inference worker threads: `3`
- Client queue behavior: blocking bounded queue (`queue.Queue`) with timeout wakeup
- Comparison rule: change one variable at a time (no multi-change tuning jumps)

Current next controlled experiment:
- Image-path A/B only
- A: `1920x1080` camera publish + client resize to `640x640`
- B: direct `640x640` camera publish + no client resize
- Keep all other settings fixed (see throughput workflow in [RUNBOOK.md](RUNBOOK.md))

### Live stack status update (2026-03-25)

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
| `backend/` | Planned dashboard backend bridge and API layer |
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
export THESIS_ROOT=/home/francisco/Desktop/Thesis-Code
export ROS_DOMAIN_ID=42  # Isolate from other ROS 2 systems
```

### ROS 2 workspace overlay
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

---

## Naming conventions

### Raw bags — `bags/raw/`
```
YYYY-MM-DD__slice__<tag>
```
Example: `2026-02-26__slice__longrun`

Record with `-o` pointing directly to the final name, or rename immediately after stopping:
```bash
mv rosbag2_<auto-timestamp> YYYY-MM-DD__slice__<tag>
```

### Eval bags — `bags/eval/`
```
YYYY-MM-DD__eval__<rawbag>__<tracker>
```
Example: `2026-02-27__eval__2026-02-25__slice__primary__sort`

These are created automatically by `eval_replay.launch.py` — do not rename manually.

### Live camera bags — `bags/live_camera/`
```
YYYY-MM-DD__<session_description>
```
Example: `2026-03-09__camera_validation`

---

## Common commands

### Run dashboard frontend
```bash
cd $THESIS_ROOT/user-interface
npm install
npm run dev
```

The frontend defaults to `mock` data mode and does not require a running backend to start.

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
