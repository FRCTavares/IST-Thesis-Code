#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${THESIS_HOST_CONFIG_FILE:-/etc/default/thesis-host-health}"
MODE="${1:-}"

usage() {
    cat <<'EOF'
Usage: sudo set_pi_network_mode.sh unattended|pixhawk|status

pixhawk: prefer ISR Aero.Next GCS Wi-Fi, optionally fall back to the configured
         AERONEXT local-router profile, stop/disable Tailscale, and activate the
         dedicated Pixhawk Ethernet profile without a default route.
unattended: enable/start Tailscale and leave NetworkManager to recover Wi-Fi.
status: report the configured mode and active connections without secrets.
EOF
}

[[ "$EUID" -eq 0 ]] || { echo "[error] root is required"; exit 1; }
[[ -r "$CONFIG_FILE" ]] || { echo "[error] missing $CONFIG_FILE"; exit 1; }

set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
set +a

INTERFACE="${THESIS_HOST_INTERFACE:-wlan0}"
PIXHAWK_WIFI="${THESIS_HOST_PIXHAWK_WIFI_CONNECTION:-ISR Aero.Next GCS}"
PIXHAWK_WIFI_FALLBACK="${THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION:-}"
PIXHAWK_ETHERNET="${THESIS_HOST_PIXHAWK_ETHERNET_CONNECTION:-pixhawk-apm}"

set_mode() {
    local requested="$1"
    sed -i "s/^THESIS_HOST_MODE=.*/THESIS_HOST_MODE=$requested/" "$CONFIG_FILE"
}

connection_exists() {
    nmcli -t -f NAME connection show | grep -Fxq -- "$1"
}

activate_field_wifi() {
    local candidate=""
    local active_wifi=""

    for candidate in "$PIXHAWK_WIFI" "$PIXHAWK_WIFI_FALLBACK"; do
        [ -n "$candidate" ] || continue

        if ! connection_exists "$candidate"; then
            echo "[warn] missing field Wi-Fi profile: $candidate" >&2
            continue
        fi

        echo "[field] trying Wi-Fi profile: $candidate" >&2

        if nmcli connection up "$candidate" ifname "$INTERFACE"; then
            active_wifi="$(
                nmcli -g GENERAL.CONNECTION device show "$INTERFACE"
            )"

            if [ "$active_wifi" = "$candidate" ]; then
                echo "$candidate"
                return 0
            fi
        fi

        echo "[warn] field Wi-Fi activation failed: $candidate" >&2
    done

    return 1
}

case "$MODE" in
    status)
        echo "configured_mode=${THESIS_HOST_MODE:-unattended}"
        echo "wifi_interface=$INTERFACE"
        echo "wifi_connection=$(nmcli -g GENERAL.CONNECTION device show "$INTERFACE" 2>/dev/null || true)"
        echo "field_wifi_primary=$PIXHAWK_WIFI"
        echo "field_wifi_fallback=${PIXHAWK_WIFI_FALLBACK:-none}"
        echo "ethernet_connection=$(nmcli -g GENERAL.CONNECTION device show eth0 2>/dev/null || true)"
        echo "tailscaled=$(systemctl is-active tailscaled.service 2>/dev/null || true)"
        ;;
    pixhawk)
        connection_exists "$PIXHAWK_ETHERNET" || {
            echo "[error] missing NetworkManager profile: $PIXHAWK_ETHERNET"
            exit 1
        }

        # Establish an approved field Wi-Fi path before disabling remote
        # recovery. The canonical ISR GCS profile always has first priority.
        active_wifi="$(activate_field_wifi)" || {
            echo "[error] no approved field Wi-Fi profile could be activated"
            exit 1
        }

        nmcli connection modify "$PIXHAWK_ETHERNET" \
            ipv4.never-default yes ipv6.never-default yes
        nmcli connection up "$PIXHAWK_ETHERNET" ifname eth0
        set_mode pixhawk
        systemctl disable --now tailscaled.service
        systemctl start thesis-host-health.service
        echo "[ok] Pixhawk mode: field Wi-Fi=$active_wifi, Pixhawk Ethernet active, Tailscale disabled"
        ;;
    unattended)
        set_mode unattended
        systemctl enable --now tailscaled.service
        nmcli device connect "$INTERFACE" >/dev/null
        systemctl start thesis-host-health.service
        echo "[ok] unattended mode: NetworkManager recovery and Tailscale enabled"
        ;;
    *)
        usage
        exit 2
        ;;
esac
