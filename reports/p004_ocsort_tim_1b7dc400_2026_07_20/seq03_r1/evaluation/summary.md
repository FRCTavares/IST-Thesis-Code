# TIM Target Correctness Summary

- Bag: `bags/replay/p004_ocsort_tim_1b7dc400_2026_07_20/seq03_r1`
- Annotations: `docs/data/annotations/june_hard_sequences/seq03_ocsort_305578f3.csv`
- Timebase: `header`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 32.554 | 81.385 |
| wrong duration [s] | 0.050 | 1.400 |
| lost duration [s] | 63.123 | 12.942 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 95.727 | 95.727 |
| correct ratio | 0.340 | 0.850 |
| wrong ratio | 0.001 | 0.015 |
| lost ratio | 0.659 | 0.135 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
