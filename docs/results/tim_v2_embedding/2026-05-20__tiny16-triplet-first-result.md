# TIM-V2E Tiny16 Triplet First Result

Date: 2026-05-20

## Purpose

Test a metric-learning version of Tiny16 to reduce reliance on the binary correct-vs-distractor classifier.

This is offline prototype work only. It does not modify live TIM.

## Model

- input: 64x128 RGB crop
- output: 16D L2-normalised embedding
- objective: triplet loss
- margin: 0.4
- epochs: 30
- batch size: 64
- CPU-only training

Triplets:

- anchor: selected-target crop
- positive: another selected-target crop
- negative: distractor crop, preferably same event when available

## Dataset

Dataset roots:

- `datasets/tim_embedding_filtered/critical_crossing_relaxed`
- `datasets/tim_embedding_filtered/hard_reentry`

Train/test:

- train samples: 1441
- test samples: 713
- memory correct samples: 715

## Embedding separation result

Global test separation:

| correct_N | distractor_N | correct_mean | distractor_mean | gap |
|---:|---:|---:|---:|---:|
| 351 | 362 | 0.844 | 0.528 | +0.316 |

Event-level separation:

| Event | correct_mean | distractor_mean | gap |
|---|---:|---:|---:|
| reentry_id_switch | 0.774 | 0.286 | +0.489 |
| transition_uncertain | 0.875 | 0.869 | +0.005 |
| visible_but_wrong_best_candidate | 0.871 | 0.339 | +0.532 |
| wrong_target_interval | 0.809 | 0.895 | -0.086 |

## Policy simulation result

Using source-filtered triplet similarities.

### Threshold 0.0 / candidate 0.3

Critical crossing:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.116 |
| wrong_s | 27.739 | 27.739 |
| lost_s | 0.000 | 0.000 |

Hard re-entry:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 68.932 |
| wrong_s | 35.613 | 35.613 |
| lost_s | 0.000 | 0.000 |

### Threshold 0.5 / candidate 0.7

Critical crossing:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.116 |
| wrong_s | 27.739 | 27.739 |
| lost_s | 0.000 | 0.000 |

Hard re-entry:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 68.449 |
| wrong_s | 35.613 | 35.613 |
| lost_s | 0.000 | 0.483 |

## Interpretation

The first triplet model is more thesis-aligned than the binary classifier, but it is not operationally useful yet.

It improves over hand-crafted descriptors on some critical-crossing appearance comparisons, especially `visible_but_wrong_best_candidate`, but it fails the hard re-entry `wrong_target_interval`.

The policy simulations show no useful improvement. With stricter thresholds, the model slightly damages correct time in hard re-entry without reducing wrong time.

## Decision

Do not replace the binary Tiny16 model with this first triplet model.

Next step:

- add hard-negative triplet sampling,
- prefer negatives from the same frame/event/time window,
- focus training on annotated dangerous intervals,
- then rerun policy simulation.
