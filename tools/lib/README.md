# Live Stack Shell Library

This folder contains shell fragments sourced by `tools/start_live_stack.sh`.

These files are not standalone entrypoints. They split the live-stack launcher
into smaller areas so the main script can stay focused on orchestration.

## Modules

| File | Status | Purpose |
| --- | --- | --- |
| `live_defaults.sh` | Support library | Defines default live-stack configuration and profile/resolution helpers. |
| `live_usage.sh` | Support library | Prints basic and advanced command-line usage text. |
| `live_cli.sh` | Support library | Parses and validates `start_live_stack.sh` command-line arguments. |
| `live_camera.sh` | Support library | Handles camera preflight checks, camera process cleanup, and camera startup readiness. |
| `live_storage.sh` | Support library | Enforces the free-space gate before any live recording directory is created. |

## Execution contract

These files expect to be sourced by `tools/start_live_stack.sh`.

They rely on variables and helper functions defined by the entrypoint, including
logging functions, run-directory paths, and live-stack configuration variables.
Do not execute these files directly.

## Edit policy

Keep behavior changes small and deliberate. This library controls live hardware
startup, process cleanup, ROS launch arguments, and camera recovery paths.

Safe cleanup examples:

- comments and usage text,
- grouping related defaults,
- adding validation messages,
- removing stale options only after checking `start_live_stack.sh`.

Risky cleanup examples:

- changing camera preflight behavior,
- changing tracker/TIM defaults,
- changing process-kill patterns,
- changing ROS topic or launch arguments.
