# TIM-V2E Embedding Dataset Builder and Filtering

Date: 2026-05-20

## Purpose

Create the first labelled crop dataset for a lightweight learned TIM-V2E identity embedding.

The dataset is generated offline from exact ROS bags, `/tracks`, and matching target-correctness annotations.

## Builder

Script:

- `tools/analysis/build_tim_embedding_dataset.py`

Outputs:

- `samples.csv`
- `crops/*.png`
- `summary.md`

Generated crop datasets are ignored by git.

## Raw dataset export

Critical crossing:

- output: `datasets/tim_embedding/critical_crossing`
- samples: 1443
- correct: 695
- distractor: 719
- other: 29

Hard re-entry:

- output: `datasets/tim_embedding/hard_reentry`
- samples: 1169
- correct: 381
- distractor: 408
- other: 380

## Filtered dataset attempt

A strict filter was tested:

- minimum bbox height: 32 px
- maximum clipped fraction: 0.25
- excluded `full_occlusion`

This worked for the hard re-entry bag but removed all critical-crossing crops, because many critical-crossing boxes are strongly clipped after padding.

## Relaxed critical-crossing export

A relaxed filter was used for critical crossing:

- minimum bbox height: 32 px
- maximum clipped fraction: 0.65
- excluded `full_occlusion`

Output:

- `datasets/tim_embedding_filtered/critical_crossing_relaxed`

Result:

| Split | Count |
|---|---:|
| train | 903 |
| test | 487 |

Role counts:

| Role | Count |
|---|---:|
| correct | 685 |
| distractor | 680 |
| other | 25 |

Event counts:

| Event | Count |
|---|---:|
| clean_tracking | 441 |
| hard_reentry | 462 |
| late_reentry | 37 |
| reentry_id_switch | 81 |
| visible_but_wrong_best_candidate | 369 |

## Hard re-entry filtered export

Output:

- `datasets/tim_embedding_filtered/hard_reentry`

Result:

| Split | Count |
|---|---:|
| train | 718 |
| test | 308 |

Role counts:

| Role | Count |
|---|---:|
| correct | 381 |
| distractor | 408 |
| other | 237 |

## Visual inspection

The hard re-entry crops are clean and visually separable.

The critical-crossing relaxed crops are imperfect but usable for a first prototype. The key test cases remain difficult because some selected-target crops are partial or lower-body dominated.

## Decision

Proceed to a first learned 16D embedding experiment.

Use this dataset only as prototype evidence. Final claims still require more bags and stricter validation.
