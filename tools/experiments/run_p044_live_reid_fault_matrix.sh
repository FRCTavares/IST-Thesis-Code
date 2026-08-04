#!/usr/bin/env bash
# Controlled Issue #44 live ReID transport-fault matrix.
#
# Conditions:
#   pass_through
#     Relay mode none.
#   suppressed_result
#     Genuine perception results are consumed but not forwarded.
#   backend_failure
#     Genuine results are replaced by explicit failure results.
#   delayed_result
#     Genuine results are delayed beyond the TIM deadline.
#
# All conditions use ambiguity_guarded at 250 ms. CPU MARS remains
# authoritative and RepVGG remains observational.

set -o pipefail
set +e
set +u

if [ "$#" -lt 3 ] || [ "$#" -gt 5 ]; then
  printf '%s\n' \
    "Usage:" \
    "  $0 <bag_path> <target_id> <run_name> [rate] [repetitions]" \
    "" \
    "Example smoke:" \
    "  $0 bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1 1 hard_reentry_fault_smoke 1.0 1"
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
REPETITIONS="${5:-1}"

IMAGE_TOPIC="${P044_IMAGE_TOPIC:-/camera/image_raw}"

DETECTOR_HEF="$THESIS_ROOT/models/hef/yolov6n.hef"
REID_HEF="$THESIS_ROOT/models/reid/repvgg_a0_person_reid_512.hef"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"
TIM_CONFIG="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"

COLLECTOR="$THESIS_ROOT/tools/experiments/collect_p044_transport_evidence.py"
FAULT_RELAY="$THESIS_ROOT/tools/experiments/p044_reid_fault_relay.py"
RESOURCE_SAMPLER="$THESIS_ROOT/tools/experiments/sample_process_groups.py"

REQUEST_TOPIC="/appearance/reid/request"
RAW_RESULT_TOPIC="/appearance/reid/result_raw"
RESULT_TOPIC="/appearance/reid/result"
RELAY_STATUS_TOPIC="/p044/reid_fault/status"

APPEARANCE_POLICY="ambiguity_guarded"
INTERVAL_MS="250.0"
DEADLINE_MS="500.0"
DELAY_MS="1000.0"

HEAD="$(git rev-parse HEAD)"
SHORT_HEAD="$(git rev-parse --short=8 HEAD)"
DATE_TAG="$(date +%Y_%m_%d)"
TAG="p044_live_reid_fault_${SHORT_HEAD}_${DATE_TAG}_${RUN_NAME}"

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
    '/thesis_bringup/perception_pipeline_node|/thesis_bringup/target_memory_mars_node|collect_p044_transport_evidence.py|p044_reid_fault_relay.py|sample_process_groups.py|ros2 bag play|ros2 bag record' \
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
  local own_pgid

  pgid="$(resolve_pgid "$pid")"

  if [ "$?" -ne 0 ] || [ -z "$pgid" ]; then
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

  if [ -z "$pid" ] || [ -z "$pgid" ]; then
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
  local status=0

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
      status=1
    fi
  done

  REGISTERED_PIDS=()
  REGISTERED_PGIDS=()
  REGISTERED_LABELS=()

  return "$status"
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
    pass_through)
      printf '%s %s\n' "none" "0.0"
      ;;
    suppressed_result)
      printf '%s %s\n' "suppress_result" "0.0"
      ;;
    backend_failure)
      printf '%s %s\n' "backend_failure" "0.0"
      ;;
    delayed_result)
      printf '%s %s\n' "delay_result" "$DELAY_MS"
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
  "$FAULT_RELAY" \
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

set +u
source /opt/ros/jazzy/setup.bash
ros_status=$?

source "$THESIS_ROOT/ros2_ws/install/setup.bash"
workspace_status=$?
set +u

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
  "schema": "p044_live_reid_fault_matrix_v1",
  "git_head": "$HEAD",
  "source_bag": "$BAG_PATH",
  "image_topic": "$IMAGE_TOPIC",
  "target_id": $TARGET_ID,
  "rate": $RATE,
  "repetitions": $REPETITIONS,
  "condition_order": "rotated",
  "conditions": {
    "pass_through": {
      "relay_mode": "none",
      "delay_ms": 0.0
    },
    "suppressed_result": {
      "relay_mode": "suppress_result",
      "delay_ms": 0.0
    },
    "backend_failure": {
      "relay_mode": "backend_failure",
      "delay_ms": 0.0
    },
    "delayed_result": {
      "relay_mode": "delay_result",
      "delay_ms": $DELAY_MS
    }
  },
  "fixed_controls": {
    "cpu_mars_authoritative": true,
    "repvgg_observational": true,
    "repvgg_ranking_enabled": false,
    "repvgg_memory_enabled": false,
    "repvgg_decision_integration_enabled": false,
    "appearance_request_policy": "$APPEARANCE_POLICY",
    "appearance_compute_min_interval_ms": $INTERVAL_MS,
    "tim_deadline_ms": $DEADLINE_MS,
    "qos_reliability": "BEST_EFFORT",
    "qos_depth": 1
  }
}
EOF

run_condition() {
  local condition="$1"
  local repetition="$2"
  local settings
  local relay_mode
  local delay_ms

  settings="$(condition_settings "$condition")"

  if [ "$?" -ne 0 ]; then
    printf 'ERROR: unsupported condition: %s\n' "$condition"
    return 1
  fi

  read -r relay_mode delay_ms <<< "$settings"

  local condition_tag="r${repetition}_${condition}"
  local report_dir="$REPORT_ROOT/$condition_tag"
  local bag_dir="$BAG_ROOT/$condition_tag"
  local log_dir="$LOG_ROOT/$condition_tag"

  local collector_pid
  local relay_pid
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

  printf '\nRunning condition=%s repetition=%s mode=%s delay_ms=%s\n' \
    "$condition" \
    "$repetition" \
    "$relay_mode" \
    "$delay_ms"

  cat > "$report_dir/run_metadata.json" <<EOF
{
  "schema": "p044_live_reid_fault_run_v1",
  "git_head": "$HEAD",
  "condition": "$condition",
  "repetition": $repetition,
  "source_bag": "$BAG_PATH",
  "image_topic": "$IMAGE_TOPIC",
  "target_id": $TARGET_ID,
  "rate": $RATE,
  "relay_mode": "$relay_mode",
  "relay_delay_ms": $delay_ms,
  "appearance_request_policy": "$APPEARANCE_POLICY",
  "appearance_compute_min_interval_ms": $INTERVAL_MS,
  "tim_deadline_ms": $DEADLINE_MS,
  "request_topic": "$REQUEST_TOPIC",
  "raw_result_topic": "$RAW_RESULT_TOPIC",
  "result_topic": "$RESULT_TOPIC",
  "relay_status_topic": "$RELAY_STATUS_TOPIC",
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
    "collector" ||
    return 1

  setsid "$THESIS_ROOT/thesis_env/bin/python" \
    "$FAULT_RELAY" \
    --input-topic "$RAW_RESULT_TOPIC" \
    --output-topic "$RESULT_TOPIC" \
    --status-topic "$RELAY_STATUS_TOPIC" \
    --status-period-s 0.25 \
    --mode "$relay_mode" \
    --delay-ms "$delay_ms" \
    --summary-path "$report_dir/relay_summary.json" \
    > "$log_dir/relay.log" 2>&1 &
  relay_pid=$!

  register_process \
    "$relay_pid" \
    "fault relay" ||
    return 1

  if ! wait_for_log \
    "$log_dir/relay.log" \
    "Enabled experiment-only P044 ReID fault relay" \
    "$relay_pid"; then
    printf 'ERROR: fault relay did not become ready.\n'
    cat "$log_dir/relay.log"
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
    -p reid_enabled:=true \
    -p reid_hef_path:="$REID_HEF" \
    -p reid_request_topic:="$REQUEST_TOPIC" \
    -p reid_result_topic:="$RAW_RESULT_TOPIC" \
    -p reid_queue_capacity:=4 \
    -p reid_qos_depth:=1 \
    -p reid_status_topic:=/perception/reid/status \
    -p reid_status_period_s:=0.25 \
    > "$log_dir/perception.log" 2>&1 &
  perception_pid=$!

  register_process \
    "$perception_pid" \
    "perception" ||
    return 1

  perception_pgid="$(resolve_pgid "$perception_pid")"

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
    -p appearance_request_policy:="$APPEARANCE_POLICY" \
    -p appearance_compute_min_interval_ms:="$INTERVAL_MS" \
    -p mars_model_path:="$MARS_MODEL" \
    -p appearance_async_reid_enabled:=true \
    -p appearance_async_reid_request_topic:="$REQUEST_TOPIC" \
    -p appearance_async_reid_result_topic:="$RESULT_TOPIC" \
    -p appearance_async_reid_queue_capacity:=8 \
    -p appearance_async_reid_deadline_ms:="$DEADLINE_MS" \
    -p appearance_async_reid_qos_depth:=1 \
    > "$log_dir/tim.log" 2>&1 &
  tim_pid=$!

  register_process \
    "$tim_pid" \
    "TIM-MARS" ||
    return 1

  tim_pgid="$(resolve_pgid "$tim_pid")"

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
    "$REQUEST_TOPIC" \
    "$RAW_RESULT_TOPIC" \
    "$RESULT_TOPIC" \
    "$RELAY_STATUS_TOPIC" \
    /target_memory_mars \
    /target_memory_mars/status \
    > "$log_dir/record.log" 2>&1 &
  recorder_pid=$!

  register_process \
    "$recorder_pid" \
    "recorder" ||
    return 1

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
    "resource sampler" ||
    return 1

  sleep 2

  setsid ros2 bag play "$BAG_PATH" \
    --topics "$IMAGE_TOPIC" /tracks \
    --rate "$RATE" \
    --disable-keyboard-controls \
    > "$log_dir/play.log" 2>&1 &
  play_pid=$!

  register_process \
    "$play_pid" \
    "bag playback" ||
    return 1

  wait "$play_pid"
  play_status=$?

  # Allow the 500 ms TIM deadline and the 1000 ms delayed relay path
  # to drain before shutting down the evidence processes.
  sleep 4

  cleanup_registered
  cleanup_status=$?

  cleanup_unmatched

  if [ "$?" -ne 0 ]; then
    cleanup_status=1
  fi

  if [ "$cleanup_status" -ne 0 ]; then
    printf 'ERROR: cleanup failed for %s.\n' "$condition_tag"
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
    printf 'ERROR: bag playback failed for %s.\n' "$condition_tag"
    return 1
  fi

  for required_summary in \
    "$report_dir/collector/summary.json" \
    "$report_dir/relay_summary.json" \
    "$report_dir/resources/summary.json"
  do
    if [ ! -s "$required_summary" ]; then
      printf 'ERROR: required summary is absent: %s\n' \
        "$required_summary"
      return 1
    fi
  done

  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$report_dir/collector/summary.json" \
    "$report_dir/relay_summary.json" \
    "$report_dir/resources/summary.json" \
    "$condition" \
    "$relay_mode" <<'PY'
from pathlib import Path
import json
import sys


collector_path = Path(sys.argv[1])
relay_path = Path(sys.argv[2])
resources_path = Path(sys.argv[3])
condition = sys.argv[4]
relay_mode = sys.argv[5]

collector = json.loads(
    collector_path.read_text(
        encoding="utf-8"
    )
)
relay = json.loads(
    relay_path.read_text(
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

if relay.get("mode") != relay_mode:
    raise SystemExit(
        "relay mode mismatch"
    )

counts = collector.get("counts", {})
relay_counts = relay.get("counts", {})
reid = collector.get("reid", {})
executor = reid.get(
    "latest_executor",
    {},
)
transport = reid.get(
    "latest_tim_transport",
    {},
)

if int(counts.get("timing", 0)) <= 0:
    raise SystemExit(
        "no detector timing samples were collected"
    )

if int(counts.get("requests", 0)) <= 0:
    raise SystemExit(
        "no TIM ReID requests were collected"
    )

received = int(
    relay_counts.get(
        "received",
        0,
    )
)

if received <= 0:
    raise SystemExit(
        "relay received no raw perception results"
    )

if int(
    relay_counts.get(
        "malformed_inputs",
        0,
    )
) != 0:
    raise SystemExit(
        "relay observed malformed input"
    )

if int(
    relay_counts.get(
        "publish_errors",
        0,
    )
) != 0:
    raise SystemExit(
        "relay publication errors were observed"
    )

if int(relay.get("delayed_queue_depth", -1)) != 0:
    raise SystemExit(
        "relay delayed queue did not drain"
    )

if int(relay.get("abandoned_delayed", -1)) != 0:
    raise SystemExit(
        "relay abandoned delayed results"
    )

if int(executor.get("failed", -1)) != 0:
    raise SystemExit(
        "real Hailo executor reported a backend failure"
    )

if int(executor.get("queued", -1)) != 0:
    raise SystemExit(
        "executor queue did not drain"
    )

if executor.get("in_flight_request_id") is not None:
    raise SystemExit(
        "executor retained in-flight work"
    )

if int(transport.get("in_flight", -1)) != 0:
    raise SystemExit(
        "TIM ledger did not drain"
    )

if int(
    reid.get(
        "maximum_engine_active_calls",
        -1,
    )
) != 1:
    raise SystemExit(
        "Hailo execution was not serialized"
    )

accepted = int(
    transport.get(
        "accepted_results",
        0,
    )
)
expired = int(
    transport.get(
        "expired_in_flight",
        0,
    )
)
result_reasons = transport.get(
    "result_reasons",
    {},
)

forwarded = int(
    relay_counts.get(
        "forwarded",
        0,
    )
)
suppressed = int(
    relay_counts.get(
        "suppressed",
        0,
    )
)
injected = int(
    relay_counts.get(
        "injected_backend_failures",
        0,
    )
)
delayed_scheduled = int(
    relay_counts.get(
        "delayed_scheduled",
        0,
    )
)
delayed_published = int(
    relay_counts.get(
        "delayed_published",
        0,
    )
)

successful_results = int(
    counts.get(
        "successful_results",
        0,
    )
)
failed_results = int(
    counts.get(
        "failed_results",
        0,
    )
)
result_count = int(
    counts.get(
        "results",
        0,
    )
)

if condition == "pass_through":
    if forwarded <= 0:
        raise SystemExit(
            "pass-through forwarded no results"
        )

    if suppressed != 0 or injected != 0:
        raise SystemExit(
            "pass-through unexpectedly injected a fault"
        )

    if delayed_scheduled != 0:
        raise SystemExit(
            "pass-through unexpectedly delayed results"
        )

    if successful_results <= 0 or failed_results != 0:
        raise SystemExit(
            "pass-through result accounting is invalid"
        )

    if accepted <= 0:
        raise SystemExit(
            "pass-through produced no accepted observation"
        )

elif condition == "suppressed_result":
    if suppressed != received:
        raise SystemExit(
            "suppressed-result accounting mismatch"
        )

    if forwarded != 0 or result_count != 0:
        raise SystemExit(
            "suppressed results reached TIM"
        )

    if accepted != 0 or expired <= 0:
        raise SystemExit(
            "suppressed-result TIM accounting is invalid"
        )

elif condition == "backend_failure":
    if injected != received:
        raise SystemExit(
            "backend-failure injection accounting mismatch"
        )

    if forwarded <= 0:
        raise SystemExit(
            "backend failures were not forwarded"
        )

    if successful_results != 0 or failed_results <= 0:
        raise SystemExit(
            "backend-failure result accounting is invalid"
        )

    if accepted != 0:
        raise SystemExit(
            "backend failure was accepted"
        )

    if int(
        result_reasons.get(
            "backend_failure",
            0,
        )
    ) <= 0:
        raise SystemExit(
            "TIM did not report backend_failure"
        )

elif condition == "delayed_result":
    if delayed_scheduled != received:
        raise SystemExit(
            "delayed-result scheduling mismatch"
        )

    if delayed_published <= 0 or forwarded <= 0:
        raise SystemExit(
            "delayed results were not published"
        )

    if successful_results <= 0 or failed_results != 0:
        raise SystemExit(
            "delayed result stream is invalid"
        )

    if accepted != 0 or expired <= 0:
        raise SystemExit(
            "delayed-result TIM accounting is invalid"
        )

    if int(
        result_reasons.get(
            "unknown_or_not_in_flight",
            0,
        )
    ) <= 0:
        raise SystemExit(
            "TIM did not reject delayed results as unknown"
        )

else:
    raise SystemExit(
        f"unsupported validation condition: {condition}"
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

print(
    f"PASS: {condition} live fault accounting is valid."
)
PY

  validation_status=$?

  if [ "$validation_status" -ne 0 ]; then
    return "$validation_status"
  fi

  return 0
}

section "2. Controlled four-condition execution"

for repetition in $(seq 1 "$REPETITIONS"); do
  rotation="$(( (repetition - 1) % 4 ))"

  case "$rotation" in
    0)
      order="pass_through suppressed_result backend_failure delayed_result"
      ;;
    1)
      order="suppressed_result backend_failure delayed_result pass_through"
      ;;
    2)
      order="backend_failure delayed_result pass_through suppressed_result"
      ;;
    3)
      order="delayed_result pass_through suppressed_result backend_failure"
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

section "3. Build compact fault comparison"

if [ "$overall_status" -eq 0 ]; then
  "$THESIS_ROOT/thesis_env/bin/python" - \
    "$REPORT_ROOT" \
    "$REPETITIONS" <<'PY'
from pathlib import Path
import json
import sys
from typing import Any


root = Path(sys.argv[1])
repetitions = int(sys.argv[2])

conditions = (
    "pass_through",
    "suppressed_result",
    "backend_failure",
    "delayed_result",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


runs: list[dict[str, Any]] = []

for repetition in range(
    1,
    repetitions + 1,
):
    for condition in conditions:
        run_root = (
            root
            / f"r{repetition}_{condition}"
        )

        collector = load_json(
            run_root
            / "collector"
            / "summary.json"
        )
        relay = load_json(
            run_root
            / "relay_summary.json"
        )

        transport = (
            collector.get(
                "reid",
                {},
            ).get(
                "latest_tim_transport",
                {},
            )
        )
        executor = (
            collector.get(
                "reid",
                {},
            ).get(
                "latest_executor",
                {},
            )
        )

        runs.append(
            {
                "repetition": repetition,
                "condition": condition,
                "relay_mode": relay.get(
                    "mode"
                ),
                "collector_counts": collector.get(
                    "counts",
                    {},
                ),
                "relay_counts": relay.get(
                    "counts",
                    {},
                ),
                "relay_abandoned_delayed": relay.get(
                    "abandoned_delayed"
                ),
                "tim_transport": {
                    "constructed": transport.get(
                        "constructed"
                    ),
                    "published": transport.get(
                        "published"
                    ),
                    "accepted_results": transport.get(
                        "accepted_results"
                    ),
                    "expired_in_flight": transport.get(
                        "expired_in_flight"
                    ),
                    "in_flight": transport.get(
                        "in_flight"
                    ),
                    "result_reasons": transport.get(
                        "result_reasons",
                        {},
                    ),
                },
                "executor": {
                    "submitted": executor.get(
                        "submitted"
                    ),
                    "executed": executor.get(
                        "executed"
                    ),
                    "succeeded": executor.get(
                        "succeeded"
                    ),
                    "failed": executor.get(
                        "failed"
                    ),
                    "queued": executor.get(
                        "queued"
                    ),
                    "in_flight_request_id": executor.get(
                        "in_flight_request_id"
                    ),
                },
            }
        )

payload = {
    "schema": "p044_live_reid_fault_comparison_v1",
    "repetitions": repetitions,
    "conditions": list(conditions),
    "runs": runs,
    "claim_boundary": {
        "experiment_only_fault_injection": True,
        "production_perception_modified": False,
        "production_tim_modified": False,
        "cpu_mars_authoritative": True,
        "repvgg_observational": True,
        "repvgg_ranking_enabled": False,
        "repvgg_memory_enabled": False,
        "repvgg_decision_integration_enabled": False,
        "canonical_policy_changed": False,
        "authoritative_repvgg_safety_proven": False,
    },
}

output = root / "fault_matrix_summary.json"
output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print(f"Written {output}")
PY

  comparison_status=$?

  if [ "$comparison_status" -ne 0 ]; then
    overall_status=1
  fi
fi

section "4. Final hygiene"

cleanup_all
cleanup_status=$?

remaining_pids="$(matching_runtime_pids)"

if [ -n "$remaining_pids" ]; then
  printf 'ERROR: experiment processes remain active:\n%s\n' \
    "$remaining_pids"
  overall_status=1
fi

hailortcli scan
final_hailo_status=$?

if [ "$final_hailo_status" -ne 0 ]; then
  printf 'ERROR: Hailo device was not released cleanly.\n'
  overall_status=1
fi

git status --branch --short
git status --short

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: repository changed during hardware execution.\n'
  overall_status=1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  overall_status=1
fi

printf '\n===== result =====\n'
printf 'cleanup_status:     %s\n' "$cleanup_status"
printf 'comparison_status:  %s\n' "${comparison_status:-not-run}"
printf 'final_hailo_status: %s\n' "$final_hailo_status"
printf 'overall_status:     %s\n' "$overall_status"

if [ "$overall_status" -eq 0 ]; then
  printf 'PASS: live P044 ReID fault matrix completed.\n'
  printf 'Report: %s\n' "$REPORT_ROOT"
  printf 'Evidence bags: %s\n' "$BAG_ROOT"
  printf 'Logs: %s\n' "$LOG_ROOT"
  printf 'CPU MARS remained authoritative.\n'
  printf 'RepVGG remained observational.\n'
else
  printf 'ATTENTION: inspect the first failed condition.\n'
fi

exit "$overall_status"
