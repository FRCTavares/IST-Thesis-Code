# External benchmark data contract

This directory contains tracked contracts and manifests for Issue #30.

It does not contain external dataset images or large generated outputs.

## Tracked files

- `manifest.schema.json`: schema for the frozen benchmark manifest.
- `sequence_manifest.json`: current benchmark manifest.
- future small normalized annotation or provenance files when justified.

## Local ignored storage

- `data/datasets/external/`: original downloaded datasets.
- `data/datasets/processed/`: normalized adapter outputs and caches.
- `artifacts/reports/p030_broader_sequences/`: generated evaluation reports.
- `ros2_ws/log/p030_broader_sequences/`: generated logs.

## Current status

The manifest begins as `draft_not_frozen`.

Sequence names, target identities and frame ranges must not be treated as final until the manifest status becomes `frozen`.

The freeze must occur before final benchmark evaluation and before any parameter tuning based on external outcomes.
