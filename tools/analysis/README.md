# tools/analysis

Last reviewed: 2026-09-10

## Purpose

Offline and live analysis tools for TIM-MARS evaluation, runtime
characterisation, and diagnostics. The directory is broad but grouped by
function; it is not restructured into subdirectories because several paths
here are pinned by the prospective-freeze manifest.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `tim_evaluation.py` | Shared library | Single authority for annotation parsing, time origins, output-validity, freshness sampling and interval integration. |
| `evaluate_tim_target_correctness.py` | Correctness | Track-ID correctness and durations for raw `/target` vs TIM `/target_memory_mars`. |
| `evaluate_tim_target_bbox_correctness.py` | Correctness | Spatial bbox agreement against the annotated target track. |
| `evaluate_tim_by_event_type.py` | Correctness | Selected-target correctness aggregated by annotation `event_type`. |
| `evaluate_physical_target_bbox_v2.py`, `physical_target_bbox_evaluation_v2.py`, `physical_target_reference_v2.py` | Physical-v2 evaluator | Identity-independent physical-target evaluator (frozen for H01–H03). `*_v2` supersedes the retained v1 files. |
| `validate_tim_evaluation_split.py` | Gate | Validates the frozen split, hashes, people/clothing records and the final-release gate. |
| `derive_presence_conditioned_metrics.py` | Reporting | Pure downstream presence-conditioned percentages from one physical-v2 report. |
| `p058_target_reid_*.py` | Baseline | Simple post-MOT Target-ReID arm for Issue #58 (baseline/calibration/runtime/sweep). |
| `analyse_bag_timing.py`, `check_live_timing_invariants.py`, `collect_live_timing_stats.py` | Timing | Offline stats/plots and live `/timing` invariant/percentile checks. Import `tools.timing_contract`. |
| `analyse_bag_tracking.py`, `analyse_tracker_target_continuity.py`, `analyse_tim_*` | Diagnostics | Tracker continuity, state occupancy, ReID workload, resilience-evidence analysis. |
| `summarize_control_diagnostics.py` | Diagnostics | Integrity summary of recorded `/control_ref/diagnostics` (Issue #74): mode occupancy, reason counts, recovery-attempt bookkeeping, and the hard check that recovery is never active with non-zero translation. Not the final #50/#74 analyser. |
| `extract_tim_all_scores.py`, `extract_tim_mars_reid_similarity.py` | Diagnostics | Candidate `all_scores` and MARS/ReID similarity extraction to explain accept/reject decisions. |
| `aggregate_*_report.py`, `plot_parameter_sensitivity.py`, `render_bbox_size_report_outputs.py` | Aggregation | Combine per-cell experiment output into reports, tables and figures. |
| `*external*`, `catalogue_external_tracking_dataset.py`, `select_first_phase_benchmark.py` | External datasets | VisDrone/MOT/DanceTrack acquisition, validation, selection and outcome scoring. |
| `cvat_physical_reference.py` | Annotation bridge | Exact-frame CVAT ↔ physical-reference-v2 conversion (fail-closed). |
| `templates/` | Assets | Blank annotation templates consumed by the evaluators and the UI. |

## Rules

- CLI evaluators are thin layers: they must import evaluation semantics from
  `tim_evaluation.py` and never define their own annotation parser, time
  origin, output-validity rule or duration step. This keeps event rows summing
  exactly to the selected-target totals.
- A selected-target output is valid only when its ID is non-zero and any
  present bbox is finite with positive width and height.
- Full-pipeline reruns from `/camera/image_raw` regenerate tracker IDs;
  annotations made for one run are not valid for another unless the IDs match
  or an ID-independent evaluator is used.
- `*_v2` physical-target files and `validate_tim_evaluation_split.py` are
  frozen for H01–H03 — do not move or rename them.

## See also

- `docs/design/tim_tooling_index.md` — replay/evaluation path authority
- `docs/data/splits/README.md` — evaluation split policy
- `templates/target_correctness_annotations_template.csv` — annotation format
  (`[start_s, end_s)` half-open intervals; gaps allowed and unscored)
