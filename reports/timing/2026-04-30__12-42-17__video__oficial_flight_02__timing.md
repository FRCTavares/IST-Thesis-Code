# Timing Summary: 2026-04-30__12-42-17__video__oficial_flight_02
Bag: `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-04-30__12-42-17__video__oficial_flight_02`
Timing vocabulary: canonical fields only (`pub_dt_ms` is the cadence metric).
Contract schema: `v3`
- metric_windows: `{'det_out_fps_seconds': 3.0}`
- metric_thresholds_ms: `{'e2e_det_ms': 120.0, 'pub_dt_ms': 120.0, 'infer_ms': 20.0, 'container_queue_ms': 100.0, 'track_ms': 25.0, 'e2e_target_ms': 150.0}`
Base window: first to last `/timing` message (bag timestamps)
- start_ns: `1777549353435538768`
- end_ns: `1777549701518000616`
- duration_s: `348.082`
## Per-field stats (/timing)
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 6012 | 1.350 | 0.775 | 4.092 | 6.916 | 0.343 | 16.992 |
| container_queue_ms | 6012 | 0.991 | 0.635 | 1.870 | 5.080 | 0.405 | 772.583 |
| zmq_roundtrip_ms | 6012 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| infer_ms | 6012 | 14.853 | 9.721 | 37.975 | 42.918 | 5.545 | 62.923 |
| e2e_det_ms | 6012 | 20.335 | 14.841 | 44.315 | 51.548 | 7.234 | 821.902 |
| pub_dt_ms | 6012 | 57.956 | 38.955 | 139.737 | 259.840 | 11.121 | 918.348 |

## Achieved Hz (counts over base window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 6011 | 17.269 |
| /target | 5987 | 17.200 |
| /timing | 6012 | 17.272 |
| /timing_tracker | 5995 | 17.223 |
| /tracks | 5995 | 17.223 |

## Active-only window (gap-filtered)
Definition: samples with `pub_dt_ms <= 100.0` ms
- start_ns: `1777549353580823026`
- end_ns: `1777549701518000616`
- duration_s: `234.757`
- gap_count: `684`
- gap_removed_s: `113.325`
- dropped_samples: `684`

### Per-field stats (/timing), active-only
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 5328 | 1.329 | 0.764 | 4.073 | 6.749 | 0.343 | 16.992 |
| container_queue_ms | 5328 | 0.857 | 0.631 | 1.862 | 5.019 | 0.405 | 14.639 |
| zmq_roundtrip_ms | 5328 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| infer_ms | 5328 | 14.560 | 9.658 | 37.738 | 42.901 | 5.545 | 56.045 |
| e2e_det_ms | 5328 | 19.868 | 14.700 | 44.207 | 51.748 | 7.234 | 88.087 |
| pub_dt_ms | 5328 | 44.553 | 37.089 | 83.959 | 97.683 | 11.121 | 99.987 |

### Achieved Hz (active-only window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 5434 | 23.147 |
| /target | 5136 | 21.878 |
| /timing | 5589 | 23.808 |
| /timing_tracker | 4996 | 21.282 |
| /tracks | 4932 | 21.009 |

## Tracker runtime
Topic: `/timing_tracker` (field: `track_ms`)
| metric | value |
|---|---:|
| n | 4996 |
| mean (ms) | 4.879 |
| p50 (ms) | 0.600 |
| p95 (ms) | 20.928 |
| p99 (ms) | 34.978 |
| max (ms) | 145.513 |

Active-only Hz (tracker timing): `21.282`

## Target end-to-end runtime
Topic: `/timing_target` (field: `e2e_target_ms`)
| metric | value |
|---|---:|
| n | 5178 |
| mean (ms) | 0.831 |
| p50 (ms) | 0.000 |
| p95 (ms) | 0.000 |
| p99 (ms) | 39.933 |
| max (ms) | 113.402 |

Active-only Hz (target timing): `22.057`

## Figures
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/e2e_det_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/e2e_det_ms_cdf.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/pub_dt_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/pub_dt_ms_cdf.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/track_ms_hist.png`
- `/home/francisco/Desktop/Thesis-Code/figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/track_ms_cdf.png`
