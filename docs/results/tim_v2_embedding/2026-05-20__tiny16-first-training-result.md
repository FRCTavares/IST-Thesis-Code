# TIM-V2E Tiny16 First Training Result

Date: 2026-05-20

## Purpose

Train the first lightweight learned identity cue for TIM-V2E using the exported crop dataset.

This is an offline prototype only. It does not modify live TIM.

## Dataset

Dataset roots:

- `datasets/tim_embedding_filtered/critical_crossing_relaxed`
- `datasets/tim_embedding_filtered/hard_reentry`

Training samples:

- train: 1441
- test: 713
- memory correct samples: 715

The memory descriptor was built only from train-split correct target crops, then evaluated on test-split ambiguous/re-entry crops.

## Model

Tiny CNN:

- input: 64x128 RGB crop
- output: 16D L2-normalised embedding
- CPU-only prototype
- supervised binary training objective: correct target vs distractor

Training:

- epochs: 20
- batch size: 64
- learning rate: 1e-3

## Result

Global test separation:

| correct_N | distractor_N | correct_mean | distractor_mean | gap |
|---:|---:|---:|---:|---:|
| 351 | 362 | 0.836 | -0.893 | +1.729 |

Event-level test separation:

| Event | correct_N | distractor_N | correct_mean | distractor_mean | gap |
|---|---:|---:|---:|---:|---:|
| reentry_id_switch | 39 | 42 | 0.783 | -0.989 | +1.772 |
| transition_uncertain | 6 | 6 | 0.953 | -0.965 | +1.918 |
| visible_but_wrong_best_candidate | 175 | 193 | 0.759 | -0.950 | +1.709 |
| wrong_target_interval | 97 | 121 | 0.950 | -0.767 | +1.717 |

## Comparison against hand-crafted descriptors

The learned 16D prototype strongly outperforms the hand-crafted descriptors on the key critical-crossing failure interval.

For `visible_but_wrong_best_candidate`:

| Descriptor | Gap |
|---|---:|
| HSV16 | +0.003 |
| HSV-GRAD16 | +0.008 |
| Tiny16 learned embedding | +1.709 |

For `reentry_id_switch`:

| Descriptor | Gap |
|---|---:|
| HSV16 | -0.191 |
| HSV-GRAD16 | -0.055 |
| Tiny16 learned embedding | +1.772 |

## Interpretation

This is the first strong evidence that learned identity evidence can solve cases where colour/gradient descriptors fail.

However, this is still prototype evidence. The current model is trained with a binary correct-vs-distractor objective on two bags, so it may overfit to specific clothing or scenario appearance.

## Decision

Continue the learned embedding path.

Next step:

- replace or supplement binary classification with a metric-learning objective,
- export train/test similarity CSVs,
- compare learned embedding directly inside the same audit framework used for HSV16 and HSV-GRAD16,
- only then consider TIM integration.
