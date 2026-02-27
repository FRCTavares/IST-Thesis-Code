# Useful Commands — Thesis Project

Quick reference for the most important commands used across the thesis work.
Organised by task area. All host commands assume `~/Desktop/Thesis` unless noted.

---

## 1. Golden State Check (run before any session)

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

# Container — safe test clip present
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /root/thesis_service/example_640_x10_safe.mp4

# Host — ZMQ port not already bound
ss -ltnp | grep 5555 || true
```

---

## 2. Docker Container

```bash
# Start container
cd ~/pi-ai-kit-ubuntu
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi

# Shell into container
docker compose -f docker-compose.yaml exec hailo-ubuntu-pi bash
# or:
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash

# Run a one-off command in the container
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc 'hailortcli scan'

# Stop / restart container
docker compose -f docker-compose.yaml stop hailo-ubuntu-pi
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
```

---

## 3. Inference Service (Container)

```bash
# Standard run (single clip, stops at EOS ~110 s)
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service
  ./run_detection_zmq.sh
'

# Looping / forever mode (for long runs / bags)
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service
  ./run_detection_zmq_forever.sh
'

# With custom video source
export HAILO_VIDEO_SINK=fakesink
export HAILO_LOOP_VIDEO=0
export HAILO_VIDEO_SOURCE=/root/thesis_service/resources/example_640_x10.mp4
./run_detection_zmq.sh

# Baseline inference benchmark (no service, direct pipeline)
cd /root/hailo-rpi5-examples && source ./setup_env.sh
timeout 10s python3 -m basic_pipelines.detection_simple \
  --input /usr/local/hailo/resources/videos/example_640.mp4 \
  --hef-path /usr/local/hailo/resources/models/hailo8/yolov6n.hef \
  --show-fps --disable-sync --frame-rate 30
```

---

## 4. ROS 2 Workspace Build

```bash
cd ~/Desktop/Thesis/ros2_ws

# Build specific packages
colcon build --packages-select thesis_msgs
colcon build --packages-select thesis_inference_client thesis_tracker \
  thesis_target_selector thesis_bringup

# Build everything
colcon build

# Source workspace (required after every build, every new terminal)
source install/setup.bash
```

---

## 5. ROS 2 Launch

```bash
cd ~/Desktop/Thesis/ros2_ws && source install/setup.bash

# Full pipeline (inference → tracker → target selector)
ros2 launch thesis_bringup first_ros2_slice.launch.py

# Tracker evaluation replay (swap tracker with arg)
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=bags/raw/eval_bag tracker:=sort

ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=bags/raw/eval_bag tracker:=ocsort

# Run individual nodes
ros2 run thesis_inference_client inference_client_node --ros-args \
  -p addr:=tcp://127.0.0.1:5555 -p topic:=dets \
  -p img_w:=640 -p img_h:=640 -p min_score:=0.35 -p conflate:=true
```

---

## 6. ROS 2 Inspection

```bash
# Topic rates
ros2 topic hz /detections
ros2 topic hz /tracks
ros2 topic hz /target

# Single message inspection
ros2 topic echo /tracks --once
ros2 topic echo /target --once
ros2 topic echo /timing --once

# Message interfaces
ros2 interface show thesis_msgs/msg/Timing
ros2 interface show thesis_msgs/msg/Detection

# Node / topic graph
ros2 node list
ros2 topic list

# Bag metadata
ros2 bag info bags/raw/2026-02-25__slice__primary
```

---

## 7. Bag Recording

```bash
cd ~/Desktop/Thesis/bags/raw
export RMW_FASTRTPS_USE_SHM=0   # suppress SHM warning

# Record all thesis topics (MCAP)
ros2 bag record --storage mcap \
  --topics /detections /tracks /target /timing /timing_tracker

# Record detections only (for eval replay input)
ros2 bag record --storage mcap -o detections_only /detections /timing

# Stop gracefully — always use SIGINT to ensure metadata is written
# (Ctrl-C in the terminal, or:)
kill -SIGINT <bag_record_pid>

# Rename to convention immediately after recording:
#   Raw:  YYYY-MM-DD__slice__<tag>
#   Eval: produced automatically by eval_replay.launch.py into bags/eval/
# Example:
mv rosbag2_2026_02_27-16_30_00 2026-02-27__slice__<tag>

# Inspect a bag
ros2 bag info bags/raw/2026-02-26__slice__primary
```

---

## 8. Offline Analysis

```bash
cd ~/Desktop/Thesis

# Timing analysis (lat_ms, loop_ms, pub_dt_ms, track_ms — stats + figures)
python3 tools/analyse_bag_timing.py bags/raw/2026-02-25__slice__primary

# With options (output to reports/timing/, figures to figures/)
python3 tools/analyse_bag_timing.py bags/raw/2026-02-25__slice__primary \
  --out reports/timing/2026-02-26__timing_summary.md --figdir figures/timing/

# Active-only analysis (gap filter to exclude restarts)
python3 tools/analyse_bag_timing.py bags/raw/2026-02-25__slice__primary \
  --gap-ms 100 --out reports/timing/2026-02-26__timing_summary_longrun.md

# Tracker metrics analysis (output goes to reports/tracking/<run_dir>/)
python3 tools/analyse_bag_tracking.py \
  bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort \
  --tag sort
```

---

## 9. ZMQ Quick Validation (Host Python one-liners)

```bash
# Receive one detection frame and print it
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

# Pub-dt stall detector
python3 - <<'PY'
import zmq, json, time
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.setsockopt(zmq.RCVTIMEO, 3000)
s.connect("tcp://127.0.0.1:5555")
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

---

## 10. Host Client Tester (`host_client/client_tester.py`)

```bash
cd ~/Desktop/Thesis/host_client

# Baseline run (frozen SORT params)
./client_tester.py \
  --addr tcp://127.0.0.1:5555 --topic dets \
  --w 640 --h 640 \
  --iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 \
  --print_every 60

# With timing record and GC disabled
./client_tester.py \
  --addr tcp://127.0.0.1:5555 --topic dets \
  --w 640 --h 640 \
  --iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 \
  --print_every 60 --gc_disable --timing \
  --record run_$(date +%Y%m%d_%H%M%S).jsonl
```

---

## 11. Container Setup / Troubleshooting

```bash
# Fix hailonet SONAME mismatch
ln -sf /lib/libhailort.so.4.20.0 /lib/libhailort.so.4.17.0 && ldconfig

# Install TAPPAS core
apt-get install -y pkg-config hailo-tappas-core

# Download HEFs and resources
cd /root/hailo-rpi5-examples && ./download_resources.sh --all

# Symlink YOLO postprocess SO
ln -sf /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so \
  /usr/local/hailo/resources/so/libyolo_hailortpp_postprocess.so && ldconfig

# Source hailo-rpi5-examples env (required inside container before any pipeline call)
cd /root/hailo-rpi5-examples && source ./setup_env.sh

# Create extended test clip (10× loop, no re-encode)
ffmpeg -stream_loop 9 -i example_640.mp4 -c copy example_640_x10.mp4
```

---

## 12. Key Frozen Parameters

| Parameter | Value | Context |
|-----------|-------|---------|
| `iou` | 0.18 | SORT tracker |
| `max_age` | 4 | SORT tracker |
| `min_hits` | 3 | SORT tracker |
| `min_score` | 0.35 | Detection confidence threshold |
| ZMQ port | 5555 | Service → host |
| ZMQ topic | `b"dets"` | Multipart frame: `[topic, payload]` |
| Hailo driver | 4.20.0 | **Do not update kernel — will break driver** |
| HEF | `yolov6n_hailo8.hef` | Confirmed working at ~30 Hz |
| Bag format | MCAP | Always pass `--storage mcap` |
| Inference rate | ~30 Hz | Pre-camera baseline |
| Control rate target | 30 Hz | `/control_ref` output rate |
| Latency target | p95 ≤ 200 ms | End-to-end |

---

## 13. Typical Session Startup (Full Pipeline)

```bash
# Terminal 1 — start inference service
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service && ./run_detection_zmq_forever.sh
'

# Terminal 2 — build + launch ROS 2 slice
cd ~/Desktop/Thesis/ros2_ws
colcon build && source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0
ros2 launch thesis_bringup first_ros2_slice.launch.py

# Terminal 3 — record bag (rename immediately after Ctrl-C)
cd ~/Desktop/Thesis/bags/raw
export RMW_FASTRTPS_USE_SHM=0
ros2 bag record --storage mcap \
  --topics /detections /tracks /target /timing /timing_tracker
# After recording: mv rosbag2_<timestamp> YYYY-MM-DD__slice__<tag>

# Terminal 4 — validate topics live
ros2 topic hz /detections /tracks /target
```
