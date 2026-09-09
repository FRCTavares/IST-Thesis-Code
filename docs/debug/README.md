# Debug and recovery

Last reviewed: 2026-09-09

## Purpose

Current recovery procedures for hardware and host failures that can prevent the
canonical thesis runtime from starting or operating correctly.

## Contents

| Path | Role |
| --- | --- |
| `HAILO_RECOVERY.md` | Hailo device, driver, DKMS, and runtime recovery. |
| `LIVE_STACK_CAMERA_RECOVERY.md` | TEVS/camera/live-stack recovery. |
| `UNATTENDED_PI_OPERATION.md` | Safe unattended Raspberry Pi operation and recovery. |

## Rules

- These are current operational runbooks, not experiment-result authority.
- Prefer narrow diagnosis and targeted recovery over broad process/device resets.
- Historical recovery procedures belong under `docs/archive/`.
