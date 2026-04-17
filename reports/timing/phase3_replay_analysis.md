# Timing Summary: 2026-03-29__control_validation_clean
Bag: `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-03-29__control_validation_clean`
Timing vocabulary: canonical fields only (`pub_dt_ms` is the cadence metric).
Contract schema: `v3`
- metric_windows: `{'det_out_fps_seconds': 3.0}`
- metric_thresholds_ms: `{'e2e_det_ms': 120.0, 'pub_dt_ms': 120.0, 'infer_ms': 20.0, 'container_queue_ms': 100.0, 'track_ms': 25.0, 'e2e_target_ms': 150.0}`
Base window: first to last `/timing` message (bag timestamps)
- start_ns: `1774798517964325176`
- end_ns: `1774798636540532033`
- duration_s: `118.576`
## Per-field stats (/timing)
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 1402 | 7.385 | 6.271 | 17.141 | 24.066 | 1.840 | 37.787 |
| container_queue_ms | 1402 | 1.276 | 0.983 | 2.964 | 3.962 | 0.466 | 5.996 |
| zmq_roundtrip_ms | 1402 | 18.752 | 17.685 | 27.590 | 36.384 | 9.658 | 56.353 |
| infer_ms | 1402 | 6.737 | 6.459 | 8.991 | 10.124 | 5.119 | 14.005 |
| e2e_det_ms | 1402 | 29.248 | 27.586 | 45.772 | 59.256 | 13.135 | 77.579 |
| pub_dt_ms | 1402 | 84.690 | 72.862 | 166.357 | 240.066 | 0.403 | 1118.592 |

## Achieved Hz (counts over base window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 1401 | 11.815 |
| /target | 1389 | 11.714 |
| /timing | 1402 | 11.824 |
| /timing_tracker | 0 | 0.000 |
| /tracks | 0 | 0.000 |

## Active-only window (gap-filtered)
Definition: samples with `pub_dt_ms <= 100.0` ms
- start_ns: `1774798517964325176`
- end_ns: `1774798636540532033`
- duration_s: `45.917`
- gap_count: `478`
- gap_removed_s: `72.659`
- dropped_samples: `478`

### Per-field stats (/timing), active-only
| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 924 | 7.967 | 6.847 | 17.715 | 24.658 | 1.840 | 37.787 |
| container_queue_ms | 924 | 1.205 | 0.853 | 3.050 | 3.949 | 0.466 | 5.996 |
| zmq_roundtrip_ms | 924 | 18.857 | 17.797 | 27.783 | 36.992 | 9.658 | 56.353 |
| infer_ms | 924 | 6.665 | 6.298 | 8.929 | 10.518 | 5.119 | 14.005 |
| e2e_det_ms | 924 | 30.079 | 28.415 | 46.699 | 59.441 | 13.135 | 77.579 |
| pub_dt_ms | 924 | 51.672 | 51.659 | 91.724 | 98.011 | 0.403 | 99.803 |

### Achieved Hz (active-only window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 1049 | 22.846 |
| /target | 805 | 17.532 |
| /timing | 1078 | 23.477 |
| /timing_tracker | 0 | 0.000 |
| /tracks | 0 | 0.000 |

## Figures
- `reports/timing/phase3_replay_figures/e2e_det_ms_hist.png`
- `reports/timing/phase3_replay_figures/e2e_det_ms_cdf.png`
- `reports/timing/phase3_replay_figures/pub_dt_ms_hist.png`
- `reports/timing/phase3_replay_figures/pub_dt_ms_cdf.png`
