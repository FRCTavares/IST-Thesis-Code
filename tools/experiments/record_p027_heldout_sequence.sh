#!/usr/bin/env bash

THESIS_ROOT="${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
cd "$THESIS_ROOT" || exit 1

export GIT_PAGER=cat
export PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

scenario="${1:-}"

case "$scenario" in
    h01)
        split_id="heldout_h01_exit_reentry"
        scenario_dir="h01_exit_reentry"
        tag="p027_h01_exit_reentry"
        ;;
    h02)
        split_id="heldout_h02_crossing"
        scenario_dir="h02_crossing"
        tag="p027_h02_crossing"
        ;;
    h03)
        split_id="heldout_h03_occlusion_distractor"
        scenario_dir="h03_occlusion_distractor"
        tag="p027_h03_occlusion_distractor"
        ;;
    *)
        echo "Usage: tools/experiments/record_p027_heldout_sequence.sh h01|h02|h03"
        exit 2
        ;;
esac

SPLIT_PATH="$THESIS_ROOT/docs/data/splits/tim_mars_split_v2.json"
SOURCE_RECORD_ROOT="$THESIS_ROOT/bags/source/held_out/2026-09/$scenario_dir"
RAW_RECORDING_MIN_FREE_GIB="${RAW_RECORDING_MIN_FREE_GIB:-40}"
RUN_ID="${RUN_ID:-$(date +%F__%H-%M-%S)}"

export SOURCE_RECORD_ROOT
export RAW_RECORDING_MIN_FREE_GIB
export RUN_ID

source_bag="$SOURCE_RECORD_ROOT/${RUN_ID}__source__${tag}__image_raw_detections"

echo
echo "============================================================"
echo "Issue #27 prospective held-out source capture"
echo "============================================================"
echo "Split entry: $split_id"
echo "Scenario:    $scenario"
echo "Resolution:  640x480 source imagery"
echo "Detector:    frozen YOLOv8s live detector, 640x640 inference"
echo "Record:      /camera/image_raw + /detections"
echo "Tracker:     OFF"
echo "TIM-MARS:    OFF"
echo "Control:     OFF"
echo "Dashboard:   OFF"
echo "MAVROS:      OFF"
echo "Output root: $SOURCE_RECORD_ROOT"
echo "Expected:    $source_bag"
echo
echo "IMPORTANT:"
echo "  This is prospective held-out evidence."
echo "  Do not inspect tracker/TIM correctness, candidate scores, or"
echo "  architecture outcomes before all H01-H03 source recordings,"
echo "  physical-v2 annotations, participant/outfit records, and hashes"
echo "  have passed the final release gate."
echo "============================================================"
echo

if [[ ! -f "$SPLIT_PATH" ]]; then
    echo "[error] active split manifest missing: $SPLIT_PATH"
    exit 1
fi

python3 "$THESIS_ROOT/tools/analysis/validate_tim_evaluation_split.py"     --verify-hashes
freeze_status=$?

if [[ "$freeze_status" -ne 0 ]]; then
    echo "[error] active prospective freeze validation failed"
    exit "$freeze_status"
fi

entry_status="$(
    python3 - "$SPLIT_PATH" "$split_id" <<'PY_INNER'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
wanted = sys.argv[2]

for entry in manifest["sets"]["final_held_out"]:
    if entry["id"] == wanted:
        print(entry["status"])
        break
else:
    raise SystemExit(f"held-out split entry not found: {wanted}")
PY_INNER
)"

if [[ "$entry_status" != "reserved_pending_capture" ]]; then
    echo "[error] split entry is not pending capture: $entry_status"
    echo "[error] refusing to create another retained held-out source"
    exit 1
fi

mkdir -p "$SOURCE_RECORD_ROOT"

if [[ -e "$source_bag" ]]; then
    echo "[error] refusing to overwrite existing source bag:"
    echo "        $source_bag"
    exit 1
fi

echo
echo "Physical scenario contract:"
case "$scenario" in
    h01)
        echo "  - begin with selected physical target clearly visible"
        echo "  - include at least one distractor"
        echo "  - target fully exits the image and remains absent for 5-8 s"
        echo "  - distractor remains visible during at least part of the absence"
        echo "  - target re-enters and stays visible for >=10 s"
        echo "  - do NOT inspect whether any tracker ID actually changed"
        ;;
    h02)
        echo "  - selected physical target + at least one distractor"
        echo "  - start clearly separated"
        echo "  - perform two close crossings"
        echo "  - include sustained overlap/near-overlap before separation"
        echo "  - keep recording >=10 s after the final separation"
        ;;
    h03)
        echo "  - selected physical target + at least one distractor"
        echo "  - target remains physically in the scene"
        echo "  - create partial then full visual occlusion"
        echo "  - keep a distractor visible near the target's last visible location"
        echo "  - reveal the same target again and retain >=10 s of clear visibility"
        echo "  - this is occlusion, not the full scene exit used by H01"
        ;;
esac

echo
echo "Type 'stop' at the live-stack prompt when the physical scenario is complete."
echo

"$THESIS_ROOT/tools/start_live_stack.sh"     --res vga     --source-record-no-mavros     --detector-model yolov8s     --tag "$tag"

launcher_status=$?

if [[ "$launcher_status" -ne 0 ]]; then
    echo "[error] live stack exited with status $launcher_status"
    echo "[info] retain any partial evidence; do not delete it silently"
    exit "$launcher_status"
fi

echo
echo "============================================================"
echo "CAPTURE COMPLETED — INTEGRITY INSPECTION ONLY"
echo "============================================================"

if [[ ! -d "$source_bag" ]]; then
    echo "[error] expected source bag was not found:"
    echo "        $source_bag"
    exit 1
fi

if [[ ! -f "$source_bag/metadata.yaml" ]]; then
    echo "[error] source bag metadata.yaml is missing"
    exit 1
fi

mcap_count="$(
    find "$source_bag" -maxdepth 1 -type f -name '*.mcap' | wc -l
)"
if [[ "$mcap_count" -lt 1 ]]; then
    echo "[error] source bag contains no finalized MCAP file"
    exit 1
fi

echo "Retained source:"
echo "  $source_bag"
echo
echo "Allowed now:"
echo "  - ros2 bag info / topic counts / duration / timestamps"
echo "  - camera-image quality review"
echo "  - verify the intended physical scenario occurred"
echo "  - physical-v2 annotation from source imagery"
echo "  - anonymous participant/outfit coding"
echo
echo "Forbidden now:"
echo "  - tracker correctness review"
echo "  - TIM-MARS correctness review"
echo "  - candidate-score inspection"
echo "  - threshold/model/tracker selection using this sequence"
echo "  - comparative architecture evaluation"
echo
echo "Do not rename or delete this retained source."
echo "============================================================"
