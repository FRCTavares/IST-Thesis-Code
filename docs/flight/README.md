# Flight and field procedures

Last reviewed: 2026-09-09

## Purpose

Current physical-capture, held-out evaluation, and aircraft-validation
procedures.

## Contents

| Path | Role |
| --- | --- |
| `P027_HELDOUT_CAPTURE_RUNBOOK.md` | Current H01-H03 held-out capture workflow. |
| `P027_HELDOUT_EXECUTION_PLAN_v2.md` | Active Stage-7 prospective held-out execution contract. |
| `P027_H01_EXIT_REENTRY.md` | H01 scenario definition. |
| `P027_H02_CROSSING.md` | H02 scenario definition. |
| `P027_H03_OCCLUSION_DISTRACTOR.md` | H03 scenario definition. |
| `P050_FLIGHT_VALIDATION.md` | Current closed-loop aircraft-validation status and boundary. |
| `p064_high_resolution_capture_runbook.md` | Issue #64 high-resolution appearance-source procedure and frozen R3 evidence boundary. |
| `P027_HELDOUT_EXECUTION_PLAN.md` | Superseded v1 plan retained unchanged for Stage-7 provenance. |

## Rules

- `P027_HELDOUT_EXECUTION_PLAN_v2.md` is the active Issue #27 execution authority.
- Do not inspect held-out algorithm outcomes before the prospective release gate permits it.
- Held-out execution must use a clean revision that passes the frozen v4
  validator. The newest validated first-parent execution checkpoint identified
  on 2026-09-09 is `1f57e2d55ec41342edc75e48032106b69278ae04`. Later `main` revisions contain
  documentation-only changes inside directory-scoped frozen source paths and
  therefore intentionally fail the bytewise source-freeze check. For H01-H03,
  use a clean worktree at a validator-passing revision rather than weakening or
  re-freezing the prospective contract.
- Historical flight procedures belong under `docs/archive/flight/`.
- Do not rewrite frozen capture/evaluation assumptions to match newer runtime defaults.
