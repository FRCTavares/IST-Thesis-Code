# Retained flight-evidence package (#50 / #74)

What one retained physical closed-loop trial must preserve so the
controller-facing thesis metrics can be reconstructed afterward without
another flight. This is evidence plumbing; it does not authorise flight and
does not change controller, TIM-MARS, detector, tracker, or evaluation
behaviour.

## Canonical location

The retained **video bag directory**
(`bags/live_camera/<RUN_ID>__video[__<tag>]/`) is the single canonical
evidence package for a trial. Everything below lives inside it.

## Contents

| Artifact | Path in the package | How it gets there | Required |
| --- | --- | --- | --- |
| rosbag (MCAP) | `*.mcap` + `metadata.yaml` | `ros2 bag record` (`--field-record --control-mavros`) | yes |
| controller diagnostics | `/control_ref/diagnostics` in the bag | `control_ref_node` (`thesis_msgs/ControlDiagnostics`, one per command) | yes (when control runs) |
| run metadata / provenance | `run_metadata.json` | `tools/live/write_live_run_metadata.py` (schema v1) | yes |
| flight metadata (plain text) | `flight_metadata.txt` | `tools/start_live_stack.sh` | yes |
| target-authority events | `target_authority_events.jsonl` | `dashboard_bridge_node` → archived on stop | yes |
| controller runtime log | `run_logs/control.log` | `tools/live/archive_run_evidence.py` on stop | yes |
| dashboard bridge log | `run_logs/dashboard_bridge.log` | same | yes |
| TIM-MARS node log | `run_logs/target_memory_mars.log` | same | yes |
| operator event log | `run_logs/operator_events.jsonl` | same (optional-file; `absent` recorded if never written) | yes for retained trials |
| archival manifest | `run_logs/archive_manifest.json` | `archive_run_evidence.py` | yes |
| recorder finalization outcome | `run_logs/recorder_finalize_outcome.txt` (`graceful`/`escalated`) | `finalize_recorders` on stop | yes |
| bag integrity report | `bag_integrity.json` | `tools/live/verify_retained_bag.py` on stop | yes |
| evidence-package status | `evidence_package_status.json` | `tools/live/verify_evidence_package.py` on stop | yes |
| paired raw-image bag | `<RUN_ID>__video__…__image_raw/` (sibling dir) | `--record-raw` | recommended |
| physical-person annotation | added post-flight (`tim_physical_target_bbox_v2`) | manual, from the retained imagery | pending post-flight |
| native Pixhawk `.bin` dataflash | `pixhawk_dataflash/*.bin` + `dataflash_manifest.json` | `tools/live/archive_pixhawk_dataflash.py --source-bin <file>` (retrieval verification pending) | pending post-flight (control field trials) |

`run_metadata.json.git.commit` is the exact Git SHA; `run_metadata.json.hashes`
carries the SHA-256 of the detector HEF, the MARS ReID model and
`tim_mars_canonical.yaml`.

## Controller provenance

`run_metadata.json` now records the **running** `control_ref_node`'s resolved
parameters (queried live via `ros2 param dump`, never mirrored from launch
arguments — which would miss every node default):

- `resolved_parameters.control_ref_node` — `rate_hz`, `img_w`, `img_h`,
  `desired_h_norm`, `stale_timeout_s`, `future_tolerance_s`, `yaw_kp`,
  `forward_kp`, `lateral_kp`, `deadband_ex`, `deadband_h`, `max_yaw_z`,
  `max_vx`, `max_vy`, `max_delta_yaw_z`, `max_delta_vx`, `max_delta_vy`,
  `use_lateral`, `invert_*`, `enable_yaw_recovery`, `recovery_yaw_rate`,
  `recovery_max_duration_s`, `recovery_max_integrated_yaw_rad`,
  `recovery_last_trusted_max_age_s`, plus every other declared parameter;
- `resolved_parameters_meta.control_ref_node.query_ok` — `true` only when the
  live query succeeded. A failed query is **not** replaced with source
  defaults; the validator (`tools/live/validate_live_run_metadata.py`) fails
  the run;
- `expected_parameters.control_ref_node.enable_yaw_recovery` is asserted
  against the launcher intent (`false` baseline / `true` candidate). A
  mismatch fails `tools/live/validate_live_run_metadata.py`. Baseline is the
  default; the candidate needs the gated `--control-yaw-recovery` opt-in.

## Operator event log

`tools/live/operator_event.py <event> --run-id "$RUN_ID" ...` appends one JSON
line per event to `ros2_ws/log/live_stack/<RUN_ID>/operator_events.jsonl`
(archived into `run_logs/` on stop). Event types: `trial_start`, `trial_end`,
`target_selected`, `operator_takeover`, `abort`, `unexpected_behavior`,
`trial_verdict`. `abort` **requires** a class and a free-text reason.
Every event carries `ts_utc` (UTC wall clock, which aligns directly with ROS
bag timestamps — the live stack uses no simulated time) and, on the Pi,
`ts_monotonic_ns`; `trial_start` also records a `clock_pair`
(`monotonic_ns` / `system_ns`) sample for cross-clock alignment.

## Controlled stop, finalization and verification

`stop_stack` runs a deliberate sequence (Issue #50/#74, `tools/lib/live_shutdown.sh`):

1. `stop_app_nodes` — application publishers/nodes are SIGINT'd first (the
   controller emits its final safe-zero + shutdown diagnostic) while the
   recorders keep running; `STOP_APP_GRACE_S` (3 s) then SIGTERM stragglers;
2. `STOP_APP_SETTLE_S` (2 s) settle so the last messages reach the recorders;
3. `finalize_recorders` — SIGINT to each recorder and allow up to
   `RECORDER_FINALIZE_GRACE_S` (10 s, env-overridable) for process exit after
   flushing/finalizing; escalate to SIGTERM then SIGKILL only if still alive.
   Final cleanup is restricted to recorder processes/descendants tracked for
   this run, never host-wide process matching; writes
   `run_logs/recorder_finalize_outcome.txt`;
4. archive `run_logs/` + `target_authority_events.jsonl`;
5. `verify_retained_bag.py` → `bag_integrity.json` (finalized `metadata.yaml`
   only — never reopens the bag while the recorder holds it);
6. `verify_evidence_package.py` → `evidence_package_status.json`, printing
   **`EVIDENCE PACKAGE INCOMPLETE`** if any required artifact is missing,
   a required topic is empty, provenance is invalid, the archive manifest is
   incomplete, or recorder finalization escalated.

Process/flight safety always runs (safe-zero, controlled shutdown, cleanup);
evidence failure is reported and persisted, never turned into unsafe process
behaviour. A failed bag is **kept**, not deleted.

`evidence_package_status.json.status` is one of `complete_runtime_evidence`,
`incomplete_runtime_evidence`, `pending_postflight_annotation`,
`pending_pixhawk_dataflash`. The Pi-side runtime files alone never make a
package scientifically final.

## Native Pixhawk DataFlash

`tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir <bag>
--source-bin <file.bin>` copies an **explicitly supplied** `.bin` into
`<bag>/pixhawk_dataflash/`, SHA-256s both sides, refuses to overwrite, and
writes `dataflash_manifest.json` with `hardware_verification: pending`. It
never talks to an FCU and never "selects the latest log" — the operator
retrieves the file with the real field tooling and identifies the exact trial
file. **Real-hardware retrieval verification is pending** (no Pixhawk available).

## MAVROS setpoint / statustext evidence

The retained video bag adds `/mavros/setpoint_raw/target_local` (the FCU's
echo of the setpoint it is acting on — compare against `/control_ref/cmd_vel`)
and `/mavros/statustext/recv` (FCU prearm / EKF / failsafe / mode-change
messages needed to interpret a trial). Both are standard ArduPilot MAVROS
plugins not on the `apm` denylist; either may legitimately carry zero
messages, so the bag verifier requires them **present, not non-zero**.

## Interpretation cautions

- TIM `LOCKED` is **not** physical ground truth. Whether the followed geometry
  is the correct physical person requires the post-flight physical-v2
  annotation.
- A zero command is not proof of a stationary hover, and command publication
  is not proof of Pixhawk execution — cross-check `/mavros/local_position/*`,
  `/mavros/setpoint_raw/target_local` and the native `.bin`.
- The baseline keeps bounded yaw recovery **OFF**; the candidate is the gated
  `--control-yaw-recovery` opt-in. Only the perception-state -> motion-authority
  mapping changes, not TIM-MARS identity or the normal-following control law.

## Controller diagnostics

`control_ref_node` publishes one `thesis_msgs/ControlDiagnostics` message on
`/control_ref/diagnostics` for every command on `/control_ref/cmd_vel` (shared
`header.stamp`, join 1:1). It makes bag-native the mode, decision reason,
recovery enabled/active state, recovery direction / elapsed / integrated yaw /
configured budget / configured max duration, last-trusted observation age and
validity, `status_fresh` / `target_fresh`, and the final `(vx, vy, yaw_z)`.
`control.log` is retained unchanged and still carries the same information as
text. Quick integrity check:
`python3 tools/analysis/summarize_control_diagnostics.py <bag>`.

**Trial condition.** Bounded yaw recovery defaults OFF (**baseline**:
perception `LOST` -> hover). It is enabled only by the deliberately gated
`--field-record --control-mavros --control-yaw-recovery
--acknowledge-yaw-recovery-candidate` (**candidate**: `LOST` + eligible
trusted history -> bounded yaw-only recovery, translation still prohibited).
`run_metadata.json` `resolved_parameters.control_ref_node.enable_yaw_recovery`
is asserted against the launcher intent (`--expect-param`), so a mismatched
trial fails `validate_live_run_metadata.py`; `flight_metadata.txt` records
`trial_condition` and `control_yaw_recovery_enabled`. Match it with the
operator `trial_start` event (`--condition candidate --recovery-enabled` or
`--condition baseline`). The candidate changes only the perception-state ->
motion-authority mapping, not TIM-MARS identity or the normal-following law.

## Still separate / pending

- **real-hardware** Pixhawk DataFlash retrieval verification (no Pixhawk yet);
- the final #50/#74 scientific metrics analyser;
- the physical-v2 flight-annotation tooling.
