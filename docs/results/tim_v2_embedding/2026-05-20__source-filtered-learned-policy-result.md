# TIM-V2E Source-Filtered Learned Policy Result

Date: 2026-05-20

## Purpose

Re-run the learned TIM-V2E policy after fixing a similarity-source contamination issue.

The previous `all_similarity_scores.csv` combined multiple datasets. Frame IDs and track IDs are not globally unique across bags, so the simulator could accidentally use similarity rows from the wrong dataset.

## Fix

The Tiny16 trainer now exports `dataset_root` in the similarity CSV.

The simulator now supports:

- `--similarity-source-contains critical_crossing_relaxed`
- `--similarity-source-contains hard_reentry`

This filters similarity rows to the correct dataset source.

## Critical crossing result

Source filter:

- `critical_crossing_relaxed`

Policy:

- selected low threshold: 0.0
- candidate high threshold: 0.3
- confirmation frames: 3

Result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.116 |
| wrong_s | 27.739 | 27.739 |
| lost_s | 0.000 | 0.000 |

Policy activity:

- suppressed_s: 0.000
- reacquired_s: 0.000

Interpretation:

- The source-filtered learned policy has no effect on the critical crossing bag.
- This means the previous small critical-crossing improvement was caused by mixed-source similarity contamination or by non-source-safe similarity matching.

## Hard re-entry result

Source filter:

- `hard_reentry`

Result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 75.088 |
| wrong_s | 35.613 | 18.350 |
| lost_s | 0.000 | 11.106 |

Policy activity:

- suppressed_s: 11.106
- reacquired_s: 6.157

Interpretation:

- The learned policy remains useful on the hard re-entry bag.
- It converts substantial wrong-target output into correct output and LOST.

## Decision

Do not integrate live yet.

Current conclusion:

- learned appearance helps in the hard re-entry bag,
- learned appearance does not yet solve the critical crossing bag,
- the next step is to diagnose whether critical crossing fails because of high similarity on the wrong selected track, insufficient candidate similarity availability, or overfitting from binary training.

Next technical direction:

- move from binary correct-vs-distractor classification toward metric learning,
- or add a candidate dominance policy only if correct candidates consistently score above the current wrong selected track.
