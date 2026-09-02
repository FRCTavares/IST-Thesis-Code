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
5. connect the real Pixhawk and verify MAVROS telemetry;
6. audit the current #74 state-aware controller and its default-OFF recovery
   behaviour;
7. freeze the exact target-selection, control-authority and abort procedure;
8. define the exact retained bag/topic set.

Existing launcher capabilities such as `--field-record`, `--record-mavros` and
`--record-raw` are not, by themselves, an approved #50 flight command.

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
