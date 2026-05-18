# TIM-V2F Second-Pair Validation Attempt: Invalid Pair

Date: 2026-05-18

## Tested Pair

Scores:

`reports/tim_v0/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1__r2/target_memory_all_scores.csv`

Annotations:

`docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1_r4_cooldown/target_correctness_annotations.csv`

## TIM-V2F Result

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.300 | 0.674 | 0.026 |

## Oracle Candidate-Presence Analysis

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.455 |
| correct_absent_ratio | 0.545 |
| correct_rank0_ratio | 0.302 |
| correct_rank1_ratio | 0.150 |
| correct_rank2plus_ratio | 0.002 |

## Interpretation

This is not a valid validation pair for TIM-V2F.

The annotated correct target ID is absent from the candidate score file in 54.5% of evaluated frames. Therefore, no offline association policy can select the annotated target for most of the interval.

The likely cause is a mismatch between the annotation file and the score file, or a replay where tracker IDs differ from the annotated eval bag.

## Consequence

Do not use this pair to judge TIM-V2F.

A valid second-bag test requires:

1. target correctness annotations from the exact same eval bag,
2. `target_memory_all_scores.csv` generated from that exact same eval bag,
3. oracle candidate presence high enough to make target selection possible.
