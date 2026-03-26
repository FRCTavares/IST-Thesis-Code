# Runbook

Quick recipes for core operations.
All commands run from `$THESIS_ROOT/` unless noted.

## Frontend dashboard (new workspace)

Run the React + TypeScript dashboard locally:

```bash
cd $THESIS_ROOT/user-interface
npm install
npm run dev
```

Environment variables are documented in `user-interface/.env.example`.
Without env overrides, frontend mode defaults to `backend`.
For standalone UI development, run with `VITE_DASHBOARD_DATA_MODE=mock`.

**Live camera operational mode:** Use the frozen manual startup sequence documented below.

---

## 1 — Live camera (lean operational mode)

### Preferred startup (single command)

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

Default behavior now includes `control_ref_node` with MAVROS mirroring disabled (`enable_mavros=false`).
The launcher sets `ROS_DOMAIN_ID` to `42` by default (or uses your exported value if already set).

Optional flags:

- Disable control node: `./tools/start_live_stack.sh --no-control`
- Enable MAVROS mirror publish in control node: `./tools/start_live_stack.sh --control-mavros`

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

- Video: `http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45`
- Telemetry: `ws://<PI_IP>:8765`
- Control API: `http://<PI_IP>:8090` (`POST /api/model`, `POST /api/replay`)

Tip: If video still stutters, lower only `quality` first (for example 40 or 35).

### Dashboard troubleshooting (2026-03-25 fixes)

- Symptom: dashboard video pane is blank.
  - Cause: QoS mismatch between `web_video_server` default subscriber profile and `/camera/dashboard` publisher.
  - Fix: use `qos_profile=sensor_data` in MJPEG stream URL (included above and in `tools/start_live_stack.sh`).

- Symptom: detections visible but boxes are shifted/scaled incorrectly.
  - Cause: dashboard bridge normalization basis not matching detection coordinate basis.
  - Fix: keep dashboard bridge `img_w/img_h` aligned to inference bbox basis (`640x640` in current stack).
  - Current default launch path in `tools/start_live_stack.sh` already sets this correctly.

- Symptom: clicking model buttons does nothing.
  - Cause: frontend API path/host mismatch or silent request failure.
  - Fixes now in baseline:
    - control endpoint is served by `dashboard_bridge_node` on port `8090`
    - frontend defaults API base URL to `http://<dashboard-host>:8090`
    - frontend reports model-switch request errors in control status
  - Quick check:
    - `ss -ltnp | rg ':8090|:8765|:8080'`
    - `python3 - <<'PY'`
      `import json, urllib.request`
      `req=urllib.request.Request('http://127.0.0.1:8090/api/model', data=json.dumps({'model':'yolov8s'}).encode(), headers={'Content-Type':'application/json'}, method='POST')`
      `print(urllib.request.urlopen(req, timeout=5).read().decode())`
      `PY`

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

Canonical timing outputs are focused on:

- `/timing`: `pre_ms`, `zmq_roundtrip_ms`, `infer_ms`, `e2e_det_ms`, `pub_dt_ms`
- `/timing_tracker`: `track_ms` (if present)
- `/timing_target`: `e2e_target_ms` (if present)

Legacy aliases (`lat_ms`, `recv_ms`, `json_ms`, `loop_ms`) are accepted only as read fallback for historical data.

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

Canonical figure names from timing analysis include:

- `e2e_det_ms_hist.png`, `e2e_det_ms_cdf.png`
- `pub_dt_ms_hist.png`, `pub_dt_ms_cdf.png`

**Note:** `/timing_tracker` is profiling-only and will not be present in lean operational bags.

Validate canonical keys in generated reports:

```bash
python3 tools/validate_canonical_metrics.py \
  --json reports/timing/live_stats.json \
  --markdown reports/timing/<bag>__timing.md
```

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

### Throughput tuning and diagnostics (current workflow)

Use this when validating inference throughput without tracker/target/control overhead.

Frozen Baseline B (do not change during comparisons):

- `queue_size=4`
- `num_workers=3`
- blocking queue worker wakeup (`queue.Queue` + `get(timeout)`), no `sleep(0)` idle loop

**1) Rebuild inference client after code changes**

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_inference_client --symlink-install
source install/setup.bash
```

**2) Start tuned stack (camera + inference only)**

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh --no-tracker --no-target --no-control --no-dashboard --infer-queue-size 4 --infer-workers 3
```

**3) Restart container inference service with profiling enabled**

```bash
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc "
set -euo pipefail
pkill -f '/root/thesis_service/detection_zmq.py$' || true
VENV=/root/hailo-rpi5-examples/venv_hailo_rpi_examples
export PYTHONPATH=/root/hailo-rpi5-examples:${PYTHONPATH:-}
cd /root/thesis_service
export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND=tcp://0.0.0.0:5556
export HAILO_INFER_WIDTH=640
export HAILO_INFER_HEIGHT=640
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter
export HAILO_REQREP_LOG_EVERY=20
nohup \"$VENV/bin/python\" /root/thesis_service/detection_zmq.py > /tmp/detection_zmq_live.log 2>&1 &
sleep 2
tail -n 20 /tmp/detection_zmq_live.log
"
```

Expected log line:

- `ROUTER inference service listening on tcp://0.0.0.0:5556`

**4) ROS graph/session sanity check**

```bash
source /opt/ros/jazzy/setup.bash
source $THESIS_ROOT/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 daemon stop
ros2 daemon start
sleep 2
echo ROS_DOMAIN_ID=$ROS_DOMAIN_ID
ros2 node list
ros2 topic list
```

**5) Throughput checks**

```bash
ros2 topic hz /camera/image_raw
ros2 topic hz /detections
ros2 topic echo /camera/fps --once
```

Notes:

- In this Jazzy setup, `ros2 topic hz` has no QoS override flags and can under-report BEST_EFFORT sensor streams (especially `/camera/image_raw`).
- Treat `/camera/fps` as the authoritative camera source-rate check and use `/detections` rate plus inference log timing for throughput conclusions.

**6) Capture logs for analysis**

```bash
tail -n 120 $THESIS_ROOT/log/live_stack/latest/inference.log
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 sh -lc "grep reqrep_prof /tmp/detection_zmq_live.log | tail -n 80"
```

Interpretation:

- If `service_ms` stays mostly in low teens but `pub_dt_p95_ms` is high and `empty_polls` grows rapidly, the remaining bottleneck is upstream scheduling/frame delivery (not container inference).
- If `reqrep_prof` lines are missing in `/tmp/detection_zmq_live.log`, verify the container was started with `HAILO_REQREP_LOG_EVERY` set; until then, use client `rt_ms` trend as a provisional service-health indicator.

### Focused image-path A/B protocol (single-variable test)

Goal: isolate camera/image transport and resize cost without changing frozen inference settings.

Test A (current path):

- camera publishes `1920x1080`
- client resizes to `640x640`

Test B (direct path):

- camera publishes `640x640`
- client bypasses resize when frame is already `640x640`

Keep fixed in both A and B:

- same container config
- same inference queue/workers (Baseline B)
- same runtime scope (camera + inference only for first pass)

Compare these fields over matched windows:

- FPS (`/detections` + sent-delta/window from `inference.log`)
- `e2e_det_ms`
- `pre_ms`
- `resize_ms`
- `pub_dt_p50_ms`
- `pub_dt_p95_ms`

### Full-pipeline retest sequence (after A/B)

1) Full stack functional run first (no bag):

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh --infer-queue-size 4 --infer-workers 3
```

Validate topic activity and control-rate usability before recording.

1) Profiling run second (with bag):

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__baselineB_fullstack_profile \
  /camera/fps /detections /timing /target /tracks /timing_tracker
```

Note: keep recording disabled in functional-run checks to avoid subscriber overhead during go/no-go evaluation.
