# P058 lightweight-vs-integrated-tracking development evidence

Status: promoted development evidence; not held out; not complete

## Purpose

Tracked, byte-for-byte-copied artifacts backing
[`../p058_lightweight_vs_integrated_tracking_summary.md`](../p058_lightweight_vs_integrated_tracking_summary.md).
Does not rerun the experiment or alter the matrix.

## Copied artifacts

- `p058_lightweight_vs_integrated_tracking_v1.yaml` -- the frozen
  architecture-comparison manifest (6 architectures x 4 sequences,
  annotation-availability matrix, pending-annotation file list with exact
  reasons, cost-evidence join schema).
- `p058_sort_tim_calibration_v1.yaml` -- the SORT+TIM calibration manifest
  (reuses the Issue #31 dimension grid verbatim; asymmetric safety gate
  definition).
- `sort_calibration_lock.json` -- materialized-configuration lock for the
  29-cell SORT calibration sweep.
- `calibration_aggregate.{csv,json}` -- the 29-row calibration sweep
  result.
- `sort_calibration_selection.json` -- the safety-gate outcome
  (`no_safe_configuration_found`, with the closest-but-failing candidate
  attached).
- `matrix_all_cells.{csv,json}` -- the full 24-cell architecture-comparison
  matrix (11 available, 12 pending_annotation, 1
  no_safe_configuration_found).
- `SHA256SUMS` -- hashes of every file in this directory.

## Regeneration

```
tools/experiments/run_tim_tracker_calibration.py --run --resume
tools/analysis/aggregate_sort_calibration.py
tools/analysis/aggregate_lightweight_vs_integrated_report.py
```

Historical generated files, replay bags, the canonical YAML, and the
existing (now-flagged-stale) June DeepSORT annotation CSVs were not edited
or moved.
