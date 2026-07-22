#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${THESIS_HOST_CONFIG_FILE:-/etc/default/thesis-host-health}"
MODE="${1:-}"

usage() {
    cat <<'EOF'
Usage: sudo set_pi_network_mode.sh unattended|pixhawk|status

pixhawk: require ISR Aero.Next GCS Wi-Fi, stop/disable Tailscale, and activate
         the dedicated Pixhawk Ethernet profile without a default route.
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
PIXHAWK_ETHERNET="${THESIS_HOST_PIXHAWK_ETHERNET_CONNECTION:-pixhawk-apm}"

set_mode() {
    local requested="$1"
    sed -i "s/^THESIS_HOST_MODE=.*/THESIS_HOST_MODE=$requested/" "$CONFIG_FILE"
}

connection_exists() {
    nmcli -t -f NAME connection show | grep -Fxq -- "$1"
}

case "$MODE" in
    status)
        echo "configured_mode=${THESIS_HOST_MODE:-unattended}"
        echo "wifi_interface=$INTERFACE"
        echo "wifi_connection=$(nmcli -g GENERAL.CONNECTION device show "$INTERFACE" 2>/dev/null || true)"
        echo "ethernet_connection=$(nmcli -g GENERAL.CONNECTION device show eth0 2>/dev/null || true)"
        echo "tailscaled=$(systemctl is-active tailscaled.service 2>/dev/null || true)"
        ;;
    pixhawk)
        connection_exists "$PIXHAWK_WIFI" || {
            echo "[error] missing NetworkManager profile: $PIXHAWK_WIFI"
            exit 1
        }
        connection_exists "$PIXHAWK_ETHERNET" || {
            echo "[error] missing NetworkManager profile: $PIXHAWK_ETHERNET"
            exit 1
        }

        # Establish the required physical path before disabling remote recovery.
        nmcli connection up "$PIXHAWK_WIFI" ifname "$INTERFACE"
        active_wifi="$(nmcli -g GENERAL.CONNECTION device show "$INTERFACE")"
        [[ "$active_wifi" == "$PIXHAWK_WIFI" ]] || {
            echo "[error] AERONEXT Wi-Fi did not become active"
            exit 1
        }

        nmcli connection modify "$PIXHAWK_ETHERNET" \
            ipv4.never-default yes ipv6.never-default yes
        nmcli connection up "$PIXHAWK_ETHERNET" ifname eth0
        set_mode pixhawk
        systemctl disable --now tailscaled.service
        systemctl start thesis-host-health.service
        echo "[ok] Pixhawk mode: AERONEXT active, Pixhawk Ethernet active, Tailscale disabled"
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
