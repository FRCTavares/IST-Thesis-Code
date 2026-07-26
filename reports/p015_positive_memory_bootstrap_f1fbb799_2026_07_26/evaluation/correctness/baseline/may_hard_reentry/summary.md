# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p015_positive_bootstrap_f1fbb799/baseline_055984a3/may_hard_reentry`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 38.283 | 62.513 |
| wrong duration [s] | 7.927 | 0.100 |
| lost duration [s] | 21.490 | 5.087 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 67.700 | 67.700 |
| stale output duration [s] | 0.000 | 0.000 |
| correct ratio | 0.565 | 0.923 |
| wrong ratio | 0.117 | 0.001 |
| lost ratio | 0.317 | 0.075 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
