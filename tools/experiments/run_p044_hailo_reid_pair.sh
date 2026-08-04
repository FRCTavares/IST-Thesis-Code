#!/usr/bin/env bash

set +e
set +u
set -o pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 5 ]; then
  printf '%s\n' \
    "Usage:" \
    "  $0 <bag_path> <target_id> <run_name> [rate] [repetitions]" \
    "" \
    "Example:" \
    "  $0 bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1 1 hard_reentry 1.0 3"
  exit 2
fi

THESIS_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." &&
    pwd
)"

cd "$THESIS_ROOT" || {
  printf 'ERROR: could not enter thesis root.\n'
  exit 1
}

export GIT_PAGER=cat
export PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

BAG_PATH="$1"
TARGET_ID="$2"
RUN_NAME="$3"
RATE="${4:-1.0}"
REPETITIONS="${5:-1}"

ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-44}"
export ROS_DOMAIN_ID

DETECTOR_HEF="$THESIS_ROOT/models/hef/yolov6n.hef"
REID_HEF="$THESIS_ROOT/models/reid/repvgg_a0_person_reid_512.hef"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"
TIM_CONFIG="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
COLLECTOR="$THESIS_ROOT/tools/experiments/collect_p044_transport_evidence.py"

HEAD="$(git rev-parse HEAD)"
HEAD8="$(git rev-parse --short=8 HEAD)"
DATE_TAG="$(date +%Y_%m_%d)"

TAG="p044_hailo_reid_pair_${HEAD8}_${DATE_TAG}_${RUN_NAME}"
REPORT_ROOT="$THESIS_ROOT/reports/$TAG"
BAG_ROOT="$THESIS_ROOT/bags/replay/$TAG"
LOG_ROOT="$THESIS_ROOT/ros2_ws/log/$TAG"

overall_status=0
ACTIVE_PIDS=()

section() {
  printf '\n\n======================================================================\n'
  printf '%s\n' "$1"
  printf '======================================================================\n'
}

register_pid() {
  ACTIVE_PIDS+=("$1")
}

process_group_alive() {
  local group_id="$1"

  if [ -z "$group_id" ]; then
    return 1
  fi

  kill -0 -- "-$group_id" \
    >/dev/null 2>&1
}

stop_pid() {
  local pid="$1"
  local label="$2"

  if [ -z "$pid" ]; then
    return 0
  fi

  if ! process_group_alive "$pid"; then
    wait "$pid" >/dev/null 2>&1 || true
    return 0
  fi

  printf 'Stopping %s process group (pgid=%s)\n' \
    "$label" \
    "$pid"

  kill -INT -- "-$pid" \
    >/dev/null 2>&1 || true

  for _ in $(seq 1 40); do
    if ! process_group_alive "$pid"; then
      wait "$pid" >/dev/null 2>&1 || true
      return 0
    fi

    sleep 0.25
  done

  kill -TERM -- "-$pid" \
    >/dev/null 2>&1 || true

  for _ in $(seq 1 20); do
    if ! process_group_alive "$pid"; then
      wait "$pid" >/dev/null 2>&1 || true
      return 0
    fi

    sleep 0.25
  done

  kill -KILL -- "-$pid" \
    >/dev/null 2>&1 || true

  for _ in $(seq 1 12); do
    if ! process_group_alive "$pid"; then
      wait "$pid" >/dev/null 2>&1 || true
      return 0
    fi

    sleep 0.25
  done

  printf 'ERROR: %s process group remains active (pgid=%s).\n' \
    "$label" \
    "$pid"

  ps -eo pid=,pgid=,stat=,cmd= |
    awk -v group_id="$pid" \
      '$2 == group_id {print}'

  return 1
}

matching_smoke_pids() {
  pgrep -f \
    '/thesis_bringup/perception_pipeline_node|/thesis_bringup/target_memory_mars_node|collect_p044_transport_evidence.py|ros2 bag play|ros2 bag record' \
    2>/dev/null |
    awk -v self="$$" '$1 != self {print}' ||
    true
}

stop_matching_smoke_processes() {
  local signal
  local pids
  local pid

  for signal in INT TERM KILL; do
    pids="$(matching_smoke_pids)"

    if [ -z "$pids" ]; then
      return 0
    fi

    while IFS= read -r pid; do
      if [ -n "$pid" ]; then
        kill "-$signal" "$pid" \
          >/dev/null 2>&1 || true
      fi
    done <<< "$pids"

    for _ in $(seq 1 20); do
      if [ -z "$(matching_smoke_pids)" ]; then
        return 0
      fi

      sleep 0.25
    done
  done

  pids="$(matching_smoke_pids)"

  if [ -n "$pids" ]; then
    printf 'ERROR: unmatched smoke processes remain:\n%s\n' \
      "$pids"
    return 1
  fi

  return 0
}

cleanup_all() {
  local index
  local cleanup_status=0

  for ((index=${#ACTIVE_PIDS[@]}-1; index>=0; index--)); do
    stop_pid \
      "${ACTIVE_PIDS[$index]}" \
      "background process"

    if [ "$?" -ne 0 ]; then
      cleanup_status=1
    fi
  done

  ACTIVE_PIDS=()

  stop_matching_smoke_processes

  if [ "$?" -ne 0 ]; then
    cleanup_status=1
  fi

  return "$cleanup_status"
}

trap 'cleanup_all >/dev/null 2>&1 || true' INT TERM EXIT

section "1. Evidence preflight"

git status --branch --short
git status --short --untracked-files=all

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: tracked repository is not clean.\n'
  exit 1
fi

for path in \
  "$BAG_PATH" \
  "$DETECTOR_HEF" \
  "$REID_HEF" \
  "$MARS_MODEL" \
  "$TIM_CONFIG" \
  "$COLLECTOR"
do
  if [ ! -e "$path" ]; then
    printf 'ERROR: required path is absent: %s\n' "$path"
    overall_status=1
  fi
done

if ! [[ "$TARGET_ID" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR: target_id must be a positive integer.\n'
  overall_status=1
fi

if ! [[ "$RATE" =~ ^[0-9]+([.][0-9]*)?$ ]]; then
  printf 'ERROR: rate must be numeric.\n'
  overall_status=1
fi

if ! [[ "$REPETITIONS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'ERROR: repetitions must be a positive integer.\n'
  overall_status=1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  overall_status=1
fi

if ! command -v setsid >/dev/null 2>&1; then
  printf 'ERROR: setsid is unavailable.\n'
  overall_status=1
fi

if [ "$overall_status" -ne 0 ]; then
  exit "$overall_status"
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

hailortcli scan
scan_status=$?

if [ "$scan_status" -ne 0 ]; then
  printf 'ERROR: Hailo device scan failed.\n'
  exit 1
fi

BAG_INFO="$(ros2 bag info "$BAG_PATH" 2>&1)"
bag_info_status=$?

if [ "$bag_info_status" -ne 0 ]; then
  printf '%s\n' "$BAG_INFO"
  exit 1
fi

if printf '%s\n' "$BAG_INFO" |
   grep -Fq "Topic: /camera/image_raw "; then
  IMAGE_TOPIC="/camera/image_raw"
elif printf '%s\n' "$BAG_INFO" |
     grep -Fq "Topic: /camera/dashboard "; then
  IMAGE_TOPIC="/camera/dashboard"
else
  printf 'ERROR: source bag has no supported camera image topic.\n'
  exit 1
fi

if ! printf '%s\n' "$BAG_INFO" |
     grep -Fq "Topic: /tracks "; then
  printf 'ERROR: source bag has no /tracks topic.\n'
  exit 1
fi

printf 'Git HEAD:     %s\n' "$HEAD"
printf 'Bag:          %s\n' "$BAG_PATH"
printf 'Image topic:  %s\n' "$IMAGE_TOPIC"
printf 'Target ID:    %s\n' "$TARGET_ID"
printf 'Rate:         %s\n' "$RATE"
printf 'Repetitions:  %s\n' "$REPETITIONS"
printf 'Report root:  %s\n' "$REPORT_ROOT"

mkdir -p "$REPORT_ROOT" "$BAG_ROOT" "$LOG_ROOT"

printf '%s\n' "$BAG_INFO" > "$REPORT_ROOT/source_bag_info.txt"
git --no-pager show -s --format=fuller HEAD > "$REPORT_ROOT/git_commit.txt"
hailortcli scan > "$REPORT_ROOT/hailo_scan.txt" 2>&1
uname -a > "$REPORT_ROOT/uname.txt"
free -h > "$REPORT_ROOT/memory_preflight.txt" 2>&1

if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd measure_temp > "$REPORT_ROOT/temperature_preflight.txt" 2>&1
fi

SITE_PACKAGES="$(
  "$THESIS_ROOT/thesis_env/bin/python" - <<'PY'
import site

paths = site.getsitepackages()
print(paths[0] if paths else "")
PY
)"

PERCEPTION_PYTHONPATH="/usr/lib/python3/dist-packages"

if [ -n "$SITE_PACKAGES" ]; then
  PERCEPTION_PYTHONPATH="${PERCEPTION_PYTHONPATH}:${SITE_PACKAGES}"
fi

if [ -n "${PYTHONPATH:-}" ]; then
  PERCEPTION_PYTHONPATH="${PERCEPTION_PYTHONPATH}:${PYTHONPATH}"
fi

wait_for_log() {
  local log_path="$1"
  local pattern="$2"
  local pid="$3"

  for _ in $(seq 1 60); do
    if grep -Fq "$pattern" "$log_path" 2>/dev/null; then
      return 0
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 1
    fi

    sleep 0.5
  done

  return 1
}

run_condition() {
  local condition="$1"
  local repetition="$2"
  local reid_enabled="false"
  local async_enabled="false"

  if [ "$condition" = "treatment" ]; then
    reid_enabled="true"
    async_enabled="true"
  fi

  local condition_tag="r${repetition}_${condition}"
  local report_dir="$REPORT_ROOT/$condition_tag"
  local bag_dir="$BAG_ROOT/$condition_tag"
  local log_dir="$LOG_ROOT/$condition_tag"

  mkdir -p "$report_dir" "$bag_dir" "$log_dir"

  cleanup_all
  initial_cleanup_status=$?

  if [ "$initial_cleanup_status" -ne 0 ]; then
    printf 'ERROR: pre-condition cleanup failed.\n'
    return "$initial_cleanup_status"
  fi

  printf '\nRunning condition=%s repetition=%s\n' \
    "$condition" \
    "$repetition"

  cat > "$report_dir/run_metadata.json" <<EOF
{
  "schema": "p044_hailo_reid_pair_run_v1",
  "git_head": "$HEAD",
  "condition": "$condition",
  "repetition": $repetition,
  "source_bag": "$BAG_PATH",
  "image_topic": "$IMAGE_TOPIC",
  "target_id": $TARGET_ID,
  "rate": $RATE,
  "detector_hef": "$DETECTOR_HEF",
  "reid_hef": "$REID_HEF",
  "reid_enabled": $reid_enabled,
  "tim_async_reid_enabled": $async_enabled,
  "appearance_request_policy": "all_candidates",
  "appearance_compute_min_interval_ms": 250.0,
  "ros_domain_id": $ROS_DOMAIN_ID
}
EOF

  setsid "$THESIS_ROOT/thesis_env/bin/python" "$COLLECTOR" \
    --output-dir "$report_dir/collector" \
    --condition "$condition" \
    > "$log_dir/collector.log" 2>&1 &
  collector_pid=$!
  register_pid "$collector_pid"

  setsid env \
    PYTHONPATH="$PERCEPTION_PYTHONPATH" \
    ros2 run thesis_bringup perception_pipeline_node \
    --ros-args \
    -p image_topic:="$IMAGE_TOPIC" \
    -p image_reliability:=best_effort \
    -p image_qos_depth:=2 \
    -p img_w:=640 \
    -p img_h:=640 \
    -p inference_backend:=hailo_direct \
    -p hailo_hef_path:="$DETECTOR_HEF" \
    -p allow_stub_fallback:=false \
    -p publish_timing:=true \
    -p reid_enabled:="$reid_enabled" \
    -p reid_hef_path:="$REID_HEF" \
    -p reid_request_topic:=/appearance/reid/request \
    -p reid_result_topic:=/appearance/reid/result \
    -p reid_queue_capacity:=4 \
    -p reid_qos_depth:=1 \
    -p reid_status_topic:=/perception/reid/status \
    -p reid_status_period_s:=0.25 \
    > "$log_dir/perception.log" 2>&1 &
  perception_pid=$!
  register_pid "$perception_pid"

  if ! wait_for_log \
    "$log_dir/perception.log" \
    "image_topic=" \
    "$perception_pid"; then
    printf 'ERROR: perception did not become ready.\n'
    cat "$log_dir/perception.log"
    return 1
  fi

  setsid ros2 run thesis_bringup target_memory_mars_node \
    --ros-args \
    --params-file "$TIM_CONFIG" \
    -p tracks_topic:=/tracks \
    -p target_topic:=/target_memory_mars \
    -p status_topic:=/target_memory_mars/status \
    -p select_topic:=/target_memory_mars/select \
    -p selected_track_id:="$TARGET_ID" \
    -p mirror_raw_target_selection:=false \
    -p appearance_enabled:=true \
    -p appearance_image_topic:="$IMAGE_TOPIC" \
    -p appearance_request_policy:=all_candidates \
    -p appearance_compute_min_interval_ms:=250.0 \
    -p mars_model_path:="$MARS_MODEL" \
    -p appearance_async_reid_enabled:="$async_enabled" \
    -p appearance_async_reid_request_topic:=/appearance/reid/request \
    -p appearance_async_reid_result_topic:=/appearance/reid/result \
    -p appearance_async_reid_queue_capacity:=8 \
    -p appearance_async_reid_deadline_ms:=500.0 \
    -p appearance_async_reid_qos_depth:=1 \
    > "$log_dir/tim.log" 2>&1 &
  tim_pid=$!
  register_pid "$tim_pid"

  if ! wait_for_log \
    "$log_dir/tim.log" \
    "TIM-MARS node ready" \
    "$tim_pid"; then
    printf 'ERROR: TIM-MARS did not become ready.\n'
    cat "$log_dir/tim.log"
    return 1
  fi

  setsid ros2 bag record \
    -s mcap \
    -o "$bag_dir/evidence" \
    --topics \
    /timing \
    /detections \
    /perception/reid/status \
    /appearance/reid/request \
    /appearance/reid/result \
    /target_memory_mars \
    /target_memory_mars/status \
    > "$log_dir/record.log" 2>&1 &
  recorder_pid=$!
  register_pid "$recorder_pid"

  sampler_pid=""

  if command -v pidstat >/dev/null 2>&1; then
    setsid pidstat \
      -h \
      -r \
      -u \
      -p "${perception_pid},${tim_pid}" \
      1 \
      > "$report_dir/pidstat.txt" 2>&1 &
    sampler_pid=$!
    register_pid "$sampler_pid"
  else
    printf 'pidstat unavailable\n' \
      > "$report_dir/pidstat_unavailable.txt"
  fi

  sleep 2

  setsid ros2 bag play "$BAG_PATH" \
    --topics "$IMAGE_TOPIC" /tracks \
    --rate "$RATE" \
    --disable-keyboard-controls \
    > "$log_dir/play.log" 2>&1 &
  play_pid=$!
  register_pid "$play_pid"

  wait "$play_pid"
  play_status=$?

  sleep 3

  stop_pid "$recorder_pid" "recorder"
  stop_pid "$sampler_pid" "resource sampler"
  stop_pid "$tim_pid" "TIM-MARS"
  stop_pid "$perception_pid" "perception"
  stop_pid "$collector_pid" "collector"

  cleanup_all
  cleanup_status=$?

  if [ "$cleanup_status" -ne 0 ]; then
    printf 'ERROR: condition cleanup failed for %s.\n' \
      "$condition_tag"
    return "$cleanup_status"
  fi

  ros2 bag reindex "$bag_dir/evidence" \
    > "$log_dir/reindex.log" 2>&1 || true
  ros2 bag info "$bag_dir/evidence" \
    > "$report_dir/evidence_bag_info.txt" 2>&1 || true

  free -h > "$report_dir/memory_after.txt" 2>&1

  if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp \
      > "$report_dir/temperature_after.txt" 2>&1
  fi

  if [ "$play_status" -ne 0 ]; then
    printf 'ERROR: bag playback failed for %s.\n' "$condition_tag"
    return 1
  fi

  if [ ! -f "$report_dir/collector/summary.json" ]; then
    printf 'ERROR: collector summary missing for %s.\n' "$condition_tag"
    return 1
  fi

  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$report_dir/collector/summary.json" \
    "$condition" <<'PY'
from pathlib import Path
import json
import sys


path = Path(sys.argv[1])
condition = sys.argv[2]
summary = json.loads(path.read_text(encoding="utf-8"))

if summary.get("condition") != condition:
    raise SystemExit("collector condition mismatch")

timing_count = int(
    summary.get("counts", {}).get("timing", 0)
)

if timing_count <= 0:
    raise SystemExit(
        "no detector timing messages were collected"
    )

if condition == "reference":
    if int(
        summary.get("counts", {}).get("requests", 0)
    ) != 0:
        raise SystemExit(
            "reference condition unexpectedly emitted ReID requests"
        )
else:
    if int(
        summary.get("counts", {}).get("requests", 0)
    ) <= 0:
        raise SystemExit(
            "treatment condition emitted no ReID requests"
        )

print(
    f"PASS: {condition} summary passed minimum evidence checks."
)
PY
  summary_status=$?

  if [ "$summary_status" -ne 0 ]; then
    return "$summary_status"
  fi

  return 0
}

section "2. Paired evidence execution"

for repetition in $(seq 1 "$REPETITIONS"); do
  run_condition reference "$repetition"
  reference_status=$?

  if [ "$reference_status" -ne 0 ]; then
    overall_status=1
    break
  fi

  sleep 3

  run_condition treatment "$repetition"
  treatment_status=$?

  if [ "$treatment_status" -ne 0 ]; then
    overall_status=1
    break
  fi

  sleep 3
done

section "3. Build paired comparison"

if [ "$overall_status" -eq 0 ]; then
  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$REPORT_ROOT" \
    "$REPETITIONS" <<'PY'
from pathlib import Path
import json
import statistics
import sys


root = Path(sys.argv[1])
repetitions = int(sys.argv[2])


def load(condition: str) -> list[dict]:
    values = []

    for repetition in range(1, repetitions + 1):
        path = (
            root
            / f"r{repetition}_{condition}"
            / "collector"
            / "summary.json"
        )
        values.append(
            json.loads(
                path.read_text(encoding="utf-8")
            )
        )

    return values


def finite(values):
    return [
        float(value)
        for value in values
        if value is not None
    ]


def mean_metric(
    summaries: list[dict],
    group: str,
    metric: str,
    statistic: str,
):
    values = finite(
        summary[group][metric][statistic]
        for summary in summaries
    )

    if not values:
        return None

    return statistics.fmean(values)


reference = load("reference")
treatment = load("treatment")

reference_infer = mean_metric(
    reference,
    "detector",
    "infer_ms",
    "mean",
)
treatment_infer = mean_metric(
    treatment,
    "detector",
    "infer_ms",
    "mean",
)

reference_p95 = mean_metric(
    reference,
    "detector",
    "infer_ms",
    "p95",
)
treatment_p95 = mean_metric(
    treatment,
    "detector",
    "infer_ms",
    "p95",
)

comparison = {
    "schema": "p044_hailo_reid_pair_comparison_v1",
    "repetitions": repetitions,
    "reference_detector_infer_mean_ms": reference_infer,
    "treatment_detector_infer_mean_ms": treatment_infer,
    "detector_infer_mean_delta_ms": (
        None
        if reference_infer is None
        or treatment_infer is None
        else treatment_infer - reference_infer
    ),
    "reference_detector_infer_p95_ms": reference_p95,
    "treatment_detector_infer_p95_ms": treatment_p95,
    "detector_infer_p95_delta_ms": (
        None
        if reference_p95 is None
        or treatment_p95 is None
        else treatment_p95 - reference_p95
    ),
    "treatment_requests": sum(
        int(item["counts"]["requests"])
        for item in treatment
    ),
    "treatment_results": sum(
        int(item["counts"]["results"])
        for item in treatment
    ),
    "treatment_successful_results": sum(
        int(item["counts"]["successful_results"])
        for item in treatment
    ),
    "treatment_failed_results": sum(
        int(item["counts"]["failed_results"])
        for item in treatment
    ),
    "maximum_executor_queued": max(
        int(
            item["reid"][
                "maximum_executor_queued"
            ]
        )
        for item in treatment
    ),
    "maximum_engine_active_calls": max(
        int(
            item["reid"][
                "maximum_engine_active_calls"
            ]
        )
        for item in treatment
    ),
}

output = root / "pair_comparison.json"
output.write_text(
    json.dumps(
        comparison,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print(json.dumps(comparison, indent=2, sort_keys=True))
PY
  comparison_status=$?

  if [ "$comparison_status" -ne 0 ]; then
    overall_status=1
  fi
fi

section "4. Final evidence result"

git status --branch --short
git status --short

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: evidence runner changed tracked files.\n'
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

printf 'Evidence report: %s\n' "$REPORT_ROOT"
printf 'Evidence bags:   %s\n' "$BAG_ROOT"
printf 'Runtime logs:    %s\n' "$LOG_ROOT"
printf 'overall_status:  %s\n' "$overall_status"

if [ "$overall_status" -eq 0 ]; then
  printf 'PASS: paired detector-only and detector-plus-ReID evidence completed.\n'
else
  printf 'ATTENTION: paired evidence did not complete successfully.\n'
fi

exit "$overall_status"
