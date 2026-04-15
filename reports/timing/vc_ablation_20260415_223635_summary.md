# Paired Videoconvert Ablation Summary

Pair ID: `vc_ablation_20260415_223635`
Date: 2026-04-15

## Setup (matched A/B)

- Common settings: `perception-mode=single-process`, `async_max_inflight=1`, `allow_stub_fallback=false`, `publish_timing_topic=false`
- A: `hailo_use_videoconvert=true`
- B: `hailo_use_videoconvert=false`
- Duration: 45 s each, back-to-back in same session

Artifacts:

- A timing: `reports/timing/vc_ablation_20260415_223635_A_on.json`
- A invariants: `reports/timing/vc_ablation_20260415_223635_A_on_invariants.log`
- B timing: `reports/timing/vc_ablation_20260415_223635_B_off.json`
- B invariants: `reports/timing/vc_ablation_20260415_223635_B_off_invariants.log`

## Decision Metrics (B - A)

| Metric | A (on) | B (off) | Delta (B-A) | Delta % |
|---|---:|---:|---:|---:|
| `/timing` Hz | 9.732 | 9.599 | -0.133 | -1.37% |
| `container_queue_ms` p50 | 93.701 | 91.037 | -2.664 | -2.84% |
| `container_queue_ms` p95 | 106.799 | 110.149 | +3.349 | +3.14% |
| `e2e_det_ms` p95 | 115.654 | 121.875 | +6.221 | +5.38% |
| `e2e_det_ms` p99 | 177.754 | 179.649 | +1.896 | +1.07% |
| `pub_dt_ms` p95 | 118.695 | 159.996 | +41.301 | +34.80% |
| `pub_dt_ms` p99 | 148.489 | 196.542 | +48.053 | +32.36% |
| `infer_ms` p95 | 8.688 | 8.439 | -0.249 | -2.86% |
| `detections_per_msg.mean` | 1.043 | 1.000 | -0.043 | -4.17% |
| `zero_ratio` | 0.000 | 0.000 | +0.000 | n/a |

## Invariants / Workload Gate

- Invariants: no non-zero fail counters found in either A or B logs.
- Workload comparability: acceptable (`detections_per_msg.mean` delta 0.043, `zero_ratio` unchanged at 0.0).

## Verdict

`hailo_use_videoconvert=false` is **not** a keeper on this backend path.

Reasons:

- No material queue-wait improvement (`container_queue_ms` p95 worsened).
- End-to-end detection latency worsened (`e2e_det_ms` p95/p99 both higher).
- Cadence dipped slightly.
- Publication tails regressed substantially (`pub_dt_ms` p95/p99).

Operational decision: keep `hailo_use_videoconvert=true` as default and prioritize backend-path redesign over further videoconvert flag tuning.
