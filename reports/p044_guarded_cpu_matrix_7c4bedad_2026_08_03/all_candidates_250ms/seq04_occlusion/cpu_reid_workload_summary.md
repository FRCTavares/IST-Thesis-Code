# TIM-MARS CPU ReID workload

- Run: `all_candidates_250ms/seq04_occlusion`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/all_candidates_250ms/seq04_occlusion`
- Duration: 66.393 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 1585 |
| `appearance_candidates` | 4438 |
| `appearance_features_valid` | 3759 |
| `appearance_encoding_eligible` | 613 |
| `appearance_backend_calls` | 212 |
| `appearance_backend_requested` | 613 |
| `appearance_backend_returned` | 613 |
| `appearance_backend_valid` | 613 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 212 | 65.542 | 63.112 | 104.287 | 112.175 | 456.633 |
| steady state | 211 | 63.689 | 63.095 | 103.665 | 110.845 | 112.507 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 66.834 |
| non-call latency mean (ms) | 1.279 |
| mean displacement (ms) | 65.554 |
| callback overhead mean (ms) | 1.291 |
| backend/callback correlation | 0.999970 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 23.872869 |
| `backend_call_record_fraction` | 0.133754 |
| `backend_calls_per_second` | 3.193090 |
| `requested_crops_per_second` | 9.232851 |
| `requested_per_call` | 2.891509 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.209283 |
| `backend_wall_fraction_of_run_steady_state` | 0.202405 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | PASS |
| first call is warm-up outlier | PASS |
| warm-up threshold (ms) | 189.286 |
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
