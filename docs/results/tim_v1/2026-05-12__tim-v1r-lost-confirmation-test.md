# TIM-V1R LOST Confirmation Test

## Goal

Test whether requiring the same LOST-state candidate to pass the reacquisition threshold for 3 consecutive frames improves TIM-V1 safety.

## Bag

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

## Result

| Method | accept_score_lost | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|
| TIM-V1 confirm1 | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V1 confirm1 | 0.55 | 0.603 | 0.000 | 0.397 |
| TIM-V1 confirm1 | 0.50 | 0.788 | 0.000 | 0.212 |
| TIM-V1 confirm1 | 0.45 | 0.603 | 0.170 | 0.227 |
| TIM-V1R confirm3 | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V1R confirm3 | 0.55 | 0.308 | 0.000 | 0.692 |
| TIM-V1R confirm3 | 0.50 | 0.784 | 0.000 | 0.216 |
| TIM-V1R confirm3 | 0.45 | 0.603 | 0.279 | 0.118 |

## Interpretation

The simple 3-frame LOST confirmation gate did not improve the useful operating point.

At `accept_score_lost=0.50`, the result was slightly worse:

- correct ratio: 0.788 -> 0.784
- lost ratio: 0.212 -> 0.216
- wrong ratio remained 0.000

At `accept_score_lost=0.45`, the result became less safe:

- wrong ratio: 0.170 -> 0.279

At `accept_score_lost=0.55`, the confirmation gate became too conservative and prevented the useful reacquisition.

## Decision

Do not keep this as the next TIM-V1 improvement.

The failure suggests that the distractor is persistent, not just a one-frame spike. Therefore, simple consecutive-frame confirmation is insufficient. The next improvement should compare candidates using appearance margin, second-best margin, or hypothesis evidence, not just repeated acceptance of the same best candidate.
