# Thesis Documentation

This folder contains the active thesis documentation, trusted result summaries, evaluation annotations, and archived historical material.

## Folder map

- `design/` - active design notes, evaluation protocols, and tooling maps.
- `results/` - current result summaries that should be used for thesis writing, supervisor updates, and final interpretation.
- `annotations/` - trusted annotation files used by current evaluations.
- `Control-Pixhawk-MAVROS/` - current control and MAVROS integration notes.
- `Debug/` - current hardware and runtime recovery notes.
- `Daily-Logs/` - chronological engineering logs.
- `reports/` - longer written reports.
- `archive/` - superseded notes, intermediate evaluations, old annotation versions, and historical material.

## Current selected-target tracking results

Use these as the active result sources:

- `results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`
- `results/selected_target_tracking/hard_reentry_compute_throughput_summary.md`

The multi-tracker hard-reentry summary is the main source of truth for the TIM-MARS selected-target evaluation.

It supersedes earlier TIM-V2, TIM-V2Q, active-MARS, conservative-MARS, and early DeepSORT comparison notes now stored under `archive/results/`.

## Current trusted hard-reentry annotations

Use these active annotation files:

- `annotations/hard_reentry/bytetrack_tim_mars_final.csv`
- `annotations/hard_reentry/deepsort_mars_target1_final.csv`
- `annotations/hard_reentry/ocsort_tim_mars_r1.csv`

Older manual-review and intermediate annotation versions are kept under `archive/annotations/`.

## Archive policy

Move a document to `archive/` when it is useful for traceability but no longer represents the current interpretation, current workflow, or trusted evaluation input.

Do not delete historical notes unless they are generated artefacts or clearly accidental duplicates.
