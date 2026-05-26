# Hard re-entry annotation review

Date: 2026-05-25

## Reason for review

The original hard re-entry annotation was found to mark the selected target ID switch too early.

The previous annotation treated the interval beginning around 68 s as a wrong-target interval with the selected person assigned to ID 96. Manual review of the ID-review video showed that the selected person remains ID 1 until approximately 75.9 s. Therefore, the original annotation overestimated raw wrong-target duration and overestimated TIM improvement in this scenario.

## Annotation correction

The hard re-entry annotation was rewritten as clean ground-truth identity intervals.

Short detector, tracker, renderer, raw-output, and TIM-output flickers were not encoded as separate ground-truth intervals. The annotation describes the true selected-person identity and visibility, not the system behaviour.

Main corrected identity sequence:

| Interval | Ground truth |
|---|---|
| 0.0-5.8 s | target visible, no selected target yet |
| 5.8-54.4 s | selected person is ID 1 |
| 54.4-55.1 s | crossing / uncertain selected-person detection |
| 55.1-73.9 s | selected person remains ID 1 |
| 73.9-75.9 s | crossing / uncertain identity |
| 75.9-86.0 s | selected person becomes ID 96 |
| 86.0-87.8 s | target not reliably visible |
| 87.8-105.1 s | selected person is ID 113 |
| 105.1-106.4 s | target not reliably visible |
| 106.4-110.4 s | selected person is ID 142 |
| 110.4-116.5 s | selected person remains ID 142, but tracking behaviour is unstable |
| 116.5-136.8 s | selected person is ID 161 |

## Impact on TIM-V2H hard re-entry result

### Previous result

| Metric | Raw | TIM-V2H |
|---|---:|---:|
| correct_s | 68.932 | 80.762 |
| wrong_s | 35.613 | 16.901 |
| lost_s | 0.000 | 6.881 |

### Reviewed annotation result

| Metric | Raw | TIM-V2H |
|---|---:|---:|
| correct_s | 73.036 | 75.451 |
| wrong_s | 28.490 | 19.557 |
| lost_s | 0.000 | 6.519 |

## Interpretation

After annotation review, TIM-V2H still reduces wrong-target following in the hard re-entry scenario, but the improvement is smaller than previously reported.

The corrected result is:

- correct target duration increases by 2.415 s
- wrong-target duration decreases by 8.933 s
- lost duration increases by 6.519 s

This is a more conservative and more reliable result.

## Methodological note

The reviewed annotation supports the current evaluation principle:

> The annotation defines the selected person's true identity and visibility. It must not encode raw tracker flicker, TIM suppression, or renderer overlay flicker as ground truth.

Those behaviours are measured by the evaluator, not manually inserted into the annotation.
