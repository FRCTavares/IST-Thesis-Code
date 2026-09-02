# Raspberry Pi Host Tools

This directory owns host-level Raspberry Pi administration for the thesis
system. It is intentionally separate from ROS, perception, tracking, and
aircraft-control startup.

## Contents

| Path | Purpose |
| --- | --- |
| `install_unattended_host_recovery.sh` | Validates and installs the host recovery configuration. |
| `set_pi_network_mode.sh` | Switches between unattended/Tailscale and fail-closed AERONEXT/Pixhawk networking. |
| `thesis_host_health.py` | Performs bounded host-only health checks and recovery. |
| `systemd/` | Version-controlled systemd units, defaults, and drop-ins consumed by the installer. |

The layout under `systemd/` mirrors each installed configuration's role, but
these files are repository assets—not files to copy manually. The installer
validates them, creates backups, installs them with explicit permissions, and
reloads the affected services.

## Commands

From the repository root:

```bash
./tools/host/install_unattended_host_recovery.sh --dry-run
sudo ./tools/host/install_unattended_host_recovery.sh
sudo ./tools/host/set_pi_network_mode.sh status
sudo ./tools/host/set_pi_network_mode.sh pixhawk
sudo ./tools/host/set_pi_network_mode.sh unattended
```

Field/GCS Wi-Fi profiles are not passive NetworkManager preferences and must
have autoconnect disabled; the host installer persists that policy across
reboots. Entering `pixhawk` mode first requires physical Ethernet carrier on
the interface bound to `pixhawk-apm`; without carrier the transition fails
before changing Wi-Fi. After carrier is proven, the mode attempts
`ISR Aero.Next GCS`, then the explicitly configured approved AERONEXT fallback
if required. The Pixhawk Ethernet profile must remain active with physical
carrier and without a default route, and only after those gates pass is
Tailscale stopped/disabled.

While `pixhawk` mode is active, Pixhawk Ethernet loss is fail-closed. A
NetworkManager dispatcher hook requests an immediate host-only transition back
to `unattended`; the periodic host-health check independently verifies the same
carrier/profile/no-default-route contract as a slower backstop. The unattended
transition explicitly drops any active approved field Wi-Fi, relinquishes the
Pixhawk Ethernet profile, restores ordinary NetworkManager autoconnect, and
re-enables Tailscale. Unattended health recovery never uses a generic
`nmcli device connect wlan0`; it only re-enables device autoconnect, so field/GCS
profiles persisted with `connection.autoconnect=no` remain excluded. The health
monitor also never activates field Wi-Fi on its own: loss of the field-network
contract returns to `unattended` and requires a new explicit `pixhawk` command.
Ethernet appearance never enters field mode automatically;
a new explicit `pixhawk` command is always required. A Tailscale maintenance
shell is therefore expected to disconnect during a successful field transition.

## Safety contract

- Host recovery must never start ROS, MAVROS, perception, control, recording,
  arming, or any aircraft-facing service.
- Pixhawk mode must fail closed unless the Pixhawk Ethernet profile exists,
  has physical carrier, is the active connection on its bound interface, owns
  no default route, and either the primary ISR field Wi-Fi or explicitly
  configured AERONEXT fallback profile becomes active. ISR is always attempted
  first.
- Loss of the Pixhawk Ethernet contract while already in field mode must exit
  to unattended networking; carrier restoration alone must never re-enter
  field mode.
- Never commit Wi-Fi credentials, Tailscale state/auth keys, or SSH keys.
- Run `python3 -m pytest -q tools/tests/test_host_health.py` after changes.
