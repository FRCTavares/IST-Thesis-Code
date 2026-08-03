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
  echo "Issue #44 appearance controls:"
  echo "  TIM_APPEARANCE_REQUEST_POLICY=all_candidates|geometry_winner|ambiguity_guarded"
  echo "  TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS=<non-negative milliseconds>"
  echo "  Unset controls are resolved from TIM_MARS_CONFIG."
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

printf -v RUN_COMMAND '%q ' "$0" "$@"
RUN_COMMAND="${RUN_COMMAND% }"

if [[ -n "${THESIS_ROOT+x}" ]]; then
  THESIS_ROOT_SOURCE="environment"
else
  THESIS_ROOT_SOURCE="runner_default"
fi
THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"

if [[ -n "${ROS_DOMAIN_ID+x}" ]]; then
  ROS_DOMAIN_ID_SOURCE="environment"
else
  ROS_DOMAIN_ID_SOURCE="runner_default"
fi
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

if [[ -n "${TIM_REPLAY_OUT_ROOT+x}" ]]; then
  OUT_ROOT_SOURCE="environment"
else
  OUT_ROOT_SOURCE="runner_default"
fi
OUT_ROOT="${TIM_REPLAY_OUT_ROOT:-$THESIS_ROOT/bags/replay/memory_tim_safety_eval}"

if [[ -n "${TIM_REPLAY_REPORT_ROOT+x}" ]]; then
  REPORT_ROOT_SOURCE="environment"
else
  REPORT_ROOT_SOURCE="runner_default"
fi
REPORT_ROOT="${TIM_REPLAY_REPORT_ROOT:-$THESIS_ROOT/reports/memory_tim_safety_eval}"

if [[ -n "${TIM_REPLAY_LOG_ROOT+x}" ]]; then
  LOG_ROOT_SOURCE="environment"
else
  LOG_ROOT_SOURCE="runner_default"
fi
LOG_ROOT="${TIM_REPLAY_LOG_ROOT:-$THESIS_ROOT/ros2_ws/log/memory_tim_safety_eval}"

OUT_BAG="$OUT_ROOT/$RUN_NAME"
REPORT_DIR="$REPORT_ROOT/$RUN_NAME"
LOG_DIR="$LOG_ROOT/$RUN_NAME"

if [[ -n "${MARS_MODEL_PATH+x}" ]]; then
  MARS_MODEL_PATH_SOURCE="environment"
else
  MARS_MODEL_PATH_SOURCE="runner_default"
fi
MARS_MODEL_PATH="${MARS_MODEL_PATH:-$THESIS_ROOT/models/reid/mars-small128.pb}"

if [[ -n "${TIM_MARS_CONFIG+x}" ]]; then
  TIM_MARS_CONFIG_SOURCE="environment"
else
  TIM_MARS_CONFIG_SOURCE="runner_default"
fi
TIM_MARS_CONFIG="${TIM_MARS_CONFIG:-$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml}"
TIM_METADATA_HELPER="$THESIS_ROOT/tools/experiments/write_tim_run_metadata.py"

# RAW_TARGET_MODE controls how /target is produced during replay:
#   source      -> replay original /target from the input bag
#   selected_id -> synthesize /target from a fixed tracker ID
#   annotation  -> synthesize /target from annotation CSV + /tracks
if [[ -n "${RAW_TARGET_MODE+x}" ]]; then
  RAW_TARGET_MODE_SOURCE="environment"
else
  RAW_TARGET_MODE_SOURCE="runner_default"
fi
RAW_TARGET_MODE="${RAW_TARGET_MODE:-source}"

if [[ -n "${MARS_APPEARANCE_IMAGE_TOPIC+x}" ]]; then
  REQUESTED_APPEARANCE_IMAGE_TOPIC="$MARS_APPEARANCE_IMAGE_TOPIC"
  APPEARANCE_IMAGE_TOPIC_REQUEST_SOURCE="MARS_APPEARANCE_IMAGE_TOPIC"
elif [[ -n "${TIM_APPEARANCE_IMAGE_TOPIC+x}" ]]; then
  REQUESTED_APPEARANCE_IMAGE_TOPIC="$TIM_APPEARANCE_IMAGE_TOPIC"
  APPEARANCE_IMAGE_TOPIC_REQUEST_SOURCE="TIM_APPEARANCE_IMAGE_TOPIC"
else
  REQUESTED_APPEARANCE_IMAGE_TOPIC=""
  APPEARANCE_IMAGE_TOPIC_REQUEST_SOURCE="auto_detect"
fi

# false: TIM starts from selected_track_id and must recover ID switches itself.
# true:  TIM mirrors /target reselection events, useful for preservation/oracle tests.
if [[ -n "${TIM_MIRROR_RAW_TARGET_SELECTION+x}" ]]; then
  TIM_MIRROR_RAW_TARGET_SELECTION_SOURCE="environment"
else
  TIM_MIRROR_RAW_TARGET_SELECTION_SOURCE="runner_default"
fi
TIM_MIRROR_RAW_TARGET_SELECTION="${TIM_MIRROR_RAW_TARGET_SELECTION:-false}"

if [[ ! -f "$TIM_MARS_CONFIG" ]]; then
  echo "[error] canonical TIM-MARS config not found: $TIM_MARS_CONFIG" >&2
  exit 1
fi

CANONICAL_APPEARANCE_REQUEST_POLICY="$(
  awk \
    '$1 == "appearance_request_policy:" { print $2; exit }' \
    "$TIM_MARS_CONFIG"
)"
CANONICAL_APPEARANCE_COMPUTE_MIN_INTERVAL_MS="$(
  awk \
    '$1 == "appearance_compute_min_interval_ms:" { print $2; exit }' \
    "$TIM_MARS_CONFIG"
)"

if [[ -z "$CANONICAL_APPEARANCE_REQUEST_POLICY" ]]; then
  echo "[error] appearance_request_policy missing from $TIM_MARS_CONFIG" >&2
  exit 1
fi

if [[ -z "$CANONICAL_APPEARANCE_COMPUTE_MIN_INTERVAL_MS" ]]; then
  echo "[error] appearance_compute_min_interval_ms missing from $TIM_MARS_CONFIG" >&2
  exit 1
fi

if [[ -n "${TIM_APPEARANCE_REQUEST_POLICY:-}" ]]; then
  TIM_APPEARANCE_REQUEST_POLICY_SOURCE="environment"
else
  TIM_APPEARANCE_REQUEST_POLICY_SOURCE="canonical_config"
fi

TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE="${TIM_APPEARANCE_REQUEST_POLICY:-$CANONICAL_APPEARANCE_REQUEST_POLICY}"

case "$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" in
  all_candidates|geometry_winner|ambiguity_guarded)
    ;;
  *)
    printf \
      '[error] invalid TIM_APPEARANCE_REQUEST_POLICY=%s; expected all_candidates, geometry_winner, or ambiguity_guarded\n' \
      "$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" \
      >&2
    exit 2
    ;;
esac

if [[ -n "${TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS:-}" ]]; then
  TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE="environment"
else
  TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE="canonical_config"
fi

TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE="${TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS:-$CANONICAL_APPEARANCE_COMPUTE_MIN_INTERVAL_MS}"

if ! [[ "$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" =~ ^[0-9]+([.][0-9]*)?$ ]]; then
  printf \
    '[error] invalid TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS=%s; expected a non-negative numeric value\n' \
    "$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" \
    >&2
  exit 2
fi

# rclpy infers a parameter override without a decimal point as INTEGER.
# The ROS parameter is declared as DOUBLE, so preserve numeric meaning while
# ensuring values such as "0" and "250" are forwarded as "0.0" and "250.0".
if [[ "$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" != *.* ]]; then
  TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE="${TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE}.0"
fi

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
echo "[info] TIM_MARS_CONFIG=$TIM_MARS_CONFIG"
echo "[info] TIM_MARS_CONFIG_SOURCE=$TIM_MARS_CONFIG_SOURCE"
echo "[info] RAW_TARGET_MODE=$RAW_TARGET_MODE"
echo "[info] RAW_TARGET_MODE_SOURCE=$RAW_TARGET_MODE_SOURCE"
echo "[info] TIM_MIRROR_RAW_TARGET_SELECTION=$TIM_MIRROR_RAW_TARGET_SELECTION"
echo "[info] TIM_MIRROR_RAW_TARGET_SELECTION_SOURCE=$TIM_MIRROR_RAW_TARGET_SELECTION_SOURCE"
echo "[info] TIM_APPEARANCE_REQUEST_POLICY=$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE"
echo "[info] TIM_APPEARANCE_REQUEST_POLICY_SOURCE=$TIM_APPEARANCE_REQUEST_POLICY_SOURCE"
echo "[info] TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS=$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE"
echo "[info] TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE=$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE"

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

if [[ -n "$REQUESTED_APPEARANCE_IMAGE_TOPIC" ]]; then
  TIM_APPEARANCE_IMAGE_TOPIC="$REQUESTED_APPEARANCE_IMAGE_TOPIC"
  TIM_APPEARANCE_IMAGE_TOPIC_SOURCE="$APPEARANCE_IMAGE_TOPIC_REQUEST_SOURCE"
else
  BAG_INFO="$(ros2 bag info "$BAG_PATH" 2>/dev/null)"

  if grep -Fq "Topic: /camera/dashboard " <<<"$BAG_INFO"; then
    TIM_APPEARANCE_IMAGE_TOPIC="/camera/dashboard"
    TIM_APPEARANCE_IMAGE_TOPIC_SOURCE="bag_auto_detect_dashboard"
  elif grep -Fq "Topic: /camera/image_raw " <<<"$BAG_INFO"; then
    TIM_APPEARANCE_IMAGE_TOPIC="/camera/image_raw"
    TIM_APPEARANCE_IMAGE_TOPIC_SOURCE="bag_auto_detect_image_raw"
  else
    TIM_APPEARANCE_IMAGE_TOPIC="/camera/image_raw"
    TIM_APPEARANCE_IMAGE_TOPIC_SOURCE="runner_fallback_missing_topic"
    echo "[warn] input bag has no supported appearance image topic" >&2
  fi
fi

echo "[info] TIM_APPEARANCE_IMAGE_TOPIC=$TIM_APPEARANCE_IMAGE_TOPIC"
echo "[info] TIM_APPEARANCE_IMAGE_TOPIC_SOURCE=$TIM_APPEARANCE_IMAGE_TOPIC_SOURCE"

rm -rf "$OUT_BAG" "$REPORT_DIR" "$LOG_DIR"
mkdir -p "$OUT_ROOT" "$REPORT_DIR" "$LOG_DIR"

printf -v EFFECTIVE_RUN_COMMAND \
  'RAW_TARGET_MODE=%q TIM_MIRROR_RAW_TARGET_SELECTION=%q TIM_MARS_CONFIG=%q MARS_MODEL_PATH=%q TIM_APPEARANCE_IMAGE_TOPIC=%q TIM_APPEARANCE_REQUEST_POLICY=%q TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS=%q TIM_REPLAY_OUT_ROOT=%q TIM_REPLAY_REPORT_ROOT=%q TIM_REPLAY_LOG_ROOT=%q ROS_DOMAIN_ID=%q %s' \
  "$RAW_TARGET_MODE" \
  "$TIM_MIRROR_RAW_TARGET_SELECTION" \
  "$TIM_MARS_CONFIG" \
  "$MARS_MODEL_PATH" \
  "$TIM_APPEARANCE_IMAGE_TOPIC" \
  "$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" \
  "$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" \
  "$OUT_ROOT" \
  "$REPORT_ROOT" \
  "$LOG_ROOT" \
  "$ROS_DOMAIN_ID" \
  "$RUN_COMMAND"

python3 "$TIM_METADATA_HELPER" \
  --repo-root "$THESIS_ROOT" \
  --output-dir "$REPORT_DIR" \
  --config "$TIM_MARS_CONFIG" \
  --runner "$THESIS_ROOT/tools/experiments/run_one_memory_tim_replay.sh" \
  --command "$RUN_COMMAND" \
  --effective-command "$EFFECTIVE_RUN_COMMAND" \
  --runtime "tracks_topic=/tracks" \
  --runtime "mirror_target_topic=/target" \
  --runtime "target_topic=/target_memory_mars" \
  --runtime "status_topic=/target_memory_mars/status" \
  --runtime "select_topic=/target_memory_mars/select" \
  --runtime "selected_track_id=$TARGET_ID" \
  --runtime "mirror_raw_target_selection=$TIM_MIRROR_RAW_TARGET_SELECTION" \
  --runtime "appearance_image_topic=$TIM_APPEARANCE_IMAGE_TOPIC" \
  --runtime "appearance_request_policy=$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" \
  --runtime "appearance_compute_min_interval_ms=$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" \
  --runtime "mars_model_path=$MARS_MODEL_PATH" \
  --field "run_name=$RUN_NAME" \
  --field "bag_path=$BAG_PATH" \
  --field "output_bag=$OUT_BAG" \
  --field "annotation_csv=$ANN_CSV" \
  --field "target_id=$TARGET_ID" \
  --field "rate=$RATE" \
  --field "raw_target_mode=$RAW_TARGET_MODE" \
  --field "appearance_request_policy=$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" \
  --field "appearance_compute_min_interval_ms=$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" \
  --source "THESIS_ROOT=$THESIS_ROOT_SOURCE" \
  --source "ROS_DOMAIN_ID=$ROS_DOMAIN_ID_SOURCE" \
  --source "output_root=$OUT_ROOT_SOURCE" \
  --source "report_root=$REPORT_ROOT_SOURCE" \
  --source "log_root=$LOG_ROOT_SOURCE" \
  --source "mars_model_path=$MARS_MODEL_PATH_SOURCE" \
  --source "tim_mars_config=$TIM_MARS_CONFIG_SOURCE" \
  --source "raw_target_mode=$RAW_TARGET_MODE_SOURCE" \
  --source "mirror_raw_target_selection=$TIM_MIRROR_RAW_TARGET_SELECTION_SOURCE" \
  --source "appearance_image_topic=$TIM_APPEARANCE_IMAGE_TOPIC_SOURCE" \
  --source "appearance_request_policy=$TIM_APPEARANCE_REQUEST_POLICY_SOURCE" \
  --source "appearance_compute_min_interval_ms=$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE"

cleanup_ros
trap cleanup_ros EXIT

echo "[info] starting TIM-MARS memory-only node"

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
  -p appearance_request_policy:="$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE" \
  -p appearance_compute_min_interval_ms:="$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE" \
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
