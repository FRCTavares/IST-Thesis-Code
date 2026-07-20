# TIM Target Correctness Summary

- Bag: `bags/replay/p004_tim_matrix_1b7dc400_2026_07_20/ocsort`
- Annotations: `docs/data/annotations/may_hard_reentry/ocsort_f17cdf80_autonomous.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 33.599 | 61.830 |
| wrong duration [s] | 0.000 | 0.000 |
| lost duration [s] | 32.431 | 4.200 |
| target absent but output [s] | 0.100 | 0.300 |
| target not visible [s] | 1.885 | 1.885 |
| visible target duration [s] | 66.030 | 66.030 |
| correct ratio | 0.509 | 0.936 |
| wrong ratio | 0.000 | 0.000 |
| lost ratio | 0.491 | 0.064 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
