# Runbook

Practical commands for day-to-day operation.
All commands run from `$THESIS_ROOT` unless noted.

Use this file as the command source of truth.

## Fast path (daily operation)

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42

cd "$THESIS_ROOT/ros2_ws"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install

cd "$THESIS_ROOT"
./tools/start_live_stack.sh --profile daily
./tools/start_ui_stack.sh
```

If startup fails, inspect `ros2_ws/log/live_stack/latest/` first before manual restarts.

## Current runtime defaults

From `tools/start_live_stack.sh`:

- Perception mode default: `single-process`
- Tracker default: `sort`
- Camera default: `1280x720@30`
- Published perception image default in single-process mode: `640x640` letterboxed from capture
- Camera sensor trigger/rate-control writes: disabled by default for reliability
- Active `/dev/video0` preflight stream probe: disabled by default; media graph preflight still runs
- Control node: enabled by default
- MAVROS mirroring: disabled by default
- Dashboard bridge + web video: enabled by default
- Legacy detector port `:5556`: expected only in `--perception-mode legacy`

## Scope and assumptions

- Primary platform: Raspberry Pi 5 + Hailo (full live stack).
- Fallback platform: generic Linux (UI, replay, offline analysis).
- ROS 2 distro: Jazzy.
- Workspace root: `$HOME/Desktop/Thesis-Code`.

## Success checks (required)

This runbook is complete when you can do all three:

1. Start live stack end-to-end on target hardware.
2. Run replay on recorded bags.
3. Run timing/tracking analyses and produce output reports.

## 0) One-time shell setup

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

Optional (recommended in ~/.bashrc):

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

## 0.1) First-run prerequisites

### Required tools (all platforms)

- `bash`, `python3`, `pip`, `git`
- `npm` (UI)
- `ros2` + `colcon` (for ROS workflows)
- `docker` + `docker compose` (for Hailo inference service path)

Quick sanity checks:

```bash
command -v python3
command -v npm
command -v ros2
command -v colcon
command -v docker
docker compose version
```

### Mandatory external dependency (RPi5 + Hailo path)

This repository expects the Hailo compose environment at `$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu`.
`tools/start_live_stack.sh` still supports `~/pi-ai-kit-ubuntu` as compatibility fallback on older hosts.

```bash
git clone https://github.com/hailo-ai/pi-ai-kit-ubuntu.git "$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu"
cd "$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu"
docker compose -f docker-compose.yaml pull
```

If your team uses a fork, clone that fork into the same path.

### Build ROS workspace once

```bash
cd "$THESIS_ROOT/ros2_ws"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

Generic Linux fallback note:

- If no Hailo hardware is available, skip live-stack sections and use section 5 (replay/analysis) plus UI mock mode via `tools/start_ui_stack.sh --mode mock`.

## 1) Keep all ROS/colcon logs inside ros2_ws

Use this once per machine/user to force colcon artifacts under ros2_ws:

```bash
export WS=$THESIS_ROOT/ros2_ws
mkdir -p "${COLCON_HOME:-$HOME/.colcon}"
cat > "${COLCON_HOME:-$HOME/.colcon}/defaults.yaml" <<EOF
build:
  base-paths:
    - $WS/src
  build-base: $WS/build
  install-base: $WS/install
log-base: $WS/log
EOF
```

For runtime ROS logs in manual sessions, set:

```bash
export ROS_LOG_DIR=$THESIS_ROOT/ros2_ws/log/runtime/manual_$(date +%Y-%m-%d__%H-%M-%S)
mkdir -p "$ROS_LOG_DIR"
```

Notes:

- tools/start_live_stack.sh now automatically forces ROS_LOG_DIR to `ros2_ws/log/runtime/{run-id}`.
- tools/start_live_stack.sh run logs are under `ros2_ws/log/live_stack/{run-id}`.
- tools/start_ui_stack.sh run logs are under `ros2_ws/log/ui_stack/{run-id}`.
- If you see logs in ~/.ros/log during live stack startup, verify you started with tools/start_live_stack.sh and not a manual command in another shell.

## 2) Live stack (recommended)

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

What this script does:

1. Preflight and stale-process cleanup.
2. ROS env and log directory setup.
3. Perception path readiness by mode: legacy starts container detection service; single-process starts perception pipeline node.
4. Node startup order: camera -> (legacy inference OR single-process perception) -> tracker -> dashboard -> control.
5. Interactive runtime with `status`, `clear`, `stop` commands.

Default:

- control_ref_node enabled
- MAVROS mirror disabled (safe default)
- ROS_DOMAIN_ID defaults to 42 unless already exported

Useful flags:

- Disable control: ./tools/start_live_stack.sh --no-control
- Enable MAVROS mirror: ./tools/start_live_stack.sh --control-mavros
- Camera + inference only: ./tools/start_live_stack.sh --no-tracker --no-target --no-control --no-dashboard
- Safer camera fallback profile: ./tools/start_live_stack.sh --profile safe-camera
- Enable deeper active stream probe when diagnosing camera faults: ./tools/start_live_stack.sh --camera-preflight-stream-probe-on
- Enable sensor FPS/exposure writes only when explicitly needed: ./tools/start_live_stack.sh --camera-rate-controls-on
- Enable sensor trigger_mode writes only when explicitly needed: ./tools/start_live_stack.sh --camera-trigger-control-on
- Legacy perception path: ./tools/start_live_stack.sh --perception-mode legacy
- Single-process perception mode (default; in-process backend, stub fallback): ./tools/start_live_stack.sh --perception-mode single-process
- Single-process queue tuning: ./tools/start_live_stack.sh --perception-hailo-queue-buffers 1
- Disable pre-hailonet videoconvert stage: ./tools/start_live_stack.sh --perception-hailo-videoconvert-off
- Allow stub fallback if host Hailo init fails: ./tools/start_live_stack.sh --perception-allow-stub-fallback
- Tighten image subscription queue depth: ./tools/start_live_stack.sh --perception-image-qos-depth 1

Deprecated launcher flags:

- `--perception-async-latest-frame-on/off` was removed; queue+worker mode is now always used in single-process mode.

Full option list:

```bash
./tools/start_live_stack.sh --help
./tools/start_live_stack.sh --help-advanced
```

If you want to enable host-side Hailo dependencies for single-process mode:

- Install/probe host Python bindings: ./tools/install_host_hailo_bindings.sh
- Optional no-root runtime shim: ./tools/setup_local_tappas_runtime.sh

Note:

- start_live_stack.sh auto-detects local runtime assets from infer_service/opt/tappas_runtime_3_31 when present.

Stop:

- In prompt: `stop`, `quit`, or `exit`
- If the interactive shell is gone, terminate stack processes explicitly:

```bash
pkill -f 'camera_bringup.launch.py|camera_capture_node|inference_client_node|detector_node|perception_pipeline_node|tracker_node|control_ref_node|dashboard_bridge_node|web_video_server' || true
```

Verification checkpoint (live stack healthy):

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
ros2 topic list | rg '/camera/image_raw|/detections|/timing|/target'
ss -ltnp | rg ':5556|:8080|:8090|:8765'
```

Expected:

- Core topics are listed.
- Required service ports are listening. Note: :5556 is only expected in legacy perception mode.

Run UI in parallel (second terminal):

```bash
cd $THESIS_ROOT
./tools/start_ui_stack.sh
```

Notes:

- UI launcher now skips npm install by default.
- Use `./tools/start_ui_stack.sh --install` when you want to refresh dependencies.

Useful UI flags:

- Mock mode: ./tools/start_ui_stack.sh --mode mock
- Custom port: ./tools/start_ui_stack.sh --port 5174

Verification checkpoint (UI healthy):

- Open `http://127.0.0.1:5173` (or remote host IP and chosen port).
- Dashboard connects to telemetry websocket and backend API if running in backend mode.

## 3) Manual startup (legacy ZMQ path, troubleshooting only)

This section reproduces the legacy deployment shape manually.

- Useful for isolating startup faults.
- Not the recommended day-to-day path.
- Preferred path remains `./tools/start_live_stack.sh`.

Terminal 1 - Camera:

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_LOG_DIR=$THESIS_ROOT/ros2_ws/log/runtime/manual_camera_$(date +%Y-%m-%d__%H-%M-%S)
mkdir -p "$ROS_LOG_DIR"
ros2 launch thesis_bringup camera_bringup.launch.py
```

Terminal 2 - Inference service in container:

```bash
cd "$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu"
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi

docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash
# inside container
VENV=/root/thesis_deprecated/hailo-rpi5-examples/venv_hailo_rpi_examples
export PYTHONPATH=/root/thesis_deprecated/hailo-rpi5-examples:${PYTHONPATH:-}
cd /root/thesis_service
export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND=tcp://0.0.0.0:5556
export HAILO_INFER_WIDTH=640
export HAILO_INFER_HEIGHT=640
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter
$VENV/bin/python /root/thesis_deprecated/infer_service/detection_zmq.py
```

Terminal 3+ - Remaining nodes:

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

ros2 run thesis_tracker tracker_node
ros2 run thesis_bringup dashboard_bridge_node --ros-args -p img_w:=640 -p img_h:=640
ros2 run web_video_server web_video_server --ros-args -p port:=8080
```

Targeting note:

- Target selection is now strictly user-driven through `dashboard_bridge_node`.
- `POST /api/target` is the only supported way to select a target.
- There is no automatic target-selection fallback in the live stack, replay flows, or first ROS 2 slice.
- When no target is explicitly selected, `/target` publishes the empty target state (`id=0`, zero geometry, zero score/quality).

Dashboard:

- Video: http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45
- Telemetry: ws://<PI_IP>:8765
- Control API: http://<PI_IP>:8090

Manual mode verification:

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
ros2 node list | rg 'inference_client_node|detector_node|tracker_node|dashboard_bridge_node'
```

## 4) Record bags

Lean operational bag:

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__<session_description> \
  /camera/fps /detections /timing /target /timing_target
```

Use for field sessions and timeline metrics with low storage overhead.

Raw profiling bag:

```bash
cd $THESIS_ROOT/bags/raw
ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker /timing_target
# rename output folder after stop
```

Use for replay/evaluation runs. Save under `bags/raw`.

## 5) Replay and analysis

Eval replay:

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name> \
  tracker:=sort
```

Replay verification:

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
ros2 topic hz /timing
```

Expected:

- Replay publishes `/timing` steadily during bag playback.

Timing:

```bash
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/raw/<bag_name>
# or
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/live_camera/<bag_name>
```

Expected output:

- Markdown timing report file.
- Figure files in the selected figure directory.

Tracking:

```bash
python3 tools/analyse_bag_tracking.py $THESIS_ROOT/bags/eval/<eval_bag_name>
```

Expected output:

- `summary.md` and plot files under `reports/tracking/<eval_bag_name>/`.

## 5.1) Timing vocabulary (canonical)

Use these names in runtime analysis, reports, and UI interpretation:

- `e2e_det_ms`: Detection end-to-end latency from camera callback seen to detection publish completion.
- `pub_dt_ms`: Detection publish cadence interval (ms between consecutive `/timing` publishes).
- `det_out_fps`: Detection output rate derived from `/detections` callback cadence.
- `camera_input_fps`: Camera publish FPS from `/camera/fps`.
- `container_queue_ms`: Pre-infer wait before inference starts.
- `infer_ms`: Inference compute duration.
- `track_ms`: Tracker backend compute duration.
- `e2e_target_ms`: End-to-end latency to target publish completion.

Clock-domain note:

- `src_stamp_ns` is source/sensor clock metadata and may not be directly comparable to host monotonic timing without synchronization.
- `pub_dt_ms`, `det_out_fps`, and `camera_input_fps` are cadence-derived metrics.

Full old-to-new mapping, producers/consumers, and deprecation status is in `TIMING_FIELD_AUDIT.md`.

Freeze note:

- Timing schema v3 is frozen for the thesis baseline.
- Canonical timing names must not change unless metric semantics change.
- Remaining aliases are deprecated compatibility/history only.

## 5.2) Operator Metric Priority (Thesis)

Top 5 during live runs:

1. `e2e_det_ms` p95: end-to-end detection responsiveness.
2. `pub_dt_ms` p95: cadence stability and freshness.
3. `det_out_fps`: effective perception output rate.
4. `container_queue_ms` p95: bottleneck visibility before inference.
5. `camera_input_fps`: camera feed health relative to detector throughput.

Top 5 during offline analysis:

1. `e2e_det_ms` p95/p99: latency tail behavior.
2. `pub_dt_ms` p95/p99: cadence jitter and restart-gap impact.
3. `container_queue_ms` distribution: queue pressure/bottleneck location.
4. `infer_ms` distribution: compute cost stability.
5. `e2e_target_ms` p95 (when target stream present): downstream control readiness latency.

## 6) Quick troubleshooting

Camera check:

```bash
ros2 topic echo /camera/fps --once
```

Ports check:

```bash
ss -ltnp | rg ':5556|:8080|:8090|:8765'
```

ROS graph refresh:

```bash
source /opt/ros/jazzy/setup.bash
source $THESIS_ROOT/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 daemon stop
ros2 daemon start
sleep 2
ros2 node list
ros2 topic list
```

If startup says camera is not publishing:

- Rerun tools/start_live_stack.sh once.
- Try conservative camera mode: `./tools/start_live_stack.sh --profile safe-camera`
- Check cable/sensor state.
- If camera tooling/processes are stuck in uninterruptible `D` state, reboot host. Userspace cannot reliably kill that state.
- Use the active stream probe only for diagnosis: `./tools/start_live_stack.sh --camera-preflight-stream-probe-on`

Camera-startup notes:

- The normal launcher preflights the media graph and capture link, but avoids an active `/dev/video0` stream probe by default because that path can wedge bad camera-driver states.
- Sensor `trigger_mode` and rate/exposure control writes are opt-in. This keeps daily startup from poking the TEVS I2C control path unless you explicitly request it.
- The camera node has startup/stall watchdogs; if no frames arrive, it exits so the live stack fails fast instead of continuing in a half-alive state.
- Camera helpers live in `tools/lib/live_camera.sh`; CLI/default/help helpers live in `tools/lib/live_cli.sh`, `tools/lib/live_defaults.sh`, and `tools/lib/live_usage.sh`.

Additional common failures:

- Inference client timeout spam (legacy mode only):
  - Check detector service inside container is running.
  - Confirm `addr:=tcp://127.0.0.1:5556` (or host/IP override) matches service bind.
- Empty ROS graph:
  - Verify `ROS_DOMAIN_ID` matches all terminals.
  - Re-source `/opt/ros/jazzy/setup.bash` and workspace overlay.
- UI shows no live data:
  - Confirm API `:8090` and WS `:8765` ports are reachable.
  - Use UI mock mode to isolate backend vs frontend issues.
- `ros2 run` cannot find packages:
  - Rebuild workspace with `colcon build --symlink-install` in `ros2_ws`.

Live log triage quick commands:

```bash
cd "$THESIS_ROOT"
ls -1 ros2_ws/log/live_stack/latest
tail -n 80 ros2_ws/log/live_stack/latest/camera.log
tail -n 80 ros2_ws/log/live_stack/latest/perception_pipeline.log
tail -n 80 ros2_ws/log/live_stack/latest/inference.log
```

Note: `perception_pipeline.log` exists in single-process mode; `inference.log` exists in legacy mode.

## 7) Control validation quick checks

Verify control node is running and publishing:

```bash
source /opt/ros/jazzy/setup.bash
source $THESIS_ROOT/ros2_ws/install/setup.bash
ros2 node list | rg control_ref_node
ros2 topic hz /control_ref/cmd_vel
```

For deterministic sign checks, run an isolated control node on test topics:

```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -r __node:=control_ref_test_node \
  -p target_topic:=/target_test \
  -p cmd_topic:=/control_ref_test/cmd_vel \
  -p enable_mavros:=false
```

Expected behavior from validated baseline:

- center target -> vx=0, yaw_z=0
- left target -> yaw_z < 0
- right target -> yaw_z > 0
- far target (smaller h) -> vx > 0
- near target (larger h) -> vx < 0
- stale/lost target -> vx=0, yaw_z=0

## 8) Canonical repository paths (for command context)

- ROS packages: `ros2_ws/src/`
- Inference service code: `infer_service/`
- Utility scripts: `tools/`
- Live bags: `bags/live_camera/`
- Replay source bags: `bags/raw/`
- Eval output bags: `bags/eval/`
- Tracking reports: `reports/tracking/`

## 9) Last validated assumptions

- Date: 2026-04-15
- ROS: Jazzy
- Default live path: single-process perception via `tools/start_live_stack.sh`
- Legacy compose path: `$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu` (with `~/pi-ai-kit-ubuntu` compatibility fallback)

## 10) Queue-buffer 1-vs-2 decision workflow (single-process)

Use this flow to choose `--perception-hailo-queue-buffers 1` vs `2` with
workload-matched evidence.

### 10.1) Capture queue=1 run (10 min)

Terminal A:

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh --perception-mode single-process --perception-hailo-queue-buffers 1
```

Terminal B:

```bash
cd $THESIS_ROOT
python3 tools/collect_live_timing_stats.py \
  --duration 600 \
  --run-label "q1_$(date +%Y%m%d_%H%M%S)" \
  --json-out "reports/timing/q1_$(date +%Y%m%d_%H%M%S).json"
```

Stop the stack after collection completes.

Quick sanity check (container queue visibility):

- Verify `/timing.container_queue_ms` appears in the JSON under `metrics['/timing']`.
- This field tracks pre-infer wait (`t_infer_start_ns - t_pre_end_ns`).

### 10.2) Capture queue=2 run (10 min)

Terminal A:

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh --perception-mode single-process --perception-hailo-queue-buffers 2
```

Terminal B:

```bash
cd $THESIS_ROOT
python3 tools/collect_live_timing_stats.py \
  --duration 600 \
  --run-label "q2_$(date +%Y%m%d_%H%M%S)" \
  --json-out "reports/timing/q2_$(date +%Y%m%d_%H%M%S).json"
```

Stop the stack after collection completes.

### 10.3) Validate report schema

```bash
cd $THESIS_ROOT
python3 tools/validate_canonical_metrics.py \
  --json reports/timing/<q1_report>.json \
  --json reports/timing/<q2_report>.json \
  --require-tracker \
  --require-target
```

### 10.4) Decide default with gates

```bash
cd $THESIS_ROOT
python3 tools/decide_queue_buffer_default.py \
  --q1-json reports/timing/<q1_report>.json \
  --q2-json reports/timing/<q2_report>.json \
  --baseline-queue 2 \
  --min-timing-hz 9.0 \
  --dpm-mean-tolerance 0.10 \
  --zero-ratio-delta-max 0.05 \
  --json-out reports/timing/queue_decision_$(date +%Y%m%d_%H%M%S).json
```

Interpretation:

- exit code `0`: gates passed and default selected.
- exit code `1`: one or more gates failed (no decision).
- exit code `2`: input/schema error.

Important:

- For cutover decisions, do not use `--allow-missing-detection-load`.
- Use `--allow-missing-detection-load` only for smoke-checking older reports
  that predate `detection_stream` stats.
- If your shell uses `set -e` and you still want JSON output when gates fail,
  add `--exit-zero-on-gate-fail`.

### 10.5) Tracker-side optimization variant (when queue gate stalls)

If q1 vs q2 remains blocked by low Hz/comparability, run a tracker-focused pass
with lower instrumentation overhead and tuned SORT gating.

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh \
  --perception-mode single-process \
  --perception-hailo-queue-buffers 2 \
  --tracker-gc-probe-off \
  --tracker-iou-threshold 0.22 \
  --tracker-max-age 3 \
  --tracker-min-hits 2 \
  --tracker-centre-gate 320.0
```

Then collect a standard 10-minute artifact and compare against baseline.

### 10.6) Perception container_queue optimization variant (videoconvert ablation)

Use this when `/timing` throughput is limited by pre-infer wait.

Baseline (videoconvert enabled):

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh \
  --perception-mode single-process \
  --perception-hailo-videoconvert-on
```

Ablation candidate (disable pre-hailonet videoconvert):

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh \
  --perception-mode single-process \
  --perception-hailo-videoconvert-off
```

For either run, collect a normal 10-minute timing report and compare:

- `/timing` Hz
- `container_queue_ms` p50/p95/mean
- `e2e_det_ms` p95/p99
- `pub_dt_ms` p95/p99
- detection workload comparability (`detections_per_msg.mean`, `zero_ratio`)
