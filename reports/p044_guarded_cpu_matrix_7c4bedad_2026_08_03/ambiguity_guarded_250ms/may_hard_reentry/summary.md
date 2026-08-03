# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/may_hard_reentry`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 39.383 | 62.297 |
| wrong duration [s] | 6.747 | 0.283 |
| lost duration [s] | 21.570 | 5.120 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 67.700 | 67.700 |
| stale output duration [s] | 0.720 | 0.720 |
| correct ratio | 0.582 | 0.920 |
| wrong ratio | 0.100 | 0.004 |
| lost ratio | 0.319 | 0.076 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
