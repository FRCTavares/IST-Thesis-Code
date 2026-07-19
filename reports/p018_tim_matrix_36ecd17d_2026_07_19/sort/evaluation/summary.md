# TIM Target Correctness Summary

- Bag: `bags/replay/p018_tim_matrix_36ecd17d_2026_07_19/sort`
- Annotations: `docs/data/annotations/may_hard_reentry/sort_f17cdf80_autonomous.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 29.286 | 52.099 |
| wrong duration [s] | 0.000 | 5.300 |
| lost duration [s] | 37.032 | 8.919 |
| target absent but output [s] | 0.150 | 0.300 |
| target not visible [s] | 1.547 | 1.547 |
| visible target duration [s] | 66.318 | 66.318 |
| correct ratio | 0.442 | 0.786 |
| wrong ratio | 0.000 | 0.080 |
| lost ratio | 0.558 | 0.134 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
