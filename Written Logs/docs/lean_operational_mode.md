# Lean Operational Mode

## Purpose

This document freezes the validated live perception configuration used for operational indoor and outdoor runs.

It separates the fast operational path from heavier profiling and debug configurations.

## Status

**Frozen on:** 2026-03-11  
**Basis:** 2026-03-10 10-minute validation run  
**Operational decision:** GO for outdoor testing in lean mode only

### Validated Performance Results

| Metric | Value |
|---|---|
| Duration | 598.229 s |
| `/detections` rate | 16.644 Hz |
| `/target` rate | 16.629 Hz |
| `lat_ms` mean | 61.698 ms |
| `lat_ms` p95 | 91.296 ms |
| `lat_ms` p99 | 112.012 ms |
| `loop_ms` mean | 33.641 ms |
| Final temperature | 59.3°C |
| Throttling | `0x0` (none) |
| Memory | Stable |

## Operational Rules

Lean operational mode enforces the following constraints:

**Enabled:**
- Tracker fast score path
- Minimal topic recording
- Operational validation only

**Disabled:**
- Per-track Python IoU score recovery
- `/timing_tracker` topic
- `/tracks` recording in operational bags
- Long-lived debug subscribers during recording
- `ros2 topic hz` during bag capture
- Ad hoc debug instrumentation

**Recording policy:**
- Record only the minimum topics required for operational validation

## Lean Recording Topics

### Required operational topics:
| Topic | Purpose |
|---|---|
| `/camera/fps` | Frame rate monitoring |
| `/detections` | Detection outputs from inference |
| `/timing` | End-to-end timing measurements |
| `/target` | Selected target for control |

### Excluded from operational bags:
- `/tracks` — Not recorded (use profiling mode if needed)
- `/timing_tracker` — Not recorded (use profiling mode if needed)

---

## Not Allowed in Operational Runs

These are **profiling-only features** and must remain disabled in normal field sessions:

**Prohibited during operational runs:**
- `/tracks` recording
- `/timing_tracker` recording
- Long-lived `ros2 topic hz` commands
- Extra subscriber-based inspection tools
- Ad hoc debug instrumentation not previously validated

**Rationale:**
These features add subscriber load and can distort timing measurements. Use profiling mode for debugging.

## Live vs Profiling Mode

| Item | Lean operational mode | Profiling mode |
|---|---|---|
| Purpose | Field validation and live runs | Bottleneck analysis and debugging |
| Tracker score path | Fast path | Full/debug path allowed |
| `/timing_tracker` | Disabled | Enabled |
| `/tracks` recording | Disabled | Enabled |
| Bag topics | `/camera/fps`, `/detections`, `/timing`, `/target` | May include `/tracks`, `/timing_tracker` |
| Debug subscribers | Avoided | Allowed if needed |
| Target use | Real-time operation | Measurement and diagnosis |

## Frozen Startup Order

### Terminal 1 — Camera Bringup
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch thesis_bringup camera_bringup.launch.py
```

### Terminal 2 — Container Live Inference Service
```bash
# Enter container first
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash

# Inside container:
VENV=/root/hailo-rpi5-examples/venv_hailo_rpi_examples
export PYTHONPATH=/root/hailo-rpi5-examples:${PYTHONPATH:-}
cd /root/thesis_service

export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND=tcp://0.0.0.0:5556
export HAILO_INFER_WIDTH=640
export HAILO_INFER_HEIGHT=640
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter

$VENV/bin/python /root/thesis_service/detection_zmq.py
```

### Terminal 3 — Inference Client
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_inference_client inference_client_node --ros-args \
  -p image_topic:=/camera/image_raw \
  -p addr:=tcp://127.0.0.1:5556 \
  -p queue_size:=1 \
  -p img_w:=640 \
  -p img_h:=640 \
  -p min_score:=0.35
```

### Terminal 4 — Tracker
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_tracker tracker_node
```

### Terminal 5 — Target Selector
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_target_selector target_selector_node
```

### Terminal 6 — Dashboard Bridge
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_bringup dashboard_bridge_node --ros-args \
  -p img_w:=640 \
  -p img_h:=640
```

### Terminal 7 — Web Video Service
```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run web_video_server web_video_server --ros-args -p port:=8080
```

Dashboard endpoints:
- Video: `http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg`
- Telemetry: `ws://<PI_IP>:8765`

## One-command Startup (Preferred)

```bash
cd ~/Desktop/Thesis-Code
./tools/start_live_stack.sh
```

Interactive shutdown in same terminal: `stop`, `quit`, or `exit`.

---

## Operational Bag Command

```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__<session_description> \
  /camera/fps \
  /detections \
  /timing \
  /target
```

---

## Success Criteria

A lean operational run is valid if:

- `/detections` and `/target` sustain at least 15 Hz
- `lat_ms` p95 stays at or below 200 ms
- No clear rate decay appears across the run
- `vcgencmd get_throttled` returns `0x0`
- Memory remains stable
- No manual intervention is required during the run

---

## Known Limitations

**Restart reliability is not yet frozen:**
- System restart behavior is not yet fully characterized
- Clean startup sequence is documented but recovery procedures are pending

**Profiling mode still causes avoidable overhead:**
- `/tracks` and `/timing_tracker` recording adds subscriber load
- This overhead distorts timing measurements
- Profiling mode should only be used for dedicated debugging sessions

**Tracker runtime is not measured in lean mode:**
- `/timing_tracker` is disabled in operational runs
- Tracker performance cannot be profiled during field tests
- Switch to profiling mode if tracker bottleneck analysis is needed

**Authoritative tracker runtime measurement remains profiling-only:**
- `track_ms` in `/timing` is currently always 0.0 (not authoritative)
- Real tracker runtime is only available in `/timing_tracker` topic
- This is by design to keep operational mode overhead minimal

