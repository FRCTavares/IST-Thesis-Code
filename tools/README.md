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
| `tools/thesis_live.sh` | Convenience wrapper | Small wrapper around live-stack and UI startup commands. |
| `tools/thesis_eval.sh` | Convenience/provenance wrapper | Small wrapper around selected evaluation commands; check paths before using old official shortcuts. |
| `tools/start_live_stack.sh` | Live operation entrypoint | Starts the live camera, perception, tracker, TIM/control/dashboard stack. |
| `tools/start_ui_stack.sh` | UI operation entrypoint | Starts the dashboard frontend with consistent environment/logging. |
| `tools/timing_contract.py` | Shared contract | Defines canonical timing metric names, aliases, labels, and thresholds. |

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
