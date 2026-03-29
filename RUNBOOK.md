# Runbook

Practical commands for day-to-day operation.
All commands run from $THESIS_ROOT unless noted.

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
- tools/start_live_stack.sh now automatically forces ROS_LOG_DIR to ros2_ws/log/runtime/<run-id>.
- tools/start_live_stack.sh run logs are under ros2_ws/log/live_stack/<run-id>.
- tools/start_ui_stack.sh run logs are under ros2_ws/log/ui_stack/<run-id>.
- If you see logs in ~/.ros/log during live stack startup, verify you started with tools/start_live_stack.sh and not a manual command in another shell.

## 2) Live stack (recommended)

```bash
cd $THESIS_ROOT
./tools/start_live_stack.sh
```

Default:
- control_ref_node enabled
- MAVROS mirror disabled (safe default)
- ROS_DOMAIN_ID defaults to 42 unless already exported

Useful flags:
- Disable control: ./tools/start_live_stack.sh --no-control
- Enable MAVROS mirror: ./tools/start_live_stack.sh --control-mavros
- Camera + inference only: ./tools/start_live_stack.sh --no-tracker --no-target --no-control --no-dashboard

Stop:
- In prompt: stop, quit, or exit
- Fallback: ./tools/stop_live_stack.sh

Run UI in parallel (second terminal):

```bash
cd $THESIS_ROOT
./tools/start_ui_stack.sh --skip-install
```

Useful UI flags:
- Mock mode: ./tools/start_ui_stack.sh --mode mock
- Custom port: ./tools/start_ui_stack.sh --port 5174

## 3) Manual startup (fallback)

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
cd ~/pi-ai-kit-ubuntu
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi

docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash
# inside container
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
ros2 run thesis_target_selector target_selector_node
ros2 run thesis_bringup dashboard_bridge_node --ros-args -p img_w:=640 -p img_h:=640
ros2 run web_video_server web_video_server --ros-args -p port:=8080
```

Dashboard:
- Video: http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45
- Telemetry: ws://<PI_IP>:8765
- Control API: http://<PI_IP>:8090

## 4) Record bags

Lean operational bag:

```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export RMW_FASTRTPS_USE_SHM=0

ros2 bag record --storage mcap \
  -o ../bags/live_camera/YYYY-MM-DD__<session_description> \
  /camera/fps /detections /timing /target
```

Raw profiling bag:

```bash
cd $THESIS_ROOT/bags/raw
ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker
# rename output folder after stop
```

## 5) Replay and analysis

Eval replay:

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<bag_name> \
  tracker:=sort
```

Timing:

```bash
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/raw/<bag_name>
# or
python3 tools/analyse_bag_timing.py $THESIS_ROOT/bags/live_camera/<bag_name>
```

Tracking:

```bash
python3 tools/analyse_bag_tracking.py $THESIS_ROOT/bags/eval/<eval_bag_name>
```

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
- Check cable/sensor state.
- If camera process is stuck in D state, reboot host.

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
