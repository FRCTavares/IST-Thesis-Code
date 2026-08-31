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

Entering `pixhawk` mode first attempts `ISR Aero.Next GCS`. If that profile
cannot be activated, it may use the explicitly configured approved AERONEXT
local-router fallback profile. If neither field profile works, the transition
fails closed. Successful field mode stops/disables Tailscale, so run the
transition locally because a remote Tailscale shell is expected to disconnect.

## Safety contract

- Host recovery must never start ROS, MAVROS, perception, control, recording,
  arming, or any aircraft-facing service.
- Pixhawk mode must fail closed unless the Pixhawk Ethernet profile exists
  and either the primary ISR field Wi-Fi or explicitly configured AERONEXT
  fallback profile becomes active. ISR is always attempted first.
- Never commit Wi-Fi credentials, Tailscale state/auth keys, or SSH keys.
- Run `python3 -m pytest -q tools/tests/test_host_health.py` after changes.
