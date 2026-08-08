# Issue #32 Runtime/Resource Characterization -- Aggregate

## Replay algorithmic-cost pass (deterministic, non-real-time; not a live latency claim)

| Architecture | Sequence | Tracker CPU (s) | TIM CPU (s) | Combined CPU (s) | Peak RSS (KiB) | Live status |
|---|---|---:|---:|---:|---:|---|
| bytetrack_raw | dev_may_hard_reentry | 28.697 | n/a | 28.697 | 119332 | not_measured_live_this_session |
| bytetrack_tim | dev_may_hard_reentry | 28.890 | 44.609 | 73.499 | 815460 | measured |
| sort_raw | dev_may_hard_reentry | 28.215 | n/a | 28.215 | 119216 | not_measured_live_this_session |
| sort_tim | dev_may_hard_reentry | 28.764 | 45.573 | 74.336 | 762160 | not_measured_live_this_session |
| deepsort_raw | dev_may_hard_reentry | 345.645 | n/a | 345.645 | 786084 | not_measured_live_this_session |
| deepsort_tim | dev_may_hard_reentry | 344.592 | 44.025 | 388.617 | 792024 | not_measured_live_this_session |

## Comparative overhead of adding TIM-MARS (replay CPU cost only)

| Tracker | Raw CPU (s) -> TIM CPU (s) delta | Peak RSS delta (KiB) |
|---|---:|---:|
| bytetrack | +44.803 | +696128 |
| sort | +46.121 | +642944 |
| deepsort | +42.971 | +5940 |
