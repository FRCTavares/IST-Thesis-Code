# Tools Directory

This directory contains the repository's executable tooling and the assets
owned by those tools: replay, evaluation, annotation/review, live operation,
host recovery, camera diagnostics, and setup.

Most final TIM-MARS evaluation work should use the more specific subfolder tools
rather than ad-hoc ROS commands.

## Main entrypoints

| Tool | Status | Purpose |
| --- | --- | --- |
| `tools/thesis_build.sh` | Build entrypoint | Builds the ROS 2 workspace with repository-local logs. |
| `tools/reproduce_tim_mars.py` | Reproducibility entrypoint | Validates frozen inputs, builds the workspace, runs the canonical TIM-MARS matrix, and verifies tables and provenance. |
| `tools/start_live_stack.sh` | Live operation entrypoint | Starts the live camera, perception, tracker, TIM/control/dashboard stack. |
| `tools/start_ui_stack.sh` | UI compatibility entrypoint | Delegates browser-frontend startup to the separately owned `FRCTavares/IST-Thesis-UI` repository; it contains no npm/Vite implementation. |
| `tools/timing_contract.py` | Shared contract | Defines schema-v4 timing fields, topic ownership, labels, metric tiers, and warning thresholds. |

Individual evaluation and replay commands remain in their owning
`analysis/`, `experiments/`, `catalogue/`, or `bag/` directories. The single
public exception is `tools/reproduce_tim_mars.py`, which composes the frozen
split, build helper, canonical component matrix, evaluators, fingerprints, and
table-consistency checks without hiding their recorded commands or provenance.

## Live field recording

Current retained-data procedures are issue-specific rather than one generic
field session:

- Issue #27 final held-out source capture:
  `docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md` and
  `tools/experiments/record_p027_heldout_sequence.sh`.
- Issue #50 closed-loop aircraft validation:
  `docs/flight/P050_FLIGHT_VALIDATION.md`. This procedure is currently
  **not executable** until the exact current-system flight command is frozen.
- Issue #64 representative small-target/high-resolution capture:
  `docs/flight/p064_high_resolution_capture_runbook.md`.

Do not use archived P023 or S01/S02/S03/V01 commands as current operator
instructions.

### Optional combined raw recording

The normal live bag keeps the dashboard, detections, tracks, TIM-MARS outputs,
timing, and control topics. Add a clean camera stream without replacing those
outputs by using:

```bash
./tools/start_live_stack.sh --field-record --record-raw --tag SCENARIO_NAME
```

This creates three synchronized recordings:

- the normal live pipeline bag under `bags/live_camera/`;
- a separate `__image_raw` MCAP bag containing `/camera/image_raw`;
- a separate `__mavros` MCAP bag containing Pixhawk telemetry.

Raw recording requires at least 40 GiB free by default. At 640x480 BGR8 and a
true 30 FPS, the theoretical uncompressed payload is about 28 MB/s or 1.7
GB/min. ROS/DDS and live-stack load can reduce the delivered raw frame rate, so
check the recorded count and duration with `ros2 bag info` before leaving the
field. The raw bag is clean camera imagery, not a guarantee of 30 recorded FPS.
Because the measured combined mode does not approach 30 raw FPS, it is a
diagnostic option and is not recommended for the source-first field session.

`--field-record` enforces the AERONEXT/Pixhawk Ethernet network mode and stops
Tailscale. Run it from the Pi's local terminal when the Pixhawk is connected.

## Subdirectories

| Directory | Purpose |
| --- | --- |
| `analysis/` | Offline bag analysis, selected-target correctness, bbox correctness, timing checks, and TIM diagnostic extraction. |
| `experiments/` | Reproducible TIM-MARS replay runners and controlled target publishers. |
| `bag_annotation_ui/` | Local annotation/review UI and visual validation rendering tools. |
| `bag/` | Standalone bag overlay/video utilities. |
| `live/` | Small live ROS 2 inspection helpers. |
| `camera/` | Camera probing and validation scripts. |
| `catalogue/` | Builds the TIM evaluation bag/run catalogue. |
| `host/` | Raspberry Pi networking, recovery, installation, and co-located systemd assets. |
| `setup/` | Host/runtime setup helpers. |
| `lib/` | Shared shell fragments sourced by `start_live_stack.sh`. |
| `tests/` | Automated contracts for repository tooling. |

## Layout contract

- Keep the small, commonly invoked repository entrypoints directly under
  `tools/`.
- Put domain-specific commands, support modules, templates, and installation
  assets in the owning subdirectory.
- Keep service/configuration assets beside the installer that consumes them;
  `tools/host/systemd/` is the source for the Pi host-recovery installation.
- Do not create a separate top-level deployment tree for tool-owned assets.
- Generated `__pycache__`, `.pyc`, and `.pytest_cache` content is ignored and
  must not be committed.
- Sourced modules under `tools/lib/` are not standalone executables.

## Audit status

The directory was reference- and path-audited on 22 July 2026. The cleanup
removed unused convenience wrappers, a redundant track-video renderer, and a
broken date-specific comparison preset whose input bags no longer exist. The
remaining tools are either current entrypoints, tested workflow components,
hardware diagnostics, or explicitly documented support utilities.

## Recommended final evaluation path

For final selected-target TIM-MARS evaluation:

1. Use `tools/experiments/run_one_memory_tim_replay.sh` for memory-only TIM-MARS
   replay over existing tracks/targets/annotations.
2. Use `tools/analysis/evaluate_tim_target_correctness.py` for selected-target
   duration metrics.
3. Use `tools/analysis/evaluate_tim_target_bbox_correctness.py` when spatial bbox
   agreement is needed.
4. Use `tools/analysis/evaluate_tim_by_event_type.py` for event-level summaries.
5. Use annotation/review tools only for manual inspection and annotation editing.

## Policy

Treat documented entrypoint paths as a compatibility interface. Many reports,
commands, runbooks, and local workflows refer to them directly.

Prefer this order for cleanup:

1. document purpose and status,
2. verify references,
3. make behavior changes only when needed,
4. run syntax checks,
5. commit only noticeable changes.
