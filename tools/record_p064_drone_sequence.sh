#!/usr/bin/env bash

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
cd "$THESIS_ROOT" || exit 1

scenario="${1:-}"

if [[ -z "$scenario" ]]; then
    echo "Usage: tools/record_p064_drone_sequence.sh <scenario>"
    echo "Example: tools/record_p064_drone_sequence.sh small_target_r1"
    exit 1
fi

if [[ ! "$scenario" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "[error] scenario may contain only letters, numbers, '_' and '-'"
    exit 1
fi

export GIT_PAGER=cat
export PAGER=cat

export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

export SOURCE_RECORD_ROOT="${SOURCE_RECORD_ROOT:-/dev/shm/p064_source_video}"
export RAW_RECORDING_MIN_FREE_GIB="${RAW_RECORDING_MIN_FREE_GIB:-3}"
export RUN_ID="${RUN_ID:-$(date +%F__%H-%M-%S)}"

tag="p064_drone_${scenario}"
source_bag="$SOURCE_RECORD_ROOT/${RUN_ID}__source__${tag}__image_raw_detections"
final_bag="$THESIS_ROOT/bags/source_video/$(basename "$source_bag")"

mkdir -p "$SOURCE_RECORD_ROOT" "$THESIS_ROOT/bags/source_video"

echo
echo "============================================================"
echo "Issue #64 representative drone capture"
echo "============================================================"
echo "Source:   native 1280x720 HD"
echo "Detector: YOLOv8s, inference remains 640x640"
echo "Replay:   ByteTrack + TIM-MARS generated deterministically afterward"
echo "Record:   /camera/image_raw + /detections"
echo "RAM bag:  $source_bag"
echo
echo "Scene:"
echo "  1. target clearly visible with >=1 distractor"
echo "  2. move from larger/medium target to genuinely small drone scale"
echo "  3. include crossing or partial occlusion"
echo "  4. include target exit / disappearance"
echo "  5. include re-entry with distractor visible"
echo "  6. keep recording a few seconds after reacquisition"
echo
echo "No target selection or 'ids' command is required during source capture."
echo "Keep the run short. Type 'stop' at the live-stack prompt when done."
echo "============================================================"
echo

"$THESIS_ROOT/tools/start_live_stack.sh" \
    --res hd \
    --source-record-no-mavros \
    --detector-model yolov8s \
    --tag "$tag"

launcher_status=$?

if [[ "$launcher_status" -ne 0 ]]; then
    echo "[error] live stack exited with status $launcher_status"
    echo "[info] RAM evidence, if any, remains under $SOURCE_RECORD_ROOT"
    exit "$launcher_status"
fi

if [[ ! -d "$source_bag" ]]; then
    echo "[error] expected RAM-backed source bag was not found:"
    echo "        $source_bag"
    exit 1
fi

if [[ -e "$final_bag" ]]; then
    echo "[error] refusing to overwrite existing final bag:"
    echo "        $final_bag"
    echo "[info] RAM source remains at:"
    echo "       $source_bag"
    exit 1
fi

echo
echo "[copy] preserving completed capture under bags/source_video/"
cp -a "$source_bag" "$final_bag"

copy_status=$?
if [[ "$copy_status" -ne 0 ]]; then
    echo "[error] copy failed; RAM source has NOT been removed:"
    echo "        $source_bag"
    exit "$copy_status"
fi

source_bytes="$(du -sb "$source_bag" | awk '{print $1}')"
final_bytes="$(du -sb "$final_bag" | awk '{print $1}')"

if [[ "$source_bytes" != "$final_bytes" ]]; then
    echo "[error] copied directory size does not match RAM source"
    echo "        RAM:   $source_bytes bytes"
    echo "        FINAL: $final_bytes bytes"
    echo "[info] RAM source has NOT been removed"
    exit 1
fi

echo
echo "============================================================"
echo "CAPTURE PRESERVED"
echo "============================================================"
echo "Final bag:"
echo "  $final_bag"
echo
echo "RAM source retained for safety:"
echo "  $source_bag"
echo
echo "Do not delete either copy until the bag has been validated."
echo "============================================================"
