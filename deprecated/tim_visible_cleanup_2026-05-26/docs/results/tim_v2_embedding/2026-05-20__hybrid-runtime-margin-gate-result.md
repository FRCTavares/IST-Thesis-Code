# TIM-V2E Hybrid Runtime Margin-Gate Result

Date: 2026-05-20

## Purpose

Test whether the best annotation-event policy can be approximated using runtime-available signals.

The previous best policy required similarity only in annotated dangerous events such as `hard_reentry`, `reentry_id_switch`, and `wrong_target_interval`. Live TIM cannot know those labels.

This experiment replaces annotation-event gates with a runtime-style ambiguity gate:

- require learned similarity only when top-2 candidate score margin is below a threshold,
- suppress the current selected target if similarity is missing or below threshold,
- allow confirmed reacquisition of a high-similarity candidate.

## Policy

Embedding:

- Tiny16 hybrid model
- CE classification loss + triplet loss
- 16D L2-normalised embedding

Runtime gate:

- top-2 score margin threshold: 0.10
- selected low-similarity threshold: 0.0
- candidate high-similarity threshold: 0.3
- reacquire confirmation frames: 3
- max similarity time delta: 0.10 s

## Critical crossing result

| Metric | Raw | Policy | Delta |
|---|---:|---:|---:|
| correct_s | 12.116 | 29.971 | +17.855 |
| wrong_s | 27.739 | 0.046 | -27.693 |
| lost_s | 0.000 | 9.839 | +9.839 |

Policy activity:

- suppressed_s: 12.435
- suppressed_frames: 273
- reacquired_s: 18.857
- reacquired_frames: 414

## Hard re-entry result

| Metric | Raw | Policy | Delta |
|---|---:|---:|---:|
| correct_s | 68.932 | 72.553 | +3.621 |
| wrong_s | 35.613 | 16.901 | -18.712 |
| lost_s | 0.000 | 15.090 | +15.090 |

Policy activity:

- suppressed_s: 15.090
- suppressed_frames: 125
- reacquired_s: 4.708
- reacquired_frames: 39

## Interpretation

This is the strongest runtime-style TIM-V2E policy result so far.

The critical-crossing result is especially strong: wrong-target output is almost eliminated and much of it is converted into correct reacquisition.

The hard re-entry result is also improved, although not as strongly as the annotation-event-gated policy. The policy reduces wrong-target duration by about 18.7 s and increases correct duration by about 3.6 s, with the expected cost of more LOST time.

This policy is closer to a live implementation because it does not depend on manual annotation event labels.

## Decision

This becomes the current best TIM-V2E candidate policy.

Do not integrate live yet.

Next steps:

1. replace the offline margin gate with real TIM state and candidate-margin logic,
2. test on more bags,
3. measure Tiny16 CPU inference latency,
4. add a held-out evaluation before making final thesis claims.
