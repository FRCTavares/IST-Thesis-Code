#!/usr/bin/env bash
# Read-only macOS GCS connectivity check and direct Pi repository shell.

set +u
set -o pipefail

EXPECTED_SSID="ISR Aero.Next GCS"
EXPECTED_SUBNET_PREFIX="192.168.8."
PI_ADDRESS="192.168.8.174"
PI_USER="francisco"
PI_HOSTNAME="fcstpi"
REMOTE_REPOSITORY="/home/francisco/Desktop/Thesis-Code"
CHECK_ONLY=0
FAILURES=0
WIFI_INTERFACE=""

pass() {
    printf 'PASS  %s\n' "$1"
}

fail() {
    FAILURES=$((FAILURES + 1))
    printf 'FAIL  %s\n' "$1"
    if [[ -n "${2:-}" ]]; then
        printf '      fix: %s\n' "$2"
    fi
}

info() {
    printf 'INFO  %s\n' "$1"
}

usage() {
    cat <<'EOF_USAGE'
Usage: thesis-field-connect [--check|--help]

Checks the Mac-to-GCS-to-Pi link. With no option, opens a Pi repository shell
after every mandatory check passes; --check only reports status.
EOF_USAGE
}

discover_wifi_interface() {
    local hardware
    hardware="$(networksetup -listallhardwareports 2>/dev/null || true)"
    WIFI_INTERFACE="$(
        printf '%s\n' "$hardware" | awk '
            /^Hardware Port: (Wi-Fi|AirPort)$/ {
                if (getline > 0 && $1 == "Device:") {
                    print $2
                    exit
                }
            }
        '
    )"
    if [[ -n "$WIFI_INTERFACE" ]]; then
        pass "Wi-Fi interface: $WIFI_INTERFACE"
    else
        fail "Wi-Fi interface not discovered" \
            "open System Settings > Network and confirm Wi-Fi is available"
    fi
}

check_ssid() {
    local output ssid
    if [[ -z "$WIFI_INTERFACE" ]]; then
        info "Wi-Fi SSID unavailable because no Wi-Fi interface was discovered"
        return
    fi

    output="$(networksetup -getairportnetwork "$WIFI_INTERFACE" 2>&1 || true)"
    ssid="${output#Current Wi-Fi Network: }"
    if [[ "$output" == Current\ Wi-Fi\ Network:* && -n "$ssid" ]]; then
        if [[ "$ssid" == "$EXPECTED_SSID" ]]; then
            pass "Wi-Fi SSID: $ssid"
        else
            fail "Wi-Fi SSID: $ssid" \
                "connect the Mac to $EXPECTED_SSID"
        fi
    else
        info "Wi-Fi SSID not reliably exposed by this macOS version"
    fi
}

check_local_address() {
    local address last_octet
    if [[ -z "$WIFI_INTERFACE" ]]; then
        fail "Mac GCS IPv4 address not checked" \
            "connect the Mac to $EXPECTED_SSID"
        return
    fi

    address="$(ipconfig getifaddr "$WIFI_INTERFACE" 2>/dev/null || true)"
    last_octet="${address##*.}"
    if [[ "$address" == "$EXPECTED_SUBNET_PREFIX"* ]] \
        && [[ "$last_octet" =~ ^[0-9]+$ ]] \
        && (( last_octet >= 1 && last_octet <= 254 )); then
        pass "Mac GCS address: $address/24 on $WIFI_INTERFACE"
    else
        fail "no 192.168.8.x address on ${WIFI_INTERFACE:-Wi-Fi}" \
            "connect the Mac to $EXPECTED_SSID"
    fi
}

check_route() {
    local output route_interface route_flags
    output="$(route -n get "$PI_ADDRESS" 2>&1 || true)"
    route_interface="$(printf '%s\n' "$output" | awk '$1 == "interface:" {print $2; exit}')"
    route_flags="$(printf '%s\n' "$output" | awk '$1 == "flags:" {print $2; exit}')"
    if [[ -n "$WIFI_INTERFACE" && "$route_interface" == "$WIFI_INTERFACE" ]] \
        && [[ "$route_flags" != *GATEWAY* ]] \
        && ! printf '%s\n' "$output" | grep -Eq '(^|[^0-9])100\.[0-9]+\.[0-9]+\.[0-9]+([^0-9]|$)'; then
        pass "direct route to $PI_ADDRESS uses $WIFI_INTERFACE"
    else
        fail "route to $PI_ADDRESS is not direct on ${WIFI_INTERFACE:-Wi-Fi}" \
            "connect to $EXPECTED_SSID and inspect: route -n get $PI_ADDRESS"
    fi
}

check_reachability() {
    if ping -c 1 -W 1000 "$PI_ADDRESS" >/dev/null 2>&1; then
        pass "Pi responds: $PI_ADDRESS"
    else
        fail "$PI_ADDRESS unreachable" \
            "verify the Pi is associated with the GCS"
    fi
}

check_ssh_identity() {
    local output rc
    output="$(
        ssh -o BatchMode=yes -o ConnectTimeout=5 -o ConnectionAttempts=1 \
            "$PI_USER@$PI_ADDRESS" \
            'printf "hostname=%s\n" "$(hostname)"; printf "user=%s\n" "$(whoami)"; if [ -d /home/francisco/Desktop/Thesis-Code ]; then echo "repository=present"; else echo "repository=missing"; fi' \
            2>&1
    )"
    rc=$?

    if [[ "$rc" -ne 0 ]]; then
        if grep -Fqi 'Permission denied' <<< "$output"; then
            fail "passwordless SSH authentication failed" \
                "check the existing SSH key for $PI_USER@$PI_ADDRESS"
        elif grep -Eqi 'host key verification failed|authenticity of host' <<< "$output"; then
            fail "SSH host-key verification failed" \
                "verify the Pi host key with a direct ssh $PI_USER@$PI_ADDRESS connection"
        else
            fail "passwordless SSH connection failed" \
                "verify GCS association, then run ssh -o BatchMode=yes $PI_USER@$PI_ADDRESS"
        fi
        fail "remote identity not verified" "restore the SSH connection first"
        fail "remote repository not verified" "restore the SSH connection first"
        return
    fi

    pass "passwordless SSH: $PI_USER@$PI_ADDRESS"
    if grep -Fxq "hostname=$PI_HOSTNAME" <<< "$output" \
        && grep -Fxq "user=$PI_USER" <<< "$output"; then
        pass "remote identity: $PI_USER@$PI_HOSTNAME"
    else
        fail "unexpected remote identity" \
            "expected hostname=$PI_HOSTNAME and user=$PI_USER"
    fi

    if grep -Fxq 'repository=present' <<< "$output"; then
        pass "remote repository: $REMOTE_REPOSITORY"
    else
        fail "remote repository missing: $REMOTE_REPOSITORY" \
            "inspect the Pi filesystem after verifying its identity"
    fi
}

run_checks() {
    discover_wifi_interface
    check_ssid
    check_local_address
    check_route
    check_reachability
    check_ssh_identity
}

open_remote_shell() {
    printf '\nNext on Pi:\n'
    printf 'tools/flight/field_preflight_check.sh\n\n'
    printf 'Once GCS + Pixhawk field mode is physically ready:\n'
    printf 'tools/flight/field_preflight_check.sh --passive-live-gate\n\n'

    exec ssh -t -o BatchMode=yes -o ConnectTimeout=5 \
        "$PI_USER@$PI_ADDRESS" \
        'cd /home/francisco/Desktop/Thesis-Code || exit 1; export GIT_PAGER=cat; export PAGER=cat; export GH_PAGER=cat; set +u; exec "${SHELL:-/bin/bash}" -i'
}

main() {
    if [[ $# -gt 1 ]]; then
        usage
        return 2
    fi
    case "${1:-}" in
        "") ;;
        --check) CHECK_ONLY=1 ;;
        -h|--help) usage; return 0 ;;
        *) usage; return 2 ;;
    esac

    printf 'Mac/GCS field connectivity (read-only)\n\n'
    run_checks
    if [[ "$FAILURES" -ne 0 ]]; then
        printf '\nMAC/GCS LINK: NOT READY\n'
        return 1
    fi

    printf '\nMAC/GCS LINK: READY\n'
    if [[ "$CHECK_ONLY" -eq 1 ]]; then
        return 0
    fi
    open_remote_shell
}

main "$@"
