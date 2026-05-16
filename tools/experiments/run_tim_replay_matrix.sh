#!/usr/bin/env bash
set -eo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage:"
  echo "  $0 <bag_path> <target_id> [rate]"
  exit 1
fi

BAG_PATH="$1"
TARGET_ID="$2"
RATE="${3:-0.5}"

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"

TRACKERS=(sort ocsort bytetrack deepsort)
TIM_MODES=(off on)

for tracker in "${TRACKERS[@]}"; do
  for tim_mode in "${TIM_MODES[@]}"; do
    echo
    echo "============================================================"
    echo "RUN tracker=$tracker tim=$tim_mode target=$TARGET_ID"
    echo "============================================================"

    if ! "$THESIS_ROOT/tools/experiments/run_one_clean_tim_replay.sh" \
      "$BAG_PATH" \
      "$TARGET_ID" \
      "$tracker" \
      "$tim_mode" \
      "$RATE" \
      120; then
      echo "[warn] matrix run failed: tracker=$tracker tim=$tim_mode target=$TARGET_ID"
      echo "[warn] continuing with next configuration"
    fi
  done
done
