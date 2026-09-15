# tools/host

Last reviewed: 2026-09-09

## Purpose

Host-level Raspberry Pi administration for the thesis system: unattended
recovery, field/Tailscale network switching, and bounded host health checks.
Deliberately separate from ROS, perception, tracking and aircraft control.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `install_unattended_host_recovery.sh` | Installer | Validates and installs the host-recovery configuration with backups and explicit permissions. |
| `set_pi_network_mode.sh` | Network switch | Switches between unattended/Tailscale and fail-closed field/Pixhawk networking. |
| `thesis_host_health.py` | Health check | Bounded host-only reachability checks and recovery. |
| `systemd/` | Assets | Version-controlled units, defaults and drop-ins consumed by the installer — repository assets, not files to copy manually. |

## Rules

- Host recovery must never start ROS, MAVROS, perception, control, recording,
  arming or any aircraft-facing service.
- `set_pi_network_mode.sh pixhawk` fails closed unless Pixhawk Ethernet
  and an approved field Wi-Fi profile are available. Field mode stops Tailscale;
  invoke it from the Pi console or GCS-local SSH to `192.168.8.174`.
  Reconnect to the same address if the Wi-Fi profile switch drops the shell.
- Never commit Wi-Fi credentials, Tailscale state/auth keys or SSH keys.
- Run `python3 -m pytest -q tools/tests/test_host_health.py` after changes.

## See also

- `docs/debug/UNATTENDED_PI_OPERATION.md` — operating procedure and commands
