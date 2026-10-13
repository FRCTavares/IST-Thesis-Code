# tools

Last reviewed: 2026-10-13

## Purpose

Executable tooling for the TIM-MARS system — building the workspace, running the
live stack, flight preflight and evidence verification, runtime analysis, and
Raspberry Pi host recovery — plus the assets those tools own. Domain
commands live in the subdirectory that owns them; only stable entrypoints and
one repository-wide contract sit directly under `tools/`.

## Entrypoints

The first three are stable user/operator-facing repository entrypoints. Reports,
runbooks and tests reference them by path, so treat their paths as a
compatibility interface.

| Path | Kind | Why it exists |
| --- | --- | --- |
| `tools/thesis_build.sh` | Build | Builds the ROS 2 workspace with repository-local colcon logs. |
| `tools/start_live_stack.sh` | Live operation | Starts camera → perception → tracker → TIM-MARS → control/dashboard in a fixed order.  |
| `tools/start_ui_stack.sh` | UI compatibility | Delegates dashboard startup to `IST-Thesis-UI/tools/start_dashboard.sh`; this repository contains no frontend runtime. |
| `tools/timing_contract.py` | Contract (library) | Canonical schema-v4 timing fields, topic ownership, metric tiers and warning thresholds. Imported as `tools.timing_contract`; not a CLI. |

## Contents

| Path | Role |
| --- | --- |
| `analysis/` | Runtime diagnostics: timing statistics, control-diagnostics summary, visual-time bounds, source-header audit. |
| `experiments/` | Resource and hardware samplers for a running stack. |
| `camera/` | Camera V4L2 mode probing (hardware diagnostics). |
| `live/` | Live inspection, evidence verification, and the strict offline field-evidence summary gate. |
| `host/` | Raspberry Pi networking / unattended recovery and its `systemd/` assets. |
| `flight/` | Flight-preflight and field-readiness command-line helpers. |
| `mac/` | macOS-side connection helpers for field operation. |
| `setup/` | Host Hailo / TAPPAS runtime setup helpers. |
| `lib/` | Shared implementation used by the launcher and experiment tools (sourced shell fragments; the process-group supervisor). Not standalone executables. |
| `tests/` | pytest contracts for the non-ROS tooling and the launcher. |

## Recording modes

`tools/start_live_stack.sh` exposes several distinct recording contracts:

- `--field-record` enables the retained structured field-evidence profile with
  separate MJPEG visual recording and managed MAVROS telemetry.
- `--record-structured-visual` uses the same structured evidence profile without
  MAVROS for ground development; it is not an approved aircraft launch command.
- `--source-record` records source `/camera/image_raw` plus MAVROS telemetry
  while disabling tracker/TIM-MARS processing for source acquisition.
- `--source-record-no-mavros` records `/camera/image_raw` plus `/detections`
  without MAVROS or field-network changes.
- `--record-raw` adds the separate synchronized raw-image diagnostic bag; it is
  not part of the approved aircraft launch profile.
- `--record-mavros` is the lower-level MAVROS telemetry recording switch used by
  recording profiles; normal field operation should use `--field-record`.
- `--tag NAME` assigns the retained run/bag tag.

Use `./tools/start_live_stack.sh --help` and `--help-advanced` for the complete
current CLI contract.

## Rules

- Direct children of `tools/` are stable entrypoints or the single repo-wide
  contract. Everything domain-specific goes in the owning subdirectory.
- Documented entrypoint paths are a compatibility interface — grep for a tool
  before renaming or moving it.
- Keep tool-owned assets beside the tool (`host/systemd/`). No separate deploy tree.
- Generated `__pycache__/`, `*.pyc` and `.pytest_cache/` are never committed.

## See also

- Path authority: `docs/design/tim_tooling_index.md`
- README standard: `docs/design/README_STANDARD.md`
- Operating the stack: `docs/OPERATIONS.md`
- Field-day procedure: `docs/flight/field_day_runbook.md`
- Non-aircraft raw capture diagnostic:
  `./tools/start_live_stack.sh --record --record-raw --tag DIAGNOSTIC`
  (not an approved aircraft launch command)
