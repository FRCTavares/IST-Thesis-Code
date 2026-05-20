# TIM-V2E Hard Re-entry HSV16 Descriptor Audit

Date: 2026-05-20

## Input

Bag:

- `artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

Annotations:

- `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv`

Output:

- `reports/tim_v2_embedding/hard_reentry_hsv16/summary.md`
- `reports/tim_v2_embedding/hard_reentry_hsv16/descriptor_scores.csv`

## Descriptor

The tested descriptor was `hsv16`:

- 64x128 crop
- upper/lower body split
- 8 hue bins for upper body
- 8 hue bins for lower body
- mean target memory built from clean/correct visible intervals
- image topic: `/camera/image_raw`

## Result

Global similarity:

| Role | N | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| correct | 509 | 0.995 | 0.998 | 0.999 |
| distractor | 543 | 0.949 | 0.950 | 0.976 |
| other | 508 | 0.973 | 0.975 | 0.990 |

Event-level result:

| Event | Correct mean | Distractor mean | Gap |
|---|---:|---:|---:|
| correct_tracking | 0.996 | 0.947 | +0.049 |
| recovered_target | 0.997 | 0.947 | +0.051 |
| transition_uncertain | 0.994 | 0.963 | +0.031 |
| wrong_target_interval | 0.992 | 0.954 | +0.039 |

## Interpretation

In this hard re-entry bag, hue-only HSV contains useful identity signal. During the wrong-target interval, the annotated correct target remains more similar to the clean target memory than the distractor.

However, this result does not generalise to the critical crossing bag, where HSV produced near-zero or negative separation in the most important ambiguous intervals.

## Decision

Do not use `hsv16` alone as the final TIM-V2E cue.

Use this result as evidence that appearance is relevant, but the descriptor must be stronger than hue-only HSV.

Next step:

- implement `hsv_grad16` or `hsv32_grad16` as a stronger hand descriptor baseline, then compare against the learned 16D embedding path.
