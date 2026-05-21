# TIM-V2E Hybrid Event-Gated Policy Result

Date: 2026-05-20

## Purpose

Evaluate the best current TIM-V2E policy candidate:

- Tiny16 hybrid embedding,
- classification + triplet training,
- source-filtered similarity,
- confirmed learned reacquisition,
- event-gated require-similarity.

This is offline simulation only. It does not modify live TIM.

## Policy

Embedding:

- Tiny16 hybrid model,
- CE classification loss + triplet loss,
- 16D L2-normalised embedding,
- trained on filtered crop datasets.

Policy:

- selected low-similarity threshold: 0.0
- candidate high-similarity threshold: 0.3
- reacquire confirmation frames: 3
- max similarity time delta: 0.10 s
- require similarity only in dangerous/re-entry events

Critical crossing require-similarity events:

- `hard_reentry`
- `late_reentry`
- `reentry_id_switch`
- `visible_but_wrong_best_candidate`

Hard re-entry require-similarity events:

- `wrong_target_interval`
- `transition_uncertain`

## Critical crossing result

Output:

- `reports/tim_v2_embedding/v2e_hybrid_critical_crossing_require_sim_gated_thr0_high03_c3/summary.md`

Global result:

| Metric | Raw | Policy | Delta |
|---|---:|---:|---:|
| correct_s | 12.116 | 30.882 | +18.766 |
| wrong_s | 27.739 | 0.000 | -27.739 |
| lost_s | 0.000 | 8.973 | +8.973 |

Policy activity:

- suppressed_s: 8.973
- suppressed_frames: 197
- reacquired_s: 18.857
- reacquired_frames: 414

Event-level result:

| Event | Raw wrong_s | Policy correct_s | Policy wrong_s | Policy lost_s |
|---|---:|---:|---:|---:|
| hard_reentry | 12.344 | 11.387 | 0.000 | 0.957 |
| late_reentry | 1.458 | 0.319 | 0.000 | 1.139 |
| reentry_id_switch | 2.551 | 2.004 | 0.000 | 0.547 |
| visible_but_wrong_best_candidate | 11.387 | 5.147 | 0.000 | 6.240 |

## Hard re-entry result

Output:

- `reports/tim_v2_embedding/v2e_hybrid_hard_reentry_require_sim_gated_thr0_high03_c3/summary.md`

Global result:

| Metric | Raw | Policy | Delta |
|---|---:|---:|---:|
| correct_s | 68.932 | 72.674 | +3.742 |
| wrong_s | 35.613 | 2.052 | -33.561 |
| lost_s | 0.000 | 29.818 | +29.818 |

Policy activity:

- suppressed_s: 29.818
- suppressed_frames: 247
- reacquired_s: 4.708
- reacquired_frames: 39

Event-level result:

| Event | Raw wrong_s | Policy correct_s | Policy wrong_s | Policy lost_s |
|---|---:|---:|---:|---:|
| correct_tracking | 0.604 | 49.254 | 0.362 | 0.604 |
| recovered_target | 2.052 | 18.470 | 0.966 | 1.449 |
| transition_uncertain | 0.483 | 0.241 | 0.000 | 0.724 |
| wrong_target_interval | 32.474 | 4.708 | 0.724 | 27.041 |

## Interpretation

This is the best TIM-V2E offline policy result so far.

The key policy insight is that appearance should not be required globally. Requiring similarity everywhere damages normal tracking. Instead, appearance should be required only in unstable/re-entry/ambiguous intervals.

The event-gated policy removes almost all wrong target output in both evaluated bags.

The cost is increased LOST time, especially in hard re-entry. For UAV control, this is acceptable in principle because wrong-person following is worse than LOST.

## Decision

This is the current best TIM-V2E candidate for further development.

Do not integrate live yet.

Next steps:

1. translate event-gated logic from annotation-event simulation into real TIM state gates,
2. use TIM states and score ambiguity instead of annotation event labels,
3. test on held-out bags,
4. verify latency cost of Tiny16 CPU inference,
5. only then consider live optional enablement.
