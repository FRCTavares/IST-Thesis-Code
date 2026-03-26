# Useful Commands — Thesis Project

Quick reference for the most important commands used across the thesis work.
Organized by workflow: live camera (primary) and file-based replay (baseline/eval).

**Path conventions:** All commands assume `~/Desktop/Thesis-Code` unless noted.

**Important timing note:** `track_ms` inside `/timing` is currently always 0.0 (not authoritative). Real tracker runtime is in `/timing_tracker` topic.

---

---

## 1. Golden State Check (Run Before Any Session)

```bash
# Host — verify Hailo driver
modinfo hailo_pci | grep "^version"
# expected: 4.20.0

# Container — runtime versions
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 hailortcli --version
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 dpkg -l | grep -E "hailort|hailo-tappas-core"
# expected: hailort 4.20.0-1, hailo-tappas-core 3.31.0+1-1

# Container — GStreamer plugin
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  gst-inspect-1.0 hailonet >/dev/null 2>&1 && echo "hailonet OK" || echo "hailonet MISSING"

# Container — postprocess SO (tappas 3.31 path)
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so

# Container — HEF present
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /root/thesis_service/resources/hefs/yolov6n_hailo8.hef

# Host — camera device permissions (live camera only)
ls -l /dev/video0
# should be accessible by user or add user to video group: sudo usermod -a -G video $USER

# Host — ZMQ ports not already bound
ss -ltnp | grep 5555 || true  # file-based service
ss -ltnp | grep 5556 || true  # live camera service
```

---

## 2. Build ROS 2 Workspace

```bash
cd ~/Desktop/Thesis-Code/ros2_ws

# Recommended: symlink-install for faster Python iteration
colcon build --symlink-install \
  --packages-up-to thesis_bringup thesis_inference_client thesis_tracker \
  thesis_target_selector thesis_msgs

# Source workspace (required after build, in every new terminal)
source install/setup.bash
```

---

## 3. File-Based Inference Service — Replay and Baseline Work Only

**Port:** 5555 (not used for live camera)

**Use cases:** Tracker evaluation replay, baseline timing comparisons, initial testing.

### Start File-Based Service

```bash
# Looping mode (for long runs / bags)
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service && ./run_detection_zmq_forever.sh
'

# Single clip mode (stops at EOS ~110s)
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service && ./run_detection_zmq.sh
'
```

### Launch File-Based Pipeline

```bash
cd ~/Desktop/Thesis-Code/ros2_ws && source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

# Full pipeline (inference → tracker → target selector)
ros2 launch thesis_bringup first_ros2_slice.launch.py

# Tracker evaluation replay (swap tracker algorithm)
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=bags/raw/eval_bag tracker:=sort
```

### Record File-Based Bag

```bash
cd ~/Desktop/Thesis-Code/bags/raw
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  --topics /detections /tracks /target /timing /timing_tracker

# After Ctrl-C: rename to convention YYYY-MM-DD__slice__<tag>
```

---

## 4. Live Camera Stack — Normal Startup (Port 5556)

This is the **primary workflow** for live camera validation and outdoor testing.

### One-command startup (preferred)

```bash
cd ~/Desktop/Thesis-Code
./tools/start_live_stack.sh
```

Interactive stop in same terminal:
- `stop`
- `quit`
- `exit`

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
source install/setup.bash
ros2 run thesis_tracker tracker_node
```

### Terminal 5 — Target Selector

```bash
cd ~/Desktop/Thesis-Code/ros2_ws
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

### Terminal 7 — Web Video Server

```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run web_video_server web_video_server --ros-args -p port:=8080
```

Dashboard endpoints:
- Video: `http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg`
- Telemetry: `ws://<PI_IP>:8765`

### Manual startup note

```bash
# Use this manual sequence only when debugging startup internals.
# Normal operations should use ./tools/start_live_stack.sh
cd ~/Desktop/Thesis-Code
./tools/start_live_stack.sh
```

Interactive stop in same terminal:
- `stop`
- `quit`
- `exit`

---

## 5. One-Shot Validation Checks (Debug Only)

**Use for health checks only. Do NOT leave these running during bag recording — they add subscriber load and can distort measurements.**

```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source install/setup.bash

# One-shot topic inspection (safe, use freely)
ros2 topic echo /camera/fps --once
ros2 topic echo /detections --once
ros2 topic echo /tracks --once
ros2 topic echo /target --once
ros2 topic echo /timing --once

# Message interfaces
ros2 interface show thesis_msgs/msg/Timing
ros2 interface show thesis_msgs/msg/Detection
ros2 interface show thesis_msgs/msg/Track
ros2 interface show thesis_msgs/msg/Target

# Node list
ros2 node list
ros2 topic list

# Rate monitoring (ADDS LOAD — close terminal before bag recording)
ros2 topic hz /detections  # stop before recording
ros2 topic hz /tracks      # stop before recording
ros2 topic hz /target      # stop before recording
```

---

## 6. Bag Recording

### Live Camera Bag

```bash
cd ~/Desktop/Thesis-Code/ros2_ws
source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  -o ../bags/live_camera/2026-03-10__stability_10min \
  /camera/fps \
  /detections \
  /timing \
  /tracks \
  /timing_tracker \
  /target

# Run for target duration (e.g., 8-10 minutes for stress test)
# Stop cleanly with Ctrl-C (SIGINT)
```

### Bag Inspection

```bash
ros2 bag info bags/raw/2026-02-26__slice__primary
ros2 bag info bags/live_camera/2026-03-10__stability_10min
```

---

## 7. Offline Timing Analysis

```bash
cd ~/Desktop/Thesis-Code

# Normal timing analysis (canonical fields from /timing + track_ms from /timing_tracker)
python3 tools/analyse_bag_timing.py bags/live_camera/2026-03-10__stability_10min \
  --out reports/timing/W11_2026-03-10__stability_10min.md \
  --figdir figures/timing/

# Validate canonical metric keys in generated outputs
python3 tools/validate_canonical_metrics.py \
  --json reports/timing/live_stats.json \
  --markdown reports/timing/W11_2026-03-10__stability_10min.md

# Gap-filtered analysis (exclude restarts, only active runs)
python3 tools/analyse_bag_timing.py bags/raw/2026-02-25__slice__primary \
  --gap-ms 100 \
  --out reports/timing/2026-02-26__timing_summary_active_only.md

# Tracker metrics analysis (HOTA, IDF1, MOTA from ground truth comparison)
python3 tools/analyse_bag_tracking.py \
  bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort \
  --tag sort
```

---

## 8. Thermal and Resource Monitoring

```bash
# Current temperature (Pi 5)
vcgencmd measure_temp

# Check for throttling events
vcgencmd get_throttled
# 0x0 = no throttling, any other value = throttling occurred

# Continuous temperature logging (every 30s for 10 minutes)
cd ~/Desktop/Thesis-Code/reports/system
for i in {1..20}; do
  echo "$(date +%s) $(vcgencmd measure_temp | cut -d= -f2)" | tee -a thermal_log_$(date +%Y%m%d).txt
  sleep 30
done

# Resource usage monitoring
htop  # interactive
top -b -d 30 -n 20 > resource_log.txt  # batch: 30s intervals, 20 samples

# Memory usage
free -h

# Process memory monitoring (check for leaks)
watch -n 5 'ps aux | grep -E "camera_capture|inference_client|tracker_node"'

# Disk space
df -h ~/Desktop/Thesis-Code/bags

# ZMQ connection status
ss -ltnp | grep -E "5555|5556"
```

---

## 9. Key Frozen Parameters

| Parameter | Value | Context |
|-----------|-------|---------|
| `iou` | 0.18 | SORT tracker |
| `max_age` | 4 | SORT tracker |
| `min_hits` | 3 | SORT tracker |
| `min_score` | 0.35 | Detection confidence threshold |
| ZMQ port (file-based) | 5555 | Service → host (file replay) |
| ZMQ port (live camera) | 5556 | Service → host (live camera) |
| Hailo driver | 4.20.0 | **Do not update kernel — will break driver** |
| HEF | `yolov6n_hailo8.hef` | Confirmed working at ~30 Hz |
| Bag format | MCAP | Always pass `--storage mcap` |
| File-based inference rate | ~30 Hz | Pre-camera baseline |
| Live camera target | ≥15 Hz | Sustained rate on all topics |
| Latency target (excellent) | p95 ≤120 ms | End-to-end |
| Latency target (acceptable) | p95 ≤200 ms | End-to-end |

---

## 10. Troubleshooting and Recovery

### Docker Container Management

```bash
# Start container
cd ~/pi-ai-kit-ubuntu
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi

# Shell into container
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash

# Stop / restart container
docker compose -f docker-compose.yaml stop hailo-ubuntu-pi
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
```

### Container One-Time Setup (Recovery Only)

**These are recovery commands, not normal workflow. Only run if golden state check fails.**

```bash
# Inside container only:

# Fix hailonet SONAME mismatch (if gst-inspect-1.0 hailonet fails)
ln -sf /lib/libhailort.so.4.20.0 /lib/libhailort.so.4.17.0 && ldconfig

# Install TAPPAS core (if missing)
apt-get install -y pkg-config hailo-tappas-core

# Download HEFs and resources (if missing)
cd /root/hailo-rpi5-examples && ./download_resources.sh --all

# Symlink YOLO postprocess SO (if missing)
ln -sf /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so \
  /usr/local/hailo/resources/so/libyolo_hailortpp_postprocess.so && ldconfig
```

### ZMQ Quick Validation (Debug)

```bash
# Receive one detection frame (file-based, port 5555)
python3 - <<'PY'
import zmq, json
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.connect("tcp://127.0.0.1:5555")
topic, payload = s.recv_multipart()
msg = json.loads(payload.decode())
print("n_dets:", len(msg.get("dets", [])))
print("sample:", msg.get("dets", [])[:2])
PY

# Same for live camera service (port 5556)
python3 - <<'PY'
import zmq, json
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.connect("tcp://127.0.0.1:5556")
topic, payload = s.recv_multipart()
msg = json.loads(payload.decode())
print("n_dets:", len(msg.get("dets", [])))
print("sample:", msg.get("dets", [])[:2])
PY

# Pub-dt stall detector (debug timing issues)
python3 - <<'PY'
import zmq, json, time
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.setsockopt(zmq.RCVTIMEO, 3000)
s.connect("tcp://127.0.0.1:5556")  # or 5555 for file-based
last_t = None
while True:
    try:
        _, payload = s.recv_multipart()
        msg = json.loads(payload)
        t = msg.get("t_pub", 0)
        if last_t and t:
            dt = (t - last_t) / 1e6
            if dt > 80:
                print(f"STALL pub_dt_ms={dt:.1f}")
        last_t = t
    except zmq.error.Again:
        print("timeout")
PY
```

### Baseline Inference Benchmark (Debug Performance)

```bash
# Inside container: direct pipeline (no ZMQ, no ROS overhead)
cd /root/hailo-rpi5-examples && source ./setup_env.sh
timeout 10s python3 -m basic_pipelines.detection_simple \
  --input /usr/local/hailo/resources/videos/example_640.mp4 \
  --hef-path /usr/local/hailo/resources/models/hailo8/yolov6n.hef \
  --show-fps --disable-sync --frame-rate 30
```
