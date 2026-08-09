# Issue #32 Appearance Budget -- p032_ground_run_7e51e79a_2026_08_09_dev_may_hard_reentry_corrected

- bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p032_ground_run_7e51e79a_2026_08_09_dev_may_hard_reentry_corrected/evidence`
- git commit: `7e51e79a12481e0cea591e022352d1804a7bd95f`
- measurement mode: `live_sustained`
- record count: 4109
- duration: 1196.771 s

## Budget

- frames invoking appearance: 2470 (0.601 fraction)
- candidates encoded / s: 2.474
- embeddings / s: 2.474
- cache hit rate (estimate): 0.372

## Latency (ms)

| Metric | n | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| TIM core (`lat_ms`) | 4109 | 42.631 | 68.625 | 78.693 | 84.537 | 458.918 |
| MARS extraction (`appearance_backend_wall_ms`) | 2470 | 47.002 | 75.513 | 80.271 | 84.732 | 457.881 |

## Skip reasons

| Reason | Count |
|---|---:|
| cached_interval | 1318 |
| cached_same_image | 118 |
| no_candidates | 43 |
| no_image | 1 |
| no_policy_requested_candidates | 1 |
| ok | 2470 |
| stale_image | 158 |
