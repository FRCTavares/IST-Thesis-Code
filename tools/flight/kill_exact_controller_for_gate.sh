#!/usr/bin/env bash
set +u

RUN_ID="${1:-}"

if [[ -z "$RUN_ID" ]]; then
    echo "Usage: $0 RUN_ID"
    exit 2
fi

RUN_DIR="ros2_ws/log/live_stack/$RUN_ID"
PID_FILE="$RUN_DIR/pids.txt"

if [[ ! -f "$PID_FILE" ]]; then
    echo "FAIL: $PID_FILE missing"
    exit 1
fi

LAUNCH_PID="$(awk '$2=="control" {print $1}' "$PID_FILE")"

if [[ "$(printf '%s\n' "$LAUNCH_PID" | sed '/^$/d' | wc -l)" -ne 1 ]]; then
    echo "FAIL: control launcher PID missing/ambiguous"
    exit 1
fi

EXE_PID="$(pgrep -P "$LAUNCH_PID" -f control_ref_node || true)"

if [[ "$(printf '%s\n' "$EXE_PID" | sed '/^$/d' | wc -l)" -ne 1 ]]; then
    echo "FAIL: controller child PID missing/ambiguous"
    exit 1
fi

ps -p "$LAUNCH_PID","$EXE_PID" -o pid,ppid,args

read -r -p "Non-zero reference visible. Type YES to kill exact child $EXE_PID: " CONFIRM

if [[ "$CONFIRM" != "YES" ]]; then
    echo "CANCELLED"
    exit 1
fi

date --iso-8601=ns | tee "$RUN_DIR/controller_process_loss.txt"
kill -KILL "$EXE_PID"
RC=$?
date --iso-8601=ns | tee -a "$RUN_DIR/controller_process_loss.txt"

if [[ "$RC" -ne 0 ]]; then
    echo "FAIL: kill failed"
    exit 1
fi

sleep 1

if kill -0 "$EXE_PID" 2>/dev/null; then
    echo "FAIL: controller child still alive"
    exit 1
fi

echo "PASS: exact controller child terminated"
