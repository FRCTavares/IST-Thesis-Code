# TIM Target Correctness Summary

- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p015_positive_bootstrap_f1fbb799/candidate_f1fbb799/seq04_occlusion`
- Annotations: `/home/francisco/Desktop/Thesis-Code/docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv`
- Timebase: `header`
- Maximum output age: `0.900 s`

## Main comparison

| Metric | Raw /target | TIM-MARS /target_memory_mars |
|---|---:|---:|
| correct duration [s] | 5.993 | 39.593 |
| wrong duration [s] | 0.700 | 0.000 |
| lost duration [s] | 50.129 | 17.229 |
| target absent but output [s] | 0.000 | 0.000 |
| target not visible [s] | 8.987 | 8.987 |
| visible target duration [s] | 56.822 | 56.822 |
| stale output duration [s] | 0.000 | 0.000 |
| correct ratio | 0.105 | 0.697 |
| wrong ratio | 0.012 | 0.000 |
| lost ratio | 0.882 | 0.303 |

## Interpretation

- Higher correct ratio is good.
- Higher wrong ratio is bad.
- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.
- Valid target duration alone must not be used as the main success metric.
- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.
- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.
