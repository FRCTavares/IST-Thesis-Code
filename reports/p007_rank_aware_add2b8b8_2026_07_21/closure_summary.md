# Issue #7 — Rank-aware bypass safety evidence

- Base commit: `164a70c64d50afa321ccd8f4550e463b60413739`
- Implementation commit: `add2b8b87963ac26ae2551762ecccfaf119a7780`
- Candidate-belief confirmation is composed when every candidate proposal is created.
- Rank-aware proposals therefore use the same enabled confirmation policies as normal proposals.
- Canonical configuration and thresholds were not changed.

## Validation

- Focused rank-aware suite: 13 passed, 1 expected xfail.
- Complete thesis_bringup non-linter suite: 166 passed, 3 deselected, 3 expected xfails.
- Deterministic runner suite: 40 passed.
- thesis_bringup build: passed.

## Four-case preservation

| Sequence | Correct delta [s] | Wrong delta [s] | Lost delta [s] | Replay semantic | Event semantic | Gate |
|---|---:|---:|---:|---|---|---|
| may | +0.000 | +0.000 | +0.000 | n/a | n/a | PASS |
| seq01 | +0.000 | +0.000 | +0.000 | n/a | n/a | PASS |
| seq03 | +0.000 | +0.000 | +0.000 | True | True | PASS |
| seq04 | +0.000 | +0.000 | +0.000 | True | True | PASS |

Seq03 and Seq04 raw event CSV hashes differ only because the candidate evaluator wrote CRLF line endings. Parsed fields, row keys, numeric values, and semantic hashes are identical.

Closure evidence is recorded under `reports/p007_rank_aware_add2b8b8_2026_07_21/`.
