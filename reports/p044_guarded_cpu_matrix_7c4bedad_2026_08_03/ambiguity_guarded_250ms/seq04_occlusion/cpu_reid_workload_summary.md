# TIM-MARS CPU ReID workload

- Run: `ambiguity_guarded_250ms/seq04_occlusion`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/seq04_occlusion`
- Duration: 66.393 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 1586 |
| `appearance_candidates` | 4439 |
| `appearance_features_valid` | 2470 |
| `appearance_encoding_eligible` | 616 |
| `appearance_backend_calls` | 205 |
| `appearance_backend_requested` | 369 |
| `appearance_backend_returned` | 369 |
| `appearance_backend_valid` | 369 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 205 | 38.564 | 24.084 | 88.544 | 90.435 | 442.635 |
| steady state | 204 | 36.583 | 24.063 | 88.031 | 89.893 | 93.631 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 39.878 |
| non-call latency mean (ms) | 1.309 |
| mean displacement (ms) | 38.569 |
| callback overhead mean (ms) | 1.314 |
| backend/callback correlation | 0.999961 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 23.888150 |
| `backend_call_record_fraction` | 0.129256 |
| `backend_calls_per_second` | 3.087686 |
| `requested_crops_per_second` | 5.557836 |
| `requested_per_call` | 1.800000 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.119073 |
| `backend_wall_fraction_of_run_steady_state` | 0.112406 |

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
