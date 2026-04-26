#!/usr/bin/env bash

parse_and_validate_live_stack_args() {
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
        --camera-trigger-control-off)
            CAMERA_APPLY_TRIGGER_CONTROL_BOOL="false"
            shift
            ;;
        --camera-trigger-control-on)
            CAMERA_APPLY_TRIGGER_CONTROL_BOOL="true"
            shift
            ;;
        --camera-preflight-stream-probe-off)
            CAMERA_PREFLIGHT_STREAM_PROBE_BOOL="false"
            shift
            ;;
        --camera-preflight-stream-probe-on)
            CAMERA_PREFLIGHT_STREAM_PROBE_BOOL="true"
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

}
