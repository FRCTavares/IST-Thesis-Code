# Thesis Workspace

Last reviewed: 2026-05-26

ROS 2 workspace for live camera perception, tracking, selected-target identity memory, user-driven target selection, optional control output, dashboard operation, and reproducible replay/analysis.

## Documentation map

Root documentation is split by purpose:

- `README.md` (this file): orientation, quick paths, and navigation.
- `RUNBOOK.md`: command source of truth for setup, live operation, replay, analysis, and troubleshooting.
- `REPO_DEEP_DIVE.md`: architecture, boundaries, package responsibilities, and repository layout.
- `LIVE_STACK_CAMERA_RECOVERY.md`: camera failure triage/recovery for RPi5 + TEVS incidents.
- `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md`: migration history, performance gates, and optimization backlog.

## Runtime snapshot

- Default live perception mode is `single-process` via `./tools/start_live_stack.sh`.
- Legacy frame-ZMQ mode remains available as `--perception-mode legacy` for rollback and debugging.
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
| OCSORT + TIM `/target_memory` | 0.713 | 0.278 | 0.009 |
| Raw DeepSORT MARS `/target` | 0.684 | 0.071 | 0.245 |

Interpretation:

- OCSORT + TIM improves correct duration and nearly eliminates lost duration.
- DeepSORT MARS is much safer against wrong-target output.
- TIM Final must reduce wrong-target duration while keeping runtime cost closer to OCSORT/TIM than to DeepSORT MARS.

## Live stack operator cheat sheet

Most live sessions start with one of these:

```bash
cd "$THESIS_ROOT"

# Baseline daily profile (default)
./tools/start_live_stack.sh --profile daily

# Conservative camera-first profile (uses 640x480 defaults)
./tools/start_live_stack.sh --profile safe-camera

# Slightly tighter latency defaults
./tools/start_live_stack.sh --profile performance
```

While the script is running, use the built-in prompt commands:

- `status` to print tracked process IDs.
- `ids` to show visible track IDs.
- `target <id>` to select an active target.
- `clear-target` to clear the selection.
- `clear` to clear terminal noise.
- `stop` (or `exit`) for ordered shutdown.

If you need full option coverage, including tracker and perception tuning:

```bash
./tools/start_live_stack.sh --help-advanced
```

## Project objective

Provide an end-to-end experimental stack that can:

1. Ingest camera frames in ROS 2.
2. Run detector inference through either the default single-process Hailo pipeline or the legacy ZMQ rollback path.
3. Track candidates and expose explicit user-driven target selection for control and UI.
4. Maintain selected-target identity through TIM and publish `/target_memory` when target memory is enabled.
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
./tools/start_live_stack.sh --profile daily
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
ros2 topic list | rg '/camera/image_raw|/camera/dashboard|/detections|/tracks|/target|/target_memory|/timing'
ss -ltnp | rg ':5556|:8080|:8090|:8765|:5173'
```

Note: `:5556` is expected only in legacy mode.

## Fast failure triage

If live startup aborts, check in this order:

1. Launcher logs in `ros2_ws/log/live_stack/latest/` (camera/inference process logs are split per component).
2. Camera-specific recovery actions in `LIVE_STACK_CAMERA_RECOVERY.md`.
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
- `LIVE_STACK_CAMERA_RECOVERY.md` for camera incident response.
- `SINGLE_PROCESS_PERCEPTION_MIGRATION_PLAN.md` for migration/performance context.
