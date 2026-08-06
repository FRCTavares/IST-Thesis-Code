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

## Split-level acquisition provenance

`dataset_sources.json` schema version 2 records verified archives per split.

A dataset may therefore be:

- `not_downloaded` when no admissible split is verified;
- `partially_verified` when only some admissible splits are verified;
- `fully_verified` only when every admissible split is verified.

Each acquisition record retains the archive filename, SHA-256, byte size,
installed split path, verification date, sequence count, annotation count and
image count. Large archives and extracted images remain ignored.

The tracked verifier checks those fields against local storage without selecting
a sequence, target identity or frame range.

## Annotation-only sequence profiles

`profile_external_tracking_dataset.py` creates deterministic profiles from the
tracked source registry, local catalogue, normalized annotations and existing
candidate-selection policy.

Profiles contain sequence geometry, annotation counts, explicit exclusion
reasons and physical-target candidate facts. They do not contain tracker IDs,
TIM-MARS scores, recovery outcomes or benchmark selections.

MOT17 and DanceTrack use the official frame rate in `seqinfo.ini`. A dataset
without source timing metadata, including the installed VisDrone layout, must
receive `--frame-rate` explicitly. Such an input is labelled
`explicit_cli_unfrozen` and remains unfrozen until its provenance is resolved
and the benchmark manifest is deliberately frozen.

## VisDrone timing provenance

The official VisDrone FAQ states that the original videos were captured at
24 FPS and that only part of their frames was extracted for annotation.

These are separate facts:

- `original_capture_frame_rate_hz` is `24.0`;
- `exported_sequence_frame_rate_hz` remains unavailable;
- adjacent exported images are not assumed to be consecutive original-video
  frames;
- exported-frame indices therefore do not define authoritative physical time.

An explicit profiler `--frame-rate` remains an unfrozen deterministic analysis
or replay input. For VisDrone it must not be described as source metadata,
exported cadence or physical timestamp evidence. Sequence selection remains
frame-index-only until exported cadence is authoritatively resolved.

## Verified DanceTrack validation acquisition

The official DanceTrack validation archive is installed locally for
non-commercial research evaluation.

Verified acquisition facts:

- split: `val`;
- archive: `val.zip`;
- archive size: `4,209,785,614` bytes;
- archive SHA-256:
  `90ba30973761ce0b81a9654c11086d87537392475ac8bc666d842e645641277c`;
- installed sequences: 25;
- ground-truth files: 25;
- source images: 25,508;
- source frame rate: 20 FPS from each sequence's `seqinfo.ini`;
- verification date: 6 August 2026.

The DanceTrack training split remains absent. Therefore, the dataset
acquisition status is `partially_verified`, not `fully_verified`.

The acquisition does not select a benchmark sequence, physical identity,
initialization window or frame range. It does not modify the benchmark
manifest or inspect tracker and TIM-MARS outcomes.
