# TIM Tooling Index

Date: 2026-05-20

## Purpose

Make TIM tooling easier to navigate after TIM-V2E exploration.

## Live path

Use for flight/live operation:

- `tools/start_live_stack.sh`
- `ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py`
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_node.py`
- `ros2_ws/src/thesis_bringup/thesis_bringup/appearance_memory.py`

Do not run training or policy simulation tools during flight.

## Core correctness evaluation

Use these for Raw vs TIM selected-target correctness:

- `tools/analysis/evaluate_tim_target_correctness.py`
- `tools/analysis/extract_tim_all_scores.py`
- `tools/analysis/evaluate_tim_policy_timeline.py`
- `tools/analysis/diagnose_tim_wrong_intervals.py`
- `tools/analysis/run_tim_standard_comparison.py`

`run_tim_standard_comparison.py` is the standard scenario-summary wrapper. It reads existing annotations, policy `summary.md`, and policy `timeline.csv`, then writes generated local output under `reports/tim_standard_matrix/<scenario>/`. It does not run ROS, replay bags, or touch live defaults.

## TIM-V2E learned appearance tools

Use these for current TIM-V2E offline work:

- `tools/analysis/evaluate_tim_identity_descriptor.py`
- `tools/analysis/build_tim_embedding_dataset.py`
- `tools/analysis/train_tim_embedding_tiny.py`
- `tools/analysis/train_tim_embedding_triplet.py`
- `tools/analysis/train_tim_embedding_hybrid.py`
- `tools/analysis/simulate_tim_v2e_learned_suppression.py`
- `tools/analysis/benchmark_tim_embedding_latency.py`

Current best model family:

- `train_tim_embedding_hybrid.py`

Current best offline policy simulator:

- `simulate_tim_v2e_learned_suppression.py`

Current best offline policy:

- Tiny16 hybrid embedding,
- runtime margin gate,
- margin threshold 0.10,
- current similarity threshold 0.0,
- candidate similarity threshold 0.3,
- confirmation frames 3.

## Visual review tools

Use these for overlay videos and review frames:

- `tools/bag/render_tim_policy_overlay_video.py`
- `tools/bag/export_tim_policy_overlay_frames.py`
- `tools/analysis/evaluate_tim_v2e_video_review_annotations.py`

## Historical TIM-V2 policy experiments

Keep for traceability, but do not use as current best path unless explicitly revisiting old hypotheses:

- `tools/analysis/simulate_tim_hypothesis_policy.py`
- `tools/analysis/simulate_tim_v2f_runner_up_policy.py`
- `tools/analysis/simulate_tim_v2h_appearance_gate_policy.py`
- `tools/analysis/simulate_tim_v2i_lost_reacquire_policy.py`
- `tools/analysis/simulate_tim_v2m_locked_suppression.py`
- `tools/analysis/simulate_tim_v2m_armed_locked_suppression.py`

## Generated folders

Do not commit generated files from:

- `datasets/tim_embedding/`
- `datasets/tim_embedding_filtered/`
- `reports/tim_standard_matrix/`
- `reports/tim_v2_embedding/`
- `reports/tim_v0/`
- `reports/tim_v2*_sweep*/`

Only commit curated summaries under `docs/results/...`.

## Rule for future experiments

Every future TIM experiment should produce:

1. metrics,
2. visual evidence,
3. short interpretation,
4. clear comparison with Raw.
