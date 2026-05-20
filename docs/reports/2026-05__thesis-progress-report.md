# May 2026 Thesis Progress Report

Generated: 2026-05-20 11:09

## Executive Summary

May was a major thesis-development month. The work moved from TIM-V1 implementation and evidence gathering into TIM-V2 offline policy design, corrected evaluation methodology, ROS replay validation, and first live-code integration of rank-aware reacquisition.

Main outcome:

> TIM-V2K is currently the strongest implemented candidate. It improves LOST-state rank-aware reacquisition, but it does not solve wrong-LOCKED persistence. The remaining research direction is stronger identity evidence or a more selective wrong-LOCKED detector.

## Repository State

```text
clean
```

## May Commit History

```text
918f1e4 2026-05-20 05-20-2026: Add TIM-V2 current status summary
dc3ac12 2026-05-20 05-20-2026: Add TIM-V2M locked-suppression analysis
b328761 2026-05-20 05-20-2026: Finalize TIM-V2K replay implementation hooks
939f94c 2026-05-20 05-20-2026: Add TIM-V2K ROS hard-reentry validation
f71da3f 2026-05-20 05-19-2026: Expose TIM-V2K target-memory node parameters
1638bc0 2026-05-20 05-19-2026: Add TIM-V2K rank-aware reacquisition core
bda1a84 2026-05-19 05-19-2026: Add TIM-V2K design specification
57cb8d3 2026-05-19 05-19-2026: Add TIM-V2 appearance extraction tooling
2fc51ac 2026-05-19 05-19-2026: Add corrected TIM-V2K TIM-V1M analysis
daddb41 2026-05-18 05-18-2026: Add TIM-V2 offline design conclusion
7ff5a04 2026-05-18 05-18-2026: Add TIM-V2 appearance-gating offline analysis
fd453c8 2026-05-18 05-18-2026: Add TIM-V2F generalisation analysis on TIM-V1M
8b248bc 2026-05-18 05-18-2026: Document invalid TIM-V2F second-pair validation
ff936ba 2026-05-18 05-18-2026: Add TIM-V2 offline policy simulations
c1c527a 2026-05-18 05-18-2026: Add TIM-V2 offline hypothesis simulation results
a68329c 2026-05-16 05-16-2026: Add TIM-V2 hypothesis competition plan
e2c3ee6 2026-05-16 05-16-2026: Add appearance cooldown correctness result
42325d1 2026-05-16 05-16-2026: Add cooldown hard reentry correctness annotation
7803544 2026-05-16 05-16-2026: Document appearance cooldown activation
02aeb53 2026-05-16 05-16-2026: Add appearance update cooldown after reacquisition
6e83170 2026-05-16 05-16-2026: Document appearance challenge gate test
6bbe05f 2026-05-16 05-16-2026: Add experimental appearance challenge gate
9370d08 2026-05-16 05-16-2026: Add final hard reentry correctness result
4283042 2026-05-16 05-16-2026: Finalise hard reentry correctness annotation
48d11a9 2026-05-16 05-16-2026: Add eval bag annotation rule
83f58a4 2026-05-16 05-16-2026: Refine hard reentry correctness annotation
b407ee7 2026-05-16 05-16-2026: Add raw appearance diagnostics to TIM scores
e16d9fe 2026-05-16 05-16-2026: Prevent replay runner from overwriting eval bags
ba08209 2026-05-16 05-16-2026: Add TIM candidate competition diagnosis
6fcf085 2026-05-16 05-16-2026: Add TIM all-scores candidate availability diagnosis
f40773c 2026-05-16 05-16-2026: Export and extract TIM all candidate scores
2109ff3 2026-05-16 05-16-2026: Add TIM wrong-interval diagnostic script
4d5a30a 2026-05-16 05-16-2026: Add TIM-V1 appearance failure diagnosis
1a92c86 2026-05-16 05-16-2026: Add hard reentry target correctness result
157d171 2026-05-16 05-16-2026: Add hard reentry matrix table
d98e1e2 2026-05-16 05-16-2026: Add TIM matrix summary collector
25f13ea 2026-05-16 05-16-2026: Add hard reentry tracker matrix summary
ca6612b 2026-05-16 05-16-2026: Add DeepSORT hard reentry replay result
a4d546b 2026-05-16 05-16-2026: Document DeepSORT replay enablement
63e4133 2026-05-16 05-15-2026: Let TIM replay matrix continue after failed config
9123b25 2026-05-16 05-15-2026: Add largest-target replay selection
1ded4e1 2026-05-16 05-15-2026: Document hard reentry matrix target-id issue
9b50ac4 2026-05-14 05-14-2026: Add TIM replay matrix runner
7ece8bf 2026-05-14 05-14-2026: Add clean TIM replay experiment runner
e302d2a 2026-05-14 05-14-2026: Remove duplicate replay validation note
ff1e8ea 2026-05-14 05-14-2026: Add clean replay validation result
4de1502 2026-05-14 05-14-2026: Add clean replay validation result
8942a02 2026-05-14 05-14-2026: Add TIM-V1 raw dataset summary
69c9b27 2026-05-12 05-12-2026: Add final TIM-V1 interpretation
6272e11 2026-05-12 05-12-2026: Document rejected TIM-V1R confirmation test
94537d9 2026-05-12 05-12-2026: Document rejected TIM-V1P descriptor test
85d27ca 2026-05-12 05-12-2026: Add tracked TIM-V1M ablation summary
e2376eb 2026-05-12 05-12-2026: Add TIM-V1M appearance ablation
9438371 2026-05-12 05-12-2026: Refine TIM-V1M annotation and threshold sweep
f9bdfa9 2026-05-11 05-11-2026: Finalise TIM-V1 day log and next plan
b0b6e8d 2026-05-11 05-11-2026: Log TIM-V1M threshold sweep
8e68a22 2026-05-11 05-11-2026: Add offline TIM-V1 threshold sweep
243323e 2026-05-11 05-11-2026: Add TIM-V1M manual review notes
2c7b731 2026-05-11 05-11-2026: Log TIM-V1M appearance-critical crossing run
4b60e20 2026-05-11 05-11-2026: Log TIM-V1 appearance ablation
e0c2255 2026-05-11 05-11-2026: Log TIM-V1 target correctness result
033f1c8 2026-05-11 05-11-2026: Add TIM-V1J manual correctness annotations
429b08b 2026-05-11 05-11-2026: Log TIM-V1 two-person ambiguity evidence
10a06ba 2026-05-11 05-11-2026: Log TIM-V1 appearance report
54b8b67 2026-05-11 05-11-2026: Add TIM-V1 appearance diagnostics report
472562d 2026-05-11 05-11-2026: Log TIM-V1 occlusion smoke evidence
09ab597 2026-05-11 05-11-2026: Log version-neutral TIM analysis wording
24df2f9 2026-05-11 05-11-2026: Make TIM bag analysis wording version-neutral
252ce6a 2026-05-11 05-11-2026: Log TIM bag appearance diagnostics
66f1a8c 2026-05-11 05-11-2026: Export TIM appearance diagnostics in bag analysis
7535869 2026-05-11 05-11-2026: Add TIM live diagnostics sample
7ef083b 2026-05-11 05-11-2026: Log TIM live appearance diagnostics
f8074ec 2026-05-11 05-11-2026: Add TIM appearance extraction diagnostics
9c25f80 2026-05-11 05-11-2026: Log TIM image-derived appearance proof
f6e2625 2026-05-11 05-11-2026: Prove TIM image-derived appearance matching
e5bf5a3 2026-05-11 05-11-2026: Log TIM-V1B live validation
6efe2d6 2026-05-11 05-11-2026: Log TIM appearance live-stack flags
c47b793 2026-05-11 05-11-2026: Add TIM appearance live-stack flags
17310ca 2026-05-11 05-11-2026: Test TIM-V1B node appearance extraction
0dad097 2026-05-11 05-11-2026: Log TIM-V1B wrapper integration
8e7e69d 2026-05-11 05-11-2026: Add TIM-V1B image appearance extraction
4138e3f 2026-05-11 05-11-2026: Log TIM-V1A core integration
46bbd07 2026-05-11 05-11-2026: Integrate TIM-V1A appearance cue
4d1df65 2026-05-09 05-09-2026: Add TIM-V1A appearance feature utilities
1375ebe 2026-05-09 05-09-2026: Prepare TIM field recording and TIM-V1A design
3d3c79f 2026-05-07 07-05-2026: Add UAV dataset recording protocol
33451f8 2026-05-07 07-05-2026: Update daily log with dataset recording mode
ad779d1 2026-05-07 07-05-2026: Add dataset bag recording mode
b41867d 2026-05-07 07-05-2026: Condense TIM V0 correctness results
8a6ab7e 2026-05-07 07-05-2026: Add second TIM correctness annotation
5b72206 2026-05-07 07-05-2026: Add TIM target correctness evaluation protocol
e2e22f5 2026-05-07 07-05-2026: Freeze TIM-V0 baseline
7855af9 2026-05-06 05-06-2026: Add TIM-V0 replay workflow
2d9e728 2026-05-06 05-06-2026: Add MAVROS Ethernet bench plan
e07f9c9 2026-05-06 05-06-2026: Add TIM-V0 live UI validation result
32a9208 2026-05-06 05-06-2026: Show TIM-V0 target memory in dashboard
3d39437 2026-05-06 05-06-2026: Add TIM-V1 latent target memory plan
200c07e 2026-05-06 05-06-2026: Add TIM-V0 threshold sensitivity results
5b326f8 2026-05-06 05-06-2026: Add TIM-V0 threshold sensitivity sweep
bd70b7c 2026-05-06 05-06-2026: Add TIM-V0 thesis figure export workflow
85fa910 2026-05-06 05-06-2026: Add TIM-V0 replacement ID CLI alias
ee6ecc4 2026-05-06 05-06-2026: Update novelty plan and daily plan
d369ba1 2026-05-05 05-05-2026: Add TIM-V0 results and daily log
b86ca58 2026-05-05 05-05-2026: Add TIM-V0 state duration metrics
62b17c6 2026-05-05 05-05-2026: Add TIM-V0 fault failure diagnostics
37f390c 2026-05-05 05-05-2026: Add TIM-V0 batch fault injection analysis
d89dd4a 2026-05-05 05-05-2026: Add Hailo and camera recovery guides
3d9c4f9 2026-05-05 05-05-2026: Add TIM-V0 live stack flags
cf2ca25 2026-05-05 05-05-2026: Documents Updated
ca476c5 2026-05-05 05-05-2026: Make TIM-V0 target output control-safe
4889ed8 2026-05-05 05-05-2026: Start TIM-V0 with live stack
bd99c4b 2026-05-05 Add TIM-V0 selected-target memory and evaluation tools
c4f4271 2026-05-04 04-05-2026: Documentation Update
dac89ba 2026-05-04 04-05-2026: consolidate generated outputs and documentation paths
d99f6e7 2026-05-04 04-05-2026: consolidate generated outputs and documentation paths
```

## Main Workstreams

### 1. TIM-V1 consolidation

TIM-V1 established that selected-target memory improves continuity over raw tracker-ID following, but hard crossing and re-entry cases still produce wrong-target duration.

Evidence files:
- `docs/results/tim_v1/2026-05-12__tim-v1m-appearance-ablation.md` — TIM-V1M Appearance Ablation
- `docs/results/tim_v1/2026-05-12__tim-v1p-appearance-descriptor-test.md` — TIM-V1P Appearance Descriptor Test
- `docs/results/tim_v1/2026-05-12__tim-v1r-lost-confirmation-test.md` — TIM-V1R LOST Confirmation Test
- `docs/results/tim_v1/2026-05-14__dataset-summary.md` — TIM-V1 Dataset Recording Summary - 2026-05-14
- `docs/results/tim_v1/2026-05-15__hard-reentry-matrix-notes.md` — TIM Replay Matrix Notes - Hard Re-entry Bag
- `docs/results/tim_v1/2026-05-16__all-scores-candidate-availability-diagnosis.md` — TIM All-Scores Candidate Availability Diagnosis
- `docs/results/tim_v1/2026-05-16__all-scores-candidate-competition-diagnosis.md` — TIM All-Scores Candidate Competition Diagnosis
- `docs/results/tim_v1/2026-05-16__appearance-challenge-test.md` — Appearance Challenge Gate Test
- `docs/results/tim_v1/2026-05-16__appearance-cooldown-test.md` — Appearance Update Cooldown Test
- `docs/results/tim_v1/2026-05-16__appearance-failure-diagnosis.md` — TIM-V1 Appearance Failure Diagnosis
- `docs/results/tim_v1/2026-05-16__cooldown-correctness-result.md` — Appearance Cooldown Correctness Result
- `docs/results/tim_v1/2026-05-16__deepsort-enabled.md` — DeepSORT Enabled for Replay Matrix
- `docs/results/tim_v1/2026-05-16__eval-bag-annotation-rule.md` — Eval Bag Annotation Rule
- `docs/results/tim_v1/2026-05-16__hard-reentry-correctness-result.md` — Hard Re-entry Correctness Result - OC-SORT TIM-on
- `docs/results/tim_v1/2026-05-16__hard-reentry-final-correctness.md` — Hard Re-entry Final Correctness Result
- `docs/results/tim_v1/2026-05-16__hard-reentry-matrix-table.md` — Hard Re-entry Tracker/TIM Matrix Table
- `docs/results/tim_v1/2026-05-16__hard-reentry-tracker-matrix-summary.md` — Hard Re-entry Tracker/TIM Matrix Summary
- `docs/results/tim_v1/2026-05-16__hard-reentry-wrong-interval-diagnosis.md` — TIM Wrong-Interval Diagnosis

### 2. Correctness-first evaluation

The evaluation moved beyond valid target duration and now separates correct target duration, wrong target duration, lost/uncertain duration, pre-selection intervals, and same-person duplicate cases.

Annotation and review assets:
- `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/manual_review_notes.md`
- `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv`
- `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1_r4_cooldown/manual_review_notes.md`
- `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1_r4_cooldown/target_correctness_annotations.csv`
- `docs/annotations/tim_v1j_two_person_ambiguity/manual_review_notes.md`
- `docs/annotations/tim_v1j_two_person_ambiguity/target_correctness_annotations.csv`
- `docs/annotations/tim_v1m_appearance_critical_crossing/manual_review_notes.md`
- `docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`
- `docs/annotations/tim_v1m_appearance_critical_crossing/target_id_aliases.csv`

### 3. TIM-V2 offline policy exploration

| Policy | Main idea | Outcome |
|---|---|---|
| TIM-V2A/B/C | Hypothesis accumulation over candidate scores | Failed, reinforced drifted identity. |
| TIM-V2E | Frame-level contradiction suppression | Reduced wrong target but created too much LOST/UNCERTAIN. |
| TIM-V2F | Persistent runner-up policy | Helped one hard-reentry bag but did not generalise. |
| TIM-V2G | Additive appearance weighting | Only slight improvement. |
| TIM-V2H | Appearance-gated runner-up | Better than additive appearance but still limited. |
| TIM-V2I | Appearance-confirmed LOST reacquisition | Strong wrong suppression but too much lost target. |
| TIM-V2J | Frozen HSV template experiments | Upper-body crop improved signal, but not enough as a final policy. |
| TIM-V2K | Rank-aware appearance reacquisition | Implemented. Useful for LOST-state reacquisition. |
| TIM-V2M | Armed wrong-LOCKED suppression | Partial. Not ready for live implementation. |

TIM-V2 result files:
- `docs/results/tim_v2/2026-05-18__tim-v2-design-conclusion.md` — TIM-V2 Offline Design Conclusion
- `docs/results/tim_v2/2026-05-18__tim-v2-offline-hypothesis-negative-result.md` — TIM-V2 Offline Hypothesis Simulation: Negative Result
- `docs/results/tim_v2/2026-05-18__tim-v2e-frame-contradiction-result.md` — TIM-V2E Frame-Level Contradiction Result
- `docs/results/tim_v2/2026-05-18__tim-v2f-runner-up-policy-result.md` — TIM-V2F Persistent Runner-Up Policy Result
- `docs/results/tim_v2/2026-05-18__tim-v2f-second-pair-invalid.md` — TIM-V2F Second-Pair Validation Attempt: Invalid Pair
- `docs/results/tim_v2/2026-05-18__tim-v2f-v2g-tim-v1m-generalisation.md` — TIM-V2F/TIM-V2G Generalisation Test on TIM-V1M
- `docs/results/tim_v2/2026-05-18__tim-v2h-v2i-appearance-gating-result.md` — TIM-V2H/TIM-V2I Appearance-Gating Result
- `docs/results/tim_v2/2026-05-19__tim-v2k-corrected-tim-v1m-result.md` — TIM-V2K Corrected TIM-V1M Result
- `docs/results/tim_v2/2026-05-20__tim-v2-current-status-summary.md` — TIM-V2 Current Status Summary
- `docs/results/tim_v2/2026-05-20__tim-v2k-ros-hard-reentry-validation.md` — TIM-V2K ROS Replay Validation on Hard-Reentry Bag
- `docs/results/tim_v2/2026-05-20__tim-v2m-armed-locked-suppression-result.md` — TIM-V2M Armed Locked-Suppression Result

### 4. Corrected TIM-V1M evaluation

A major methodological issue was found: early replay extraction selected target ID 1 before the annotation’s operator-selection time. This invalidated earlier TIM-V1M final claims. Corrected extraction uses `select_delay_s=20.40`.

Corrected findings:

- The corrected score/annotation pair is valid enough for offline policy testing.
- Naive rank-0 selection is unsafe.
- The oracle result shows the bag is targetable if identity selection is solved.

### 5. ROS replay and validation infrastructure

Replay tooling was updated to avoid mixing historical topics with newly generated outputs. Target-memory-only replay was added to validate policies against frozen tracker IDs.

Launch files:
- `ros2_ws/src/thesis_bringup/launch/eval_replay.launch.py`
- `ros2_ws/src/thesis_bringup/launch/eval_replay_ambiguous.launch.py`
- `ros2_ws/src/thesis_bringup/launch/eval_replay_occluded.launch.py`
- `ros2_ws/src/thesis_bringup/launch/eval_replay_target_memory_extract.launch.py`
- `ros2_ws/src/thesis_bringup/launch/eval_target_memory_only_extract.launch.py`

Analysis tools:
- `tools/analysis/analyse_bag_timing.py`
- `tools/analysis/analyse_tim_v0_bag.py`
- `tools/analysis/analyse_tim_v1_appearance.py`
- `tools/analysis/check_live_timing_invariants.py`
- `tools/analysis/collect_live_timing_stats.py`
- `tools/analysis/collect_tim_matrix_summary.py`
- `tools/analysis/diagnose_tim_wrong_intervals.py`
- `tools/analysis/evaluate_tim_policy_timeline.py`
- `tools/analysis/evaluate_tim_target_correctness.py`
- `tools/analysis/evaluate_tim_v0_fault_injection.py`
- `tools/analysis/evaluate_tim_v0_fault_injection_batch.py`
- `tools/analysis/export_tim_v0_thesis_figures.py`
- `tools/analysis/extract_frozen_template_appearance.py`
- `tools/analysis/extract_frozen_template_appearance_upper_body.py`
- `tools/analysis/extract_tim_all_scores.py`
- `tools/analysis/merge_frozen_hsv_into_scores.py`
- `tools/analysis/simulate_tim_hypothesis_policy.py`
- `tools/analysis/simulate_tim_v2f_runner_up_policy.py`
- `tools/analysis/simulate_tim_v2h_appearance_gate_policy.py`
- `tools/analysis/simulate_tim_v2i_lost_reacquire_policy.py`
- `tools/analysis/simulate_tim_v2k_rank_aware_reacquire_policy.py`
- `tools/analysis/simulate_tim_v2m_armed_locked_suppression.py`
- `tools/analysis/simulate_tim_v2m_locked_suppression.py`
- `tools/analysis/sweep_tim_v0_fault_thresholds.py`
- `tools/analysis/sweep_tim_v1_thresholds_offline.py`

### 6. TIM-V2K implementation

TIM-V2K was implemented in the core TIM module behind a disabled-by-default configuration flag and exposed through the ROS target-memory node.

Status:

- core implementation: done
- ROS parameters: done
- unit tests: done
- replay hooks: done
- default behaviour preserved unless enabled

### 7. TIM-V2M negative result

TIM-V2M tested wrong-LOCKED suppression. It reduced wrong duration in some configurations, but no configuration met the practical target while preserving enough correct target time. It should not be implemented live in its current form.

## Key Quantitative Evidence

### `docs/results/tim_v2/2026-05-18__tim-v2-design-conclusion.md`

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |
| TIM-V2E | 0.574 | 0.247 | 0.179 |

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |
| TIM-V2F | 0.693 | 0.277 | 0.030 |

### `docs/results/tim_v2/2026-05-18__tim-v2-offline-hypothesis-negative-result.md`

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |

| Policy | Correct | Wrong | Lost | Result |
|---|---:|---:|---:|---|
| V2A naive total-score accumulation | 0.652 | 0.346 | 0.002 | worse than TIM-V1 |
| V2B anti-switch confirmation, total evidence | 0.649 | 0.332 | 0.018 | worse than TIM-V1 |
| V2C neutral evidence | 0.644 | 0.333 | 0.023 | worse than TIM-V1 |
| V2C geometry evidence | 0.644 | 0.333 | 0.023 | worse than TIM-V1 |

### `docs/results/tim_v2/2026-05-18__tim-v2e-frame-contradiction-result.md`

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |

| frame_margin | confirm_frames | Correct | Wrong | Lost |
|---:|---:|---:|---:|---:|
| 0.35 | 5 | 0.574 | 0.247 | 0.179 |

### `docs/results/tim_v2/2026-05-18__tim-v2f-runner-up-policy-result.md`

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.913 |
| correct_absent_ratio | 0.087 |
| correct_rank0_ratio | 0.656 |
| correct_rank1_ratio | 0.258 |

| Parameter | Value |
|---|---:|
| runner_min_geom | 0.40 |
| runner_max_gap | 0.35 |
| runner_confirm_frames | 15 |
| reacquire_confirm_frames | 3 |

### `docs/results/tim_v2/2026-05-18__tim-v2f-second-pair-invalid.md`

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.300 | 0.674 | 0.026 |

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.455 |
| correct_absent_ratio | 0.545 |
| correct_rank0_ratio | 0.302 |
| correct_rank1_ratio | 0.150 |
| correct_rank2plus_ratio | 0.002 |

### `docs/results/tim_v2/2026-05-18__tim-v2f-v2g-tim-v1m-generalisation.md`

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.957 |
| correct_absent_ratio | 0.043 |
| correct_rank0_ratio | 0.672 |
| correct_rank1_ratio | 0.283 |
| correct_rank2plus_ratio | 0.001 |

| Parameter | Value |
|---|---:|
| runner_min_geom | 0.40 |
| runner_max_gap | 0.35 |
| runner_confirm_frames | 15 |
| reacquire_confirm_frames | 3 |

### `docs/results/tim_v2/2026-05-18__tim-v2h-v2i-appearance-gating-result.md`

| Signal | Correct candidates | Wrong candidates |
|---|---:|---:|
| appearance_raw mean | 0.641 | 0.275 |
| appearance_raw median | 0.703 | 0.336 |
| geometry mean | 0.602 | 0.337 |
| geometry median | 0.436 | 0.334 |

| Condition | Frames |
|---|---:|
| correct_app > best_wrong_app | 288 / 844 |
| correct_geom > best_wrong_geom | 263 / 844 |

### `docs/results/tim_v2/2026-05-19__tim-v2k-corrected-tim-v1m-result.md`

| Policy | Correct | Wrong | Lost |
|---|---:|---:|---:|
| always_lost | 0.000 | 0.000 | 1.000 |
| rank0 | 0.509 | 0.431 | 0.060 |
| oracle_if_present | 0.901 | 0.000 | 0.099 |

| Parameter | Value |
|---|---:|
| lock_min_total | 0.30 |
| lock_min_geom | 0.10 |
| lost_min_total | 0.40 |
| lost_min_geom | 0.10 |
| lost_min_app | 0.05 |
| lost_app_margin | 0.03 |
| lost_confirm_frames | 1 |
| missing_ttl_frames | 8 |
| appearance_source | appearance_raw |

### `docs/results/tim_v2/2026-05-20__tim-v2-current-status-summary.md`

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.554 | 0.264 | 0.182 |

### `docs/results/tim_v2/2026-05-20__tim-v2k-ros-hard-reentry-validation.md`

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2K ROS replay | 0.656 | 0.333 | 0.012 |

Note: this result is a negative validation for hard re-entry. TIM-V2K does not solve wrong-LOCKED persistence on this bag.

| Interval | Selected | Correct |
|---|---:|---:|
| 68.092-68.759 s | 1 | 96 |
| 69.125-100.611 s | 1 | 96 -> 142 |
| 110.043-115.455 s | 142 -> 1 | 161 |

### `docs/results/tim_v2/2026-05-20__tim-v2m-armed-locked-suppression-result.md`

| Parameter | Value |
|---|---:|
| challenger_min_total | 0.50 |
| challenger_min_geom | 0.50 |
| challenger_margin_to_current | 0.45 |
| challenger_confirm_frames | 5 |
| arm_after_instability_frames | 90 |

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.550 | 0.290 | 0.160 |

## Design Files

- `docs/design/tim_v2_hypothesis_competition_plan.md` — TIM-V2 Plan - Hypothesis-Based Selected-Target Memory
- `docs/design/tim_v2k_rank_aware_reacquisition.md` — TIM-V2K: Rank-Aware Appearance Reacquisition

## Daily Logs

- `docs/Daily-Logs/T-23_2026-05-11_to_05-17/artefacts.md` — artefacts.md
- `docs/Daily-Logs/T-23_2026-05-11_to_05-17/daily/2026-05-11__tim-v1a-core-appearance.md` — Daily Log - 2026-05-11 - TIM-V1A Core Appearance Cue
- `docs/Daily-Logs/T-23_2026-05-11_to_05-17/daily/2026-05-12__tim-v1-threshold-and-annotation-followup.md` — Daily Plan - 2026-05-12 - TIM-V1 Annotation, Threshold Tuning, and Report Consolidation
- `docs/Daily-Logs/T-23_2026-05-11_to_05-17/index.md` — T-23 - 2026-05-11 to 2026-05-17
- `docs/Daily-Logs/T-23_2026-05-11_to_05-17/weekly.md` — Weekly Log - T-23 - 2026-05-11 to 2026-05-17
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-04__.md` — 2026-05-04__.md
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-05__.md` — Daily Log - 2026-05-05 - TIM-V0 Implementation, Evaluation, and Recovery Hardening
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-06__.md` — Daily Plan - 2026-05-06 - Freeze TIM-V0 and Prepare TIM-V1
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-07__.md` — Dataset bag recording mode
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-08__.md` — 2026-05-08__.md
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-09__.md` — TIM-V0 Evaluation Consolidation and TIM-V1A Preparation
- `docs/Daily-Logs/T-24_2026-05-04_to_05-10/daily/2026-05-10__.md` — 2026-05-10__.md

## Main Thesis-Level Conclusions

1. TIM should be framed as a selected-target control-validity layer, not generic MOT.
2. Wrong target duration is the key safety metric, not only valid target duration.
3. TIM-V1 improves continuity but can remain confidently wrong after hard re-entry.
4. TIM-V2K helps one specific failure class: rank-aware reacquisition after LOST/UNCERTAIN.
5. TIM-V2K does not solve wrong-LOCKED persistence.
6. TIM-V2M showed that simple wrong-LOCKED suppression is too blunt.
7. The next meaningful research step is stronger identity evidence, likely via better appearance descriptors or lightweight learned embeddings.

## Recommended Next Steps

1. Freeze TIM-V2K as the currently implemented candidate, disabled by default.
2. Do not implement TIM-V2M live yet.
3. Prepare a supervisor update summarising the two failure classes.
4. Design the next identity cue: stronger crop policy, frozen template, or 8-16D learned embedding.
5. Re-evaluate with corrected annotations and frozen tracker-ID bags only.

## Methodological Notes

- Do not compare annotations against regenerated tracker IDs unless a new annotation is created.
- Use frozen eval bags for correctness claims.
- Do not mix replayed historical `/tracks`, `/target`, or `/target_memory/status` with newly generated outputs.
- When evaluating `/target_memory/status`, treat `target_track_id` as control-valid only if state is visible and not LOST/UNCERTAIN.
- Track aliases may be needed when the tracker creates near-duplicate same-person fragments.
