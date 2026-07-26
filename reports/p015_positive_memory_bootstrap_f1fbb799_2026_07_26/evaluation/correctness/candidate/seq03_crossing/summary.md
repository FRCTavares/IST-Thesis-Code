# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p015_positive_bootstrap_f1fbb799/candidate_f1fbb799/seq03_crossing`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 12.457 | 73.892 |
| wrong duration [s] | 54.020 | 6.053 |
| lost duration [s] | 29.250 | 15.782 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 95.727 | 95.727 |
| stale output duration [s] | 0.000 | 0.000 |
| correct ratio | 0.130 | 0.772 |
| wrong ratio | 0.564 | 0.063 |
| lost ratio | 0.306 | 0.165 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
