# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p015_positive_bootstrap_f1fbb799/candidate_f1fbb799/seq01_clean`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 55.550 | 108.750 |
| wrong duration [s] | 0.000 | 0.000 |
| lost duration [s] | 66.790 | 13.590 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 0.000 | 0.000 |
| visible target duration [s] | 122.340 | 122.340 |
| stale output duration [s] | 13.640 | 13.590 |
| correct ratio | 0.454 | 0.889 |
| wrong ratio | 0.000 | 0.000 |
| lost ratio | 0.546 | 0.111 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
