# TIM-MARS tooling index

Date: 2026-09-01

## Purpose

This is the path authority for the maintained TIM-MARS implementation,
operator entrypoints and runtime tooling. Every
repository path in this document is checked automatically by
`tools/tests/test_documented_operator_contract.py`.

Only `mars` and `off` are supported target-memory operator modes.

## Runtime implementation

- Package overview: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/README.md`
- Pure identity-memory core: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory.py`
- ROS node: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory_mars_node.py`
- Runtime/image attachment: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/runtime.py`
- Hard-negative memory: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/hard_negative_memory.py`
- Positive appearance memory: `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/positive_appearance_memory.py`
- Canonical configuration: `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
- Tracker node: `ros2_ws/src/thesis_tracker/thesis_tracker/nodes/tracker_node.py`
- Tracker configurations: `ros2_ws/src/thesis_bringup/config/`

## Operator entrypoints

- Live stack: `tools/start_live_stack.sh`
- Dashboard compatibility launcher: `tools/start_ui_stack.sh`
- Authoritative dashboard frontend: `FRCTavares/IST-Thesis-UI`
- ROS workspace build: `tools/thesis_build.sh`
- Flight-day operator sheet: `docs/flight/field_day_runbook.md`
- Retained flight-evidence package: `docs/flight/retained_evidence_package.md`
- Operator event recorder: `tools/live/operator_event.py`
- Run-evidence log archiver: `tools/live/archive_run_evidence.py`
- Retained-bag integrity check: `tools/live/verify_retained_bag.py`
- Evidence-package completeness check: `tools/live/verify_evidence_package.py`
- Pixhawk DataFlash archiver: `tools/live/archive_pixhawk_dataflash.py`
- Controller diagnostics summary: `tools/analysis/summarize_control_diagnostics.py`
- Timing analysis: `tools/analysis/analyse_bag_timing.py`, `tools/analysis/check_live_timing_invariants.py`
- Resource samplers: `tools/experiments/sample_hardware_health.py`, `tools/experiments/sample_process_groups.py`
- Tools overview: `tools/README.md`

The browser frontend is independently owned by `FRCTavares/IST-Thesis-UI`,
normally checked out at `~/Desktop/IST-Thesis-UI`. Its authoritative launcher is
`~/Desktop/IST-Thesis-UI/tools/start_dashboard.sh`. The local
`tools/start_ui_stack.sh` entrypoint is retained only as an operator
compatibility shim and must not contain frontend build/runtime implementation.

## Replay

- Bag playback with tracker and dashboard bridge: `ros2_ws/src/thesis_bringup/launch/eval_replay.launch.py`
- Timing contract used by the analysers: `tools/timing_contract.py`

## Research archive

Evaluation, annotation, ablation and experiment tooling, split definitions and
result summaries are not part of this tree. They are at Git tag
`archive/thesis-final-20261013`.
