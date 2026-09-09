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
