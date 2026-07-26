# P1.5 corrective correctness comparison

- Baseline: `055984a3867b5fb1bfc22615f052bc17831e61a3`
- Candidate: `f1fbb7994766080481fe8cf3b9acac9862867c9b`
- Gate: **PASS**

| Sequence | Baseline correct | Candidate correct | Baseline wrong | Candidate wrong | Baseline lost | Candidate lost | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| may_hard_reentry | 62.513 | 62.513 | 0.100 | 0.100 | 5.087 | 5.087 | PASS |
| seq01_clean | 108.750 | 108.750 | 0.000 | 0.000 | 13.590 | 13.590 | PASS |
| seq03_crossing | 73.892 | 73.892 | 6.053 | 6.053 | 15.782 | 15.782 | PASS |
| seq04_occlusion | 39.593 | 39.593 | 0.000 | 0.000 | 17.229 | 17.229 | PASS |
