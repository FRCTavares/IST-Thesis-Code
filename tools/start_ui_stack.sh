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
UI_DIR="${UI_DIR:-$THESIS_ROOT/user-interface}"
PI_IP="${PI_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"

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
SKIP_INSTALL=0

print_usage() {
    cat <<EOF
Usage: start_ui_stack.sh [options]

Starts the dashboard frontend and keeps logs in ros2_ws/log/ui_stack/<run-id>/.
Run this in a second terminal while tools/start_live_stack.sh is running.

Options:
  --mode <backend|mock|offline>   Data mode for dashboard (default: backend)
  --host <host>                   Vite host bind (default: 0.0.0.0)
  --port <port>                   Vite dev server port (default: 5173)
  --api-base-url <url>            Override VITE_DASHBOARD_API_BASE_URL
  --ws-url <url>                  Override VITE_DASHBOARD_WS_URL
  --skip-install                  Skip npm install step
  -h, --help                      Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
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

echo "[info] run: $RUN_ID logs=$RUN_DIR"
echo "[info] ui: mode=$MODE bind=${UI_HOST}:${UI_PORT}"
echo "[info] backend: api=$API_BASE_URL ws=$WS_URL"

echo "[step] preparing frontend"
cd "$UI_DIR"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    echo "[step] npm install"
    npm install >"$RUN_DIR/npm_install.log" 2>&1
else
    echo "[info] npm install skipped"
fi

export VITE_DASHBOARD_DATA_MODE="$MODE"
export VITE_DASHBOARD_API_BASE_URL="$API_BASE_URL"
export VITE_DASHBOARD_WS_URL="$WS_URL"

echo "[step] starting UI server"
echo "[info] open: http://127.0.0.1:$UI_PORT (or PI IP if remote)"
echo "[info] stop: Ctrl-C"

npm run dev -- --host "$UI_HOST" --port "$UI_PORT" 2>&1 | tee "$RUN_DIR/ui.log"
