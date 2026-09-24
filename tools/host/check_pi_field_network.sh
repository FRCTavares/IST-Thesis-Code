#!/usr/bin/env bash
set +u
set -o pipefail

CONFIG_FILE="${THESIS_HOST_CONFIG_FILE:-/etc/default/thesis-host-health}"
EXPECTED_GCS_CIDR="${FIELD_PREFLIGHT_GCS_CIDR:-192.168.8.174/24}"
EXPECTED_PIXHAWK_PI_CIDR="${FIELD_PREFLIGHT_PIXHAWK_PI_CIDR:-192.168.144.183/24}"
PIXHAWK_ADDRESS="${FIELD_PREFLIGHT_PIXHAWK_ADDRESS:-192.168.144.14}"

fail() {
    echo "[error] $*" >&2
    exit 1
}

[[ -r "$CONFIG_FILE" ]] || fail "missing readable field-network config: $CONFIG_FILE"

set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
set +a

WIFI_INTERFACE="${THESIS_HOST_INTERFACE:-wlan0}"
ETHERNET_INTERFACE="${THESIS_HOST_PIXHAWK_ETHERNET_INTERFACE:-eth0}"
PRIMARY="${THESIS_HOST_PIXHAWK_WIFI_CONNECTION:-ISR Aero.Next GCS}"
FALLBACK="${THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION:-}"
ETH_PROFILE="${THESIS_HOST_PIXHAWK_ETHERNET_CONNECTION:-pixhawk-apm}"

[[ "${THESIS_HOST_MODE:-unattended}" == "pixhawk" ]] \
    || fail "configured host mode is not pixhawk"

ACTIVE_WIFI="$(nmcli -g GENERAL.CONNECTION device show "$WIFI_INTERFACE" 2>/dev/null || true)"
if [[ "$ACTIVE_WIFI" != "$PRIMARY" ]] \
    && { [[ -z "$FALLBACK" ]] || [[ "$ACTIVE_WIFI" != "$FALLBACK" ]]; }; then
    fail "approved field Wi-Fi is not active: ${ACTIVE_WIFI:-none}"
fi

grep -Fq "inet $EXPECTED_GCS_CIDR" \
    < <(ip -4 -o addr show dev "$WIFI_INTERFACE" 2>/dev/null) \
    || fail "expected GCS address missing: $EXPECTED_GCS_CIDR"

[[ "$(cat "/sys/class/net/$ETHERNET_INTERFACE/carrier" 2>/dev/null || true)" == "1" ]] \
    || fail "Pixhawk Ethernet carrier absent"

ACTIVE_ETH="$(nmcli -g GENERAL.CONNECTION device show "$ETHERNET_INTERFACE" 2>/dev/null || true)"
[[ "$ACTIVE_ETH" == "$ETH_PROFILE" ]] \
    || fail "Pixhawk Ethernet profile is not active"

ETH_STATE="$(
    nmcli -g ipv4.method,ipv4.addresses,ipv4.never-default,ipv6.never-default,connection.interface-name \
        connection show "$ETH_PROFILE" 2>/dev/null || true
)"

grep -Fxq 'manual' <<< "$ETH_STATE" \
    || fail "Pixhawk Ethernet is not static/manual"
grep -Fxq "$EXPECTED_PIXHAWK_PI_CIDR" <<< "$ETH_STATE" \
    || fail "Pixhawk Ethernet profile address mismatch"
[[ "$(grep -Fxc 'yes' <<< "$ETH_STATE")" -ge 2 ]] \
    || fail "Pixhawk Ethernet is not never-default"
grep -Fxq "$ETHERNET_INTERFACE" <<< "$ETH_STATE" \
    || fail "Pixhawk Ethernet profile interface mismatch"

grep -Fq "inet $EXPECTED_PIXHAWK_PI_CIDR" \
    < <(ip -4 -o addr show dev "$ETHERNET_INTERFACE" 2>/dev/null) \
    || fail "expected Pixhawk-side Pi address missing: $EXPECTED_PIXHAWK_PI_CIDR"

[[ -z "$(ip route show default dev "$ETHERNET_INTERFACE" 2>/dev/null)" ]] \
    || fail "Pixhawk Ethernet owns a default route"

ip route show default 2>/dev/null \
    | grep -Eq " dev ${WIFI_INTERFACE}([[:space:]]|$)" \
    || fail "field Wi-Fi does not own the default route"

[[ "$(systemctl is-active tailscaled.service 2>/dev/null || true)" == "inactive" ]] \
    || fail "Tailscale is not inactive"

ip route get "$PIXHAWK_ADDRESS" 2>/dev/null \
    | grep -Eq " dev ${ETHERNET_INTERFACE}([[:space:]]|$)" \
    || fail "Pixhawk route is not via $ETHERNET_INTERFACE"

ping -c 1 -W 1 "$PIXHAWK_ADDRESS" >/dev/null 2>&1 \
    || fail "Pixhawk is unreachable: $PIXHAWK_ADDRESS"

echo "[ok] existing Pixhawk field-network contract is valid"
