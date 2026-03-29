# Thesis workspace

ROS-first workspace for live perception/control experiments, replay evaluation, and dashboard operation.

## Quick start

### 1) Set environment

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42
```

### 2) Frontend only (no ROS/hardware)

```bash
cd $THESIS_ROOT/user-interface
npm install
VITE_DASHBOARD_DATA_MODE=mock npm run dev
```

### 3) Live stack (recommended)

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

### 4) Replay + analysis

Use workflows in RUNBOOK.md.

## Logging policy (important)

Keep all ROS and colcon logs under ros2_ws:

- colcon logs/build/install are pinned via RUNBOOK setup to ros2_ws/{log,build,install}
- tools/start_live_stack.sh now forces ROS_LOG_DIR to:
  - ros2_ws/log/runtime/<run-id>

If you run ROS commands manually, set ROS_LOG_DIR yourself before launching nodes.

## System architecture

Active flow:

Drone -> ROS Topics -> Dashboard Bridge + web_video_server -> Dashboard UI

Main components:

- ros2_ws/src/thesis_bringup: launch files + dashboard bridge + control node
- ros2_ws/src/thesis_inference_client: ZMQ inference client
- ros2_ws/src/thesis_tracker: SORT/OC-SORT/ByteTrack tracker node
- ros2_ws/src/thesis_target_selector: target lock/selection node
- infer_service: container-side detection service
- user-interface: React + TypeScript dashboard
- tools: bag/timing/tracking analysis scripts

## Core workflows

### Live run

```bash
./tools/start_live_stack.sh
```

### Record lean operational bag

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__<session_description> \
  /camera/fps /detections /timing /target
```

### Eval replay

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name> \
  tracker:=sort
```

### Timing analysis

```bash
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/raw/<bag_name>
```

### Tracking analysis

```bash
python3 tools/analyse_bag_tracking.py $THESIS_ROOT/bags/eval/<eval_bag_name>
```

## References

- RUNBOOK.md: operational commands and troubleshooting
- Written Logs/: weekly and daily planning/execution notes
