#!/usr/bin/env bash

TRACKER_TYPE="ocsort"
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
CAMERA_APPLY_TRIGGER_CONTROL_BOOL="false"
CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
CAMERA_PREFLIGHT_STREAM_PROBE_BOOL="false"
CAMERA_STARTUP_FRAME_TIMEOUT_S=20.0
CAMERA_STALL_TIMEOUT_S=4.0
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
# Video bag recording, disabled by default.
# Enabled with: --record-video
ENABLE_ROSBAG=0
BAG_TAG=""
BAG_OUT_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}/bags/live_camera"
RECORD_MAVROS=0

apply_startup_profile() {
    local profile="$1"
    case "$profile" in
        daily)
            CAMERA_WIDTH=1280
            CAMERA_HEIGHT=720
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
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
            CAMERA_APPLY_RATE_CONTROLS_BOOL="false"
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
