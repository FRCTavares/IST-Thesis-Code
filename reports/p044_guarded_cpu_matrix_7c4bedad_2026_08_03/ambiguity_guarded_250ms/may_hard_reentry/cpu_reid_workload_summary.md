# TIM-MARS CPU ReID workload

- Run: `ambiguity_guarded_250ms/may_hard_reentry`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/may_hard_reentry`
- Duration: 67.439 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 950 |
| `appearance_candidates` | 2788 |
| `appearance_features_valid` | 956 |
| `appearance_encoding_eligible` | 372 |
| `appearance_backend_calls` | 184 |
| `appearance_backend_requested` | 195 |
| `appearance_backend_returned` | 195 |
| `appearance_backend_valid` | 195 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 184 | 25.882 | 22.151 | 41.064 | 43.557 | 470.755 |
| steady state | 183 | 23.451 | 22.144 | 40.796 | 43.023 | 45.162 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 27.150 |
| non-call latency mean (ms) | 1.391 |
| mean displacement (ms) | 25.759 |
| callback overhead mean (ms) | 1.268 |
| backend/callback correlation | 0.999991 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 14.086823 |
| `backend_call_record_fraction` | 0.193684 |
| `backend_calls_per_second` | 2.728395 |
| `requested_crops_per_second` | 2.891506 |
| `requested_per_call` | 1.059783 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.070617 |
| `backend_wall_fraction_of_run_steady_state` | 0.063637 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | PASS |
| first call is warm-up outlier | PASS |
| warm-up threshold (ms) | 100.000 |
| calls excluded from steady state | 1 |

## Integrity

| Check | Result |
|---|---:|
| `all_required_fields_present` | PASS |
| `has_backend_calls` | PASS |
| `has_positive_backend_wall_time` | PASS |
| `non_call_records_with_nonzero_backend_wall_ms` | PASS |
| `returned_not_greater_than_requested` | PASS |
| `valid_not_greater_than_returned` | PASS |
