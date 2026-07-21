# Issue #6 — Hard-negative structural safety evidence

- Implementation commit: `03409564f5107d6808054dac12294b004d9d4381`
- Canonical configuration SHA-256: `55332935fe859edff60bedf910f126487b5da6a8e13bbe5bb7662f2645359dbc`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Hard-negative promotion requires consecutive trusted continuity observations.
- Staged evidence expires after an unobserved update or continuity break.
- `hard_negative_max_positive_similarity=1.01` remains unchanged.

## Replay comparison

| Sequence | Correct delta [s] | Wrong delta [s] | Lost delta [s] | Gate |
|---|---:|---:|---:|---|
| may | +0.000 | +0.000 | +0.000 | PASS |
| seq01 | +0.000 | +0.000 | +0.000 | PASS |
| seq03 | +0.000 | +0.000 | +0.000 | PASS |
| seq04 | +0.000 | +0.000 | +0.000 | PASS |

## Lifecycle audit

- Status: True
- Committed insertions: 49
- Invalid insertions: 0
