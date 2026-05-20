# TIM-V2E Tiny16 Similarity CSV Export

Date: 2026-05-20

## Purpose

Export per-sample learned embedding similarity scores so the Tiny16 cue can be analysed and later used by offline TIM-V2E policy simulations.

## Input

Datasets:

- `datasets/tim_embedding_filtered/critical_crossing_relaxed`
- `datasets/tim_embedding_filtered/hard_reentry`

Training output:

- `reports/tim_v2_embedding/tiny16_train_memory_eval_csv/summary.md`
- `reports/tim_v2_embedding/tiny16_train_memory_eval_csv/test_similarity_scores.csv`

## Method

The Tiny16 model was trained on train-split crops.

The selected-target memory vector was computed from train-split correct target embeddings only.

Each test crop was scored by cosine similarity to that train-memory vector.

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

## Interpretation

The learned Tiny16 cue produces strong separation on the current prototype test set, including the critical crossing intervals where HSV16 and HSV-GRAD16 failed.

This remains prototype evidence because the model is trained on two bags with a binary correct-vs-distractor objective. It should not yet be treated as a final thesis result.

## Next step

Use `test_similarity_scores.csv` to test a TIM-V2E offline policy:

- suppress control when the selected LOCKED track has low similarity,
- prefer candidate reacquisition when similarity is high,
- compare wrong/correct/lost duration against TIM-V2K and HSV baselines.
