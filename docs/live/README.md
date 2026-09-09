# docs/live

Last reviewed: 2026-09-09

## Purpose

Operational contracts for running the live dashboard stack: network exposure,
access control, and the operator-facing trust boundary. Runbooks and field
procedures for a flight day stay in `docs/flight/`.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `dashboard_trust_boundary.md` | Access contract | Defines the dashboard bind policy, control-endpoint token, CORS / WebSocket-origin allowlist, and the field-network assumptions for `tools/start_live_stack.sh`. |

## Rules

- Loopback bind is the default; a non-loopback bind requires
  `DASHBOARD_CONTROL_TOKEN` and the launcher enforces this.
- No secret is committed; the operator supplies the token through the
  environment.
- The dashboard is a command surface into TIM-MARS, never the selected-person
  identity authority.

## See also

- [Flight-day operator sheet](../flight/README.md)
- [Control contracts](../control/README.md)
