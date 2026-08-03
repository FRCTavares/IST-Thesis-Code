# TIM-MARS CPU ReID workload

- Run: `all_candidates_250ms/seq03_crossing`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/all_candidates_250ms/seq03_crossing`
- Duration: 96.080 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 2336 |
| `appearance_candidates` | 5124 |
| `appearance_features_valid` | 4249 |
| `appearance_encoding_eligible` | 698 |
| `appearance_backend_calls` | 322 |
| `appearance_backend_requested` | 698 |
| `appearance_backend_returned` | 698 |
| `appearance_backend_valid` | 698 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 322 | 42.780 | 42.523 | 68.870 | 72.020 | 416.238 |
| steady state | 321 | 41.617 | 42.505 | 68.523 | 71.469 | 81.150 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 43.980 |
| non-call latency mean (ms) | 1.282 |
| mean displacement (ms) | 42.698 |
| callback overhead mean (ms) | 1.200 |
| backend/callback correlation | 0.999944 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 24.313172 |
| `backend_call_record_fraction` | 0.137842 |
| `backend_calls_per_second` | 3.351388 |
| `requested_crops_per_second` | 7.264809 |
| `requested_per_call` | 2.167702 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.143374 |
| `backend_wall_fraction_of_run_steady_state` | 0.139041 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | PASS |
| first call is warm-up outlier | PASS |
| warm-up threshold (ms) | 127.514 |
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
