# 2026-05-20 — TIM-V2E Learned Appearance and Video Review

## Objective

Continue TIM-V2 after TIM-V2K and TIM-V2M by testing whether a stronger appearance cue can reduce wrong selected-target following.

The target direction was TIM-V2E:

- event-triggered learned identity evidence,
- selected-target memory, not generic MOT,
- offline/replay validation before live integration,
- preserve live defaults.

## Technical direction decision

The current evidence supports the hybrid direction:

- keep TIM-V2K for rank-aware LOST/UNCERTAIN reacquisition,
- add stronger learned identity evidence,
- use learned appearance conservatively for suppression/reacquisition,
- do not implement TIM-V2M live yet.

Reason:

- TIM-V2K helps LOST/UNCERTAIN reacquisition,
- TIM-V2M reduced wrong target in some cases but sacrificed too much correct target time,
- HSV appearance is useful but inconsistent,
- wrong target is worse than LOST for UAV control.

## Descriptor audits

Implemented:

- `tools/analysis/evaluate_tim_identity_descriptor.py`

Tested hand-crafted descriptors:

1. `hsv16`
2. `hsv_grad16`

### HSV16 result

Critical crossing:

- `visible_but_wrong_best_candidate`: gap +0.003
- `reentry_id_switch`: gap -0.191

Hard re-entry:

- `wrong_target_interval`: gap +0.039

Interpretation:

- HSV16 can help in the hard re-entry bag,
- but fails in critical crossing,
- not reliable enough as the TIM-V2E cue.

### HSV-GRAD16 result

Critical crossing:

- `visible_but_wrong_best_candidate`: gap +0.008
- `reentry_id_switch`: gap -0.055

Hard re-entry:

- `wrong_target_interval`: gap +0.019

Interpretation:

- gradient evidence improves the negative critical-crossing case slightly,
- but still fails the key ambiguous interval,
- and weakens the hard re-entry result compared with HSV16.

Decision:

- stop hand-crafted descriptor work for now,
- proceed to learned 8-16D embedding.

## Embedding dataset

Implemented:

- `tools/analysis/build_tim_embedding_dataset.py`

Generated crop datasets from exact bags, `/tracks`, and matching annotations.

Raw exports:

- `datasets/tim_embedding/critical_crossing`
  - samples: 1443
  - correct: 695
  - distractor: 719
  - other: 29
- `datasets/tim_embedding/hard_reentry`
  - samples: 1169
  - correct: 381
  - distractor: 408
  - other: 380

Added crop-quality filtering and split labels.

A strict critical-crossing filter removed all crops, so a relaxed critical-crossing export was used:

- `datasets/tim_embedding_filtered/critical_crossing_relaxed`
  - samples: 1390
  - train: 903
  - test: 487
  - correct: 685
  - distractor: 680
  - other: 25

Hard re-entry filtered:

- `datasets/tim_embedding_filtered/hard_reentry`
  - samples: 1026
  - train: 718
  - test: 308
  - correct: 381
  - distractor: 408
  - other: 237

Generated crop sheets for visual inspection.

Conclusion:

- hard re-entry crops are clean and visually separable,
- critical-crossing relaxed crops are imperfect but usable for prototype experiments,
- this is not final thesis-grade dataset evidence yet.

## Tiny16 learned embedding

Implemented:

- `tools/analysis/train_tim_embedding_tiny.py`

Model:

- input: 64x128 RGB crop,
- output: 16D L2-normalised embedding,
- small depthwise CNN,
- CPU-only prototype,
- binary correct-vs-distractor objective.

Initial corrected evaluation:

- memory vector built from train-split correct crops,
- evaluated on test split.

Result:

| Event | correct_mean | distractor_mean | gap |
|---|---:|---:|---:|
| reentry_id_switch | 0.783 | -0.989 | +1.772 |
| transition_uncertain | 0.953 | -0.965 | +1.918 |
| visible_but_wrong_best_candidate | 0.759 | -0.950 | +1.709 |
| wrong_target_interval | 0.950 | -0.767 | +1.717 |

Interpretation:

- learned identity evidence is much stronger than HSV16 or HSV-GRAD16 on the prototype crop dataset,
- but this is still prototype evidence and may overfit to clothing or bag-specific distractors.

## Similarity-source contamination issue

Discovered that combined `all_similarity_scores.csv` was unsafe because:

- frame IDs are not globally unique across bags,
- track IDs are not globally unique across bags.

Fix:

- trainer now exports `dataset_root`,
- simulator can filter with `--similarity-source-contains`.

This avoided accidental cross-bag similarity contamination.

## Learned suppression and reacquisition simulation

Implemented:

- `tools/analysis/simulate_tim_v2e_learned_suppression.py`

Policies tested:

1. suppression only,
2. suppression plus confirmed learned reacquisition.

Source-filtered result:

### Critical crossing

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.116 |
| wrong_s | 27.739 | 27.739 |
| lost_s | 0.000 | 0.000 |

Interpretation:

- source-filtered learned policy has no effect on critical crossing,
- previous apparent improvement was not reliable,
- critical crossing still requires further diagnosis/training improvement.

### Hard re-entry

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 75.088 |
| wrong_s | 35.613 | 18.350 |
| lost_s | 0.000 | 11.106 |

Interpretation:

- learned TIM-V2E improves hard re-entry,
- converts wrong following into correct reacquisition and LOST,
- this is a favourable UAV-control trade because wrong target is worse than LOST.

## Video review

Implemented:

- `tools/bag/render_tim_policy_overlay_video.py`
- `tools/bag/export_tim_policy_overlay_frames.py`
- `tools/analysis/evaluate_tim_v2e_video_review_annotations.py`

Added manual visual annotations:

- `docs/annotations/tim_v2e_video_review_hard_reentry/target_correctness_annotations.csv`
- `docs/annotations/tim_v2e_video_review_critical_crossing/target_correctness_annotations.csv`

### Hard re-entry video-review result

| Metric | Raw | TIM-V2E | Delta |
|---|---:|---:|---:|
| correct_s | 83.920 | 86.680 | +2.760 |
| wrong_s | 31.870 | 20.880 | -10.990 |
| lost_s | 8.680 | 16.910 | +8.230 |

Interpretation:

- TIM-V2E reduces visually confirmed wrong-person following,
- increases correct output slightly,
- increases LOST time,
- this is a safer control trade.

### Critical crossing video-review result

| Metric | Raw | TIM-V2E | Delta |
|---|---:|---:|---:|
| correct_s | 14.470 | 14.470 | +0.000 |
| wrong_s | 0.000 | 0.000 | +0.000 |
| lost_s | 38.000 | 38.000 | +0.000 |

Interpretation:

- TIM-V2E does not improve critical crossing,
- visual review suggests the main failure is target loss, not wrong-person following,
- this differs from earlier automatic timeline labels and must be treated carefully.

## Current conclusion

TIM-V2E learned appearance is promising but not ready for live integration.

Supported narrow claim:

> In the hard re-entry scenario, a lightweight learned identity cue reduces visually confirmed wrong-person following by converting part of it into correct reacquisition or LOST.

Unsupported claim:

> TIM-V2E robustly solves critical crossing or general selected-target identity maintenance.

## Next steps

1. Fix/check any truncated result notes.
2. Diagnose why source-filtered learned TIM-V2E has no effect on critical crossing.
3. Move Tiny16 from binary correct-vs-distractor classification toward metric learning.
4. Add more evaluation bags before making final thesis claims.
5. Do not integrate live TIM-V2E yet.
