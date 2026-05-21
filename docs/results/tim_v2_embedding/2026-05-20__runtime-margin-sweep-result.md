# TIM-V2E Runtime Margin Sweep Result

Date: 2026-05-20

## Purpose

Test whether the runtime margin-gated TIM-V2E policy depends strongly on the chosen top-2 candidate score margin threshold.

This sweep uses the current best offline TIM-V2E configuration:

- Tiny16 hybrid embedding,
- source-filtered similarity,
- selected low-similarity threshold: 0.0,
- candidate high-similarity threshold: 0.3,
- reacquire confirmation frames: 3,
- max similarity time delta: 0.10 s,
- require similarity only when the runtime top-2 score margin is below the tested threshold.

## Sweep result

| Case | Margin | Policy correct_s | Policy wrong_s | Policy lost_s |
|---|---:|---:|---:|---:|
| critical | 0.03 | 29.561 | 0.228 | 10.066 |
| critical | 0.05 | 29.698 | 0.137 | 10.021 |
| critical | 0.10 | 29.971 | 0.046 | 9.839 |
| critical | 0.15 | 29.971 | 0.046 | 9.839 |
| critical | 0.20 | 29.971 | 0.046 | 9.839 |
| hard | 0.03 | 72.553 | 17.022 | 14.969 |
| hard | 0.05 | 72.553 | 17.022 | 14.969 |
| hard | 0.10 | 72.553 | 16.901 | 15.090 |
| hard | 0.15 | 72.553 | 16.901 | 15.090 |
| hard | 0.20 | 72.553 | 16.901 | 15.090 |

## Interpretation

The runtime margin threshold is not highly sensitive in the tested range.

For critical crossing, performance improves up to approximately 0.10 and then saturates. Wrong-target duration is almost eliminated for margins of 0.10 and above.

For hard re-entry, the margin threshold has little effect. Wrong-target duration remains around 17 s for all tested margins, meaning the limiting factor in this bag is not primarily margin-gate sensitivity.

## Decision

Use margin threshold 0.10 as the current offline operating point.

This value is defensible because:

- it nearly eliminates wrong-target output in critical crossing,
- it does not materially damage hard re-entry compared with nearby thresholds,
- it has a clear runtime interpretation as a top-2 candidate ambiguity gate.

## Next step

Replace annotation/timeline assumptions with real TIM runtime conditions:

- TIM state in UNCERTAIN, LOST, or REACQUIRED,
- low top-2 candidate score margin,
- missing or low learned similarity for the current selected target,
- confirmed high-similarity candidate for reacquisition.

Do not integrate live yet. First test this policy on more bags and measure Tiny16 CPU inference latency.
