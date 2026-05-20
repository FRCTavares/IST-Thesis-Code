# TIM-V2E HSV-GRAD16 Descriptor Audit

Date: 2026-05-20

## Purpose

Evaluate whether adding a simple gradient-orientation component to the HSV descriptor improves selected-target identity separation in the two current TIM-V2E evaluation bags.

The tested descriptor was `hsv_grad16`:

- 64x128 crop
- 8D colour descriptor from upper/lower hue histograms
- 8D gradient orientation descriptor from Sobel magnitude-weighted orientation histogram
- L2 normalised descriptor
- memory built from clean/correct visible intervals

## Critical crossing result

Output:

- `reports/tim_v2_embedding/critical_crossing_hsv_grad16/summary.md`
- `reports/tim_v2_embedding/critical_crossing_hsv_grad16/descriptor_scores.csv`

Global similarity:

| Role | N | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| correct | 831 | 0.963 | 0.976 | 0.989 |
| distractor | 864 | 0.945 | 0.960 | 0.988 |
| other | 30 | 0.810 | 0.798 | 0.866 |

Event-level result:

| Event | Correct mean | Distractor mean | Gap |
|---|---:|---:|---:|
| clean_tracking | 0.970 | 0.940 | +0.030 |
| hard_reentry | 0.976 | 0.936 | +0.040 |
| reentry_id_switch | 0.905 | 0.959 | -0.055 |
| visible_but_wrong_best_candidate | 0.965 | 0.956 | +0.008 |

## Hard re-entry result

Output:

- `reports/tim_v2_embedding/hard_reentry_hsv_grad16/summary.md`
- `reports/tim_v2_embedding/hard_reentry_hsv_grad16/descriptor_scores.csv`

Global similarity:

| Role | N | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| correct | 509 | 0.992 | 0.994 | 0.998 |
| distractor | 543 | 0.966 | 0.968 | 0.983 |
| other | 508 | 0.920 | 0.920 | 0.953 |

Event-level result:

| Event | Correct mean | Distractor mean | Gap |
|---|---:|---:|---:|
| correct_tracking | 0.993 | 0.966 | +0.027 |
| recovered_target | 0.995 | 0.962 | +0.032 |
| transition_uncertain | 0.993 | 0.975 | +0.018 |
| wrong_target_interval | 0.987 | 0.968 | +0.019 |

## Comparison with HSV16

Critical crossing:

| Event | HSV16 gap | HSV-GRAD16 gap | Interpretation |
|---|---:|---:|---|
| hard_reentry | +0.025 | +0.040 | improved |
| reentry_id_switch | -0.191 | -0.055 | improved but still wrong |
| visible_but_wrong_best_candidate | +0.003 | +0.008 | still near zero |

Hard re-entry:

| Event | HSV16 gap | HSV-GRAD16 gap | Interpretation |
|---|---:|---:|---|
| wrong_target_interval | +0.039 | +0.019 | worse |

## Interpretation

Adding a coarse gradient descriptor improves some critical-crossing separation, especially reducing the negative gap in `reentry_id_switch`.

However, it still fails the key ambiguous interval:

- `visible_but_wrong_best_candidate`: gap only +0.008

It also weakens the hard re-entry result compared with hue-only HSV.

## Decision

Do not integrate `hsv_grad16` into TIM.

The hand-crafted descriptor path is not strong enough. The next technical step should be a lightweight learned 8-16D embedding, evaluated offline before live integration.

This result strengthens the argument that TIM-V2E needs learned identity evidence rather than more threshold tuning on hand-crafted colour/gradient cues.

Hard re-entry:

| Event | HSV16 gap | HSV-GRAD16 gap | Interpretation |
|---|---:|---:|---|
| wrong_target_interval | +0.039 | +0.019 | worse |

## Interpretation

Adding a coarse gradient descriptor improves some critical-crossing separation, especially reducing the negative gap in `reentry_id_switch`.

However, it still fails the key ambiguous interval:

- `visible_but_wrong_best_candidate`: gap only +0.008

It also weakens the hard re-entry result compared with hue-only HSV.

## Decision

Do not integrate `hsv_grad16` into TIM.

The hand-crafted descriptor path is not strong enough. The next technical step should be a lightweight learned 8-16D embedding, evaluated offline before live integration.

This result strengthens the argument that TIM-V2E needs learned identity evidence rather than more threshold tuning on hand-crafted colour/gradient cues.
