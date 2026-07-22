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

Entering `pixhawk` mode intentionally changes Wi-Fi to `ISR Aero.Next GCS` and
stops/disables Tailscale. Run that transition locally because a remote
Tailscale shell is expected to disconnect.

## Safety contract

- Host recovery must never start ROS, MAVROS, perception, control, recording,
  arming, or any aircraft-facing service.
- Pixhawk mode must fail closed unless the required AERONEXT and Ethernet
  NetworkManager profiles exist and AERONEXT becomes active.
- Never commit Wi-Fi credentials, Tailscale state/auth keys, or SSH keys.
- Run `python3 -m pytest -q tools/tests/test_host_health.py` after changes.
