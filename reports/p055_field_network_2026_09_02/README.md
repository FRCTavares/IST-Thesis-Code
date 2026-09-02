# P055 field-network retained evidence

Date: 2 September 2026

Issue: #55

Implementation commit:

    3a42c8e433bf547e8360a42bf2d45916de189afa

This directory retains the raw host-network evidence used to close the Issue
#55 M6 field-network gate.

## Files

- `positive_field_entry.log` — real Pixhawk-connected transition from
  unattended maintenance networking to `ISR Aero.Next GCS`, with
  `pixhawk-apm` active, no Ethernet default route, and Tailscale inactive,
  followed by a controlled return to unattended mode.
- `physical_pixhawk_unplug.log` — real physical Pixhawk Ethernet removal while
  already in field mode, proving automatic fail-closed return to unattended
  networking through the NetworkManager dispatcher path.
- `SHA256SUMS` — digest of the two retained raw logs.

Original raw-log SHA-256 values:

- positive field entry:
  `5ac3af66d607dac0e6dd26274275d005f0bab55309054a17312d690fb2a8704c`
- physical Pixhawk unplug:
  `93fc137facb8bb68e13eabef6b4ec24f494f58a00327bc91ad909dce5585c52c`

## Final physical-disconnect result

The physical-unplug evidence records:

- valid real field state on `ISR Aero.Next GCS`;
- `pixhawk-apm` active with carrier present;
- Tailscale inactive;
- no default route on Pixhawk Ethernet;
- physical carrier loss at `2026-09-02T12:34:00.434Z`;
- automatic unattended exit at `2026-09-02T12:34:08.752Z`;
- carrier-loss to unattended detection: `8318 ms`;
- maintenance `ISR` Wi-Fi and Tailscale recovered by
  `2026-09-02T12:34:14Z`;
- no emergency rollback;
- `REAL_PHYSICAL_DISCONNECT_GATE=PASS`;
- `NO_PIXHAWK_NO_AERONEXT_GCS=PASS`;
- `FAST_DISPATCHER_PATH=PASS`.

The two-minute periodic health monitor was stopped during the physical-unplug
test, so the successful automatic exit is attributable to the fast
NetworkManager dispatcher path rather than the slower health backstop.
