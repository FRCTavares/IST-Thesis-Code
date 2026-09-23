# Control contracts

Last reviewed: 2026-09-14

## Purpose

Maintained controller, Pixhawk, and MAVROS integration contracts for the thesis
system.

## Contents

| Path | Role |
| --- | --- |
| `p074_state_aware_control_contract.md` | Frozen Issue #74 state-aware selected-person control contract. |
| `pixhawk6x_ethernet_mavros_report.md` | Historical Ethernet/MAVROS evidence; current field commands live in `docs/flight/field_day_runbook.md`. |

## Rules

- TIM-MARS remains the sole selected-person identity authority.
- Raw `/target`, tracker output, and detector candidates never acquire motion authority.
- Physical closed-loop validation belongs to the current flight-validation procedure.
