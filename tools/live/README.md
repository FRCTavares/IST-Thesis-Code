# tools/live

Last reviewed: 2026-09-09

## Purpose

Small command-line helpers for live ROS 2 operation: runtime inspection while
the live stack runs, and the Issue #55 UI-integration gate. Not evaluation
tools.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `print_track_ids.py` | Inspection | Prints observed tracker IDs, scores and bbox summaries from live `/tracks`. |
| `validate_live_run_metadata.py`, `write_live_run_metadata.py` | Provenance | Write and validate live-run metadata sidecars. |
| `validate_target_authority_ground_run.py` | Check | Validates a recorded target-authority ground run. |
| `run_issue55_m6_integration.sh` | Issue #55 M6 gate | Repeatable bag-replay integration test of the external-frontend / dashboard-backend contract (HTTP/WebSocket/MJPEG, target select/clear, frozen-reconfiguration 409s). Starts no controller, MAVROS, camera, detector or Hailo. |
| `m6_integration_probe.py`, `m6_image_relay.py` | Issue #55 M6 gate | Assertions and a minimal best-effort image relay used only by the M6 gate. |

## Rules

- Inspection helpers are for confirming state before selecting or debugging a
  target; for final metrics use `tools/analysis/`.
- The M6 gate produces no scientific result. Every child runs under
  `tools/lib/run_in_owned_process_group.py`; evidence is written under
  `ros2_ws/log/issue55_m6/<timestamp>/`. Run with
  `bash tools/live/run_issue55_m6_integration.sh` (override `M6_BAG` /
  `ROS_DOMAIN_ID` if needed).
