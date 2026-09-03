# Issue #50 — Current Aircraft Validation Status

## Status

**NOT YET EXECUTABLE AS A RETAINED FLIGHT PROCEDURE.**

Issue #50 owns the current closed-loop aircraft validation. The archived P023
documents are historical and must not be used as current launch instructions.

The field browser/iPhone workflow is maintained separately in
`docs/flight/P055_FIELD_UI_RUNBOOK.md`. That document owns UI/network
operation only; this #50 procedure remains authoritative for aircraft control,
MAVROS, abort handling, and retained flight evidence.

Before a final #50 flight command is frozen, the following still require
current-system verification:

1. provision and validate the approved AERONEXT fallback Wi-Fi profile;
2. verify `ISR Aero.Next GCS` remains first-priority field Wi-Fi;
3. verify `pixhawk-apm` on Ethernet has no default route;
4. verify Tailscale is disabled/inactive in field mode;
5. audit the current #74 state-aware controller and its default-OFF recovery
   behaviour;
6. freeze the exact target-selection, control-authority and abort procedure;
7. define the exact retained bag/topic set.

Existing launcher capabilities such as `--field-record`, `--record-mavros` and
`--record-raw` are not, by themselves, an approved #50 flight command.

## 2 September 2026 MAVROS launch reconciliation

The normal/field live path now has one MAVROS owner. `--record-mavros` launches
MAVROS, waits for `/mavros/state` to report `connected: true`, verifies the
stream-rate service, requests the configured stream rate, and retains MAVROS
telemetry in the normal live bag. `--field-record` is only a convenience alias
for normal live recording plus this canonical MAVROS path; it does not perform
a network-mode transition and does not launch a second MAVROS instance.

Field networking must therefore be entered and verified before live-stack
startup. This matches the headless field workflow: enter `pixhawk` explicitly,
allow Tailscale to stop, reconnect from the approved GCS LAN, verify the field
network state, and only then launch the live stack.

The retained MAVROS evidence includes `/mavros/battery`, state/extended-state,
RC context, position/velocity context, and the actual #74 controller MAVROS
output `/mavros/setpoint_velocity/cmd_vel`. The obsolete
`cmd_vel_unstamped` recording mismatch has been removed.

This reconciliation no longer represents only a software contract. On
3 September 2026 the real Pixhawk Ethernet/MAVROS telemetry path was physically
validated while the aircraft remained disarmed. Passive MAVLink inspection
showed the active FCU as `10.1`; MAVROS targeting `10.1` then reported
`connected: true`, identified ArduCopter 4.6.3 on Pixhawk 6X, delivered
`/mavros/battery` (16.263 V, 98%, present), and published
`/mavros/imu/data_raw` at approximately 50 Hz after the stream-rate request.

This physical telemetry PASS does not yet promote the stack to an approved
aircraft procedure. Controller mirroring, target authority, manual
takeover/abort behaviour, control-sign checks, and the exact first closed-loop
command remain #50 ground gates.

A repository-native `--field-record --no-control --no-dashboard` ground run
then exercised the corrected Thesis-Code MAVROS lifecycle directly. The
retained 55.834 s MCAP contained 2,772 `/mavros/imu/data_raw` messages
(approximately 49.65 Hz), 2,765 battery messages, 2,768 RC-input messages and
2,768 RC-output messages. A subsequent passive five-second Ethernet capture
decoded 5,178 of 5,178 MAVLink frames as system/component `10.1`, including
HEARTBEAT, RAW_IMU, RC_CHANNELS and BATTERY_STATUS. No `9.1` frame was present
in that passive sample.

The same native run exposed two host-side validation defects rather than a
telemetry failure. The repeated short-lived raw-IMU startup probes could report
a false negative despite a healthy approximately 50 Hz stream, and broad
process-name cleanup could match an invoking shell whose command line happened
to contain stack-process names.

Both defects were hardened and physically re-tested on 3 September 2026.
Stale-process discovery is now PID-first and explicitly excludes the launcher
ancestry, while raw-IMU readiness uses one QoS-explicit sensor-data subscriber
for the complete readiness window. A fresh disarmed
`--field-record --no-control --no-dashboard` regression connected MAVROS to
target `10.1`, reported `MAVROS raw IMU stream detected`, reached the normal
live runtime, and stopped cleanly without leaving MAVROS, controller, launcher
or recorder processes behind.

The retained regression MCAP was 57.797 s long and contained 2,866
`/mavros/imu/data_raw` messages (approximately 49.59 Hz), 2,860 battery
messages (approximately 49.48 Hz), 2,860 `/mavros/rc/in` messages,
2,860 `/mavros/rc/out` messages, and 2,873 global-position messages
(approximately 49.71 Hz). The repository-native MAVROS lifecycle and the two
launcher hardening changes therefore pass this physical disarmed regression.

Two independent follow-up items remain from this regression.
`/mavros/extended_state` was advertised but retained zero messages. The FCU
also repeatedly reported `PreArm: RC not found`; however, the RC transmitter
was not available or powered during this session, so that message is expected
for the tested setup and is not evidence of a Pixhawk/MAVROS defect. Real RC
input and manual pilot takeover remain untested and mandatory before flight.
The recorder also reported 841 transport-layer message losses; final retained
flight evidence must account for message-loss behaviour rather than assuming
a lossless bag.

During the same 3 September ground session an independent operator-facing GCS
telemetry path was also physically present. Mission Planner on the ground
station was connected through a 433 MHz telemetry radio and displayed live
vehicle/map telemetry while visibly reporting the aircraft as `DISARMED`. The
Mission Planner serial connection was shown at 57600 baud. This provides useful
physical evidence that the operator had a separate GCS telemetry view while the
Raspberry Pi used the Ethernet/MAVROS path.

The telemetry-radio/GCS observation is not evidence of an RC pilot-control
link and therefore does not clear the manual-takeover gate. During this
3 September session the RC transmitter/controller was not available and was
not powered, so the FCU message `PreArm: RC not found` is expected under the
tested physical setup and is not classified here as a Pixhawk/MAVROS defect.
The real RC input and manual-pilot takeover path were therefore not tested and
remain a mandatory physical ground gate before flight.

A subsequent UI-visible disarmed ground run passed the current operator
target-authority path with aircraft control explicitly disabled. The field UI
showed the live camera, numbered ByteTrack candidates, TIM-MARS state, real
MAVROS battery telemetry and `NO_CONTROL`. The operator selected tracker ID
`#4`; TIM-MARS visibly reached `LOCKED`; CLEAR then returned the system to
`NO_TARGET`.

The retained authority event log independently records generation 1 as
`authority_state="selection_requested"`, `reason="operator_select"` and
`requested_target_id=4`, followed by generation 2 as
`authority_state="cleared"` with `reason="operator_clear"`. The 194.134 s
MCAP retained 5,016 `/target_memory_mars` messages, 5,016
`/target_memory_mars/status` messages and 5,061 `/tracks` messages. Its metadata
records `control_enabled=0`, `mavros_mirror_enabled=false`,
`target_authority_source=/target_memory_mars` and `record_mavros=1`.

This physically passes the UI SELECT -> LOCKED -> CLEAR -> NO_TARGET
target-authority gate in a disarmed no-control configuration. It does not clear
the separate RC/manual-takeover, controller-sign, controller-to-MAVROS
mirroring or first closed-loop aircraft-command gates. The same run retained
zero `/mavros/extended_state` messages and reported 2,726 transport-layer
message losses; both remain follow-up items before final retained flight
evidence.

## 3 September 2026 abrupt-reset observation

During the same ground-validation session the Raspberry Pi experienced one
abrupt restart. The previous boot journal ended without an orderly systemd
shutdown sequence. No retained evidence identified a kernel panic, thermal
shutdown, OOM event, filesystem failure, explicit reboot/shutdown request, or
power-button event. `/sys/fs/pstore` contained no crash record. The systemd
hardware watchdog was configured and active with a 30 s runtime timeout, but
the available evidence does not establish that the watchdog caused the reset.
The reset cause is therefore recorded as unclassified rather than inferred.

Post-reboot behaviour failed safe. The host returned in `unattended` mode on
the maintenance `ISR` Wi-Fi profile with Tailscale active. Although physical
Pixhawk Ethernet carrier remained present, `pixhawk-apm` was not automatically
activated, no Pixhawk route was installed, and no MAVROS process was running.
The system therefore did not automatically restore field or aircraft-control
state after the restart.

This observation does not block continued disarmed ground validation, but a
repeat unexplained reset is a flight-readiness blocker and must be investigated
before any retained aircraft flight.

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

The exact retained ground/hover/flight launch commands must be added here
under Issue #50 after the current live-stack/control audit. Until then, do not
substitute commands from `docs/archive/flight/`.
