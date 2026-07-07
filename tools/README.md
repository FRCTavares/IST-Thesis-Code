# Tools Directory

This directory contains thesis support tools for replay, evaluation,
annotation/review, visualization, live operation, camera diagnostics, and setup.

Most final TIM-MARS evaluation work should use the more specific subfolder tools
rather than ad-hoc ROS commands.

## Main entrypoints

| Tool | Status | Purpose |
| --- | --- | --- |
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
| `setup/` | Host/runtime setup helpers. |
| `lib/` | Shared shell fragments sourced by `start_live_stack.sh`. |

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

Do not move, rename, or delete scripts casually. Many reports, commands,
runbooks, and local workflows refer to these paths directly.

Prefer this order for cleanup:

1. document purpose and status,
2. verify references,
3. make behavior changes only when needed,
4. run syntax checks,
5. commit only noticeable changes.
