# TIM Target Correctness Summary

- Bag: `bags/replay/p018_ocsort_tim_2d1ae5e9_2026_07_19/seq04_r2`
- Annotations: `docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 36.589 | 39.886 |
| wrong duration [s] | 0.100 | 0.150 |
| lost duration [s] | 20.133 | 16.786 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 9.594 | 9.594 |
| visible target duration [s] | 56.822 | 56.822 |
| correct ratio | 0.644 | 0.702 |
| wrong ratio | 0.002 | 0.003 |
| lost ratio | 0.354 | 0.295 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
