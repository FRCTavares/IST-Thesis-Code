# Issue #50 — Aircraft Validation Preparation Record

## Status

This is the detailed Issue #50 preparation record, not the day-of-flight
operator sheet. Current flight-day authority is `docs/flight/README.md`.

**NOT YET EXECUTABLE AS A RETAINED FLIGHT PROCEDURE.**

Issue #50 owns the current closed-loop aircraft validation. The archived P023
documents are historical and must not be used as current launch instructions.

Before a final #50 flight command is frozen, the following still require
current-system verification:

1. provision and validate the approved AERONEXT fallback Wi-Fi profile;
2. verify `ISR Aero.Next GCS` remains first-priority field Wi-Fi;
3. verify `pixhawk-apm` on Ethernet has no default route;
4. verify Tailscale is disabled/inactive in field mode;
5. connect the real Pixhawk and verify MAVROS telemetry;
6. audit the current #74 state-aware controller and its default-OFF recovery
   behaviour;
7. freeze the exact target-selection, control-authority and abort procedure;
8. define the exact retained bag/topic set.

Existing launcher capabilities such as `--field-record`, `--record-mavros` and
`--record-raw` are not, by themselves, an approved #50 flight command.

### 9 September software-control audit

The aircraft-facing MAVROS contract was audited against the installed ROS 2
Jazzy MAVROS configuration before retained flight use. The installed ArduPilot
`setpoint_velocity` plugin defaults to `LOCAL_NED`, while the thesis controller
produces forward/lateral commands relative to the aircraft body. The managed
live path therefore sets and reads back
`/mavros/setpoint_velocity mav_frame=BODY_NED` before controller mirroring can
start.

The same hardening change makes `--field-record` use the existing managed
MAVROS startup rather than a second late MAVROS instance, rejects a
pre-existing MAVROS process so the retained run owns its FCU connection,
requires successful field-network entry, FCU connection, stream-rate setup and
raw-IMU evidence, and records the actual stamped controller-facing MAVROS topic
`/mavros/setpoint_velocity/cmd_vel`. `--control-mavros` remains explicit,
is accepted only together with `--field-record`, and does not arm the aircraft
or change flight mode. `--record-mavros` alone remains telemetry-only. Bounded
yaw recovery remains forced OFF by the live launcher.

The software command contract is therefore substantially narrower, but the
retained aircraft command remains blocked until the real Pixhawk/network,
ground-sign and pilot-takeover gates in `docs/flight/README.md` pass.

### 9 September evidence-retention plumbing

Three evidence-plumbing changes were made so a retained trial can be
reconstructed from its bag directory alone (no controller behaviour, TIM-MARS,
detector, tracker, threshold, model, config or evaluation change):

1. **Run logs retained with the bag.** `tools/start_live_stack.sh` now archives
   `control.log`, `dashboard_bridge.log`, `target_memory_mars.log` and the
   operator event log into `<bag>/run_logs/` on stop, keyed by the exact
   `RUN_ID` (never the mutable `latest` symlink), via
   `tools/live/archive_run_evidence.py`. It refuses to overwrite an existing
   retained destination, never deletes the source logs, and records a missing
   required log explicitly in `run_logs/archive_manifest.json` rather than
   creating an empty placeholder.
2. **Controller parameters frozen into provenance.** `run_metadata.json` now
   records the running `control_ref_node`'s resolved parameters (gains,
   limits, slew, freshness timeout, and the frozen #74 recovery bounds),
   queried live via `ros2 param dump` — never mirrored from launch arguments.
   `enable_yaw_recovery` is asserted to be `false`. A failed query is recorded
   as `query_ok=false` and fails `tools/live/validate_live_run_metadata.py`;
   it is never replaced with source-code defaults.
3. **Operator event log.** `tools/live/operator_event.py` appends structured
   JSONL events (`trial_start`, `trial_end`, `target_selected`,
   `operator_takeover`, `abort` with class + reason, `unexpected_behavior`,
   `trial_verdict`) tied to `RUN_ID`, with UTC and monotonic timestamps for
   ROS synchronisation.

The retained package is specified in
`docs/flight/retained_evidence_package.md`. Bounded yaw recovery remains
forced OFF; no candidate-recovery activation path was added. Native Pixhawk
`.bin` dataflash retrieval remains manual.

### 10 September bounded yaw-recovery candidate activation

The frozen Issue #74 bounded yaw-only recovery candidate can now be selected
for a physical trial through a deliberate, default-OFF launcher opt-in
(`tools/lib/live_cli.sh` / `tools/lib/live_defaults.sh`):

- **baseline** (default, no new flags): perception `LOST` -> hover / zero
  motion. `enable_yaw_recovery:=false`.
- **candidate**: `--field-record --control-mavros --control-yaw-recovery
  --acknowledge-yaw-recovery-candidate`. Perception `LOST` + eligible recent
  trusted history -> bounded yaw-only recovery (translation still prohibited);
  `LOST` without eligible evidence -> hover. `enable_yaw_recovery:=true`.

`--control-yaw-recovery` fails before launch without the acknowledgement, or
without control + `--control-mavros` + `--field-record`. No recovery bound is
a CLI knob; the frozen `control_ref_node` values are used unchanged. Retained
provenance asserts the running node's `enable_yaw_recovery` against the
launcher intent (`--expect-param`), so a mismatched trial fails the provenance
validator. `flight_metadata.txt` records `trial_condition` and
`control_yaw_recovery_enabled`. The operator records the matching `trial_start`
event (`--condition candidate --recovery-enabled` / `--condition baseline`);
the launcher prints the exact command at startup. No arming/mode-change
authority is added; `docs/flight/README.md` physical gates still apply.

### 10 September retained-finalization hardening

Home-only engineering hardening so a future retained trial survives recorder
truncation, shutdown-order mistakes and incomplete packaging:

- **Shutdown order** (`tools/lib/live_shutdown.sh`): application nodes stop
  first (controller emits its final safe-zero + shutdown diagnostic while the
  recorders keep running), then a `STOP_APP_SETTLE_S` window, then
  `finalize_recorders` sends SIGINT to the recorder(s) and waits up to
  `RECORDER_FINALIZE_GRACE_S` (10 s, was ~1 s) for process exit after
  flushing/finalizing before any SIGTERM/SIGKILL escalation. Final cleanup is
  restricted to recorder processes/descendants tracked for that run rather
  than host-wide process matching; finalized MCAP + `metadata.yaml` are checked
  immediately afterward by the bag verifier. Recorder finalization is
  deliberate, not an accidental consequence of reversing a PID array. The
  controller shutdown-zero is unchanged.
- **Bag integrity** (`tools/live/verify_retained_bag.py` → `bag_integrity.json`):
  from the finalized `metadata.yaml` only — directory, metadata parse,
  non-empty storage file, storage format, required topics present, and
  non-zero counts where scientifically required
  (`/control_ref/cmd_vel`, `/control_ref/diagnostics`, and `/mavros/state` +
  `/mavros/imu/data_raw` under `--field-record`).
- **Evidence package** (`tools/live/verify_evidence_package.py` →
  `evidence_package_status.json`): required vs missing vs optional-absent vs
  pending post-flight; runs the provenance validator; status
  `complete_runtime_evidence` / `incomplete_runtime_evidence` /
  `pending_postflight_annotation` / `pending_pixhawk_dataflash`. Prints
  `EVIDENCE PACKAGE INCOMPLETE`; process/flight safety is never affected and a
  failed bag is kept.
- **MAVROS evidence**: added `/mavros/setpoint_raw/target_local` (FCU setpoint
  echo vs `/control_ref/cmd_vel`) and `/mavros/statustext/recv` (FCU
  prearm/EKF/failsafe/mode messages) — both standard ArduPilot plugins, not on
  the `apm` denylist; required present, not non-zero.
- **Overwrite safety**: `refuse_existing_bag_dir` fails before recording into
  an existing non-empty directory (RUN_ID stays deterministic, Issue #118).
- **Pixhawk DataFlash**: `tools/live/archive_pixhawk_dataflash.py` archives an
  explicitly-supplied `.bin` (SHA-256, refuse overwrite, preserve source,
  manifest). It never talks to an FCU and never selects "latest".
  **Real-hardware retrieval verification is pending** — no Pixhawk available.

Full copy-paste procedure: `docs/flight/field_day_runbook.md`.

### Combined raw recording (diagnostic)

`./tools/start_live_stack.sh --field-record --record-raw --tag SCENARIO`
produces the normal live-pipeline MCAP bag with MAVROS telemetry plus a separate
synchronised `__image_raw` MCAP bag with `/camera/image_raw`. `--field-record`
enforces the field/Pixhawk network mode (ISR Wi-Fi first, with the approved
AERONEXT fallback), stops Tailscale, starts one managed MAVROS instance and
verifies the `BODY_NED` velocity contract, so run it from the Pi's local
terminal with the Pixhawk connected.

Raw recording requires at least 40 GiB free (enforced by
`tools/lib/live_storage.sh`). The measured combined raw frame rate stays well
below the 640x480 30 FPS nominal, so this mode is a diagnostic option, not the
source-first field session — verify the recorded frame count and duration with
`ros2 bag info` before leaving the field.

## Safe network inspection

When preparing Issue #50 with the real field hardware:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    sudo ./tools/host/set_pi_network_mode.sh pixhawk
    nmcli -t -f ACTIVE,SSID dev wifi
    ip route
    systemctl is-active tailscaled

Required before aircraft operation:

- approved field Wi-Fi only, with ISR preferred whenever available;
- Pixhawk Ethernet route present without becoming the default route;
- Tailscale inactive;
- no automatic arming;
- manual pilot takeover available.

The exact retained ground/hover/flight launch commands must be frozen in
`docs/flight/README.md` after the current live-stack/control audit. Until then,
do not substitute commands from `docs/archive/flight/`.
