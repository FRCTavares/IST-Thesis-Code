#!/usr/bin/env bash
#
# Issue #55 M6 — bag-replay live UI / dashboard-backend integration gate.
#
# Purpose:
#   Prove that the externally owned IST-Thesis-UI frontend integrates with the
#   Thesis-Code dashboard backend over HTTP / WebSocket / MJPEG, driving a
#   fresh canonical TIM-MARS target-authority instance from a recorded bag.
#
# This is an ENGINEERING INTEGRATION test only. It produces no scientific
# result. It never starts the controller, MAVROS, Pixhawk, physical camera,
# detector inference, or Hailo. It replays only the input/evidence topics
# (/camera/image_raw, /detections, /tracks) and never the bag's stored
# /target, /target_memory_mars, or /target_memory_mars/status.
#
# All long-lived children run under tools/lib/run_in_owned_process_group.py so
# each owns a session/process-group that is torn down on exit. No global pkill.
#
set +e
set +u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THESIS_ROOT="$(cd "$HERE/../.." && pwd)"
export THESIS_ROOT

THESIS_UI_ROOT="${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}"
export THESIS_UI_ROOT
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

BAG="${M6_BAG:-$THESIS_ROOT/bags/replay/p025_seq01_physical_v2_tim_mars_2026_08_29}"
CANONICAL_CFG="$THESIS_ROOT/ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
MARS_MODEL="$THESIS_ROOT/models/reid/mars-small128.pb"

API_HOST=127.0.0.1 ; API_PORT=8090
WS_HOST=127.0.0.1 ; WS_PORT=8765
VIDEO_HOST=127.0.0.1 ; VIDEO_PORT=8080
UI_HOST=127.0.0.1 ; UI_PORT=5173

IMAGE_TOPIC=/camera/image_raw
DASHBOARD_TOPIC=/camera/dashboard

RUN_TS="$(date +%Y-%m-%d__%H-%M-%S)"
LOG_DIR="$THESIS_ROOT/ros2_ws/log/issue55_m6/$RUN_TS"
mkdir -p "$LOG_DIR"

RUN_HELPER="$THESIS_ROOT/tools/lib/run_in_owned_process_group.py"
PROBE="$HERE/m6_integration_probe.py"

OWNED_PIDS=()
OWNED_NAMES=()
FAIL=0

log() { printf '[m6] %s\n' "$*" | tee -a "$LOG_DIR/harness.log" ; }

record_check() {
  local name="$1" result="$2" detail="$3"
  printf '%-46s %-4s %s\n' "$name" "$result" "$detail" | tee -a "$LOG_DIR/checks.txt"
  case "$result" in
    PASS|WARN) : ;;
    *) FAIL=1 ;;
  esac
}

start_owned() {
  # start_owned <name> <logfile> <command...>
  local name="$1" logfile="$2" ; shift 2
  log "start ${name}: $*"
  setsid python3 "$RUN_HELPER" "$@" >"$LOG_DIR/$logfile" 2>&1 &
  local pid=$!
  OWNED_PIDS+=("$pid")
  OWNED_NAMES+=("$name")
  printf '%s %s\n' "$pid" "$name" >>"$LOG_DIR/owned_pids.txt"
}

wait_tcp() {
  # wait_tcp <host> <port> <timeout_s>
  local host="$1" port="$2" timeout="$3" i=0
  while [ "$i" -lt "$((timeout * 5))" ]; do
    if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(0 if s.connect_ex(('$host',$port))==0 else 1)"; then
      return 0
    fi
    sleep 0.2 ; i=$((i + 1))
  done
  return 1
}

cleanup() {
  log "cleanup: tearing down ${#OWNED_PIDS[@]} owned process groups"
  local idx
  for (( idx=${#OWNED_PIDS[@]} - 1 ; idx >= 0 ; idx-- )); do
    local p="${OWNED_PIDS[$idx]}"
    if kill -0 "$p" 2>/dev/null; then
      log "  SIGTERM ${OWNED_NAMES[$idx]} (supervisor $p)"
      kill -TERM "$p" 2>/dev/null
    fi
  done
  local waited=0
  while [ "$waited" -lt 120 ]; do
    local any=0
    for p in "${OWNED_PIDS[@]}"; do kill -0 "$p" 2>/dev/null && any=1; done
    [ "$any" -eq 0 ] && break
    sleep 0.1 ; waited=$((waited + 1))
  done
  for idx in "${!OWNED_PIDS[@]}"; do
    local p="${OWNED_PIDS[$idx]}"
    if kill -0 "$p" 2>/dev/null; then
      log "  escalate SIGUSR1 ${OWNED_NAMES[$idx]} (supervisor $p)"
      kill -USR1 "$p" 2>/dev/null
    fi
  done
  sleep 1

  {
    echo "=== post-cleanup port check ==="
    for pair in "$API_HOST:$API_PORT" "$WS_HOST:$WS_PORT" "$VIDEO_HOST:$VIDEO_PORT" "$UI_HOST:$UI_PORT"; do
      h="${pair%:*}" ; pt="${pair#*:}"
      if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.4); sys.exit(0 if s.connect_ex(('$h',$pt))==0 else 1)"; then
        echo "STILL-LISTENING $pair"
      else
        echo "free $pair"
      fi
    done
    echo "=== post-cleanup owned survivors ==="
    for idx in "${!OWNED_PIDS[@]}"; do
      p="${OWNED_PIDS[$idx]}"
      kill -0 "$p" 2>/dev/null && echo "SURVIVOR ${OWNED_NAMES[$idx]} $p" || echo "gone ${OWNED_NAMES[$idx]} $p"
    done
    echo "=== repository root hygiene ==="
    [ -e "$THESIS_ROOT/log" ] && echo "DIRTY $THESIS_ROOT/log" || echo "clean no-root-log"
    [ -e "$THESIS_ROOT/hailort.log" ] && echo "DIRTY $THESIS_ROOT/hailort.log" || echo "clean no-hailort-log"
    [ -e "$HERE/hailort.log" ] && echo "DIRTY $HERE/hailort.log" || echo "clean no-tools-hailort-log"
  } | tee -a "$LOG_DIR/cleanup_report.txt"
}
trap cleanup EXIT INT TERM

log "run dir: $LOG_DIR"
log "ROS_DOMAIN_ID=$ROS_DOMAIN_ID  bag=$BAG"

# --- environment / preconditions -------------------------------------------
if [ ! -d "$BAG" ]; then log "FATAL: bag not found: $BAG"; exit 2; fi
if [ ! -f "$CANONICAL_CFG" ]; then log "FATAL: canonical TIM config missing"; exit 2; fi
if [ ! -f "$MARS_MODEL" ]; then log "FATAL: MARS model missing: $MARS_MODEL"; exit 2; fi
if [ ! -x "$THESIS_UI_ROOT/tools/start_dashboard.sh" ]; then
  log "FATAL: external UI launcher missing: $THESIS_UI_ROOT/tools/start_dashboard.sh"; exit 2
fi

source /opt/ros/jazzy/setup.bash 2>/dev/null
if [ -f "$THESIS_ROOT/ros2_ws/install/setup.bash" ]; then
  source "$THESIS_ROOT/ros2_ws/install/setup.bash" 2>/dev/null
fi
export ROS_LOG_DIR="$LOG_DIR/ros_log"
mkdir -p "$ROS_LOG_DIR"

# provenance snapshot
{
  echo "run_ts=$RUN_TS"
  echo "thesis_code_head=$(git -C "$THESIS_ROOT" rev-parse HEAD 2>/dev/null)"
  echo "thesis_code_branch=$(git -C "$THESIS_ROOT" branch --show-current 2>/dev/null)"
  echo "thesis_ui_head=$(git -C "$THESIS_UI_ROOT" rev-parse HEAD 2>/dev/null)"
  echo "live_ui_tree_at_36636e9b=$(git -C "$THESIS_ROOT" rev-parse 36636e9b:live-ui 2>/dev/null)"
  echo "ros_domain_id=$ROS_DOMAIN_ID"
  echo "bag=$BAG"
  echo "canonical_cfg_sha256=$(sha256sum "$CANONICAL_CFG" | awk '{print $1}')"
  echo "mars_model_sha256=$(sha256sum "$MARS_MODEL" | awk '{print $1}')"
} | tee "$LOG_DIR/provenance.txt"

# --- 1. dashboard bridge ---------------------------------------------------
start_owned dashboard_bridge dashboard_bridge.log \
  ros2 run thesis_bringup dashboard_bridge_node --ros-args \
    -p api_host:="$API_HOST" -p api_port:="$API_PORT" \
    -p ws_host:="$WS_HOST" -p ws_port:="$WS_PORT" \
    -p runtime_reconfiguration_enabled:=false \
    -p img_w:=640 -p img_h:=640 \
    -p target_authority_event_log_path:="$LOG_DIR/target_authority_events.jsonl"

if wait_tcp "$API_HOST" "$API_PORT" 30 && wait_tcp "$WS_HOST" "$WS_PORT" 30; then
  record_check "dashboard_bridge_api_ws_listening" PASS "api=$API_PORT ws=$WS_PORT"
else
  record_check "dashboard_bridge_api_ws_listening" FAIL "ports did not open"
  log "aborting: dashboard bridge did not come up"; exit 1
fi

# --- 2. fresh canonical TIM-MARS -----------------------------------------
start_owned target_memory_mars target_memory_mars.log \
  ros2 run thesis_bringup target_memory_mars_node --ros-args \
    --params-file "$CANONICAL_CFG" \
    -p image_width:=640.0 -p image_height:=640.0 \
    -p appearance_image_topic:="$IMAGE_TOPIC" \
    -p mars_model_path:="$MARS_MODEL" \
    -p selected_track_id:=0

log "waiting for target_memory_mars_node to register a /target_memory_mars/select subscriber"
tim_ready=0
for i in $(seq 1 90); do
  if ros2 topic info /target_memory_mars/select 2>/dev/null | grep -q "Subscription count: [1-9]"; then
    tim_ready=1 ; break
  fi
  sleep 1
done
if [ "$tim_ready" -eq 1 ]; then
  record_check "tim_mars_node_up_and_subscribed" PASS "select subscriber present"
else
  record_check "tim_mars_node_up_and_subscribed" FAIL "no select subscriber after 90s"
fi
ros2 node info /target_memory_mars_node >"$LOG_DIR/tim_node_info.txt" 2>&1

# --- 3. image relay /camera/image_raw -> /camera/dashboard ---------------
# topic_tools is not installed on the runtime host and image_transport
# republish subscribes RELIABLE (incompatible with the recorded BEST_EFFORT
# camera QoS), so a minimal dedicated best-effort relay is used.
start_owned image_relay image_relay.log \
  python3 "$HERE/m6_image_relay.py" \
    --source "$IMAGE_TOPIC" --target "$DASHBOARD_TOPIC"

# --- 4. web_video_server -------------------------------------------------
start_owned web_video_server web_video_server.log \
  ros2 run web_video_server web_video_server --ros-args \
    -p port:="$VIDEO_PORT" -p address:="$VIDEO_HOST"
if wait_tcp "$VIDEO_HOST" "$VIDEO_PORT" 30; then
  record_check "web_video_server_listening" PASS "port=$VIDEO_PORT"
else
  record_check "web_video_server_listening" FAIL "port did not open"
fi

# --- 5. background topic recorders (evidence of authoritative command path)
start_owned select_echo select_echo.log ros2 topic echo /target_memory_mars/select std_msgs/msg/UInt32
start_owned clear_echo clear_echo.log ros2 topic echo /target_memory_mars/clear std_msgs/msg/Empty
start_owned tim_target_echo tim_target_echo.log ros2 topic echo /target_memory_mars thesis_msgs/msg/TargetState
start_owned tim_status_echo tim_status_echo.log ros2 topic echo /target_memory_mars/status std_msgs/msg/String

# --- 6. bag replay (input topics only, looped) --------------------------
start_owned bag_play bag_play.log \
  ros2 bag play "$BAG" --loop --read-ahead-queue-size 200 \
    --topics "$IMAGE_TOPIC" /detections /tracks

log "waiting for replayed /camera/dashboard traffic"
dash_ok=0
for i in $(seq 1 40); do
  if timeout 6 ros2 topic hz "$DASHBOARD_TOPIC" 2>/dev/null | grep -q "average rate"; then
    dash_ok=1 ; break
  fi
  sleep 1
done
timeout 6 ros2 topic hz "$DASHBOARD_TOPIC" >"$LOG_DIR/camera_dashboard_hz.txt" 2>&1
timeout 6 ros2 topic hz /tracks >"$LOG_DIR/tracks_hz.txt" 2>&1
if [ "$dash_ok" -eq 1 ]; then
  record_check "camera_dashboard_has_replay_traffic" PASS "$(head -c 120 "$LOG_DIR/camera_dashboard_hz.txt" | tr '\n' ' ')"
else
  record_check "camera_dashboard_has_replay_traffic" FAIL "no /camera/dashboard hz"
fi

# --- 7. external UI (delegates to IST-Thesis-UI launcher) ---------------
start_owned external_ui external_ui.log \
  env DASHBOARD_UI_HOST="$UI_HOST" DASHBOARD_UI_PORT="$UI_PORT" \
  "$THESIS_ROOT/tools/start_ui_stack.sh" \
    --api-base-url "http://$API_HOST:$API_PORT" \
    --ws-url "ws://$WS_HOST:$WS_PORT" \
    --host "$UI_HOST" --port "$UI_PORT" --mode backend
if wait_tcp "$UI_HOST" "$UI_PORT" 40; then
  record_check "external_ui_serving_5173" PASS "port=$UI_PORT"
else
  record_check "external_ui_serving_5173" FAIL "port did not open"
fi

# let TIM warm up appearance model + streams settle
log "settling 12s before probe"
sleep 12

# --- 8. HTTP / WS / MJPEG / target-authority probe ---------------------
python3 "$PROBE" \
  --api-base "http://$API_HOST:$API_PORT" \
  --ws-url "ws://$WS_HOST:$WS_PORT" \
  --video-base "http://$VIDEO_HOST:$VIDEO_PORT" \
  --ui-base "http://$UI_HOST:$UI_PORT" \
  --dashboard-topic "$DASHBOARD_TOPIC" \
  --out-dir "$LOG_DIR/probe" 2>&1 | tee "$LOG_DIR/probe.log"
PROBE_RC=${PIPESTATUS[0]}
if [ "$PROBE_RC" -eq 0 ]; then
  record_check "integration_probe" PASS "all probe assertions passed"
else
  record_check "integration_probe" FAIL "probe rc=$PROBE_RC (see probe.log)"
fi

# --- 9. authoritative command path reached the fresh TIM node ----------
if grep -q "data:" "$LOG_DIR/select_echo.log" 2>/dev/null; then
  record_check "select_command_reached_tim_topic" PASS "$(grep -m1 'data:' "$LOG_DIR/select_echo.log" | tr -d ' ')"
else
  record_check "select_command_reached_tim_topic" FAIL "no UInt32 on /target_memory_mars/select"
fi
if [ -s "$LOG_DIR/clear_echo.log" ] && grep -q -- "---" "$LOG_DIR/clear_echo.log" 2>/dev/null; then
  record_check "clear_command_reached_tim_topic" PASS "empty msg observed"
else
  record_check "clear_command_reached_tim_topic" WARN "no clear msg captured"
fi
if [ -s "$LOG_DIR/tim_target_echo.log" ] && grep -q "id:" "$LOG_DIR/tim_target_echo.log" 2>/dev/null; then
  record_check "tim_publishes_target_state" PASS "TargetState observed on /target_memory_mars"
else
  record_check "tim_publishes_target_state" FAIL "no /target_memory_mars output"
fi

# --- 10. safety: nothing flight-related was started -------------------
FLIGHT_HITS="$(pgrep -af 'mavros|px4|pixhawk|control_ref_node|controller_node|apm|mavproxy' | grep -v run_issue55_m6 | grep -v 'pgrep -af')"
if [ -z "$FLIGHT_HITS" ]; then
  record_check "no_flight_stack_running" PASS "no mavros/controller/pixhawk processes"
else
  record_check "no_flight_stack_running" FAIL "$FLIGHT_HITS"
fi

# --- 11. frozen live-ui migration tree unchanged ---------------------
LIVE_UI_AT_M4M5="$(git -C "$THESIS_ROOT" rev-parse 36636e9b:live-ui 2>/dev/null)"
if [ "$LIVE_UI_AT_M4M5" = "634754dd789c32ba1d75216855a9dd77e187774b" ]; then
  record_check "live_ui_migration_tree_matches_provenance" PASS "36636e9b:live-ui=$LIVE_UI_AT_M4M5"
else
  record_check "live_ui_migration_tree_matches_provenance" FAIL "got $LIVE_UI_AT_M4M5"
fi

log "collecting node + topic inventory"
ros2 node list  >"$LOG_DIR/ros_node_list.txt" 2>&1
ros2 topic list >"$LOG_DIR/ros_topic_list.txt" 2>&1

# --- summary --------------------------------------------------------------
echo
echo "==================== ISSUE #55 M6 SUMMARY ===================="
cat "$LOG_DIR/checks.txt"
echo "============================================================="
if [ "$FAIL" -eq 0 ]; then
  echo "M6 RESULT: PASS"
  echo "M6 RESULT: PASS" >"$LOG_DIR/RESULT.txt"
else
  echo "M6 RESULT: FAIL"
  echo "M6 RESULT: FAIL" >"$LOG_DIR/RESULT.txt"
fi
echo "evidence: $LOG_DIR"

exit "$FAIL"
