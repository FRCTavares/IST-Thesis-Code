#!/usr/bin/env bash

set +u

THESIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_ROOT="${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}"
UI_LAUNCHER="$UI_ROOT/tools/start_dashboard.sh"

UI_PORT="${FIELD_UI_PORT:-5173}"
API_PORT=8090
WS_PORT=8765
VIDEO_PORT=8080

ALLOW_UNAPPROVED_WIFI="${FIELD_UI_ALLOW_UNAPPROVED_WIFI:-0}"
ALLOW_TAILSCALE="${FIELD_UI_ALLOW_TAILSCALE:-0}"

RUN_ID="$(date +%F__%H-%M-%S)"
RUN_DIR="$THESIS_ROOT/ros2_ws/log/field_ui/$RUN_ID"
LIVE_FIFO="$RUN_DIR/live_stack.fifo"
LIVE_LOG="$RUN_DIR/live_stack.log"
UI_LOG="$RUN_DIR/ui.log"

LIVE_PID=""
UI_PID=""
CLEANED=0

mkdir -p "$RUN_DIR" || exit 1

cleanup() {
    if [ "$CLEANED" -eq 1 ]; then
        return
    fi
    CLEANED=1

    printf '\n[field-ui] stopping...\n'

    if [ -n "$LIVE_PID" ] && kill -0 "$LIVE_PID" 2>/dev/null; then
        printf 'stop\n' >&9 2>/dev/null || true

        for _ in $(seq 1 20); do
            if ! kill -0 "$LIVE_PID" 2>/dev/null; then
                break
            fi
            sleep 0.25
        done

        if kill -0 "$LIVE_PID" 2>/dev/null; then
            kill -TERM "$LIVE_PID" 2>/dev/null || true
        fi
    fi

    if [ -n "$UI_PID" ] && kill -0 "$UI_PID" 2>/dev/null; then
        kill -TERM "$UI_PID" 2>/dev/null || true
        wait "$UI_PID" 2>/dev/null || true
    fi

    exec 9>&- 2>/dev/null || true

    rm -f "$LIVE_FIFO"

    printf '[field-ui] stopped\n'
}

trap cleanup INT TERM EXIT

printf '\n============================================================\n'
printf 'THESIS FIELD UI\n'
printf '============================================================\n'

cd "$THESIS_ROOT" || exit 1

if [ ! -x "$UI_LAUNCHER" ]; then
    printf '[error] external UI launcher not found: %s\n' "$UI_LAUNCHER" >&2
    exit 2
fi

if [ ! -f "$UI_ROOT/dist/index.html" ]; then
    printf '[error] prebuilt UI artifact not found: %s\n' "$UI_ROOT/dist/index.html" >&2
    printf '[hint] build IST-Thesis-UI before field deployment; no npm, Node, Vite, or node_modules are required during field runtime\n' >&2
    exit 2
fi

WLAN_IP="$(
    ip -4 -o addr show dev wlan0 2>/dev/null \
        | awk '{split($4,a,"/"); print a[1]; exit}'
)"

if [ -z "$WLAN_IP" ]; then
    printf '[error] wlan0 has no IPv4 address\n' >&2
    exit 3
fi

SSID="$(
    nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null \
        | sed -n 's/^yes://p' \
        | head -n 1
)"

if [ -z "$SSID" ]; then
    printf '[error] no active Wi-Fi SSID detected on wlan0\n' >&2
    exit 3
fi

SSID_LOWER="${SSID,,}"

WIFI_APPROVED=0
if [ "$SSID" = "ISR Aero.Next GCS" ]; then
    WIFI_APPROVED=1
elif [[ "$SSID_LOWER" == *"aeronext"* || "$SSID_LOWER" == *"aero.next"* ]]; then
    WIFI_APPROVED=1
fi

if [ "$WIFI_APPROVED" -ne 1 ]; then
    if [[ "$ALLOW_UNAPPROVED_WIFI" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
        printf '[warn] bench override: unapproved Wi-Fi accepted: %s\n' "$SSID"
    else
        printf '[error] current Wi-Fi is not an approved field network: %s\n' "$SSID" >&2
        printf '[expected] ISR Aero.Next GCS or an AERONEXT local network\n' >&2
        printf '[bench only] FIELD_UI_ALLOW_UNAPPROVED_WIFI=1 tools/start_field_ui.sh\n' >&2
        exit 4
    fi
fi

TAILSCALE_ACTIVE=0

if systemctl is-active --quiet tailscaled 2>/dev/null; then
    TAILSCALE_ACTIVE=1
fi

if ip link show tailscale0 >/dev/null 2>&1; then
    TAILSCALE_ACTIVE=1
fi

TAILSCALE_STATUS="inactive"

if [ "$TAILSCALE_ACTIVE" -eq 1 ]; then
    if [[ "$ALLOW_TAILSCALE" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
        printf '[warn] bench override: Tailscale is active\n'
        TAILSCALE_STATUS="active (bench override)"
    else
        printf '[error] Tailscale is active; field policy requires it inactive\n' >&2
        printf '[error] refusing to start the field UI\n' >&2
        printf '[note] the launcher does not disable Tailscale automatically because doing so can terminate a remote maintenance session\n' >&2
        exit 5
    fi
fi

for PORT in "$UI_PORT" "$API_PORT" "$WS_PORT" "$VIDEO_PORT"; do
    if ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${PORT}$"; then
        printf '[error] TCP port %s is already in use\n' "$PORT" >&2
        printf '[hint] stop the previous dashboard/live session before field launch\n' >&2
        exit 6
    fi
done

printf '\n[field-ui] network\n'
printf '  SSID: %s\n' "$SSID"
printf '  Pi:   %s\n' "$WLAN_IP"

printf '\n[field-ui] safety\n'
printf '  Tailscale: %s\n' "$TAILSCALE_STATUS"
printf '  UI bind:   %s:%s\n' "$WLAN_IP" "$UI_PORT"
printf '  API bind:  %s:%s\n' "$WLAN_IP" "$API_PORT"
printf '  WS bind:   %s:%s\n' "$WLAN_IP" "$WS_PORT"
printf '  video:     %s:%s\n' "$WLAN_IP" "$VIDEO_PORT"

printf '\n[field-ui] logs\n'
printf '  %s\n' "$RUN_DIR"

mkfifo "$LIVE_FIFO" || exit 7

# Keep both ends open so start_live_stack.sh does not see EOF while the
# field launcher owns the session.
exec 9<>"$LIVE_FIFO"

export PI_IP="$WLAN_IP"

export DASHBOARD_BRIDGE_BIND_HOST="$WLAN_IP"
export DASHBOARD_BRIDGE_ALLOWED_ORIGINS="http://${WLAN_IP}:${UI_PORT}"
export DASHBOARD_BRIDGE_PUBLISH_HZ="30.0"

export WEB_VIDEO_BIND_HOST="$WLAN_IP"

printf '\n[field-ui] starting canonical live stack...\n'

"$THESIS_ROOT/tools/start_live_stack.sh" "$@" \
    < "$LIVE_FIFO" \
    > "$LIVE_LOG" 2>&1 &

LIVE_PID=$!

printf '[field-ui] starting browser frontend...\n'

XDG_STATE_HOME="$RUN_DIR/ui_state" \
VITE_DASHBOARD_DATA_MODE=backend \
"$UI_LAUNCHER" \
    --mode backend \
    --host "$WLAN_IP" \
    --port "$UI_PORT" \
    > "$UI_LOG" 2>&1 &

UI_PID=$!

wait_http() {
    local url="$1"
    local attempts="${2:-60}"

    for _ in $(seq 1 "$attempts"); do
        if curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
            return 0
        fi

        if ! kill -0 "$LIVE_PID" 2>/dev/null; then
            return 1
        fi

        sleep 1
    done

    return 1
}

wait_tcp() {
    local host="$1"
    local port="$2"
    local attempts="${3:-60}"

    for _ in $(seq 1 "$attempts"); do
        if timeout 1 bash -c "echo >/dev/tcp/${host}/${port}" \
            >/dev/null 2>&1; then
            return 0
        fi

        if ! kill -0 "$LIVE_PID" 2>/dev/null; then
            return 1
        fi

        sleep 1
    done

    return 1
}

printf '\n[field-ui] waiting for backend readiness...\n'

READY=1

if ! wait_http "http://${WLAN_IP}:${API_PORT}/api/models" 60; then
    printf '[error] dashboard API did not become ready\n' >&2
    READY=0
fi

if ! wait_tcp "$WLAN_IP" "$WS_PORT" 10; then
    printf '[error] dashboard WebSocket did not become ready\n' >&2
    READY=0
fi

if ! wait_tcp "$WLAN_IP" "$VIDEO_PORT" 10; then
    printf '[error] MJPEG server did not become ready\n' >&2
    READY=0
fi

if ! wait_http "http://${WLAN_IP}:${UI_PORT}/" 20; then
    printf '[error] frontend did not become ready\n' >&2
    READY=0
fi

if [ "$READY" -ne 1 ]; then
    printf '\n===== LIVE LOG TAIL =====\n'
    tail -n 80 "$LIVE_LOG" 2>/dev/null || true

    printf '\n===== UI LOG TAIL =====\n'
    tail -n 80 "$UI_LOG" 2>/dev/null || true

    exit 8
fi

PHONE_URL="http://${WLAN_IP}:${UI_PORT}"

printf '\n============================================================\n'
printf 'FIELD UI READY\n'
printf '============================================================\n'
printf '\n'
printf 'Network: %s\n' "$SSID"
printf 'Pi:      %s\n' "$WLAN_IP"
printf '\n'
printf 'Open on iPhone:\n'
printf '  %s\n' "$PHONE_URL"
printf '\n'

if command -v qrencode >/dev/null 2>&1; then
    printf 'Scan locally generated QR code:\n\n'
    qrencode -t ANSIUTF8 "$PHONE_URL"
    printf '\n'
else
    printf 'QR: qrencode is not installed; URL above works fully offline.\n'
fi

printf '\n'
printf 'No internet connection is required.\n'
printf 'Press Ctrl-C here to stop the complete field UI/live session.\n'
printf '\n============================================================\n'

while true; do
    if ! kill -0 "$LIVE_PID" 2>/dev/null; then
        printf '\n[error] live stack exited unexpectedly\n' >&2
        tail -n 80 "$LIVE_LOG" 2>/dev/null || true
        exit 9
    fi

    if ! kill -0 "$UI_PID" 2>/dev/null; then
        printf '\n[error] frontend exited unexpectedly\n' >&2
        tail -n 80 "$UI_LOG" 2>/dev/null || true
        exit 10
    fi

    sleep 2
done
