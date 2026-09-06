#!/usr/bin/env bash

set +u

# Compatibility entrypoint for the independently owned IST-Thesis-UI frontend.
#
# Frontend build/runtime implementation belongs to:
#   ${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}/tools/start_dashboard.sh
#
# Thesis-Code deliberately contains no npm, Vite, static-server, or frontend
# logging implementation here.

THESIS_UI_ROOT="${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}"
UI_LAUNCHER="$THESIS_UI_ROOT/tools/start_dashboard.sh"

if [ -n "${UI_HOST:-}" ] && [ -z "${DASHBOARD_UI_HOST:-}" ]; then
    export DASHBOARD_UI_HOST="$UI_HOST"
fi

if [ -n "${UI_PORT:-}" ] && [ -z "${DASHBOARD_UI_PORT:-}" ]; then
    export DASHBOARD_UI_PORT="$UI_PORT"
fi

FORWARD_ARGS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --api-base-url)
            if [ "$#" -lt 2 ]; then
                printf 'ERROR: --api-base-url requires a value\n' >&2
                exit 2
            fi
            export VITE_DASHBOARD_API_BASE_URL="$2"
            shift 2
            ;;
        --ws-url)
            if [ "$#" -lt 2 ]; then
                printf 'ERROR: --ws-url requires a value\n' >&2
                exit 2
            fi
            export VITE_DASHBOARD_WS_URL="$2"
            shift 2
            ;;
        --skip-install)
            # The authoritative launcher already skips installation by default.
            shift
            ;;
        -v|--verbose)
            printf 'NOTE: %s is a legacy compatibility flag and is ignored.\n' "$1" >&2
            shift
            ;;
        *)
            FORWARD_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ ! -d "$THESIS_UI_ROOT" ]; then
    printf 'ERROR: IST-Thesis-UI checkout not found: %s\n' "$THESIS_UI_ROOT" >&2
    printf 'Set THESIS_UI_ROOT to the frontend repository checkout.\n' >&2
    exit 3
fi

if [ ! -f "$UI_LAUNCHER" ]; then
    printf 'ERROR: authoritative UI launcher not found: %s\n' "$UI_LAUNCHER" >&2
    exit 3
fi

if [ ! -x "$UI_LAUNCHER" ]; then
    printf 'ERROR: authoritative UI launcher is not executable: %s\n' "$UI_LAUNCHER" >&2
    exit 3
fi

exec "$UI_LAUNCHER" "${FORWARD_ARGS[@]}"
