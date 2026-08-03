#!/usr/bin/env bash

# Controlled Issue #44 CPU candidate-policy correctness matrix.
#
# Conditions:
#   all_candidates at 250 ms
#   ambiguity_guarded at 250 ms
#
# Each condition is replayed over the same four canonical sequences.
# The existing memory-only replay wrapper performs correctness evaluation
# and records exact runtime provenance. This runner does not change the
# canonical YAML or enable RepVGG ranking, memory, or decision integration.

set +e
set +u
set -o pipefail

THESIS_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." &&
    pwd
)" || exit 1

cd "$THESIS_ROOT" || exit 1

export GIT_PAGER=cat
export PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

RUN_SUFFIX="${1:-r1}"
RATE="${2:-1.0}"
PREFLIGHT_ONLY="${P044_PREFLIGHT_ONLY:-false}"

WRAPPER="$THESIS_ROOT/tools/experiments/run_one_memory_tim_replay.sh"
CANONICAL="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"

GIT_HEAD="$(git rev-parse HEAD)"
SHORT_HEAD="$(git rev-parse --short=8 HEAD)"
DATE_TAG="$(date +%Y_%m_%d)"

RUN_TAG="p044_guarded_cpu_matrix_${SHORT_HEAD}_${DATE_TAG}_${RUN_SUFFIX}"

OUT_ROOT="$THESIS_ROOT/bags/replay/$RUN_TAG"
REPORT_ROOT="$THESIS_ROOT/reports/$RUN_TAG"
LOG_ROOT="$THESIS_ROOT/ros2_ws/log/$RUN_TAG"

RUN_STATUS_TSV="$REPORT_ROOT/run_status.tsv"
RUN_MANIFEST="$REPORT_ROOT/run_manifest.json"
EXECUTION_SUMMARY="$REPORT_ROOT/execution_summary.json"

overall_status=0

sequence_names=(
  "may_hard_reentry"
  "seq01_clean"
  "seq03_crossing"
  "seq04_occlusion"
)

sequence_bags=(
  "$THESIS_ROOT/bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1"
  "$THESIS_ROOT/bags/source/official_flights/2026-06-19/seq01_clean_four_person/full_pipeline/2026-06-19__12-45-45__video__2026-06-19__official__seq01__clean_four_person__yolov8s_bytetrack_tim_mars"
  "$THESIS_ROOT/bags/replay/p006b_hard_negative_03409564_2026_07_21/seq03"
  "$THESIS_ROOT/bags/replay/p006b_hard_negative_03409564_2026_07_21/seq04"
)

sequence_annotations=(
  "$THESIS_ROOT/docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv"
  "$THESIS_ROOT/docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv"
  "$THESIS_ROOT/docs/data/annotations/june_hard_sequences/seq03_ocsort_305578f3.csv"
  "$THESIS_ROOT/docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv"
)

sequence_target_ids=(
  "1"
  "1"
  "1"
  "1"
)

matching_runtime_processes() {
  pgrep -af \
    '/thesis_bringup/perception_pipeline_node|/thesis_bringup/target_memory_mars_node|ros2 bag play|ros2 bag record' \
    2>/dev/null |
    awk -v self="$$" '$1 != self {print}' ||
    true
}

cleanup_runtime_processes() {
  local pids=""

  pids="$(
    matching_runtime_processes |
      awk '{print $1}' |
      sort -u
  )"

  if [ -n "$pids" ]; then
    printf '%s\n' "$pids" |
      xargs -r kill -INT 2>/dev/null
    sleep 2

    pids="$(
      matching_runtime_processes |
        awk '{print $1}' |
        sort -u
    )"

    if [ -n "$pids" ]; then
      printf '%s\n' "$pids" |
        xargs -r kill -TERM 2>/dev/null
      sleep 2
    fi
  fi
}

printf '\n===== Issue #44 guarded CPU matrix preflight =====\n'
printf 'git HEAD:      %s\n' "$GIT_HEAD"
printf 'run tag:       %s\n' "$RUN_TAG"
printf 'rate:          %s\n' "$RATE"
printf 'preflight:     %s\n' "$PREFLIGHT_ONLY"
printf 'output root:   %s\n' "$OUT_ROOT"
printf 'report root:   %s\n' "$REPORT_ROOT"
printf 'log root:      %s\n' "$LOG_ROOT"

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: tracked repository is not clean.\n'
  overall_status=1
fi

if [ ! -x "$WRAPPER" ]; then
  printf 'ERROR: replay wrapper is absent or not executable.\n'
  overall_status=1
fi

if [ ! -f "$CANONICAL" ]; then
  printf 'ERROR: canonical configuration is absent.\n'
  overall_status=1
fi

if [ ! -f "$MARS_MODEL" ]; then
  printf 'ERROR: CPU MARS model is absent.\n'
  overall_status=1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  overall_status=1
fi

if [ -n "$(matching_runtime_processes)" ]; then
  printf 'ERROR: matching runtime processes are already active.\n'
  matching_runtime_processes
  overall_status=1
fi

python3 - "$RATE" <<'PY'
import math
import sys

try:
    rate = float(sys.argv[1])
except ValueError as exc:
    raise SystemExit(f"ERROR: invalid replay rate: {exc}")

if not math.isfinite(rate) or rate <= 0.0:
    raise SystemExit("ERROR: replay rate must be finite and positive.")

print(f"PASS: replay rate validated as {rate}.")
PY
rate_status=$?

if [ "$rate_status" -ne 0 ]; then
  overall_status=1
fi

for index in "${!sequence_names[@]}"; do
  name="${sequence_names[$index]}"
  bag="${sequence_bags[$index]}"
  annotation="${sequence_annotations[$index]}"

  if [ ! -d "$bag" ]; then
    printf 'ERROR: input bag is absent for %s: %s\n' \
      "$name" \
      "$bag"
    overall_status=1
  fi

  if [ ! -f "$annotation" ]; then
    printf 'ERROR: annotation is absent for %s: %s\n' \
      "$name" \
      "$annotation"
    overall_status=1
  fi
done

if [ "$PREFLIGHT_ONLY" != "true" ]; then
  for path in "$OUT_ROOT" "$REPORT_ROOT" "$LOG_ROOT"; do
    if [ -e "$path" ]; then
      printf 'ERROR: output path already exists: %s\n' "$path"
      overall_status=1
    fi
  done
fi

if [ "$overall_status" -ne 0 ]; then
  printf 'ABORT: matrix preflight failed.\n'
  exit "$overall_status"
fi

if [ "$PREFLIGHT_ONLY" = "true" ]; then
  printf 'PASS: guarded matrix preflight completed without creating outputs.\n'
  exit 0
fi

source /opt/ros/jazzy/setup.bash
ros_status=$?

source "$THESIS_ROOT/ros2_ws/install/setup.bash"
workspace_status=$?

if [ "$ros_status" -ne 0 ] ||
   [ "$workspace_status" -ne 0 ]; then
  printf 'ERROR: ROS environment setup failed.\n'
  exit 1
fi

mkdir -p "$OUT_ROOT" "$REPORT_ROOT" "$LOG_ROOT"

printf 'condition\tsequence\tstatus\toutput_bag\treport_dir\tlog_file\n' \
  > "$RUN_STATUS_TSV"

python3 - \
  "$RUN_MANIFEST" \
  "$THESIS_ROOT" \
  "$GIT_HEAD" \
  "$RUN_TAG" \
  "$RATE" \
  "$CANONICAL" \
  "$WRAPPER" <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys


(
    output_value,
    root_value,
    git_head,
    run_tag,
    rate_value,
    canonical_value,
    wrapper_value,
) = sys.argv[1:]

root = Path(root_value)
canonical = Path(canonical_value)
wrapper = Path(wrapper_value)

payload = {
    "schema": "p044_guarded_cpu_matrix_manifest_v1",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "git_head": git_head,
    "run_tag": run_tag,
    "rate": float(rate_value),
    "canonical_config": {
        "path": str(canonical.relative_to(root)),
        "sha256": hashlib.sha256(
            canonical.read_bytes()
        ).hexdigest(),
        "appearance_request_policy": "all_candidates",
        "appearance_compute_min_interval_ms": 250.0,
    },
    "runner": (
        "tools/experiments/"
        "run_p044_guarded_cpu_policy_matrix.sh"
    ),
    "wrapper": str(wrapper.relative_to(root)),
    "conditions": [
        {
            "slug": "all_candidates_250ms",
            "appearance_request_policy": "all_candidates",
            "appearance_compute_min_interval_ms": 250.0,
        },
        {
            "slug": "ambiguity_guarded_250ms",
            "appearance_request_policy": "ambiguity_guarded",
            "appearance_compute_min_interval_ms": 250.0,
        },
    ],
    "sequences": [
        {
            "name": "may_hard_reentry",
            "target_id": 1,
            "input_bag": (
                "bags/reference/tim_good/"
                "2026-05-14__hard_reentry__bytetrack__"
                "tim_mars_v4_margin010__target_1"
            ),
            "annotation_csv": (
                "docs/data/annotations/may_hard_reentry/"
                "bytetrack_hard_reentry.csv"
            ),
        },
        {
            "name": "seq01_clean",
            "target_id": 1,
            "input_bag": (
                "bags/source/official_flights/2026-06-19/"
                "seq01_clean_four_person/full_pipeline/"
                "2026-06-19__12-45-45__video__2026-06-19__"
                "official__seq01__clean_four_person__"
                "yolov8s_bytetrack_tim_mars"
            ),
            "annotation_csv": (
                "docs/data/annotations/june_hard_sequences/"
                "seq01_bytetrack.csv"
            ),
        },
        {
            "name": "seq03_crossing",
            "target_id": 1,
            "input_bag": (
                "bags/replay/"
                "p006b_hard_negative_03409564_2026_07_21/"
                "seq03"
            ),
            "annotation_csv": (
                "docs/data/annotations/june_hard_sequences/"
                "seq03_ocsort_305578f3.csv"
            ),
        },
        {
            "name": "seq04_occlusion",
            "target_id": 1,
            "input_bag": (
                "bags/replay/"
                "p006b_hard_negative_03409564_2026_07_21/"
                "seq04"
            ),
            "annotation_csv": (
                "docs/data/annotations/june_hard_sequences/"
                "seq04_ocsort_305578f3.csv"
            ),
        },
    ],
    "execution_order": (
        "paired by sequence with alternating first condition"
    ),
    "claim_boundary": {
        "cpu_mars_authoritative": True,
        "repvgg_ranking_enabled": False,
        "repvgg_memory_enabled": False,
        "repvgg_decision_integration_enabled": False,
        "canonical_policy_changed": False,
    },
}

Path(output_value).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
manifest_status=$?

if [ "$manifest_status" -ne 0 ]; then
  printf 'ERROR: could not write run manifest.\n'
  exit "$manifest_status"
fi

trap cleanup_runtime_processes EXIT INT TERM

printf '\n===== Execute paired matrix =====\n'

for sequence_index in "${!sequence_names[@]}"; do
  sequence="${sequence_names[$sequence_index]}"
  bag="${sequence_bags[$sequence_index]}"
  annotation="${sequence_annotations[$sequence_index]}"
  target_id="${sequence_target_ids[$sequence_index]}"

  if [ $((sequence_index % 2)) -eq 0 ]; then
    policies=(
      "all_candidates"
      "ambiguity_guarded"
    )
  else
    policies=(
      "ambiguity_guarded"
      "all_candidates"
    )
  fi

  for policy in "${policies[@]}"; do
    condition="${policy}_250ms"

    condition_out="$OUT_ROOT/$condition"
    condition_report="$REPORT_ROOT/$condition"
    condition_log="$LOG_ROOT/$condition"

    run_report="$condition_report/$sequence"
    run_output="$condition_out/$sequence"
    run_log_dir="$condition_log/$sequence"
    run_log="$run_log_dir/wrapper.log"

    mkdir -p "$run_log_dir"

    printf '\n--- %s / %s ---\n' "$condition" "$sequence"

    RAW_TARGET_MODE="source" \
    TIM_MIRROR_RAW_TARGET_SELECTION="false" \
    TIM_MARS_CONFIG="$CANONICAL" \
    MARS_MODEL_PATH="$MARS_MODEL" \
    TIM_APPEARANCE_REQUEST_POLICY="$policy" \
    TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS="250" \
    TIM_REPLAY_OUT_ROOT="$condition_out" \
    TIM_REPLAY_REPORT_ROOT="$condition_report" \
    TIM_REPLAY_LOG_ROOT="$condition_log" \
    ROS_DOMAIN_ID="44" \
      "$WRAPPER" \
        "$bag" \
        "$target_id" \
        "$sequence" \
        "$annotation" \
        "$RATE" \
        > "$run_log" 2>&1
    run_status=$?

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$condition" \
      "$sequence" \
      "$run_status" \
      "$run_output" \
      "$run_report" \
      "$run_log" \
      >> "$RUN_STATUS_TSV"

    if [ "$run_status" -ne 0 ]; then
      printf 'ERROR: replay failed for %s / %s.\n' \
        "$condition" \
        "$sequence"
      tail -n 120 "$run_log"
      overall_status=1
      break 2
    fi

    for required in \
      "$run_output" \
      "$run_report/summary.csv" \
      "$run_report/summary.md" \
      "$run_report/run_metadata.json" \
      "$run_report/tim_mars_resolved_runtime.json"
    do
      if [ ! -e "$required" ]; then
        printf 'ERROR: expected run output is absent: %s\n' \
          "$required"
        overall_status=1
      fi
    done

    if [ "$overall_status" -ne 0 ]; then
      break 2
    fi

    sleep 2

    lingering="$(matching_runtime_processes)"

    if [ -n "$lingering" ]; then
      printf 'ERROR: runtime processes remain after %s / %s:\n%s\n' \
        "$condition" \
        "$sequence" \
        "$lingering"
      overall_status=1
      break 2
    fi
  done
done

python3 - \
  "$RUN_STATUS_TSV" \
  "$EXECUTION_SUMMARY" \
  "$RUN_TAG" \
  "$GIT_HEAD" \
  "$overall_status" <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import sys


status_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
run_tag = sys.argv[3]
git_head = sys.argv[4]
overall_status = int(sys.argv[5])

rows = []

if status_path.is_file():
    with status_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(
            csv.DictReader(
                stream,
                delimiter="\t",
            )
        )

payload = {
    "schema": "p044_guarded_cpu_matrix_execution_v1",
    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_tag": run_tag,
    "git_head": git_head,
    "expected_runs": 8,
    "observed_runs": len(rows),
    "successful_runs": sum(
        int(row["status"]) == 0
        for row in rows
    ),
    "overall_status": overall_status,
    "runs": rows,
}

output_path.write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
summary_status=$?

if [ "$summary_status" -ne 0 ]; then
  overall_status=1
fi

printf '\n===== Final hygiene =====\n'

cleanup_runtime_processes

remaining="$(matching_runtime_processes)"

if [ -n "$remaining" ]; then
  printf 'ERROR: matrix processes remain:\n%s\n' "$remaining"
  overall_status=1
else
  printf 'PASS: no matrix processes remain.\n'
fi

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: tracked repository changed during the matrix.\n'
  git status --short
  overall_status=1
fi

if [ -e log ]; then
  printf 'ERROR: root log/ exists.\n'
  overall_status=1
else
  printf 'PASS: no root log/ exists.\n'
fi

if [ -e hailort.log ]; then
  printf 'ERROR: root hailort.log exists.\n'
  overall_status=1
else
  printf 'PASS: no root hailort.log exists.\n'
fi

printf '\n===== Matrix result =====\n'
printf 'run tag:        %s\n' "$RUN_TAG"
printf 'report root:    %s\n' "$REPORT_ROOT"
printf 'output root:    %s\n' "$OUT_ROOT"
printf 'log root:       %s\n' "$LOG_ROOT"
printf 'summary status: %s\n' "$summary_status"
printf 'overall status: %s\n' "$overall_status"

if [ "$overall_status" -eq 0 ]; then
  printf 'PASS: all eight guarded correctness runs completed.\n'
  printf 'Next: analyse CPU workload and aggregate correctness deltas.\n'
else
  printf 'ATTENTION: inspect run_status.tsv and the failing wrapper log.\n'
fi

exit "$overall_status"
