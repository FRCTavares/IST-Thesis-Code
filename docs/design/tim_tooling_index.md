# TIM-MARS tooling index

Date: 2026-07-23

## Purpose

This is the path authority for the maintained TIM-MARS implementation,
operator entrypoints, replay/evaluation tools, and promoted evidence. Every
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
- Dashboard launcher: `tools/start_ui_stack.sh`
- Dashboard instructions: `live-ui/README.md`
- ROS workspace build: `tools/thesis_build.sh`
- Field recording plan: `docs/flight/SOURCE_FIRST_FIELD_RECORDING_PLAN.md`
- Tools overview: `tools/README.md`

The dashboard application is in `live-ui/`. From the repository root, use
`./tools/start_ui_stack.sh`; use `./tools/start_ui_stack.sh --install` after a
fresh checkout to install frontend dependencies.

## Replay and evaluation

- Single reproducibility command: `tools/reproduce_tim_mars.py`
- Deterministic TIM replay: `tools/experiments/run_deterministic_tim_replay.py`
- Component-ablation runner: `tools/experiments/run_tim_component_ablation.py`
- Replay instructions: `tools/experiments/README.md`
- Physical-target bbox evaluator: `tools/analysis/evaluate_tim_target_bbox_correctness.py`
- Tracker-ID diagnostic evaluator: `tools/analysis/evaluate_tim_target_correctness.py`
- Event evaluator: `tools/analysis/evaluate_tim_by_event_type.py`
- Candidate-score extractor: `tools/analysis/extract_tim_all_scores.py`
- Evaluation split validator: `tools/analysis/validate_tim_evaluation_split.py`
- Analysis instructions: `tools/analysis/README.md`

## Frozen experiment definitions

- Development/final split: `docs/data/splits/tim_mars_split_v1.json`
- Split policy: `docs/data/splits/README.md`
- Component-ablation manifest: `docs/data/ablations/tim_mars_component_ablation_v1.yaml`
- Component-ablation interpretation: `docs/data/ablations/README.md`

## Visual review

- Side-by-side raw/TIM renderer: `tools/bag/render_tim_comparison_video.py`
- General bag overlay renderer: `tools/bag/render_bag_overlay_video.py`
- Annotation/review UI: `tools/bag_annotation_ui/tim_clean_ui.py`
- Annotation UI instructions: `tools/bag_annotation_ui/README.md`

## Promoted tracked evidence

- Evidence-version authority: `docs/algorithm/tim_mars_evidence_versions.md`
- Machine-readable evidence map: `docs/data/catalogue/tim_evidence_versions.json`
- Current dual-oracle development audit: `docs/results/selected_target_tracking/p028_wrong_oracle_audit.md`
- Seven-row development component ablation: `docs/results/selected_target_tracking/p028_component_ablation_development/README.md`
- Current rank-aware safety evidence: `reports/p007_rank_aware_add2b8b8_2026_07_21/closure_summary.md`
- Hard-negative structural evidence: `reports/p006b_hard_negative_03409564_2026_07_21/closure_summary.md`
- Selected-target summary: `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`
- Throughput summary: `docs/results/selected_target_tracking/hard_reentry_compute_throughput_summary.md`

Ordinary generated outputs belong under `reports/` and are not authoritative
until promoted into a tracked evidence package or curated under
`docs/results/`. See `reports/README.md`.

## Experiment evidence rule

Every promoted TIM-MARS experiment must include:

1. source bag and annotation identity;
2. selected target and canonical configuration hash;
3. runtime overrides, Git commit, and repository state;
4. physical-target correctness and tracker-ID fragmentation diagnostics;
5. explicit comparison with the raw tracker;
6. a safety decision where wrong-person output is worse than suppressed output.
