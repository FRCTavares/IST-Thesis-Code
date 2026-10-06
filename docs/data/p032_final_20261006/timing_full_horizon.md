# Timing Summary: 2026-10-06__14-52-31__video__p032_final_mounted_vga
Bag: `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga`
Timing vocabulary: canonical fields only (`pub_dt_ms` is the cadence metric).
Contract schema: `v4`
- metric_windows: `{'det_out_fps_seconds': 3.0}`
- metric_thresholds_ms: `{'e2e_det_ms': 120.0, 'pub_dt_ms': 120.0, 'pre_infer_wait_ms': 100.0, 'infer_ms': 20.0, 'track_ms': 25.0}`
Base window: first to last `/timing` message (bag timestamps)
- start_ns: `1791294788444350276`
- end_ns: `1791296243148441782`
- duration_s: `1454.704`
## Per-field stats (/timing)
| field | n | mean | std | p50 | p90 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ros_wait_ms | 40520 | 7.889 | 10.313 | 2.470 | 24.176 | 27.845 | 37.132 | 0.037 | 83.842 |
| pre_ms | 40520 | 8.798 | 4.973 | 7.519 | 15.479 | 18.188 | 24.629 | 1.647 | 62.533 |
| ros_to_np_ms | 40520 | 0.056 | 0.112 | 0.047 | 0.065 | 0.084 | 0.143 | 0.028 | 7.172 |
| resize_ms | 40520 | 7.567 | 4.740 | 6.327 | 13.930 | 16.719 | 22.515 | 1.147 | 53.600 |
| color_ms | 40520 | 1.169 | 2.177 | 0.466 | 3.152 | 5.194 | 11.729 | 0.307 | 59.784 |
| pre_infer_wait_ms | 40520 | 1.089 | 1.945 | 0.506 | 2.708 | 4.532 | 9.990 | 0.348 | 59.773 |
| infer_ms | 40520 | 20.244 | 5.502 | 19.015 | 27.269 | 30.368 | 38.153 | 11.258 | 82.586 |
| post_ms | 40520 | 0.082 | 0.158 | 0.072 | 0.090 | 0.109 | 0.183 | 0.039 | 16.665 |
| det_pub_ms | 40520 | 1.056 | 1.610 | 0.509 | 2.659 | 3.614 | 7.979 | 0.194 | 37.201 |
| e2e_det_ms | 40520 | 39.195 | 14.201 | 34.522 | 59.928 | 66.754 | 79.893 | 13.984 | 136.839 |
| pub_dt_ms | 40520 | 35.903 | 9.162 | 34.466 | 47.110 | 51.882 | 66.675 | 16.138 | 124.970 |

## Achieved Hz (counts over base window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 40519 | 27.854 |
| /target | 40474 | 27.823 |
| /timing | 40520 | 27.854 |
| /timing_tracker | 40497 | 27.839 |
| /tracks | 40497 | 27.839 |

## Active-only window (gap-filtered)
Definition: samples with `pub_dt_ms <= 1260000.0` ms
- start_ns: `1791294788444350276`
- end_ns: `1791296243148441782`
- duration_s: `1411.350`
- gap_count: `0`
- gap_removed_s: `43.354`
- dropped_samples: `0`

### Per-field stats (/timing), active-only
| field | n | mean | std | p50 | p90 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ros_wait_ms | 40520 | 7.889 | 10.313 | 2.470 | 24.176 | 27.845 | 37.132 | 0.037 | 83.842 |
| pre_ms | 40520 | 8.798 | 4.973 | 7.519 | 15.479 | 18.188 | 24.629 | 1.647 | 62.533 |
| ros_to_np_ms | 40520 | 0.056 | 0.112 | 0.047 | 0.065 | 0.084 | 0.143 | 0.028 | 7.172 |
| resize_ms | 40520 | 7.567 | 4.740 | 6.327 | 13.930 | 16.719 | 22.515 | 1.147 | 53.600 |
| color_ms | 40520 | 1.169 | 2.177 | 0.466 | 3.152 | 5.194 | 11.729 | 0.307 | 59.784 |
| pre_infer_wait_ms | 40520 | 1.089 | 1.945 | 0.506 | 2.708 | 4.532 | 9.990 | 0.348 | 59.773 |
| infer_ms | 40520 | 20.244 | 5.502 | 19.015 | 27.269 | 30.368 | 38.153 | 11.258 | 82.586 |
| post_ms | 40520 | 0.082 | 0.158 | 0.072 | 0.090 | 0.109 | 0.183 | 0.039 | 16.665 |
| det_pub_ms | 40520 | 1.056 | 1.610 | 0.509 | 2.659 | 3.614 | 7.979 | 0.194 | 37.201 |
| e2e_det_ms | 40520 | 39.195 | 14.201 | 34.522 | 59.928 | 66.754 | 79.893 | 13.984 | 136.839 |
| pub_dt_ms | 40520 | 35.903 | 9.162 | 34.466 | 47.110 | 51.882 | 66.675 | 16.138 | 124.970 |

### Achieved Hz (active-only window)
| topic | count | Hz |
|---|---:|---:|
| /detections | 40297 | 28.552 |
| /target | 39989 | 28.334 |
| /timing | 40411 | 28.633 |
| /timing_tracker | 39968 | 28.319 |
| /tracks | 39917 | 28.283 |

## Tracker runtime
Topic: `/timing_tracker` (field: `track_ms`)
| metric | value |
|---|---:|
| n | 39968 |
| mean (ms) | 7.431 |
| std (ms) | 3.953 |
| p50 (ms) | 6.941 |
| p90 (ms) | 11.893 |
| p95 (ms) | 14.037 |
| p99 (ms) | 20.085 |
| max (ms) | 56.114 |

Active-only Hz (tracker timing): `28.319`

## Target end-to-end runtime
Topic: `/timing_target` (field: `e2e_validated_target_ms`)
| metric | value |
|---|---:|
| n | 39837 |
| mean (ms) | 78.294 |
| std (ms) | 34.319 |
| p50 (ms) | 69.535 |
| p90 (ms) | 129.672 |
| p95 (ms) | 142.128 |
| p99 (ms) | 168.836 |
| max (ms) | 350.669 |

Active-only Hz (target timing): `28.226`

## Figures
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/e2e_det_ms_hist.png`
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/e2e_det_ms_cdf.png`
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/pub_dt_ms_hist.png`
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/pub_dt_ms_cdf.png`
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/track_ms_hist.png`
- `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga/timing_figures/track_ms_cdf.png`
