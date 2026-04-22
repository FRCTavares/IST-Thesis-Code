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
# 4) ROS nodes: camera -> (legacy inference OR single-process perception) -> tracker/control/dashboard -> video.
# 5) Runtime shell: keep stack alive and allow `status|clear|stop` commands.
#
# Logging policy:
# - Script/service logs:   $ROS_WS/log/live_stack/<run-id>/
# - ROS runtime logs:      $ROS_WS/log/runtime/<run-id>/
#
# This prevents ROS logs from ending up in ~/.ros/log during live runs.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
# Legacy compose runtime is now stored under deprecated/. Keep HOME fallback for older hosts.
PI_AI_DIR_DEFAULT="$THESIS_ROOT/deprecated/pi-ai-kit-ubuntu"
if [[ -d "$PI_AI_DIR_DEFAULT" ]]; then
    PI_AI_DIR="${PI_AI_DIR:-$PI_AI_DIR_DEFAULT}"
else
    PI_AI_DIR="${PI_AI_DIR:-$HOME/pi-ai-kit-ubuntu}"
fi
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

VERBOSE="${LIVE_STACK_VERBOSE:-0}"
if [[ "$VERBOSE" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
    VERBOSE=1
else
    VERBOSE=0
fi

# Verbose logs are intentionally opt-in to keep live startup output signal-dense.
log_verbose_tag() {
    local tag="$1"
    shift
    if [[ "$VERBOSE" -eq 1 ]]; then
        echo "[$tag] $*"
    fi
}

log_info() { log_verbose_tag info "$@"; }
log_step() { log_verbose_tag step "$@"; }
log_ok() { log_verbose_tag ok "$@"; }
log_start() { log_verbose_tag start "$@"; }
log_stop() { log_verbose_tag stop "$@"; }
log_done() { log_verbose_tag done "$@"; }
log_hint() { log_verbose_tag hint "$@"; }

# Start a ROS process in the background, track pid, and redirect logs to this run directory.
start_ros_bg() {
    local name="$1"
    shift
    "$@" >"$RUN_DIR/${name}.log" 2>&1 &
    local pid=$!
    PROC_PIDS["$name"]="$pid"
    echo "$pid $name" >>"$PID_FILE"
    log_start "$name (pid=$pid)"
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

    log_ok "$name (pid=$pid)"
}

print_startup_success_summary() {
    local infer_w infer_h capture_size publish_size infer_size detector_summary tracker_summary

    infer_w="${HAILO_INFER_WIDTH:-640}"
    infer_h="${HAILO_INFER_HEIGHT:-640}"
    capture_size="${CAMERA_WIDTH}x${CAMERA_HEIGHT}"
    publish_size="${CAMERA_PUBLISH_WIDTH}x${CAMERA_PUBLISH_HEIGHT}"
    infer_size="${infer_w}x${infer_h}"

    if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
        detector_summary="mode=legacy queue=${INFER_QUEUE_SIZE} workers=${INFER_WORKERS} timeout_ms=${INFER_TIMEOUT_MS} retries=${INFER_RETRIES}"
    else
        detector_summary="mode=single-process backend=${PERCEPTION_INFERENCE_BACKEND} frame_queue=${INFER_QUEUE_SIZE} workers=${INFER_WORKERS} image_qos_depth=${PERCEPTION_IMAGE_QOS_DEPTH} hailo_queue_buffers=${PERCEPTION_HAILO_QUEUE_BUFFERS} async_max_inflight=${PERCEPTION_ASYNC_MAX_INFLIGHT}"
    fi

    if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
        tracker_summary="enabled type=${TRACKER_TYPE} iou=${TRACKER_IOU_THRESHOLD} max_age=${TRACKER_MAX_AGE} min_hits=${TRACKER_MIN_HITS} centre_gate=${TRACKER_CENTRE_GATE}"
    else
        tracker_summary="disabled"
    fi

    echo "[ok] startup summary: capture=${capture_size} publish=${publish_size} hailo_infer=${infer_size}"
    echo "[ok] detector: ${detector_summary}"
    echo "[ok] tracker: ${tracker_summary}"
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

camera_log_has_frame_activity() {
    local log_file="$RUN_DIR/camera.log"

    if [[ ! -f "$log_file" ]]; then
        return 1
    fi

    # Only accept periodic FPS logs as evidence of real frame flow.
    # The startup banner alone is not sufficient and can produce false positives.
    rg -q "Camera FPS capture=" "$log_file"
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

    log_step "stopping live stack"

    if [[ -f "$PID_FILE" ]]; then
        tac "$PID_FILE" | while read -r pid name; do
            if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
                kill_tree "$pid" INT
                log_stop "$name (pid=$pid)"
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
    pkill -f "inference_client_node|detector_node" >/dev/null 2>&1 || true
    pkill -f "perception_pipeline_node" >/dev/null 2>&1 || true
    pkill -f "tracker_node" >/dev/null 2>&1 || true
    pkill -f "control_ref_node" >/dev/null 2>&1 || true
    pkill -f "dashboard_bridge_node" >/dev/null 2>&1 || true
    pkill -f "web_video_server" >/dev/null 2>&1 || true

    docker exec "$CONTAINER_NAME" bash -lc 'pkill -f detection_zmq.py >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
    log_done "live stack stop requested"
}

trap 'stop_stack; exit 0' INT TERM

print_resolution_presets() {
    cat <<'EOF'
Available resolution presets:
    vga      640x480
    hd       1280x720
    fhd      1920x1080

Custom format:
    WIDTHxHEIGHT (example: 1024x576)
EOF
}

print_advanced_usage() {
    cat <<'EOF'
Usage: start_live_stack.sh [options]

Starts the live camera + inference + optional tracking/control/dashboard stack.
All ROS runtime logs are forced under ros2_ws/log/runtime for this run.

Options:
    --perception-mode <legacy|single-process>
                                                                            Perception path selection (default: single-process)
    -v, --verbose                     Enable verbose startup/status logs (default: warnings/errors only)
    --tracker <sort|ocsort|bytetrack|deepsort>  Tracker backend (default: sort)
    --tracker-profile-off               Disable tracker profiling instrumentation
    --tracker-gc-probe-off              Disable tracker GC probe instrumentation (lower overhead)
    --tracker-gc-probe-on               Enable tracker GC probe instrumentation
    --tracker-profile-log-every <N>     Log tracker profile every N frames (default: 30)
    --tracker-profile-serialize-every <N>
                                                                            Serialize sample every N frames (default: 0 disabled)
    --tracker-iou-threshold <F>         SORT/OCSORT IoU threshold (default: 0.18)
    --tracker-max-age <N>               SORT/OCSORT max track age (default: 4)
    --tracker-min-hits <N>              SORT/OCSORT min hits before confirm (default: 3)
    --tracker-centre-gate <F>           SORT/OCSORT centre gating pixels (default: 200)
    --tracks-off                        Disable /tracks publishing from tracker
    --tracks-require-subscribers        Publish /tracks only when subscribers are present (default)
    --tracks-ignore-subscribers         Publish /tracks regardless of subscriber count
    --tracker-timing-off                Disable /timing_tracker publishing (default)
    --tracker-timing-on                 Enable /timing_tracker publishing
    --timing-off                        Disable /timing publishing from inference client
    --resolution <preset|WIDTHxHEIGHT>  Quick camera capture resolution selector
    --list-resolutions                  Print resolution presets and exit
    --camera-width <N>                  Camera capture width (default: 1280)
    --camera-height <N>                 Camera capture height (default: 720)
    --camera-publish-width <N>          /camera/image_raw width (default: camera-width)
    --camera-publish-height <N>         /camera/image_raw height (default: camera-height)
    --camera-publish-resize-mode <resize|letterbox>
                                                                            /camera/image_raw reshape mode (default: letterbox)
    --camera-publish-encoding <bgr8|rgb8>
                                                                            /camera/image_raw encoding (default: bgr8)
    --camera-fps <N>                    Camera publish fps (default: 30)
    --dashboard-fps <N>                 Dashboard image publish fps (default: 30)
    --camera-no-flip                    Disable camera frame flip
    --camera-rate-controls-off          Disable sensor FPS/exposure rate control writes
    --camera-rate-controls-on           Enable sensor FPS/exposure rate control writes
    --camera-sensor-max-fps <N>         Sensor max_fps control (default: 30)
    --camera-ae-upper <N>               Sensor ae_exposure_upper control (default: 8333)
    --camera-ae-max <N>                 Sensor ae_exposure_max control (default: 33333)
    --camera-exposure-mode <0|1|2>      Sensor exposure mode (0=manual, 1=auto, 2=agc; default: 1)
    --camera-manual-exposure <N>        Sensor manual exposure when mode=0 (default: 8333)
    --infer-queue-size <N>              Inference queue size (legacy client + single-process ingress, default: 1)
    --infer-workers <N>                 Legacy client workers / single-process preprocess workers (default: 2)
    --infer-timeout-ms <N>              Inference request timeout ms (default: 300)
    --infer-retries <N>                 Inference retries after timeout/error (default: 0)
    --infer-print-every <N>             Inference periodic stats interval (default: 240)
    --infer-timeout-log-every <N>       Inference timeout log interval (default: 20)
    --perception-image-qos-depth <N>    Perception image subscription depth (single-process default: 2)
    --perception-hailo-queue-buffers <N>
                                                                            Hailo Gst queue max-size-buffers (single-process default: 6)
    --perception-inference-backend <name>
                                                                            Inference backend (single-process default: hailo_direct)
    --perception-async-max-inflight <N>  Experimental request for in-flight calls (single-process owner path enforces 1)
    --perception-hailo-videoconvert-off  Disable pre-hailonet videoconvert stage (single-process)
    --perception-hailo-videoconvert-on   Enable pre-hailonet videoconvert stage (single-process default)
    --perception-gc-off                 Disable Python cyclic GC in perception node
    --perception-gc-on                  Enable Python cyclic GC in perception node (default)
    --perception-no-stub-fallback       Fail fast if Hailo backend initialization fails (default)
    --perception-allow-stub-fallback    Allow stub fallback when Hailo backend initialization fails
  --no-dashboard                     Disable dashboard bridge
    --no-tracker                       Do not start tracker node
    --no-target                        Deprecated alias; target selection is now handled by dashboard bridge API
    --no-control                       Do not start control_ref_node
    --control-mavros                   Enable MAVROS mirroring in control_ref_node
    --control-stale-timeout-s <N>      Control stale target timeout seconds (default: 0.80)
    --no-web-video                     Do not start web_video_server
    --rosbag                           Record timing/tracking/control topics to rosbag
  -h, --help                         Show this help message
EOF
}

print_usage() {
    cat <<'EOF'
Usage: start_live_stack.sh [options]

Day-to-day options:
    --profile <daily|safe-camera|performance>
                                      Startup preset (default: daily)
    --perception-mode <legacy|single-process>
                                      Perception path selection (default: single-process)
    --resolution <preset|WIDTHxHEIGHT>
                                      Quick camera capture resolution selector
    --list-resolutions                 Print available resolution presets and exit
    --camera-width <N>                Camera capture width (default: profile value)
    --camera-height <N>               Camera capture height (default: profile value)
    --camera-rate-controls-off        Disable sensor FPS/exposure control writes
    --perception-inference-backend <name>
                                      Perception backend (default: hailo_direct)
    --no-tracker                      Do not start tracker node
    --no-target                       Deprecated alias; target selection is now handled by dashboard bridge API
    --no-control                      Do not start control_ref_node
    --no-dashboard                    Disable dashboard bridge
    --no-web-video                    Do not start web_video_server
    --rosbag                          Record timing/tracking/control topics
    -v, --verbose                     Enable verbose startup/status logs
    -h, --help                        Show this concise help
    --help-advanced                   Show full advanced argument list

Notes:
    - Script now runs a preflight camera stream probe with auto relink/format sync.
    - If preflight cannot stream, startup aborts early with actionable guidance.
    - Available resolution presets:
      vga=640x480, hd=1280x720, fhd=1920x1080
EOF
}

TRACKER_TYPE="sort"
PERCEPTION_MODE="single-process"
STARTUP_PROFILE="daily"
TRACKER_PROFILE_ENABLED=0
TRACKER_PROFILE_LOG_EVERY_N=30
TRACKER_PROFILE_SERIALIZE_EVERY_N=0
TRACKER_PROFILE_PUBLISH_DETAILS=1
TRACKER_PROFILE_GC_PROBE=0
TRACKER_IOU_THRESHOLD=0.18
TRACKER_MAX_AGE=4
TRACKER_MIN_HITS=3
TRACKER_CENTRE_GATE=200.0
TRACKER_PUBLISH_TRACKS_BOOL="true"
TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL="true"
TRACKER_PUBLISH_TIMING_BOOL="false"
INFER_PUBLISH_TIMING_BOOL="true"
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
CAMERA_PUBLISH_WIDTH=0
CAMERA_PUBLISH_HEIGHT=0
CAMERA_PUBLISH_RESIZE_MODE="letterbox"
CAMERA_PUBLISH_ENCODING="bgr8"
CAMERA_PUBLISH_SHAPE_EXPLICIT=0
CAMERA_FPS=30.0
CAMERA_DASHBOARD_FPS=30.0
CAMERA_FLIP_BOOL="true"
CAMERA_APPLY_RATE_CONTROLS_BOOL="true"
CAMERA_SENSOR_MAX_FPS=30
CAMERA_SENSOR_AE_UPPER=8333
CAMERA_SENSOR_AE_MAX=33333
CAMERA_SENSOR_EXPOSURE_MODE=1
CAMERA_SENSOR_MANUAL_EXPOSURE=8333
INFER_QUEUE_SIZE=1
INFER_WORKERS=2
INFER_TIMEOUT_MS=300
INFER_RETRIES=0
INFER_PRINT_EVERY=240
INFER_TIMEOUT_LOG_EVERY=20
PERCEPTION_IMAGE_QOS_DEPTH=2
PERCEPTION_HAILO_QUEUE_BUFFERS=6
PERCEPTION_ASYNC_MAX_INFLIGHT=1
PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL="true"
PERCEPTION_GC_DISABLE_BOOL="false"
PERCEPTION_ALLOW_STUB_FALLBACK_BOOL="false"
PERCEPTION_INFERENCE_BACKEND="hailo_direct"
ENABLE_DASHBOARD_BRIDGE=1
ENABLE_TRACKER=1
ENABLE_CONTROL=1
CONTROL_MAVROS_BOOL="false"
CONTROL_STALE_TIMEOUT_S=0.80
ENABLE_WEB_VIDEO=1
ENABLE_ROSBAG=0

# Profiles tune camera + inference defaults for known operator intents.
apply_startup_profile() {
    local profile="$1"
    case "$profile" in
        daily)
            CAMERA_WIDTH=1280
            CAMERA_HEIGHT=720
            CAMERA_APPLY_RATE_CONTROLS_BOOL="true"
            INFER_QUEUE_SIZE=1
            INFER_WORKERS=2
            INFER_TIMEOUT_MS=300
            INFER_RETRIES=0
            CONTROL_STALE_TIMEOUT_S=0.80
            ;;
        safe-camera)
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            INFER_QUEUE_SIZE=1
            INFER_WORKERS=1
            INFER_TIMEOUT_MS=300
            INFER_RETRIES=0
            CONTROL_STALE_TIMEOUT_S=0.90
            ;;
        performance)
            CAMERA_WIDTH=1280
            CAMERA_HEIGHT=720
            CAMERA_APPLY_RATE_CONTROLS_BOOL="true"
            INFER_QUEUE_SIZE=1
            INFER_WORKERS=2
            INFER_TIMEOUT_MS=250
            INFER_RETRIES=0
            CONTROL_STALE_TIMEOUT_S=0.70
            ;;
        *)
            echo "[error] invalid --profile '$profile' (expected daily|safe-camera|performance)"
            exit 1
            ;;
    esac
}

normalize_double_literal() {
    local value="$1"
    if [[ "$value" =~ ^-?[0-9]+$ ]]; then
        echo "${value}.0"
    else
        echo "$value"
    fi
}

apply_resolution_selector() {
    local raw_selector="$1"
    local selector="${raw_selector,,}"

    case "$selector" in
        vga|480p)
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            ;;
        hd|720p)
            CAMERA_WIDTH=1280
            CAMERA_HEIGHT=720
            ;;
        fhd|1080p|fullhd)
            CAMERA_WIDTH=1920
            CAMERA_HEIGHT=1080
            ;;
        *)
            if [[ "$raw_selector" =~ ^([0-9]+)[xX]([0-9]+)$ ]]; then
                CAMERA_WIDTH="${BASH_REMATCH[1]}"
                CAMERA_HEIGHT="${BASH_REMATCH[2]}"
            else
                echo "[error] invalid --resolution '$raw_selector' (expected vga|hd|fhd|WIDTHxHEIGHT)"
                return 1
            fi
            ;;
    esac

    return 0
}

# Parse CLI overrides. Validation happens in the next block so parse logic stays linear.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            if [[ $# -lt 2 ]]; then
                echo "[error] --profile requires a value"
                print_usage
                exit 1
            fi
            STARTUP_PROFILE="${2,,}"
            apply_startup_profile "$STARTUP_PROFILE"
            shift 2
            ;;
        --perception-mode)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-mode requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_MODE="${2,,}"
            shift 2
            ;;
        --resolution|--res)
            if [[ $# -lt 2 ]]; then
                echo "[error] --resolution requires a value"
                print_usage
                exit 1
            fi
            if ! apply_resolution_selector "$2"; then
                print_resolution_presets
                exit 1
            fi
            shift 2
            ;;
        --list-resolutions)
            print_resolution_presets
            exit 0
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
        -v|--verbose)
            VERBOSE=1
            shift
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
        --tracker-gc-probe-off)
            TRACKER_PROFILE_GC_PROBE=0
            shift
            ;;
        --tracker-gc-probe-on)
            TRACKER_PROFILE_GC_PROBE=1
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
        --tracker-iou-threshold)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-iou-threshold requires a value"
                print_usage
                exit 1
            fi
            TRACKER_IOU_THRESHOLD="$(normalize_double_literal "$2")"
            shift 2
            ;;
        --tracker-max-age)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-max-age requires a value"
                print_usage
                exit 1
            fi
            TRACKER_MAX_AGE="$2"
            shift 2
            ;;
        --tracker-min-hits)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-min-hits requires a value"
                print_usage
                exit 1
            fi
            TRACKER_MIN_HITS="$2"
            shift 2
            ;;
        --tracker-centre-gate)
            if [[ $# -lt 2 ]]; then
                echo "[error] --tracker-centre-gate requires a value"
                print_usage
                exit 1
            fi
            TRACKER_CENTRE_GATE="$(normalize_double_literal "$2")"
            shift 2
            ;;
        --tracks-off)
            TRACKER_PUBLISH_TRACKS_BOOL="false"
            shift
            ;;
        --tracks-require-subscribers)
            TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL="true"
            shift
            ;;
        --tracks-ignore-subscribers)
            TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL="false"
            shift
            ;;
        --tracker-timing-off)
            TRACKER_PUBLISH_TIMING_BOOL="false"
            shift
            ;;
        --tracker-timing-on)
            TRACKER_PUBLISH_TIMING_BOOL="true"
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
        --camera-publish-width)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-publish-width requires a value"
                print_usage
                exit 1
            fi
            CAMERA_PUBLISH_WIDTH="$2"
            CAMERA_PUBLISH_SHAPE_EXPLICIT=1
            shift 2
            ;;
        --camera-publish-height)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-publish-height requires a value"
                print_usage
                exit 1
            fi
            CAMERA_PUBLISH_HEIGHT="$2"
            CAMERA_PUBLISH_SHAPE_EXPLICIT=1
            shift 2
            ;;
        --camera-publish-resize-mode)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-publish-resize-mode requires a value"
                print_usage
                exit 1
            fi
            CAMERA_PUBLISH_RESIZE_MODE="${2,,}"
            shift 2
            ;;
        --camera-publish-encoding)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-publish-encoding requires a value"
                print_usage
                exit 1
            fi
            CAMERA_PUBLISH_ENCODING="${2,,}"
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
        --camera-rate-controls-off)
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            shift
            ;;
        --camera-rate-controls-on)
            CAMERA_APPLY_RATE_CONTROLS_BOOL="true"
            shift
            ;;
        --camera-sensor-max-fps)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-sensor-max-fps requires a value"
                print_usage
                exit 1
            fi
            CAMERA_SENSOR_MAX_FPS="$2"
            shift 2
            ;;
        --camera-ae-upper)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-ae-upper requires a value"
                print_usage
                exit 1
            fi
            CAMERA_SENSOR_AE_UPPER="$2"
            shift 2
            ;;
        --camera-ae-max)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-ae-max requires a value"
                print_usage
                exit 1
            fi
            CAMERA_SENSOR_AE_MAX="$2"
            shift 2
            ;;
        --camera-exposure-mode)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-exposure-mode requires a value"
                print_usage
                exit 1
            fi
            CAMERA_SENSOR_EXPOSURE_MODE="$2"
            shift 2
            ;;
        --camera-manual-exposure)
            if [[ $# -lt 2 ]]; then
                echo "[error] --camera-manual-exposure requires a value"
                print_usage
                exit 1
            fi
            CAMERA_SENSOR_MANUAL_EXPOSURE="$2"
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
        --perception-image-qos-depth)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-image-qos-depth requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_IMAGE_QOS_DEPTH="$2"
            shift 2
            ;;
        --perception-hailo-queue-buffers)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-hailo-queue-buffers requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_HAILO_QUEUE_BUFFERS="$2"
            shift 2
            ;;
        --perception-inference-backend)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-inference-backend requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_INFERENCE_BACKEND="${2,,}"
            shift 2
            ;;
        --perception-async-max-inflight)
            if [[ $# -lt 2 ]]; then
                echo "[error] --perception-async-max-inflight requires a value"
                print_usage
                exit 1
            fi
            PERCEPTION_ASYNC_MAX_INFLIGHT="$2"
            shift 2
            ;;
        --perception-async-latest-frame-off|--perception-async-latest-frame-on)
            echo "[error] $1 has been removed; single-process always uses queue+worker mode"
            exit 1
            ;;
        --perception-hailo-videoconvert-off)
            PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL="false"
            shift
            ;;
        --perception-hailo-videoconvert-on)
            PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL="true"
            shift
            ;;
        --perception-gc-off)
            PERCEPTION_GC_DISABLE_BOOL="true"
            shift
            ;;
        --perception-gc-on)
            PERCEPTION_GC_DISABLE_BOOL="false"
            shift
            ;;
        --perception-no-stub-fallback)
            PERCEPTION_ALLOW_STUB_FALLBACK_BOOL="false"
            shift
            ;;
        --perception-allow-stub-fallback)
            PERCEPTION_ALLOW_STUB_FALLBACK_BOOL="true"
            shift
            ;;
        --no-tracker)
            ENABLE_TRACKER=0
            shift
            ;;
        --no-target)
            echo "[warn] --no-target is deprecated; target selection now lives in dashboard_bridge_node /api/target"
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
        --help-advanced)
            print_advanced_usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate resolved configuration before we touch hardware/container state.
case "$PERCEPTION_MODE" in
    legacy|single-process)
        ;;
    *)
        echo "[error] invalid --perception-mode '$PERCEPTION_MODE' (expected legacy|single-process)"
        exit 1
        ;;
esac

case "$PERCEPTION_INFERENCE_BACKEND" in
    hailo|hailo_direct|direct|hailort|hailo_gst|gst|stub|none)
        ;;
    *)
        echo "[error] invalid --perception-inference-backend '$PERCEPTION_INFERENCE_BACKEND'"
        echo "        expected one of: hailo_direct, hailo_gst, hailo, gst, direct, hailort, stub, none"
        exit 1
        ;;
esac

if [[ "$CAMERA_PUBLISH_SHAPE_EXPLICIT" -eq 0 ]]; then
    if [[ "$PERCEPTION_MODE" == "single-process" ]]; then
        CAMERA_PUBLISH_WIDTH=640
        CAMERA_PUBLISH_HEIGHT=640
    else
        CAMERA_PUBLISH_WIDTH="$CAMERA_WIDTH"
        CAMERA_PUBLISH_HEIGHT="$CAMERA_HEIGHT"
    fi
fi

case "$TRACKER_TYPE" in
    sort|ocsort|bytetrack|deepsort)
        ;;
    *)
        echo "[error] invalid tracker '$TRACKER_TYPE' (expected sort|ocsort|bytetrack|deepsort)"
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

if [[ "$TRACKER_PROFILE_SERIALIZE_EVERY_N" -gt 0 ]]; then
    echo "[warn] tracker serialization profiling enabled (every ${TRACKER_PROFILE_SERIALIZE_EVERY_N} frames); this can add jitter"
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

if ! [[ "$CAMERA_PUBLISH_WIDTH" =~ ^[0-9]+$ ]] || [[ "$CAMERA_PUBLISH_WIDTH" -lt 1 ]]; then
    echo "[error] --camera-publish-width must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_PUBLISH_HEIGHT" =~ ^[0-9]+$ ]] || [[ "$CAMERA_PUBLISH_HEIGHT" -lt 1 ]]; then
    echo "[error] --camera-publish-height must be a positive integer"
    exit 1
fi

case "$CAMERA_PUBLISH_RESIZE_MODE" in
    resize|letterbox)
        ;;
    *)
        echo "[error] --camera-publish-resize-mode must be one of resize, letterbox"
        exit 1
        ;;
esac

case "$CAMERA_PUBLISH_ENCODING" in
    bgr8|rgb8)
        ;;
    *)
        echo "[error] --camera-publish-encoding must be one of bgr8, rgb8"
        exit 1
        ;;
esac

if ! [[ "$CAMERA_DASHBOARD_FPS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "[error] --dashboard-fps must be a positive number"
    exit 1
fi

if ! [[ "$CAMERA_SENSOR_MAX_FPS" =~ ^[0-9]+$ ]] || [[ "$CAMERA_SENSOR_MAX_FPS" -lt 1 ]]; then
    echo "[error] --camera-sensor-max-fps must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_SENSOR_AE_UPPER" =~ ^[0-9]+$ ]] || [[ "$CAMERA_SENSOR_AE_UPPER" -lt 1 ]]; then
    echo "[error] --camera-ae-upper must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_SENSOR_AE_MAX" =~ ^[0-9]+$ ]] || [[ "$CAMERA_SENSOR_AE_MAX" -lt 1 ]]; then
    echo "[error] --camera-ae-max must be a positive integer"
    exit 1
fi

if ! [[ "$CAMERA_SENSOR_EXPOSURE_MODE" =~ ^[0-2]$ ]]; then
    echo "[error] --camera-exposure-mode must be one of 0, 1, 2"
    exit 1
fi

if ! [[ "$CAMERA_SENSOR_MANUAL_EXPOSURE" =~ ^[0-9]+$ ]] || [[ "$CAMERA_SENSOR_MANUAL_EXPOSURE" -lt 1 ]]; then
    echo "[error] --camera-manual-exposure must be a positive integer"
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

if ! [[ "$PERCEPTION_IMAGE_QOS_DEPTH" =~ ^[0-9]+$ ]] || [[ "$PERCEPTION_IMAGE_QOS_DEPTH" -lt 1 ]]; then
    echo "[error] --perception-image-qos-depth must be a positive integer"
    exit 1
fi

if ! [[ "$PERCEPTION_HAILO_QUEUE_BUFFERS" =~ ^[0-9]+$ ]] || [[ "$PERCEPTION_HAILO_QUEUE_BUFFERS" -lt 1 ]]; then
    echo "[error] --perception-hailo-queue-buffers must be a positive integer"
    exit 1
fi

if ! [[ "$PERCEPTION_ASYNC_MAX_INFLIGHT" =~ ^[0-9]+$ ]] || [[ "$PERCEPTION_ASYNC_MAX_INFLIGHT" -lt 1 ]]; then
    echo "[error] --perception-async-max-inflight must be a positive integer"
    exit 1
fi

if [[ "$PERCEPTION_MODE" == "single-process" ]] && [[ "$PERCEPTION_ASYNC_MAX_INFLIGHT" -ne 1 ]]; then
    echo "[warn] single-process owner path enforces async_max_inflight=1; requested=${PERCEPTION_ASYNC_MAX_INFLIGHT}"
fi

if ! [[ "$CONTROL_STALE_TIMEOUT_S" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "[error] --control-stale-timeout-s must be a positive number"
    exit 1
fi

if [[ "$ENABLE_CONTROL" -eq 1 && "$ENABLE_DASHBOARD_BRIDGE" -eq 0 ]]; then
    echo "[warn] control requires /target from dashboard_bridge_node after target_selector removal; disabling control"
    ENABLE_CONTROL=0
fi

# Readiness helpers used by startup phases.
wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout_s="$3"
    local required="${4:-0}"

    local start_ts
    start_ts="$(date +%s)"

    while true; do
        if (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
            log_ok "port ${host}:${port} is reachable"
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
        log_ok "topic ${topic} produced a message"
        return 0
    fi

    if [[ "$required" == "1" ]]; then
        echo "[error] timeout waiting for required topic message on ${topic}"
        return 1
    fi

    echo "[warn] timeout waiting for topic message on ${topic}; continuing anyway"
    return 0
}

STACK_PROC_PATTERN="camera_bringup.launch.py|camera_capture_node|inference_client_node|detector_node|perception_pipeline_node|tracker_node|control_ref_node|dashboard_bridge_node|web_video_server"
CAMERA_MEDIA_DEV_OVERRIDE=""

# Preflight helpers keep startup deterministic and fail early on known bad host states.
check_stuck_camera_processes() {
    local stuck_lines
    stuck_lines="$(ps -eo pid=,stat=,cmd= | awk '$2 ~ /^D/ && $0 ~ /(camera_capture_node|v4l2-ctl|media-ctl)/ {print}' || true)"

    if [[ -n "${stuck_lines:-}" ]]; then
        echo "[error] detected camera/V4L2 process(es) stuck in uninterruptible I/O state (D):"
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
            log_info "auto-detected camera media graph on $CAMERA_MEDIA_DEV_OVERRIDE"
            return 0
        fi
    done

    echo "[warn] no media device currently exposes TEVS camera entities"
    log_hint "runtime auto-select can only choose among detected camera media graphs"
    log_hint "cam0/cam1 selection comes from boot overlay and requires reboot to change"

    local klog
    klog="$(journalctl -k -b --no-pager 2>/dev/null | tail -n 500 || true)"
    if [[ -n "${klog:-}" ]] && grep -qiE "pca953x.*failed writing register|probe.*error -121" <<<"$klog"; then
        log_hint "kernel reports camera control I2C probe failure (pca953x/-121)"
        log_hint "verify camera port (cam0/cam1) and overlay in /boot/firmware/config.txt"
    fi

    return 1
}

detect_tevs_sensor_entity() {
    local media_dev="${1:-/dev/media0}"
    local topology

    topology="$(media-ctl -d "$media_dev" -p 2>/dev/null || true)"
    if [[ -z "${topology:-}" ]]; then
        return 1
    fi

    awk '
        match($0, /- entity[[:space:]]+[0-9]+:[[:space:]]+tevs[^\(]*/) {
            s = substr($0, RSTART, RLENGTH)
            sub(/- entity[[:space:]]+[0-9]+:[[:space:]]+/, "", s)
            gsub(/[[:space:]]+$/, "", s)
            print s
            exit
        }
    ' <<<"$topology"
}

configure_camera_stream_path() {
    local media_dev="$1"
    local sensor_entity="$2"
    local width="$3"
    local height="$4"
    local fmt="fmt:UYVY8_1X16/${width}x${height} field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"

    timeout 5s media-ctl -d "$media_dev" -l '"csi2":4 -> "rp1-cfe-csi2_ch0":0 [1]' >/dev/null 2>&1 || return 1
    timeout 5s media-ctl -d "$media_dev" -V "\"${sensor_entity}\":0 [${fmt}]" >/dev/null 2>&1 || return 1
    timeout 5s media-ctl -d "$media_dev" -V '"csi2":0 ['"${fmt}"']' >/dev/null 2>&1 || return 1
    timeout 5s media-ctl -d "$media_dev" -V '"csi2":4 ['"${fmt}"']' >/dev/null 2>&1 || return 1
    return 0
}

probe_camera_stream_once() {
    local width="$1"
    local height="$2"
    timeout 8s v4l2-ctl -d /dev/video0 \
        --set-fmt-video="width=${width},height=${height},pixelformat=UYVY" \
        --stream-mmap=4 \
        --stream-count=10 \
        --stream-to=/dev/null \
        --stream-poll >/dev/null 2>&1
}

preflight_validate_camera_stream() {
    local media_dev="${CAMERA_MEDIA_DEV_OVERRIDE:-/dev/media0}"
    local sensor_entity
    local tried_fallback=0

    if [[ ! -e "$media_dev" ]]; then
        echo "[error] camera media device not found for stream preflight: $media_dev"
        return 1
    fi

    sensor_entity="$(detect_tevs_sensor_entity "$media_dev" || true)"
    if [[ -z "${sensor_entity:-}" ]]; then
        echo "[error] unable to detect TEVS sensor entity on $media_dev"
        return 1
    fi

    if configure_camera_stream_path "$media_dev" "$sensor_entity" "$CAMERA_WIDTH" "$CAMERA_HEIGHT" \
        && probe_camera_stream_once "$CAMERA_WIDTH" "$CAMERA_HEIGHT"; then
        log_ok "camera stream preflight passed at ${CAMERA_WIDTH}x${CAMERA_HEIGHT}"
        return 0
    fi

    if [[ "$CAMERA_WIDTH" -ne 640 || "$CAMERA_HEIGHT" -ne 480 ]]; then
        tried_fallback=1
        if configure_camera_stream_path "$media_dev" "$sensor_entity" 640 480 \
            && probe_camera_stream_once 640 480; then
            echo "[warn] camera stream preflight failed at ${CAMERA_WIDTH}x${CAMERA_HEIGHT}; falling back to 640x480"
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            if [[ "$CAMERA_PUBLISH_SHAPE_EXPLICIT" -eq 0 ]]; then
                CAMERA_PUBLISH_WIDTH=640
                CAMERA_PUBLISH_HEIGHT=480
            fi
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            log_ok "camera stream preflight passed at 640x480"
            return 0
        fi
    fi

    echo "[error] camera stream preflight failed on /dev/video0"
    if [[ "$tried_fallback" -eq 1 ]]; then
        echo "[error] attempted both configured mode and 640x480 fallback"
    fi
    log_hint "if kernel shows i2c_designware timeout or tevs ret=-110, reboot host before retry"
    return 1
}

preflight_enable_csi_capture_link() {
    local media_dev="${CAMERA_MEDIA_DEV_OVERRIDE:-/dev/media0}"
    local topology

    if [[ ! -e "$media_dev" ]]; then
        return 0
    fi

    topology="$(media-ctl -d "$media_dev" -p 2>/dev/null || true)"
    if [[ -z "${topology:-}" ]]; then
        return 0
    fi

    if ! grep -q '"rp1-cfe-csi2_ch0"' <<<"$topology"; then
        return 0
    fi

    if grep -Eq '"csi2":[[:space:]]*4[[:space:]]*->[[:space:]]*"rp1-cfe-csi2_ch0":0[[:space:]]*\[(ENABLED|1)\]' <<<"$topology"; then
        log_ok "camera capture link csi2->rp1-cfe-csi2_ch0 already enabled on $media_dev"
        return 0
    fi

    if media-ctl -d "$media_dev" -l '"csi2":4 -> "rp1-cfe-csi2_ch0":0 [1]' >/dev/null 2>&1; then
        log_info "pre-enabled csi2->rp1-cfe-csi2_ch0 on $media_dev"
        return 0
    fi

    echo "[warn] failed to pre-enable csi2->rp1-cfe-csi2_ch0 on $media_dev"
    log_hint "camera node will still attempt media init; inspect $RUN_DIR/camera.log if startup fails"
    return 0
}

camera_log_has_sensor_control_error() {
    local log_file="$RUN_DIR/camera.log"

    if [[ ! -f "$log_file" ]]; then
        return 1
    fi

    rg -qi "Sensor rate control timed out|VIDIOC_S_EXT_CTRLS: failed: Connection timed out|VIDIOC_S_EXT_CTRLS: failed: Unknown error 220|max_fps: Connection timed out|max_fps: Unknown error 220" "$log_file"
}

camera_log_has_context_invalid_error() {
    local log_file="$RUN_DIR/camera.log"

    if [[ ! -f "$log_file" ]]; then
        return 1
    fi

    rg -qi "context is not valid|ExternalShutdownException|failed to create guard_condition" "$log_file"
}

camera_kernel_has_link_not_enabled() {
    journalctl -k -b --no-pager 2>/dev/null \
        | tail -n 240 \
        | rg -qi "csi2_ch0 node link is not enabled|stream on failed in subdev|Wrong width or height"
}

camera_kernel_has_i2c_timeout() {
    journalctl -k -b --no-pager 2>/dev/null \
        | tail -n 240 \
        | rg -qi "i2c_designware.*timeout|tevs .*failed to read from register|ret=-110"
}

stop_camera_process_only() {
    local pid="${PROC_PIDS[camera]:-}"

    if [[ -z "${pid:-}" ]]; then
        return 0
    fi

    if kill -0 "$pid" >/dev/null 2>&1; then
        kill_tree "$pid" INT
        sleep 1
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill_tree "$pid" TERM
        fi
        log_stop "camera (pid=$pid)"
    fi

    unset 'PROC_PIDS[camera]'
    return 0
}

build_camera_args() {
    CAMERA_ARGS=()
    if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 0 ]]; then
        CAMERA_ARGS+=("publish_dashboard_topic:=false")
    fi

    CAMERA_ARGS+=("width:=$CAMERA_WIDTH")
    CAMERA_ARGS+=("height:=$CAMERA_HEIGHT")
    CAMERA_ARGS+=("publish_width:=$CAMERA_PUBLISH_WIDTH")
    CAMERA_ARGS+=("publish_height:=$CAMERA_PUBLISH_HEIGHT")
    CAMERA_ARGS+=("publish_resize_mode:=$CAMERA_PUBLISH_RESIZE_MODE")
    CAMERA_ARGS+=("publish_encoding:=$CAMERA_PUBLISH_ENCODING")
    CAMERA_ARGS+=("fps:=$CAMERA_FPS")
    CAMERA_ARGS+=("dashboard_fps:=$CAMERA_DASHBOARD_FPS")
    CAMERA_ARGS+=("flip_image:=$CAMERA_FLIP_BOOL")
    CAMERA_ARGS+=("apply_sensor_rate_controls:=$CAMERA_APPLY_RATE_CONTROLS_BOOL")
    CAMERA_ARGS+=("sensor_max_fps:=$CAMERA_SENSOR_MAX_FPS")
    CAMERA_ARGS+=("sensor_ae_exposure_upper:=$CAMERA_SENSOR_AE_UPPER")
    CAMERA_ARGS+=("sensor_ae_exposure_max:=$CAMERA_SENSOR_AE_MAX")
    CAMERA_ARGS+=("sensor_exposure_mode:=$CAMERA_SENSOR_EXPOSURE_MODE")
    CAMERA_ARGS+=("sensor_manual_exposure:=$CAMERA_SENSOR_MANUAL_EXPOSURE")
    if [[ -n "${CAMERA_MEDIA_DEV_OVERRIDE:-}" ]]; then
        CAMERA_ARGS+=("media_dev:=$CAMERA_MEDIA_DEV_OVERRIDE")
    fi
}

start_camera_with_readiness() {
    # Return codes:
    #   0 -> healthy startup with frame activity
    #   2 -> process died during startup
    #   3 -> fatal startup error detected in logs
    #   4 -> process alive but no frame evidence within readiness window
    start_ros_bg camera ros2 launch thesis_bringup camera_bringup.launch.py "${CAMERA_ARGS[@]}"
    sleep 2
    if ! check_proc_alive camera; then
        return 2
    fi
    if ! wait_for_topic_message /camera/image_raw 20 1 sensor_data best_effort volatile; then
        if ! check_proc_alive camera; then
            return 2
        fi
        if wait_for_topic_message /camera/capture_fps 8 0; then
            echo "[warn] /camera/image_raw readiness probe timed out, but /camera/capture_fps is active; continuing"
            return 0
        fi
        if camera_log_has_frame_activity; then
            echo "[warn] /camera/image_raw readiness probe timed out, but camera log shows active frame pipeline; continuing"
            return 0
        fi
        if camera_log_has_fatal_error; then
            return 3
        fi
        return 4
    fi
    return 0
}

tracker_state="off"
control_state="off"
dashboard_state="off"
web_video_state="off"
rosbag_state="off"

if [[ "$ENABLE_TRACKER" -eq 1 ]]; then tracker_state="on"; fi
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

# Phase 1: host preflight + camera stream sanity checks.
log_info "run: $RUN_ID"
log_info "logs: $RUN_DIR"
log_info "mode: perception=$PERCEPTION_MODE"
log_info "cfg: camera_capture=${CAMERA_WIDTH}x${CAMERA_HEIGHT} camera_publish=${CAMERA_PUBLISH_WIDTH}x${CAMERA_PUBLISH_HEIGHT}(${CAMERA_PUBLISH_RESIZE_MODE},${CAMERA_PUBLISH_ENCODING})@${CAMERA_FPS} infer=q${INFER_QUEUE_SIZE}/w${INFER_WORKERS}/t${INFER_TIMEOUT_MS}ms/r${INFER_RETRIES} img_qos_depth=${PERCEPTION_IMAGE_QOS_DEPTH} hailo_queue_buffers=${PERCEPTION_HAILO_QUEUE_BUFFERS} async_max_inflight=${PERCEPTION_ASYNC_MAX_INFLIGHT} hailo_videoconvert=${PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL} perception_gc_disable=${PERCEPTION_GC_DISABLE_BOOL} allow_stub_fallback=${PERCEPTION_ALLOW_STUB_FALLBACK_BOOL} control_stale=${CONTROL_STALE_TIMEOUT_S}s"
log_info "cfg: camera_rate_controls=${CAMERA_APPLY_RATE_CONTROLS_BOOL} sensor_max_fps=${CAMERA_SENSOR_MAX_FPS} ae_upper=${CAMERA_SENSOR_AE_UPPER} ae_max=${CAMERA_SENSOR_AE_MAX} exposure_mode=${CAMERA_SENSOR_EXPOSURE_MODE}"
log_info "nodes: tracker=$tracker_state control=$control_state dashboard=$dashboard_state web_video=$web_video_state rosbag=$rosbag_state"
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    log_info "tracker: type=$TRACKER_TYPE tracks=$TRACKER_PUBLISH_TRACKS_BOOL tracks_require_subscribers=$TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL timing_topic=$TRACKER_PUBLISH_TIMING_BOOL profile=$TRACKER_PROFILE_ENABLED gc_probe=$TRACKER_PROFILE_GC_PROBE iou=$TRACKER_IOU_THRESHOLD max_age=$TRACKER_MAX_AGE min_hits=$TRACKER_MIN_HITS centre_gate=$TRACKER_CENTRE_GATE"
fi
log_step "preflight checks"
if ! check_stuck_camera_processes; then
    exit 1
fi
if ! cleanup_existing_stack_processes; then
    exit 1
fi
detect_camera_media_device || true
preflight_enable_csi_capture_link || true
if ! preflight_validate_camera_stream; then
    exit 1
fi

# Phase 2: source ROS overlays after preflight succeeds.
log_step "sourcing ROS environment"
cd "$ROS_WS"
export ROS_LOG_DIR
set +u
source /opt/ros/jazzy/setup.bash
if [[ -f "install/setup.bash" ]]; then
    source install/setup.bash
else
    echo "[error] missing workspace setup: $ROS_WS/install/setup.bash"
    log_hint "build the ROS workspace first:"
    log_hint "       cd $ROS_WS"
    log_hint "       source /opt/ros/jazzy/setup.bash"
    log_hint "       colcon build --symlink-install"
    log_hint "       source install/setup.bash"
    exit 1
fi
set -u
export ROS_DOMAIN_ID
log_info "ros: domain=$ROS_DOMAIN_ID log_dir=$ROS_LOG_DIR"

# Phase 3: mode-specific perception readiness (container legacy path or host single-process path).
if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
    if [[ ! -f "$PI_AI_DIR/docker-compose.yaml" ]]; then
        echo "[error] legacy compose file not found: $PI_AI_DIR/docker-compose.yaml"
        echo "[hint] set PI_AI_DIR or place compose project at $THESIS_ROOT/deprecated/pi-ai-kit-ubuntu"
        stop_stack
        exit 1
    fi

    log_step "ensuring container is up"
    (
        cd "$PI_AI_DIR"
        docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
    ) >"$RUN_DIR/container_up.log" 2>&1

    # If the bind mount is stale (e.g. host dir recreated), detection script can disappear
    # inside an otherwise running container. Recreate once to refresh mounts.
    if ! docker exec "$CONTAINER_NAME" test -f /root/thesis_deprecated/infer_service/detection_zmq.py >/dev/null 2>&1; then
        echo "[warn] detection service script missing in container mount; recreating container"
        (
            cd "$PI_AI_DIR"
            docker compose -f docker-compose.yaml up -d --force-recreate hailo-ubuntu-pi
        ) >>"$RUN_DIR/container_up.log" 2>&1

        if ! docker exec "$CONTAINER_NAME" test -f /root/thesis_deprecated/infer_service/detection_zmq.py >/dev/null 2>&1; then
            echo "[error] container mount is still missing /root/thesis_deprecated/infer_service/detection_zmq.py"
            echo "[error] check docker-compose bind mount for thesis_deprecated and host path contents"
            stop_stack
            exit 1
        fi
    fi

    log_step "starting detection service in container"
    docker exec "$CONTAINER_NAME" bash -lc '
set -euo pipefail
for pid in $(pgrep -f detection_zmq.py || true); do
    if [ "$pid" != "$$" ]; then
        kill "$pid" >/dev/null 2>&1 || true
    fi
done
HAILO_EXAMPLES_DIR=/root/thesis_deprecated/hailo-rpi5-examples
if [ ! -d "$HAILO_EXAMPLES_DIR" ]; then
    HAILO_EXAMPLES_DIR=/root/hailo-rpi5-examples
fi
VENV="$HAILO_EXAMPLES_DIR/venv_hailo_rpi_examples"
export PYTHONPATH="$HAILO_EXAMPLES_DIR:${PYTHONPATH:-}"
DETECTION_ENTRY=/root/thesis_deprecated/infer_service/detection_zmq.py
if [ ! -f "$DETECTION_ENTRY" ]; then
    echo "missing detection entrypoint: $DETECTION_ENTRY" >&2
    exit 1
fi
cd /root/thesis_service
export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND=tcp://0.0.0.0:5556
export HAILO_INFER_WIDTH=640
export HAILO_INFER_HEIGHT=640
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter
export HAILO_DET_LABEL=person
export HAILO_REQREP_LOG_EVERY=${HAILO_REQREP_LOG_EVERY:-0}
nohup "$VENV/bin/python" "$DETECTION_ENTRY" > /tmp/detection_zmq_live.log 2>&1 &
' >"$RUN_DIR/container_infer_start.log" 2>&1

    if ! wait_for_port 127.0.0.1 5556 20 1; then
        stop_stack
        exit 1
    fi
else
    log_step "single-process perception mode selected"
    log_info "single-process mode will run in-process perception_pipeline_node"
    if [[ "$PERCEPTION_ALLOW_STUB_FALLBACK_BOOL" == "true" ]]; then
        log_hint "host Hailo init failures will fallback to stub backend (override enabled)"
    else
        log_hint "host Hailo init failures are fail-fast by default; use --perception-allow-stub-fallback to override"
    fi
    log_info "skipping container detection_zmq startup in single-process mode"
fi

log_step "starting ROS nodes"
# rclpy expects camera fps launch parameter as DOUBLE; normalize integer input to float.
if [[ "$CAMERA_FPS" =~ ^[0-9]+$ ]]; then
    CAMERA_FPS="${CAMERA_FPS}.0"
fi

# rclpy expects dashboard_fps launch parameter as DOUBLE; normalize integer input to float.
if [[ "$CAMERA_DASHBOARD_FPS" =~ ^[0-9]+$ ]]; then
    CAMERA_DASHBOARD_FPS="${CAMERA_DASHBOARD_FPS}.0"
fi

# Camera is the first ROS dependency in the chain. Retry once for two known failure classes.
camera_retry_applied=0
camera_safe_retry_applied=0
while true; do
    build_camera_args
    if start_camera_with_readiness; then
        break
    fi

    camera_start_rc=$?
    if [[ "$camera_start_rc" -eq 2 ]]; then
        echo "[error] camera process exited during startup; see $RUN_DIR/camera.log"
    elif [[ "$camera_start_rc" -eq 3 ]]; then
        echo "[error] camera startup failed; see $RUN_DIR/camera.log"
    else
        echo "[error] camera node is running but not publishing frames"
    fi

    if [[ "$camera_retry_applied" -eq 0 ]] \
        && [[ "$CAMERA_APPLY_RATE_CONTROLS_BOOL" == "true" ]] \
        && camera_log_has_sensor_control_error; then
        echo "[warn] detected TEVS sensor control timeout/error during camera init"
        echo "[warn] retrying camera startup once with sensor rate controls disabled"
        CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
        camera_retry_applied=1
        stop_camera_process_only
        continue
    fi

    if [[ "$camera_safe_retry_applied" -eq 0 ]]; then
        if [[ "$camera_start_rc" -eq 3 ]] && camera_log_has_context_invalid_error; then
            echo "[warn] camera startup hit ROS context-invalid shutdown path"
            echo "[warn] retrying camera startup once in safe mode (640x480, rate controls off)"
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            if [[ "$CAMERA_PUBLISH_SHAPE_EXPLICIT" -eq 0 ]]; then
                CAMERA_PUBLISH_WIDTH=640
                CAMERA_PUBLISH_HEIGHT=480
            fi
            camera_safe_retry_applied=1
            stop_camera_process_only
            continue
        fi

        if [[ "$camera_start_rc" -eq 4 ]]; then
            echo "[warn] camera is running but no frames reached /camera/image_raw"
            echo "[warn] retrying camera startup once in safe mode (640x480, rate controls off)"
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            if [[ "$CAMERA_PUBLISH_SHAPE_EXPLICIT" -eq 0 ]]; then
                CAMERA_PUBLISH_WIDTH=640
                CAMERA_PUBLISH_HEIGHT=480
            fi
            camera_safe_retry_applied=1
            stop_camera_process_only
            continue
        fi
    fi

    if camera_kernel_has_link_not_enabled; then
        log_hint "kernel reports camera link/stream state error (csi2_ch0 link or stream-on failed)"
        log_hint "verify media graph link state and camera format alignment before retry"
    fi

    if camera_kernel_has_i2c_timeout; then
        log_hint "kernel reports TEVS/I2C timeout activity; camera pipeline may be wedged"
        log_hint "reboot host to recover the camera driver path before retrying"
    fi

    log_hint "check camera cable/sensor state and try restarting stack"
    log_hint "if issue persists, reboot host to reset camera pipeline"
    log_hint "if media topology lacks sensor entities, verify /boot/firmware/config.txt overlay port (cam0 vs cam1)"
    stop_stack
    exit 1
done

if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
    start_ros_bg detector ros2 run thesis_inference_client detector_node --ros-args \
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
    if ! check_proc_alive detector; then
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
        log_info "single-process: using local postprocess lib at $PERCEPTION_RUNTIME_POST_SO"
    fi

    start_ros_bg perception_pipeline env PYTHONPATH="$PERCEPTION_PYTHONPATH" LD_LIBRARY_PATH="$PERCEPTION_LD_LIBRARY_PATH" GST_PLUGIN_PATH="$PERCEPTION_GST_PLUGIN_PATH" ros2 run thesis_bringup perception_pipeline_node --ros-args \
        -p image_topic:=/camera/image_raw \
        -p img_w:=640 \
        -p img_h:=640 \
        -p frame_queue_size:=$INFER_QUEUE_SIZE \
        -p num_workers:=$INFER_WORKERS \
        -p image_qos_depth:=$PERCEPTION_IMAGE_QOS_DEPTH \
        -p hailo_queue_max_buffers:=$PERCEPTION_HAILO_QUEUE_BUFFERS \
        -p async_max_inflight:=$PERCEPTION_ASYNC_MAX_INFLIGHT \
        -p hailo_use_videoconvert:=$PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL \
        -p disable_python_gc:=$PERCEPTION_GC_DISABLE_BOOL \
        -p label:=person \
        -p min_score:=0.35 \
        -p inference_backend:=$PERCEPTION_INFERENCE_BACKEND \
        -p allow_stub_fallback:=$PERCEPTION_ALLOW_STUB_FALLBACK_BOOL \
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

# Phase 4: bring up downstream nodes after camera + perception are healthy.
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    start_ros_bg tracker ros2 run thesis_tracker tracker_node --ros-args \
        -p tracker_type:=$TRACKER_TYPE \
        -p iou_threshold:=$TRACKER_IOU_THRESHOLD \
        -p max_age:=$TRACKER_MAX_AGE \
        -p min_hits:=$TRACKER_MIN_HITS \
        -p centre_gate:=$TRACKER_CENTRE_GATE \
        -p publish_tracks:=$TRACKER_PUBLISH_TRACKS_BOOL \
        -p publish_tracks_requires_subscribers:=$TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL \
        -p publish_timing_topic:=$TRACKER_PUBLISH_TIMING_BOOL \
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

if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    # Container model-switch API is only meaningful in legacy perception mode.
    DASHBOARD_CONTAINER_MODEL_SWITCH_BOOL="false"
    if [[ "$PERCEPTION_MODE" == "legacy" ]]; then
        DASHBOARD_CONTAINER_MODEL_SWITCH_BOOL="true"
    fi

    start_ros_bg dashboard_bridge ros2 run thesis_bringup dashboard_bridge_node --ros-args \
        -p img_w:=640 \
        -p img_h:=640 \
        -p camera_ref_w:=$CAMERA_WIDTH \
        -p camera_ref_h:=$CAMERA_HEIGHT \
        -p camera_publish_resize_mode:=$CAMERA_PUBLISH_RESIZE_MODE \
        -p enable_container_model_switch_api:=$DASHBOARD_CONTAINER_MODEL_SWITCH_BOOL
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

if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 && "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
    echo "[ok] Live stack started successfully. Dashboard: $VIDEO_URL | WS: $WS_URL"
elif [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    echo "[ok] Live stack started successfully. WS: $WS_URL"
else
    echo "[ok] Live stack started successfully."
fi
print_startup_success_summary

log_done "live stack ready"
log_info "logs: $RUN_DIR"
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 && "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
    log_info "dashboard: video=$VIDEO_URL ws=$WS_URL"
fi
if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    if [[ "$ENABLE_WEB_VIDEO" -eq 0 ]]; then
        log_info "dashboard: ws=$WS_URL"
    fi
else
    log_info "dashboard: disabled"
fi
log_info "commands: status | clear | stop"

# Runtime control loop keeps operators in one shell for quick status/stop commands.
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
