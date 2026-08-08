# Issue #32 Appearance Budget -- p032_ground_run_331ccc24_2026_08_08_dev_may_hard_reentry

- bag: `/home/francisco/Desktop/Thesis-Code/bags/replay/p032_ground_run_331ccc24_2026_08_08_dev_may_hard_reentry/evidence`
- git commit: `331ccc24634f21fc95746d3e0d1423cb55597950`
- measurement mode: `live_sustained`
- record count: 4064
- duration: 1195.544 s

## Budget

- frames invoking appearance: 2472 (0.608 fraction)
- candidates encoded / s: 2.467
- embeddings / s: 2.467
- cache hit rate (estimate): 0.369

## Latency (ms)

| Metric | n | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| TIM core (`lat_ms`) | 4064 | 41.637 | 67.803 | 78.874 | 83.807 | 462.931 |
| MARS extraction (`appearance_backend_wall_ms`) | 2472 | 46.514 | 76.231 | 79.946 | 83.618 | 461.280 |

## Skip reasons

| Reason | Count |
|---|---:|
| cached_interval | 1267 |
| cached_same_image | 111 |
| no_candidates | 45 |
| ok | 2472 |
| stale_image | 169 |
