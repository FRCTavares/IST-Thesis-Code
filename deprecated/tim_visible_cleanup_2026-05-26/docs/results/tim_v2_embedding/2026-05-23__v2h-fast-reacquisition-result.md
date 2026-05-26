# TIM-V2H Fast Reacquisition Result

Date: 2026-05-23  
Scope: offline comparison of TIM-V2E confirmation settings on the two current standard scenarios.

## Purpose

The previous best TIM-V2E configuration reduced wrong-target following using learned appearance similarity and a runtime margin gate. However, inspection of V2E LOST intervals showed that many LOST frames already contained the correct candidate with high embedding similarity.

This suggested that V2E was too slow to reacquire after suppressing the raw selected ID.

The hypothesis tested here is:

> Reducing the reacquisition confirmation requirement can reduce LOST time without increasing wrong-target time.

## Policy variants

All variants use the same base policy:

- TIM-V2E learned appearance suppression
- runtime top-2 margin gate
- margin gate threshold: 0.10
- selected similarity threshold: 0.0
- candidate high similarity threshold: 0.30
- max similarity time delta: 0.10 s
- similarity file: `reports/tim_v2_embedding/tiny16_hybrid_ce_tri025_tw1s/all_similarity_scores.csv`

Only the reacquisition confirmation count changes:

| Variant | reacquire_confirm_frames |
|---|---:|
| V2E c3 | 3 |
| V2H c2 | 2 |
| V2H c1 | 1 |

## Results

### Hard re-entry

| Method | correct_s | wrong_s | lost_s | suppressed_s | reacquired_s |
|---|---:|---:|---:|---:|---:|
| V2E c3 | 72.553 | 16.901 | 15.090 | 15.090 | 4.708 |
| V2H c2 | 75.692 | 16.901 | 11.951 | 11.951 | 7.847 |
| V2H c1 | 80.762 | 16.901 | 6.881 | 6.881 | 12.917 |

### Critical crossing

| Method | correct_s | wrong_s | lost_s | suppressed_s | reacquired_s |
|---|---:|---:|---:|---:|---:|
| V2E c3 | 29.971 | 0.046 | 9.839 | 12.435 | 18.857 |
| V2H c2 | 31.019 | 0.046 | 8.791 | 11.387 | 19.905 |
| V2H c1 | 32.340 | 0.046 | 7.470 | 10.066 | 21.226 |

## Interpretation

The one-frame confirmation setting improved both standard scenarios.

Compared with V2E c3:

- hard re-entry:
  - correct_s increased from 72.553 to 80.762
  - lost_s decreased from 15.090 to 6.881
  - wrong_s stayed unchanged at 16.901

- critical crossing:
  - correct_s increased from 29.971 to 32.340
  - lost_s decreased from 9.839 to 7.470
  - wrong_s stayed unchanged at 0.046

This supports the hypothesis that V2E was over-conservative during reacquisition. The learned similarity signal was already strong enough for earlier candidate acceptance in the evaluated cases.

## Current decision

TIM-V2H c1 is the current best offline candidate.

Current best configuration:

- runtime margin gate threshold: 0.10
- selected similarity threshold: 0.0
- candidate high similarity threshold: 0.30
- reacquire confirmation frames: 1
- max similarity time delta: 0.10 s

## Caveat

This is still an offline result on two standard scenarios. Before changing live defaults, this should be validated on additional recorded bags or a replay set with more distractors, occlusions, and target re-entry cases.
