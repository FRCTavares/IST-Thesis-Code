# TIM-MARS CPU ReID workload

- Run: `ambiguity_guarded_250ms/seq03_crossing`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/ambiguity_guarded_250ms/seq03_crossing`
- Duration: 96.078 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 2336 |
| `appearance_candidates` | 5124 |
| `appearance_features_valid` | 2878 |
| `appearance_encoding_eligible` | 723 |
| `appearance_backend_calls` | 329 |
| `appearance_backend_requested` | 412 |
| `appearance_backend_returned` | 412 |
| `appearance_backend_valid` | 412 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 329 | 27.853 | 22.160 | 52.642 | 73.709 | 415.778 |
| steady state | 328 | 26.670 | 22.152 | 52.536 | 72.910 | 76.056 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 29.033 |
| non-call latency mean (ms) | 1.260 |
| mean displacement (ms) | 27.773 |
| callback overhead mean (ms) | 1.180 |
| backend/callback correlation | 0.999950 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 24.313517 |
| `backend_call_record_fraction` | 0.140839 |
| `backend_calls_per_second` | 3.424292 |
| `requested_crops_per_second` | 4.288172 |
| `requested_per_call` | 1.252280 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.095377 |
| `backend_wall_fraction_of_run_steady_state` | 0.091050 |

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
