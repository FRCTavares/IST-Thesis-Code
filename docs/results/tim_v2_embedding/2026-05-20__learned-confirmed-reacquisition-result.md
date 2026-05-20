# TIM-V2E Learned Confirmed Reacquisition Result

Date: 2026-05-20

## Purpose

Test a conservative learned-appearance policy with suppression plus confirmed reacquisition.

This is an offline simulation only. It does not modify live TIM.

## Policy

Parameters:

- selected low-similarity threshold: 0.0
- candidate high-similarity threshold: 0.3
- reacquire confirmation frames: 3
- max similarity time delta: 0.10 s

Behaviour:

1. If current selected track similarity is below threshold, suppress output to LOST.
2. If a candidate has high learned similarity for the confirmation window, reacquire it.
3. No one-frame direct switching is allowed.

## Critical crossing result

Output:

- `reports/tim_v2_embedding/v2e_learned_reacquire_critical_crossing_thr0_high03_c3/summary.md`

Global result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.799 |
| wrong_s | 27.739 | 26.737 |
| lost_s | 0.000 | 0.319 |

Policy activity:

- suppressed_s: 0.364
- suppressed_frames: 8
- reacquired_s: 0.683
- reacquired_frames: 15

Event-level result:

| Event | Raw wrong_s | Policy wrong_s | Policy lost_s | Policy correct_s |
|---|---:|---:|---:|---:|
| hard_reentry | 12.344 | 12.344 | 0.000 | 0.000 |
| late_reentry | 1.458 | 0.638 | 0.228 | 0.592 |
| reentry_id_switch | 2.551 | 2.551 | 0.000 | 0.000 |
| visible_but_wrong_best_candidate | 11.387 | 11.205 | 0.091 | 0.091 |

## Hard re-entry result

Output:

- `reports/tim_v2_embedding/v2e_learned_reacquire_hard_reentry_thr0_high03_c3/summary.md`

Global result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 75.088 |
| wrong_s | 35.613 | 19.677 |
| lost_s | 0.000 | 9.778 |

Policy activity:

- suppressed_s: 9.778
- suppressed_frames: 81
- reacquired_s: 6.157
- reacquired_frames: 51

Event-level result:

| Event | Raw wrong_s | Policy wrong_s | Policy lost_s | Policy correct_s |
|---|---:|---:|---:|---:|
| correct_tracking | 0.604 | 0.604 | 0.000 | 49.616 |
| recovered_target | 2.052 | 2.052 | 0.000 | 18.832 |
| transition_uncertain | 0.483 | 0.241 | 0.241 | 0.483 |
| wrong_target_interval | 32.474 | 16.780 | 9.537 | 6.157 |

## Interpretation

Confirmed learned reacquisition improves the hard re-entry bag significantly. It converts part of the wrong-target interval into correct target output and part into LOST.

This is a better control trade than raw TIM output.

However, the policy is still weak on the critical crossing bag. It only recovers small parts of `late_reentry` and `visible_but_wrong_best_candidate`, while leaving `hard_reentry` and `reentry_id_switch` unchanged.

## Decision

Do not integrate live yet.

Before further policy work, diagnose candidate and similarity coverage in the critical crossing bag. The key question is whether the correct candidate is actually present in `target_memory_all_scores.csv` during the failed intervals and whether a learned similarity value exists for that candidate.

If the correct candidate is absent, policy tuning cannot fix the interval.
