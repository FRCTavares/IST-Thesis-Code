# Timing Summary: 2026-04-30__12-29-33__video__oficial_flight_01
Bag: `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-04-30__12-29-33__video__oficial_flight_01`
Timing vocabulary: canonical fields only (`pub_dt_ms` is the cadence metric).
Contract schema: `v3`
- metric_windows: `{'det_out_fps_seconds': 3.0}`
- metric_thresholds_ms: `{'e2e_det_ms': 120.0, 'pub_dt_ms': 120.0, 'infer_ms': 20.0, 'container_queue_ms': 100.0, 'track_ms': 25.0, 'e2e_target_ms': 150.0}`
Base window: first to last `/timing` message (bag timestamps)
- start_ns: `1777548588869168501`
- end_ns: `1777548997761538054`
- duration_s: `408.892`
## Per-field stats (/timing)
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 6669 | 1.403 | 0.857 | 4.149 | 6.953 | 0.327 | 14.256 |
| container_queue_ms | 6669 | 1.028 | 0.638 | 1.893 | 5.521 | 0.342 | 826.232 |
| zmq_roundtrip_ms | 6669 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| infer_ms | 6669 | 19.499 | 11.896 | 40.604 | 46.298 | 5.555 | 74.532 |
| e2e_det_ms | 6669 | 25.405 | 18.050 | 48.794 | 56.432 | 7.621 | 878.070 |
| pub_dt_ms | 6669 | 61.321 | 46.580 | 137.077 | 198.936 | 9.249 | 890.329 |

## Achieved Hz (counts over base window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 6668 | 16.307 |
| /target | 6648 | 16.259 |
| /timing | 6669 | 16.310 |
| /timing_tracker | 6647 | 16.256 |
| /tracks | 6647 | 16.256 |

## Active-only window (gap-filtered)
Definition: samples with `pub_dt_ms <= 100.0` ms
- start_ns: `1777548588869168501`
- end_ns: `1777548997761538054`
- duration_s: `278.074`
- gap_count: `917`
- gap_removed_s: `130.819`
- dropped_samples: `917`

### Per-field stats (/timing), active-only
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 5752 | 1.411 | 0.852 | 4.208 | 7.015 | 0.327 | 14.256 |
| container_queue_ms | 5752 | 0.911 | 0.634 | 2.050 | 5.817 | 0.342 | 17.093 |
| zmq_roundtrip_ms | 5752 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| infer_ms | 5752 | 19.179 | 11.788 | 40.874 | 47.021 | 5.555 | 74.532 |
| e2e_det_ms | 5752 | 24.983 | 17.798 | 49.233 | 57.329 | 7.621 | 93.357 |
| pub_dt_ms | 5752 | 49.009 | 42.922 | 90.591 | 98.238 | 9.249 | 99.978 |

### Achieved Hz (active-only window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 5918 | 21.282 |
| /target | 5544 | 19.937 |
| /timing | 6111 | 21.976 |
| /timing_tracker | 5367 | 19.301 |
| /tracks | 5302 | 19.067 |

## Tracker runtime
Topic: `/timing_tracker` (field: `track_ms`)
| metric | value |
|---|---:|
| n | 5367 |
| mean (ms) | 7.639 |
| p50 (ms) | 2.558 |
| p95 (ms) | 25.432 |
| p99 (ms) | 46.891 |
| max (ms) | 191.366 |

Active-only Hz (tracker timing): `19.301`

## Target end-to-end runtime
Topic: `/timing_target` (field: `e2e_target_ms`)
| metric | value |
|---|---:|
| n | 5564 |
| mean (ms) | 1.290 |
| p50 (ms) | 0.000 |
| p95 (ms) | 0.000 |
| p99 (ms) | 59.467 |
| max (ms) | 254.572 |

Active-only Hz (target timing): `20.009`

## Figures
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/e2e_det_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/e2e_det_ms_cdf.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/pub_dt_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/pub_dt_ms_cdf.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/track_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/track_ms_cdf.png`
