# TIM Target Correctness Summary

- Bag: `bags/replay/p002_historical_deepsort_current_93e047b5_2026_07_19`
- Annotations: `docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 33.580 | 60.760 |
| wrong duration [s] | 2.000 | 0.000 |
| lost duration [s] | 32.120 | 6.940 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 67.700 | 67.700 |
| correct ratio | 0.496 | 0.897 |
| wrong ratio | 0.030 | 0.000 |
| lost ratio | 0.474 | 0.103 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
