# TIM-MARS CPU ReID workload

- Run: `all_candidates_250ms/may_hard_reentry`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/all_candidates_250ms/may_hard_reentry`
- Duration: 67.610 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 950 |
| `appearance_candidates` | 2788 |
| `appearance_features_valid` | 1773 |
| `appearance_encoding_eligible` | 369 |
| `appearance_backend_calls` | 182 |
| `appearance_backend_requested` | 369 |
| `appearance_backend_returned` | 369 |
| `appearance_backend_valid` | 369 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 182 | 46.126 | 43.806 | 54.002 | 64.961 | 429.189 |
| steady state | 181 | 44.010 | 43.805 | 53.431 | 61.071 | 73.192 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 47.401 |
| non-call latency mean (ms) | 1.408 |
| mean displacement (ms) | 45.993 |
| callback overhead mean (ms) | 1.275 |
| backend/callback correlation | 0.999980 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 14.051164 |
| `backend_call_record_fraction` | 0.191579 |
| `backend_calls_per_second` | 2.691907 |
| `requested_crops_per_second` | 5.457768 |
| `requested_per_call` | 2.027473 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.124168 |
| `backend_wall_fraction_of_run_steady_state` | 0.117820 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | PASS |
| first call is warm-up outlier | PASS |
| warm-up threshold (ms) | 131.415 |
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
