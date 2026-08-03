# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/seq04_occlusion`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 36.343 | 37.693 |
| wrong duration [s] | 0.000 | 0.000 |
| lost duration [s] | 20.479 | 19.129 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 9.594 | 9.594 |
| visible target duration [s] | 56.822 | 56.822 |
| stale output duration [s] | 0.000 | 0.000 |
| correct ratio | 0.640 | 0.663 |
| wrong ratio | 0.000 | 0.000 |
| lost ratio | 0.360 | 0.337 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
