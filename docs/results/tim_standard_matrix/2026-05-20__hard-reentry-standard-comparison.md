# Hard Re-entry Standard TIM Comparison

Date: 2026-05-20

## Scenario

Hard re-entry / ID-switch scenario with OCSORT and selected target ID 1.

This is the first standard comparison package after TIM-V2E exploration.

## Methods compared in this package

- Raw selected tracker-ID following
- TIM-V2E offline runtime-margin candidate

TIM-V2E is not live-integrated. It is evaluated offline using the current best policy:

- Tiny16 hybrid embedding,
- runtime top-2 margin gate,
- missing/low similarity suppression,
- confirmed high-similarity reacquisition.

## Automatic scoring result

| Metric | Raw | TIM-V2E offline | Delta |
|---|---:|---:|---:|
| correct_s | 68.932 | 72.553 | +3.621 |
| wrong_s | 35.613 | 16.901 | -18.712 |
| lost_s | 0.000 | 15.090 | +15.090 |

## Manual video-review result

| Metric | Raw | TIM-V2E video review | Delta |
|---|---:|---:|---:|
| correct_s | 83.920 | 86.680 | +2.760 |
| wrong_s | 31.870 | 20.880 | -10.990 |
| lost_s | 8.680 | 16.910 | +8.230 |

## Interpretation

Both automatic scoring and manual video review show the same direction:

- wrong-person following decreases,
- correct target output increases slightly,
- LOST output increases.

This is favourable for UAV control because wrong-person following is worse than LOST.

## Visual evidence

The overlay video shows intervals where raw remains on the wrong ID while TIM-V2E reacquires the visually correct person or suppresses output.

Relevant generated file:

- `reports/tim_v2_embedding/videos/hard_reentry_raw_vs_tim_v2e_learned.mp4`

## Current claim

This scenario supports the following claim:

> TIM-V2E can improve selected-target control safety in hard re-entry / ID-switch conditions by reducing wrong-person following compared with raw selected-ID tracking.

## Limits

This is not yet a final thesis-wide claim.

Still required:

1. add TIM-V0, TIM-V1, and TIM-V2K into the same matrix,
2. evaluate more scenarios,
3. test on held-out bags,
4. convert the offline TIM-V2E policy into real runtime TIM-state gates.
