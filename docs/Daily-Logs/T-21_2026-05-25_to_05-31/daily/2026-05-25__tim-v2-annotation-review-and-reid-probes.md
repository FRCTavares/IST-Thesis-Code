# 2026-05-25, TIM-V2 annotation review and ReID probes

## Objective

Continue TIM-V2 evaluation on the reviewed hard-reentry case, focusing on selected-target correctness, wrong-target reduction, and appearance-based recovery after tracker ID switches.

## Main findings

1. The old hard-reentry annotation was wrong around the main crossing interval. ID 1 was labelled as a distractor too early.
2. After review, ID 1 remains the selected target until about 73.9 s, followed by a transition-uncertain interval until about 75.9 s.
3. This explained the false-negative learned similarity values seen in the previous TIM-V2H results.
4. The hard-reentry embedding dataset was rebuilt using the reviewed annotation.
5. Corrected in-dataset Tiny16 appearance improves TIM substantially.
6. Held-out Tiny16 does not generalise safely from critical-crossing to hard-reentry.
7. MARS ReID was tested using the existing DeepSORT MARS model in the repo.
8. MARS does not help when memory comes from a different target/video.
9. MARS does show useful same-run relative similarity in the 75-86 s failure window.
10. The next experiment should be TIM-V2Q, a MARS relative-margin policy.

## Corrected dataset

- Dataset: `datasets/tim_embedding_filtered_reviewed/hard_reentry`
- Crops exported: 1076
- ID 1 from 71.396-73.718 s is now labelled as correct / correct_tracking.
- ID 96 in the same interval is not labelled as the selected target.

## Corrected Tiny16 in-dataset result

- Output: `reports/tim_v2_embedding/tiny16_hybrid_reviewed_hard_ce_tri025_tw1s`
- correct mean: 0.905
- distractor mean: -0.703
- gap: 1.608
- false-negative raw-correct frames <= -0.70: 0

| Method | Correct s | Wrong s | Lost s |
|---|---:|---:|---:|
| Raw selected ID | 73.036 | 28.490 | 0.000 |
| V2H, corrected in-dataset Tiny16 | 79.434 | 17.384 | 4.708 |

Interpretation: corrected in-dataset learned appearance improves TIM, but this is not a generalisation result because hard-reentry crops were included in training.

## Held-out Tiny16 result

- Eval-only dataset: `datasets/tim_embedding_filtered_reviewed/hard_reentry_eval_only`
- Output: `reports/tim_v2_embedding/tiny16_hybrid_critical_only_eval_hard_reviewed`
- Policy output: `reports/tim_v2h_heldout_embedding/hard_reentry_c1`

| Method | Correct s | Wrong s | Lost s |
|---|---:|---:|---:|
| Raw selected ID | 73.036 | 28.490 | 0.000 |
| V2H, held-out Tiny16 | 66.759 | 29.577 | 5.191 |

Interpretation: Tiny16 does not generalise safely from critical-crossing to hard-reentry.

## MARS ReID probe

- Model: `models/reid/mars-small128.pb`
- Extractor: `MarsSmall128Extractor.encode(image, boxes)`
- New tool: `tools/analysis/extract_tim_mars_reid_similarity.py`

MARS critical-only memory result:

| Method | Correct s | Wrong s | Lost s |
|---|---:|---:|---:|
| Raw selected ID | 73.036 | 28.490 | 0.000 |
| V2H, MARS critical-only memory | 72.674 | 28.369 | 0.483 |

MARS same-run memory with threshold policy gave the same result, so absolute-threshold gating is not suitable.

Manual inspection of 75-86 s showed useful relative signal:

- ID 1, distractor: about 0.50-0.76
- ID 96, correct: about 0.89-0.94
- ID 113, later target candidate: about 0.89-0.95

## Next task

Implement TIM-V2Q as an offline MARS relative-margin policy probe.

Core rule:

```text
if candidate_sim - current_selected_sim >= margin:
    allow candidate switch or reacquisition
```
