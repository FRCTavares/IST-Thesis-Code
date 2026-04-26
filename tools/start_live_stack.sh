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

source "$THESIS_ROOT/tools/lib/live_usage.sh"
source "$THESIS_ROOT/tools/lib/live_defaults.sh"

source "$THESIS_ROOT/tools/lib/live_cli.sh"
parse_and_validate_live_stack_args "$@"

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

source "$THESIS_ROOT/tools/lib/live_camera.sh"

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
log_info "cfg: camera_trigger_control=${CAMERA_APPLY_TRIGGER_CONTROL_BOOL} camera_rate_controls=${CAMERA_APPLY_RATE_CONTROLS_BOOL} preflight_stream_probe=${CAMERA_PREFLIGHT_STREAM_PROBE_BOOL} sensor_max_fps=${CAMERA_SENSOR_MAX_FPS} ae_upper=${CAMERA_SENSOR_AE_UPPER} ae_max=${CAMERA_SENSOR_AE_MAX} exposure_mode=${CAMERA_SENSOR_EXPOSURE_MODE}"
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
