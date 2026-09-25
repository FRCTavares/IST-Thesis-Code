# tools/live

Last reviewed: 2026-09-14

## Purpose

Small command-line helpers for live ROS 2 operation: runtime inspection while
the live stack runs, retained-flight evidence plumbing, and the Issue #55
UI-integration gate. Not evaluation tools.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `print_track_ids.py` | Inspection | Prints observed tracker IDs, scores and bbox summaries from live `/tracks`. |
| `validate_live_run_metadata.py`, `write_live_run_metadata.py` | Provenance | Write and validate live-run metadata sidecars, including the live query of `control_ref_node`'s resolved parameters. |
| `archive_run_evidence.py` | Evidence retention | Copies the run's `control.log`, `dashboard_bridge.log`, `target_memory_mars.log` and operator event log into `<bag>/run_logs/` keyed by the exact `RUN_ID`; writes `archive_manifest.json`; refuses to overwrite existing retained evidence. Called by `tools/start_live_stack.sh` at stop. |
| `verify_retained_bag.py` | Bag integrity | Deterministic check of a finalized rosbag2 bag from its `metadata.yaml` (dir/metadata/storage-file/format/required-topics/non-zero-counts); writes `bag_integrity.json` beside the bag; never opens the bag while the recorder holds it, never deletes it. |
| `verify_evidence_package.py` | Package completeness | Checks the full retained #50/#74 package after stop; writes `evidence_package_status.json` with `complete_runtime_evidence` / `incomplete_runtime_evidence` / `pending_postflight_annotation` / `pending_pixhawk_dataflash`; runs the bag verifier + provenance validator; never fabricates post-flight artifacts. |
| `summarize_field_evidence.py` | Field acceptance | Prints structured topic rates, transport loss and visual/runtime status; exits nonzero unless the finalized structured-plus-visual runtime package is acceptable. |
| `archive_pixhawk_dataflash.py` | DataFlash retention | Associates an explicitly-supplied ArduPilot `.bin` with a retained trial (SHA-256 both sides, refuse overwrite, preserve source, `dataflash_manifest.json`). Never talks to an FCU, never picks "latest". |
| `operator_event.py` | Operator events | Append-only JSONL recorder for physical-trial operator events, including the final B-C-B O1/O2/O3 opportunity boundaries. `verify_evidence_package.py --expect-bcb-opportunities TAG` applies the strict final-comparison run/trial/lifecycle contract: accepted runs require the complete O1/O2/O3 sequence, while rejected safety-abort runs may retain a coherent prefix terminated by explicit abort/end/rejected-verdict events. `completed` records that the prescribed opportunity ended; correct-person reacquisition and timing are derived from retained ROS/video evidence. |
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
