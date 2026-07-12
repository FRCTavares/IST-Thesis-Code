#!/usr/bin/env bash
set -eo pipefail

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

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

BAG_PATH="$(realpath "$BAG_PATH")"
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

mkdir -p "$LOG_DIR" "$OUT_ROOT"

source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
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
echo "[info] OUT_BAG=$OUT_BAG"
echo "[info] LOG_DIR=$LOG_DIR"

cleanup() {
  echo "[info] cleaning up background processes"
  jobs -pr | xargs -r kill || true
  pkill -f "ros2 bag play|ros2 bag record|perception_pipeline_node|tracker_node|dashboard_bridge_node|target_memory_mars_node" || true
}
trap cleanup EXIT

echo "[info] stopping old replay processes"
pkill -f "ros2 bag play|ros2 bag record|perception_pipeline_node|tracker_node|dashboard_bridge_node|target_memory_mars_node" || true
sleep 2

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
  mkdir -p "$LOG_DIR"
  echo "[warn] output exists, using OUT_BAG=$OUT_BAG"
fi

TRACKER_CONFIG="$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tracker_${TRACKER}.yaml"
if [[ ! -f "$TRACKER_CONFIG" ]]; then
  echo "[error] tracker config not found: $TRACKER_CONFIG"
  exit 4
fi

echo "[info] starting detector: $DETECTOR_MODEL"
ros2 run thesis_bringup perception_pipeline_node --ros-args \
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

echo "[info] starting tracker: $TRACKER"
ros2 run thesis_tracker tracker_node --ros-args \
  --params-file "$TRACKER_CONFIG" \
  >"$LOG_DIR/tracker.log" 2>&1 &

echo "[info] starting dashboard bridge"
ros2 run thesis_bringup dashboard_bridge_node --ros-args \
  -p ws_host:=127.0.0.1 \
  -p ws_port:=0 \
  -p api_host:=127.0.0.1 \
  -p api_port:=8090 \
  -p publish_hz:=30.0 \
  >"$LOG_DIR/dashboard_bridge.log" 2>&1 &


TIM_MARS_CONFIG="${TIM_MARS_CONFIG:-$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml}"

if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_MARS_CONFIG" ]]; then
  echo "[error] canonical TIM-MARS config not found: $TIM_MARS_CONFIG" >&2
  exit 1
fi

echo "[info] TIM_MARS_CONFIG=$TIM_MARS_CONFIG"

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  echo "[info] starting TIM-MARS"
  ros2 run thesis_bringup target_memory_mars_node --ros-args \
    --params-file "$TIM_MARS_CONFIG" \
    -p tracks_topic:=/tracks \
    -p mirror_target_topic:=/target \
    -p target_topic:=/target_memory_mars \
    -p status_topic:=/target_memory_mars/status \
    -p select_topic:=/target_memory_mars/select \
    -p selected_track_id:=0 \
    -p mirror_raw_target_selection:=${MARS_MIRROR_RAW_TARGET_SELECTION:-true} \
    -p appearance_image_topic:=/camera/image_raw \
    -p mars_model_path:="${MARS_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}" \
    >"$LOG_DIR/target_memory_mars.log" 2>&1 &
fi

sleep 4

echo "[info] nodes before playback"
ros2 node list | sort | tee "$LOG_DIR/nodes_before_play.txt" || true

echo "[info] starting recorder"
TOPICS=(/camera/image_raw /detections /timing /tracks /target /timing_tracker /timing_target)
if [[ "$RUN_TIM_MARS" == "true" ]]; then
  TOPICS+=(/target_memory_mars /target_memory_mars/status)
fi

ros2 bag record -s mcap -o "$OUT_BAG" --topics "${TOPICS[@]}" \
  >"$LOG_DIR/record.log" 2>&1 &
REC_PID=$!

sleep 2

echo "[info] starting image-only playback"
ros2 bag play "$BAG_PATH" \
  --topics /camera/image_raw \
  --rate "$RATE" \
  >"$LOG_DIR/play.log" 2>&1 &
PLAY_PID=$!

wait_for_tracks() {
  local timeout_s="$1"
  local start_s
  start_s="$(date +%s)"

  echo "[info] waiting for /tracks"
  while true; do
    local now_s elapsed
    now_s="$(date +%s)"
    elapsed=$((now_s - start_s))

    if (( elapsed > timeout_s )); then
      echo "[error] /tracks not seen within ${timeout_s}s"
      return 1
    fi

    if timeout 2s ros2 topic echo /tracks --once >"$LOG_DIR/tracks_once.txt" 2>/dev/null; then
      if grep -q "id:" "$LOG_DIR/tracks_once.txt"; then
        echo "[ok] /tracks available"
        return 0
      fi
    fi

    sleep 1
  done
}


wait_for_target_id() {
  local target_id="$1"
  local timeout_s="$2"
  local start_s
  start_s="$(date +%s)"

  echo "[info] waiting for target id $target_id in /tracks"
  while true; do
    local now_s elapsed
    now_s="$(date +%s)"
    elapsed=$((now_s - start_s))

    if (( elapsed > timeout_s )); then
      echo "[error] target id $target_id not seen in /tracks within ${timeout_s}s"
      return 1
    fi

    if timeout 2s ros2 topic echo /tracks --once >"$LOG_DIR/tracks_once.txt" 2>/dev/null; then
      if grep -q "id: ${target_id}" "$LOG_DIR/tracks_once.txt"; then
        echo "[ok] target id $target_id found"
        return 0
      fi
    fi

    sleep 1
  done
}

resolve_largest_target() {
  for _ in $(seq 1 "$TARGET_WAIT_TIMEOUT"); do
    if timeout 2s ros2 topic echo /tracks --once >"$LOG_DIR/tracks_once.txt" 2>/dev/null; then
      CHOSEN_ID="$(python3 "$THESIS_ROOT/tools/experiments/select_largest_track_id.py" "$LOG_DIR/tracks_once.txt" 2>"$LOG_DIR/select_largest_error.log" || true)"
      if [[ -n "${CHOSEN_ID:-}" ]]; then
        echo "$CHOSEN_ID" > "$LOG_DIR/chosen_target_id.txt"
        TARGET_ID="$CHOSEN_ID"
        echo "[ok] largest target resolved to id: $TARGET_ID"
        return 0
      fi
    fi
    sleep 1
  done

  echo "[error] could not resolve largest target id"
  cat "$LOG_DIR/select_largest_error.log" 2>/dev/null || true
  return 1
}

select_target() {
  local target_id="$1"

  echo "[info] selecting target via API: $target_id"
  curl -s -X POST http://127.0.0.1:8090/api/target \
    -H "Content-Type: application/json" \
    -d "{\"target\": ${target_id}}" | tee "$LOG_DIR/target_api_response.json" || true
  echo

  if [[ "$RUN_TIM_MARS" == "true" ]]; then
    echo "[info] selecting target via TIM-MARS select topic: $target_id"
    ros2 topic pub --once \
      --qos-reliability best_effort \
      /target_memory_mars/select \
      std_msgs/msg/UInt32 \
      "{data: ${target_id}}" >"$LOG_DIR/tim_mars_select.log" 2>&1 || true
  fi
}

wait_for_tracks "$TARGET_WAIT_TIMEOUT"

if [[ "${TARGET_ID,,}" == "largest" ]]; then
  resolve_largest_target
else
  wait_for_target_id "$TARGET_ID" "$TARGET_WAIT_TIMEOUT"
fi

sleep 2
select_target "$TARGET_ID"

echo "[info] waiting for playback to finish"
wait "$PLAY_PID" || true

echo "[info] stopping recorder"
kill -INT "$REC_PID" || true

for _ in $(seq 1 "$RECORDER_STOP_TIMEOUT"); do
  if ! kill -0 "$REC_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if kill -0 "$REC_PID" >/dev/null 2>&1; then
  echo "[warn] recorder did not exit after SIGINT, sending SIGTERM"
  kill "$REC_PID" || true
  sleep 2
fi

wait "$REC_PID" || true

echo "[ok] done"
echo "[ok] eval bag: $OUT_BAG"
echo "[ok] report: $REPORT_DIR"
echo "[ok] logs: $LOG_DIR"
