#!/usr/bin/env bash
# Controlled Issue #44 Hailo ReID load matrix.
#
# Conditions:
#   reference       detector only, all_candidates, 250 ms
#   selective       detector + RepVGG, all_candidates, 250 ms
#   forced_frequent detector + RepVGG, all_candidates, 0 ms
#
# CPU MARS remains authoritative. RepVGG ranking, memory, cache, and target
# decisions remain disabled.

set -o pipefail
set +e
set +u

if [ "$#" -lt 3 ] || [ "$#" -gt 5 ]; then
  printf '%s\n' \
    "Usage:" \
    "  $0 <bag_path> <target_id> <run_name> [rate] [repetitions]" \
    "" \
    "Example:" \
    "  $0 bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1 1 hard_reentry_load 1.0 3"
  exit 2
fi

THESIS_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." &&
    pwd
)"

cd "$THESIS_ROOT" || {
  printf 'ERROR: could not enter thesis repository.\n'
  exit 1
}

export GIT_PAGER=cat
export PAGER=cat
export GH_PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

BAG_PATH="$1"
TARGET_ID="$2"
RUN_NAME="$3"
RATE="${4:-1.0}"
REPETITIONS="${5:-3}"

IMAGE_TOPIC="${P044_IMAGE_TOPIC:-/camera/image_raw}"
DETECTOR_HEF="$THESIS_ROOT/models/hef/yolov6n.hef"
REID_HEF="$THESIS_ROOT/models/reid/repvgg_a0_person_reid_512.hef"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"
TIM_CONFIG="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"

COLLECTOR="$THESIS_ROOT/tools/experiments/collect_p044_transport_evidence.py"
RESOURCE_SAMPLER="$THESIS_ROOT/tools/experiments/sample_process_groups.py"

HEAD="$(git rev-parse HEAD)"
SHORT_HEAD="$(git rev-parse --short=8 HEAD)"
DATE_TAG="$(date +%Y_%m_%d)"
TAG="p044_hailo_reid_load_${SHORT_HEAD}_${DATE_TAG}_${RUN_NAME}"

REPORT_ROOT="$THESIS_ROOT/reports/$TAG"
BAG_ROOT="$THESIS_ROOT/bags/replay/$TAG"
LOG_ROOT="$THESIS_ROOT/ros2_ws/log/$TAG"

overall_status=0

declare -a REGISTERED_PIDS=()
declare -a REGISTERED_PGIDS=()
declare -a REGISTERED_LABELS=()

section() {
  printf '\n\n======================================================================\n'
  printf '%s\n' "$1"
  printf '======================================================================\n'
}

matching_runtime_pids() {
  pgrep -f \
    '/thesis_bringup/perception_pipeline_node|/thesis_bringup/target_memory_mars_node|collect_p044_transport_evidence.py|sample_process_groups.py|ros2 bag play|ros2 bag record' \
    2>/dev/null |
    awk -v self="$$" '$1 != self {print}' ||
    true
}

resolve_pgid() {
  local pid="$1"
  local attempt
  local pgid

  for attempt in $(seq 1 40); do
    pgid="$(
      ps -o pgid= -p "$pid" 2>/dev/null |
        tr -d '[:space:]'
    )"

    if [ -n "$pgid" ]; then
      printf '%s\n' "$pgid"
      return 0
    fi

    sleep 0.05
  done

  return 1
}

group_has_members() {
  local pgid="$1"

  ps -eo pgid= 2>/dev/null |
    awk -v expected="$pgid" '
      {
        gsub(/[[:space:]]/, "", $0)
        if ($0 == expected) {
          found = 1
        }
      }
      END {
        exit(found ? 0 : 1)
      }
    '
}

register_process() {
  local pid="$1"
  local label="$2"
  local pgid

  pgid="$(resolve_pgid "$pid")"
  resolve_status=$?

  if [ "$resolve_status" -ne 0 ] ||
     [ -z "$pgid" ]; then
    printf 'ERROR: could not resolve process group for %s PID %s.\n' \
      "$label" \
      "$pid"
    return 1
  fi

  own_pgid="$(
    ps -o pgid= -p "$$" 2>/dev/null |
      tr -d '[:space:]'
  )"

  if [ "$pgid" = "$own_pgid" ]; then
    printf 'ERROR: %s did not start in an isolated process group.\n' \
      "$label"
    return 1
  fi

  REGISTERED_PIDS+=("$pid")
  REGISTERED_PGIDS+=("$pgid")
  REGISTERED_LABELS+=("$label")

  printf 'Registered %s: pid=%s pgid=%s\n' \
    "$label" \
    "$pid" \
    "$pgid"

  return 0
}

stop_process_group() {
  local pid="$1"
  local pgid="$2"
  local label="$3"
  local signal
  local attempts
  local attempt

  if [ -z "$pid" ] ||
     [ -z "$pgid" ]; then
    return 0
  fi

  if ! group_has_members "$pgid"; then
    wait "$pid" 2>/dev/null || true
    return 0
  fi

  for signal in INT TERM KILL; do
    case "$signal" in
      INT)
        attempts=20
        ;;
      TERM)
        attempts=20
        ;;
      KILL)
        attempts=8
        ;;
    esac

    printf 'Stopping %s process group %s with %s.\n' \
      "$label" \
      "$pgid" \
      "$signal"

    kill "-$signal" -- "-$pgid" 2>/dev/null || true

    for attempt in $(seq 1 "$attempts"); do
      if ! group_has_members "$pgid"; then
        wait "$pid" 2>/dev/null || true
        return 0
      fi

      sleep 0.25
    done
  done

  if group_has_members "$pgid"; then
    printf 'ERROR: process group %s for %s remains active.\n' \
      "$pgid" \
      "$label"
    return 1
  fi

  wait "$pid" 2>/dev/null || true
  return 0
}

cleanup_registered() {
  local index
  local cleanup_status=0

  for ((
    index=${#REGISTERED_PIDS[@]}-1;
    index>=0;
    index--
  )); do
    stop_process_group \
      "${REGISTERED_PIDS[$index]}" \
      "${REGISTERED_PGIDS[$index]}" \
      "${REGISTERED_LABELS[$index]}"

    if [ "$?" -ne 0 ]; then
      cleanup_status=1
    fi
  done

  REGISTERED_PIDS=()
  REGISTERED_PGIDS=()
  REGISTERED_LABELS=()

  return "$cleanup_status"
}

cleanup_unmatched() {
  local pids
  local signal
  local attempt

  pids="$(matching_runtime_pids)"

  if [ -z "$pids" ]; then
    return 0
  fi

  printf 'WARNING: unmatched experiment processes detected:\n'
  ps -o pid=,ppid=,pgid=,sid=,stat=,cmd= \
    -p "$(printf '%s\n' "$pids" | paste -sd, -)" \
    2>/dev/null ||
    true

  for signal in INT TERM KILL; do
    printf '%s\n' "$pids" |
      xargs -r kill "-$signal" 2>/dev/null ||
      true

    for attempt in $(seq 1 20); do
      sleep 0.25
      pids="$(matching_runtime_pids)"

      if [ -z "$pids" ]; then
        return 0
      fi
    done
  done

  printf 'ERROR: unmatched experiment processes remain:\n%s\n' \
    "$pids"
  return 1
}

cleanup_all() {
  local status=0

  cleanup_registered

  if [ "$?" -ne 0 ]; then
    status=1
  fi

  cleanup_unmatched

  if [ "$?" -ne 0 ]; then
    status=1
  fi

  return "$status"
}

on_signal() {
  cleanup_all
  exit 130
}

trap on_signal INT TERM HUP
trap cleanup_all EXIT

wait_for_log() {
  local path="$1"
  local pattern="$2"
  local pid="$3"
  local attempt

  for attempt in $(seq 1 160); do
    if [ -f "$path" ] &&
       grep -Fq "$pattern" "$path"; then
      return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi

    sleep 0.25
  done

  return 1
}

condition_settings() {
  local condition="$1"

  case "$condition" in
    reference)
      printf '%s %s %s\n' \
        "false" \
        "false" \
        "250.0"
      ;;
    selective)
      printf '%s %s %s\n' \
        "true" \
        "true" \
        "250.0"
      ;;
    forced_frequent)
      printf '%s %s %s\n' \
        "true" \
        "true" \
        "0.0"
      ;;
    *)
      return 1
      ;;
  esac
}

section "1. Preflight"

git status --branch --short
git status --short --untracked-files=all

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: repository is not clean.\n'
  overall_status=1
fi

if [ ! -d "$BAG_PATH" ]; then
  printf 'ERROR: source bag is absent: %s\n' "$BAG_PATH"
  overall_status=1
fi

for path in \
  "$DETECTOR_HEF" \
  "$REID_HEF" \
  "$MARS_MODEL" \
  "$TIM_CONFIG" \
  "$COLLECTOR" \
  "$RESOURCE_SAMPLER"
do
  if [ ! -f "$path" ]; then
    printf 'ERROR: required file is absent: %s\n' "$path"
    overall_status=1
  fi
done

if [ -e "$REPORT_ROOT" ] ||
   [ -e "$BAG_ROOT" ] ||
   [ -e "$LOG_ROOT" ]; then
  printf 'ERROR: output tag already exists: %s\n' "$TAG"
  overall_status=1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  overall_status=1
fi

active_pids="$(matching_runtime_pids)"

if [ -n "$active_pids" ]; then
  printf 'ERROR: experiment processes are already active:\n%s\n' \
    "$active_pids"
  overall_status=1
fi

case "$TARGET_ID" in
  ''|*[!0-9]*)
    printf 'ERROR: target ID must be a positive integer.\n'
    overall_status=1
    ;;
  *)
    if [ "$TARGET_ID" -le 0 ]; then
      printf 'ERROR: target ID must be positive.\n'
      overall_status=1
    fi
    ;;
esac

case "$REPETITIONS" in
  ''|*[!0-9]*)
    printf 'ERROR: repetitions must be a positive integer.\n'
    overall_status=1
    ;;
  *)
    if [ "$REPETITIONS" -le 0 ]; then
      printf 'ERROR: repetitions must be positive.\n'
      overall_status=1
    fi
    ;;
esac

if [ "$overall_status" -ne 0 ]; then
  printf 'ABORT: preflight failed.\n'
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
hailo_status=$?

if [ "$hailo_status" -ne 0 ]; then
  printf 'ERROR: Hailo device scan failed.\n'
  exit 1
fi

bag_info_text="$(
  ros2 bag info "$BAG_PATH" 2>&1
)"
bag_info_status=$?

printf '%s\n' "$bag_info_text"

if [ "$bag_info_status" -ne 0 ]; then
  printf 'ERROR: source bag could not be inspected.\n'
  exit 1
fi

for required_source_topic in "$IMAGE_TOPIC" /tracks; do
  if ! printf '%s\n' "$bag_info_text" |
       grep -Fq "Topic: $required_source_topic |"; then
    printf 'ERROR: required source topic is absent from the bag: %s\n' \
      "$required_source_topic"
    exit 1
  fi
done

mkdir -p \
  "$REPORT_ROOT" \
  "$BAG_ROOT" \
  "$LOG_ROOT"

cat > "$REPORT_ROOT/matrix_metadata.json" <<EOF
{
  "schema": "p044_hailo_reid_load_matrix_v1",
  "git_head": "$HEAD",
  "source_bag": "$BAG_PATH",
  "image_topic": "$IMAGE_TOPIC",
  "target_id": $TARGET_ID,
  "rate": $RATE,
  "repetitions": $REPETITIONS,
  "condition_order": "rotated",
  "conditions": {
    "reference": {
      "reid_enabled": false,
      "tim_async_reid_enabled": false,
      "appearance_request_policy": "all_candidates",
      "appearance_compute_min_interval_ms": 250.0
    },
    "selective": {
      "reid_enabled": true,
      "tim_async_reid_enabled": true,
      "appearance_request_policy": "all_candidates",
      "appearance_compute_min_interval_ms": 250.0
    },
    "forced_frequent": {
      "reid_enabled": true,
      "tim_async_reid_enabled": true,
      "appearance_request_policy": "all_candidates",
      "appearance_compute_min_interval_ms": 0.0
    }
  },
  "fixed_controls": {
    "cpu_mars_authoritative": true,
    "repvgg_ranking_enabled": false,
    "repvgg_memory_enabled": false,
    "repvgg_decision_integration_enabled": false,
    "tim_queue_capacity": 8,
    "executor_queue_capacity": 4,
    "deadline_ms": 500.0,
    "qos_reliability": "BEST_EFFORT",
    "qos_depth": 1
  }
}
EOF

run_condition() {
  local condition="$1"
  local repetition="$2"
  local settings
  local reid_enabled
  local async_enabled
  local interval_ms

  settings="$(condition_settings "$condition")"

  if [ "$?" -ne 0 ]; then
    printf 'ERROR: unsupported condition: %s\n' "$condition"
    return 1
  fi

  read -r \
    reid_enabled \
    async_enabled \
    interval_ms <<< "$settings"

  local condition_tag="r${repetition}_${condition}"
  local report_dir="$REPORT_ROOT/$condition_tag"
  local bag_dir="$BAG_ROOT/$condition_tag"
  local log_dir="$LOG_ROOT/$condition_tag"

  local collector_pid
  local collector_pgid
  local perception_pid
  local perception_pgid
  local tim_pid
  local tim_pgid
  local recorder_pid
  local sampler_pid
  local play_pid
  local play_status
  local cleanup_status

  mkdir -p \
    "$report_dir" \
    "$bag_dir" \
    "$log_dir"

  cleanup_all

  if [ "$?" -ne 0 ]; then
    printf 'ERROR: pre-condition cleanup failed.\n'
    return 1
  fi

  printf '\nRunning condition=%s repetition=%s interval_ms=%s\n' \
    "$condition" \
    "$repetition" \
    "$interval_ms"

  cat > "$report_dir/run_metadata.json" <<EOF
{
  "schema": "p044_hailo_reid_load_run_v1",
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
  "appearance_compute_min_interval_ms": $interval_ms,
  "ros_domain_id": ${ROS_DOMAIN_ID:-0}
}
EOF

  setsid "$THESIS_ROOT/thesis_env/bin/python" \
    "$COLLECTOR" \
    --output-dir "$report_dir/collector" \
    --condition "$condition" \
    > "$log_dir/collector.log" 2>&1 &
  collector_pid=$!

  register_process \
    "$collector_pid" \
    "collector"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  setsid env \
    PYTHONPATH="${PYTHONPATH:-}" \
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

  register_process \
    "$perception_pid" \
    "perception"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  perception_pgid="$(
    resolve_pgid "$perception_pid"
  )"

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
    -p appearance_compute_min_interval_ms:="$interval_ms" \
    -p mars_model_path:="$MARS_MODEL" \
    -p appearance_async_reid_enabled:="$async_enabled" \
    -p appearance_async_reid_request_topic:=/appearance/reid/request \
    -p appearance_async_reid_result_topic:=/appearance/reid/result \
    -p appearance_async_reid_queue_capacity:=8 \
    -p appearance_async_reid_deadline_ms:=500.0 \
    -p appearance_async_reid_qos_depth:=1 \
    > "$log_dir/tim.log" 2>&1 &
  tim_pid=$!

  register_process \
    "$tim_pid" \
    "TIM-MARS"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  tim_pgid="$(
    resolve_pgid "$tim_pid"
  )"

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

  register_process \
    "$recorder_pid" \
    "recorder"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  setsid "$THESIS_ROOT/thesis_env/bin/python" \
    "$RESOURCE_SAMPLER" \
    --output-dir "$report_dir/resources" \
    --group "perception=$perception_pgid" \
    --group "tim=$tim_pgid" \
    --interval-s 1.0 \
    > "$log_dir/resources.log" 2>&1 &
  sampler_pid=$!

  register_process \
    "$sampler_pid" \
    "resource sampler"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  sleep 2

  setsid ros2 bag play "$BAG_PATH" \
    --topics "$IMAGE_TOPIC" /tracks \
    --rate "$RATE" \
    --disable-keyboard-controls \
    > "$log_dir/play.log" 2>&1 &
  play_pid=$!

  register_process \
    "$play_pid" \
    "bag playback"

  if [ "$?" -ne 0 ]; then
    return 1
  fi

  wait "$play_pid"
  play_status=$?

  sleep 3

  cleanup_registered
  cleanup_status=$?

  cleanup_unmatched

  if [ "$?" -ne 0 ]; then
    cleanup_status=1
  fi

  if [ "$cleanup_status" -ne 0 ]; then
    printf 'ERROR: cleanup failed for %s.\n' \
      "$condition_tag"
    return 1
  fi

  ros2 bag reindex "$bag_dir/evidence" \
    > "$log_dir/reindex.log" 2>&1 ||
    true

  ros2 bag info "$bag_dir/evidence" \
    > "$report_dir/evidence_bag_info.txt" 2>&1 ||
    true

  free -h \
    > "$report_dir/memory_after.txt" 2>&1

  if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp \
      > "$report_dir/temperature_after.txt" 2>&1
  fi

  if [ "$play_status" -ne 0 ]; then
    printf 'ERROR: bag playback failed for %s.\n' \
      "$condition_tag"
    return 1
  fi

  if [ ! -s "$report_dir/collector/summary.json" ]; then
    printf 'ERROR: collector summary is absent for %s.\n' \
      "$condition_tag"
    return 1
  fi

  if [ ! -s "$report_dir/resources/summary.json" ]; then
    printf 'ERROR: resource summary is absent for %s.\n' \
      "$condition_tag"
    cat "$log_dir/resources.log"
    return 1
  fi

  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$report_dir/collector/summary.json" \
    "$report_dir/resources/summary.json" \
    "$condition" <<'PY'
from pathlib import Path
import json
import sys


collector_path = Path(sys.argv[1])
resources_path = Path(sys.argv[2])
condition = sys.argv[3]

collector = json.loads(
    collector_path.read_text(
        encoding="utf-8"
    )
)
resources = json.loads(
    resources_path.read_text(
        encoding="utf-8"
    )
)

if collector.get("condition") != condition:
    raise SystemExit(
        "collector condition mismatch"
    )

if int(
    collector.get(
        "counts",
        {},
    ).get(
        "timing",
        0,
    )
) <= 0:
    raise SystemExit(
        "no detector timing samples were collected"
    )

request_count = int(
    collector.get(
        "counts",
        {},
    ).get(
        "requests",
        0,
    )
)

if condition == "reference":
    if request_count != 0:
        raise SystemExit(
            "reference emitted ReID requests"
        )
else:
    if request_count <= 0:
        raise SystemExit(
            f"{condition} emitted no ReID requests"
        )

    reid = collector.get("reid", {})
    executor = reid.get(
        "latest_executor",
        {},
    )
    transport = reid.get(
        "latest_tim_transport",
        {},
    )

    if int(executor.get("failed", 0)) != 0:
        raise SystemExit(
            f"{condition} has executor failures"
        )

    if int(executor.get("queued", -1)) != 0:
        raise SystemExit(
            f"{condition} executor queue did not drain"
        )

    if (
        executor.get("in_flight_request_id")
        is not None
    ):
        raise SystemExit(
            f"{condition} retained executor work"
        )

    if int(transport.get("in_flight", -1)) != 0:
        raise SystemExit(
            f"{condition} TIM ledger did not drain"
        )

    if int(
        reid.get(
            "maximum_engine_active_calls",
            -1,
        )
    ) != 1:
        raise SystemExit(
            f"{condition} Hailo calls were not serialized"
        )

groups = resources.get("groups", {})

for group_name, executable_name in (
    (
        "perception",
        "perception_pipeline_node",
    ),
    (
        "tim",
        "target_memory_mars_node",
    ),
):
    group = groups.get(group_name)

    if not isinstance(group, dict):
        raise SystemExit(
            f"missing resource group: {group_name}"
        )

    if int(group.get("sample_count", 0)) < 10:
        raise SystemExit(
            f"insufficient resource samples for {group_name}"
        )

    commands = tuple(
        str(value)
        for value in group.get(
            "observed_commands",
            [],
        )
    )

    if not any(
        executable_name in command
        for command in commands
    ):
        raise SystemExit(
            f"resource sampler never observed {executable_name}"
        )

    cpu_count = int(
        group.get(
            "cpu_percent",
            {},
        ).get(
            "count",
            0,
        )
    )

    rss_count = int(
        group.get(
            "rss_kib",
            {},
        ).get(
            "count",
            0,
        )
    )

    if cpu_count <= 0 or rss_count <= 0:
        raise SystemExit(
            f"incomplete resource metrics for {group_name}"
        )

print(
    f"PASS: {condition} collector and "
    "process-group resources are valid."
)
PY
  validation_status=$?

  if [ "$validation_status" -ne 0 ]; then
    return "$validation_status"
  fi

  return 0
}

section "2. Controlled three-condition execution"

for repetition in $(seq 1 "$REPETITIONS"); do
  rotation="$(( (repetition - 1) % 3 ))"

  case "$rotation" in
    0)
      order="reference selective forced_frequent"
      ;;
    1)
      order="selective forced_frequent reference"
      ;;
    2)
      order="forced_frequent reference selective"
      ;;
  esac

  printf '\nRepetition %s condition order: %s\n' \
    "$repetition" \
    "$order"

  for condition in $order; do
    run_condition \
      "$condition" \
      "$repetition"
    condition_status=$?

    if [ "$condition_status" -ne 0 ]; then
      overall_status=1
      break
    fi

    sleep 3
  done

  if [ "$overall_status" -ne 0 ]; then
    break
  fi
done

section "3. Build load comparison"

if [ "$overall_status" -eq 0 ]; then
  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$REPORT_ROOT" \
    "$REPETITIONS" <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import statistics
import sys
from typing import Any


root = Path(sys.argv[1])
repetitions = int(sys.argv[2])
conditions = (
    "reference",
    "selective",
    "forced_frequent",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def finite_mean(
    values: list[float | int | None],
) -> float | None:
    finite = [
        float(value)
        for value in values
        if value is not None
    ]

    if not finite:
        return None

    return statistics.fmean(finite)


def condition_summary(
    condition: str,
) -> dict[str, Any]:
    collectors = []
    resources = []

    for repetition in range(
        1,
        repetitions + 1,
    ):
        run_root = (
            root
            / f"r{repetition}_{condition}"
        )

        collectors.append(
            load_json(
                run_root
                / "collector"
                / "summary.json"
            )
        )
        resources.append(
            load_json(
                run_root
                / "resources"
                / "summary.json"
            )
        )

    detector_means = [
        item["detector"]["infer_ms"]["mean"]
        for item in collectors
    ]
    detector_p95s = [
        item["detector"]["infer_ms"]["p95"]
        for item in collectors
    ]

    constructed = 0
    published = 0
    accepted = 0
    expired = 0
    final_in_flight = 0
    executor_submitted = 0
    executor_succeeded = 0
    executor_failed = 0

    for item in collectors:
        transport = (
            item.get(
                "reid",
                {},
            ).get(
                "latest_tim_transport",
                {},
            )
        )
        executor = (
            item.get(
                "reid",
                {},
            ).get(
                "latest_executor",
                {},
            )
        )

        constructed += int(
            transport.get("constructed", 0)
        )
        published += int(
            transport.get("published", 0)
        )
        accepted += int(
            transport.get(
                "accepted_results",
                0,
            )
        )
        expired += int(
            transport.get(
                "expired_in_flight",
                0,
            )
        )
        final_in_flight += int(
            transport.get("in_flight", 0)
        )
        executor_submitted += int(
            executor.get("submitted", 0)
        )
        executor_succeeded += int(
            executor.get("succeeded", 0)
        )
        executor_failed += int(
            executor.get("failed", 0)
        )

    resource_summary = {}

    for group_name in (
        "perception",
        "tim",
    ):
        group_values = [
            resource["groups"][group_name]
            for resource in resources
        ]

        resource_summary[group_name] = {
            "cpu_percent_mean": finite_mean(
                [
                    value["cpu_percent"]["mean"]
                    for value in group_values
                ]
            ),
            "cpu_percent_p95_mean": finite_mean(
                [
                    value["cpu_percent"]["p95"]
                    for value in group_values
                ]
            ),
            "cpu_percent_maximum": max(
                float(
                    value[
                        "cpu_percent"
                    ]["maximum"]
                )
                for value in group_values
            ),
            "rss_kib_mean": finite_mean(
                [
                    value["rss_kib"]["mean"]
                    for value in group_values
                ]
            ),
            "rss_kib_maximum": max(
                float(
                    value[
                        "rss_kib"
                    ]["maximum"]
                )
                for value in group_values
            ),
            "minimum_sample_count": min(
                int(value["sample_count"])
                for value in group_values
            ),
        }

    request_delivery = (
        None
        if constructed <= 0
        else (
            100.0
            * float(executor_submitted)
            / float(constructed)
        )
    )

    result_delivery = (
        None
        if executor_succeeded <= 0
        else (
            100.0
            * float(accepted)
            / float(executor_succeeded)
        )
    )

    return {
        "repetitions": repetitions,
        "detector": {
            "infer_mean_ms": finite_mean(
                detector_means
            ),
            "infer_p95_ms": finite_mean(
                detector_p95s
            ),
        },
        "counts": {
            "requests_observed": sum(
                int(
                    item[
                        "counts"
                    ]["requests"]
                )
                for item in collectors
            ),
            "results_observed": sum(
                int(
                    item[
                        "counts"
                    ]["results"]
                )
                for item in collectors
            ),
        },
        "transport": {
            "constructed": constructed,
            "published": published,
            "executor_submitted": (
                executor_submitted
            ),
            "executor_succeeded": (
                executor_succeeded
            ),
            "executor_failed": executor_failed,
            "accepted_results": accepted,
            "expired_in_flight": expired,
            "final_in_flight": (
                final_in_flight
            ),
            "request_delivery_percent": (
                request_delivery
            ),
            "result_delivery_percent": (
                result_delivery
            ),
        },
        "resources": resource_summary,
        "maximum_executor_queued": max(
            int(
                item.get(
                    "reid",
                    {},
                ).get(
                    "maximum_executor_queued",
                    0,
                )
            )
            for item in collectors
        ),
        "maximum_engine_active_calls": max(
            int(
                item.get(
                    "reid",
                    {},
                ).get(
                    "maximum_engine_active_calls",
                    0,
                )
            )
            for item in collectors
        ),
    }


summaries = {
    condition: condition_summary(condition)
    for condition in conditions
}


def subtract(
    left: float | int | None,
    right: float | int | None,
) -> float | None:
    if left is None or right is None:
        return None

    return float(left) - float(right)


def comparison(
    left_name: str,
    right_name: str,
) -> dict[str, Any]:
    left = summaries[left_name]
    right = summaries[right_name]

    return {
        "left": left_name,
        "right": right_name,
        "detector_infer_mean_delta_ms": subtract(
            left["detector"]["infer_mean_ms"],
            right["detector"]["infer_mean_ms"],
        ),
        "detector_infer_p95_delta_ms": subtract(
            left["detector"]["infer_p95_ms"],
            right["detector"]["infer_p95_ms"],
        ),
        "perception_cpu_mean_delta_percent": subtract(
            left[
                "resources"
            ]["perception"]["cpu_percent_mean"],
            right[
                "resources"
            ]["perception"]["cpu_percent_mean"],
        ),
        "perception_rss_mean_delta_kib": subtract(
            left[
                "resources"
            ]["perception"]["rss_kib_mean"],
            right[
                "resources"
            ]["perception"]["rss_kib_mean"],
        ),
        "tim_cpu_mean_delta_percent": subtract(
            left[
                "resources"
            ]["tim"]["cpu_percent_mean"],
            right[
                "resources"
            ]["tim"]["cpu_percent_mean"],
        ),
        "tim_rss_mean_delta_kib": subtract(
            left[
                "resources"
            ]["tim"]["rss_kib_mean"],
            right[
                "resources"
            ]["tim"]["rss_kib_mean"],
        ),
    }


output = {
    "schema": (
        "p044_hailo_reid_load_comparison_v1"
    ),
    "repetitions": repetitions,
    "conditions": summaries,
    "comparisons": {
        "selective_vs_reference": comparison(
            "selective",
            "reference",
        ),
        "forced_frequent_vs_reference": comparison(
            "forced_frequent",
            "reference",
        ),
        "forced_frequent_vs_selective": comparison(
            "forced_frequent",
            "selective",
        ),
    },
    "interpretation_boundary": {
        "cpu_mars_authoritative": True,
        "repvgg_decision_integration": False,
        "geometry_winner_used": False,
        "resource_measurement": (
            "complete Linux process groups"
        ),
    },
}

output_path = root / "load_comparison.json"
output_path.write_text(
    json.dumps(
        output,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print(
    json.dumps(
        output,
        indent=2,
        sort_keys=True,
    )
)
PY
  comparison_status=$?

  if [ "$comparison_status" -ne 0 ]; then
    overall_status=1
  fi
fi

section "4. Final evidence result"

cleanup_all
cleanup_status=$?

hailortcli scan
hailo_post_status=$?

remaining_pids="$(matching_runtime_pids)"

if [ -n "$remaining_pids" ]; then
  printf 'ERROR: experiment processes remain active:\n%s\n' \
    "$remaining_pids"
  process_status=1
else
  printf 'PASS: no experiment processes remain active.\n'
  process_status=0
fi

git status --branch --short
git status --short --untracked-files=all

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: evidence runner changed tracked files.\n'
  tracked_status=1
else
  tracked_status=0
fi

if [ -e log ]; then
  printf 'ERROR: root log/ exists.\n'
  root_log_status=1
else
  printf 'PASS: no root log/ exists.\n'
  root_log_status=0
fi

if [ -e hailort.log ]; then
  printf 'ERROR: root hailort.log exists.\n'
  hailort_log_status=1
else
  printf 'PASS: no root hailort.log exists.\n'
  hailort_log_status=0
fi

if [ "$cleanup_status" -ne 0 ] ||
   [ "$hailo_post_status" -ne 0 ] ||
   [ "$process_status" -ne 0 ] ||
   [ "$tracked_status" -ne 0 ] ||
   [ "$root_log_status" -ne 0 ] ||
   [ "$hailort_log_status" -ne 0 ]; then
  overall_status=1
fi

printf 'Evidence report:    %s\n' "$REPORT_ROOT"
printf 'Evidence bags:      %s\n' "$BAG_ROOT"
printf 'Runtime logs:       %s\n' "$LOG_ROOT"
printf 'comparison_status:  %s\n' "${comparison_status:-1}"
printf 'cleanup_status:     %s\n' "$cleanup_status"
printf 'hailo_post_status:  %s\n' "$hailo_post_status"
printf 'process_status:     %s\n' "$process_status"
printf 'tracked_status:     %s\n' "$tracked_status"
printf 'overall_status:     %s\n' "$overall_status"

if [ "$overall_status" -eq 0 ]; then
  printf 'PASS: controlled three-condition Hailo ReID load matrix completed.\n'
  printf 'Resource evidence covers complete TIM and perception process groups.\n'
  printf 'CPU MARS remained authoritative and geometry_winner was not used.\n'
else
  printf 'ATTENTION: controlled load evidence did not complete successfully.\n'
fi

exit "$overall_status"
