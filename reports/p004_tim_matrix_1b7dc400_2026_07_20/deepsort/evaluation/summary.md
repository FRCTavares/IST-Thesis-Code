# TIM Target Correctness Summary

- Bag: `bags/replay/p004_tim_matrix_1b7dc400_2026_07_20/deepsort`
- Annotations: `docs/data/annotations/may_hard_reentry/deepsort_f17cdf80_autonomous.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 24.828 | 51.212 |
| wrong duration [s] | 0.100 | 15.303 |
| lost duration [s] | 42.937 | 1.350 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 67.865 | 67.865 |
| correct ratio | 0.366 | 0.755 |
| wrong ratio | 0.001 | 0.225 |
| lost ratio | 0.633 | 0.020 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
