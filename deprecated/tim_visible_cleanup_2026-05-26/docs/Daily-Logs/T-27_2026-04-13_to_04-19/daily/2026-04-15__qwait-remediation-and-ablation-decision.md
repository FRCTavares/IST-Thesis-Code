# Daily Log - 2026-04-15 (Day 15) - q_wait Remediation Validation and Decision Freeze

## Overview

Focus: close the current optimization cycle with measurable pre-infer queue-wait improvements, controlled baseline-vs-candidate evidence, and a clear keep/drop decision for the videoconvert on-vs-off comparison.

## Goals for Today

- [x] Keep q_wait visible in standard run artefacts through canonical metrics.
- [x] Finalize launcher controls for controlled videoconvert on-vs-off comparison without code edits.
- [x] Run baseline and no-videoconvert candidate under the same scene/workload.
- [x] Validate schema and workload comparability before selecting or dropping the candidate.

## Work Completed

### 1) Perception-path implementation and instrumentation closure

- Integrated async latest-frame processing path in the perception pipeline and kept it as the default operational mode.
- Promoted pre-infer queue wait to canonical metric `container_queue_ms` on `/timing`.
- Kept validator compatibility for legacy JSON artefacts that predate `container_queue_ms`.

### 2) Launcher and workflow controls

- Added explicit runtime controls in `tools/start_live_stack.sh`:
  - `--perception-async-latest-frame-on|off`
  - `--perception-hailo-videoconvert-on|off`
- Updated runbook workflow to include q_wait-focused baseline-vs-candidate validation steps.

### 3) Live validation runs (10 min each)

Baseline run:

- label: `qwait_base_20260414_233907`
- file: `artifacts/reports/timing/qwait_base_20260414_233907.json`
- `/timing` Hz: 8.879
- `container_queue_ms` mean/p95: 98.101 / 118.688
- `e2e_det_ms` p95: 199.869
- `pub_dt_ms` p95: 200.977
- detections mean/zero_ratio: 1.111 / 0.002

Candidate run (videoconvert off):

- label: `qwait_novc_20260414_235106`
- file: `artifacts/reports/timing/qwait_novc_20260414_235106.json`
- `/timing` Hz: 8.804
- `container_queue_ms` mean/p95: 95.758 / 113.697
- `e2e_det_ms` p95: 196.103
- `pub_dt_ms` p95: 199.627
- detections mean/zero_ratio: 1.005 / 0.002

Validation:

- Canonical metrics schema: PASS
- Workload comparability gate: PASS (`det mean` relative delta 0.0956, `zero_ratio` delta 0.0008)

### 4) Decision

- Candidate verdict: DROP
- Reason: queue-wait and tail metrics improved slightly, but `/timing` throughput regressed (8.879 -> 8.804) and gains were not strong enough to justify a baseline change.
- Active baseline remains:
  - async latest-frame ON
  - pre-hailonet videoconvert ON

## Deliverables Produced

- [x] Perception q_wait instrumentation and canonical contract updates
- [x] Launcher controls for explicit async/videoconvert comparisons
- [x] Two comparable 10-minute timing artefacts with explicit keep/drop verdict
- [x] Updated migration/runbook status documentation for next-session continuity

## End of Day Review

Completed:

- Closed one full implementation + measurement + decision loop for q_wait remediation.
- Preserved evidence quality (schema pass + comparability pass) before decision.
- Froze stable baseline for the next experiment cycle.

Open next step:

- Continue backend-path redesign below Python-side policy level (engine ownership/submission path and integration strategy), then revalidate against the frozen baseline.

Outcome: the no-videoconvert candidate is rejected; baseline remains stable and evidence-backed.

## Late Session Update - Branch Closure and Redesign Reality Check

### Frozen safe live baseline (enforced in code + launcher defaults)

- `async_max_inflight=1`
- `hailo_use_videoconvert=true`
- `allow_stub_fallback=false`
- tracker `publish_timing_topic=false`
- camera publish shape `640x640` (`bgr8`)

### What today proved clearly

1. Preprocessing is no longer the main bottleneck.
2. `async_max_inflight=2` is bad on this backend path.
3. First single-owner redesign iteration did not materially beat the frozen baseline.

This is not a good performance result, but it is a good engineering result: uncertainty was reduced with clean, comparable evidence.

### Closed tuning branches

- Rejected: multi-caller in-flight path (`async_max_inflight=2`) on current backend ownership model.
- Rejected: `hailo_use_videoconvert=false` on current backend path.

### Single-owner redesign smoke validation (45 s)

Run:

- `owner_validate_20260415_230120`
- timing: `artifacts/reports/timing/owner_validate_20260415_230120_smoke_45s.json`
- invariants: `artifacts/reports/timing/owner_validate_20260415_230120_smoke_45s_invariants.log`

Against frozen baseline (`vc_ablation_20260415_223635_A_on`):

- `/timing` Hz: `9.732 -> 9.655` (not improved)
- `container_queue_ms` p95: `106.799 -> 107.499` (not improved)
- `e2e_det_ms` p95: `115.654 -> 117.302` (not improved)
- `infer_ms` p95: `8.688 -> 8.542` (stable/slightly better)
- workload comparability: PASS (`detections_per_msg.mean`, `zero_ratio`)
- invariants: clean

Decision:

- NO-GO for 10-minute confirmation on this iteration.

### Thesis-relevant conclusion for this checkpoint

Safe live baseline remains operational default.
Preprocessing bottleneck has been reduced.
Backend-path contention/ownership remains the dominant limiter.
Next gains require deeper backend-path redesign or different engine integration strategy, not more launch-flag tuning.
