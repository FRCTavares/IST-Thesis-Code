# TIM-MARS Stage-1 AB-11 / AB-18 Development Ablation

Date: 7 September 2026.

This is development-only evidence. H01/H02/H03 were not captured, inspected or used, and the historical split/comparison freezes remain unchanged.

## Control neutrality

The new development-only controls were run with both controls disabled on May, Seq01, Seq03 and Seq04. Every generated semantic digest and candidate-stream digest matched the retained selected reference exactly.

## 2x2 result

| Sequence | Cell | Fresh challenge | General same-ID veto | Correct s | Correct % | Wrong s | Wrong % | LOST s | LOST % |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| may | canonical | OFF | OFF | 62.594004 | 92.233 | 0.033394 | 0.049 | 5.237512 | 7.718 |
| may | ab11 | OFF | ON | 62.594004 | 92.233 | 0.033394 | 0.049 | 5.237512 | 7.718 |
| may | ab18 | ON | OFF | 62.796330 | 92.531 | 0.033394 | 0.049 | 5.035186 | 7.419 |
| may | selected | ON | ON | 62.796330 | 92.531 | 0.033394 | 0.049 | 5.035186 | 7.419 |
| seq01 | canonical | OFF | OFF | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 |
| seq01 | ab11 | OFF | ON | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 |
| seq01 | ab18 | ON | OFF | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 |
| seq01 | selected | ON | ON | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 |
| seq03 | canonical | OFF | OFF | 25.067443 | 29.925 | 0.133349 | 0.159 | 58.566005 | 69.916 |
| seq03 | ab11 | OFF | ON | 25.067443 | 29.925 | 0.133349 | 0.159 | 58.566005 | 69.916 |
| seq03 | ab18 | ON | OFF | 24.600414 | 29.368 | 0.000000 | 0.000 | 59.166384 | 70.632 |
| seq03 | selected | ON | ON | 24.600414 | 29.368 | 0.000000 | 0.000 | 59.166384 | 70.632 |
| seq04 | canonical | OFF | OFF | 43.469300 | 59.958 | 0.000000 | 0.000 | 29.030742 | 40.042 |
| seq04 | ab11 | OFF | ON | 43.469300 | 59.958 | 0.000000 | 0.000 | 29.030742 | 40.042 |
| seq04 | ab18 | ON | OFF | 48.766241 | 67.264 | 0.000000 | 0.000 | 23.733801 | 32.736 |
| seq04 | selected | ON | ON | 48.766241 | 67.264 | 0.000000 | 0.000 | 23.733801 | 32.736 |

All cells retain zero target-absence output in the tested development sequences.

## Aggregate

| Cell | Correct s | Correct % | Wrong s | Wrong % | LOST s | LOST % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| canonical | 192.331264 | 67.406 | 0.166744 | 0.058 | 92.834259 | 32.535 |
| ab11 | 192.331264 | 67.406 | 0.166744 | 0.058 | 92.834259 | 32.535 |
| ab18 | 197.363502 | 69.170 | 0.033394 | 0.012 | 87.935370 | 30.819 |
| selected | 197.363502 | 69.170 | 0.033394 | 0.012 | 87.935370 | 30.819 |

## Mechanism attribution

- AB-11 reproduces canonical exactly on all four sequences: semantic digest, physical-v2 duration buckets and appearance workload all match.
- AB-18 reproduces the selected candidate exactly on all four sequences: semantic digest, duration buckets and appearance workload all match.
- Therefore the selected candidate's observed development delta from canonical is attributable to forced fresh same-ID appearance challenges, not to the later general same-ID committed-negative veto.
- Relative to canonical, the selected mechanism adds 5.032238 s correct authority, removes 0.133349 s wrong-person authority and removes 4.898889 s LOST/suppressed authority in aggregate.
- Seq03 remains the explicit local trade-off: fresh challenges remove 0.133349 s wrong-person authority while reducing net correct authority by 0.467029 s and increasing LOST/suppressed time by 0.600378 s.

## Classification

- **AB-11 / forced fresh challenge scheduling:** useful and essential to the selected development delta, with a context-specific availability cost on Seq03.
- **AB-18 / later general same-ID negative veto:** redundant on the four permitted development sequences. This does not classify hard-negative memory itself as redundant because the earlier challenger-specific negative path remains active.

Exact per-cell semantic digests, candidate-stream digests, physical reference hashes, resolved control provenance, commands and workload counters are retained in the companion JSON.
