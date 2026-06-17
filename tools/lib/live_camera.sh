#!/usr/bin/env bash

# Camera and host-preflight helpers for tools/start_live_stack.sh.
# This file expects the entrypoint to define logging/process helpers and live-stack config vars.

STACK_PROC_PATTERN="camera_bringup.launch.py|inference_client_node|detector_node|perception_camera_node|tracker_node|control_ref_node|dashboard_bridge_node|web_video_server"
CAMERA_MEDIA_DEV_OVERRIDE=""

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

check_stuck_camera_processes() {
    local stuck_lines
    stuck_lines="$(ps -eo pid=,stat=,cmd= | awk '$2 ~ /^D/ && $0 ~ /(v4l2-ctl|media-ctl)/ {print}' || true)"

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
        topology="$(timeout 5s media-ctl -d "$media_dev" -p 2>/dev/null || true)"
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

    topology="$(timeout 5s media-ctl -d "$media_dev" -p 2>/dev/null || true)"
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

    if configure_camera_stream_path "$media_dev" "$sensor_entity" "$CAMERA_WIDTH" "$CAMERA_HEIGHT"; then
        if [[ "$CAMERA_PREFLIGHT_STREAM_PROBE_BOOL" != "true" ]]; then
            log_ok "camera media preflight passed at ${CAMERA_WIDTH}x${CAMERA_HEIGHT}"
            return 0
        fi
        if probe_camera_stream_once "$CAMERA_WIDTH" "$CAMERA_HEIGHT"; then
            log_ok "camera stream preflight passed at ${CAMERA_WIDTH}x${CAMERA_HEIGHT}"
            return 0
        fi
        if ! check_stuck_camera_processes; then
            return 1
        fi
    fi

    if [[ "$CAMERA_PREFLIGHT_STREAM_PROBE_BOOL" != "true" ]]; then
        if configure_camera_stream_path "$media_dev" "$sensor_entity" 640 480; then
            echo "[warn] camera media preflight failed at ${CAMERA_WIDTH}x${CAMERA_HEIGHT}; falling back to 640x480"
            CAMERA_WIDTH=640
            CAMERA_HEIGHT=480
            if [[ "$CAMERA_PUBLISH_SHAPE_EXPLICIT" -eq 0 ]]; then
                CAMERA_PUBLISH_WIDTH=640
                CAMERA_PUBLISH_HEIGHT=480
            fi
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
            log_ok "camera media preflight passed at 640x480"
            return 0
        fi
        echo "[error] camera media preflight failed on $media_dev"
        log_hint "startup did not run an active /dev/video0 stream probe; use --camera-preflight-stream-probe-on for deeper diagnostics"
        return 1
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
        if ! check_stuck_camera_processes; then
            return 1
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

    topology="$(timeout 5s media-ctl -d "$media_dev" -p 2>/dev/null || true)"
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

    if timeout 5s media-ctl -d "$media_dev" -l '"csi2":4 -> "rp1-cfe-csi2_ch0":0 [1]' >/dev/null 2>&1; then
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
    CAMERA_ARGS+=("apply_sensor_trigger_control:=$CAMERA_APPLY_TRIGGER_CONTROL_BOOL")
    CAMERA_ARGS+=("apply_sensor_rate_controls:=$CAMERA_APPLY_RATE_CONTROLS_BOOL")
    CAMERA_ARGS+=("sensor_max_fps:=$CAMERA_SENSOR_MAX_FPS")
    CAMERA_ARGS+=("sensor_ae_exposure_upper:=$CAMERA_SENSOR_AE_UPPER")
    CAMERA_ARGS+=("sensor_ae_exposure_max:=$CAMERA_SENSOR_AE_MAX")
    CAMERA_ARGS+=("sensor_exposure_mode:=$CAMERA_SENSOR_EXPOSURE_MODE")
    CAMERA_ARGS+=("sensor_manual_exposure:=$CAMERA_SENSOR_MANUAL_EXPOSURE")
    CAMERA_ARGS+=("startup_frame_timeout_s:=$CAMERA_STARTUP_FRAME_TIMEOUT_S")
    CAMERA_ARGS+=("stall_timeout_s:=$CAMERA_STALL_TIMEOUT_S")
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
    if ! wait_for_topic_message /detections 20 1 sensor_data best_effort volatile; then
        if ! check_proc_alive camera; then
            return 2
        fi
        if wait_for_topic_message /detections 8 0; then
            echo "[warn] /detections readiness probe timed out, but /detections is active; continuing"
            return 0
        fi
        if camera_log_has_frame_activity; then
            echo "[warn] /detections readiness probe timed out, but integrated perception log shows active detection pipeline; continuing"
            return 0
        fi
        if camera_log_has_fatal_error; then
            return 3
        fi
        return 4
    fi
    return 0
}
