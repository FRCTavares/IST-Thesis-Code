#!/usr/bin/env bash
set -euo pipefail

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
PI_AI_DIR="${PI_AI_DIR:-$HOME/pi-ai-kit-ubuntu}"
CONTAINER_NAME="${CONTAINER_NAME:-pi-ai-kit-ubuntu-hailo-ubuntu-pi-1}"
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

if [[ -z "${PI_IP// }" ]]; then
    PI_IP="127.0.0.1"
fi

LOG_ROOT="$THESIS_ROOT/log/live_stack"
RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
RUN_DIR="$LOG_ROOT/$RUN_ID"
PID_FILE="$RUN_DIR/pids.txt"
LATEST_LINK="$LOG_ROOT/latest"

declare -A PROC_PIDS

mkdir -p "$RUN_DIR"
ln -sfn "$RUN_DIR" "$LATEST_LINK"

start_ros_bg() {
    local name="$1"
    shift
    "$@" >"$RUN_DIR/${name}.log" 2>&1 &
    local pid=$!
    PROC_PIDS["$name"]="$pid"
    echo "$pid $name" >>"$PID_FILE"
    echo "[start] $name (pid=$pid)"
}

check_proc_alive() {
    local name="$1"
    local pid="${PROC_PIDS[$name]:-}"

    if [[ -z "${pid:-}" ]]; then
        echo "[error] $name has no tracked pid"
        return 1
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
        echo "[error] $name exited unexpectedly (pid=$pid)"
        if [[ -f "$RUN_DIR/${name}.log" ]]; then
            echo "[error] last log lines from $name:"
            tail -n 30 "$RUN_DIR/${name}.log" || true
        fi
        return 1
    fi

    echo "[ok] $name is running (pid=$pid)"
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
    pkill -f "control_ref_node" >/dev/null 2>&1 || true
    pkill -f "dashboard_bridge_node" >/dev/null 2>&1 || true
    pkill -f "web_video_server" >/dev/null 2>&1 || true

    docker exec "$CONTAINER_NAME" bash -lc 'pkill -f detection_zmq.py >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
    echo "[done] live stack stop requested"
}

trap 'stop_stack; exit 0' INT TERM

print_usage() {
    cat <<'EOF'
Usage: start_live_stack.sh [options]

Options:
  --tracker <sort|ocsort|bytetrack>  Tracker backend (default: sort)
    --tracker-profile-off               Disable tracker profiling instrumentation
    --tracker-profile-log-every <N>     Log tracker profile every N frames (default: 1)
    --tracker-profile-serialize-every <N>
                                                                            Serialize sample every N frames (default: 10, 0 disables)
        --tracks-off                         Disable /tracks publishing from tracker
        --timing-off                         Disable /timing publishing from inference client
    --camera-width <N>                 Camera publish width passed to camera_bringup (default: 1920)
    --camera-height <N>                Camera publish height passed to camera_bringup (default: 1080)
    --infer-queue-size <N>             Inference client frame queue size (default: 1)
    --infer-workers <N>                Inference client worker threads (default: 2)
  --no-dashboard                     Disable dashboard bridge
    --no-tracker                       Do not start tracker node
    --no-target                        Do not start target selector node
    --no-control                       Do not start control_ref_node
    --control-mavros                   Enable MAVROS mirroring in control_ref_node
    --no-web-video                     Do not start web_video_server
    --rosbag                           Record timing/tracking/control topics to rosbag
  -h, --help                         Show this help message
EOF
}

TRACKER_TYPE="sort"
TRACKER_PROFILE_ENABLED=1
TRACKER_PROFILE_LOG_EVERY_N=1
TRACKER_PROFILE_SERIALIZE_EVERY_N=10
TRACKER_PROFILE_PUBLISH_DETAILS=1
TRACKER_PROFILE_GC_PROBE=1
TRACKER_PUBLISH_TRACKS_BOOL="true"
INFER_PUBLISH_TIMING_BOOL="true"
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080
INFER_QUEUE_SIZE=1
INFER_WORKERS=2
ENABLE_DASHBOARD_BRIDGE=1
ENABLE_TRACKER=1
ENABLE_TARGET_SELECTOR=1
ENABLE_CONTROL=1
CONTROL_MAVROS_BOOL="false"
ENABLE_WEB_VIDEO=1
ENABLE_ROSBAG=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tracker)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker requires a value"
                print_usage
                exit 1
            fi
            TRACKER_TYPE="${2,,}"
            shift 2
            ;;
        --no-dashboard)
            ENABLE_DASHBOARD_BRIDGE=0
            ENABLE_WEB_VIDEO=0
            shift
            ;;
        --tracker-profile-off)
            TRACKER_PROFILE_ENABLED=0
            shift
            ;;
        --tracker-profile-log-every)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-profile-log-every requires a value"
                print_usage
                exit 1
            fi
            TRACKER_PROFILE_LOG_EVERY_N="$2"
            shift 2
            ;;
        --tracker-profile-serialize-every)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-profile-serialize-every requires a value"
                print_usage
                exit 1
            fi
            TRACKER_PROFILE_SERIALIZE_EVERY_N="$2"
            shift 2
            ;;
        --tracks-off)
            TRACKER_PUBLISH_TRACKS_BOOL="false"
            shift
            ;;
        --timing-off)
            INFER_PUBLISH_TIMING_BOOL="false"
            shift
            ;;
        --camera-width)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-width requires a value"
                print_usage
                exit 1
            fi
            CAMERA_WIDTH="$2"
            shift 2
            ;;
        --camera-height)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-height requires a value"
                print_usage
                exit 1
            fi
            CAMERA_HEIGHT="$2"
            shift 2
            ;;
        --infer-queue-size)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-queue-size requires a value"
                print_usage
                exit 1
            fi
            INFER_QUEUE_SIZE="$2"
            shift 2
            ;;
        --infer-workers)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-workers requires a value"
                print_usage
                exit 1
            fi
            INFER_WORKERS="$2"
            shift 2
            ;;
        --no-tracker)
            ENABLE_TRACKER=0
            shift
            ;;
        --no-target)
            ENABLE_TARGET_SELECTOR=0
            shift
            ;;
        --no-control)
            ENABLE_CONTROL=0
            shift
            ;;
        --control-mavros)
            CONTROL_MAVROS_BOOL="true"
            shift
            ;;
        --no-web-video)
            ENABLE_WEB_VIDEO=0
            shift
            ;;
        --rosbag)
            ENABLE_ROSBAG=1
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

case "$TRACKER_TYPE" in
    sort|ocsort|bytetrack)
        ;;
    *)
        echo "[error] invalid tracker '$TRACKER_TYPE' (expected sort|ocsort|bytetrack)"
        exit 1
        ;;
esac

if ! [[ "$TRACKER_PROFILE_LOG_EVERY_N" =~ ^[0-9]+$ ]]; then
    echo "[error] --tracker-profile-log-every must be a non-negative integer"
    exit 1
fi

if ! [[ "$TRACKER_PROFILE_SERIALIZE_EVERY_N" =~ ^[0-9]+$ ]]; then
    echo "[error] --tracker-profile-serialize-every must be a non-negative integer"
    exit 1
fi

if ! [[ "$INFER_QUEUE_SIZE" =~ ^[0-9]+$ ]] || [[ "$INFER_QUEUE_SIZE" -lt 1 ]]; then
    echo "[error] --infer-queue-size must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_WIDTH" =~ ^[0-9]+$ ]] || [[ "$CAMERA_WIDTH" -lt 1 ]]; then
    echo "[error] --camera-width must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_HEIGHT" =~ ^[0-9]+$ ]] || [[ "$CAMERA_HEIGHT" -lt 1 ]]; then
    echo "[error] --camera-height must be a positive integer"
    exit 1
fi

if ! [[ "$INFER_WORKERS" =~ ^[0-9]+$ ]] || [[ "$INFER_WORKERS" -lt 1 ]]; then
    echo "[error] --infer-workers must be a positive integer"
    exit 1
fi

wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout_s="$3"
    local required="${4:-0}"

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
            if [[ "$required" == "1" ]]; then
                echo "[error] timeout waiting for required port ${host}:${port}"
                return 1
            fi
            echo "[warn] timeout waiting for ${host}:${port}; continuing anyway"
            return 0
        fi
        sleep 1
    done
}

STACK_PROC_PATTERN="camera_bringup.launch.py|camera_capture_node|inference_client_node|tracker_node|target_selector_node|control_ref_node|dashboard_bridge_node|web_video_server"

check_stuck_camera_processes() {
    local stuck_lines
    stuck_lines="$(ps -eo pid=,stat=,cmd= | grep camera_capture_node | grep -v grep | awk '$2 ~ /^D/ {print}' || true)"

    if [[ -n "${stuck_lines:-}" ]]; then
        echo "[error] detected camera process(es) stuck in uninterruptible I/O state (D):"
        echo "$stuck_lines"
        echo "[error] this usually means the camera driver path is wedged; reboot is required"
        return 1
    fi

    return 0
}

cleanup_existing_stack_processes() {
    local existing
    existing="$(pgrep -af "$STACK_PROC_PATTERN" || true)"
    if [[ -z "${existing:-}" ]]; then
        return 0
    fi

    echo "[warn] found existing stack-related process(es); stopping before fresh start"
    echo "$existing"

    pkill -f "$STACK_PROC_PATTERN" >/dev/null 2>&1 || true
    sleep 1

    local remaining
    remaining="$(pgrep -af "$STACK_PROC_PATTERN" || true)"
    if [[ -n "${remaining:-}" ]]; then
        echo "[warn] some stack process(es) still running after stop attempt:"
        echo "$remaining"
        if ! check_stuck_camera_processes; then
            return 1
        fi
    fi

    return 0
}

echo "[info] logs: $RUN_DIR"
echo "[info] tracker: $TRACKER_TYPE"
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    echo "[info] dashboard bridge: enabled"
else
    echo "[info] dashboard bridge: disabled"
fi
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    echo "[info] tracker node: enabled"
    echo "[info] tracker publish_tracks: $TRACKER_PUBLISH_TRACKS_BOOL"
    if [[ "$TRACKER_PROFILE_ENABLED" -eq 1 ]]; then
        echo "[info] tracker profiling: enabled (log_every_n=$TRACKER_PROFILE_LOG_EVERY_N, serialize_every_n=$TRACKER_PROFILE_SERIALIZE_EVERY_N)"
    else
        echo "[info] tracker profiling: disabled"
    fi
else
    echo "[info] tracker node: disabled"
fi
echo "[info] inference publish_timing: $INFER_PUBLISH_TIMING_BOOL"
echo "[info] camera publish size: ${CAMERA_WIDTH}x${CAMERA_HEIGHT}"
echo "[info] inference queue_size: $INFER_QUEUE_SIZE"
echo "[info] inference workers: $INFER_WORKERS"
if [[ "$ENABLE_TARGET_SELECTOR" -eq 1 ]]; then
    echo "[info] target selector: enabled"
else
    echo "[info] target selector: disabled"
fi
if [[ "$ENABLE_CONTROL" -eq 1 ]]; then
    echo "[info] control node: enabled"
    if [[ "$CONTROL_MAVROS_BOOL" == "true" ]]; then
        echo "[info] control MAVROS mirror: enabled"
    else
        echo "[info] control MAVROS mirror: disabled (safe default)"
    fi
else
    echo "[info] control node: disabled"
fi
if [[ "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
    echo "[info] web video server: enabled"
else
    echo "[info] web video server: disabled"
fi
if [[ "$ENABLE_ROSBAG" -eq 1 ]]; then
    echo "[info] rosbag recording: enabled"
else
    echo "[info] rosbag recording: disabled"
fi
echo "[step] preflight checks"
if ! check_stuck_camera_processes; then
    exit 1
fi
if ! cleanup_existing_stack_processes; then
    exit 1
fi

echo "[step] sourcing ROS environment"
cd "$ROS_WS"
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID
echo "[info] ROS_DOMAIN_ID: $ROS_DOMAIN_ID"

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
export HAILO_DET_LABEL=person
export HAILO_REQREP_LOG_EVERY=${HAILO_REQREP_LOG_EVERY:-0}
nohup "$VENV/bin/python" /root/thesis_service/detection_zmq.py > /tmp/detection_zmq_live.log 2>&1 &
' >"$RUN_DIR/container_infer_start.log" 2>&1

if ! wait_for_port 127.0.0.1 5556 20 1; then
    stop_stack
    exit 1
fi

echo "[step] starting ROS nodes"
CAMERA_ARGS=()
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 0 ]]; then
    CAMERA_ARGS+=("publish_dashboard_topic:=false")
fi
CAMERA_ARGS+=("width:=$CAMERA_WIDTH")
CAMERA_ARGS+=("height:=$CAMERA_HEIGHT")

start_ros_bg camera ros2 launch thesis_bringup camera_bringup.launch.py "${CAMERA_ARGS[@]}"
sleep 2
if ! check_proc_alive camera; then
    stop_stack
    exit 1
fi

start_ros_bg inference ros2 run thesis_inference_client inference_client_node --ros-args \
    -p image_topic:=/camera/image_raw \
    -p addr:=tcp://127.0.0.1:5556 \
    -p queue_size:=$INFER_QUEUE_SIZE \
    -p num_workers:=$INFER_WORKERS \
    -p img_w:=640 \
    -p img_h:=640 \
    -p label:=person \
    -p min_score:=0.35 \
    -p publish_timing:=$INFER_PUBLISH_TIMING_BOOL
sleep 1
if ! check_proc_alive inference; then
    stop_stack
    exit 1
fi

if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    start_ros_bg tracker ros2 run thesis_tracker tracker_node --ros-args \
        -p tracker_type:=$TRACKER_TYPE \
        -p publish_tracks:=$TRACKER_PUBLISH_TRACKS_BOOL \
        -p profiling_enabled:=$([[ "$TRACKER_PROFILE_ENABLED" -eq 1 ]] && echo true || echo false) \
        -p profiling_log_every_n:=$TRACKER_PROFILE_LOG_EVERY_N \
        -p profiling_serialize_sample_every_n:=$TRACKER_PROFILE_SERIALIZE_EVERY_N \
        -p profiling_publish_details:=$([[ "$TRACKER_PROFILE_PUBLISH_DETAILS" -eq 1 ]] && echo true || echo false) \
        -p profiling_gc_probe:=$([[ "$TRACKER_PROFILE_GC_PROBE" -eq 1 ]] && echo true || echo false)
    sleep 1
    if ! check_proc_alive tracker; then
        stop_stack
        exit 1
    fi
fi

if [[ "$ENABLE_TARGET_SELECTOR" -eq 1 ]]; then
    start_ros_bg target_selector ros2 run thesis_target_selector target_selector_node
    sleep 1
    if ! check_proc_alive target_selector; then
        stop_stack
        exit 1
    fi
fi

if [[ "$ENABLE_CONTROL" -eq 1 ]]; then
    start_ros_bg control ros2 run thesis_bringup control_ref_node --ros-args \
        -p enable_mavros:=$CONTROL_MAVROS_BOOL \
        -p cmd_frame_id:=base_link \
        -p mavros_frame_id:=base_link
    sleep 1
    if ! check_proc_alive control; then
        stop_stack
        exit 1
    fi
fi

if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    start_ros_bg dashboard_bridge ros2 run thesis_bringup dashboard_bridge_node --ros-args \
        -p img_w:=640 \
        -p img_h:=640
    sleep 1
    if ! check_proc_alive dashboard_bridge; then
        stop_stack
        exit 1
    fi
    if ! wait_for_port 127.0.0.1 8765 15 1; then
        stop_stack
        exit 1
    fi
    if [[ "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
        start_ros_bg web_video ros2 run web_video_server web_video_server --ros-args -p port:=8080
        sleep 1
        if ! check_proc_alive web_video; then
            stop_stack
            exit 1
        fi
        if ! wait_for_port 127.0.0.1 8080 15 1; then
            stop_stack
            exit 1
        fi
    fi
fi

if [[ "$ENABLE_ROSBAG" -eq 1 ]]; then
    start_ros_bg rosbag ros2 bag record \
        /timing /timing_tracker /timing_target /detections /tracks /target /control_ref/cmd_vel \
        -o "$RUN_DIR/rosbag2"
    sleep 1
    if ! check_proc_alive rosbag; then
        stop_stack
        exit 1
    fi
fi

VIDEO_URL="http://${PI_IP}:8080/stream?topic=/camera/dashboard&type=mjpeg"
WS_URL="ws://${PI_IP}:8765"

echo "[done] live stack started"
echo "[info] PID file: $PID_FILE"
echo "[info] tail logs: tail -f $RUN_DIR/*.log"
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 && "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
    echo "[info] video: $VIDEO_URL"
fi
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    echo "[info] telemetry ws: $WS_URL"
else
    echo "[info] dashboard endpoints: disabled (--no-dashboard)"
fi
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
