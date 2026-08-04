# TIM-MARS CPU ReID workload

- Run: `ambiguity_guarded_250ms/seq01_clean`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/seq01_clean`
- Duration: 107.809 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 2464 |
| `appearance_candidates` | 9102 |
| `appearance_features_valid` | 2398 |
| `appearance_encoding_eligible` | 1318 |
| `appearance_backend_calls` | 359 |
| `appearance_backend_requested` | 359 |
| `appearance_backend_returned` | 359 |
| `appearance_backend_valid` | 359 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 359 | 23.642 | 22.261 | 25.273 | 28.471 | 412.182 |
| steady state | 358 | 22.557 | 22.260 | 25.250 | 26.644 | 35.326 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 25.016 |
| non-call latency mean (ms) | 1.505 |
| mean displacement (ms) | 23.511 |
| callback overhead mean (ms) | 1.374 |
| backend/callback correlation | 0.999976 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 22.855189 |
| `backend_call_record_fraction` | 0.145698 |
| `backend_calls_per_second` | 3.329957 |
| `requested_crops_per_second` | 3.329957 |
| `requested_per_call` | 1.000000 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.078728 |
| `backend_wall_fraction_of_run_steady_state` | 0.074905 |

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
