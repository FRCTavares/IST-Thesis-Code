# TIM-MARS CPU ReID workload

- Run: `all_candidates_250ms/seq01_clean`
- Commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1/all_candidates_250ms/seq01_clean`
- Duration: 107.964 s
- Schema: `p044_cpu_reid_workload_summary_v2`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 2465 |
| `appearance_candidates` | 9107 |
| `appearance_features_valid` | 8568 |
| `appearance_encoding_eligible` | 1297 |
| `appearance_backend_calls` | 353 |
| `appearance_backend_requested` | 1297 |
| `appearance_backend_returned` | 1297 |
| `appearance_backend_valid` | 1297 |

## Backend timing

| Population | n | Mean | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| all calls | 353 | 68.287 | 71.030 | 76.237 | 80.469 | 507.578 |
| steady state | 352 | 67.039 | 71.029 | 76.179 | 80.173 | 91.232 |

## Callback displacement

| Metric | Value |
|---|---:|
| backend-call latency mean (ms) | 69.808 |
| non-call latency mean (ms) | 1.639 |
| mean displacement (ms) | 68.169 |
| callback overhead mean (ms) | 1.521 |
| backend/callback correlation | 0.999977 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 22.831752 |
| `backend_call_record_fraction` | 0.143205 |
| `backend_calls_per_second` | 3.269618 |
| `requested_crops_per_second` | 12.013299 |
| `requested_per_call` | 3.674221 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `backend_wall_fraction_of_run_all` | 0.223274 |
| `backend_wall_fraction_of_run_steady_state` | 0.218572 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | PASS |
| first call is warm-up outlier | PASS |
| warm-up threshold (ms) | 213.086 |
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
