# Single-Owner Redesign Smoke Summary

Run tag: owner_validate_20260415_230120
Date: 2026-04-15

## Configuration

- perception_mode: single-process
- async_max_inflight: 1
- hailo_use_videoconvert: true
- allow_stub_fallback: false
- tracker publish_timing_topic: false
- camera publish: 640x640 bgr8

Artifacts:

- Timing JSON: reports/timing/owner_validate_20260415_230120_smoke_45s.json
- Invariants log: reports/timing/owner_validate_20260415_230120_smoke_45s_invariants.log
- Comparison baseline: reports/timing/vc_ablation_20260415_223635_A_on.json

## Smoke Metrics (45s)

- /timing Hz: 9.655
- container_queue_ms p50/p95/p99: 93.351 / 107.499 / 164.603
- e2e_det_ms p95/p99: 117.302 / 180.468
- pub_dt_ms p95/p99: 118.381 / 170.574
- infer_ms p95: 8.542
- detections_per_msg.mean: 1.000
- zero_ratio: 0.000

## Delta vs Frozen Baseline (A_on)

- /timing Hz: 9.732 -> 9.655 (worse)
- container_queue_ms p95: 106.799 -> 107.499 (worse)
- e2e_det_ms p95: 115.654 -> 117.302 (worse)
- e2e_det_ms p99: 177.754 -> 180.468 (worse)
- pub_dt_ms p95: 118.695 -> 118.381 (roughly flat)
- pub_dt_ms p99: 148.489 -> 170.574 (worse)
- infer_ms p95: 8.688 -> 8.542 (stable/slightly better)
- detections_per_msg.mean: 1.043 -> 1.000 (comparable)
- zero_ratio: 0.000 -> 0.000 (comparable)

## Gate Decision

- workload comparable: PASS
- invariants clean: PASS
- infer_ms stable: PASS
- cadence improved materially: FAIL
- container_queue_ms improved materially: FAIL
- e2e_det_ms improved materially: FAIL

Verdict: NO-GO for 10-minute confirmation on this iteration. Keep frozen baseline and iterate backend owner-path implementation before rerunning long confirmation.