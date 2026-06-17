# Thesis Workspace

Last reviewed: 2026-05-26

ROS 2 workspace for live camera perception, tracking, selected-target identity memory, user-driven target selection, optional control output, dashboard operation, and reproducible replay/analysis.

## Documentation map

Root documentation is split by purpose:

- `README.md` (this file): orientation, quick paths, and navigation.
- `RUNBOOK.md`: command source of truth for setup, live operation, replay, analysis, and troubleshooting.
- `REPO_DEEP_DIVE.md`: architecture, boundaries, package responsibilities, and repository layout.
- `docs/Debug/LIVE_STACK_CAMERA_RECOVERY.md`: camera failure triage/recovery for RPi5 + TEVS incidents.

## Runtime snapshot

- Default live command: `./tools/start_live_stack.sh`.
- Default live stack: integrated camera perception, VGA capture, 640x640 Hailo inference, ByteTrack, TIM-MARS appearance, dashboard target 30 FPS, control enabled, web video enabled.
- Recording command: `./tools/start_live_stack.sh --record --tag <name>`.
- Target selection is user-driven through `dashboard_bridge_node` and `POST /api/target`.
- Live logs are centralized under `ros2_ws/log/live_stack/<run-id>` and UI logs under `ros2_ws/log/ui_stack/<run-id>`.

## Current thesis status

The active thesis focus is selected-target identity maintenance for micro-UAV following. The system must keep the operator-selected person, not merely any visible track, through occlusion, hard crossings, detector misses, tracker ID switches, and distractors.

Current TIM framing:

- TIM-V0 is the frozen geometry-only selected-target memory baseline.
- TIM-V1 added optional lightweight appearance support.
- TIM Final is being driven by target-correctness evaluation rather than valid-output duration alone.
- DeepSORT MARS is now used as a strong appearance-based baseline.

Current hard re-entry comparison:

| Method | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|
| Raw OCSORT `/target` | 0.519 | 0.316 | 0.166 |
| OCSORT + TIM `/target_memory_mars` | 0.713 | 0.278 | 0.009 |
| Raw DeepSORT MARS `/target` | 0.684 | 0.071 | 0.245 |

Interpretation:

- OCSORT + TIM improves correct duration and nearly eliminates lost duration.
- DeepSORT MARS is much safer against wrong-target output.
- TIM Final must reduce wrong-target duration while keeping runtime cost closer to OCSORT/TIM than to DeepSORT MARS.

## Live stack operator cheat sheet

Default live stack:

    ./tools/start_live_stack.sh

Record a live bag:

    ./tools/start_live_stack.sh --record --tag demo1

Reduce dashboard load:

    ./tools/start_live_stack.sh --dash 10

Use a lighter debug tracker:

    ./tools/start_live_stack.sh --tracker sort --mem off

Show advanced tuning options:

    ./tools/start_live_stack.sh --help-advanced

Validated full-stack recording result from 2026-06-17:

- `/detections`: 29.92 Hz
- `/tracks`: 29.91 Hz
- `/target`: 29.89 Hz
- `/target_memory_mars`: 29.34 Hz
- `/control_ref/cmd_vel`: 29.91 Hz
- `/camera/dashboard`: 8.19 Hz recorded
- thermal status: `throttled=0x0`

## Project objective

Provide an end-to-end experimental stack that can:

1. Ingest camera frames in ROS 2.
2. Run detector inference through the integrated camera Hailo pipeline.
3. Track candidates and expose explicit user-driven target selection for control and UI.
4. Maintain selected-target identity through TIM and publish `/target_memory_mars` when TIM-MARS is enabled.
5. Publish telemetry/video/control interfaces for real-time operation.
6. Record and replay experiments for target-correctness, timing, and tracking evaluation.

## Choose your path

### Path A (target): RPi5 + Hailo live operation

Use when you need full end-to-end behavior (camera + perception + tracker + target + control + dashboard).

1. Follow `RUNBOOK.md` sections 1 through 3.
2. Start stack with `./tools/start_live_stack.sh`.
3. Start UI with `./tools/start_ui_stack.sh`.

### Path B: Generic Linux fallback

Use when Hailo hardware is unavailable and you need UI/replay/analysis workflows.

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
cd "$THESIS_ROOT"
./tools/start_ui_stack.sh --mode mock
```

Use `--mode offline` when you want a single local snapshot without any backend connection.
Replay and analysis commands are in `RUNBOOK.md`.


## Quick start

### 1) Set baseline environment

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

Optional: create a Python virtual environment for tools and analysis scripts

```bash
cd "$THESIS_ROOT"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
# Install any repo-specific Python deps if provided
# e.g. pip install -r tools/requirements.txt
```

Frontend dependencies (for `user-interface`)

```bash
cd "$THESIS_ROOT/user-interface"
npm ci
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
ros2 topic list | rg '/camera/dashboard|/detections|/tracks|/target|/target_memory_mars|/timing'
ss -ltnp | rg ':8080|:8090|:8765|:5173'
```

Note: the active live stack uses dashboard/API/WebSocket ports only; the old detector req/rep port is not required.

## Fast failure triage

If live startup aborts, check in this order:

1. Launcher logs in `ros2_ws/log/live_stack/latest/` (camera, perception, tracker, dashboard, and control logs are split per component).
2. Camera-specific recovery actions in `docs/Debug/LIVE_STACK_CAMERA_RECOVERY.md`.
3. Full troubleshooting and manual fallback steps in `RUNBOOK.md` section 6.

## Common workflows

### Replay an existing bag

```bash
cd "$THESIS_ROOT/ros2_ws"
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/artifacts/bags/live_camera/<bag_name> \
  tracker:=sort
```

Replay note:

- Target selection is now strictly user-driven through `dashboard_bridge_node`.
- `POST /api/target` is the only supported way to select a target.
- There is no automatic target-selection fallback in replay flows.
- When no target is explicitly selected, `/target` publishes the empty target state.

### Run timing analysis

```bash
cd "$THESIS_ROOT"
python3 tools/analysis/analyse_bag_timing.py "$THESIS_ROOT/artifacts/bags/live_camera/<bag_name>"
```

### Run tracking analysis

```bash
cd "$THESIS_ROOT"
python3 tools/analysis/analyse_bag_tracking.py "$THESIS_ROOT/artifacts/bags/eval/<eval_bag_name>"
```

## Done criteria

Repository operation is considered healthy when all three are true:

1. Live stack starts end-to-end on target hardware.
2. Replay runs on recorded bags and publishes expected topics.
3. Timing and tracking analyses complete and generate report artifacts.

## Where to read next

- `RUNBOOK.md` for exact commands and troubleshooting.
- `REPO_DEEP_DIVE.md` for architecture and boundaries.
- `docs/Debug/LIVE_STACK_CAMERA_RECOVERY.md` for camera incident response.
