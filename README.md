# Thesis Workspace

ROS 2 workspace for live camera perception, tracking/targeting, optional control output, dashboard operation, and reproducible replay/analysis.

## Documentation map

Root documentation is split by purpose:

- `README.md` (this file): orientation, quick paths, and navigation.
- `RUNBOOK.md`: command source of truth for setup, live operation, replay, analysis, and troubleshooting.
- `REPO_DEEP_DIVE.md`: architecture, boundaries, package responsibilities, and repository layout.
- `LIVE_STACK_CAMERA_RECOVERY.md`: camera failure triage/recovery for RPi5 + TEVS incidents.
- `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md`: migration history, performance gates, and optimization backlog.

## Runtime snapshot (2026-04-15)

- Default live perception mode is `single-process` (`./tools/start_live_stack.sh`).
- Legacy ZMQ path (`--perception-mode legacy`) remains available as rollback/troubleshooting mode.
- Default control/dashboard stack is enabled in live startup unless explicitly disabled.
- Live logs are centralized under `ros2_ws/log/live_stack/<run-id>` and ROS runtime logs under `ros2_ws/log/runtime/<run-id>`.

## Project objective

Provide an end-to-end experimental stack that can:

1. Ingest camera frames in ROS 2.
2. Run detector inference through either single-process Hailo pipeline (default) or legacy ZMQ service path.
3. Track and select a target for control and UI.
4. Publish telemetry/video/control interfaces for real-time operation.
5. Record and replay experiments for timing/tracking evaluation.

## Choose your path

### Path A (target): RPi5 + Hailo live operation

Use when you need full end-to-end behavior (camera + perception + tracker + target + control + dashboard).

1. Follow `RUNBOOK.md` sections 0 through 3.
2. Start stack with `./tools/start_live_stack.sh`.
3. Start UI with `./tools/start_ui_stack.sh`.

### Path B: Generic Linux fallback

Use when Hailo hardware is unavailable and you need UI/replay/analysis workflows.

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
cd "$THESIS_ROOT"
./tools/start_ui_stack.sh --mode mock
```

Replay/analysis commands are in `RUNBOOK.md` section 5.

### Path C: Legacy perception rollback

Use only when you need the historical frame-ZMQ path:

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh --perception-mode legacy
```

## Quick start

### 1) Set baseline environment

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

### 2) Build ROS workspace once

```bash
cd "$THESIS_ROOT/ros2_ws"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

### 3) Start live stack

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh
```

### 4) Start UI (second terminal)

```bash
cd "$THESIS_ROOT"
./tools/start_ui_stack.sh
```

### 5) Verify core health

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
ros2 topic list | rg '/camera/image_raw|/detections|/timing|/target'
ss -ltnp | rg ':5556|:8080|:8090|:8765'
```

Note: `:5556` is expected only in legacy mode.

## Common workflows

### Replay an existing raw bag

```bash
cd "$THESIS_ROOT/ros2_ws"
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name> \
  tracker:=sort
```

### Run timing analysis

```bash
cd "$THESIS_ROOT"
python3 tools/analyse_bag_timing.py "$THESIS_ROOT/bags/raw/<bag_name>"
```

### Run tracking analysis

```bash
cd "$THESIS_ROOT"
python3 tools/analyse_bag_tracking.py "$THESIS_ROOT/bags/eval/<eval_bag_name>"
```

## Done criteria

Repository operation is considered healthy when all three are true:

1. Live stack starts end-to-end on target hardware.
2. Replay runs on recorded bags and publishes expected topics.
3. Timing/tracking analyses complete and generate report artifacts.

## Where to read next

- `RUNBOOK.md` for exact commands and troubleshooting.
- `REPO_DEEP_DIVE.md` for architecture and boundaries.
- `LIVE_STACK_CAMERA_RECOVERY.md` for camera incident response.
- `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md` for migration/performance context.
