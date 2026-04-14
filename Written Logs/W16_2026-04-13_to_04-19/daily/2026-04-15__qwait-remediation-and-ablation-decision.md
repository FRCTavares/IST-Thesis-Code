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
- file: `reports/timing/qwait_base_20260414_233907.json`
- `/timing` Hz: 8.879
- `container_queue_ms` mean/p95: 98.101 / 118.688
- `e2e_det_ms` p95: 199.869
- `pub_dt_ms` p95: 200.977
- detections mean/zero_ratio: 1.111 / 0.002

Candidate run (videoconvert off):

- label: `qwait_novc_20260414_235106`
- file: `reports/timing/qwait_novc_20260414_235106.json`
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

- Re-run queue-depth 1-vs-2 comparison (`hailo_queue_max_buffers` 1 vs 2) under this frozen baseline and only keep variants that improve `container_queue_ms` without reducing `/timing` Hz.

Outcome: the no-videoconvert candidate is rejected; baseline remains stable and evidence-backed.
