# tools/lib

Last reviewed: 2026-09-09

## Purpose

Shared implementation used by the launcher and experiment tools, kept out of
the entrypoints so those stay focused on orchestration.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `live_defaults.sh` | Sourced fragment | Default live-stack configuration and profile/resolution helpers. |
| `live_usage.sh` | Sourced fragment | Basic and advanced usage text. |
| `live_cli.sh` | Sourced fragment | Parses and validates `start_live_stack.sh` arguments. |
| `live_camera.sh` | Sourced fragment | Camera preflight, cleanup and startup readiness. |
| `live_storage.sh` | Sourced fragment | Free-space gate before any recording directory is created. |
| `run_in_owned_process_group.py` | Shared supervisor | Runs a child in its own process group so a run's shutdown only tears down processes that run started; used by the live stack and several experiment/live runners. |

## Rules

- The `*.sh` fragments are sourced by `tools/start_live_stack.sh` and rely on
  its variables and functions — do not execute them directly, and they are not
  marked executable.
- `live_defaults.sh` is pinned by the prospective-freeze manifest; do not move
  or rename it before H01–H03.
- Behaviour changes here affect live hardware startup, process cleanup and ROS
  launch arguments — keep them small and deliberate.
