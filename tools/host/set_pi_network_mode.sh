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

# Serialize explicit operator transitions and automatic fail-closed exits.
# A dispatcher-triggered unattended transition waits for any in-progress
# explicit pixhawk transition to finish before changing host networking.
LOCK_FILE="${THESIS_HOST_NETWORK_MODE_LOCK:-/run/lock/thesis-network-mode.lock}"
exec 9>"$LOCK_FILE"
flock -x 9

set_mode() {
    local requested="$1"
    sed -i "s/^THESIS_HOST_MODE=.*/THESIS_HOST_MODE=$requested/" "$CONFIG_FILE"
}

connection_exists() {
    nmcli -t -f NAME connection show | grep -Fxq -- "$1"
}

disable_field_wifi_autoconnect() {
    local candidate=""

    for candidate in "$PIXHAWK_WIFI" "$PIXHAWK_WIFI_FALLBACK"; do
        [ -n "$candidate" ] || continue
        connection_exists "$candidate" || continue

        nmcli connection modify "$candidate" connection.autoconnect no
    done
}

is_field_wifi() {
    local connection="${1:-}"
    local candidate=""

    [ -n "$connection" ] || return 1

    for candidate in "$PIXHAWK_WIFI" "$PIXHAWK_WIFI_FALLBACK"; do
        [ -n "$candidate" ] || continue
        [ "$connection" = "$candidate" ] && return 0
    done

    return 1
}

disconnect_active_field_wifi() {
    local active_wifi=""
    local remaining_wifi=""

    active_wifi="$(
        nmcli -g GENERAL.CONNECTION device show "$INTERFACE" 2>/dev/null             || true
    )"

    if ! is_field_wifi "$active_wifi"; then
        return 0
    fi

    echo "[field] disconnecting field Wi-Fi profile: $active_wifi"

    if ! nmcli connection down "$active_wifi" >/dev/null 2>&1; then
        # Hard fail-closed fallback: it is safer to drop wlan0 entirely than
        # leave an approved GCS profile active without a valid Pixhawk link.
        nmcli device disconnect "$INTERFACE" >/dev/null 2>&1 || true
    fi

    remaining_wifi="$(
        nmcli -g GENERAL.CONNECTION device show "$INTERFACE" 2>/dev/null             || true
    )"

    if is_field_wifi "$remaining_wifi"; then
        echo "[error] field Wi-Fi remained active after unattended transition" >&2
        return 1
    fi
}

require_pixhawk_carrier() {
    local interface=""

    interface="$(
        nmcli -g connection.interface-name \
            connection show "$PIXHAWK_ETHERNET" 2>/dev/null \
            | head -n 1
    )"

    if [ -z "$interface" ]; then
        echo "[error] Pixhawk Ethernet profile has no bound interface: $PIXHAWK_ETHERNET" >&2
        return 1
    fi

    if [ ! -r "/sys/class/net/$interface/carrier" ]; then
        echo "[error] Pixhawk Ethernet interface not present: $interface" >&2
        return 1
    fi

    if [ "$(cat "/sys/class/net/$interface/carrier" 2>/dev/null || true)" != "1" ]; then
        echo "[error] no physical Pixhawk Ethernet carrier on $interface" >&2
        return 1
    fi

    echo "$interface"
}

verify_pixhawk_ethernet_state() {
    local interface="$1"
    local active_connection=""

    if [ "$(cat "/sys/class/net/$interface/carrier" 2>/dev/null || true)" != "1" ]; then
        echo "[error] Pixhawk Ethernet carrier disappeared on $interface" >&2
        return 1
    fi

    active_connection="$(
        nmcli -g GENERAL.CONNECTION device show "$interface" 2>/dev/null             || true
    )"

    if [ "$active_connection" != "$PIXHAWK_ETHERNET" ]; then
        echo "[error] Pixhawk Ethernet profile is not active on $interface" >&2
        return 1
    fi

    if ip route show default dev "$interface" | grep -q .; then
        echo "[error] Pixhawk Ethernet unexpectedly owns a default route" >&2
        return 1
    fi
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

maybe_start_health_check() {
    if [ "${THESIS_HOST_SKIP_HEALTH_RECHECK:-0}" != "1" ]; then
        systemctl start thesis-host-health.service
    fi
}

enter_unattended_mode() {
    # Persist unattended first so any NetworkManager down event caused by this
    # exit cannot recursively request another Pixhawk disconnect transition.
    disable_field_wifi_autoconnect
    set_mode unattended

    disconnect_active_field_wifi

    # Fully relinquish the dedicated field Ethernet profile. This is harmless
    # when carrier loss has already caused NetworkManager to deactivate it.
    nmcli connection down "$PIXHAWK_ETHERNET" >/dev/null 2>&1 || true

    # Re-enable ordinary NetworkManager device autoconnect. Saved maintenance
    # Wi-Fi profiles remain eligible; field/GCS profiles remain autoconnect=no.
    nmcli device set "$INTERFACE" autoconnect yes >/dev/null 2>&1 || true

    systemctl enable --now tailscaled.service
    maybe_start_health_check

    echo "[ok] unattended mode: field Wi-Fi inactive/non-autoconnecting; Tailscale enabled"
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

        # Field/GCS Wi-Fi is never a passive NetworkManager preference.
        # It is entered only through this explicit Pixhawk transition.
        disable_field_wifi_autoconnect

        pixhawk_interface="$(require_pixhawk_carrier)" || {
            echo "[error] refusing field Wi-Fi transition without a physically connected Pixhawk" >&2
            exit 1
        }

        # Only after physical Pixhawk Ethernet carrier is proven may wlan0 move
        # onto an approved field network.
        active_wifi="$(activate_field_wifi)" || {
            echo "[error] no approved field Wi-Fi profile could be activated"
            exit 1
        }

        nmcli connection modify "$PIXHAWK_ETHERNET" \
            ipv4.never-default yes ipv6.never-default yes
        nmcli connection up "$PIXHAWK_ETHERNET" ifname "$pixhawk_interface"

        verify_pixhawk_ethernet_state "$pixhawk_interface" || {
            echo "[error] refusing to persist Pixhawk mode with invalid Ethernet state" >&2
            disconnect_active_field_wifi || true
            exit 1
        }

        set_mode pixhawk

        # Close the small transition race between the pre-persist validation
        # and making pixhawk mode authoritative. A loss after this point is
        # also caught by the NetworkManager dispatcher.
        if ! verify_pixhawk_ethernet_state "$pixhawk_interface"; then
            echo "[error] Pixhawk link disappeared during field transition; returning unattended" >&2
            enter_unattended_mode || true
            exit 1
        fi

        systemctl disable --now tailscaled.service
        maybe_start_health_check
        echo "[ok] Pixhawk mode: field Wi-Fi=$active_wifi, Pixhawk Ethernet active on $pixhawk_interface, Tailscale disabled"
        ;;
    unattended)
        enter_unattended_mode
        ;;
    *)
        usage
        exit 2
        ;;
esac
