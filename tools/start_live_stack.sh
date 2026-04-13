#!/usr/bin/env bash
set -euo pipefail

# start_live_stack.sh
#
# Purpose:
# - Start the live thesis stack in a deterministic order.
# - Keep host-side logs in one run folder.
# - Fail fast on missing dependencies or unhealthy camera/inference startup.
#
# Startup phases:
# 1) Preflight: clear stale processes and validate camera process health.
# 2) Environment: source ROS overlays and pin ROS_DOMAIN_ID.
# 3) Container: ensure inference container/service is running (legacy mode only).
# 4) ROS nodes: camera -> (legacy inference OR single-process perception) -> tracker/target/control -> dashboard/video.
# 5) Runtime shell: keep stack alive and allow `status|clear|stop` commands.
#
# Logging policy:
# - Script/service logs:   $ROS_WS/log/live_stack/<run-id>/
# - ROS runtime logs:      $ROS_WS/log/runtime/<run-id>/
#
# This prevents ROS logs from ending up in ~/.ros/log during live runs.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
PI_AI_DIR="${PI_AI_DIR:-$HOME/pi-ai-kit-ubuntu}"
CONTAINER_NAME="${CONTAINER_NAME:-pi-ai-kit-ubuntu-hailo-ubuntu-pi-1}"
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

if [[ -z "${PI_IP// }" ]]; then
    PI_IP="127.0.0.1"
fi

LOG_ROOT="$ROS_WS/log/live_stack"
RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
RUN_DIR="$LOG_ROOT/$RUN_ID"
PID_FILE="$RUN_DIR/pids.txt"
LATEST_LINK="$LOG_ROOT/latest"
ROS_RUNTIME_LOG_ROOT="$ROS_WS/log/runtime"
ROS_LOG_DIR="$ROS_RUNTIME_LOG_ROOT/$RUN_ID"

declare -A PROC_PIDS

mkdir -p "$RUN_DIR"
mkdir -p "$ROS_LOG_DIR"
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

camera_log_has_fatal_error() {
    local log_file="$RUN_DIR/camera.log"

    if [[ ! -f "$log_file" ]]; then
        return 1
    fi

    if rg -q "process has died|Traceback \(most recent call last\)|RuntimeError:" "$log_file"; then
        echo "[error] camera log reports fatal startup error"
        tail -n 40 "$log_file" || true
        return 0
    fi

    return 1
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
    pkill -f "perception_pipeline_node" >/dev/null 2>&1 || true
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

Starts the live camera + inference + optional tracking/control/dashboard stack.
All ROS runtime logs are forced under ros2_ws/log/runtime for this run.

Options:
    --perception-mode <legacy|single-process>
                                                                            Perception path selection (default: legacy)
    --tracker <sort|ocsort|bytetrack>  Tracker backend (default: sort)
    --tracker-profile-off               Disable tracker profiling instrumentation
    --tracker-profile-log-every <N>     Log tracker profile every N frames (default: 30)
    --tracker-profile-serialize-every <N>
                                                                            Serialize sample every N frames (default: 0 disabled)
    --tracks-off                        Disable /tracks publishing from tracker
    --timing-off                        Disable /timing publishing from inference client
    --camera-width <N>                  Camera publish width (default: 1280)
    --camera-height <N>                 Camera publish height (default: 720)
    --camera-fps <N>                    Camera publish fps (default: 30)
    --dashboard-fps <N>                 Dashboard image publish fps (default: 30)
    --camera-no-flip                    Disable camera frame flip
    --infer-queue-size <N>              Inference client queue size (default: 1)
    --infer-workers <N>                 Inference client worker threads (default: 2)
    --infer-timeout-ms <N>              Inference request timeout ms (default: 300)
    --infer-retries <N>                 Inference retries after timeout/error (default: 0)
    --infer-print-every <N>             Inference periodic stats interval (default: 240)
    --infer-timeout-log-every <N>       Inference timeout log interval (default: 20)
  --no-dashboard                     Disable dashboard bridge
    --no-tracker                       Do not start tracker node
    --no-target                        Do not start target selector node
    --no-control                       Do not start control_ref_node
    --control-mavros                   Enable MAVROS mirroring in control_ref_node
    --control-stale-timeout-s <N>      Control stale target timeout seconds (default: 0.80)
    --no-web-video                     Do not start web_video_server
    --rosbag                           Record timing/tracking/control topics to rosbag
  -h, --help                         Show this help message
EOF
}

TRACKER_TYPE="sort"
PERCEPTION_MODE="legacy"
TRACKER_PROFILE_ENABLED=0
TRACKER_PROFILE_LOG_EVERY_N=30
TRACKER_PROFILE_SERIALIZE_EVERY_N=0
TRACKER_PROFILE_PUBLISH_DETAILS=1
TRACKER_PROFILE_GC_PROBE=1
TRACKER_PUBLISH_TRACKS_BOOL="true"
INFER_PUBLISH_TIMING_BOOL="true"
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
CAMERA_FPS=30.0
CAMERA_DASHBOARD_FPS=30.0
CAMERA_FLIP_BOOL="true"
INFER_QUEUE_SIZE=1
INFER_WORKERS=2
INFER_TIMEOUT_MS=300
INFER_RETRIES=0
INFER_PRINT_EVERY=240
INFER_TIMEOUT_LOG_EVERY=20
ENABLE_DASHBOARD_BRIDGE=1
ENABLE_TRACKER=1
ENABLE_TARGET_SELECTOR=1
ENABLE_CONTROL=1
CONTROL_MAVROS_BOOL="false"
CONTROL_STALE_TIMEOUT_S=0.80
ENABLE_WEB_VIDEO=1
ENABLE_ROSBAG=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --perception-mode)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-mode requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_MODE="${2,,}"
            shift 2
            ;;
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
        --camera-fps)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-fps requires a value"
                print_usage
                exit 1
            fi
            CAMERA_FPS="$2"
            shift 2
            ;;
        --dashboard-fps)
            if [[ $# -lt 2 ]]; then
                echo "[error] --dashboard-fps requires a value"
                print_usage
                exit 1
            fi
            CAMERA_DASHBOARD_FPS="$2"
            shift 2
            ;;
        --camera-no-flip)
            CAMERA_FLIP_BOOL="false"
            shift
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
        --infer-timeout-ms)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-timeout-ms requires a value"
                print_usage
                exit 1
            fi
            INFER_TIMEOUT_MS="$2"
            shift 2
            ;;
        --infer-retries)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-retries requires a value"
                print_usage
                exit 1
            fi
            INFER_RETRIES="$2"
            shift 2
            ;;
        --infer-print-every)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-print-every requires a value"
                print_usage
                exit 1
            fi
            INFER_PRINT_EVERY="$2"
            shift 2
            ;;
        --infer-timeout-log-every)
            if [[ $# -lt 2 ]]; then
                echo "[error] --infer-timeout-log-every requires a value"
                print_usage
                exit 1
            fi
            INFER_TIMEOUT_LOG_EVERY="$2"
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
        --control-stale-timeout-s)
            if [[ $# -lt 2 ]]; then
                echo "[error] --control-stale-timeout-s requires a value"
                print_usage
                exit 1
            fi
            CONTROL_STALE_TIMEOUT_S="$2"
            shift 2
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

case "$PERCEPTION_MODE" in
    legacy|single-process)
        ;;
    *)
        echo "[error] invalid --perception-mode '$PERCEPTION_MODE' (expected legacy|single-process)"
        exit 1
        ;;
esac

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

if ! [[ "$CAMERA_DASHBOARD_FPS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "[error] --dashboard-fps must be a positive number"
    exit 1
fi

if ! [[ "$INFER_WORKERS" =~ ^[0-9]+$ ]] || [[ "$INFER_WORKERS" -lt 1 ]]; then
    echo "[error] --infer-workers must be a positive integer"
    exit 1
fi

if ! [[ "$INFER_TIMEOUT_MS" =~ ^[0-9]+$ ]] || [[ "$INFER_TIMEOUT_MS" -lt 1 ]]; then
    echo "[error] --infer-timeout-ms must be a positive integer"
    exit 1
fi

if ! [[ "$INFER_RETRIES" =~ ^[0-9]+$ ]]; then
    echo "[error] --infer-retries must be a non-negative integer"
    exit 1
fi

if ! [[ "$INFER_PRINT_EVERY" =~ ^[0-9]+$ ]]; then
    echo "[error] --infer-print-every must be a non-negative integer"
    exit 1
fi

if ! [[ "$INFER_TIMEOUT_LOG_EVERY" =~ ^[0-9]+$ ]]; then
    echo "[error] --infer-timeout-log-every must be a non-negative integer"
    exit 1
fi

if ! [[ "$CONTROL_STALE_TIMEOUT_S" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "[error] --control-stale-timeout-s must be a positive number"
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

wait_for_topic_message() {
    local topic="$1"
    local timeout_s="$2"
    local required="${3:-0}"
    local qos_profile="${4:-}"
    local qos_reliability="${5:-}"
    local qos_durability="${6:-}"

    local -a echo_cmd=(ros2 topic echo "$topic" --once)
    if [[ -n "$qos_profile" ]]; then
        echo_cmd+=(--qos-profile "$qos_profile")
    fi
    if [[ -n "$qos_reliability" ]]; then
        echo_cmd+=(--qos-reliability "$qos_reliability")
    fi
    if [[ -n "$qos_durability" ]]; then
        echo_cmd+=(--qos-durability "$qos_durability")
    fi

    if timeout "${timeout_s}s" "${echo_cmd[@]}" >/dev/null 2>&1; then
        echo "[ok] topic ${topic} produced a message"
        return 0
    fi

    if [[ "$required" == "1" ]]; then
        echo "[error] timeout waiting for required topic message on ${topic}"
        return 1
    fi

    echo "[warn] timeout waiting for topic message on ${topic}; continuing anyway"
    return 0
}

STACK_PROC_PATTERN="camera_bringup.launch.py|camera_capture_node|inference_client_node|perception_pipeline_node|tracker_node|target_selector_node|control_ref_node|dashboard_bridge_node|web_video_server"
CAMERA_MEDIA_DEV_OVERRIDE=""

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

detect_camera_media_device() {
    local media_dev
    local topology

    CAMERA_MEDIA_DEV_OVERRIDE=""

    for media_dev in /dev/media*; do
        [[ -e "$media_dev" ]] || continue
        topology="$(media-ctl -d "$media_dev" -p 2>/dev/null || true)"
        [[ -n "${topology:-}" ]] || continue

        if grep -qi "driver[[:space:]]*rp1-cfe" <<<"$topology" && grep -qiE "tevs|11-0048|rp1-cfe-csi2_ch[0-9]" <<<"$topology"; then
            CAMERA_MEDIA_DEV_OVERRIDE="$media_dev"
            echo "[info] auto-detected camera media graph on $CAMERA_MEDIA_DEV_OVERRIDE"
            return 0
        fi
    done

    echo "[warn] no media device currently exposes TEVS camera entities"
    echo "[hint] runtime auto-select can only choose among detected camera media graphs"
    echo "[hint] cam0/cam1 selection comes from boot overlay and requires reboot to change"

    local klog
    klog="$(journalctl -k -b --no-pager 2>/dev/null | tail -n 500 || true)"
    if [[ -n "${klog:-}" ]] && grep -qiE "pca953x.*failed writing register|probe.*error -121" <<<"$klog"; then
        echo "[hint] kernel reports camera control I2C probe failure (pca953x/-121)"
        echo "[hint] verify camera port (cam0/cam1) and overlay in /boot/firmware/config.txt"
    fi

    return 1
}

tracker_state="off"
target_state="off"
control_state="off"
dashboard_state="off"
web_video_state="off"
rosbag_state="off"

if [[ "$ENABLE_TRACKER" -eq 1 ]]; then tracker_state="on"; fi
if [[ "$ENABLE_TARGET_SELECTOR" -eq 1 ]]; then target_state="on"; fi
if [[ "$ENABLE_CONTROL" -eq 1 ]]; then
    if [[ "$CONTROL_MAVROS_BOOL" == "true" ]]; then
        control_state="on+mavros"
    else
        control_state="on"
    fi
fi
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then dashboard_state="on"; fi
if [[ "$ENABLE_WEB_VIDEO" -eq 1 ]]; then web_video_state="on"; fi
if [[ "$ENABLE_ROSBAG" -eq 1 ]]; then rosbag_state="on"; fi

echo "[info] run: $RUN_ID"
echo "[info] logs: $RUN_DIR"
echo "[info] mode: perception=$PERCEPTION_MODE"
echo "[info] cfg: camera=${CAMERA_WIDTH}x${CAMERA_HEIGHT}@${CAMERA_FPS} infer=q${INFER_QUEUE_SIZE}/w${INFER_WORKERS}/t${INFER_TIMEOUT_MS}ms/r${INFER_RETRIES} control_stale=${CONTROL_STALE_TIMEOUT_S}s"
echo "[info] nodes: tracker=$tracker_state target=$target_state control=$control_state dashboard=$dashboard_state web_video=$web_video_state rosbag=$rosbag_state"
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    echo "[info] tracker: type=$TRACKER_TYPE tracks=$TRACKER_PUBLISH_TRACKS_BOOL profile=$TRACKER_PROFILE_ENABLED"
fi
echo "[step] preflight checks"
if ! check_stuck_camera_processes; then
    exit 1
fi
if ! cleanup_existing_stack_processes; then
    exit 1
fi
detect_camera_media_device || true

echo "[step] sourcing ROS environment"
cd "$ROS_WS"
export ROS_LOG_DIR
set +u
source /opt/ros/jazzy/setup.bash
if [[ -f "install/setup.bash" ]]; then
    source install/setup.bash
else
    echo "[error] missing workspace setup: $ROS_WS/install/setup.bash"
    echo "[hint] build the ROS workspace first:"
    echo "       cd $ROS_WS"
    echo "       source /opt/ros/jazzy/setup.bash"
    echo "       colcon build --symlink-install"
    echo "       source install/setup.bash"
    exit 1
fi
set -u
export ROS_DOMAIN_ID
echo "[info] ros: domain=$ROS_DOMAIN_ID log_dir=$ROS_LOG_DIR"

if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
    echo "[step] ensuring container is up"
    (
        cd "$PI_AI_DIR"
        docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
    ) >"$RUN_DIR/container_up.log" 2>&1

    # If the bind mount is stale (e.g. host dir recreated), detection script can disappear
    # inside an otherwise running container. Recreate once to refresh mounts.
    if ! docker exec "$CONTAINER_NAME" test -f /root/thesis_service/detection_zmq.py >/dev/null 2>&1; then
        echo "[warn] detection service script missing in container mount; recreating container"
        (
            cd "$PI_AI_DIR"
            docker compose -f docker-compose.yaml up -d --force-recreate hailo-ubuntu-pi
        ) >>"$RUN_DIR/container_up.log" 2>&1

        if ! docker exec "$CONTAINER_NAME" test -f /root/thesis_service/detection_zmq.py >/dev/null 2>&1; then
            echo "[error] container mount is still missing /root/thesis_service/detection_zmq.py"
            echo "[error] check docker-compose bind mount for thesis_service and host path contents"
            stop_stack
            exit 1
        fi
    fi

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
else
    echo "[step] single-process perception mode selected"
    echo "[info] single-process mode will run in-process perception_pipeline_node"
    echo "[warn] if host Hailo runtime is unavailable, node will fallback to stub backend"
    echo "[info] skipping container detection_zmq startup in single-process mode"
fi

echo "[step] starting ROS nodes"
CAMERA_ARGS=()
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 0 ]]; then
    CAMERA_ARGS+=("publish_dashboard_topic:=false")
fi

# rclpy expects camera fps launch parameter as DOUBLE; normalize integer input to float.
if [[ "$CAMERA_FPS" =~ ^[0-9]+$ ]]; then
    CAMERA_FPS="${CAMERA_FPS}.0"
fi

# rclpy expects dashboard_fps launch parameter as DOUBLE; normalize integer input to float.
if [[ "$CAMERA_DASHBOARD_FPS" =~ ^[0-9]+$ ]]; then
    CAMERA_DASHBOARD_FPS="${CAMERA_DASHBOARD_FPS}.0"
fi

CAMERA_ARGS+=("width:=$CAMERA_WIDTH")
CAMERA_ARGS+=("height:=$CAMERA_HEIGHT")
CAMERA_ARGS+=("fps:=$CAMERA_FPS")
CAMERA_ARGS+=("dashboard_fps:=$CAMERA_DASHBOARD_FPS")
CAMERA_ARGS+=("flip_image:=$CAMERA_FLIP_BOOL")
if [[ -n "${CAMERA_MEDIA_DEV_OVERRIDE:-}" ]]; then
    CAMERA_ARGS+=("media_dev:=$CAMERA_MEDIA_DEV_OVERRIDE")
fi

start_ros_bg camera ros2 launch thesis_bringup camera_bringup.launch.py "${CAMERA_ARGS[@]}"
sleep 2
if ! check_proc_alive camera; then
    stop_stack
    exit 1
fi
if ! wait_for_topic_message /camera/image_raw 12 1 sensor_data best_effort volatile; then
    if ! check_proc_alive camera; then
        echo "[error] camera process exited during startup; see $RUN_DIR/camera.log"
        stop_stack
        exit 1
    fi
    if camera_log_has_fatal_error; then
        echo "[error] camera startup failed; see $RUN_DIR/camera.log"
        stop_stack
        exit 1
    fi
    echo "[error] camera node is running but not publishing frames"
    echo "[hint] check camera cable/sensor state and try restarting stack"
    echo "[hint] if issue persists, reboot host to reset camera pipeline"
    echo "[hint] if media topology lacks sensor entities, verify /boot/firmware/config.txt overlay port (cam0 vs cam1)"
    stop_stack
    exit 1
fi

if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
    start_ros_bg inference ros2 run thesis_inference_client inference_client_node --ros-args \
        -p image_topic:=/camera/image_raw \
        -p addr:=tcp://127.0.0.1:5556 \
        -p queue_size:=$INFER_QUEUE_SIZE \
        -p num_workers:=$INFER_WORKERS \
        -p request_timeout_ms:=$INFER_TIMEOUT_MS \
        -p request_retries:=$INFER_RETRIES \
        -p print_every:=$INFER_PRINT_EVERY \
        -p timeout_log_every:=$INFER_TIMEOUT_LOG_EVERY \
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
else
    # Keep ROS runtime on host Python, but expose required packages for single-process mode:
    # - system dist-packages for gi/Gst
    # - project .venv site-packages for hailort/tappas Python bindings
    PERCEPTION_PYTHONPATH="/usr/lib/python3/dist-packages"
    PERCEPTION_VENV_SITE_PACKAGES=""
    if [[ -d "$THESIS_ROOT/.venv/lib" ]]; then
        PERCEPTION_VENV_SITE_PACKAGES="$(find "$THESIS_ROOT/.venv/lib" -maxdepth 2 -type d -name site-packages | head -n 1 || true)"
        if [[ -n "${PERCEPTION_VENV_SITE_PACKAGES:-}" ]]; then
            PERCEPTION_PYTHONPATH="${PERCEPTION_VENV_SITE_PACKAGES}:$PERCEPTION_PYTHONPATH"
        fi
    fi
    if [[ -n "${PYTHONPATH:-}" ]]; then
        PERCEPTION_PYTHONPATH="${PERCEPTION_PYTHONPATH}:$PYTHONPATH"
    fi

    # Optional local TAPPAS runtime shim (no root install required).
    # Expected layout defaults to tools/setup_local_tappas_runtime.sh output.
    PERCEPTION_RUNTIME_DIR="${PERCEPTION_RUNTIME_DIR:-$THESIS_ROOT/infer_service/opt/tappas_runtime_3_31}"
    PERCEPTION_RUNTIME_LIB_DIR="${PERCEPTION_RUNTIME_LIB_DIR:-$PERCEPTION_RUNTIME_DIR/usr/lib/aarch64-linux-gnu}"
    PERCEPTION_RUNTIME_GST_DIR="${PERCEPTION_RUNTIME_GST_DIR:-$PERCEPTION_RUNTIME_LIB_DIR/gstreamer-1.0}"
    PERCEPTION_RUNTIME_POST_SO="${PERCEPTION_RUNTIME_POST_SO:-$PERCEPTION_RUNTIME_LIB_DIR/hailo/tappas/post_processes/libyolo_hailortpp_post.so}"

    PERCEPTION_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
    PERCEPTION_GST_PLUGIN_PATH="${GST_PLUGIN_PATH:-}"

    if [[ -d "$PERCEPTION_RUNTIME_LIB_DIR" ]]; then
        if [[ -n "$PERCEPTION_LD_LIBRARY_PATH" ]]; then
            PERCEPTION_LD_LIBRARY_PATH="${PERCEPTION_RUNTIME_LIB_DIR}:$PERCEPTION_LD_LIBRARY_PATH"
        else
            PERCEPTION_LD_LIBRARY_PATH="$PERCEPTION_RUNTIME_LIB_DIR"
        fi
    fi

    if [[ -d "$PERCEPTION_RUNTIME_GST_DIR" ]]; then
        if [[ -n "$PERCEPTION_GST_PLUGIN_PATH" ]]; then
            PERCEPTION_GST_PLUGIN_PATH="${PERCEPTION_RUNTIME_GST_DIR}:$PERCEPTION_GST_PLUGIN_PATH"
        else
            PERCEPTION_GST_PLUGIN_PATH="$PERCEPTION_RUNTIME_GST_DIR"
        fi
    fi

    PERCEPTION_POST_SO_ARGS=()
    if [[ -f "$PERCEPTION_RUNTIME_POST_SO" ]]; then
        PERCEPTION_POST_SO_ARGS=(-p "hailo_post_so:=$PERCEPTION_RUNTIME_POST_SO")
        echo "[info] single-process: using local postprocess lib at $PERCEPTION_RUNTIME_POST_SO"
    fi

    start_ros_bg perception_pipeline env PYTHONPATH="$PERCEPTION_PYTHONPATH" LD_LIBRARY_PATH="$PERCEPTION_LD_LIBRARY_PATH" GST_PLUGIN_PATH="$PERCEPTION_GST_PLUGIN_PATH" ros2 run thesis_bringup perception_pipeline_node --ros-args \
        -p image_topic:=/camera/image_raw \
        -p img_w:=640 \
        -p img_h:=640 \
        -p label:=person \
        -p min_score:=0.35 \
        -p inference_backend:=hailo_gst \
        "${PERCEPTION_POST_SO_ARGS[@]}" \
        -p infer_timeout_ms:=$INFER_TIMEOUT_MS \
        -p timeout_log_every:=$INFER_TIMEOUT_LOG_EVERY \
        -p publish_timing:=$INFER_PUBLISH_TIMING_BOOL \
        -p log_every:=$INFER_PRINT_EVERY
    sleep 1
    if ! check_proc_alive perception_pipeline; then
        stop_stack
        exit 1
    fi
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
        -p mavros_frame_id:=base_link \
        -p stale_timeout_s:=$CONTROL_STALE_TIMEOUT_S
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

VIDEO_URL="http://${PI_IP}:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45"
WS_URL="ws://${PI_IP}:8765"

echo "[done] live stack ready"
echo "[info] logs: $RUN_DIR"
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 && "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
    echo "[info] dashboard: video=$VIDEO_URL ws=$WS_URL"
fi
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    if [[ "$ENABLE_WEB_VIDEO" -eq 0 ]]; then
        echo "[info] dashboard: ws=$WS_URL"
    fi
else
    echo "[info] dashboard: disabled"
fi
echo "[info] commands: status | clear | stop"

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
