#!/usr/bin/env bash
set -eo pipefail

# Purpose:
# - Replay TIM-MARS as a selected-target memory layer over existing tracks.
# - Choose the raw /target source from the input bag, a fixed selected ID, or
#   annotation-driven physical-target intervals.
# - Record replay output and run selected-target correctness evaluation.
#
# This is the main final TIM-MARS safety replay helper.
#
if [[ $# -lt 4 ]]; then
  echo "Usage:"
  echo "  $0 <bag_path> <target_id> <run_name> <annotation_csv> [rate]"
  echo
  echo "Environment modes:"
  echo "  RAW_TARGET_MODE=source      replay /target from the input bag"
  echo "  RAW_TARGET_MODE=selected_id publish /target from a fixed tracker ID"
  echo "  RAW_TARGET_MODE=annotation  publish /target from annotation CSV + /tracks"
  echo
  echo "  TIM_MIRROR_RAW_TARGET_SELECTION=false  autonomous TIM recovery from selected_track_id"
  echo "  TIM_MIRROR_RAW_TARGET_SELECTION=true   TIM follows /target reselection updates"
  echo
  echo "Example:"
  echo "  RAW_TARGET_MODE=source $0 bags/annotation_inputs/2026-06-19__seq02__target_reentry__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest 1 seq02_target_reentry docs/data/annotations/june_hard_sequences/seq02_bytetrack.csv 1.0"
  exit 1
fi

BAG_PATH="$1"
TARGET_ID="$2"
RUN_NAME="$3"
ANN_CSV="$4"
RATE="${5:-1.0}"

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

OUT_ROOT="${TIM_REPLAY_OUT_ROOT:-$THESIS_ROOT/bags/replay/memory_tim_safety_eval}"
REPORT_ROOT="${TIM_REPLAY_REPORT_ROOT:-$THESIS_ROOT/reports/memory_tim_safety_eval}"
LOG_ROOT="${TIM_REPLAY_LOG_ROOT:-$THESIS_ROOT/ros2_ws/log/memory_tim_safety_eval}"

OUT_BAG="$OUT_ROOT/$RUN_NAME"
REPORT_DIR="$REPORT_ROOT/$RUN_NAME"
LOG_DIR="$LOG_ROOT/$RUN_NAME"

MARS_MODEL_PATH="${MARS_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}"
TIM_MARS_CONFIG="${TIM_MARS_CONFIG:-$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml}"
# RAW_TARGET_MODE controls how /target is produced during replay:
#   source      -> replay original /target from the input bag
#   selected_id -> synthesize /target from a fixed tracker ID
#   annotation  -> synthesize /target from annotation CSV + /tracks
RAW_TARGET_MODE="${RAW_TARGET_MODE:-source}"

TIM_APPEARANCE_IMAGE_TOPIC="${MARS_APPEARANCE_IMAGE_TOPIC:-${TIM_APPEARANCE_IMAGE_TOPIC:-/camera/image_raw}}"

# false: TIM starts from selected_track_id and must recover ID switches itself.
# true:  TIM mirrors /target reselection events, useful for preservation/oracle tests.
TIM_MIRROR_RAW_TARGET_SELECTION="${TIM_MIRROR_RAW_TARGET_SELECTION:-false}"

cleanup_ros() {
  echo "[info] cleaning up background ROS processes"
  local patterns="ros2 bag play|ros2 bag record|target_memory_mars_node|publish_selected_track_target.py|publish_annotated_track_target.py"
  pkill -INT -f "$patterns" || true
  sleep 3
  pkill -TERM -f "$patterns" || true
  sleep 2
  pkill -9 -f "$patterns" || true
}

wait_for_metadata() {
  local bag="$1"
  for _ in $(seq 1 60); do
    if [[ -f "$bag/metadata.yaml" ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

stop_pid_cleanly() {
  local pid="$1"
  local name="$2"

  if kill -0 "$pid" 2>/dev/null; then
    kill -INT "$pid" 2>/dev/null || true

    for _ in $(seq 1 60); do
      if ! kill -0 "$pid" 2>/dev/null; then
        return 0
      fi
      sleep 1
    done

    echo "[warn] $name did not exit after SIGINT; sending SIGTERM"
    kill -TERM "$pid" 2>/dev/null || true

    for _ in $(seq 1 20); do
      if ! kill -0 "$pid" 2>/dev/null; then
        return 0
      fi
      sleep 1
    done

    echo "[warn] $name still alive; sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
}

echo "[info] THESIS_ROOT=$THESIS_ROOT"
echo "[info] BAG_PATH=$BAG_PATH"
echo "[info] TARGET_ID=$TARGET_ID"
echo "[info] RUN_NAME=$RUN_NAME"
echo "[info] ANN_CSV=$ANN_CSV"
echo "[info] RATE=$RATE"
echo "[info] OUT_BAG=$OUT_BAG"
echo "[info] REPORT_DIR=$REPORT_DIR"
echo "[info] LOG_DIR=$LOG_DIR"
echo "[info] APP_MARGIN=$APP_MARGIN"
echo "[info] APPEARANCE_MAX_IMAGE_AGE_MS=$APPEARANCE_MAX_IMAGE_AGE_MS"
echo "[info] APPEARANCE_COMPUTE_MIN_INTERVAL_MS=$APPEARANCE_COMPUTE_MIN_INTERVAL_MS"
echo "[info] APPEARANCE_CACHE_TTL_MS=$APPEARANCE_CACHE_TTL_MS"
echo "[info] HN_ENABLED=$HN_ENABLED"
echo "[info] HN_MARGIN=$HN_MARGIN"
echo "[info] RANK_CONFIRM=$RANK_CONFIRM"
echo "[info] RAW_TARGET_MODE=$RAW_TARGET_MODE"
echo "[info] TIM_APPEARANCE_IMAGE_TOPIC=$TIM_APPEARANCE_IMAGE_TOPIC"
echo "[info] TIM_MIRROR_RAW_TARGET_SELECTION=$TIM_MIRROR_RAW_TARGET_SELECTION"
echo "[info] ANCHOR_DRIFT_ENABLED=$ANCHOR_DRIFT_ENABLED"
echo "[info] ANCHOR_DRIFT_MAX_DISTANCE=$ANCHOR_DRIFT_MAX_DISTANCE"
echo "[info] ANCHOR_UPDATE_ALPHA=$ANCHOR_UPDATE_ALPHA"
echo "[info] CANDIDATE_BELIEF_ENABLED=$CANDIDATE_BELIEF_ENABLED"
echo "[info] CANDIDATE_BELIEF_MIN_SCORE=$CANDIDATE_BELIEF_MIN_SCORE"
echo "[info] CANDIDATE_BELIEF_CONFIRM_FRAMES=$CANDIDATE_BELIEF_CONFIRM_FRAMES"
echo "[info] ABSENCE_RECOVERY_ENABLED=$ABSENCE_RECOVERY_ENABLED"
echo "[info] ABSENCE_AFTER_MISSED_FRAMES=$ABSENCE_AFTER_MISSED_FRAMES"
echo "[info] ABSENCE_NEW_ID_REQUIRES_APPEARANCE=$ABSENCE_NEW_ID_REQUIRES_APPEARANCE"
echo "[info] ABSENCE_MIN_TOTAL=$ABSENCE_MIN_TOTAL"
echo "[info] ABSENCE_MIN_DISTANCE=$ABSENCE_MIN_DISTANCE"
echo "[info] ABSENCE_MIN_SCALE=$ABSENCE_MIN_SCALE"
echo "[info] ABSENCE_MIN_SIMILARITY=$ABSENCE_MIN_SIMILARITY"
echo "[info] ABSENCE_APPEARANCE_MARGIN=$ABSENCE_APPEARANCE_MARGIN"
echo "[info] ABSENCE_CONFIRM_FRAMES=$ABSENCE_CONFIRM_FRAMES"
echo "[info] GROUP_SPLIT_RECOVERY_ENABLED=$GROUP_SPLIT_RECOVERY_ENABLED"
echo "[info] GROUP_NEAR_DISTANCE=$GROUP_NEAR_DISTANCE"
echo "[info] GROUP_NEAR_IOU=$GROUP_NEAR_IOU"
echo "[info] GROUP_MIN_NEARBY=$GROUP_MIN_NEARBY"
echo "[info] GROUP_CONFIRM_FRAMES=$GROUP_CONFIRM_FRAMES"
echo "[info] SPLIT_CONFIRM_FRAMES=$SPLIT_CONFIRM_FRAMES"
echo "[info] SPLIT_MIN_MEAN_APP=$SPLIT_MIN_MEAN_APP"
echo "[info] SPLIT_MIN_MEAN_MARGIN=$SPLIT_MIN_MEAN_MARGIN"
echo "[info] SPLIT_MIN_MEAN_TOTAL=$SPLIT_MIN_MEAN_TOTAL"
echo "[info] SPLIT_WINNER_MARGIN=$SPLIT_WINNER_MARGIN"

if [[ ! -d "$BAG_PATH" ]]; then
  echo "[error] bag not found: $BAG_PATH" >&2
  exit 2
fi

if [[ ! -f "$ANN_CSV" ]]; then
  echo "[error] annotation CSV not found: $ANN_CSV" >&2
  exit 2
fi

source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID

rm -rf "$OUT_BAG" "$REPORT_DIR" "$LOG_DIR"
mkdir -p "$OUT_ROOT" "$REPORT_DIR" "$LOG_DIR"

cleanup_ros
trap cleanup_ros EXIT

echo "[info] starting TIM-MARS memory-only node"

if [[ ! -f "$TIM_MARS_CONFIG" ]]; then
  echo "[error] canonical TIM-MARS config not found: $TIM_MARS_CONFIG" >&2
  exit 1
fi

ros2 run thesis_bringup target_memory_mars_node --ros-args \
  --params-file "$TIM_MARS_CONFIG" \
  -p tracks_topic:=/tracks \
  -p mirror_target_topic:=/target \
  -p target_topic:=/target_memory_mars \
  -p status_topic:=/target_memory_mars/status \
  -p select_topic:=/target_memory_mars/select \
  -p selected_track_id:="$TARGET_ID" \
  -p mirror_raw_target_selection:="$TIM_MIRROR_RAW_TARGET_SELECTION" \
  -p appearance_image_topic:="$TIM_APPEARANCE_IMAGE_TOPIC" \
  -p mars_model_path:="$MARS_MODEL_PATH" \
  >"$LOG_DIR/target_memory_mars.log" 2>&1 &
TIM_PID=$!

READY=0
for _ in $(seq 1 60); do
  if rg -q "TIM-MARS node ready" "$LOG_DIR/target_memory_mars.log"; then
    echo "[ok] TIM-MARS ready"
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo "[error] TIM-MARS did not become ready"
  cat "$LOG_DIR/target_memory_mars.log" || true
  exit 3
fi

RAW_SELECTOR_PID=""
if [[ "$RAW_TARGET_MODE" == "selected_id" ]]; then
  echo "[info] starting clean selected-id raw target publisher"
  python3 "$THESIS_ROOT/tools/experiments/publish_selected_track_target.py" \
    --target-id "$TARGET_ID" \
    --tracks-topic /tracks \
    --target-topic /target \
    >"$LOG_DIR/selected_track_target.log" 2>&1 &
  RAW_SELECTOR_PID=$!
  sleep 2
elif [[ "$RAW_TARGET_MODE" == "annotation" ]]; then
  echo "[info] starting annotation-driven raw target publisher"
  python3 "$THESIS_ROOT/tools/experiments/publish_annotated_track_target.py" \
    --ros-args \
    -p annotation_csv:="$ANN_CSV" \
    -p tracks_topic:=/tracks \
    -p target_topic:=/target \
    >"$LOG_DIR/annotated_track_target.log" 2>&1 &
  RAW_SELECTOR_PID=$!
  sleep 2
elif [[ "$RAW_TARGET_MODE" != "source" ]]; then
  echo "[error] invalid RAW_TARGET_MODE=$RAW_TARGET_MODE; expected source, selected_id, or annotation" >&2
  exit 2
fi

echo "[info] starting recorder"
ros2 bag record -s mcap -o "$OUT_BAG" --topics \
  /camera/image_raw \
  /camera/dashboard \
  /tracks \
  /target \
  /target_memory_mars \
  /target_memory_mars/status \
  >"$LOG_DIR/record.log" 2>&1 &
REC_PID=$!

sleep 5

echo "[info] playing memory-only source topics"
# In source mode, replay /target from the bag.
# In selected_id/annotation modes, /target is generated by a helper publisher.
PLAY_TOPICS=(/camera/image_raw /camera/dashboard /tracks)
if [[ "$RAW_TARGET_MODE" == "source" ]]; then
  PLAY_TOPICS+=(/target)
fi

ros2 bag play "$BAG_PATH" \
  --topics "${PLAY_TOPICS[@]}" \
  --rate "$RATE" \
  --disable-keyboard-controls \
  >"$LOG_DIR/play.log" 2>&1 &
PLAY_PID=$!

wait "$PLAY_PID" || true

sleep 8

echo "[info] stopping recorder"
stop_pid_cleanly "$REC_PID" "recorder"
wait_for_metadata "$OUT_BAG" || true

if [[ -n "${RAW_SELECTOR_PID:-}" ]]; then
  echo "[info] stopping raw target publisher"
  stop_pid_cleanly "$RAW_SELECTOR_PID" "raw_target_publisher"
fi

echo "[info] stopping TIM-MARS"
stop_pid_cleanly "$TIM_PID" "target_memory_mars_node"

ros2 bag reindex "$OUT_BAG" >"$LOG_DIR/reindex.log" 2>&1 || true
ros2 bag info "$OUT_BAG" >"$LOG_DIR/bag_info.txt" 2>&1 || true

if ! rg -q "Topic: /target_memory_mars" "$LOG_DIR/bag_info.txt"; then
  echo "[error] output bag missing /target_memory_mars"
  cat "$LOG_DIR/bag_info.txt" || true
  exit 4
fi

echo "[info] evaluating target correctness"
python3 "$THESIS_ROOT/tools/analysis/evaluate_tim_target_correctness.py" \
  "$OUT_BAG" \
  --annotations "$ANN_CSV" \
  --out-dir "$REPORT_DIR" \
  --timebase header \
  >"$LOG_DIR/eval.log" 2>&1

echo "[ok] eval bag: $OUT_BAG"
echo "[ok] report:   $REPORT_DIR"
echo "[ok] logs:     $LOG_DIR"

cat "$REPORT_DIR/summary.md"
