#!/usr/bin/env bash

# Purpose:
# - Replay a source bag from image_raw.
# - Rerun detector, tracker, and optionally TIM-MARS.
# - Record a full-pipeline replay bag for diagnostic comparison.
#
# Use this only when regenerated tracker IDs and annotations are compatible.
# It is heavier and less annotation-stable than memory-only replay.
#
if [[ $# -lt 5 ]]; then
  echo "Usage:"
  echo "  $0 <bag_path> <detector_model> <target_id|largest> <tracker> <tim_mode:off|mars> [rate] [target_wait_timeout_s]"
  echo
  echo "Example:"
  echo "  $0 bags/datasets/... yolov8s largest bytetrack mars 0.5 90"
  exit 1
fi

BAG_PATH="$1"
DETECTOR_MODEL="$2"
TARGET_ID="$3"
TRACKER="$4"
TIM_MODE="$5"
RATE="${6:-0.5}"
TARGET_WAIT_TIMEOUT="${7:-90}"
RECORDER_STOP_TIMEOUT="${RECORDER_STOP_TIMEOUT:-120}"

printf -v RUN_COMMAND '%q ' "$0" "$@"
RUN_COMMAND="${RUN_COMMAND% }"

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

if [[ ! -d "$THESIS_ROOT" ]]; then
  echo "[error] thesis root not found: $THESIS_ROOT" >&2
  exit 14
fi

if [[ ! -e "$BAG_PATH" ]]; then
  echo "[error] input bag not found: $BAG_PATH" >&2
  exit 14
fi

if ! BAG_PATH="$(realpath "$BAG_PATH")"; then
  echo "[error] failed to resolve input bag path: $BAG_PATH" >&2
  exit 14
fi

BAG_BASE="$(basename "$BAG_PATH")"
HEF_PATH="$THESIS_ROOT/models/hef/${DETECTOR_MODEL}.hef"

RUN_NAME="${BAG_BASE}__detector_${DETECTOR_MODEL}__tracker_${TRACKER}__tim_${TIM_MODE}__target_${TARGET_ID}"
OUT_ROOT="${OUT_ROOT:-$THESIS_ROOT/bags/replay/full_pipeline_from_image_raw}"
REPORT_ROOT="${REPORT_ROOT:-$THESIS_ROOT/reports/full_pipeline_from_image_raw}"
LOG_ROOT="${LOG_ROOT:-$THESIS_ROOT/ros2_ws/log/full_pipeline_from_image_raw}"
OUT_BAG="$OUT_ROOT/$RUN_NAME"
REPORT_DIR="$REPORT_ROOT/$RUN_NAME"
LOG_DIR="$LOG_ROOT/$RUN_NAME"

if [[ ! -f "$HEF_PATH" ]]; then
  echo "[error] detector HEF not found: $HEF_PATH"
  exit 2
fi

if [[ "$TIM_MODE" != "off" && "$TIM_MODE" != "mars" ]]; then
  echo "[error] tim_mode must be one of: off, mars"
  exit 3
fi

RUN_TIM_MARS=false
if [[ "$TIM_MODE" == "mars" ]]; then
  RUN_TIM_MARS=true
fi

RUN_CONTROLLER="${RUN_CONTROLLER:-false}"
CONTROL_ENABLE_YAW_RECOVERY="${CONTROL_ENABLE_YAW_RECOVERY:-false}"
CONTROL_STALE_TIMEOUT_S="${CONTROL_STALE_TIMEOUT_S:-0.20}"

case "${RUN_CONTROLLER,,}" in
  true|false)
    ;;
  *)
    echo "[error] RUN_CONTROLLER must be true or false" >&2
    exit 3
    ;;
esac

case "${CONTROL_ENABLE_YAW_RECOVERY,,}" in
  true|false)
    ;;
  *)
    echo "[error] CONTROL_ENABLE_YAW_RECOVERY must be true or false" >&2
    exit 3
    ;;
esac

if [[ "${RUN_CONTROLLER,,}" == "true" && "$RUN_TIM_MARS" != "true" ]]; then
  echo "[error] RUN_CONTROLLER=true requires tim_mode=mars" >&2
  exit 3
fi

if [[ "${CONTROL_ENABLE_YAW_RECOVERY,,}" == "true" && "${RUN_CONTROLLER,,}" != "true" ]]; then
  echo "[error] CONTROL_ENABLE_YAW_RECOVERY=true requires RUN_CONTROLLER=true" >&2
  exit 3
fi

if ! mkdir -p "$LOG_DIR" "$OUT_ROOT" "$REPORT_ROOT"; then
  echo "[error] failed to create replay output directories" >&2
  exit 15
fi

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "[error] ROS 2 Jazzy setup not found: /opt/ros/jazzy/setup.bash" >&2
  exit 16
fi

if ! source /opt/ros/jazzy/setup.bash; then
  echo "[error] failed to source ROS 2 Jazzy environment" >&2
  exit 16
fi

if [[ ! -f "$THESIS_ROOT/ros2_ws/install/setup.bash" ]]; then
  echo "[error] thesis ROS workspace setup not found" >&2
  exit 16
fi

if ! source "$THESIS_ROOT/ros2_ws/install/setup.bash"; then
  echo "[error] failed to source thesis ROS workspace" >&2
  exit 16
fi

export ROS_DOMAIN_ID

echo "[info] THESIS_ROOT=$THESIS_ROOT"
echo "[info] BAG_PATH=$BAG_PATH"
echo "[info] DETECTOR_MODEL=$DETECTOR_MODEL"
echo "[info] HEF_PATH=$HEF_PATH"
echo "[info] TARGET_ID=$TARGET_ID"
echo "[info] TRACKER=$TRACKER"
echo "[info] TIM_MODE=$TIM_MODE"
echo "[info] RATE=$RATE"
echo "[info] RECORDER_STOP_TIMEOUT=$RECORDER_STOP_TIMEOUT"
echo "[info] RUN_CONTROLLER=$RUN_CONTROLLER"
echo "[info] CONTROL_ENABLE_YAW_RECOVERY=$CONTROL_ENABLE_YAW_RECOVERY"
echo "[info] CONTROL_STALE_TIMEOUT_S=$CONTROL_STALE_TIMEOUT_S"
echo "[info] OUT_BAG=$OUT_BAG"
echo "[info] LOG_DIR=$LOG_DIR"

DETECTOR_PID=""
TRACKER_PID=""
DASHBOARD_PID=""
TIM_PID=""
CONTROL_PID=""
REC_PID=""
PLAY_PID=""
RESOURCE_SAMPLER_PID=""
HARDWARE_HEALTH_PID=""

RESOURCE_SAMPLING_ENABLED="${RESOURCE_SAMPLING_ENABLED:-false}"
RESOURCE_SAMPLE_INTERVAL_S="${RESOURCE_SAMPLE_INTERVAL_S:-1.0}"
HARDWARE_HEALTH_INTERVAL_S="${HARDWARE_HEALTH_INTERVAL_S:-1.0}"
P032_RESOURCE_WARM_UP_S="${P032_RESOURCE_WARM_UP_S:-60.0}"

RESOURCE_SAMPLER="$THESIS_ROOT/tools/experiments/sample_process_groups.py"
HARDWARE_HEALTH_SAMPLER="$THESIS_ROOT/tools/experiments/sample_p044_hardware_health.py"
P032_RESOURCE_ANALYSER="$THESIS_ROOT/tools/analysis/analyse_p032_final_resources.py"

P032_ANALYSIS_START_MONOTONIC_NS=""
P032_ANALYSIS_END_MONOTONIC_NS=""

PROCESS_GROUP_SUPERVISOR=(
  "$THESIS_ROOT/tools/lib/run_in_owned_process_group.py"
)

if [[ ! -x "${PROCESS_GROUP_SUPERVISOR[0]}" ]]; then
  echo "[error] owned-process supervisor is unavailable or not executable: ${PROCESS_GROUP_SUPERVISOR[0]}" >&2
  exit 17
fi

owned_process_alive() {
  local pid="$1"

  if [[ -z "$pid" ]]; then
    return 1
  fi

  kill -0 "$pid" >/dev/null 2>&1
}

stop_owned_process() {
  local label="$1"
  local pid="$2"

  if [[ -z "$pid" ]]; then
    return 0
  fi

  if owned_process_alive "$pid"; then
    echo "[info] stopping $label supervisor pid=$pid"
    kill -TERM "$pid" >/dev/null 2>&1 || true

    for _ in $(seq 1 20); do
      if ! owned_process_alive "$pid"; then
        break
      fi
      sleep 0.1
    done
  fi

  if owned_process_alive "$pid"; then
    echo "[warn] $label still alive after SIGTERM; escalating owned process group"
    kill -USR1 "$pid" >/dev/null 2>&1 || true
  fi

  wait "$pid" 2>/dev/null || true
}

resolve_owned_pgid() {
    local label="$1"
    local supervisor_pid="$2"
    local children_path="/proc/$supervisor_pid/task/$supervisor_pid/children"
    local child_pid=""
    local pgid=""

    for _ in $(seq 1 50); do
        if [[ -r "$children_path" ]]; then
            read -r child_pid _ < "$children_path" || true

            if [[ "$child_pid" =~ ^[0-9]+$ ]] && kill -0 "$child_pid" >/dev/null 2>&1; then
                pgid="$(ps -o pgid= -p "$child_pid" 2>/dev/null | tr -d '[:space:]')"

                if [[ "$pgid" == "$child_pid" ]]; then
                    printf '%s\n' "$pgid"
                    return 0
                fi
            fi
        fi

        sleep 0.1
    done

    echo "[error] failed to resolve owned process group for $label supervisor pid=$supervisor_pid" >&2
    return 1
}

cleanup() {
  echo "[info] cleaning up runner-owned supervised processes"
stop_owned_process "hardware health sampler" "${HARDWARE_HEALTH_PID:-}"
stop_owned_process "resource sampler" "${RESOURCE_SAMPLER_PID:-}"
  stop_owned_process "playback" "${PLAY_PID:-}"
  stop_owned_process "recorder" "${REC_PID:-}"
  stop_owned_process "controller" "${CONTROL_PID:-}"
  stop_owned_process "TIM-MARS" "${TIM_PID:-}"
  stop_owned_process "dashboard bridge" "${DASHBOARD_PID:-}"
  stop_owned_process "tracker" "${TRACKER_PID:-}"
  stop_owned_process "detector" "${DETECTOR_PID:-}"
}
trap cleanup EXIT

if [[ -e "$OUT_BAG" ]]; then
  BASE_OUT="$OUT_BAG"
  i=1
  while [[ -e "${BASE_OUT}__r${i}" ]]; do
    i=$((i + 1))
  done
  OUT_BAG="${BASE_OUT}__r${i}"
  RUN_NAME="$(basename "$OUT_BAG")"
  REPORT_DIR="$REPORT_ROOT/$RUN_NAME"
  LOG_DIR="$LOG_ROOT/$RUN_NAME"
  if ! mkdir -p "$LOG_DIR" "$REPORT_DIR"; then
    echo "[error] failed to create collision-safe run directories" >&2
    exit 15
  fi
  echo "[warn] output exists, using OUT_BAG=$OUT_BAG"
fi

TRACKER_CONFIG="$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tracker_${TRACKER}.yaml"
if [[ ! -f "$TRACKER_CONFIG" ]]; then
  echo "[error] tracker config not found: $TRACKER_CONFIG"
  exit 4
fi

echo "[info] starting detector: $DETECTOR_MODEL"
"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run thesis_bringup perception_pipeline_node --ros-args \
  -p image_topic:=/camera/image_raw \
  -p img_w:=640 \
  -p img_h:=640 \
  -p label:=person \
  -p min_score:=0.35 \
  -p inference_backend:=hailo_direct \
  -p hailo_hef_path:="$HEF_PATH" \
  -p publish_timing:=true \
  -p infer_timeout_ms:=300 \
  -p allow_stub_fallback:=false \
  -p frame_queue_size:=1 \
  -p image_qos_depth:=2 \
  -p async_max_inflight:=1 \
  -p num_workers:=1 \
  >"$LOG_DIR/detector.log" 2>&1 &
DETECTOR_PID=$!

echo "[info] starting tracker: $TRACKER"
"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run thesis_tracker tracker_node --ros-args \
  --params-file "$TRACKER_CONFIG" \
  -p publish_timing_topic:=true \
  >"$LOG_DIR/tracker.log" 2>&1 &
TRACKER_PID=$!

echo "[info] starting dashboard bridge"
"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run thesis_bringup dashboard_bridge_node --ros-args \
  -p ws_host:=127.0.0.1 \
  -p ws_port:=0 \
  -p api_host:=127.0.0.1 \
  -p api_port:=8090 \
  -p publish_hz:=30.0 \
  >"$LOG_DIR/dashboard_bridge.log" 2>&1 &
DASHBOARD_PID=$!


TIM_MARS_CONFIG="${TIM_MARS_CONFIG:-$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml}"
TIM_METADATA_HELPER="$THESIS_ROOT/tools/experiments/write_tim_run_metadata.py"
TRACK_SELECTION_HELPER="$THESIS_ROOT/tools/experiments/wait_for_track_selection.py"

if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_MARS_CONFIG" ]]; then
  echo "[error] canonical TIM-MARS config not found: $TIM_MARS_CONFIG" >&2
  exit 1
fi

echo "[info] TIM_MARS_CONFIG=$TIM_MARS_CONFIG"

TIM_MIRROR_EFFECTIVE="${MARS_MIRROR_RAW_TARGET_SELECTION:-true}"
TIM_MARS_MODEL_PATH="${MARS_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}"

if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_METADATA_HELPER" ]]; then
  echo "[error] TIM-MARS metadata helper not found: $TIM_METADATA_HELPER" >&2
  exit 17
fi

if [[ ! -f "$TRACK_SELECTION_HELPER" ]]; then
  echo "[error] typed track-selection helper not found: $TRACK_SELECTION_HELPER" >&2
  exit 17
fi

if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_MARS_MODEL_PATH" ]]; then
  echo "[error] TIM-MARS appearance model not found: $TIM_MARS_MODEL_PATH" >&2
  exit 17
fi

DETECTOR_HEF_SHA_LINE=""
DETECTOR_HEF_SHA256=""
TIM_MARS_MODEL_SHA_LINE=""
TIM_MARS_MODEL_SHA256=""

if ! DETECTOR_HEF_SHA_LINE="$(sha256sum "$HEF_PATH")"; then
  echo "[error] failed to hash detector HEF: $HEF_PATH" >&2
  exit 18
fi
DETECTOR_HEF_SHA256="${DETECTOR_HEF_SHA_LINE%% *}"

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  if ! TIM_MARS_MODEL_SHA_LINE="$(sha256sum "$TIM_MARS_MODEL_PATH")"; then
    echo "[error] failed to hash TIM-MARS appearance model: $TIM_MARS_MODEL_PATH" >&2
    exit 18
  fi
  TIM_MARS_MODEL_SHA256="${TIM_MARS_MODEL_SHA_LINE%% *}"
fi

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  if ! python3 "$TIM_METADATA_HELPER" \
    --repo-root "$THESIS_ROOT" \
    --output-dir "$REPORT_DIR" \
    --config "$TIM_MARS_CONFIG" \
    --runner "$THESIS_ROOT/tools/experiments/run_one_detector_tim_replay.sh" \
    --command "$RUN_COMMAND" \
    --runtime "tracks_topic=/tracks" \
    --runtime "mirror_target_topic=/target" \
    --runtime "target_topic=/target_memory_mars" \
    --runtime "status_topic=/target_memory_mars/status" \
    --runtime "select_topic=/target_memory_mars/select" \
    --runtime "selected_track_id=0" \
    --runtime "mirror_raw_target_selection=$TIM_MIRROR_EFFECTIVE" \
    --runtime "appearance_image_topic=/camera/image_raw" \
    --runtime "mars_model_path=$TIM_MARS_MODEL_PATH" \
    --field "run_name=$RUN_NAME" \
    --field "bag_path=$BAG_PATH" \
    --field "output_bag=$OUT_BAG" \
    --field "detector_model=$DETECTOR_MODEL" \
    --field "detector_hef=$HEF_PATH" \
    --field "detector_hef_sha256=$DETECTOR_HEF_SHA256" \
    --field "mars_model_sha256=$TIM_MARS_MODEL_SHA256" \
    --field "target_id=$TARGET_ID" \
    --field "tracker=$TRACKER" \
    --field "tim_mode=$TIM_MODE" \
    --field "rate=$RATE" \
    --field "target_wait_timeout_s=$TARGET_WAIT_TIMEOUT" \
    --field "recorder_stop_timeout_s=$RECORDER_STOP_TIMEOUT" \
    --field "controller_enabled=$RUN_CONTROLLER" \
    --field "controller_target_topic=/target_memory_mars" \
    --field "controller_status_topic=/target_memory_mars/status" \
    --field "controller_cmd_topic=/control_ref/cmd_vel" \
    --field "controller_mavros_enabled=false" \
    --field "controller_yaw_recovery_enabled=$CONTROL_ENABLE_YAW_RECOVERY" \
    --field "controller_stale_timeout_s=$CONTROL_STALE_TIMEOUT_S" \
    --field "controller_image_width=640" \
    --field "controller_image_height=640" \
    --field "resource_sampling_enabled=$RESOURCE_SAMPLING_ENABLED" \
    --field "p032_resource_warm_up_s=$P032_RESOURCE_WARM_UP_S" \
    --field "resource_analysis_schema=p032_final_resource_analysis_v1"; then
    echo "[error] failed to write TIM-MARS run provenance metadata" >&2
    exit 18
  fi
fi

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  echo "[info] starting TIM-MARS"
  "${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run thesis_bringup target_memory_mars_node --ros-args \
    --params-file "$TIM_MARS_CONFIG" \
    -p tracks_topic:=/tracks \
    -p mirror_target_topic:=/target \
    -p target_topic:=/target_memory_mars \
    -p status_topic:=/target_memory_mars/status \
    -p select_topic:=/target_memory_mars/select \
    -p timing_target_topic:=/timing_target \
    -p selected_track_id:=0 \
    -p mirror_raw_target_selection:="$TIM_MIRROR_EFFECTIVE" \
    -p appearance_image_topic:=/camera/image_raw \
    -p mars_model_path:="$TIM_MARS_MODEL_PATH" \
    >"$LOG_DIR/target_memory_mars.log" 2>&1 &
  TIM_PID=$!
fi

if [[ "${RUN_CONTROLLER,,}" == "true" ]]; then
  echo "[info] starting controller characterization path"
  "${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run thesis_bringup control_ref_node --ros-args \
    -p target_topic:=/target_memory_mars \
    -p status_topic:=/target_memory_mars/status \
    -p cmd_topic:=/control_ref/cmd_vel \
    -p enable_yaw_recovery:="$CONTROL_ENABLE_YAW_RECOVERY" \
    -p img_w:=640.0 \
    -p img_h:=640.0 \
    -p enable_mavros:=false \
    -p cmd_frame_id:=base_link \
    -p stale_timeout_s:="$CONTROL_STALE_TIMEOUT_S" \
    >"$LOG_DIR/control_ref.log" 2>&1 &
  CONTROL_PID=$!
fi

sleep 4

require_alive() {
  local label="$1"
  local pid="$2"
  local log_path="$3"

  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "[ok] $label running pid=$pid"
    return 0
  fi

  echo "[error] $label exited before playback"
  if [[ -f "$log_path" ]]; then
    tail -n 80 "$log_path" || true
  fi
  return 1
}

if ! require_alive "detector" "$DETECTOR_PID" "$LOG_DIR/detector.log"; then
  exit 5
fi

if ! require_alive "tracker" "$TRACKER_PID" "$LOG_DIR/tracker.log"; then
  exit 5
fi

if ! require_alive "dashboard bridge" "$DASHBOARD_PID" "$LOG_DIR/dashboard_bridge.log"; then
  exit 5
fi

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  if ! require_alive "TIM-MARS" "$TIM_PID" "$LOG_DIR/target_memory_mars.log"; then
    exit 5
  fi
fi

if [[ "${RUN_CONTROLLER,,}" == "true" ]]; then
  if ! require_alive "controller" "$CONTROL_PID" "$LOG_DIR/control_ref.log"; then
    exit 5
  fi
fi

case "${RESOURCE_SAMPLING_ENABLED,,}" in
true)
    if [[ ! -f "$RESOURCE_SAMPLER" ]]; then
        echo "[error] resource sampler not found: $RESOURCE_SAMPLER" >&2
        exit 19
    fi

    if [[ ! -f "$HARDWARE_HEALTH_SAMPLER" ]]; then
        echo "[error] hardware-health sampler not found: $HARDWARE_HEALTH_SAMPLER" >&2
        exit 19
    fi

    if [[ ! -f "$P032_RESOURCE_ANALYSER" ]]; then
        echo "[error] P032 resource analyser not found: $P032_RESOURCE_ANALYSER" >&2
        exit 19
    fi

    DETECTOR_PGID="$(resolve_owned_pgid "detector" "$DETECTOR_PID")" || exit 19
    TRACKER_PGID="$(resolve_owned_pgid "tracker" "$TRACKER_PID")" || exit 19

    RESOURCE_GROUP_ARGS=(
        --group "detector=$DETECTOR_PGID"
        --group "tracker=$TRACKER_PGID"
    )

    echo "[info] resource detector pgid=$DETECTOR_PGID"
    echo "[info] resource tracker pgid=$TRACKER_PGID"

    if [[ "$RUN_TIM_MARS" == "true" ]]; then
        TIM_PGID="$(resolve_owned_pgid "TIM-MARS" "$TIM_PID")" || exit 19
        RESOURCE_GROUP_ARGS+=(--group "tim=$TIM_PGID")
        echo "[info] resource TIM-MARS pgid=$TIM_PGID"
    fi

    if [[ "${RUN_CONTROLLER,,}" == "true" ]]; then
        CONTROL_PGID="$(resolve_owned_pgid "controller" "$CONTROL_PID")" || exit 19
        RESOURCE_GROUP_ARGS+=(--group "controller=$CONTROL_PGID")
        echo "[info] resource controller pgid=$CONTROL_PGID"
    fi

    mkdir -p         "$REPORT_DIR/resources"         "$REPORT_DIR/hardware_health"

    echo "[info] starting process-group resource sampler"
    "${PROCESS_GROUP_SUPERVISOR[@]}"         "$THESIS_ROOT/thesis_env/bin/python"         "$RESOURCE_SAMPLER"         --output-dir "$REPORT_DIR/resources"         "${RESOURCE_GROUP_ARGS[@]}"         --interval-s "$RESOURCE_SAMPLE_INTERVAL_S"         > "$LOG_DIR/resources.log" 2>&1 &
    RESOURCE_SAMPLER_PID=$!

    echo "[info] starting hardware-health sampler"
    "${PROCESS_GROUP_SUPERVISOR[@]}"         "$THESIS_ROOT/thesis_env/bin/python"         "$HARDWARE_HEALTH_SAMPLER"         --output-dir "$REPORT_DIR/hardware_health"         --interval-s "$HARDWARE_HEALTH_INTERVAL_S"         --duration-s 0         > "$LOG_DIR/hardware_health.log" 2>&1 &
    HARDWARE_HEALTH_PID=$!

    sleep 1

    if ! require_alive         "resource sampler"         "$RESOURCE_SAMPLER_PID"         "$LOG_DIR/resources.log"; then
        exit 19
    fi

    if ! require_alive         "hardware health sampler"         "$HARDWARE_HEALTH_PID"         "$LOG_DIR/hardware_health.log"; then
        exit 19
    fi
    ;;
false)
    ;;
*)
    echo "[error] RESOURCE_SAMPLING_ENABLED must be true or false" >&2
    exit 19
    ;;
esac

echo "[info] nodes before playback"
ros2 node list | sort | tee "$LOG_DIR/nodes_before_play.txt" || true

echo "[info] starting recorder"
TOPICS=(/camera/image_raw /detections /timing /tracks /target /timing_tracker /timing_target)
if [[ "$RUN_TIM_MARS" == "true" ]]; then
  TOPICS+=(/target_memory_mars /target_memory_mars/status)
fi

if [[ "${RUN_CONTROLLER,,}" == "true" ]]; then
  TOPICS+=(/control_ref/cmd_vel)
fi

"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 bag record -s mcap -o "$OUT_BAG" --topics "${TOPICS[@]}" \
  >"$LOG_DIR/record.log" 2>&1 &
REC_PID=$!

sleep 2

if ! require_alive "recorder" "$REC_PID" "$LOG_DIR/record.log"; then
  exit 6
fi

if [[ "${RESOURCE_SAMPLING_ENABLED,,}" == "true" ]]; then
  P032_ANALYSIS_START_MONOTONIC_NS="$(
    "$THESIS_ROOT/thesis_env/bin/python" -c 'import time; print(time.monotonic_ns())'
  )" || exit 20
  echo "[info] P032 analysis start monotonic ns=$P032_ANALYSIS_START_MONOTONIC_NS"
fi

echo "[info] starting image-only playback"
"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 bag play "$BAG_PATH" \
  --topics /camera/image_raw \
  --rate "$RATE" \
  >"$LOG_DIR/play.log" 2>&1 &
PLAY_PID=$!

sleep 1

if ! require_alive "playback" "$PLAY_PID" "$LOG_DIR/play.log"; then
  exit 7
fi

wait_for_target_id() {
  local target_id="$1"
  local timeout_s="$2"
  local selection_error="$LOG_DIR/track_selection_error.log"
  local chosen_id

  echo "[info] waiting for target id $target_id through typed /tracks subscriber"

  if ! chosen_id="$(python3 "$TRACK_SELECTION_HELPER"     --topic /tracks     --timeout "$timeout_s"     --target-id "$target_id"     2>"$selection_error")"; then
    echo "[error] target id $target_id was not resolved from /tracks"
    cat "$selection_error" 2>/dev/null || true
    return 1
  fi

  if [[ "$chosen_id" != "$target_id" ]]; then
    echo "[error] typed target resolver returned unexpected id: $chosen_id"
    return 1
  fi

  echo "$chosen_id" > "$LOG_DIR/chosen_target_id.txt"
  echo "[ok] target id $target_id found"
  return 0
}


resolve_largest_target() {
  local selection_error="$LOG_DIR/track_selection_error.log"
  local chosen_id

  echo "[info] resolving largest target through typed /tracks subscriber"

  if ! chosen_id="$(python3 "$TRACK_SELECTION_HELPER"     --topic /tracks     --timeout "$TARGET_WAIT_TIMEOUT"     --largest     --min-height 40.0     2>"$selection_error")"; then
    echo "[error] could not resolve largest target id"
    cat "$selection_error" 2>/dev/null || true
    return 1
  fi

  if [[ -z "$chosen_id" ]]; then
    echo "[error] typed largest-target resolver returned an empty id"
    return 1
  fi

  TARGET_ID="$chosen_id"
  echo "$TARGET_ID" > "$LOG_DIR/chosen_target_id.txt"
  echo "[ok] largest target resolved to id: $TARGET_ID"
  return 0
}


select_target() {
  local target_id="$1"
  local response_path="$LOG_DIR/target_api_response.json"

  echo "[info] selecting target through dashboard authority API: $target_id"

  if ! curl -sS --fail-with-body -X POST http://127.0.0.1:8090/api/target \
    -H "Content-Type: application/json" \
    -d "{\"target\": ${target_id}}" \
    -o "$response_path"; then
    echo "[error] target authority API request failed"
    cat "$response_path" 2>/dev/null || true
    return 1
  fi

  cat "$response_path"
  echo

  if ! python3 -c 'import json, sys; p=json.load(open(sys.argv[1])); raise SystemExit(0 if p.get("ok") is True else 1)' "$response_path"; then
    echo "[error] target authority API did not confirm selection"
    return 1
  fi

  echo "[ok] target authority API confirmed selection"
  return 0
}

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  if [[ "${TARGET_ID,,}" == "largest" ]]; then
    if ! resolve_largest_target; then
      exit 9
    fi
  else
    if ! wait_for_target_id "$TARGET_ID" "$TARGET_WAIT_TIMEOUT"; then
      exit 10
    fi
  fi

  sleep 2

  if ! select_target "$TARGET_ID"; then
    exit 11
  fi
else
  echo "[info] TIM-MARS disabled; skipping selected-target authority bootstrap"
fi

echo "[info] waiting for playback to finish"
wait "$PLAY_PID"
PLAY_EXIT=$?
PLAY_PID=""

if [[ "${RESOURCE_SAMPLING_ENABLED,,}" == "true" ]]; then
  P032_ANALYSIS_END_MONOTONIC_NS="$(
    "$THESIS_ROOT/thesis_env/bin/python" -c 'import time; print(time.monotonic_ns())'
  )" || exit 20
  echo "[info] P032 analysis end monotonic ns=$P032_ANALYSIS_END_MONOTONIC_NS"
fi

# Resource/health measurements intentionally cover the active replay window,
# not recorder shutdown or other post-playback cleanup latency.
if [[ -n "${HARDWARE_HEALTH_PID:-}" ]]; then
    stop_owned_process "hardware health sampler" "$HARDWARE_HEALTH_PID"
    HARDWARE_HEALTH_PID=""
fi

if [[ -n "${RESOURCE_SAMPLER_PID:-}" ]]; then
    stop_owned_process "resource sampler" "$RESOURCE_SAMPLER_PID"
    RESOURCE_SAMPLER_PID=""
fi

if [[ "$PLAY_EXIT" -ne 0 ]]; then
  echo "[error] ros2 bag playback exited with status $PLAY_EXIT"
  tail -n 80 "$LOG_DIR/play.log" 2>/dev/null || true
  exit 12
fi

if [[ "${RESOURCE_SAMPLING_ENABLED,,}" == "true" ]]; then
  P032_ARCHITECTURE_GROUPS="detector,tracker"

  if [[ "$RUN_TIM_MARS" == "true" ]]; then
    P032_ARCHITECTURE_GROUPS+=",tim"
  fi

  if [[ "${RUN_CONTROLLER,,}" == "true" ]]; then
    P032_ARCHITECTURE_GROUPS+=",controller"
  fi

  echo "[info] generating P032 final resource analysis"
  echo "[info] P032 architecture groups=$P032_ARCHITECTURE_GROUPS"

  "$THESIS_ROOT/thesis_env/bin/python" "$P032_RESOURCE_ANALYSER" \
    --resources-samples "$REPORT_DIR/resources/samples.jsonl" \
    --hardware-samples "$REPORT_DIR/hardware_health/samples.jsonl" \
    --output-json "$REPORT_DIR/p032_final_resources.json" \
    --output-markdown "$REPORT_DIR/p032_final_resources.md" \
    --warm-up-s "$P032_RESOURCE_WARM_UP_S" \
    --analysis-start-monotonic-ns "$P032_ANALYSIS_START_MONOTONIC_NS" \
    --analysis-end-monotonic-ns "$P032_ANALYSIS_END_MONOTONIC_NS" \
    --architecture-groups "$P032_ARCHITECTURE_GROUPS" \
    >"$LOG_DIR/p032_final_resources.log" 2>&1
  P032_ANALYSIS_RC=$?

  if [[ "$P032_ANALYSIS_RC" -ne 0 ]]; then
    echo "[error] P032 resource analysis failed with status $P032_ANALYSIS_RC"
    tail -n 120 "$LOG_DIR/p032_final_resources.log" 2>/dev/null || true
    exit 20
  fi

  echo "[ok] P032 resource analysis: $REPORT_DIR/p032_final_resources.json"
fi

echo "[info] stopping recorder"

if owned_process_alive "$REC_PID"; then
  kill -INT "$REC_PID" >/dev/null 2>&1 || true
fi

for _ in $(seq 1 "$RECORDER_STOP_TIMEOUT"); do
  if ! owned_process_alive "$REC_PID"; then
    break
  fi
  sleep 1
done

if owned_process_alive "$REC_PID"; then
  echo "[warn] recorder did not exit after SIGINT, sending SIGTERM"
  kill -TERM "$REC_PID" >/dev/null 2>&1 || true
  sleep 2
fi

if owned_process_alive "$REC_PID"; then
  echo "[warn] recorder still alive after SIGTERM; escalating owned process group"
  kill -USR1 "$REC_PID" >/dev/null 2>&1 || true
fi

wait "$REC_PID"
REC_EXIT=$?
REC_PID=""

if [[ "$REC_EXIT" -ne 0 && "$REC_EXIT" -ne 130 && "$REC_EXIT" -ne 143 ]]; then
  echo "[error] recorder exited with unexpected status $REC_EXIT"
  tail -n 80 "$LOG_DIR/record.log" 2>/dev/null || true
  exit 13
fi

echo "[ok] done"
echo "[ok] eval bag: $OUT_BAG"
echo "[ok] report: $REPORT_DIR"
echo "[ok] logs: $LOG_DIR"
