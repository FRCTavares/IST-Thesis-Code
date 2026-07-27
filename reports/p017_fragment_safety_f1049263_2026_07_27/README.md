# P1.6 target-fragment hard-negative safety evidence

## Scope

This package validates the Issue #17 protection that prevents duplicate target fragments from entering hard-negative memory.

## Final configuration

- Final commit: `f10492637163e2b25cd72155deffd8c12d5fb69d`
- Canonical positive-similarity exclusion threshold: `0.95`
- Safety tolerance: `0.05 s`
- Frozen development sequences: May hard re-entry, Seq01 clean, Seq03 crossing, and Seq04 occlusion.

## Validation result

The canonical deterministic `0.95–1.01` sweep passed all annotated-ID, spatial, and absent-output safety gates. Threshold `0.95` was retained because it is the lowest tested safe value and therefore provides the strongest tested fragment exclusion.

A second deterministic `0.95` pass reproduced the exact generated semantic digest, topic counts, runtime contract, annotated-ID metrics, and spatial metrics on all four sequences.

## Threshold 0.95 comparison

| Sequence | Correct Δ [s] | Wrong Δ [s] | Lost Δ [s] | Spatial wrong Δ [s] | Gate |
|---|---:|---:|---:|---:|---|
| may_hard_reentry | +0.000 | +0.000 | +0.000 | +0.000 | PASS |
| seq01_clean | +0.000 | +0.000 | +0.000 | +0.000 | PASS |
| seq03_crossing | +79.398 | -78.905 | -0.493 | -0.013 | PASS |
| seq04_occlusion | +3.800 | -4.000 | +0.200 | +0.000 | PASS |

## Regression and build validation

- Related Issue #17 tests: `95 passed`.
- Focused post-build regressions: `31 passed`.
- `thesis_bringup` package build: passed.

## Evidence inventory

- `canonical_manifest.tsv`: frozen source and annotation contract.
- `threshold_summary.tsv`: threshold-level gate results.
- `threshold_matrix.tsv`: per-sequence predecessor comparison.
- `repeatability.tsv`: exact deterministic repeatability result.
- `metrics/`: predecessor and final candidate evaluator summaries.
- `validation/`: test and build logs.
- `provenance.txt`: implementation, configuration, model, and runner hashes.
- `checksums.sha256`: package file checksums.

The safety priority remains: a lost target is preferable to a wrong target.
