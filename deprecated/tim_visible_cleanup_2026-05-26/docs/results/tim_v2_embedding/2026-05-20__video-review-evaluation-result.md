# TIM-V2E Video Review Evaluation Result

Date: 2026-05-20

## Purpose

Evaluate TIM-V2E using manual visual-review annotations from the overlay videos/frames.

This result is separate from exact bag/timeline scoring. It is intended as qualitative, video-grounded evidence.

## Inputs

Annotations:

- `docs/annotations/tim_v2e_video_review_hard_reentry/target_correctness_annotations.csv`
- `docs/annotations/tim_v2e_video_review_critical_crossing/target_correctness_annotations.csv`

Evaluator:

- `tools/analysis/evaluate_tim_v2e_video_review_annotations.py`

Output:

- `reports/tim_v2_embedding/video_review_eval/summary.md`

## Hard re-entry result

| Metric | Raw | TIM-V2E | Delta |
|---|---:|---:|---:|
| correct_s | 83.920 | 86.680 | +2.760 |
| wrong_s | 31.870 | 20.880 | -10.990 |
| lost_s | 8.680 | 16.910 | +8.230 |

Ratios over scored visible time:

| Metric | Raw | TIM-V2E |
|---|---:|---:|
| correct_ratio | 0.674 | 0.696 |
| wrong_ratio | 0.256 | 0.168 |
| lost_ratio | 0.070 | 0.136 |

## Hard re-entry interpretation

TIM-V2E improves the safety trade in the hard re-entry video review.

It reduces visually confirmed wrong-target following by about 11.0 s and slightly increases correct target output. The cost is increased LOST time.

For UAV control, this is a favourable trade because wrong-person following is worse than LOST.

## Critical crossing result

| Metric | Raw | TIM-V2E | Delta |
|---|---:|---:|---:|
| correct_s | 14.470 | 14.470 | +0.000 |
| wrong_s | 0.000 | 0.000 | +0.000 |
| lost_s | 38.000 | 38.000 | +0.000 |

Ratios over scored visible time:

| Metric | Raw | TIM-V2E |
|---|---:|---:|
| correct_ratio | 0.276 | 0.276 |
| wrong_ratio | 0.000 | 0.000 |
| lost_ratio | 0.724 | 0.724 |

## Critical crossing interpretation

TIM-V2E does not improve the critical crossing video review.

However, the manual visual review suggests the main failure in this reviewed segment is lost target output rather than wrong-person following. This differs from the automatic timeline interpretation and should be treated carefully.

## Overall conclusion

The video review supports a narrow claim:

> In the hard re-entry scenario, the learned TIM-V2E cue improves control safety by reducing wrong-person following and converting part of it into correct reacquisition or LOST.

It does not support a broad claim of robust critical-crossing recovery.

## Decision

Do not integrate TIM-V2E live yet.

Next work should focus on:

1. improving critical-crossing continuity,
2. resolving disagreement between automatic timeline labels and visual review,
3. replacing the binary Tiny16 objective with a metric-learning objective,
4. adding more bags before making final thesis claims.
