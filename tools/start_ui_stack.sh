#!/usr/bin/env bash

set +u

THESIS_UI_ROOT="${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}"
UI_LAUNCHER="$THESIS_UI_ROOT/tools/start_dashboard.sh"

MODE="${VITE_DASHBOARD_DATA_MODE:-}"
HOST="${UI_HOST:-${DASHBOARD_UI_HOST:-}}"
PORT="${UI_PORT:-${DASHBOARD_UI_PORT:-}}"
API_BASE_URL="${VITE_DASHBOARD_API_BASE_URL:-}"
WS_URL="${VITE_DASHBOARD_WS_URL:-}"

INSTALL=0
VERBOSE="${UI_STACK_VERBOSE:-0}"

if [[ "${UI_SKIP_INSTALL:-1}" =~ ^(0|false|FALSE|no|NO)$ ]]; then
    INSTALL=1
fi

if [[ "$VERBOSE" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
    VERBOSE=1
else
    VERBOSE=0
fi

print_usage() {
    cat <<EOF_USAGE
Usage: start_ui_stack.sh [options]

Compatibility shim for the separately owned IST-Thesis-UI frontend.

Authoritative frontend repository:
  $THESIS_UI_ROOT

Options:
  --mode <backend|mock|offline>   Dashboard data mode
  -v, --verbose                   Print compatibility delegation details
  --host <host>                   Vite bind host
  --port <port>                   Vite port
  --api-base-url <url>            Set VITE_DASHBOARD_API_BASE_URL
  --ws-url <url>                  Set VITE_DASHBOARD_WS_URL
  --install                       Forward dependency installation request
  --skip-install                  Do not install dependencies (default)
  -h, --help                      Show this help

Environment:
  THESIS_UI_ROOT                  External UI repository root
                                  Default: \$HOME/Desktop/IST-Thesis-UI

Legacy environment variables UI_HOST, UI_PORT, UI_SKIP_INSTALL, and
UI_STACK_VERBOSE remain accepted by this compatibility shim.

For new frontend-specific workflows, run directly:
  \$THESIS_UI_ROOT/tools/start_dashboard.sh
EOF_USAGE
}

FORWARD_ARGS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        --mode)
            if [ "$#" -lt 2 ]; then
                printf '[error] --mode requires a value\n' >&2
                exit 2
            fi
            MODE="$2"
            shift 2
            ;;
        --host)
            if [ "$#" -lt 2 ]; then
                printf '[error] --host requires a value\n' >&2
                exit 2
            fi
            HOST="$2"
            shift 2
            ;;
        --port)
            if [ "$#" -lt 2 ]; then
                printf '[error] --port requires a value\n' >&2
                exit 2
            fi
            PORT="$2"
            shift 2
            ;;
        --api-base-url)
            if [ "$#" -lt 2 ]; then
                printf '[error] --api-base-url requires a value\n' >&2
                exit 2
            fi
            API_BASE_URL="$2"
            shift 2
            ;;
        --ws-url)
            if [ "$#" -lt 2 ]; then
                printf '[error] --ws-url requires a value\n' >&2
                exit 2
            fi
            WS_URL="$2"
            shift 2
            ;;
        --install)
            INSTALL=1
            shift
            ;;
        --skip-install)
            INSTALL=0
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            FORWARD_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ -n "$MODE" ]; then
    FORWARD_ARGS+=(--mode "$MODE")
fi

if [ -n "$HOST" ]; then
    FORWARD_ARGS+=(--host "$HOST")
fi

if [ -n "$PORT" ]; then
    FORWARD_ARGS+=(--port "$PORT")
fi

if [ "$INSTALL" -eq 1 ]; then
    FORWARD_ARGS+=(--install)
fi

if [ -n "$API_BASE_URL" ]; then
    export VITE_DASHBOARD_API_BASE_URL="$API_BASE_URL"
fi

if [ -n "$WS_URL" ]; then
    export VITE_DASHBOARD_WS_URL="$WS_URL"
fi

if [ ! -d "$THESIS_UI_ROOT" ]; then
    printf '[error] external UI repository not found: %s\n' "$THESIS_UI_ROOT" >&2
    printf '[hint] clone FRCTavares/IST-Thesis-UI or set THESIS_UI_ROOT\n' >&2
    exit 3
fi

if [ ! -x "$UI_LAUNCHER" ]; then
    printf '[error] external UI launcher missing or not executable: %s\n' "$UI_LAUNCHER" >&2
    exit 3
fi

if [ "$VERBOSE" -eq 1 ]; then
    printf '[info] Thesis-Code UI compatibility shim\n'
    printf '[info] delegating to: %s\n' "$UI_LAUNCHER"

    if [ -n "$API_BASE_URL" ]; then
        printf '[info] api: %s\n' "$API_BASE_URL"
    fi

    if [ -n "$WS_URL" ]; then
        printf '[info] websocket: %s\n' "$WS_URL"
    fi
fi

exec "$UI_LAUNCHER" "${FORWARD_ARGS[@]}"
