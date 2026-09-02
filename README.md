# README

Practical commands for day-to-day operation.
All commands run from `$THESIS_ROOT` unless noted.

Use this file as the command source of truth.

## Final thesis artifacts

For final TIM-MARS result evidence and local verification, start here:

- `docs/data/final_experiment_inventory.md`: promoted final replay bags, reports, and annotation CSVs.
- `docs/data/reproduce_final_results.md`: local checks for final result artifact availability.
- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`: clean canonical selected-target evidence.
- `docs/results/live/p052_target_authority_ground_evidence.md`: three retained isolated target-authority dry-runs for Issue #52.
- `bags/README.md`: bag roles, deletion policy, and naming contract.
- `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/README.md`: TIM-MARS module structure and configuration guide.

## Current runtime defaults

From `tools/start_live_stack.sh`:

- Default command: `./tools/start_live_stack.sh`
- Perception mode: integrated camera only
- Camera capture: 640x480
- Hailo inference: 640x640
- Detector default: YOLOv8s
- Tracker default: ByteTrack
- Target memory default: TIM-MARS
- TIM-MARS appearance: enabled
- Dashboard target: 30 FPS
- Control node: enabled
- Web video: enabled
- Recording: disabled by default, enabled with `--record`
- Bag tag option: `--tag <name>`

The 2026-06-17 validated full-stack recording held the critical topics at approximately 30 Hz with `throttled=0x0`.

## Scope and assumptions

- Primary platform: Raspberry Pi 5 + Hailo (full live stack).
- Fallback platform: generic Linux (UI, replay, offline analysis).
- ROS 2 distro: Jazzy.
- Workspace root: `$HOME/Desktop/Thesis-Code`.

## Clean-checkout installation

The supported development environment is Ubuntu 24.04 with ROS 2 Jazzy.

Install the generic host tools:

    sudo apt update
    sudo apt install -y \
      git \
      python3-colcon-common-extensions \
      python3-rosdep \
      python3-venv

Clone the repository and enter it:

    git clone git@github.com:FRCTavares/IST-Thesis-Code.git "$HOME/Desktop/Thesis-Code"
    cd "$HOME/Desktop/Thesis-Code" || exit 1

Install dependencies declared by the ROS packages:

    source /opt/ros/jazzy/setup.bash
    sudo rosdep init 2>/dev/null || true
    rosdep update
    rosdep install \
      --from-paths ros2_ws/src \
      --ignore-src \
      --rosdistro jazzy \
      -r \
      -y

Create the ignored project-local Python environment while retaining access to
the ROS Python packages installed by apt:

    python3 -m venv --system-site-packages thesis_env
    thesis_env/bin/python -m pip install --upgrade pip pytest

Build the workspace through the repository helper:

    tools/thesis_build.sh

Then source the environment manually or enable `.envrc` with `direnv allow`.

The Hailo runtime is platform-specific and is not installed by rosdep or as a
generic PyPI dependency. On the Raspberry Pi 5 deployment host, install the
matching HailoRT and TAPPAS system runtime first. The repository helpers
`tools/setup/install_host_hailo_bindings.sh` and
`tools/setup/setup_local_tappas_runtime.sh` support compatible host setups.

The browser frontend is owned by the separate `FRCTavares/IST-Thesis-UI` repository. The expected co-located checkout is:

    $HOME/Desktop/IST-Thesis-UI

Install its locked Node.js dependencies from that repository when needed:

    cd $HOME/Desktop/IST-Thesis-UI
    ./tools/start_dashboard.sh --install --mode backend

`Thesis-Code/tools/start_ui_stack.sh` remains only as a compatibility shim that delegates to that external launcher.

## 1) One-time shell setup

In ~/.bashrc set:

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

## 2) Live stack

Start the validated live stack:

    ./tools/start_live_stack.sh

Start the validated live stack and record:

    ./tools/start_live_stack.sh --record --tag flight_01

Useful short options:

    ./tools/start_live_stack.sh --dash 10
    ./tools/start_live_stack.sh --tracker sort --mem off
    ./tools/start_live_stack.sh --no-control
    ./tools/start_live_stack.sh --no-dashboard
    ./tools/start_live_stack.sh --help-advanced

Startup order:

1. Preflight and camera health checks.
2. `perception_camera_node` captures frames, runs Hailo inference, and publishes `/detections`, `/timing`, and `/camera/dashboard`.
3. `tracker_node` publishes `/tracks`.
4. `dashboard_bridge_node` publishes raw `/target` for telemetry and sends
   explicit selection commands on `/target_memory_mars/select` or
   `/target_memory_mars/clear`.
5. `target_memory_mars_node` validates identity and publishes the only
   controller-authoritative target on `/target_memory_mars`.
6. `control_ref_node` subscribes to `/target_memory_mars` and publishes
   `/control_ref/cmd_vel`. Raw `/target` never drives control.

The frozen live profile rejects runtime detector and tracker switching. Restart
the stack with an explicitly validated model/tracker instead. Selecting or
clearing a target immediately revokes the previous control authority until
TIM-MARS publishes a new valid target.

Removed runtime paths:

- no split camera-to-perception node chain;
- no separate live perception pipeline executable;
- no container/Docker/ZMQ inference service;
- no full-rate live raw image transport.

Detector inference is performed directly in-process through the current Hailo
runtime.

### Tracker modes

The live stack supports multiple tracker backends:

```bash
./tools/start_live_stack.sh --tracker sort
./tools/start_live_stack.sh --tracker ocsort
./tools/start_live_stack.sh --tracker bytetrack
./tools/start_live_stack.sh --tracker deepsort
```

Full option list:

```bash
./tools/start_live_stack.sh --help
./tools/start_live_stack.sh --help-advanced
```

If you want to enable host-side Hailo dependencies:

- Install or probe host Python bindings: `./tools/setup/install_host_hailo_bindings.sh`
- Optional no-root runtime shim: `./tools/setup/setup_local_tappas_runtime.sh`

Note:

- start_live_stack.sh auto-detects local runtime assets from infer_service/opt/tappas_runtime_3_31 when present.

Stop:

- In prompt: `stop`, `quit`, or `exit`
- If the interactive shell is gone, terminate stack processes explicitly:

```bash
pkill -f 'perception_camera_node|tracker_node|target_memory_mars_node|control_ref_node|dashboard_bridge_node|web_video_server' || true
```

Verification checkpoint for a healthy live stack:

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
ros2 topic list | rg '/camera/dashboard|/detections|/timing|/target|/target_memory_mars'
ss -ltnp | rg ':8080|:8090|:8765|:5173'
```

Expected:

- Core topics are listed.
- Required service ports are listening for dashboard video, API, WebSocket, and UI services.

Run the browser frontend in parallel from the separate UI repository (second terminal):

```bash
cd $HOME/Desktop/IST-Thesis-UI
./tools/start_dashboard.sh --mode backend
```

The frontend launcher defaults to `127.0.0.1:5173`. For an explicitly approved field-network/iPhone session, bind it deliberately:

```bash
cd $HOME/Desktop/IST-Thesis-UI
./tools/start_dashboard.sh --mode backend --host 0.0.0.0 --port 5173
```

Do not treat that bind as an access-control policy. API, WebSocket, video, firewall, CORS, and field-network exposure are separate Issue #55 backend security contracts.

The historical Thesis-Code command remains available for operator compatibility:

```bash
cd $THESIS_ROOT
./tools/start_ui_stack.sh --mode backend --host 0.0.0.0
```

That command contains no frontend implementation. It resolves `${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}` and delegates to the UI-owned `IST-Thesis-UI/tools/start_dashboard.sh` launcher.

The live ROS/backend services remain owned by `tools/start_live_stack.sh`: `dashboard_bridge_node` provides the HTTP API and telemetry WebSocket, and `web_video_server` provides the MJPEG stream.

Verification checkpoint for the UI:

- Open `http://127.0.0.1:5173` for a local-only launch, or the approved Pi field-network address when an explicit network bind is in use.
- In backend mode, confirm API `:8090`, WebSocket `:8765`, and video `:8080` are reachable through the intended network policy.

## 3) Manual startup

Supported live runtime:

    ./tools/start_live_stack.sh

Outdoor recording command:

    ./tools/start_live_stack.sh --record --record-mavros --tag outdoor_01

## 4) Record flight video bags

The recommended flight recording path is integrated into `tools/start_live_stack.sh`.

Use `--record` to record the dashboard image stream plus the perception, tracking, target, timing, and control topics required for later analysis and offline overlay rendering.

Every recorded live run also stores target-authority provenance. The dashboard
appends startup, select, clear, and switch-attempt generations to
`target_authority_events.jsonl`; stack shutdown archives that JSONL file beside
the bag. `flight_metadata.txt` records the authoritative topic, initial
generation, runtime log path, and frozen reconfiguration state.

### 4.1) Standard flight video bag

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh --record --tag flight_01
```

This records to:

`bags/live_camera/YYYY-MM-DD__HH-MM-SS__video__flight_01/`

Recorded topics:
/camera/dashboard
/camera/fps
/detections
/tracks
/target
/timing
/timing_tracker
/timing_target
/control_ref/cmd_vel

Notes:

- /camera/dashboard is recorded to keep field bags small; the live integrated path does not publish full-rate raw images.
- /timing_tracker is enabled automatically when --record is used.
- A flight_metadata.txt file is written next to the bag with run configuration, tracker type, perception mode, camera settings, and recorded topics.

### 4.2) Flight video bag with MAVROS context

Use this when flying with the autopilot connected and you want basic flight-state context:

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh --record --record-mavros --tag outdoor_01
```

Additional MAVROS topics:

/mavros/state
/mavros/extended_state
/mavros/battery
/mavros/rc/in
/mavros/rc/out
/mavros/local_position/pose
/mavros/local_position/velocity_local
/mavros/setpoint_velocity/cmd_vel

## 5) Replay and analysis

Replay an existing bag:

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/live_camera/<bag_name> \
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
python3 tools/analysis/analyse_bag_timing.py "$THESIS_ROOT/bags/live_camera/<bag_name>"
```

Expected output:

- Markdown timing report in `reports/timing/` by default.
- Figure files in `figures/timing/` by default.

Tracking:

```bash
python3 tools/analysis/analyse_bag_tracking.py "$THESIS_ROOT/bags/eval/<eval_bag_name>"
```

Expected output:

- `summary.md` and plot files under `reports/tracking/<eval_bag_name>/` by default.

### 5.1) Runtime timing vocabulary

The current runtime contract is **Timing schema v4**. It describes only the
direct/in-process Hailo architecture and intentionally contains no
container/ZMQ compatibility fields or fallback aliases.

The complete metric definitions, timestamp semantics, intended uses, and
selective-ReID/cache workload counters are documented in
`docs/RUNTIME_METRICS.md`.

The machine-readable contract is defined by `tools/timing_contract.py` and
`ros2_ws/src/thesis_msgs/msg/Timing.msg`.

Important clock rule:

- `src_stamp_ns` is source/sensor timestamp metadata.
- detector, tracker, and TIM-MARS stage timestamps use the host monotonic clock.
- source timestamps must not be subtracted from host-monotonic timestamps unless
  clock comparability has been established for that run.

Historical bags produced with older Timing message layouts remain historical
evidence and should be analysed with the code/schema that produced them rather
than silently reinterpreted as schema v4.

### 5.2) Operator metric priority

Primary live checks:

1. `e2e_validated_target_ms` p95: camera-callback-to-controller-authority responsiveness.
2. `e2e_det_ms` p95: detector-path responsiveness.
3. `pub_dt_ms` p95 and derived detector frequency: cadence stability.
4. `pre_infer_wait_ms` p95: in-process scheduling/backpressure before Hailo inference.
5. `infer_ms` and `track_ms`: detector and tracker compute cost.

Offline analysis additionally reports `n`, mean, population standard deviation,
p50, p90, p95, p99, maximum, cadence/jitter, and the exact selective-ReID
workload/cache counters where available.

## 6) Quick troubleshooting

Camera check:

```bash
ros2 topic echo /camera/fps --once
```

Ports check:

```bash
ss -ltnp | rg ':8080|:8090|:8765|:5173'
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

- Perception pipeline startup failure:
  - Check `perception_camera.log` in the latest live-stack log directory.
  - Confirm Hailo host dependencies and local runtime assets are available when using the Hailo backend.
- Empty ROS graph:
  - Verify `ROS_DOMAIN_ID` matches all terminals.
  - Re-source `/opt/ros/jazzy/setup.bash` and workspace overlay.
- UI shows no live data:
  - Confirm API `:8090` and WS `:8765` ports are reachable.
  - Use UI mock mode to isolate backend vs frontend issues.
- `ros2 run` cannot find packages:
  - Rebuild the workspace with `colcon build --symlink-install` in `ros2_ws`.

Live log triage quick commands:

```bash
cd "$THESIS_ROOT"
ls -1 ros2_ws/log/live_stack/latest
tail -n 80 ros2_ws/log/live_stack/latest/camera.log
tail -n 80 ros2_ws/log/live_stack/latest/perception_camera.log
tail -n 80 ros2_ws/log/live_stack/latest/inference.log
```

Note: `perception_camera.log` is the active perception log.

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
- raw `/target` output cannot produce a command; live control consumes
  `/target_memory_mars` only

## 8) Canonical repository paths (for command context)

- ROS packages: `ros2_ws/src/`
- Utility scripts: `tools/`
- Live bags: `bags/live_camera/`
- Eval output bags: `bags/eval/`
- Timing reports: `reports/timing/`
- Timing figures: `figures/timing/`
- Tracking reports: `reports/tracking/`

## 9) Last validated assumptions

- Date: 2026-06-04
- ROS: Jazzy
- Default live path: integrated camera perception via `tools/start_live_stack.sh`
- Active runtime: integrated camera live stack via `tools/start_live_stack.sh`.
