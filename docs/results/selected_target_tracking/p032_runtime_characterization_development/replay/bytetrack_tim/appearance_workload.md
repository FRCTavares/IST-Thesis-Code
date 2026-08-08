# Issue #32 Appearance Budget -- bytetrack_tim_dev_may_hard_reentry

- bag: `/home/francisco/Desktop/Thesis-Code/reports/p032_runtime_characterization_6231fdc1_2026_08_08/replay/bytetrack_tim/tim.bag`
- git commit: `6231fdc1370b78a55ffeee9a403adbbddf4fb424`
- measurement mode: `replay_algorithmic_cost`
- record count: 953
- duration: 67.607 s

## Budget

- frames invoking appearance: 226 (0.237 fraction)
- candidates encoded / s: 6.686
- embeddings / s: 6.686
- cache hit rate (estimate): 0.753

## Latency (ms)

**Unavailable in this measurement mode:** tools/experiments/run_deterministic_tim_replay.py hardcodes lat_ms=0.0 and appearance_backend_wall_ms=0.0 (verified in source): deterministic replay never measures wall time. Reporting these as zero would silently fabricate an implausible zero-latency claim. Genuine TIM core / MARS extraction latency percentiles come only from measurement_mode=live_sustained.

| Metric | n | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| TIM core (`lat_ms`) | unavailable | -- | -- | -- | -- | -- |
| MARS extraction (`appearance_backend_wall_ms`) | unavailable | -- | -- | -- | -- | -- |

## Skip reasons

| Reason | Count |
|---|---:|
| cached_interval | 613 |
| cached_same_image | 111 |
| ok | 226 |
| stale_image | 3 |
