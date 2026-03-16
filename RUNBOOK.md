# Runbook

Quick recipes for core operations.
All commands run from `$THESIS_ROOT/` unless noted.

**Live camera operational mode:** Use the frozen manual startup sequence documented below.

---

## 1 — Live camera (lean operational mode)

### Preferred startup (single command)

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

Interactive stop in same terminal:
- `stop`
- `quit`
- `exit`

Fallback stop command:
```bash
cd $THESIS_ROOT
./tools/stop_live_stack.sh
```

### Frozen manual startup sequence

The manual startup sequence is the current operational standard.

**Terminal 1 — Camera Bringup (init + capture):**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch thesis_bringup camera_bringup.launch.py
```

**Terminal 2 — Container Live Inference Service:**
```bash
cd ~/pi-ai-kit-ubuntu
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi

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

**Terminal 3 — Inference Client:**
```bash
cd $THESIS_ROOT/ros2_ws
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

**Terminal 4 — Tracker:**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_tracker tracker_node
```

**Terminal 5 — Target Selector:**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_target_selector target_selector_node
```

**Terminal 6 — Dashboard Bridge (WebSocket telemetry):**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run thesis_bringup dashboard_bridge_node --ros-args \
  -p img_w:=640 \
  -p img_h:=640
```

**Terminal 7 — Web Video Service (MJPEG stream):**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run web_video_server web_video_server --ros-args -p port:=8080
```

Dashboard endpoints:
- Video: `http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg`
- Telemetry: `ws://<PI_IP>:8765`

### Record live camera bag (lean mode)

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__<session_description> \
  /camera/fps \
  /detections \
  /timing \
  /target

# Immediately after Ctrl-C, verify bag name matches convention
```

**Output:** `bags/live_camera/YYYY-MM-DD__<session_description>/`

**Note:** `/tracks` and `/timing_tracker` are profiling-only. Do not record them in operational runs.

---

## 2 — Record a raw bag (file-based profiling mode)

**Use case:** File-based replay for tracker evaluation and profiling.

```bash
cd $THESIS_ROOT/bags/raw

ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker

# Immediately after Ctrl-C:
mv rosbag2_<auto-timestamp>  YYYY-MM-DD__slice__<tag>
# e.g.: mv rosbag2_2026-02-28-09_30_00  2026-02-28__slice__lab01
```

**Output:** `bags/raw/YYYY-MM-DD__slice__<tag>/`

**Note:** This mode includes `/tracks` and `/timing_tracker` which are profiling-only topics. Do not use for operational runs.

---

## 3 — Run eval replay

Replays a raw detections bag through the tracker and records the result.

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/2026-02-25__slice__primary \
  tracker:=sort
```

Override the date if re-running an old bag:
```bash
  run_date:=2026-02-27
```

**Output:** `bags/eval/YYYY-MM-DD__eval__<rawbag>__<tracker>/`

---

## 4 — Analyse timing

Reads `/timing` (and `/timing_tracker` if present) from a raw or live bag.

```bash
python3 tools/analyse_bag_timing.py \
  bags/raw/2026-02-25__slice__primary
# or
python3 tools/analyse_bag_timing.py \
  bags/live_camera/2026-03-10__stability_10min
```

**Outputs:**
- `reports/timing/<bag>__timing.md`
- `figures/timing/<bag>/` (PNG plots)

**Note:** `/timing_tracker` is profiling-only and will not be present in lean operational bags.

---

## 5 — Analyse tracking

Reads `/target` and `/timing_tracker` from an eval bag.

```bash
python3 tools/analyse_bag_tracking.py \
  bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort
```

Tag is auto-detected from the bag name; pass `--tag` to override.

**Outputs:**
- `reports/tracking/<evalbag>/summary.md`
- `reports/tracking/<evalbag>/target_lock_timeseries.png`
- `reports/tracking/<evalbag>/track_ms_cdf.png`
- `reports/tracking/<evalbag>/reacq_hist.png`

**Note:** Requires `/timing_tracker` which is profiling-only. Cannot be used with lean operational bags.

---

## Operational vs Profiling Modes

### Lean operational mode (live camera)
- **Use for:** Indoor validation, outdoor testing, field operations
- **Topics recorded:** `/camera/fps`, `/detections`, `/timing`, `/target`
- **Excluded:** `/tracks`, `/timing_tracker`
- **Startup:** One-command launcher (`tools/start_live_stack.sh`) or manual 7-terminal sequence

### Profiling mode (file-based)
- **Use for:** Bottleneck analysis, tracker debugging, performance profiling
- **Topics recorded:** All topics including `/tracks` and `/timing_tracker`
- **Note:** Adds subscriber overhead, distorts timing measurements
- **Not for:** Operational runs or field testing

**See also:** `Written Logs/docs/lean_operational_mode.md` for full details.

---

## Where outputs go

| Type | Location |
|---|---|
| Live camera bags (lean mode) | `bags/live_camera/YYYY-MM-DD__<session_description>/` |
| Raw bags (file-based profiling) | `bags/raw/YYYY-MM-DD__slice__<tag>/` |
| Eval bags | `bags/eval/YYYY-MM-DD__eval__<rawbag>__<tracker>/` |
| Timing reports | `reports/timing/` |
| Tracking reports + plots | `reports/tracking/<evalbag>/` |
| Timing figures | `figures/timing/<bag>/` |
| Tracking figures | `figures/tracking/` |
| Comparison reports | `reports/compare/` |
