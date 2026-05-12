# TIM-V1P Appearance Descriptor Test

## Goal

Test whether a refined handcrafted HSV descriptor improves TIM-V1 appearance matching.

Proposed descriptor changes:

- inner bbox crop shrink
- saturation/value masking
- reduced background contamination

## Bag

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

## Result

| Method | accept_score_lost | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|
| TIM-V0 OFF | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V0 OFF | 0.55 | 0.308 | 0.000 | 0.692 |
| TIM-V0 OFF | 0.50 | 0.603 | 0.000 | 0.397 |
| TIM-V0 OFF | 0.45 | 0.603 | 0.000 | 0.397 |
| TIM-V1 old ON | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V1 old ON | 0.55 | 0.603 | 0.000 | 0.397 |
| TIM-V1 old ON | 0.50 | 0.788 | 0.000 | 0.212 |
| TIM-V1 old ON | 0.45 | 0.603 | 0.170 | 0.227 |
| TIM-V1P new ON | 0.60 | 0.309 | 0.000 | 0.691 |
| TIM-V1P new ON | 0.55 | 0.603 | 0.000 | 0.397 |
| TIM-V1P new ON | 0.50 | 0.788 | 0.000 | 0.212 |
| TIM-V1P new ON | 0.45 | 0.603 | 0.353 | 0.044 |

## Interpretation

TIM-V1P did not improve the useful threshold setting.

At `accept_score_lost=0.50`, TIM-V1P matched old TIM-V1 exactly:

- correct ratio: 0.788
- wrong ratio: 0.000
- lost ratio: 0.212

At `accept_score_lost=0.45`, TIM-V1P made the unsafe case significantly worse:

- old TIM-V1 wrong ratio: 0.170
- TIM-V1P wrong ratio: 0.353

## Decision

Do not keep TIM-V1P as the default descriptor.

The original TIM-V1 descriptor is safer for now. Future appearance improvements should focus on better gating or reliability scoring, not simply stronger colour matching.
