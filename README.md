# Thesis Workspace

ROS 2 workspace for live camera perception, target tracking/selection, optional control output, and dashboard operation. The same repository also supports deterministic replay and offline analysis from recorded bags.

This root documentation is intentionally limited to 3 files:

- `README.md` (this file): onboarding and navigation
- `REPO_DEEP_DIVE.md`: objectives, architecture, and repository structure explained in depth
- `RUNBOOK.md`: concrete commands for setup, live operation, replay, analysis, and troubleshooting

If you read only these files, you should be able to run the core workflows.

## Project objective

Provide an end-to-end experimental stack that can:

1. Ingest camera frames in ROS 2.
2. Run detector inference through either the legacy Hailo service path or the new single-process perception path.
3. Track and select a target for control and UI.
4. Publish telemetry/video/control interfaces for real-time operation.
5. Record and replay experiments for timing/tracking evaluation.

## Choose your path

### Path A (target): RPi5 + Hailo live operation

Use this when you need full end-to-end behavior (camera + inference + tracker + target + optional control + dashboard).

1. Read `RUNBOOK.md` sections 0 to 3.
2. Start stack with `./tools/start_live_stack.sh`.
3. Start UI with `./tools/start_ui_stack.sh`.

### Path B: Generic Linux fallback

Use this when hardware acceleration is unavailable and you need UI/development/replay workflows.

1. Frontend-only mock mode:

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
cd "$THESIS_ROOT/user-interface"
npm install
VITE_DASHBOARD_DATA_MODE=mock npm run dev
```

1. Replay and offline analysis: follow `RUNBOOK.md` section 5.

## Done criteria (what "runs well" means)

The repository is considered operational when all three are satisfied:

1. Live stack starts end-to-end on target hardware (RPi5 + Hailo path).
2. Bag replay workflow runs and publishes expected replay topics.
3. Timing and tracking analyses complete and generate reports/figures.

Each criterion has commands and verification checks in `RUNBOOK.md`.

## Quick commands

### Set baseline environment

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

### Start live stack (recommended default)

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh
```

Perception mode options:

```bash
# Legacy mode: camera + inference_client + container detection_zmq
./tools/start_live_stack.sh --perception-mode legacy

# Single-process mode (default): camera + perception_pipeline_node
# Note: falls back to a stub backend if host Hailo runtime is unavailable.
./tools/start_live_stack.sh --perception-mode single-process
```

Host Hailo helpers:

```bash
# Install/probe Python wheels for host bindings
./tools/install_host_hailo_bindings.sh

# Optional no-root local runtime shim for single-process mode
# (extracts a local tappas runtime under infer_service/opt/tappas_runtime_3_31)
./tools/setup_local_tappas_runtime.sh
```

### Start UI in a second terminal

```bash
cd "$THESIS_ROOT"
./tools/start_ui_stack.sh
```

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

## Glossary

- Raw bag: high-fidelity bag used for replay/evaluation (`bags/raw`).
- Live camera bag: lean operational bag from live runs (`bags/live_camera`).
- Eval bag: replay output bag used for tracking metrics (`bags/eval`).
- Inference client: ROS node that sends frames to detector service over ZMQ.
- Detector service: container-side process serving detections to ROS.
- Dashboard bridge: ROS-to-web telemetry bridge for UI.

## Where to read next

- `REPO_DEEP_DIVE.md`: deep explanation of architecture, component contracts, and folder taxonomy.
- `RUNBOOK.md`: step-by-step setup and operations.
- `Written Logs/`: weekly/daily engineering notes and experiment history.
