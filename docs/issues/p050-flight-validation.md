# Issue #50 — Aircraft Validation Preparation Record

## Status

This is the detailed Issue #50 preparation record, not the day-of-flight
operator sheet. Current flight-day authority is `docs/flight/README.md`.

**ACTIVE #50 — Friday 25 September 2026 physical gates pending.** Issue #64
closed on 22 September with VGA 640x480 retained; HD was not promoted and FHD
remains excluded. The canonical linear operator sheet is
`docs/flight/README.md`. Home-side software/documentation checks prepare the
trial but do not establish FCU, restrained, process-loss, takeover or flight
evidence. #32 final mounted characterization follows the physical #50
baseline-versus-yaw-recovery retain/reject decision.

The remaining physical sequence is: provision and validate the explicitly
approved AERONEXT fallback; verify primary/fallback/fail-closed field-network
states with Pixhawk attached; static preflight; passive MAVROS/recorder gate;
compute-only sign/freshness gate; restrained BODY_NED command-path and exact
controller process-loss response; pilot RC/failsafe/PreArm go/no-go; baseline
flight; predeclared matched pairs; per-trial MCAP/visual/operator events and
exact DataFlash; physical-person annotation and final controller decision.
The 22 September remote inspection found the fallback setting empty and no
clearly named approved AERONEXT profile among saved NetworkManager profile
names. No credentials or host network state were changed remotely.

Issue #50 owns the current closed-loop aircraft validation. The archived P023
documents are historical and must not be used as current launch instructions.

The following numbered checklist records the earlier pre-runbook preparation
state. Software command/profile work is reflected in the current runbook;
physical checks still require direct observation with the real FCU:

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

### 19 September controller-status QoS correction

Remote architecture review found that TIM-MARS offered best-effort delivery
for `/target_memory_mars/status`, while `control_ref_node` requested reliable
delivery. ROS 2 Jazzy treats that pair as incompatible, so the status-dependent
authority path could not be considered integrated. The shared authority QoS
contract now retains best-effort, volatile delivery for the high-rate target
state and uses reliable, volatile delivery for authority status at both
endpoints. Focused transport and fail-closed tests plus a non-actuating ROS 2
node exchange verify status reception, trusted-state passage to controller
logic, and zero output for LOST or stale status.

This is remote software validation only. It does not replace any restrained,
props-off, FCU-response, process-loss, takeover or physical-flight gate in the
current runbook.

### 14 September real-hardware MAVLink target validation

Ground-only testing with the real Pixhawk 6X showed that the current FCU
advertises MAVLink target `10.1`, while the older June bring-up documentation
used `9.1`. With the old fixed `9.1` target MAVROS saw packets from remote
`10.1` but never reached `connected: true`; targeting `10.1` immediately
produced a valid ArduPilot heartbeat, `armed: false`, `STABILIZE`, raw IMU and
battery telemetry. `BODY_NED` read-back and the stream-rate request both
passed, and `/mavros/setpoint_velocity/cmd_vel` had zero publishers.

The launcher therefore no longer assumes one historical FCU SYSID. An explicit
`MAVROS_TGT_SYSTEM` remains authoritative when deliberately supplied;
otherwise both the retained field path and source+MAVROS path probe the bounded
approved list `10 9`, fully stopping a failed MAVROS attempt before trying the
next target. The resolved system/component and selection mode are retained in
runtime metadata. Failure to connect to every candidate aborts startup. Target
resolution does not arm the aircraft, change flight mode, or publish setpoints.


### 14 September field-network race diagnosis and revalidation

A first full field-record ground attempt did not validate the automatic MAVROS
target resolver because the host left Pixhawk network mode while the probes were
running. NetworkManager had generated an `eth0` down event while the already
connected `pixhawk-apm` profile was being reactivated; the asynchronous
fail-closed dispatcher then acted on that stale event after the Ethernet link
had recovered, returning the Pi to unattended networking.

The previously deployed Pixhawk-gated host-network implementation was recovered
from commit `3a42c8e4` and restored as the repository source of truth. Field
entry is now idempotent for an already-active approved Wi-Fi and valid
`pixhawk-apm` link, and a serialized disconnect request revalidates Ethernet
carrier, active profile and absence of an Ethernet default route before leaving
Pixhawk mode.

Real-hardware network-only revalidation passed: `ISR Aero.Next GCS` remained
active on `wlan0` at `192.168.8.174/24`, `pixhawk-apm` remained active on
`eth0` at `192.168.144.183/24`, the default route remained exclusively on
Wi-Fi, Pixhawk `192.168.144.14` was reachable, and Tailscale remained inactive.
Repeated Pixhawk-mode entry caused no interface cycle, and a deliberately
started stale disconnect service exited with `stale Pixhawk-disconnect request
ignored: Ethernet link is healthy`. Subsequent MAVROS auto-target probing was
then revalidated successfully on the repaired network path.


The first post-network-repair `9 -> 10` resolver proof then exposed two
launcher-side defects rather than a link failure. The `10.1` MAVROS instance
logged `CON: Got HEARTBEAT, connected. FCU: ArduPilot`, RC input and raw IMU,
but repeated two-second `ros2 topic echo /mavros/state --once` processes never
observed a sample and falsely rejected the healthy FCU. In addition, the
connected `mavros_node` entered its signal handler during probe cleanup and
then produced an Apport `SIGSEGV` report, while cleanup had been watching only
the `ros2 launch` wrapper PID.

The repair therefore uses the persistent per-probe MAVROS heartbeat log for
bounded target resolution and snapshots PID/start-time identities for the
entire owned launch tree before signalling it. A subsequent candidate is
forbidden until every captured identity has disappeared, with TERM/KILL
escalation restricted to those captured processes.

Real-hardware revalidation then passed with the deliberate candidate order
`9 -> 10`: `9.1` timed out and its owned process tree was removed before the
next probe; `10.1` reached the ArduPilot heartbeat and was resolved as system
10/component 1. Raw IMU telemetry was present,
`/mavros/setpoint_velocity/cmd_vel` had zero publishers, and cleanup left no
MAVROS process behind. A persistent `/mavros/state` observation additionally
captured the expected startup transition from one `connected: false` sample to
repeated `connected: true`, `armed: false`, `manual_input: true`, `STABILIZE`
samples. This demonstrated that a first-sample `--once` query is not a valid
MAVROS connectivity predicate; the remaining generic pre-existing-MAVROS check
was therefore changed to use the same bounded transition-aware observation
semantics.

A genuine physical Ethernet-loss test subsequently validated the opposite side
of the fail-closed contract. With the host initially in Pixhawk mode, physical
removal of the Pixhawk Ethernet cable changed `eth0` carrier from 1 to 0.
NetworkManager reported `activated -> unavailable` with reason
`carrier-changed`; the dispatcher/service then logged `confirmed Pixhawk
Ethernet loss; returning unattended`. The host disconnected
`ISR Aero.Next GCS`, enabled Tailscale, returned to `configured_mode=unattended`,
and automatically rejoined ordinary `ISR` Wi-Fi. The final unattended state had
no Pixhawk Ethernet connection or Ethernet route, Tailscale was active, no
MAVROS process was running, and remote access through Tailscale succeeded.
Together with the earlier stale-event test, this demonstrates that recovered
Ethernet is preserved while genuine physical link loss fails closed as
intended.

The return path was also exercised physically. Reconnecting the Pixhawk
Ethernet cable while the host remained in unattended mode restored carrier
without activating `pixhawk-apm`, without reconnecting `ISR Aero.Next GCS`,
and without disabling Tailscale; both field profiles remained
`connection.autoconnect=no`. Field authority therefore did not return merely
because the cable was restored. An explicit `pixhawk` transition was then
requested and completed with return code zero: `ISR Aero.Next GCS` reacquired
`192.168.8.174/24`, `pixhawk-apm` became active on `eth0` at
`192.168.144.183/24`, Pixhawk `192.168.144.14` was reachable, the Ethernet
interface carried no default route, and Tailscale was disabled. No MAVROS
process was started during this network round-trip.

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

Full copy-paste procedure: `docs/flight/README.md`. The field-day runbook is only a short backup.

### Combined raw recording (diagnostic)

`./tools/start_live_stack.sh --record --record-raw --tag
NON_HELD_OUT_DIAGNOSTIC` is retained only for non-held-out recorder diagnostics.
It writes the normal live-pipeline bag plus a separate synchronised
`__image_raw` MCAP bag. It does not enable the field/Pixhawk profile or MAVROS,
and it is not an approved full-stack aircraft command. Normal field recording
uses `--field-record` without `--record-raw`.

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

The exact retained ground/hover/flight commands are frozen in
`docs/flight/README.md`. Do not substitute commands from `docs/archive/flight/`.
