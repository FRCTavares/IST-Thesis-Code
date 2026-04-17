# Mode Experiment Summary: mode_compare_20260416_190754

## Artifact Issues
- empty metrics artifact skipped: reports/timing/mode_compare_20260416_190754__sp_default__r2.json (timing_count=0, detection_count=0)
- empty metrics artifact skipped: reports/timing/mode_compare_20260416_190754__sp_640x460__r2.json (timing_count=0, detection_count=0)

## Condition Medians
| condition | runs | invariants_all_ok | /timing_hz | e2e_det_p95_ms | pub_dt_p95_ms | pub_dt_p99_ms | infer_p95_ms | det_per_msg_mean | det_zero_ratio |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| sp_default | 1/2 | True | 9.822 | 124.899 | 121.709 | 176.907 | 10.055 | 0.769 | 0.2314 |
| sp_640x460 | 1/2 | True | 10.021 | 135.367 | 117.929 | 139.645 | 11.504 | 0.889 | 0.1288 |
| legacy_640x460 | 2/2 | True | 16.483 | 33.699 | 137.846 | 163.048 | 8.194 | 1.000 | 0.0171 |

## Pairwise Verdicts
### sp_640x460_vs_legacy_640x460
- all_gates_pass: False
- winner: inconclusive
- gate min_timing_hz: passed=True (sp_640x460=10.021 Hz, legacy_640x460=16.483 Hz, required >= 8.500 Hz)
- gate detection_load_comparability: passed=False (mean_delta=0.1256 (max 0.1000), zero_ratio_delta=0.1117 (max 0.0500))
- gate invariants_clean: passed=True (sp_640x460=True, legacy_640x460=True)
- gate all_runs_present: passed=False (sp_640x460 runs=1/2, legacy_640x460 runs=2/2)

### sp_default_vs_sp_640x460
- all_gates_pass: False
- winner: inconclusive
- gate min_timing_hz: passed=True (sp_default=9.822 Hz, sp_640x460=10.021 Hz, required >= 8.500 Hz)
- gate detection_load_comparability: passed=False (mean_delta=0.1548 (max 0.1000), zero_ratio_delta=0.1025 (max 0.0500))
- gate invariants_clean: passed=True (sp_default=True, sp_640x460=True)
- gate all_runs_present: passed=False (sp_default runs=1/2, sp_640x460 runs=1/2)

### sp_default_vs_legacy_640x460
- all_gates_pass: False
- winner: inconclusive
- gate min_timing_hz: passed=True (sp_default=9.822 Hz, legacy_640x460=16.483 Hz, required >= 8.500 Hz)
- gate detection_load_comparability: passed=False (mean_delta=0.2999 (max 0.1000), zero_ratio_delta=0.2142 (max 0.0500))
- gate invariants_clean: passed=True (sp_default=True, legacy_640x460=True)
- gate all_runs_present: passed=False (sp_default runs=1/2, legacy_640x460 runs=2/2)

## Recommendation
- operational_default: keep-current-single-process
- rationale: Main pair did not pass comparability/stability gates.
- remove_single_process_now: False
- remove_legacy_now: False
- policy_note: Do not remove either path in this phase. Keep rollback mode healthy and follow migration gate + release-window policy before any path deletion.
