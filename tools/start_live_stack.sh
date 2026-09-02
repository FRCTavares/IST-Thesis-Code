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
# 3) Perception readiness: validate integrated camera perception configuration.
# 4) ROS nodes: camera -> integrated-camera perception -> tracker/control/dashboard -> video.
# 5) Runtime shell: keep stack alive and allow `status|clear|stop` commands.
#
# Logging policy:
# - Script/service logs:   $ROS_WS/log/live_stack/<run-id>/
# - ROS runtime logs:      $ROS_WS/log/runtime/<run-id>/
#
# This prevents ROS logs from ending up in ~/.ros/log during live runs.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
# Current supported runtime is the integrated camera live stack.
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
REID_MODEL_PATH="${REID_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}"

if [[ -z "${PI_IP// }" ]]; then
    PI_IP="127.0.0.1"
fi

# Captured before any argument parsing consumes "$@", for Issue #54 run
# provenance (the exact invocation belongs in every retained run's metadata).
ORIGINAL_INVOCATION="$(printf '%q ' "start_live_stack.sh" "$@")"

LOG_ROOT="$ROS_WS/log/live_stack"
RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
RUN_DIR="$LOG_ROOT/$RUN_ID"
PID_FILE="$RUN_DIR/pids.txt"
LATEST_LINK="$LOG_ROOT/latest"
ROS_RUNTIME_LOG_ROOT="$ROS_WS/log/runtime"
ROS_LOG_DIR="$ROS_RUNTIME_LOG_ROOT/$RUN_ID"
TARGET_AUTHORITY_SOURCE="/target_memory_mars"
TARGET_AUTHORITY_EVENT_LOG="$RUN_DIR/target_authority_events.jsonl"

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

    detector_summary="mode=integrated-camera backend=${PERCEPTION_INFERENCE_BACKEND} model=${PERCEPTION_DETECTOR_MODEL} hef=${PERCEPTION_HAILO_HEF_PATH} frame_queue=${INFER_QUEUE_SIZE} workers=${INFER_WORKERS} image_qos_depth=${PERCEPTION_IMAGE_QOS_DEPTH} hailo_queue_buffers=${PERCEPTION_HAILO_QUEUE_BUFFERS} async_max_inflight=${PERCEPTION_ASYNC_MAX_INFLIGHT}"

    if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
        if [[ "$TRACKER_TYPE" == "deepsort" ]]; then
            tracker_summary="enabled type=${TRACKER_TYPE} max_age=${TRACKER_MAX_AGE} min_hits=${TRACKER_MIN_HITS} reid_model=${REID_MODEL_PATH}"
        else
            tracker_summary="enabled type=${TRACKER_TYPE} iou=${TRACKER_IOU_THRESHOLD} max_age=${TRACKER_MAX_AGE} min_hits=${TRACKER_MIN_HITS} centre_gate=${TRACKER_CENTRE_GATE}"
        fi
    else
        tracker_summary="disabled"
    fi

    echo "[ok] startup summary: capture=${capture_size} publish=${publish_size} hailo_infer=${infer_size}"
    echo "[ok] detector: ${detector_summary}"
    echo "[ok] tracker: ${tracker_summary}"
    echo "[ok] target memory: mode=${TARGET_MEMORY_MODE:-mars} mars=${RUN_TARGET_MEMORY_MARS:-0}"
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

archive_target_authority_events() {
    if [[ ! -f "$TARGET_AUTHORITY_EVENT_LOG" ]]; then
        return
    fi

    local bag_dir
    for bag_dir in \
        "${VIDEO_BAG_OUT_DIR:-}" \
        "${DATASET_BAG_OUT_DIR:-}"; do
        if [[ -n "$bag_dir" && -d "$bag_dir" ]]; then
            cp "$TARGET_AUTHORITY_EVENT_LOG" \
                "$bag_dir/target_authority_events.jsonl"
        fi
    done
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
    pkill -f "perception_pipeline_node|perception_camera_node" >/dev/null 2>&1 || true
    pkill -f "perception_camera_node" >/dev/null 2>&1 || true
    pkill -f "tracker_node" >/dev/null 2>&1 || true
    pkill -f "control_ref_node" >/dev/null 2>&1 || true
    pkill -f "dashboard_bridge_node" >/dev/null 2>&1 || true
    pkill -f "target_memory_mars_node" >/dev/null 2>&1 || true
    pkill -f "web_video_server" >/dev/null 2>&1 || true

    archive_target_authority_events

    log_done "live stack stop requested"
}

trap 'stop_stack; exit 0' INT TERM

source "$THESIS_ROOT/tools/lib/live_usage.sh"
source "$THESIS_ROOT/tools/lib/live_defaults.sh"
source "$THESIS_ROOT/tools/lib/live_storage.sh"

source "$THESIS_ROOT/tools/lib/live_cli.sh"
parse_and_validate_live_stack_args "$@"

if [[ "${TRACKER_TYPE:-}" == "deepsort" && ! -f "$REID_MODEL_PATH" ]]; then
    echo "[error] DeepSORT ReID model not found: $REID_MODEL_PATH"
    echo "[hint] set REID_MODEL_PATH=/path/to/mars-small128.pb"
    exit 1
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

make_safe_name() {
    printf "%s" "$1" | tr ' /:' '___' | tr -cd 'A-Za-z0-9_.-'
}

write_video_bag_metadata() {
    local metadata_file="$1"
    shift
    local -a topics=("$@")

    {
        echo "run_id=$RUN_ID"
        echo "bag_name=${VIDEO_BAG_NAME:-}"
        echo "dataset_bag_name=${DATASET_BAG_NAME:-}"
        echo "bag_tag=${BAG_TAG:-}"
        echo "date=$(date -Iseconds)"
        echo "thesis_root=$THESIS_ROOT"
        echo "ros_ws=$ROS_WS"
        echo "ros_domain_id=$ROS_DOMAIN_ID"
        echo "perception_mode=$PERCEPTION_MODE"
        echo "perception_backend=${PERCEPTION_INFERENCE_BACKEND:-}"
        echo "tracker_enabled=$ENABLE_TRACKER"
        echo "tracker_type=${TRACKER_TYPE:-}"
        echo "camera_capture=${CAMERA_WIDTH}x${CAMERA_HEIGHT}@${CAMERA_FPS}"
        echo "camera_publish=${CAMERA_PUBLISH_WIDTH}x${CAMERA_PUBLISH_HEIGHT}"
        echo "camera_publish_resize_mode=${CAMERA_PUBLISH_RESIZE_MODE:-}"
        echo "camera_publish_encoding=${CAMERA_PUBLISH_ENCODING:-}"
        echo "control_enabled=$ENABLE_CONTROL"
        echo "freshness_contract=tim_mars_output_freshness_v1"
        echo "control_stale_timeout_s=$CONTROL_STALE_TIMEOUT_S"
        echo "freshness_source_age_gate=true"
        echo "freshness_receive_age_gate=true"
        echo "target_authority_source=$TARGET_AUTHORITY_SOURCE"
        echo "target_authority_generation_initial=0"
        echo "target_authority_event_log=target_authority_events.jsonl"
        echo "target_authority_runtime_log=$TARGET_AUTHORITY_EVENT_LOG"
        echo "runtime_reconfiguration_enabled=false"
        echo "mavros_mirror_enabled=${CONTROL_MAVROS_BOOL:-false}"
        echo "record_mavros=$RECORD_MAVROS"
        echo "bag_out_dir=${VIDEO_BAG_OUT_DIR:-}"
        echo "dataset_bag_out_dir=${DATASET_BAG_OUT_DIR:-}"
        echo "log_run_dir=$RUN_DIR"
        echo ""
        echo "recorded_topics:"
        for topic in "${topics[@]}"; do
            echo "- $topic"
        done
    } > "$metadata_file"
}

# Issue #54 schema-v1 provenance record: git commit/state, exact invocation,
# hardware/software versions, model/config hashes, resolved ROS parameters,
# topic/QoS inventory, selected target, and runtime switch history. Written
# atomically alongside the plain-text summary above. Best-effort: a failure
# here degrades provenance for this run but must not take down live
# recording, so it never calls stop_stack.
write_live_run_provenance() {
    local bag_kind="$1"
    local output_path="$2"
    shift 2
    local -a topics=("$@")

    local -a recorded_topic_args=()
    local topic
    for topic in "${topics[@]}"; do
        recorded_topic_args+=(--recorded-topic "$topic")
    done

    local -a param_args=()
    local p
    if [[ -n "${PERCEPTION_CAMERA_RESOLVED_PARAMS+x}" ]]; then
        for p in "${PERCEPTION_CAMERA_RESOLVED_PARAMS[@]}"; do
            param_args+=(--param "perception_camera_node:${p}")
        done
    fi
    if [[ -n "${TRACKER_RESOLVED_PARAMS+x}" ]]; then
        for p in "${TRACKER_RESOLVED_PARAMS[@]}"; do
            param_args+=(--param "tracker_node:${p}")
        done
    fi
    if [[ -n "${DASHBOARD_BRIDGE_RESOLVED_PARAMS+x}" ]]; then
        for p in "${DASHBOARD_BRIDGE_RESOLVED_PARAMS[@]}"; do
            param_args+=(--param "dashboard_bridge_node:${p}")
        done
    fi

    local -a hash_args=()
    if [[ -n "${PERCEPTION_HAILO_HEF_PATH:-}" ]]; then
        hash_args+=(--hash-file "detector_hef=$PERCEPTION_HAILO_HEF_PATH")
    fi
    if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then
        hash_args+=(--hash-file "tim_mars_reid_model=$TARGET_MEMORY_MARS_MODEL_PATH")
        hash_args+=(--hash-file "tim_mars_config=$TARGET_MEMORY_MARS_CONFIG")
    fi

    local -a switch_log_args=()
    if [[ -f "${TARGET_AUTHORITY_EVENT_LOG:-}" ]]; then
        switch_log_args=(--switch-history-log "$TARGET_AUTHORITY_EVENT_LOG")
    fi

    if ! python3 "$THESIS_ROOT/tools/live/write_live_run_metadata.py" \
        --output "$output_path" \
        --run-id "$RUN_ID" \
        --scenario-tag "${BAG_TAG:-}" \
        --command "$ORIGINAL_INVOCATION" \
        --repo-root "$THESIS_ROOT" \
        --ros-distro "${ROS_DISTRO:-}" \
        --bag-kind "$bag_kind" \
        --bag-out-dir "$(dirname "$output_path")" \
        "${recorded_topic_args[@]}" \
        "${hash_args[@]}" \
        "${param_args[@]}" \
        "${switch_log_args[@]}"; then
        echo "[warn] failed to write live-run provenance record: $output_path"
    fi
}

post_target_selection() {
    local target_value="$1"

    python3 - "$target_value" <<'PY'
import json
import sys
import urllib.error
import urllib.request

target_raw = sys.argv[1]

try:
    target = int(target_raw)
except ValueError:
    print(f"[error] invalid target id: {target_raw}")
    sys.exit(2)

payload = json.dumps({"target": target}).encode("utf-8")
request = urllib.request.Request(
    "http://127.0.0.1:8090/api/target",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=2.0) as response:
        body = response.read().decode("utf-8", errors="replace")
        if body:
            print(body)
        else:
            print(f"[ok] target request sent: {target}")
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"[error] target API returned HTTP {exc.code}: {body}")
    sys.exit(1)
except Exception as exc:
    print(f"[error] target API request failed: {exc}")
    sys.exit(1)
PY
}

print_current_track_ids() {
    python3 "$THESIS_ROOT/tools/live/print_track_ids.py" --timeout 4.0
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
if [[ "$ENABLE_ROSBAG" -eq 1 ]]; then rosbag_state="video"; fi
if [[ "${FIELD_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then rosbag_state="${rosbag_state}+raw"; fi
if [[ "$ENABLE_DATASET_BAG" -eq 1 ]]; then
    if [[ "$rosbag_state" == "off" ]]; then
        rosbag_state="dataset"
    else
        rosbag_state="${rosbag_state}+dataset"
    fi
fi

# Phase 1: host preflight + camera stream sanity checks.
log_info "run: $RUN_ID"
log_info "logs: $RUN_DIR"
log_info "mode: perception=$PERCEPTION_MODE"
log_info "cfg: camera_capture=${CAMERA_WIDTH}x${CAMERA_HEIGHT} camera_publish=${CAMERA_PUBLISH_WIDTH}x${CAMERA_PUBLISH_HEIGHT}(${CAMERA_PUBLISH_RESIZE_MODE},${CAMERA_PUBLISH_ENCODING})@${CAMERA_FPS} detector_model=${PERCEPTION_DETECTOR_MODEL} detector_hef=${PERCEPTION_HAILO_HEF_PATH} infer=q${INFER_QUEUE_SIZE}/w${INFER_WORKERS}/t${INFER_TIMEOUT_MS}ms/retries=${INFER_RETRIES} img_qos_depth=${PERCEPTION_IMAGE_QOS_DEPTH} hailo_queue_buffers=${PERCEPTION_HAILO_QUEUE_BUFFERS} async_max_inflight=${PERCEPTION_ASYNC_MAX_INFLIGHT} hailo_videoconvert=${PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL} perception_gc_disable=${PERCEPTION_GC_DISABLE_BOOL} allow_stub_fallback=${PERCEPTION_ALLOW_STUB_FALLBACK_BOOL} control_stale=${CONTROL_STALE_TIMEOUT_S}s"
log_info "cfg: camera_trigger_control=${CAMERA_APPLY_TRIGGER_CONTROL_BOOL} camera_rate_controls=${CAMERA_APPLY_RATE_CONTROLS_BOOL} preflight_stream_probe=${CAMERA_PREFLIGHT_STREAM_PROBE_BOOL} sensor_max_fps=${CAMERA_SENSOR_MAX_FPS} ae_upper=${CAMERA_SENSOR_AE_UPPER} ae_max=${CAMERA_SENSOR_AE_MAX} exposure_mode=${CAMERA_SENSOR_EXPOSURE_MODE}"
log_info "nodes: tracker=$tracker_state control=$control_state dashboard=$dashboard_state web_video=$web_video_state rosbag=$rosbag_state"
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    if [[ "$TRACKER_TYPE" == "deepsort" ]]; then
        log_info "tracker: type=$TRACKER_TYPE tracks=$TRACKER_PUBLISH_TRACKS_BOOL tracks_require_subscribers=$TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL timing_topic=$TRACKER_PUBLISH_TIMING_BOOL profile=$TRACKER_PROFILE_ENABLED gc_probe=$TRACKER_PROFILE_GC_PROBE max_age=$TRACKER_MAX_AGE min_hits=$TRACKER_MIN_HITS reid_model=$REID_MODEL_PATH"
    else
        log_info "tracker: type=$TRACKER_TYPE tracks=$TRACKER_PUBLISH_TRACKS_BOOL tracks_require_subscribers=$TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL timing_topic=$TRACKER_PUBLISH_TIMING_BOOL profile=$TRACKER_PROFILE_ENABLED gc_probe=$TRACKER_PROFILE_GC_PROBE iou=$TRACKER_IOU_THRESHOLD max_age=$TRACKER_MAX_AGE min_hits=$TRACKER_MIN_HITS centre_gate=$TRACKER_CENTRE_GATE"
    fi
fi
log_step "preflight checks"
if [[ "${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then
    ensure_recording_storage_available \
        "${SOURCE_RECORD_ROOT:-$THESIS_ROOT/bags/source_video}" \
        "$RAW_RECORDING_MIN_FREE_GIB" || exit 1
fi
if [[ "${FIELD_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then
    ensure_recording_storage_available \
        "$BAG_OUT_ROOT" \
        "$RAW_RECORDING_MIN_FREE_GIB" || exit 1
elif [[ "$ENABLE_ROSBAG" -eq 1 ]]; then
    ensure_recording_storage_available \
        "$BAG_OUT_ROOT" \
        "$RECORDING_MIN_FREE_GIB" || exit 1
fi
if [[ "$ENABLE_DATASET_BAG" -eq 1 ]]; then
    ensure_recording_storage_available \
        "$DATASET_BAG_OUT_ROOT" \
        "$RECORDING_MIN_FREE_GIB" || exit 1
fi
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

# Phase 3: integrated camera + perception readiness.
log_step "integrated camera perception mode selected"
log_info "integrated mode will run perception_camera_node only"
if [[ "$CAMERA_PUBLISH_IMAGE_RAW_BOOL" == "true" ]]; then
    log_info "full-rate /camera/image_raw publishing is ENABLED (a raw-image recording flag is active or was explicitly requested)"
else
    log_info "full-rate /camera/image_raw publishing is disabled (no active recording path requires it)"
fi

if [[ "$PERCEPTION_ALLOW_STUB_FALLBACK_BOOL" == "true" ]]; then
    log_hint "host Hailo init failures will fallback to stub backend (override enabled)"
else
    log_hint "host Hailo init failures are fail-fast by default; use --perception-allow-stub-fallback to override"
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

# Keep ROS runtime on host Python, but expose required packages for integrated Hailo mode:
# - system dist-packages for gi/Gst
# - project thesis_env site-packages for hailort/tappas Python bindings
PERCEPTION_PYTHONPATH="/usr/lib/python3/dist-packages"
PERCEPTION_VENV_SITE_PACKAGES=""
if [[ -d "$THESIS_ROOT/thesis_env/lib" ]]; then
    PERCEPTION_VENV_SITE_PACKAGES="$(find "$THESIS_ROOT/thesis_env/lib" -maxdepth 2 -type d -name site-packages | head -n 1 || true)"
    if [[ -n "${PERCEPTION_VENV_SITE_PACKAGES:-}" ]]; then
        PERCEPTION_PYTHONPATH="${PERCEPTION_VENV_SITE_PACKAGES}:$PERCEPTION_PYTHONPATH"
    fi
fi
if [[ -n "${PYTHONPATH:-}" ]]; then
    PERCEPTION_PYTHONPATH="${PERCEPTION_PYTHONPATH}:$PYTHONPATH"
fi

# Optional local TAPPAS runtime shim (no root install required).
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
    log_info "integrated-camera: using local postprocess lib at $PERCEPTION_RUNTIME_POST_SO"
fi

camera_retry_applied=0


while true; do
    start_ros_bg perception_camera env PYTHONPATH="$PERCEPTION_PYTHONPATH" LD_LIBRARY_PATH="$PERCEPTION_LD_LIBRARY_PATH" GST_PLUGIN_PATH="$PERCEPTION_GST_PLUGIN_PATH" ros2 run thesis_bringup perception_camera_node --ros-args \
        -p width:=$CAMERA_WIDTH \
        -p height:=$CAMERA_HEIGHT \
        -p fps:=$CAMERA_FPS \
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
        -p hailo_hef_path:="$PERCEPTION_HAILO_HEF_PATH" \
        -p allow_stub_fallback:=$PERCEPTION_ALLOW_STUB_FALLBACK_BOOL \
        "${PERCEPTION_POST_SO_ARGS[@]}" \
        -p infer_timeout_ms:=$INFER_TIMEOUT_MS \
        -p timeout_log_every:=$INFER_TIMEOUT_LOG_EVERY \
        -p publish_timing:=$INFER_PUBLISH_TIMING_BOOL \
        -p log_every:=$INFER_PRINT_EVERY \
        -p publish_dashboard_topic:=true \
        -p dashboard_topic:=/camera/dashboard \
        -p dashboard_fps:=$CAMERA_DASHBOARD_FPS \
        -p publish_image_raw:=$CAMERA_PUBLISH_IMAGE_RAW_BOOL \
        -p publish_fps_topic:=true \
        -p fps_topic:=/camera/fps \
        -p startup_frame_timeout_s:=$CAMERA_STARTUP_FRAME_TIMEOUT_S \
        -p stall_timeout_s:=$CAMERA_STALL_TIMEOUT_S

    sleep 2

    if check_proc_alive perception_camera; then
        break
    fi

    echo "[error] integrated perception camera exited during startup; see $RUN_DIR/perception_camera.log"

    if [[ "$camera_retry_applied" -eq 0 ]] && grep -Eqi "sensor control|i2c|timeout|context invalid|read failed|startup/read timeout" "$RUN_DIR/perception_camera.log" 2>/dev/null; then
        echo "[warn] retrying integrated camera once in safe mode (640x480, rate controls off)"
        CAMERA_WIDTH=640
        CAMERA_HEIGHT=480
        CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
        camera_retry_applied=1
        stop_proc perception_camera || true
        continue
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
    stop_stack
    exit 1
done

# Snapshot of the exact resolved parameters used for the successful
# perception_camera_node launch above, for Issue #54 run-metadata capture.
PERCEPTION_CAMERA_RESOLVED_PARAMS=(
    "width=$CAMERA_WIDTH"
    "height=$CAMERA_HEIGHT"
    "fps=$CAMERA_FPS"
    "img_w=640"
    "img_h=640"
    "frame_queue_size=$INFER_QUEUE_SIZE"
    "num_workers=$INFER_WORKERS"
    "image_qos_depth=$PERCEPTION_IMAGE_QOS_DEPTH"
    "hailo_queue_max_buffers=$PERCEPTION_HAILO_QUEUE_BUFFERS"
    "async_max_inflight=$PERCEPTION_ASYNC_MAX_INFLIGHT"
    "hailo_use_videoconvert=$PERCEPTION_HAILO_USE_VIDEOCONVERT_BOOL"
    "disable_python_gc=$PERCEPTION_GC_DISABLE_BOOL"
    "label=person"
    "min_score=0.35"
    "inference_backend=$PERCEPTION_INFERENCE_BACKEND"
    "hailo_hef_path=$PERCEPTION_HAILO_HEF_PATH"
    "allow_stub_fallback=$PERCEPTION_ALLOW_STUB_FALLBACK_BOOL"
    "infer_timeout_ms=$INFER_TIMEOUT_MS"
    "timeout_log_every=$INFER_TIMEOUT_LOG_EVERY"
    "publish_timing=$INFER_PUBLISH_TIMING_BOOL"
    "log_every=$INFER_PRINT_EVERY"
    "publish_dashboard_topic=true"
    "dashboard_topic=/camera/dashboard"
    "dashboard_fps=$CAMERA_DASHBOARD_FPS"
    "publish_image_raw=$CAMERA_PUBLISH_IMAGE_RAW_BOOL"
    "publish_fps_topic=true"
    "fps_topic=/camera/fps"
    "startup_frame_timeout_s=$CAMERA_STARTUP_FRAME_TIMEOUT_S"
    "stall_timeout_s=$CAMERA_STALL_TIMEOUT_S"
)

# Phase 4: bring up downstream nodes after camera + perception are healthy.
if [[ "$ENABLE_TRACKER" -eq 1 ]]; then
    TRACKER_PYTHONPATH="${PYTHONPATH:-}"
    TRACKER_VENV_SITE_PACKAGES=""

    if [[ -d "$THESIS_ROOT/thesis_env/lib" ]]; then
        TRACKER_VENV_SITE_PACKAGES="$(
            find "$THESIS_ROOT/thesis_env/lib" -maxdepth 2 -type d -name site-packages | head -n 1 || true
        )"

        if [[ -n "${TRACKER_VENV_SITE_PACKAGES:-}" ]]; then
            if [[ -n "$TRACKER_PYTHONPATH" ]]; then
                TRACKER_PYTHONPATH="${TRACKER_VENV_SITE_PACKAGES}:$TRACKER_PYTHONPATH"
            else
                TRACKER_PYTHONPATH="$TRACKER_VENV_SITE_PACKAGES"
            fi
        fi
    fi

    start_ros_bg tracker env PYTHONPATH="$TRACKER_PYTHONPATH" ros2 run thesis_tracker tracker_node --ros-args \
        -p tracker_type:=$TRACKER_TYPE \
        -p reid_model_path:="$REID_MODEL_PATH" \
        -p reid_batch_size:=32 \
        -p max_cosine_distance:=0.2 \
        -p max_iou_distance:=0.7 \
        -p nn_budget:=100 \
        -p only_position_gating:=false \
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

    TRACKER_RESOLVED_PARAMS=(
        "tracker_type=$TRACKER_TYPE"
        "reid_model_path=$REID_MODEL_PATH"
        "reid_batch_size=32"
        "max_cosine_distance=0.2"
        "max_iou_distance=0.7"
        "nn_budget=100"
        "only_position_gating=false"
        "iou_threshold=$TRACKER_IOU_THRESHOLD"
        "max_age=$TRACKER_MAX_AGE"
        "min_hits=$TRACKER_MIN_HITS"
        "centre_gate=$TRACKER_CENTRE_GATE"
        "publish_tracks=$TRACKER_PUBLISH_TRACKS_BOOL"
        "publish_tracks_requires_subscribers=$TRACKER_PUBLISH_TRACKS_REQUIRES_SUBSCRIBERS_BOOL"
        "publish_timing_topic=$TRACKER_PUBLISH_TIMING_BOOL"
    )
fi

if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then
    DASHBOARD_RUNTIME_RECONFIGURATION_BOOL="false"

    start_ros_bg dashboard_bridge ros2 run thesis_bringup dashboard_bridge_node --ros-args \
        -p ws_host:="$DASHBOARD_BRIDGE_BIND_HOST" \
        -p api_host:="$DASHBOARD_BRIDGE_BIND_HOST" \
        -p allowed_origins:="$DASHBOARD_BRIDGE_ALLOWED_ORIGINS" \
        -p publish_hz:="$DASHBOARD_BRIDGE_PUBLISH_HZ" \
        -p img_w:=640 \
        -p img_h:=640 \
        -p camera_ref_w:=$CAMERA_WIDTH \
        -p camera_ref_h:=$CAMERA_HEIGHT \
        -p runtime_reconfiguration_enabled:=$DASHBOARD_RUNTIME_RECONFIGURATION_BOOL \
        -p target_authority_event_log_path:="$TARGET_AUTHORITY_EVENT_LOG" \
        -p validated_target_topic:=/target_memory_mars \
        -p target_select_topic:=/target_memory_mars/select \
        -p target_clear_topic:=/target_memory_mars/clear
    sleep 1
    if ! check_proc_alive dashboard_bridge; then
        stop_stack
        exit 1
    fi
    DASHBOARD_READY_HOST="$DASHBOARD_BRIDGE_BIND_HOST"
    if [[ "$DASHBOARD_READY_HOST" == "0.0.0.0" || "$DASHBOARD_READY_HOST" == "::" ]]; then
        DASHBOARD_READY_HOST="127.0.0.1"
    fi

    if ! wait_for_port "$DASHBOARD_READY_HOST" 8765 15 1; then
        stop_stack
        exit 1
    fi

    DASHBOARD_BRIDGE_RESOLVED_PARAMS=(
        "ws_host=$DASHBOARD_BRIDGE_BIND_HOST"
        "api_host=$DASHBOARD_BRIDGE_BIND_HOST"
        "allowed_origins=$DASHBOARD_BRIDGE_ALLOWED_ORIGINS"
        "publish_hz=$DASHBOARD_BRIDGE_PUBLISH_HZ"
        "img_w=640"
        "img_h=640"
        "camera_ref_w=$CAMERA_WIDTH"
        "camera_ref_h=$CAMERA_HEIGHT"
        "runtime_reconfiguration_enabled=$DASHBOARD_RUNTIME_RECONFIGURATION_BOOL"
        "validated_target_topic=/target_memory_mars"
        "target_select_topic=/target_memory_mars/select"
        "target_clear_topic=/target_memory_mars/clear"
    )

    if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then
        if [[ ! -f "$TARGET_MEMORY_MARS_CONFIG" ]]; then
            echo "[error] canonical TIM-MARS config not found: $TARGET_MEMORY_MARS_CONFIG"
            stop_stack
            exit 1
        fi

        start_ros_bg target_memory_mars ros2 run thesis_bringup target_memory_mars_node --ros-args \
            --params-file "$TARGET_MEMORY_MARS_CONFIG" \
            -p target_topic:=/target_memory_mars \
            -p status_topic:=/target_memory_mars/status \
            -p select_topic:=/target_memory_mars/select \
            -p image_width:=${CAMERA_WIDTH}.0 \
            -p image_height:=${CAMERA_HEIGHT}.0 \
            -p appearance_enabled:="$TARGET_MEMORY_APPEARANCE_BOOL" \
            -p appearance_image_topic:="$TARGET_MEMORY_MARS_IMAGE_TOPIC" \
            -p mars_model_path:="$TARGET_MEMORY_MARS_MODEL_PATH"
        sleep 1
        if ! check_proc_alive target_memory_mars; then
            stop_stack
            exit 1
        fi
    fi

    if [[ "$ENABLE_WEB_VIDEO" -eq 1 ]]; then
        start_ros_bg web_video ros2 run web_video_server web_video_server --ros-args \
            -p address:="$WEB_VIDEO_BIND_HOST" \
            -p port:=8080
        sleep 1
        if ! check_proc_alive web_video; then
            stop_stack
            exit 1
        fi
        WEB_VIDEO_READY_HOST="$WEB_VIDEO_BIND_HOST"
        if [[ "$WEB_VIDEO_READY_HOST" == "0.0.0.0" || "$WEB_VIDEO_READY_HOST" == "::" ]]; then
            WEB_VIDEO_READY_HOST="127.0.0.1"
        fi

        if ! wait_for_port "$WEB_VIDEO_READY_HOST" 8080 15 1; then
            stop_stack
            exit 1
        fi
    fi
fi

if [[ "$ENABLE_CONTROL" -eq 1 ]]; then
    start_ros_bg control ros2 run thesis_bringup control_ref_node --ros-args \
        -p target_topic:=/target_memory_mars \
        -p status_topic:=/target_memory_mars/status \
        -p enable_yaw_recovery:=false \
        -p img_w:=${CAMERA_WIDTH}.0 \
        -p img_h:=${CAMERA_HEIGHT}.0 \
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

# Start MAVROS telemetry when --record-mavros is enabled.
# This keeps --record-mavros self-contained:
# launch MAVROS, wait for FCU connection, request streams, then start bag recording.
if [[ "$RECORD_MAVROS" -eq 1 ]]; then
    MAVROS_START_TS="$(date +%s)"

    mavros_elapsed() {
        local now
        now="$(date +%s)"
        printf "%02ds" "$((now - MAVROS_START_TS))"
    }

    mavros_log() {
        local level="$1"
        shift
        echo "[$level] [mavros $(mavros_elapsed)] $*"
    }

    MAVROS_FCU_URL="${MAVROS_FCU_URL:-udp://:14550@}"
    MAVROS_TGT_SYSTEM="${MAVROS_TGT_SYSTEM:-9}"
    MAVROS_TGT_COMPONENT="${MAVROS_TGT_COMPONENT:-1}"
    MAVROS_STREAM_RATE="${MAVROS_STREAM_RATE:-50}"

    mavros_log info "--record-mavros enabled: starting MAVROS telemetry"
    mavros_log info "config: fcu_url=${MAVROS_FCU_URL} target=${MAVROS_TGT_SYSTEM}.${MAVROS_TGT_COMPONENT} stream_rate=${MAVROS_STREAM_RATE}Hz"

    if timeout 3 ros2 topic echo /mavros/state --once 2>/dev/null | grep -q "connected: true"; then
        mavros_log ok "MAVROS already connected"
    else
        mavros_log info "launching MAVROS node"
        start_ros_bg mavros ros2 launch mavros apm.launch \
            fcu_url:="$MAVROS_FCU_URL" \
            tgt_system:="$MAVROS_TGT_SYSTEM" \
            tgt_component:="$MAVROS_TGT_COMPONENT"

        mavros_log info "waiting for MAVROS connection on /mavros/state, timeout 60s"
        MAVROS_CONNECTED=0

        for i in {1..60}; do
            if timeout 3 ros2 topic echo /mavros/state --once 2>/dev/null | grep -q "connected: true"; then
                MAVROS_CONNECTED=1
                break
            fi

            if (( i % 5 == 0 )); then
                mavros_log info "still waiting for MAVROS connection, ${i}/60s"
            fi

            sleep 1
        done

        if [[ "$MAVROS_CONNECTED" -ne 1 ]]; then
            mavros_log error "MAVROS did not report connected: true on /mavros/state"
            stop_stack
            exit 1
        fi

        mavros_log ok "MAVROS connected"
    fi

    mavros_log info "waiting for /mavros/set_stream_rate service, timeout 10s"
    MAVROS_STREAM_SERVICE_READY=0

    for i in {1..20}; do
        if ros2 service list 2>/dev/null | grep -qx "/mavros/set_stream_rate"; then
            MAVROS_STREAM_SERVICE_READY=1
            break
        fi

        if (( i % 5 == 0 )); then
            mavros_log info "still waiting for stream-rate service, attempt ${i}/20"
        fi

        sleep 0.5
    done

    if [[ "$MAVROS_STREAM_SERVICE_READY" -ne 1 ]]; then
        mavros_log error "/mavros/set_stream_rate service not available"
        stop_stack
        exit 1
    fi

    mavros_log ok "stream-rate service available"
    mavros_log info "requesting MAVROS streams at ${MAVROS_STREAM_RATE} Hz"

    if ! ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
        "{stream_id: 0, message_rate: ${MAVROS_STREAM_RATE}, on_off: true}"; then
        mavros_log error "failed to request MAVROS stream rate"
        stop_stack
        exit 1
    fi

    mavros_log info "checking /mavros/imu/data_raw, timeout 10s"
    MAVROS_IMU_READY=0

    for i in {1..20}; do
        if timeout 2 ros2 topic echo /mavros/imu/data_raw --once 2>/dev/null | grep -q "header:"; then
            MAVROS_IMU_READY=1
            break
        fi

        if (( i % 5 == 0 )); then
            mavros_log info "still waiting for raw IMU sample, attempt ${i}/20"
        fi

        sleep 0.5
    done

    if [[ "$MAVROS_IMU_READY" -ne 1 ]]; then
        mavros_log warn "/mavros/imu/data_raw did not publish during startup check"
        mavros_log warn "bag recording will still include MAVROS topics, but IMU stream may be missing"
    else
        mavros_log ok "MAVROS raw IMU stream detected"
    fi

    mavros_log ok "MAVROS telemetry setup finished"
fi

if [[ "$ENABLE_ROSBAG" -eq 1 ]]; then
    mkdir -p "$BAG_OUT_ROOT"

    BAG_TAG_SAFE=""
    if [[ -n "${BAG_TAG:-}" ]]; then
        BAG_TAG_SAFE="$(make_safe_name "$BAG_TAG")"
    fi

    if [[ -n "$BAG_TAG_SAFE" ]]; then
        VIDEO_BAG_NAME="${RUN_ID}__video__${BAG_TAG_SAFE}"
    else
        VIDEO_BAG_NAME="${RUN_ID}__video"
    fi

    VIDEO_BAG_OUT_DIR="$BAG_OUT_ROOT/$VIDEO_BAG_NAME"

    VIDEO_BAG_TOPICS=(
        /camera/dashboard
        /camera/fps
        /detections
        /tracks
        /target
    )

    if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then
        VIDEO_BAG_TOPICS+=(
            /target_memory_mars
            /target_memory_mars/status
        )
    fi

    VIDEO_BAG_TOPICS+=(
        /timing
        /timing_tracker
        /timing_target
        /control_ref/cmd_vel
    )

    if [[ "$RECORD_MAVROS" -eq 1 ]]; then
        VIDEO_BAG_TOPICS+=(
            /mavros/state
            /mavros/extended_state
            /mavros/imu/data_raw
            /mavros/imu/data
            /mavros/imu/mag
            /mavros/imu/static_pressure
            /mavros/imu/temperature_imu
            /mavros/rc/in
            /mavros/rc/out
            /mavros/battery
            /mavros/global_position/global
            /mavros/global_position/rel_alt
            /mavros/global_position/local
            /mavros/local_position/pose
            /mavros/local_position/velocity_local
            /mavros/setpoint_velocity/cmd_vel
        )
    fi

    echo "[ok] video bag recording enabled"
    echo "[ok] video bag output: $VIDEO_BAG_OUT_DIR"
    echo "[ok] video bag topics:"
    for topic in "${VIDEO_BAG_TOPICS[@]}"; do
        echo "     $topic"
    done

    export RMW_FASTRTPS_USE_SHM=0

    QOS_OVERRIDE_FILE="/etc/thesis/live_record_qos_overrides.yaml"

    if [[ -f "$QOS_OVERRIDE_FILE" ]]; then
        start_ros_bg rosbag ros2 bag record \
            --storage mcap \
            --qos-profile-overrides-path "$QOS_OVERRIDE_FILE" \
            -o "$VIDEO_BAG_OUT_DIR" \
            "${VIDEO_BAG_TOPICS[@]}"
    else
        start_ros_bg rosbag ros2 bag record \
            --storage mcap \
            -o "$VIDEO_BAG_OUT_DIR" \
            "${VIDEO_BAG_TOPICS[@]}"
    fi

    sleep 1
    if ! check_proc_alive rosbag; then
        stop_stack
        exit 1
    fi

    for _ in {1..20}; do
        if [[ -d "$VIDEO_BAG_OUT_DIR" ]]; then
            break
        fi
        sleep 0.1
    done

    if [[ -d "$VIDEO_BAG_OUT_DIR" ]]; then
        write_video_bag_metadata "$VIDEO_BAG_OUT_DIR/flight_metadata.txt" "${VIDEO_BAG_TOPICS[@]}"
        echo "[ok] video bag metadata: $VIDEO_BAG_OUT_DIR/flight_metadata.txt"
        write_live_run_provenance video "$VIDEO_BAG_OUT_DIR/run_metadata.json" "${VIDEO_BAG_TOPICS[@]}"
    else
        echo "[warn] video bag output directory not visible yet; metadata was not written"
    fi
fi


if [[ "$ENABLE_DATASET_BAG" -eq 1 ]]; then
    mkdir -p "$DATASET_BAG_OUT_ROOT"

    BAG_TAG_SAFE=""
    if [[ -n "${BAG_TAG:-}" ]]; then
        BAG_TAG_SAFE="$(make_safe_name "$BAG_TAG")"
    fi

    if [[ -n "$BAG_TAG_SAFE" ]]; then
        DATASET_BAG_NAME="${RUN_ID}__dataset__${BAG_TAG_SAFE}"
    else
        DATASET_BAG_NAME="${RUN_ID}__dataset"
    fi

    DATASET_BAG_OUT_DIR="$DATASET_BAG_OUT_ROOT/$DATASET_BAG_NAME"

    DATASET_BAG_TOPICS=(
        /camera/image_raw
        /camera/fps
        /detections
        /tracks
        /target
        /timing
        /timing_tracker
        /timing_target
    )

    if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then
        DATASET_BAG_TOPICS+=(
            /target_memory_mars
            /target_memory_mars/status
        )
    fi

    echo "[ok] dataset bag recording enabled"
    echo "[ok] dataset bag output: $DATASET_BAG_OUT_DIR"
    echo "[ok] dataset bag topics:"
    for topic in "${DATASET_BAG_TOPICS[@]}"; do
        echo "     $topic"
    done

    export RMW_FASTRTPS_USE_SHM=0

    start_ros_bg dataset_rosbag ros2 bag record \
        --storage mcap \
        -o "$DATASET_BAG_OUT_DIR" \
        "${DATASET_BAG_TOPICS[@]}"

    sleep 1
    if ! check_proc_alive dataset_rosbag; then
        stop_stack
        exit 1
    fi

    for _ in {1..20}; do
        if [[ -d "$DATASET_BAG_OUT_DIR" ]]; then
            break
        fi
        sleep 0.1
    done

    if [[ -d "$DATASET_BAG_OUT_DIR" ]]; then
        write_video_bag_metadata "$DATASET_BAG_OUT_DIR/dataset_metadata.txt" "${DATASET_BAG_TOPICS[@]}"
        write_live_run_provenance dataset "$DATASET_BAG_OUT_DIR/run_metadata.json" "${DATASET_BAG_TOPICS[@]}"
        echo "[ok] dataset bag metadata: $DATASET_BAG_OUT_DIR/dataset_metadata.txt"
    else
        echo "[warn] dataset bag output directory not visible yet; metadata not written"
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

if [[ "${FIELD_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then
    RAW_IMAGE_BAG_OUT_DIR="${VIDEO_BAG_OUT_DIR}__image_raw"
    echo "[raw] starting synchronized raw image recorder: $RAW_IMAGE_BAG_OUT_DIR"

    if [[ -f "$VIDEO_BAG_OUT_DIR/flight_metadata.txt" ]]; then
        echo "raw_image_bag_out_dir=$RAW_IMAGE_BAG_OUT_DIR" >> "$VIDEO_BAG_OUT_DIR/flight_metadata.txt"
    fi

    sleep 3

    if [[ -f "$QOS_OVERRIDE_FILE" ]]; then
        start_ros_bg raw_image_bag ros2 bag record \
            --storage mcap \
            --qos-profile-overrides-path "$QOS_OVERRIDE_FILE" \
            -o "$RAW_IMAGE_BAG_OUT_DIR" \
            --topics /camera/image_raw
    else
        start_ros_bg raw_image_bag ros2 bag record \
            --storage mcap \
            -o "$RAW_IMAGE_BAG_OUT_DIR" \
            --topics /camera/image_raw
    fi

    sleep 1
    if ! check_proc_alive raw_image_bag; then
        echo "[error] raw image recorder failed"
        stop_stack
        exit 1
    fi

    for _ in {1..20}; do
        if [[ -d "$RAW_IMAGE_BAG_OUT_DIR" ]]; then
            break
        fi
        sleep 0.1
    done

    if [[ -d "$RAW_IMAGE_BAG_OUT_DIR" ]]; then
        write_video_bag_metadata "$RAW_IMAGE_BAG_OUT_DIR/raw_image_metadata.txt" /camera/image_raw
        write_live_run_provenance raw_image "$RAW_IMAGE_BAG_OUT_DIR/run_metadata.json" /camera/image_raw
        {
            echo "paired_video_bag=$VIDEO_BAG_OUT_DIR"
            echo "raw_image_expected_rate_hz=$CAMERA_FPS"
        } >> "$RAW_IMAGE_BAG_OUT_DIR/raw_image_metadata.txt"
        echo "[ok] raw image bag metadata: $RAW_IMAGE_BAG_OUT_DIR/raw_image_metadata.txt"
    else
        echo "[warn] raw image bag output directory not visible yet; metadata was not written"
    fi
fi

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

if [[ "${SOURCE_RECORD_MODE:-0}" -eq 1 ]]; then
    SOURCE_ROOT="${SOURCE_RECORD_ROOT:-$THESIS_ROOT/bags/source_video}"
    MAVROS_BAG_ROOT="$THESIS_ROOT/bags/mavros"
    mkdir -p "$SOURCE_ROOT" "$MAVROS_BAG_ROOT"

    echo "[source] source evidence root: $SOURCE_ROOT"

    SOURCE_TAG_SAFE="${BAG_TAG:-source_record}"
    SOURCE_RUN_ID="${RUN_ID:-$(date +%F__%H-%M-%S)}"

    SOURCE_RAW_BAG_SUFFIX="image_raw"
    if [[ "${SOURCE_DETECTIONS_RECORD:-0}" -eq 1 ]]; then
        SOURCE_RAW_BAG_SUFFIX="image_raw_detections"
    fi

    SOURCE_RAW_BAG_OUT_DIR="$SOURCE_ROOT/${SOURCE_RUN_ID}__source__${SOURCE_TAG_SAFE}__${SOURCE_RAW_BAG_SUFFIX}"
    SOURCE_MAVROS_BAG_OUT_DIR="$MAVROS_BAG_ROOT/${SOURCE_RUN_ID}__source__${SOURCE_TAG_SAFE}__mavros"

    if [[ "${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then
        SOURCE_RECORD_TOPICS=(
            /camera/image_raw
        )
        if [[ "${SOURCE_DETECTIONS_RECORD:-0}" -eq 1 ]]; then
            SOURCE_RECORD_TOPICS+=(
                /detections
            )
        fi

        echo "[source] starting source evidence recorder: $SOURCE_RAW_BAG_OUT_DIR"
        sleep 3

        SOURCE_QOS_OVERRIDE_FILE="/etc/thesis/live_record_qos_overrides.yaml"

        SOURCE_ROSBAG_EXTRA_ARGS=()
        if [[ "${SOURCE_DETECTIONS_RECORD:-0}" -eq 1 ]]; then
            # Issue #64 high-bandwidth evidence capture. Keep DDS/image
            # semantics unchanged while reducing recorder-side serialization
            # pressure. 512 MiB is roughly several seconds of HD source data.
            SOURCE_ROSBAG_EXTRA_ARGS+=(
                --storage-preset-profile fastwrite
                --max-cache-size 536870912
            )
        fi

        if [[ -f "$SOURCE_QOS_OVERRIDE_FILE" ]]; then
            start_ros_bg source_raw_image_bag ros2 bag record \
                --storage mcap \
                "${SOURCE_ROSBAG_EXTRA_ARGS[@]}" \
                --qos-profile-overrides-path "$SOURCE_QOS_OVERRIDE_FILE" \
                -o "$SOURCE_RAW_BAG_OUT_DIR" \
                --topics "${SOURCE_RECORD_TOPICS[@]}"
        else
            start_ros_bg source_raw_image_bag ros2 bag record \
                --storage mcap \
                "${SOURCE_ROSBAG_EXTRA_ARGS[@]}" \
                -o "$SOURCE_RAW_BAG_OUT_DIR" \
                --topics "${SOURCE_RECORD_TOPICS[@]}"
        fi

        sleep 1
        if ! check_proc_alive source_raw_image_bag; then
            echo "[error] source raw image recorder failed"
            stop_stack
            exit 1
        fi

        for _ in {1..20}; do
            if [[ -d "$SOURCE_RAW_BAG_OUT_DIR" ]]; then
                break
            fi
            sleep 0.1
        done

        if [[ -d "$SOURCE_RAW_BAG_OUT_DIR" ]]; then
            write_live_run_provenance source "$SOURCE_RAW_BAG_OUT_DIR/run_metadata.json" "${SOURCE_RECORD_TOPICS[@]}"
        else
            echo "[warn] source raw image bag output directory not visible yet; provenance not written"
        fi
    fi

    if [[ "${SOURCE_MAVROS_RECORD:-0}" -eq 1 ]]; then
        echo "[source] enforcing AERONEXT/Pixhawk network mode (Tailscale will stop)"
        sudo "$THESIS_ROOT/tools/host/set_pi_network_mode.sh" pixhawk

        echo "[source] starting MAVROS Pixhawk 6X Ethernet link"
        export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

        start_ros_bg source_mavros_pixhawk bash -lc 'source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" && ros2 launch mavros apm.launch fcu_url:=udp://:14550@ tgt_system:=9 tgt_component:=1'

        sleep 8

        echo "[source] requesting MAVLink streams"
        bash -lc 'source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" && ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate "{stream_id: 0, message_rate: 50, on_off: true}"' || true

        echo "[source] starting MAVROS recorder: $SOURCE_MAVROS_BAG_OUT_DIR"

        start_ros_bg source_mavros_bag bash -lc "source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID=42 && ros2 bag record --storage mcap -o '$SOURCE_MAVROS_BAG_OUT_DIR' --topics /mavros/imu/data_raw /mavros/imu/data /mavros/imu/mag /mavros/imu/static_pressure /mavros/imu/temperature_imu /mavros/rc/in /mavros/rc/out /mavros/battery /mavros/global_position/global /mavros/global_position/rel_alt /mavros/global_position/local /mavros/local_position/pose /mavros/local_position/velocity_local /mavros/state /mavros/extended_state"

        sleep 1
        if ! check_proc_alive source_mavros_bag; then
            echo "[error] source MAVROS recorder failed"
            stop_stack
            exit 1
        fi
    fi
fi

log_info "commands: status | ids | target <id> | clear-target | clear | stop"

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
        ids|tracks)
            print_current_track_ids
            ;;
        target\ *)
            target_id="${cmd#target }"
            target_id="${target_id//[[:space:]]/}"
            if [[ -z "$target_id" ]]; then
                echo "[error] usage: target <track_id>"
            else
                post_target_selection "$target_id"
            fi
            ;;
        clear-target|target-clear)
            post_target_selection 0
            ;;
        *)
            echo "[info] unknown command: $cmd"
            echo "[info] valid commands: status, ids, target <id>, clear-target, clear, stop, quit, exit"
            ;;
    esac
done
