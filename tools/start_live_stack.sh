#!/usr/bin/env bash
set -euo pipefail

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
PI_AI_DIR="${PI_AI_DIR:-$HOME/pi-ai-kit-ubuntu}"
CONTAINER_NAME="${CONTAINER_NAME:-pi-ai-kit-ubuntu-hailo-ubuntu-pi-1}"
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}') }"

if [[ -z "${PI_IP// }" ]]; then
    PI_IP="127.0.0.1"
fi

LOG_ROOT="$THESIS_ROOT/log/live_stack"
RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
RUN_DIR="$LOG_ROOT/$RUN_ID"
PID_FILE="$RUN_DIR/pids.txt"
LATEST_LINK="$LOG_ROOT/latest"

mkdir -p "$RUN_DIR"
ln -sfn "$RUN_DIR" "$LATEST_LINK"

start_ros_bg() {
    local name="$1"
    shift
    "$@" >"$RUN_DIR/${name}.log" 2>&1 &
    local pid=$!
    echo "$pid $name" >>"$PID_FILE"
    echo "[start] $name (pid=$pid)"
}

kill_tree() {
    local pid="$1"
    local sig="${2:-TERM}"

    if [[ -z "${pid:-}" ]]; then
        return
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
        return
    fi

    local child
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        kill_tree "$child" "$sig"
    done

    kill -s "$sig" "$pid" >/dev/null 2>&1 || true
}

STOP_DONE=0
stop_stack() {
    if [[ "$STOP_DONE" -eq 1 ]]; then
        return
    fi
    STOP_DONE=1

    echo "[step] stopping live stack"

    if [[ -f "$PID_FILE" ]]; then
        tac "$PID_FILE" | while read -r pid name; do
            if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
                kill_tree "$pid" INT
                echo "[stop] $name (pid=$pid)"
            fi
        done

        sleep 1

        tac "$PID_FILE" | while read -r pid _name; do
            if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
                kill_tree "$pid" TERM
            fi
        done
    fi

    # Force-clean known host-side processes in case ros2 launch left children behind.
    pkill -f "camera_bringup.launch.py" >/dev/null 2>&1 || true
    pkill -f "camera_capture_node" >/dev/null 2>&1 || true
    pkill -f "inference_client_node" >/dev/null 2>&1 || true
    pkill -f "tracker_node" >/dev/null 2>&1 || true
    pkill -f "target_selector_node" >/dev/null 2>&1 || true
    pkill -f "dashboard_bridge_node" >/dev/null 2>&1 || true
    pkill -f "web_video_server" >/dev/null 2>&1 || true

    docker exec "$CONTAINER_NAME" bash -lc 'pkill -f detection_zmq.py >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
    echo "[done] live stack stop requested"
}

trap 'stop_stack; exit 0' INT TERM

wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout_s="$3"

    local start_ts
    start_ts="$(date +%s)"

    while true; do
        if (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
            echo "[ok] port ${host}:${port} is reachable"
            return 0
        fi

        local now
        now="$(date +%s)"
        if (( now - start_ts >= timeout_s )); then
            echo "[warn] timeout waiting for ${host}:${port}; continuing anyway"
            return 0
        fi
        sleep 1
    done
}

echo "[info] logs: $RUN_DIR"
echo "[step] sourcing ROS environment"
cd "$ROS_WS"
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u

echo "[step] ensuring container is up"
(
    cd "$PI_AI_DIR"
    docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
) >"$RUN_DIR/container_up.log" 2>&1

echo "[step] starting detection service in container"
docker exec "$CONTAINER_NAME" bash -lc '
set -euo pipefail
for pid in $(pgrep -f detection_zmq.py || true); do
    if [ "$pid" != "$$" ]; then
        kill "$pid" >/dev/null 2>&1 || true
    fi
done
VENV=/root/hailo-rpi5-examples/venv_hailo_rpi_examples
export PYTHONPATH=/root/hailo-rpi5-examples:${PYTHONPATH:-}
cd /root/thesis_service
export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND=tcp://0.0.0.0:5556
export HAILO_INFER_WIDTH=640
export HAILO_INFER_HEIGHT=640
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter
nohup "$VENV/bin/python" /root/thesis_service/detection_zmq.py > /tmp/detection_zmq_live.log 2>&1 &
' >"$RUN_DIR/container_infer_start.log" 2>&1

wait_for_port 127.0.0.1 5556 20

echo "[step] starting ROS nodes"
start_ros_bg camera ros2 launch thesis_bringup camera_bringup.launch.py
sleep 2

start_ros_bg inference ros2 run thesis_inference_client inference_client_node --ros-args \
    -p image_topic:=/camera/image_raw \
    -p addr:=tcp://127.0.0.1:5556 \
    -p queue_size:=1 \
    -p img_w:=640 \
    -p img_h:=640 \
    -p min_score:=0.35
sleep 1

start_ros_bg tracker ros2 run thesis_tracker tracker_node
sleep 1

start_ros_bg target_selector ros2 run thesis_target_selector target_selector_node
sleep 1

start_ros_bg dashboard_bridge ros2 run thesis_bringup dashboard_bridge_node --ros-args \
    -p img_w:=640 \
    -p img_h:=640
sleep 1

start_ros_bg web_video ros2 run web_video_server web_video_server --ros-args -p port:=8080
wait_for_port 127.0.0.1 8080 15

VIDEO_URL="http://${PI_IP}:8080/stream?topic=/camera/dashboard&type=mjpeg"
WS_URL="ws://${PI_IP}:8765"

echo "[done] live stack started"
echo "[info] PID file: $PID_FILE"
echo "[info] tail logs: tail -f $RUN_DIR/*.log"
echo "[info] video: $VIDEO_URL"
echo "[info] telemetry ws: $WS_URL"
echo "[info] type stop, quit, or exit to stop everything"

while true; do
    if ! read -r -p "live-stack> " cmd; then
        cmd="exit"
    fi

    case "${cmd,,}" in
        stop|quit|exit)
            stop_stack
            break
            ;;
        clear)
            clear
            ;;
        status)
            echo "[info] running pids from $PID_FILE"
            if [[ -f "$PID_FILE" ]]; then
                cat "$PID_FILE"
            else
                echo "[warn] no pid file found"
            fi
            ;;
        *)
            echo "[info] unknown command: $cmd"
            echo "[info] valid commands: status, clear, stop, quit, exit"
            ;;
    esac
done
