# Issue #55 M6 field-network validation

## Status

**PASS — 2 September 2026.**

This document retains the final live field-network evidence required by Issue
#55 M6. It complements the already completed real-iPhone UI, target-selection,
frontend-packaging, shutdown, and performance gates.

Issue #55 itself remains open for M7, which removes the old internal frontend
only after this M6 closure.

## Required invariant

The final host-network invariant is:

`NO PIXHAWK -> NO AERONEXT GCS`

The invariant applies both before field entry and continuously after field mode
has been entered.

Field mode is explicit. Physical Ethernet carrier is a prerequisite but never
an automatic trigger.

## Implementation reference

Thesis-Code implementation commit:

    3a42c8e433bf547e8360a42bf2d45916de189afa

Installed/tested component SHA-256 values:

- `thesis_host_health.py`: `981f5bfbcbb83c2966ded9f347861c02af397006fb64af10d8276ec9045dd910`
- `set_pi_network_mode.sh`: `6baf82af994230a6ba8d24b5e08982ae56e33366e4696e35bef6d22267ab636b`
- NetworkManager dispatcher:
  `5e71ba769b3937d7ca35df2d96fcda446dbe0412ccb2c7c1151cf8a6b036b6f6`

The installed copies matched these repository digests during final validation.

## Retained raw evidence

Raw evidence is retained under:

    reports/p055_field_network_2026_09_02/

Positive field-entry log SHA-256:

    5ac3af66d607dac0e6dd26274275d005f0bab55309054a17312d690fb2a8704c

Physical Pixhawk-unplug log SHA-256:

    93fc137facb8bb68e13eabef6b4ec24f494f58a00327bc91ad909dce5585c52c

## Real positive field entry

The retained positive-entry run proved:

- start state: maintenance Wi-Fi `ISR`, mode `unattended`, Tailscale active;
- real Pixhawk carrier present;
- explicit field transition succeeded;
- field Wi-Fi became `ISR Aero.Next GCS`;
- Pi field address was `192.168.8.174/24`;
- `pixhawk-apm` was the active Ethernet connection;
- Pixhawk Ethernet had no default route;
- mode was `pixhawk`;
- Tailscale was inactive;
- GCS `connection.autoconnect` remained `no`;
- controlled return restored `ISR`, `unattended`, and Tailscale.

Retained markers:

- `REAL_FIELD_ENTRY_GATE=PASS`;
- `REAL_FIELD_ROLLBACK_GATE=PASS`;
- `REAL_POSITIVE_FIELD_GATE=PASS`.

## Real physical Pixhawk disconnect

The final continuous-invariant test entered a valid real field state, stopped
the periodic two-minute health timer to isolate the fast NetworkManager
dispatcher path, and then physically removed the Pixhawk Ethernet cable.

Timeline:

- carrier loss:
  `2026-09-02T12:34:00.434Z`;
- automatic unattended exit:
  `2026-09-02T12:34:08.752Z`;
- carrier-loss to unattended:
  `8318 ms`;
- maintenance-network recovery:
  `2026-09-02T12:34:14Z`.

Final post-unplug state:

- Wi-Fi: `ISR`;
- Pixhawk carrier: `0`;
- no active `pixhawk-apm` connection;
- mode: `unattended`;
- Tailscale: active;
- GCS `connection.autoconnect`: `no`;
- default route: maintenance `wlan0` only;
- emergency rollback: not used.

The disconnect service completed successfully with
`Result=success`, `ExecMainCode=0`, and `ExecMainStatus=0`.

Retained markers:

- `REAL_PHYSICAL_DISCONNECT_GATE=PASS`;
- `NO_PIXHAWK_NO_AERONEXT_GCS=PASS`;
- `FAST_DISPATCHER_PATH=PASS`.

## Recovery-policy audit

The final health-monitor audit also closed two policy holes before live
validation:

1. unattended recovery no longer uses generic
   `nmcli device connect wlan0`; it only re-enables NetworkManager device
   autoconnect, leaving field/GCS profiles with
   `connection.autoconnect=no` excluded;
2. the health monitor never activates field Wi-Fi itself. Any invalid
   field-network state returns to `unattended`; only a new explicit operator
   `pixhawk` transition may activate an approved GCS profile.

## Final source validation

Immediately after the live physical-disconnect gate:

- host recovery tests: `27 passed`;
- network-mode shell syntax: PASS;
- installer shell syntax: PASS;
- dispatcher shell syntax: PASS;
- health-monitor Python compile: PASS;
- systemd unit verification: PASS;
- `git diff --check`: PASS;
- no root `log/`, `hailort.log`, or `.pytest_cache` artifacts.

## M6 conclusion

The approved field-network gate is closed.

Combined with the previously completed real-iPhone UI, numbered-overlay,
SELECT -> LOCKED -> CLEAR -> NO_TARGET, static-frontend, deterministic shutdown,
and A/B/C performance gates, Issue #55 M6 is complete.

M7 is therefore unblocked but is not part of this validation.
