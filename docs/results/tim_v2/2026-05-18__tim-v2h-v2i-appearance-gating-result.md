# TIM-V2H/TIM-V2I Appearance-Gating Result

Date: 2026-05-18

## Bag

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Annotation:

`docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

All-scores source:

`reports/tim_v2_sources/tim_v1m_appearance_critical_crossing/target_memory_all_scores__tm_extract.csv`

## Appearance Signal Diagnostic

The current lightweight HSV appearance cue has useful aggregate separation:

| Signal | Correct candidates | Wrong candidates |
|---|---:|---:|
| appearance_raw mean | 0.641 | 0.275 |
| appearance_raw median | 0.703 | 0.336 |
| geometry mean | 0.602 | 0.337 |
| geometry median | 0.436 | 0.334 |

However, frame-level dominance is limited:

| Condition | Frames |
|---|---:|
| correct_app > best_wrong_app | 288 / 844 |
| correct_geom > best_wrong_geom | 263 / 844 |

This means appearance contains signal, but is not reliable enough as a simple additive score.

## Results

| Policy | Correct | Wrong | Lost | Interpretation |
|---|---:|---:|---:|---|
| TIM-V2F geometry runner-up | 0.430 | 0.299 | 0.271 | weak generalisation |
| TIM-V2G additive appearance | 0.439 | 0.284 | 0.277 | slight improvement |
| TIM-V2H appearance-gated runner-up | 0.574 | 0.171 | 0.255 | strong wrong suppression |
| TIM-V2I appearance-confirmed LOST reacquisition | 0.599 | 0.164 | 0.237 | best current result |

No TIM-V2I configuration reached the target condition:

- correct >= 0.70
- wrong <= 0.10
- lost <= 0.25

## Interpretation

Appearance works better as a gate than as an additive score. TIM-V2H and TIM-V2I substantially reduce wrong-target duration on the appearance-critical bag, but correct target availability remains too low.

The current HSV histogram appearance cue is useful but not strong enough for reliable identity recovery through hard crossings and re-entry.

## Consequence

The next TIM-V2 direction should improve the appearance cue itself, not keep increasing scalar weights.

Recommended next step:

- freeze a pre-occlusion target appearance template,
- compare re-entry candidates against that frozen template,
- avoid updating appearance memory during UNCERTAIN, LOST, and immediately after REACQUIRED,
- consider a stronger lightweight learned embedding if HSV remains insufficient.
