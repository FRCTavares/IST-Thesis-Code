# TIM-V2E Critical Crossing HSV16 Descriptor Audit

Date: 2026-05-20

## Input

Bag:

- `artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Annotations:

- `docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

Aliases:

- `docs/annotations/tim_v1m_appearance_critical_crossing/target_id_aliases.csv`

Output:

- `reports/tim_v2_embedding/critical_crossing_hsv16/summary.md`
- `reports/tim_v2_embedding/critical_crossing_hsv16/descriptor_scores.csv`

## Descriptor

The tested descriptor was `hsv16`:

- 64x128 crop
- upper/lower body split
- 8 hue bins for upper body
- 8 hue bins for lower body
- mean target memory built from clean/correct visible intervals

## Result

Global similarity:

| Role | N | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| correct | 831 | 0.922 | 0.958 | 0.981 |
| distractor | 864 | 0.922 | 0.955 | 0.980 |
| other | 30 | 0.572 | 0.531 | 0.729 |

Event-level result:

| Event | Correct mean | Distractor mean | Gap |
|---|---:|---:|---:|
| clean_tracking | 0.941 | 0.911 | +0.030 |
| hard_reentry | 0.945 | 0.919 | +0.025 |
| reentry_id_switch | 0.744 | 0.935 | -0.191 |
| visible_but_wrong_best_candidate | 0.939 | 0.935 | +0.003 |

## Interpretation

Hue-only HSV has weak and inconsistent identity signal.

It gives a small positive gap during `hard_reentry`, but it fails badly during `reentry_id_switch` and gives almost no separation during `visible_but_wrong_best_candidate`.

This is not reliable enough to become the final TIM-V2E policy cue.

## Decision

Do not integrate `hsv16` into live TIM as a decision cue.

Use this result as evidence that TIM-V2E needs either:

1. a stronger hand descriptor using colour plus texture/gradient evidence, or
2. a lightweight learned 8-16D identity embedding.

This supports the learned embedding path and avoids more threshold sweeps on weak HSV evidence.
