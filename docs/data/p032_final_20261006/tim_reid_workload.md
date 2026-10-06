# TIM-MARS ReID workload

- Run: `2026-10-06__14-52-31__video__p032_final_mounted_vga`
- Commit: `None`
- Bag: `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga`
- Duration: 1453.993 s
- Schema: `p032_tim_mars_reid_workload_summary_v3`

## Workload totals

| Metric | Value |
|---|---:|
| `status_records` | 40483 |
| `status_records_total` | 40484 |
| `excluded_non_frame_status_records` | 1 |
| `appearance_candidates` | 40667 |
| `appearance_features_valid` | 40462 |
| `appearance_encoding_eligible` | 5152 |
| `appearance_backend_calls` | 5144 |
| `appearance_backend_requested` | 5152 |
| `appearance_backend_returned` | 5152 |
| `appearance_backend_valid` | 5152 |
| `appearance_cache_lookups` | 35515 |
| `appearance_cache_hits` | 35310 |
| `appearance_cache_misses` | 201 |
| `appearance_cache_expired` | 4 |
| `appearance_cache_invalidated` | 0 |

## Backend timing

| Population | n | Mean | Std | p50 | p90 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all calls | 5144 | 84.769 | 12.238 | 83.659 | 97.459 | 103.484 | 125.078 | 290.062 |
| steady state | 5144 | 84.769 | 12.238 | 83.659 | 97.459 | 103.484 | 125.078 | 290.062 |

## Exact appearance-cache accounting

| Metric | Value |
|---|---:|
| lookups | 35515 |
| hits | 35310 |
| misses | 201 |
| expired | 4 |
| invalidated | 0 |
| hit rate | 0.994228 |
| accounting identity, totals | PASS |
| accounting identity, every record | PASS |

## TIM-MARS processing impact

| Metric | Value |
|---|---:|
| backend-call processing mean (ms) | 86.309 |
| non-call processing mean (ms) | 1.893 |
| mean processing displacement (ms) | 84.415 |
| non-backend processing mean (ms) | 1.540 |
| backend/processing correlation | 0.996454 |

## Derived load

| Metric | Value |
|---|---:|
| `status_records_per_second` | 27.842643 |
| `backend_call_record_fraction` | 0.127066 |
| `backend_calls_per_second` | 3.537844 |
| `requested_crops_per_second` | 3.543347 |
| `requested_per_call` | 1.001555 |
| `returned_per_requested` | 1.000000 |
| `valid_per_requested` | 1.000000 |
| `valid_embeddings_per_second` | 3.543347 |
| `cache_hit_rate` | 0.994228 |
| `backend_wall_fraction_of_run_all` | 0.299898 |
| `backend_wall_fraction_of_run_steady_state` | 0.299898 |

## Warm-up classification

| Metric | Value |
|---|---:|
| first call is largest | FAIL |
| first call is warm-up outlier | FAIL |
| warm-up threshold (ms) | 250.974 |
| calls excluded from steady state | 0 |

## Integrity

| Check | Result |
|---|---:|
| `all_required_fields_present` | PASS |
| `has_backend_calls` | PASS |
| `has_positive_backend_wall_time` | PASS |
| `non_call_records_with_nonzero_backend_wall_ms` | PASS |
| `returned_not_greater_than_requested` | PASS |
| `valid_not_greater_than_returned` | PASS |
| `cache_accounting_identity_totals` | PASS |
| `cache_accounting_identity_all_records` | PASS |
