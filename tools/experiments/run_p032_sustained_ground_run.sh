#!/usr/bin/env bash

set +e
set +u

THESIS_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." &&
  pwd
)"

cd "$THESIS_ROOT" || {
  printf 'ERROR: could not enter repository root.\n'
  exit 1
}

export GIT_PAGER=cat
export PAGER=cat
export GH_PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"

# Issue #32 canonical live/onboard sustained run.
#
# Source imagery and tracks come from a recorded bag through the
# established Issue #44 timestamp-refresh relay (p044_soak_input_relay.py),
# republished onto the live topics that the real detector, tracker, and
# TIM-MARS nodes consume at realistic cadence. The nodes, hardware, and
# Hailo accelerator are real; the source is a replayed recording, not a
# physically live camera. This is "live/onboard sustained execution" in
# the sense Issue #32 requires it (true node execution, real thermal/CPU
# exposure, real cadence and contention) as distinct from the deterministic,
# non-real-time replay pass used for algorithm compute-cost comparison.
#
# The canonical CPU-MARS TIM-MARS appearance path is used. Hailo ReID
# offload (Issue #44 scope) is not enabled -- it is observational-only and
# not the canonical default.

if [ "$#" -lt 3 ] || [ "$#" -gt 5 ]; then
  printf '%s\n' \
    'Usage:' \
    '  run_p032_sustained_ground_run.sh BAG_PATH TARGET_ID RUN_NAME [RATE] [DURATION_S]'
  exit 2
fi

BAG_PATH="$1"
TARGET_ID="$2"
RUN_NAME="$3"
RATE="${4:-1.0}"
DURATION_S="${5:-960.0}"

EXPECTED_BRANCH="issue-32-runtime-resource-characterization"

DETECTOR_HEF="$THESIS_ROOT/models/hef/yolov8s.hef"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"
TIM_CONFIG="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"

TIMING_COLLECTOR="$THESIS_ROOT/tools/analysis/collect_live_timing_stats.py"
INVARIANT_CHECKER="$THESIS_ROOT/tools/analysis/check_live_timing_invariants.py"
INPUT_RELAY="$THESIS_ROOT/tools/experiments/p044_soak_input_relay.py"
RESOURCE_SAMPLER="$THESIS_ROOT/tools/experiments/sample_process_groups.py"
HEALTH_SAMPLER="$THESIS_ROOT/tools/experiments/sample_p044_hardware_health.py"
APPEARANCE_ANALYSER="$THESIS_ROOT/tools/analysis/analyse_p032_appearance_budget.py"
SUSTAINED_ANALYSER="$THESIS_ROOT/tools/analysis/analyze_p032_sustained_run.py"

SOURCE_IMAGE_TOPIC="/p032/ground_run/source/image"
SOURCE_TRACKS_TOPIC="/p032/ground_run/source/tracks"
IMAGE_TOPIC="/camera/image_raw"
TRACKS_TOPIC="/tracks"
RELAY_STATUS_TOPIC="/p032/ground_run/input_relay/status"

APPEARANCE_POLICY="ambiguity_guarded"
INTERVAL_MS="250.0"

HEAD="$(git rev-parse HEAD)"
HEAD_SHORT="$(git rev-parse --short=8 HEAD)"
DATE_TAG="$(date +%Y_%m_%d)"
TAG="p032_ground_run_${HEAD_SHORT}_${DATE_TAG}_${RUN_NAME}"

REPORT_DIR="$THESIS_ROOT/reports/$TAG"
BAG_DIR="$THESIS_ROOT/bags/replay/$TAG"
LOG_DIR="$THESIS_ROOT/ros2_ws/log/$TAG"

overall_status=0
cleanup_status=0
smoke_status=1
timing_status=1
appearance_status=0
analysis_status=1
log_scan_status=1
final_hailo_status=1

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
    '/thesis_bringup/perception_pipeline_node|/thesis_bringup/target_memory_mars_node|p044_soak_input_relay.py|collect_live_timing_stats.py|sample_process_groups.py|sample_p044_hardware_health.py|ros2 bag play|ros2 bag record' \
    2>/dev/null |
    awk -v self="$$" '$1 != self {print}' ||
    true
}

resolve_pgid() {
  local pid="$1"
  local attempt
  local pgid

  for attempt in $(seq 1 30); do
    pgid="$(
      ps -o pgid= -p "$pid" 2>/dev/null |
        tr -d '[:space:]'
    )"

    if [ -n "$pgid" ]; then
      printf '%s\n' "$pgid"
      return 0
    fi

    sleep 0.1
  done

  return 1
}

register_process() {
  local pid="$1"
  local label="$2"
  local pgid

  pgid="$(resolve_pgid "$pid")" || {
    printf 'ERROR: could not resolve process group for %s PID %s.\n' \
      "$label" "$pid"
    return 1
  }

  REGISTERED_PIDS+=("$pid")
  REGISTERED_PGIDS+=("$pgid")
  REGISTERED_LABELS+=("$label")

  printf 'Registered %s: pid=%s pgid=%s\n' \
    "$label" "$pid" "$pgid"
}

stop_process_group() {
  local pgid="$1"
  local label="$2"
  local signal
  local attempt

  if ! kill -0 -- "-$pgid" 2>/dev/null; then
    return 0
  fi

  for signal in INT TERM KILL; do
    printf 'Stopping %s process group %s with %s.\n' \
      "$label" "$pgid" "$signal"

    kill "-$signal" -- "-$pgid" 2>/dev/null || true

    for attempt in $(seq 1 40); do
      if ! kill -0 -- "-$pgid" 2>/dev/null; then
        return 0
      fi

      sleep 0.1
    done
  done

  printf 'ERROR: process group %s for %s did not stop.\n' \
    "$pgid" "$label"
  return 1
}

cleanup_registered() {
  local index

  for ((
    index=${#REGISTERED_PGIDS[@]}-1;
    index>=0;
    index--
  )); do
    stop_process_group \
      "${REGISTERED_PGIDS[$index]}" \
      "${REGISTERED_LABELS[$index]}" ||
      cleanup_status=1
  done
}

cleanup_unmatched() {
  local pids
  local pid
  local pgid

  pids="$(matching_runtime_pids)"

  for pid in $pids; do
    pgid="$(resolve_pgid "$pid")" || continue
    stop_process_group "$pgid" "unmatched runtime" ||
      cleanup_status=1
  done
}

cleanup_all() {
  cleanup_registered
  cleanup_unmatched
}

wait_for_log() {
  local path="$1"
  local pattern="$2"
  local pid="$3"
  local attempt

  for attempt in $(seq 1 120); do
    if [ -f "$path" ] &&
       rg -q -- "$pattern" "$path"; then
      return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi

    sleep 0.1
  done

  return 1
}

trap cleanup_all EXIT INT TERM

section "1. Preflight"

git status --branch --short
git status --short

if [ "$(git branch --show-current)" != "$EXPECTED_BRANCH" ]; then
  printf 'ERROR: unexpected branch.\n'
  exit 1
fi

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: tracked repository is not clean.\n'
  exit 1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  exit 1
fi

if ! command -v timeout >/dev/null 2>&1; then
  printf 'ERROR: GNU timeout is required for bounded loop playback.\n'
  exit 1
fi

if [ -n "$(matching_runtime_pids)" ]; then
  printf 'ERROR: related runtime processes are already active.\n'
  matching_runtime_pids
  exit 1
fi

for path in \
  "$BAG_PATH" \
  "$DETECTOR_HEF" \
  "$MARS_MODEL" \
  "$TIM_CONFIG" \
  "$TIMING_COLLECTOR" \
  "$INVARIANT_CHECKER" \
  "$INPUT_RELAY" \
  "$RESOURCE_SAMPLER" \
  "$HEALTH_SAMPLER" \
  "$APPEARANCE_ANALYSER" \
  "$SUSTAINED_ANALYSER"
do
  if [ ! -e "$path" ]; then
    printf 'ERROR: required path is absent: %s\n' "$path"
    exit 1
  fi
done

THESIS_ROOT="$THESIS_ROOT" \
RATE="$RATE" \
DURATION_S="$DURATION_S" \
TARGET_ID="$TARGET_ID" \
"$THESIS_ROOT/thesis_env/bin/python" - <<'PY'
import os

rate = float(os.environ["RATE"])
duration = float(os.environ["DURATION_S"])
target = int(os.environ["TARGET_ID"])

if rate <= 0.0:
    raise SystemExit("ERROR: rate must be positive.")

if duration < 900.0:
    raise SystemExit(
        "ERROR: Issue #32 sustained ground run must be at least 900 seconds "
        "to approach thermal steady state."
    )

if target <= 0:
    raise SystemExit("ERROR: target ID must be positive.")
PY

argument_status=$?

if [ "$argument_status" -ne 0 ]; then
  exit "$argument_status"
fi

for path in "$REPORT_DIR" "$BAG_DIR" "$LOG_DIR"; do
  if [ -e "$path" ]; then
    printf 'ERROR: output path already exists: %s\n' "$path"
    exit 1
  fi
done

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

hailortcli scan || exit 1
ros2 bag info "$BAG_PATH" || exit 1

mkdir -p \
  "$REPORT_DIR/timing" \
  "$REPORT_DIR/resources" \
  "$REPORT_DIR/health" \
  "$REPORT_DIR/appearance" \
  "$BAG_DIR" \
  "$LOG_DIR" ||
  exit 1

cat > "$REPORT_DIR/run_metadata.json" <<EOF
{
  "schema": "p032_live_sustained_run_v1",
  "execution_commit": "$HEAD",
  "source_bag": "$BAG_PATH",
  "target_id": $TARGET_ID,
  "rate": $RATE,
  "duration_s": $DURATION_S,
  "duration_control": "external_wall_clock_timeout",
  "warm_up_s": 60.0,
  "source_image_topic": "$SOURCE_IMAGE_TOPIC",
  "source_tracks_topic": "$SOURCE_TRACKS_TOPIC",
  "output_image_topic": "$IMAGE_TOPIC",
  "output_tracks_topic": "$TRACKS_TOPIC",
  "detector_hef": "$DETECTOR_HEF",
  "appearance_backend": "cpu_mars",
  "appearance_request_policy": "$APPEARANCE_POLICY",
  "appearance_compute_min_interval_ms": $INTERVAL_MS,
  "hailo_reid_offload_enabled": false,
  "measurement_mode": "live_sustained",
  "source_category": "replayed_bag_via_timestamp_refresh_relay",
  "physically_live_camera": false,
  "canonical_policy_changed": false,
  "production_nodes_modified": false
}
EOF

section "2. Start sustained stack"

setsid "$THESIS_ROOT/thesis_env/bin/python" \
  "$INPUT_RELAY" \
  --input-image-topic "$SOURCE_IMAGE_TOPIC" \
  --output-image-topic "$IMAGE_TOPIC" \
  --input-tracks-topic "$SOURCE_TRACKS_TOPIC" \
  --output-tracks-topic "$TRACKS_TOPIC" \
  --status-topic "$RELAY_STATUS_TOPIC" \
  --summary-path "$REPORT_DIR/input_relay_summary.json" \
  > "$LOG_DIR/input_relay.log" 2>&1 &
relay_pid=$!

register_process "$relay_pid" "input relay" || exit 1
relay_pgid="$(resolve_pgid "$relay_pid")" || exit 1

if ! wait_for_log \
  "$LOG_DIR/input_relay.log" \
  "P044 sustained-input relay ready" \
  "$relay_pid"; then
  printf 'ERROR: input relay did not become ready.\n'
  cat "$LOG_DIR/input_relay.log"
  exit 1
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
  -p reid_enabled:=false \
  > "$LOG_DIR/perception.log" 2>&1 &
perception_pid=$!

register_process "$perception_pid" "perception" || exit 1
perception_pgid="$(resolve_pgid "$perception_pid")" || exit 1

if ! wait_for_log \
  "$LOG_DIR/perception.log" \
  "image_topic=" \
  "$perception_pid"; then
  printf 'ERROR: perception did not become ready.\n'
  cat "$LOG_DIR/perception.log"
  exit 1
fi

setsid ros2 run thesis_bringup target_memory_mars_node \
  --ros-args \
  --params-file "$TIM_CONFIG" \
  -p tracks_topic:="$TRACKS_TOPIC" \
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
  -p appearance_async_reid_enabled:=false \
  > "$LOG_DIR/tim.log" 2>&1 &
tim_pid=$!

register_process "$tim_pid" "TIM-MARS" || exit 1
tim_pgid="$(resolve_pgid "$tim_pid")" || exit 1

if ! wait_for_log \
  "$LOG_DIR/tim.log" \
  "TIM-MARS node ready" \
  "$tim_pid"; then
  printf 'ERROR: TIM-MARS did not become ready.\n'
  cat "$LOG_DIR/tim.log"
  exit 1
fi

section "3. Pre-run smoke: live timing invariants"

"$THESIS_ROOT/thesis_env/bin/python" \
  "$INVARIANT_CHECKER" \
  --once \
  --topic-timeout 30 \
  > "$LOG_DIR/smoke_invariants.log" 2>&1
smoke_status=$?

cat "$LOG_DIR/smoke_invariants.log"

if [ "$smoke_status" -ne 0 ]; then
  printf 'ERROR: pre-run timing-invariant smoke check failed. Aborting before the long sustained run.\n'
  overall_status=1
  exit 1
fi

printf 'PASS: pre-run smoke confirmed /timing, /timing_tracker, /timing_target invariants and topic wiring.\n'

setsid ros2 bag record \
  -s mcap \
  -o "$BAG_DIR/evidence" \
  --topics \
  /timing \
  /timing_tracker \
  /timing_target \
  /detections \
  /tracks \
  "$RELAY_STATUS_TOPIC" \
  /target_memory_mars \
  /target_memory_mars/status \
  > "$LOG_DIR/record.log" 2>&1 &
recorder_pid=$!

register_process "$recorder_pid" "recorder" || exit 1
sleep 1

setsid "$THESIS_ROOT/thesis_env/bin/python" \
  "$RESOURCE_SAMPLER" \
  --output-dir "$REPORT_DIR/resources" \
  --group "perception=$perception_pgid" \
  --group "tim=$tim_pgid" \
  --group "relay=$relay_pgid" \
  --interval-s 1.0 \
  > "$LOG_DIR/resources.log" 2>&1 &
resource_pid=$!

register_process "$resource_pid" "resource sampler" || exit 1

setsid "$THESIS_ROOT/thesis_env/bin/python" \
  "$HEALTH_SAMPLER" \
  --output-dir "$REPORT_DIR/health" \
  --interval-s 5.0 \
  > "$LOG_DIR/health.log" 2>&1 &
health_pid=$!

register_process "$health_pid" "health sampler" || exit 1

WARM_UP_S=60.0
COLLECTOR_DURATION_S="$(
  "$THESIS_ROOT/thesis_env/bin/python" -c \
    "print(max(1.0, float(\"$DURATION_S\") - float(\"$WARM_UP_S\")))"
)"

section "4. Run timestamp-continuous looping replay"

# rosbag2 applies --playback-duration inside the source timestamp range.
# Combined with --loop, the source restarts before reaching a duration
# longer than the bag and playback never ends on its own. Use a host
# wall-clock watchdog instead, matching the established P044 pattern.
setsid timeout \
  --foreground \
  --signal=TERM \
  --kill-after=15s \
  "${DURATION_S}s" \
  ros2 bag play "$BAG_PATH" \
  --rate "$RATE" \
  --loop \
  --disable-keyboard-controls \
  --topics \
  /camera/image_raw \
  /tracks \
  --remap \
  "/camera/image_raw:=$SOURCE_IMAGE_TOPIC" \
  "/tracks:=$SOURCE_TRACKS_TOPIC" \
  > "$LOG_DIR/playback.log" 2>&1 &
playback_pid=$!

register_process "$playback_pid" "bag playback" || exit 1

printf 'Warm-up window: %ss. Latency percentile collection starts after warm-up so steady-state statistics exclude pipeline warm-up; resource and health sampling cover the full run including warm-up.\n' "$WARM_UP_S"
sleep "$WARM_UP_S"

if ! kill -0 "$playback_pid" 2>/dev/null; then
  printf 'ERROR: bag playback exited during the warm-up window.\n'
  overall_status=1
fi

setsid "$THESIS_ROOT/thesis_env/bin/python" \
  "$TIMING_COLLECTOR" \
  --duration "$COLLECTOR_DURATION_S" \
  --run-label "$TAG" \
  --json-out "$REPORT_DIR/timing/live_timing_summary.json" \
  > "$LOG_DIR/timing_collector.log" 2>&1 &
timing_pid=$!

register_process "$timing_pid" "timing collector" || exit 1

wait "$playback_pid"
playback_raw_status=$?
playback_status="$playback_raw_status"
playback_end_reason="player_exit"

# GNU timeout returns 124 when the requested wall-clock duration expires.
# That is the expected successful termination mechanism.
if [ "$playback_raw_status" -eq 124 ]; then
  playback_status=0
  playback_end_reason="duration_watchdog"
fi

printf 'playback_raw_status: %s\n' "$playback_raw_status"
printf 'playback_status:     %s\n' "$playback_status"
printf 'playback_end_reason: %s\n' "$playback_end_reason"

if [ "$playback_status" -ne 0 ]; then
  printf 'ERROR: bounded bag playback failed.\n'
  overall_status=1
fi

printf 'Waiting for the timing collector to complete its bounded window.\n'
wait "$timing_pid"
timing_status=$?

if [ "$timing_status" -ne 0 ]; then
  printf 'ERROR: live timing collector exited abnormally.\n'
  overall_status=1
fi

sleep 5

section "5. Pre-cleanup liveness"

for entry in \
  "relay:$relay_pid" \
  "perception:$perception_pid" \
  "tim:$tim_pid" \
  "recorder:$recorder_pid" \
  "resources:$resource_pid" \
  "health:$health_pid"
do
  label="${entry%%:*}"
  pid="${entry##*:}"

  if kill -0 "$pid" 2>/dev/null; then
    printf 'PASS: %s remained alive through the bounded run.\n' "$label"
  else
    printf 'ERROR: %s exited before controlled cleanup.\n' "$label"
    overall_status=1
  fi
done

section "6. Controlled cleanup"

cleanup_registered
cleanup_unmatched
trap - EXIT INT TERM

for path in \
  "$REPORT_DIR/timing/live_timing_summary.json" \
  "$REPORT_DIR/input_relay_summary.json" \
  "$REPORT_DIR/resources/summary.json" \
  "$REPORT_DIR/resources/samples.jsonl" \
  "$REPORT_DIR/health/summary.json" \
  "$REPORT_DIR/health/samples.jsonl"
do
  if [ ! -s "$path" ]; then
    printf 'ERROR: required evidence file is absent or empty: %s\n' "$path"
    overall_status=1
  fi
done

section "7. Appearance-budget analysis"

"$THESIS_ROOT/thesis_env/bin/python" \
  "$APPEARANCE_ANALYSER" \
  "$BAG_DIR/evidence" \
  --topic /target_memory_mars/status \
  --run-name "$TAG" \
  --git-commit "$HEAD" \
  --json-out "$REPORT_DIR/appearance/appearance_budget.json" \
  --markdown-out "$REPORT_DIR/appearance/appearance_budget.md" \
  --measurement-mode live_sustained \
  > "$LOG_DIR/appearance_analysis.log" 2>&1
appearance_status=$?

cat "$LOG_DIR/appearance_analysis.log"

if [ "$appearance_status" -ne 0 ]; then
  overall_status=1
fi

section "8. Sustained evidence analysis"

"$THESIS_ROOT/thesis_env/bin/python" \
  "$SUSTAINED_ANALYSER" \
  --timing-summary "$REPORT_DIR/timing/live_timing_summary.json" \
  --relay-summary "$REPORT_DIR/input_relay_summary.json" \
  --resources-summary "$REPORT_DIR/resources/summary.json" \
  --resources-samples "$REPORT_DIR/resources/samples.jsonl" \
  --health-summary "$REPORT_DIR/health/summary.json" \
  --health-samples "$REPORT_DIR/health/samples.jsonl" \
  --duration-s "$DURATION_S" \
  --warm-up-s 60.0 \
  --output "$REPORT_DIR/sustained_analysis.json" \
  > "$LOG_DIR/analysis.log" 2>&1

analysis_status=$?

cat "$LOG_DIR/analysis.log"

if [ "$analysis_status" -ne 0 ]; then
  overall_status=1
fi

section "9. Log and hygiene validation"

rg -n -i \
  'traceback|segmentation fault|fatal|uncaught exception|error:' \
  "$LOG_DIR" \
  --glob '*.log' \
  --glob '!analysis.log' \
  --glob '!appearance_analysis.log' \
  --glob '!smoke_invariants.log' \
  > "$REPORT_DIR/log_error_scan.txt"

log_scan_raw_status=$?
log_scan_status="$log_scan_raw_status"

if [ "$log_scan_raw_status" -eq 0 ]; then
  log_scan_status=1
  cat "$REPORT_DIR/log_error_scan.txt"
  printf 'ATTENTION: runtime error-pattern matches were found.\n'
  overall_status=1
elif [ "$log_scan_raw_status" -eq 1 ]; then
  log_scan_status=0
  printf 'PASS: no runtime error-pattern matches found.\n'
  : > "$REPORT_DIR/log_error_scan.txt"
else
  printf 'ERROR: runtime log scan failed.\n'
  overall_status=1
fi

hailortcli scan
final_hailo_status=$?

if [ "$final_hailo_status" -ne 0 ]; then
  overall_status=1
fi

if [ -n "$(matching_runtime_pids)" ]; then
  printf 'ERROR: related runtime processes remain active.\n'
  matching_runtime_pids
  overall_status=1
fi

git status --branch --short
git status --short

if [ -n "$(git status --short)" ]; then
  printf 'ERROR: tracked repository changed during execution.\n'
  overall_status=1
fi

if [ -e log ] || [ -e hailort.log ]; then
  printf 'ERROR: root runtime noise exists.\n'
  overall_status=1
fi

section "10. Result"

printf 'playback_raw_status:%s\n' "$playback_raw_status"
printf 'playback_status:    %s\n' "$playback_status"
printf 'playback_end_reason:%s\n' "$playback_end_reason"
printf 'smoke_status:       %s\n' "$smoke_status"
printf 'timing_status:      %s\n' "$timing_status"
printf 'appearance_status:  %s\n' "$appearance_status"
printf 'cleanup_status:     %s\n' "$cleanup_status"
printf 'analysis_status:    %s\n' "$analysis_status"
printf 'log_scan_status:    %s\n' "$log_scan_status"
printf 'final_hailo_status: %s\n' "$final_hailo_status"
printf 'overall_status:     %s\n' "$overall_status"

if [ "$overall_status" -eq 0 ]; then
  printf 'PASS: bounded Issue #32 sustained ground run completed.\n'
  printf 'Report: %s\n' "$REPORT_DIR"
  printf 'Evidence bag: %s\n' "$BAG_DIR"
  printf 'Logs: %s\n' "$LOG_DIR"
else
  printf 'ATTENTION: inspect the first reported violation above.\n'
fi

exit "$overall_status"
