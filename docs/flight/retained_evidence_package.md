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
| run metadata / provenance | `run_metadata.json` | `tools/live/write_live_run_metadata.py` (schema v1) | yes |
| flight metadata (plain text) | `flight_metadata.txt` | `tools/start_live_stack.sh` | yes |
| target-authority events | `target_authority_events.jsonl` | `dashboard_bridge_node` → archived on stop | yes |
| controller runtime log | `run_logs/control.log` | `tools/live/archive_run_evidence.py` on stop | yes |
| dashboard bridge log | `run_logs/dashboard_bridge.log` | same | yes |
| TIM-MARS node log | `run_logs/target_memory_mars.log` | same | yes |
| operator event log | `run_logs/operator_events.jsonl` | same (optional-file; `absent` recorded if never written) | yes for retained trials |
| archival manifest | `run_logs/archive_manifest.json` | `archive_run_evidence.py` | yes |
| paired raw-image bag | `<RUN_ID>__video__…__image_raw/` (sibling dir) | `--record-raw` | recommended |
| physical-person annotation | added post-flight (`tim_physical_target_bbox_v2`) | manual, from the retained imagery | yes (post-flight) |
| native Pixhawk `.bin` dataflash | added manually beside the package | **manual**, not yet automated | yes for the candidate trial |

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
- `expected_parameters.control_ref_node.enable_yaw_recovery` is asserted to be
  `false` for the current baseline. `docs/control/p074_state_aware_control_contract.md`
  and the live launcher keep bounded yaw recovery **OFF**; this task does not
  add a way to turn it on.

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

## Interpretation cautions

- TIM `LOCKED` is **not** physical ground truth. Whether the followed geometry
  is the correct physical person requires the post-flight physical-v2
  annotation.
- A zero command is not proof of a stationary hover, and command publication
  is not proof of Pixhawk execution — cross-check `/mavros/local_position/*`
  and the native `.bin`.
- The current baseline keeps bounded yaw recovery **OFF**. A candidate trial
  that turns it on is a future, separately-gated change.

## Still manual / separate (not in this task)

- native Pixhawk `.bin` dataflash retrieval;
- a `/control_ref/diagnostics` topic for mode / recovery state;
- adding `/mavros/setpoint_raw/target_local` and `/mavros/statustext` to the
  recorded topic set;
- recorder shutdown-order / grace-period changes;
- the final #50/#74 metrics analyser and the physical-v2 flight-annotation
  tooling.
