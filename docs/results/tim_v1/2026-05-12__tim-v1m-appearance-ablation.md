# TIM-V1M Appearance Ablation

Bag:

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Annotation:

`docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

## Result

| Method | accept_score_lost | Correct ratio | Wrong ratio | Lost ratio | Correct [s] | Wrong [s] | Lost [s] |
|---|---:|---:|---:|---:|---:|---:|---:|
| TIM-V0, appearance OFF | 0.60 | 0.308 | 0.000 | 0.692 | 15.20 | 0.00 | 34.13 |
| TIM-V0, appearance OFF | 0.55 | 0.308 | 0.000 | 0.692 | 15.20 | 0.00 | 34.13 |
| TIM-V0, appearance OFF | 0.50 | 0.603 | 0.000 | 0.397 | 29.75 | 0.00 | 19.58 |
| TIM-V0, appearance OFF | 0.45 | 0.603 | 0.000 | 0.397 | 29.75 | 0.00 | 19.58 |
| TIM-V1, appearance ON | 0.60 | 0.308 | 0.000 | 0.692 | 15.20 | 0.00 | 34.13 |
| TIM-V1, appearance ON | 0.55 | 0.603 | 0.000 | 0.397 | 29.75 | 0.00 | 19.58 |
| TIM-V1, appearance ON | 0.50 | 0.788 | 0.000 | 0.212 | 38.87 | 0.00 | 10.46 |
| TIM-V1, appearance ON | 0.45 | 0.603 | 0.170 | 0.227 | 29.75 | 8.40 | 11.18 |

## Interpretation

At `accept_score_lost=0.50`, TIM-V1 improves over TIM-V0:

- correct ratio: 0.603 -> 0.788
- lost ratio: 0.397 -> 0.212
- wrong ratio remains 0.000

At `accept_score_lost=0.45`, TIM-V1 becomes too permissive and introduces wrong-target output.

This supports the claim that appearance can improve reacquisition on the hard crossing bag, but only with an appropriate LOST-state acceptance threshold.
