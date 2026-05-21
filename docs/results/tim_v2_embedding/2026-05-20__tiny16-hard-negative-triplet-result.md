# TIM-V2E Tiny16 Hard-Negative Triplet Result

Date: 2026-05-20

## Purpose

Improve the first triplet embedding by replacing random/easy negatives with harder negatives from the same time window.

This is offline prototype work only. It does not modify live TIM.

## Training setup

Model:

- Tiny16 CNN embedding
- input: 64x128 RGB crop
- output: 16D L2-normalised embedding
- loss: triplet loss
- margin: 0.4

Hard-negative setting:

- negative mode: `same_time_window`
- negative time window: 1.0 s
- epochs: 40
- batch size: 64
- learning rate: 1e-3

## Embedding result

Global test separation:

| Model | correct_mean | distractor_mean | gap |
|---|---:|---:|---:|
| first triplet | 0.844 | 0.528 | +0.316 |
| hard-negative triplet | 0.833 | 0.370 | +0.462 |

Event-level comparison:

| Event | first triplet gap | hard-negative gap |
|---|---:|---:|
| reentry_id_switch | +0.489 | +0.664 |
| transition_uncertain | +0.005 | -0.058 |
| visible_but_wrong_best_candidate | +0.532 | +0.762 |
| wrong_target_interval | -0.086 | -0.057 |

## Policy simulation

### Critical crossing, threshold 0.5, candidate 0.7

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 11.979 |
| wrong_s | 27.739 | 27.739 |
| lost_s | 0.000 | 0.137 |

### Hard re-entry, threshold 0.5, candidate 0.7

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 68.449 |
| wrong_s | 35.613 | 35.613 |
| lost_s | 0.000 | 0.483 |

## Interpretation

Hard-negative triplet sampling improves descriptor separation, especially in the critical-crossing appearance comparisons.

However, the embedding is still not useful for TIM policy simulation. It does not reduce wrong-target duration and slightly damages correct time at the tested threshold.

The main failure remains the hard re-entry `wrong_target_interval`, where the learned similarity still favours the distractor over the correct target.

## Decision

Do not integrate the triplet model into TIM.

For now:

- binary Tiny16 remains the strongest operational prototype but has overfitting risk,
- triplet Tiny16 is more thesis-aligned but not policy-useful yet,
- the next training direction should be hybrid classification + metric loss or supervised contrastive learning with harder same-frame negatives.
