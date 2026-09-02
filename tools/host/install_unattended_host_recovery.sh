#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THESIS_ROOT="${THESIS_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SYSTEMD_ASSET_ROOT="$SCRIPT_DIR/systemd"
NETWORKMANAGER_ASSET_ROOT="$SCRIPT_DIR/networkmanager"
INTERFACE="wlan0"
DRY_RUN=0
CONFIGURE_FIREWALL=1

usage() {
    cat <<'EOF'
Usage: sudo ./tools/host/install_unattended_host_recovery.sh [options]

Install the host-only SSH, Tailscale, watchdog, journal, and health-check
configuration used for unattended Raspberry Pi operation.

Options:
  --interface NAME  NetworkManager interface to recover (default: wlan0)
  --no-firewall     Do not configure the Tailscale-only UFW policy
  --dry-run         Validate and print intended changes without installing
  -h, --help        Show this help

This installer never enables or starts ROS, MAVROS, the live thesis stack, or
any aircraft-affecting service.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --interface)
            [[ $# -ge 2 ]] || { echo "[error] --interface needs a value"; exit 2; }
            INTERFACE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --no-firewall)
            CONFIGURE_FIREWALL=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[error] unknown option: $1"
            usage
            exit 2
            ;;
    esac
done

if [[ ! "$INTERFACE" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo "[error] invalid interface name: $INTERFACE"
    exit 2
fi

required_files=(
    "$THESIS_ROOT/tools/host/thesis_host_health.py"
    "$THESIS_ROOT/tools/host/set_pi_network_mode.sh"
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.service"
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.timer"
    "$SYSTEMD_ASSET_ROOT/thesis-pixhawk-disconnect.service"
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.default"
    "$NETWORKMANAGER_ASSET_ROOT/dispatcher.d/90-thesis-pixhawk-disconnect"
    "$SYSTEMD_ASSET_ROOT/tailscaled.service.d/10-thesis-recovery.conf"
    "$SYSTEMD_ASSET_ROOT/ssh.service.d/10-thesis-recovery.conf"
    "$SYSTEMD_ASSET_ROOT/system.conf.d/10-thesis-watchdog.conf"
    "$SYSTEMD_ASSET_ROOT/journald.conf.d/10-thesis-retention.conf"
)

for file in "${required_files[@]}"; do
    [[ -f "$file" ]] || { echo "[error] missing deployment file: $file"; exit 1; }
done

if [[ "$CONFIGURE_FIREWALL" -eq 1 ]] && ! command -v ufw >/dev/null; then
    echo "[error] ufw is required unless --no-firewall is used"
    exit 1
fi

if ! command -v nmcli >/dev/null; then
    echo "[error] nmcli is required to enforce field Wi-Fi policy"
    exit 1
fi

if ! command -v flock >/dev/null; then
    echo "[error] flock is required to serialize field-network transitions"
    exit 1
fi

disable_field_wifi_autoconnect() {
    local candidate=""

    for candidate in \
        "${THESIS_HOST_PIXHAWK_WIFI_CONNECTION:-}" \
        "${THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION:-}"
    do
        [ -n "$candidate" ] || continue

        if nmcli -t -f NAME connection show | grep -Fxq -- "$candidate"; then
            nmcli connection modify "$candidate" connection.autoconnect no
            echo "[ok] field Wi-Fi autoconnect disabled: $candidate"
        else
            echo "[warn] configured field Wi-Fi profile is not installed: $candidate" >&2
        fi
    done
}

python3 -m py_compile "$THESIS_ROOT/tools/host/thesis_host_health.py"
systemd-analyze verify \
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.service" \
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.timer" \
    "$SYSTEMD_ASSET_ROOT/thesis-pixhawk-disconnect.service"

destinations=(
    "/usr/local/libexec/thesis_host_health.py"
    "/usr/local/sbin/thesis-network-mode"
    "/etc/systemd/system/thesis-host-health.service"
    "/etc/systemd/system/thesis-host-health.timer"
    "/etc/systemd/system/thesis-pixhawk-disconnect.service"
    "/etc/NetworkManager/dispatcher.d/90-thesis-pixhawk-disconnect"
    "/etc/default/thesis-host-health"
    "/etc/systemd/system/tailscaled.service.d/10-thesis-recovery.conf"
    "/etc/systemd/system/ssh.service.d/10-thesis-recovery.conf"
    "/etc/systemd/system.conf.d/10-thesis-watchdog.conf"
    "/etc/systemd/journald.conf.d/10-thesis-retention.conf"
)

backup_only=(
    "/etc/default/ufw"
    "/etc/ufw/user.rules"
    "/etc/ufw/user6.rules"
)

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] validated host recovery deployment"
    echo "[dry-run] interface=$INTERFACE"
    printf '[dry-run] install %s\n' "${destinations[@]}"
    printf '[dry-run] back up before firewall changes %s\n' "${backup_only[@]}"
    echo "[dry-run] enable NetworkManager.service tailscaled.service ssh.socket thesis-host-health.timer"
    echo "[dry-run] enforce configured field Wi-Fi profiles with connection.autoconnect=no"
    echo "[dry-run] install Pixhawk-link dispatcher fail-closed exit hook and service"
    if [[ "$CONFIGURE_FIREWALL" -eq 1 ]]; then
        echo "[dry-run] enable UFW: deny inbound, allow tailscale0, allow UDP 41641 on $INTERFACE, allow Pixhawk UDP 14550 on eth0"
    fi
    echo "[dry-run] no ROS, MAVROS, perception, control, or flight service is enabled"
    exit 0
fi

if [[ "$EUID" -ne 0 ]]; then
    echo "[error] installation requires root; rerun with sudo"
    exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="/var/backups/thesis-host-recovery/$timestamp"
mkdir -p "$backup_root"

backup_if_present() {
    local destination="$1"
    if [[ -e "$destination" ]]; then
        local backup="$backup_root${destination}"
        mkdir -p "$(dirname "$backup")"
        cp -a "$destination" "$backup"
    fi
}

for destination in "${destinations[@]}"; do
    backup_if_present "$destination"
done
for destination in "${backup_only[@]}"; do
    backup_if_present "$destination"
done

install -D -m 0755 \
    "$THESIS_ROOT/tools/host/thesis_host_health.py" \
    /usr/local/libexec/thesis_host_health.py
install -D -m 0755 \
    "$THESIS_ROOT/tools/host/set_pi_network_mode.sh" \
    /usr/local/sbin/thesis-network-mode
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.service" \
    /etc/systemd/system/thesis-host-health.service
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.timer" \
    /etc/systemd/system/thesis-host-health.timer
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/thesis-pixhawk-disconnect.service" \
    /etc/systemd/system/thesis-pixhawk-disconnect.service
install -D -m 0755 \
    "$NETWORKMANAGER_ASSET_ROOT/dispatcher.d/90-thesis-pixhawk-disconnect" \
    /etc/NetworkManager/dispatcher.d/90-thesis-pixhawk-disconnect
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/thesis-host-health.default" \
    /etc/default/thesis-host-health
sed -i "s/^THESIS_HOST_INTERFACE=.*/THESIS_HOST_INTERFACE=$INTERFACE/" \
    /etc/default/thesis-host-health

set -a
# shellcheck disable=SC1091
source /etc/default/thesis-host-health
set +a

# Persist the core gating invariant in NetworkManager itself. Field/GCS Wi-Fi
# may only be activated explicitly after Pixhawk carrier is proven.
disable_field_wifi_autoconnect

install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/tailscaled.service.d/10-thesis-recovery.conf" \
    /etc/systemd/system/tailscaled.service.d/10-thesis-recovery.conf
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/ssh.service.d/10-thesis-recovery.conf" \
    /etc/systemd/system/ssh.service.d/10-thesis-recovery.conf
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/system.conf.d/10-thesis-watchdog.conf" \
    /etc/systemd/system.conf.d/10-thesis-watchdog.conf
install -D -m 0644 \
    "$SYSTEMD_ASSET_ROOT/journald.conf.d/10-thesis-retention.conf" \
    /etc/systemd/journald.conf.d/10-thesis-retention.conf
install -d -m 0700 /var/lib/thesis-host-health

systemctl daemon-reload
systemctl enable NetworkManager.service tailscaled.service ssh.socket
systemctl enable --now thesis-host-health.timer
systemctl restart systemd-journald.service
systemctl start thesis-host-health.service

if [[ "$CONFIGURE_FIREWALL" -eq 1 ]]; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow in on tailscale0 comment 'Tailnet only services'
    ufw allow in on "$INTERFACE" proto udp to any port 41641 \
        comment 'Tailscale direct transport'
    ufw allow in on eth0 proto udp to any port 14550 \
        comment 'Pixhawk MAVLink Ethernet'
    ufw --force enable
fi

echo "[ok] installed host-only recovery configuration"
echo "[ok] backup: $backup_root"
echo "[ok] watchdog configuration takes effect after the next controlled reboot"
echo "[ok] no thesis runtime, MAVROS, control, or aircraft service was enabled"
systemctl --no-pager --full status thesis-host-health.timer | sed -n '1,18p'
