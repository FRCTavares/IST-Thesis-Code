#!/usr/bin/env bash
set -euo pipefail

# start_ui_stack.sh
#
# Purpose:
# - Start the dashboard frontend in a consistent way.
# - Make it easy to run in parallel with tools/start_live_stack.sh.
# - Keep UI startup logs under ros2_ws/log/ui_stack/<run-id>/.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_WS="${ROS_WS:-$THESIS_ROOT/ros2_ws}"
UI_DIR="${UI_DIR:-$THESIS_ROOT/live-ui}"
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}' || true)}"

if [[ -z "${PI_IP// }" ]]; then
    PI_IP="127.0.0.1"
fi

LOG_ROOT="$ROS_WS/log/ui_stack"
RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
RUN_DIR="$LOG_ROOT/$RUN_ID"
LATEST_LINK="$LOG_ROOT/latest"

MODE="${VITE_DASHBOARD_DATA_MODE:-backend}"
UI_HOST="${UI_HOST:-0.0.0.0}"
UI_PORT="${UI_PORT:-5173}"
API_BASE_URL="${VITE_DASHBOARD_API_BASE_URL:-http://${PI_IP}:8090}"
WS_URL="${VITE_DASHBOARD_WS_URL:-ws://${PI_IP}:8765}"
SKIP_INSTALL="${UI_SKIP_INSTALL:-1}"
VERBOSE="${UI_STACK_VERBOSE:-0}"

if [[ "$SKIP_INSTALL" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
    SKIP_INSTALL=1
else
    SKIP_INSTALL=0
fi

if [[ "$VERBOSE" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
    VERBOSE=1
else
    VERBOSE=0
fi

log_verbose_tag() {
    local tag="$1"
    shift
    if [[ "$VERBOSE" -eq 1 ]]; then
        echo "[$tag] $*"
    fi
}

log_info() { log_verbose_tag info "$@"; }
log_step() { log_verbose_tag step "$@"; }
log_hint() { log_verbose_tag hint "$@"; }

wait_for_ui_ready() {
    local pid="$1"
    local host="$2"
    local port="$3"
    local timeout_s="$4"

    local start_ts
    start_ts="$(date +%s)"

    while true; do
        if ! kill -0 "$pid" >/dev/null 2>&1; then
            return 2
        fi

        if (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
            return 0
        fi

        local now
        now="$(date +%s)"
        if (( now - start_ts >= timeout_s )); then
            return 1
        fi

        sleep 1
    done
}

print_usage() {
    cat <<EOF
Usage: start_ui_stack.sh [options]

Starts the dashboard frontend and keeps logs in ros2_ws/log/ui_stack/<run-id>/.
Run this in a second terminal while tools/start_live_stack.sh is running.

Options:
  --mode <backend|mock|offline>   Data mode for dashboard (default: backend)
  -v, --verbose                   Enable verbose startup logs (default: warnings/errors only)
  --host <host>                   Vite host bind (default: 0.0.0.0)
  --port <port>                   Vite dev server port (default: 5173)
  --api-base-url <url>            Override VITE_DASHBOARD_API_BASE_URL
  --ws-url <url>                  Override VITE_DASHBOARD_WS_URL
  --install                       Run npm install before start (default: skipped)
  --skip-install                  Skip npm install step (default)
  -h, --help                      Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --mode)
            if [[ $# -lt 2 ]]; then
                echo "[error] --mode requires a value"
                print_usage
                exit 1
            fi
            MODE="$2"
            shift 2
            ;;
        --host)
            if [[ $# -lt 2 ]]; then
                echo "[error] --host requires a value"
                print_usage
                exit 1
            fi
            UI_HOST="$2"
            shift 2
            ;;
        --port)
            if [[ $# -lt 2 ]]; then
                echo "[error] --port requires a value"
                print_usage
                exit 1
            fi
            UI_PORT="$2"
            shift 2
            ;;
        --api-base-url)
            if [[ $# -lt 2 ]]; then
                echo "[error] --api-base-url requires a value"
                print_usage
                exit 1
            fi
            API_BASE_URL="$2"
            shift 2
            ;;
        --ws-url)
            if [[ $# -lt 2 ]]; then
                echo "[error] --ws-url requires a value"
                print_usage
                exit 1
            fi
            WS_URL="$2"
            shift 2
            ;;
        --install)
            SKIP_INSTALL=0
            shift
            ;;
        --skip-install)
            SKIP_INSTALL=1
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

case "$MODE" in
    backend|mock|offline)
        ;;
    *)
        echo "[error] invalid --mode '$MODE' (expected backend|mock|offline)"
        exit 1
        ;;
esac

if ! [[ "$UI_PORT" =~ ^[0-9]+$ ]] || [[ "$UI_PORT" -lt 1 ]] || [[ "$UI_PORT" -gt 65535 ]]; then
    echo "[error] --port must be an integer between 1 and 65535"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "[error] npm is not installed or not in PATH"
    exit 1
fi

if [[ ! -d "$UI_DIR" ]]; then
    echo "[error] UI directory not found: $UI_DIR"
    exit 1
fi

mkdir -p "$RUN_DIR"
ln -sfn "$RUN_DIR" "$LATEST_LINK"

log_info "run: $RUN_ID logs=$RUN_DIR"
log_info "ui: mode=$MODE bind=${UI_HOST}:${UI_PORT}"
log_info "backend: api=$API_BASE_URL ws=$WS_URL"

log_step "preparing frontend"
cd "$UI_DIR"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    log_step "npm install"
    npm install >"$RUN_DIR/npm_install.log" 2>&1
else
    log_info "npm install skipped"
fi

export VITE_DASHBOARD_DATA_MODE="$MODE"
export VITE_DASHBOARD_API_BASE_URL="$API_BASE_URL"
export VITE_DASHBOARD_WS_URL="$WS_URL"

log_step "starting UI server"
log_hint "open: http://127.0.0.1:$UI_PORT (or PI IP if remote)"
log_hint "stop: Ctrl-C"

npm run dev -- --host "$UI_HOST" --port "$UI_PORT" >"$RUN_DIR/ui.log" 2>&1 &
UI_PID=$!

UI_HEALTH_HOST="$UI_HOST"
if [[ "$UI_HEALTH_HOST" == "0.0.0.0" ]] || [[ "$UI_HEALTH_HOST" == "::" ]]; then
    UI_HEALTH_HOST="127.0.0.1"
fi

set +e
wait_for_ui_ready "$UI_PID" "$UI_HEALTH_HOST" "$UI_PORT" 25
ready_rc=$?
set -e

if [[ "$ready_rc" -eq 2 ]]; then
    set +e
    wait "$UI_PID"
    rc=$?
    set -e
    echo "[error] UI server exited during startup (code=$rc); see $RUN_DIR/ui.log"
    exit "$rc"
fi

if [[ "$ready_rc" -eq 1 ]]; then
    echo "[error] timeout waiting for UI server on ${UI_HEALTH_HOST}:${UI_PORT}; see $RUN_DIR/ui.log"
    kill "$UI_PID" >/dev/null 2>&1 || true
    wait "$UI_PID" >/dev/null 2>&1 || true
    exit 1
fi

LOCAL_URL="http://127.0.0.1:${UI_PORT}"
REMOTE_URL="http://${PI_IP}:${UI_PORT}"
echo "[ok] UI started successfully"
echo "[ok] Dashboard URLs"
echo "  local : ${LOCAL_URL}"
echo "  remote: ${REMOTE_URL}"
echo "[ok] Backend Endpoints"
echo "  api   : ${API_BASE_URL}"
echo "  ws    : ${WS_URL}"
echo "[ok] Logs"
echo "  run   : ${RUN_DIR}"
echo "  ui    : ${RUN_DIR}/ui.log"

TAIL_PID=""
if [[ "$VERBOSE" -eq 1 ]]; then
    tail -n +1 -f "$RUN_DIR/ui.log" &
    TAIL_PID=$!
fi

set +e
wait "$UI_PID"
rc=$?
set -e

if [[ -n "${TAIL_PID:-}" ]]; then
    kill "$TAIL_PID" >/dev/null 2>&1 || true
    wait "$TAIL_PID" >/dev/null 2>&1 || true
fi

if [[ "$rc" -ne 0 ]] && [[ "$rc" -ne 130 ]]; then
    echo "[error] UI server exited (code=$rc); see $RUN_DIR/ui.log"
fi

exit "$rc"
