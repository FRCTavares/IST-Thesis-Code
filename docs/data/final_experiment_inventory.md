# Final Experiment Inventory

## Naming note

Several final evidence folders keep their historical `paper_final_*` names because they were generated for the submitted ROBOT2026 paper. These names are frozen for traceability; they should not be used as the naming pattern for new thesis reruns.

## Final autonomous selected-target replay bags

- `bags/replay/paper_final_tim_results_2026_07_03/`
- DeepSORT May memory replay bag: deleted during the 9 July 2026 cleanup; generated reports and preserved metadata remain, but it is not part of the reproducible final bag set.
- `bags/replay/paper_final_deepsort_june_full_2026_07_04/`

## Final diagnostic replay bags

- `bags/replay/paper_final_deepsort_june_memory_2026_07_04/`
- `bags/replay/paper_final_deepsort_may_2026_07_03/`

## Final reports

- `reports/paper_final_tim_results_2026_07_03/`
- `reports/paper_final_deepsort_may_2026_07_03/`
- `reports/paper_final_deepsort_may_memory_2026_07_03/`
- `reports/paper_final_deepsort_june_full_2026_07_04/`
- `reports/paper_final_deepsort_june_memory_2026_07_04/`
- `reports/paper_final_method_comparison_2026_07_03/`
- `reports/paper_final_sequence_audit_2026_07_04/`
- `reports/paper_final_tables_2026_07_04/`

## Final annotation CSVs

- `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- `docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv`
- `docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq03_deepsort.csv`
- `docs/data/annotations/june_hard_sequences/seq04_deepsort.csv`

## Quarantine

Old, failed, or development-only artifacts were moved under `bags/review/quarantine_*`.

## Interpretation note

Annotation-driven DeepSORT reports are diagnostics, not autonomous baselines. They measure whether DeepSORT contained the correct physical target track when the correct target-ID handoff was supplied from annotations.

## Non-final annotations kept for provenance

- `docs/data/annotations/june_hard_sequences/seq02_bytetrack.csv`
- `docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv`

## Final Issue #30 / P030 broader-sequence evidence

Canonical thesis-facing summary:
`docs/results/selected_target_tracking/p030_broader_sequences_summary.md`.
Full chronological engineering record:
`docs/issues/p1-12-broader-sequences.md`.

Final retained primary scope: 4 ROS 2 development sequences (`may_hard_reentry`,
`seq01_clean`, `seq03_crossing`, `seq04_occlusion`) + 3 VisDrone-MOT sequences
(`uav0000117_02622_v`, `uav0000137_00458_v`, `uav0000339_00001_v`). DanceTrack
(5 sequences) and `uav0000268_05773_v` (4K VisDrone) are excluded from primary
scope with documented rationale; their manifest entries and any generated
evidence are retained, not deleted.

- Frozen sequence manifest and schema:
  `docs/data/external_benchmark/sequence_manifest.json`,
  `docs/data/external_benchmark/manifest.schema.json`
- Full-pipeline per-sequence reports:
  `artifacts/reports/p030_broader_sequences/external_frame_reports/`
- Oracle-candidate per-sequence reports:
  `artifacts/reports/p030_broader_sequences/oracle_frame_reports/`
- Full-pipeline and oracle aggregates (kept separate, never merged):
  `artifacts/reports/p030_broader_sequences/first_phase_aggregate.json`,
  `artifacts/reports/p030_broader_sequences/oracle_aggregate.json`
- Bbox-height-stratified diagnostic (data, table export, figures):
  `artifacts/reports/p030_broader_sequences/bbox_size_stratified_report.json`,
  `artifacts/reports/p030_broader_sequences/bbox_size_stratified_report.csv`,
  `artifacts/reports/p030_broader_sequences/bbox_size_outcome_fractions.png`,
  `artifacts/reports/p030_broader_sequences/bbox_size_candidate_availability.png`
- Corrected ByteTrack ROS 2 event-recovery reports (June Seq03/Seq04, replacing
  the earlier OC-SORT-provenance evidence):
  `artifacts/reports/p030_broader_sequences/seq03_crossing_bytetrack/report.json`,
  `artifacts/reports/p030_broader_sequences/seq04_occlusion_bytetrack/report.json`
- May/June Seq01 event-recovery reports (Issue #26 evidence, reused unmodified):
  `reports/p026_event_recovery_b50f914a_2026_08_05/may_hard_reentry/report.json`,
  `reports/p026_event_recovery_b50f914a_2026_08_05/seq01_clean/report.json`
- Builder/aggregation scripts (all tracked, all reused unmodified by
  downstream analysis rather than duplicated):
  `tools/analysis/run_external_sequence_report.py`,
  `tools/analysis/aggregate_first_phase_report.py`,
  `tools/analysis/aggregate_oracle_report.py`,
  `tools/analysis/build_oracle_candidate_bag.py`,
  `tools/analysis/bbox_size_stratified_report.py`,
  `tools/analysis/render_bbox_size_report_outputs.py`

The `artifacts/reports/p030_broader_sequences/` directory is git-ignored
generated output, regenerable from the tracked scripts above against the
frozen manifest and existing capture/replay bags; it is not duplicated
into version control.

## Final Issue #31 / P031 parameter-sensitivity evidence

Canonical thesis-facing summary:
`docs/results/selected_target_tracking/p031_parameter_sensitivity_summary.md`.
Full chronological engineering record:
`docs/issues/p1-13-parameter-sensitivity.md`.

116 deterministic TIM replay + event-recovery evaluation cells (29
configurations x 4 development sequences: `dev_may_hard_reentry`,
`dev_june_seq01`, `dev_june_seq03`, `dev_june_seq04`), all executed under
canonical config hash
`e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`.

- Frozen sweep manifest, lock, and matrix:
  `docs/data/parameter_sensitivity/tim_mars_parameter_sensitivity_v1.yaml`
- Generated per-cell reports (git-ignored, regenerable):
  `reports/p031_parameter_sensitivity_5b340c2b_2026-08-08/sequences/`
- Generated aggregate tables and figures (git-ignored, regenerable):
  `reports/p031_parameter_sensitivity_5b340c2b_2026-08-08/aggregate/`
- Tracked copies of the lock file, final-invocation provenance, all four
  per-batch execution logs, aggregate CSV/JSON tables, and figures, with
  `SHA256SUMS`:
  `docs/results/selected_target_tracking/p031_parameter_sensitivity_development/`
- Sweep/replay/evaluation tooling (reused unmodified, no TIM-MARS algorithm
  logic duplicated):
  `tools/experiments/run_tim_parameter_sensitivity.py`,
  `tools/analysis/aggregate_parameter_sensitivity_report.py`,
  `tools/analysis/plot_parameter_sensitivity.py`

The `reports/p031_parameter_sensitivity_5b340c2b_2026-08-08/` directory is
git-ignored generated output, regenerable from the tracked scripts above
against the frozen manifest, canonical config, and existing source bags; it
is not duplicated into version control beyond the tracked copies above.

