# Daily Plan - 2026-04-16 (Day 16) - Backend Submission Redesign Iteration

## Context Carry-Over

- Safe live baseline is frozen and operational:
  - async_max_inflight=1
  - hailo_use_videoconvert=true
  - allow_stub_fallback=false
  - tracker publish_timing_topic=false
  - camera publish 640x640 bgr8
- Closed branches (do not reopen without architecture change):
  - async_max_inflight=2
  - hailo_use_videoconvert=false
- First single-owner smoke was stable and clean, but no material latency/cadence win.

## Primary Objective

Deliver one deeper backend-path redesign iteration and evaluate it with strict evidence gates against the frozen baseline.

## Tomorrow To-Do (Priority Ordered)

### 1) Pre-run discipline and baseline lock

- [ ] Confirm no lingering live-stack processes before any run.
- [ ] Start stack with frozen baseline only (no extra tuning flags).
- [ ] Capture fresh 45 s baseline smoke artifact for same-session comparability.

### 2) Backend-path redesign iteration (single-owner model stays intact)

- [ ] Refine owner submission path so newest-frame semantics are explicit under load.
- [ ] Verify stale frames are dropped before infer (never queued for later processing).
- [ ] Add/verify minimal owner-path observability needed to reason about submit behavior (without adding hot-path overhead).

### 3) Controlled validation loop (no tuning sprawl)

- [ ] Run 45 s candidate smoke under matched scene/workload.
- [ ] Validate canonical schema and invariants.
- [ ] Compare candidate vs same-session baseline using only decision metrics:
  - /timing Hz
  - container_queue_ms p50/p95
  - e2e_det_ms p95/p99
  - pub_dt_ms p95/p99
  - infer_ms p95
  - detections_per_msg.mean
  - zero_ratio

### 4) Gate decision (hard rule)

- [ ] Proceed to 10 min confirmation only if all pass:
  - workload comparable
  - invariants clean
  - infer_ms roughly stable
  - container_queue_ms materially improved
  - e2e_det_ms materially improved
  - cadence not worse
- [ ] If any gate fails, stop and record no-go for the iteration.

### 5) End-of-day closure quality

- [ ] Update daily log with numeric evidence and explicit verdict.
- [ ] Update migration ledger with keep/drop decision.
- [ ] Keep baseline frozen unless confirmation run clearly passes.

## Practical Timebox

- Block A (start of day): baseline smoke + readiness checks
- Block B: implementation/refinement of backend-path change
- Block C: candidate smoke + gate decision
- Block D (conditional): 10 min confirmation run
- Block E: documentation and final decision write-up

## Definition of Done for 2026-04-16

At least one backend redesign iteration is fully evaluated with a clean keep/drop decision, and no ambiguous intermediate state remains in code, defaults, or logs.