#!/usr/bin/env bash
set +e

# Purpose:
# - Build a /camera/image_raw bag from an external dataset image folder
#   (DanceTrack, VisDrone-MOT).
# - Run the real thesis detector (Hailo YOLOv6n) and ByteTrack tracker
#   against it, live, exactly as run_one_detector_tim_replay.sh does for
#   recorded flight bags.
# - Record /camera/image_raw, /detections and /tracks into ONE output bag.
#
# No TIM-MARS, no dashboard bridge, no live target selection: this produces
# one shared detector/ByteTrack candidate stream per Issue #30's requirement
# that the raw baseline and TIM-MARS branches consume identical detections
# and tracks. tools/experiments/run_deterministic_tim_replay.py is the next
# step, run separately against this script's output bag, to deterministically
# generate the paired raw-versus-TIM-MARS streams from that one candidate
# stream.
#
if [[ $# -lt 3 ]]; then
  echo "Usage:"
  echo "  $0 <image_dir> <frame_rate_hz> <output_bag> [detector_model] [tracker]"
  exit 1
fi

IMAGE_DIR="$1"
FRAME_RATE="$2"
OUT_BAG="$3"
DETECTOR_MODEL="${4:-yolov8s}"
TRACKER="${5:-bytetrack}"

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
PLAY_RATE="${PLAY_RATE:-0.1}"
READ_AHEAD_QUEUE_SIZE="${READ_AHEAD_QUEUE_SIZE:-20}"
NODE_STARTUP_WAIT_S="${NODE_STARTUP_WAIT_S:-6}"
RECORDER_START_WAIT_S="${RECORDER_START_WAIT_S:-2}"
RECORDER_STOP_WAIT_S="${RECORDER_STOP_WAIT_S:-5}"

HEF_PATH="$THESIS_ROOT/models/hef/${DETECTOR_MODEL}.hef"
TRACKER_CONFIG="$THESIS_ROOT/ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tracker_${TRACKER}.yaml"

if [[ ! -f "$HEF_PATH" ]]; then
  echo "[error] detector HEF not found: $HEF_PATH"
  exit 2
fi

if [[ ! -f "$TRACKER_CONFIG" ]]; then
  echo "[error] tracker config not found: $TRACKER_CONFIG"
  exit 3
fi

if [[ -e "$OUT_BAG" ]]; then
  echo "[error] output bag already exists: $OUT_BAG"
  exit 4
fi

SOURCE_BAG="${OUT_BAG}__source"
LOG_DIR="${LOG_DIR:-$THESIS_ROOT/ros2_ws/log/p030_external_capture/$(basename "$OUT_BAG")}"
mkdir -p "$LOG_DIR" "$(dirname "$OUT_BAG")"

source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
export ROS_DOMAIN_ID

echo "[info] building source image bag: $SOURCE_BAG"
python3 "$THESIS_ROOT/tools/experiments/images_to_camera_bag.py" \
  "$IMAGE_DIR" "$SOURCE_BAG" --frame-rate "$FRAME_RATE" \
  > "$LOG_DIR/images_to_bag.log" 2>&1
BUILD_STATUS=$?
if [[ $BUILD_STATUS -ne 0 ]]; then
  echo "[error] failed to build source bag, see $LOG_DIR/images_to_bag.log"
  exit 5
fi

cleanup() {
  pkill -f "ros2 bag play|ros2 bag record|perception_pipeline_node|tracker_node" 2>/dev/null
}
trap cleanup EXIT

pkill -f "ros2 bag play|ros2 bag record|perception_pipeline_node|tracker_node" 2>/dev/null
sleep 2

echo "[info] starting detector: $DETECTOR_MODEL"
ros2 run thesis_bringup perception_pipeline_node --ros-args \
  -p image_topic:=/camera/image_raw \
  -p img_w:=640 -p img_h:=640 \
  -p label:=person -p min_score:=0.35 \
  -p inference_backend:=hailo_direct \
  -p hailo_hef_path:="$HEF_PATH" \
  -p publish_timing:=true -p infer_timeout_ms:=300 \
  -p allow_stub_fallback:=false -p frame_queue_size:=1 \
  -p image_qos_depth:=2 -p async_max_inflight:=1 -p num_workers:=1 \
  > "$LOG_DIR/detector.log" 2>&1 &

echo "[info] starting tracker: $TRACKER"
ros2 run thesis_tracker tracker_node --ros-args \
  --params-file "$TRACKER_CONFIG" \
  > "$LOG_DIR/tracker.log" 2>&1 &

sleep "$NODE_STARTUP_WAIT_S"

echo "[info] checking free disk space"
MIN_FREE_GIB="${MIN_FREE_GIB:-25}"
AVAILABLE_GIB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
if (( AVAILABLE_GIB < MIN_FREE_GIB )); then
  echo "[error] only ${AVAILABLE_GIB}GiB free, refusing to record (minimum ${MIN_FREE_GIB}GiB)"
  exit 6
fi

echo "[info] starting recorder (zstd-compressed)"
ros2 bag record -s mcap -o "$OUT_BAG" \
  --compression-mode file --compression-format zstd \
  --topics /camera/image_raw /detections /tracks \
  > "$LOG_DIR/record.log" 2>&1 &
REC_PID=$!
sleep "$RECORDER_START_WAIT_S"

echo "[info] playing source bag at rate=$PLAY_RATE (read-ahead-queue-size=$READ_AHEAD_QUEUE_SIZE)"
ros2 bag play "$SOURCE_BAG" --topics /camera/image_raw --rate "$PLAY_RATE" \
  --read-ahead-queue-size "$READ_AHEAD_QUEUE_SIZE" \
  > "$LOG_DIR/play.log" 2>&1
PLAY_STATUS=$?
if [[ $PLAY_STATUS -ne 0 ]]; then
  echo "[error] ros2 bag play exited with status $PLAY_STATUS, see $LOG_DIR/play.log"
  kill -INT "$REC_PID" 2>/dev/null
  wait "$REC_PID" 2>/dev/null
  rm -rf "$SOURCE_BAG"
  exit 7
fi

sleep "$RECORDER_STOP_WAIT_S"
kill -INT "$REC_PID" 2>/dev/null

for _ in $(seq 1 30); do
  if ! kill -0 "$REC_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if kill -0 "$REC_PID" >/dev/null 2>&1; then
  kill "$REC_PID" 2>/dev/null
  sleep 2
fi

wait "$REC_PID" 2>/dev/null

rm -rf "$SOURCE_BAG"

echo "[ok] capture bag: $OUT_BAG"
echo "[ok] logs: $LOG_DIR"
