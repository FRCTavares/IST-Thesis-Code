#!/usr/bin/env bash
set -eo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage:"
  echo "  $0 <bag_path> <target_id> <tracker> <tim_mode:off|hsv|mars|both|on> [rate] [target_wait_timeout_s]"
  exit 1
fi

BAG_PATH="$1"
TARGET_ID="$2"
TRACKER="$3"
TIM_MODE="$4"
RATE="${5:-0.5}"
TARGET_WAIT_TIMEOUT="${6:-90}"

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

BAG_PATH="$(realpath "$BAG_PATH")"
BAG_BASE="$(basename "$BAG_PATH")"
RUN_NAME="${BAG_BASE}__tracker_${TRACKER}__tim_${TIM_MODE}__target_${TARGET_ID}"
OUT_BAG="$THESIS_ROOT/artifacts/bags/eval_matrix/$RUN_NAME"
REPORT_DIR="$THESIS_ROOT/reports/tim_v0/$RUN_NAME"
LOG_DIR="$THESIS_ROOT/ros2_ws/log/eval_matrix/$RUN_NAME"

mkdir -p "$LOG_DIR"

echo "[info] THESIS_ROOT=$THESIS_ROOT"
echo "[info] BAG_PATH=$BAG_PATH"
echo "[info] RUN_NAME=$RUN_NAME"
echo "[info] OUT_BAG=$OUT_BAG"
echo "[info] LOG_DIR=$LOG_DIR"
echo "[info] TARGET_ID=$TARGET_ID"
echo "[info] TRACKER=$TRACKER"
echo "[info] TIM_MODE=$TIM_MODE"
echo "[info] RATE=$RATE"

# Backward compatibility: old "on" means TIM-HSV.
if [[ "$TIM_MODE" == "on" ]]; then
  TIM_MODE="hsv"
fi

RUN_TIM_HSV=false
RUN_TIM_MARS=false

case "$TIM_MODE" in
  off)
    ;;
  hsv)
    RUN_TIM_HSV=true
    ;;
  mars)
    RUN_TIM_MARS=true
    ;;
  both)
    RUN_TIM_HSV=true
    RUN_TIM_MARS=true
    ;;
  *)
    echo "[error] tim_mode must be one of: off, hsv, mars, both, on"
    exit 3
    ;;
esac

echo "[info] NORMALISED_TIM_MODE=$TIM_MODE"
echo "[info] RUN_TIM_HSV=$RUN_TIM_HSV"
echo "[info] RUN_TIM_MARS=$RUN_TIM_MARS"

TIM_STARTUP_SELECTED_ONLY="${TIM_STARTUP_SELECTED_ONLY:-false}"
echo "[info] TIM_STARTUP_SELECTED_ONLY=$TIM_STARTUP_SELECTED_ONLY"

source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID

cleanup() {
  echo "[info] cleaning up background processes"
  jobs -pr | xargs -r kill || true
  pkill -f "ros2 bag play|ros2 bag record|tracker_node|dashboard_bridge_node|target_memory_node|target_memory_mars_node" || true
}
trap cleanup EXIT

echo "[info] stopping old replay processes"
pkill -f "ros2 bag play|ros2 bag record|tracker_node|dashboard_bridge_node|target_memory_node|target_memory_mars_node" || true
sleep 2

if [[ -e "$OUT_BAG" ]]; then
  BASE_OUT="$OUT_BAG"
  i=1
  while [[ -e "${BASE_OUT}__r${i}" ]]; do
    i=$((i + 1))
  done
  OUT_BAG="${BASE_OUT}__r${i}"
  RUN_NAME="$(basename "$OUT_BAG")"
  REPORT_DIR="$THESIS_ROOT/reports/tim_v0/$RUN_NAME"
  LOG_DIR="$THESIS_ROOT/ros2_ws/log/eval_matrix/$RUN_NAME"
  mkdir -p "$LOG_DIR"
  echo "[warn] output exists, using OUT_BAG=$OUT_BAG"
  echo "[warn] updated RUN_NAME=$RUN_NAME"
fi

mkdir -p "$THESIS_ROOT/artifacts/bags/eval_matrix"

TRACKER_CONFIG="$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tracker_${TRACKER}.yaml"
if [[ ! -f "$TRACKER_CONFIG" ]]; then
  echo "[error] tracker config not found: $TRACKER_CONFIG"
  exit 2
fi

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

if [[ "$RUN_TIM_HSV" == "true" ]]; then
  echo "[info] starting TIM-HSV"
  ros2 run thesis_bringup target_memory_node --ros-args \
    -p tracks_topic:=/tracks \
    -p raw_target_topic:=/target \
    -p target_topic:=/target_memory \
    -p status_topic:=/target_memory/status \
    -p select_topic:=/target_memory/select \
    -p selected_track_id:=${TARGET_ID} \
    -p mirror_raw_target_selection:=$([[ "$TIM_STARTUP_SELECTED_ONLY" == "true" ]] && echo false || echo true) \
    -p appearance_enabled:=true \
    -p appearance_image_topic:=/camera/image_raw \
    -p accept_score_locked:=${TIM_ACCEPT_SCORE_LOCKED:-0.52} \
    -p accept_score_lost:=${TIM_ACCEPT_SCORE_LOST:-0.60} \
    -p ambiguity_margin:=${TIM_AMBIGUITY_MARGIN:-0.07} \
    -p appearance_weight:=${TIM_APPEARANCE_WEIGHT:-0.12} \
    -p appearance_min_similarity:=${TIM_APPEARANCE_MIN_SIMILARITY:-0.35} \
    -p appearance_ambiguous_only:=${TIM_APPEARANCE_AMBIGUOUS_ONLY:-true} \
    -p appearance_update_cooldown_after_reacquire_frames:=${TIM_APPEARANCE_UPDATE_COOLDOWN_FRAMES:-0} \
    -p appearance_challenge_enabled:=${TIM_APPEARANCE_CHALLENGE_ENABLED:-false} \
    -p appearance_challenge_min_similarity:=${TIM_APPEARANCE_CHALLENGE_MIN_SIMILARITY:-0.50} \
    -p appearance_challenge_margin:=${TIM_APPEARANCE_CHALLENGE_MARGIN:-0.20} \
    -p appearance_challenge_min_total:=${TIM_APPEARANCE_CHALLENGE_MIN_TOTAL:-0.45} \
    -p rank_aware_reacquisition_enabled:=${TIM_RANK_AWARE_REACQUISITION_ENABLED:-false} \
    -p rank_aware_lost_min_total:=${TIM_RANK_AWARE_LOST_MIN_TOTAL:-0.40} \
    -p rank_aware_lost_min_geom:=${TIM_RANK_AWARE_LOST_MIN_GEOM:-0.10} \
    -p rank_aware_lost_min_app:=${TIM_RANK_AWARE_LOST_MIN_APP:-0.05} \
    -p rank_aware_lost_app_margin:=${TIM_RANK_AWARE_LOST_APP_MARGIN:-0.03} \
    -p rank_aware_confirm_frames:=${TIM_RANK_AWARE_CONFIRM_FRAMES:-1} \
    -p rank_aware_missing_ttl_frames:=${TIM_RANK_AWARE_MISSING_TTL_FRAMES:-8} \
    >"$LOG_DIR/target_memory_hsv.log" 2>&1 &
fi

if [[ "$RUN_TIM_MARS" == "true" ]]; then
  echo "[info] starting TIM-MARS"
  ros2 run thesis_bringup target_memory_mars_node --ros-args \
    -p tracks_topic:=/tracks \
    -p raw_target_topic:=/target \
    -p target_topic:=/target_memory_mars \
    -p status_topic:=/target_memory_mars/status \
    -p select_topic:=/target_memory_mars/select \
    -p selected_track_id:=${TARGET_ID} \
    -p mirror_raw_target_selection:=$([[ "$TIM_STARTUP_SELECTED_ONLY" == "true" ]] && echo false || echo true) \
    -p appearance_enabled:=true \
    -p appearance_image_topic:=/camera/image_raw \
    -p mars_model_path:="${MARS_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}" \
    -p mars_batch_size:=${MARS_BATCH_SIZE:-32} \
    -p appearance_weight:=${MARS_APPEARANCE_WEIGHT:-0.12} \
    -p appearance_min_similarity:=${MARS_APPEARANCE_MIN_SIMILARITY:-0.35} \
    -p appearance_ambiguous_only:=${MARS_APPEARANCE_AMBIGUOUS_ONLY:-true} \
    -p appearance_update_cooldown_after_reacquire_frames:=${MARS_APPEARANCE_UPDATE_COOLDOWN_FRAMES:-0} \
    -p appearance_challenge_enabled:=${MARS_APPEARANCE_CHALLENGE_ENABLED:-false} \
    -p appearance_challenge_min_similarity:=${MARS_APPEARANCE_CHALLENGE_MIN_SIMILARITY:-0.50} \
    -p appearance_challenge_margin:=${MARS_APPEARANCE_CHALLENGE_MARGIN:-0.20} \
    -p appearance_challenge_min_total:=${MARS_APPEARANCE_CHALLENGE_MIN_TOTAL:-0.45} \
    -p appearance_conservative_enabled:=${MARS_APPEARANCE_CONSERVATIVE_ENABLED:-false} \
    -p appearance_conservative_min_similarity:=${MARS_APPEARANCE_CONSERVATIVE_MIN_SIMILARITY:-0.65} \
    -p appearance_conservative_margin:=${MARS_APPEARANCE_CONSERVATIVE_MARGIN:-0.25} \
    -p rank_aware_reacquisition_enabled:=${MARS_RANK_AWARE_REACQUISITION_ENABLED:-true} \
    -p rank_aware_confirm_frames:=${MARS_RANK_AWARE_CONFIRM_FRAMES:-1} \
    -p rank_aware_missing_ttl_frames:=${MARS_RANK_AWARE_MISSING_TTL_FRAMES:-8} \
    >"$LOG_DIR/target_memory_mars.log" 2>&1 &
fi

if [[ "$RUN_TIM_HSV" != "true" && "$RUN_TIM_MARS" != "true" ]]; then
  echo "[info] TIM disabled"
fi

sleep 3

echo "[info] nodes before playback"
ros2 node list | sort | tee "$LOG_DIR/nodes_before_play.txt" || true

echo "[info] starting recorder"
TOPICS=(/camera/image_raw /detections /tracks /target /timing_tracker /timing_target)
if [[ "$RUN_TIM_HSV" == "true" ]]; then
  TOPICS+=(/target_memory /target_memory/status)
fi
if [[ "$RUN_TIM_MARS" == "true" ]]; then
  TOPICS+=(/target_memory_mars /target_memory_mars/status)
fi

ros2 bag record -s mcap -o "$OUT_BAG" --topics "${TOPICS[@]}" \
  >"$LOG_DIR/record.log" 2>&1 &
REC_PID=$!

sleep 2

echo "[info] starting clean input playback"
ros2 bag play "$BAG_PATH" \
  --topics /camera/image_raw /detections \
  --rate "$RATE" \
  >"$LOG_DIR/play.log" 2>&1 &
PLAY_PID=$!

wait_for_target_track() {
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

select_target() {
  local target_id="$1"

  echo "[info] selecting target via API: $target_id"
  curl -s -X POST http://127.0.0.1:8090/api/target \
    -H "Content-Type: application/json" \
    -d "{\"target\": ${target_id}}" | tee "$LOG_DIR/target_api_response.json" || true
  echo

  if [[ "$TIM_STARTUP_SELECTED_ONLY" == "true" ]]; then
    echo "[info] skipping TIM select topics because TIM_STARTUP_SELECTED_ONLY=true"
    return 0
  fi

  if [[ "$RUN_TIM_HSV" == "true" ]]; then
    echo "[info] selecting target via TIM-HSV select topic: $target_id"
    ros2 topic pub --once \
      --qos-reliability best_effort \
      /target_memory/select \
      std_msgs/msg/UInt32 \
      "{data: ${target_id}}" >"$LOG_DIR/tim_hsv_select.log" 2>&1 || true
  fi

  if [[ "$RUN_TIM_MARS" == "true" ]]; then
    echo "[info] selecting target via TIM-MARS select topic: $target_id"
    ros2 topic pub --once \
      --qos-reliability best_effort \
      /target_memory_mars/select \
      std_msgs/msg/UInt32 \
      "{data: ${target_id}}" >"$LOG_DIR/tim_mars_select.log" 2>&1 || true
  fi
}

verify_target() {
  local target_id="$1"

  echo "[info] verifying /target id $target_id"
  for _ in {1..20}; do
    if timeout 2s ros2 topic echo /target --once >"$LOG_DIR/target_once.txt" 2>/dev/null; then
      if grep -q "id: ${target_id}" "$LOG_DIR/target_once.txt"; then
        echo "[ok] /target has id $target_id"
        break
      fi
    fi
    sleep 1
  done

  if [[ "$RUN_TIM_HSV" == "true" ]]; then
    echo "[info] verifying /target_memory id $target_id"
    for _ in {1..30}; do
      if timeout 2s ros2 topic echo /target_memory --once >"$LOG_DIR/target_memory_hsv_once.txt" 2>/dev/null; then
        if grep -q "id: ${target_id}" "$LOG_DIR/target_memory_hsv_once.txt"; then
          echo "[ok] /target_memory has id $target_id"
          break
        fi
      fi
      sleep 1
    done
  fi

  if [[ "$RUN_TIM_MARS" == "true" ]]; then
    echo "[info] verifying /target_memory_mars id $target_id"
    for _ in {1..30}; do
      if timeout 2s ros2 topic echo /target_memory_mars --once >"$LOG_DIR/target_memory_mars_once.txt" 2>/dev/null; then
        if grep -q "id: ${target_id}" "$LOG_DIR/target_memory_mars_once.txt"; then
          echo "[ok] /target_memory_mars has id $target_id"
          break
        fi
      fi
      sleep 1
    done
  fi

  return 0
}

if [[ "${TARGET_ID,,}" == "largest" ]]; then
  echo "[info] waiting for tracks to choose largest target"
  for i in $(seq 1 "$TARGET_WAIT_TIMEOUT"); do
    if timeout 2s ros2 topic echo /tracks --once >"$LOG_DIR/tracks_once.txt" 2>/dev/null; then
      CHOSEN_ID="$(python3 "$THESIS_ROOT/tools/experiments/select_largest_track_id.py" "$LOG_DIR/tracks_once.txt" 2>"$LOG_DIR/select_largest_error.log" || true)"
      if [[ -n "${CHOSEN_ID:-}" ]]; then
        echo "$CHOSEN_ID" > "$LOG_DIR/chosen_target_id.txt"
        TARGET_ID="$CHOSEN_ID"
        echo "[ok] largest target resolved to id: $TARGET_ID"
        break
      fi
    fi
    sleep 1
  done

  if [[ "${TARGET_ID,,}" == "largest" ]]; then
    echo "[error] could not resolve largest target id"
    cat "$LOG_DIR/select_largest_error.log" 2>/dev/null || true
    exit 4
  fi
else
  wait_for_target_track "$TARGET_ID" "$TARGET_WAIT_TIMEOUT"
fi

# Let tracker/dashboard/TIM see a few more frames before selection.
sleep 2

select_target "$TARGET_ID"

# Retry selection if TIM/raw target did not lock.
if ! verify_target "$TARGET_ID"; then
  echo "[warn] first selection verification failed; retrying target selection"
  select_target "$TARGET_ID"
  sleep 2
  verify_target "$TARGET_ID"
fi

echo "[info] waiting for playback to finish"
wait "$PLAY_PID" || true

echo "[info] stopping recorder"
kill -INT "$REC_PID" || true

for _ in {1..20}; do
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

echo "[info] analysing eval bag"
python3 "$THESIS_ROOT/tools/analysis/analyse_tim_v0_bag.py" "$OUT_BAG" || true

if [[ "$TIM_MODE" == "on" && -f "$REPORT_DIR/target_memory_status.csv" ]]; then
  python3 "$THESIS_ROOT/tools/analysis/analyse_tim_v1_appearance.py" \
    "$REPORT_DIR/target_memory_status.csv" \
    --out-root "$THESIS_ROOT/reports/tim_v1_appearance" || true
fi

echo "[ok] done"
echo "[ok] eval bag: $OUT_BAG"
echo "[ok] report: $REPORT_DIR"
echo "[ok] logs: $LOG_DIR"
