# Daily Log — 2026-03-19 (Day 19) — First Flight Attempt

## Overview

**Focus:** First supervised flight attempt with strict safety envelope and immediate rollback path.

**Result:** Flight window not executed due to bad weather (NO-GO maintained).

**Gate rule:** No flight authority handover until all pre-flight closure gates below are green.

---

## Mission Objective

- Execute first controlled flight attempt.
- Keep risk low: short windows, clear abort criteria, RC-first authority.
- End with actionable evidence for next iteration regardless of outcome.

---

## Work Completed Today (Ground Validation + Throughput Debug)

- Deep end-to-end bottleneck analysis across camera -> inference client -> container service -> detections path.
- Added detailed timing instrumentation and controlled test methodology to isolate where throughput was being lost.
- Ran multiple controlled paired-comparison tests on stack toggles and client/service behavior.
- Identified container request/response architecture as a major limiting factor in earlier runs.
- Refactored container inference service from synchronous REP pattern to asynchronous ROUTER flow with decoupled receive/process/reply behavior.
- Increased container buffering and non-blocking appsrc behavior to reduce serialization pressure.
- Tuned inference client queue/worker behavior and exposed run-time launch flags for rapid paired-comparison testing.

### Key Code/Runtime Changes Applied

- Container service (`detection_zmq.py`):
	- REP -> ROUTER
	- asynchronous event loop for in-flight handling
	- identity-based delayed replies
	- request-cycle profiling (`reqrep_prof`) retained for verification
- Inference client (`inference_client_node.py`):
	- replaced latest-only pop/clear behavior with FIFO consumption
	- replaced deque polling + `sleep(0)` idle path with bounded blocking queue (`queue.Queue`) and `get(timeout)` wakeup
	- preserved freshness policy under pressure by dropping oldest then enqueueing newest frame
- Launch script (`start_live_stack.sh`):
	- added `--infer-queue-size <N>`
	- added `--infer-workers <N>`
	- wired these to inference node params for repeatable matrix tests

### What We Discovered

- Earlier bottleneck was dominated by serialized request cycle behavior in container service.
- After service refactor, container `service_ms` dropped to low-teens in most samples (healthy headroom).
- Throughput improved significantly with client queue/worker tuning:
	- baseline (`queue_size=1`, `workers=2`) ~17.3 FPS sustained
	- tuned (`queue_size=3`, `workers=4`) ~21.3 FPS sustained
	- net gain ~+23%
- Remaining constraint appears to be upstream pacing/jitter (camera/client side), not Hailo infer stage itself.

### Current Technical Status

- Ground pipeline is materially more stable and faster than start-of-day baseline.
- Additional verification remains (camera publish-rate consistency and final queue/worker operating point selection).
- Ready for next stabilization cycle before attempting flight authority handover.

### Live Validation Snapshot (current running session)

- Inference behavior remained stable over a long live window after blocking-queue refactor.
- Recent sampled window from inference log:
	- `window_s=128.51`
	- `sent_delta=2340`
	- `fps_est=18.21`
	- `avg_pub_dt_p95_ms=115.50`
	- `avg_lat_ms=28.58`
- Most recent log lines tightened relative to earlier spikes:
	- `pub_dt_p50_ms` mostly ~46-49
	- `pub_dt_p95_ms` mostly ~97-104
	- `lat_ms` mostly ~19-34
	- `rt_ms` mostly ~13-24
	- `drop` stayed 0
- Empty-poll progression matches blocking timeout behavior rather than busy spin:
	- `empty_polls` rose from 45089 to 48472 over ~36s (~94/s)
	- with 3 workers and 20 ms timeout, theoretical ceiling ~150/s, so observed values are consistent with blocking waits.
- Live rates observed:
	- `/detections` about ~21 Hz (std ~0.018 s)
	- `/camera/fps` reported ~29.6 FPS
	- `/camera/image_raw` via `ros2 topic hz` appeared lower in this setup, likely undercounting BEST_EFFORT sensor stream.
- Container profiler visibility issue in this run:
	- `reqrep_prof` lines were not present in `/tmp/detection_zmq_live.log`
	- client-side `rt_ms` staying in teens/low-20s still suggests service path remained healthy.

### Thesis-grade progression summary (today)

| Stage | Main change | Typical outcome | Notes |
|---|---|---|---|
| Old broken state | serialized request/reply path and unstable client pacing | unstable with large jitter tails | frequent pacing spikes and poor consistency |
| Async container refactor | REP -> ROUTER asynchronous in-flight handling | container `service_ms` moved to low-teens | removed server-side serialization bottleneck |
| Multi-worker + deeper queue | increased client concurrency and queue depth | sustained throughput improved to ~21.3 FPS in tuned runs | reduced starvation relative to baseline |
| Blocking queue fix | replaced deque polling + `sleep(0)` with blocking queue timeout wakeup | empty-poll behavior became bounded and predictable | removed busy-yield contention pattern |
| Final stable live baseline (Baseline B) | queue=4, workers=3, blocking queue behavior frozen | stable live windows observed; representative run around high-teens to low-20s FPS depending on load | next decision gate is image-path comparison (`1920x1080->resize` vs direct `640x640`) |

### End-of-day freeze and next execution order

- Baseline B is frozen for comparisons:
	- `queue_size=4`
	- `num_workers=3`
	- blocking queue wakeup behavior retained
- Next tests must change one variable only:
	- focused image-path comparison (`1920x1080->resize` vs direct `640x640` publish with resize bypass)
- Full-pipeline re-test order:
	1) no-rosbag functional run with tracker + target enabled
	2) separate rosbag profiling run after functional stability is confirmed

---

## Pre-Flight Closure Gates (Must Pass First)

- [ ] **Sign matrix complete:**
	- right target (`cx > 339`) produces `angular.z > 0`
	- far target (`h < 160`) produces `linear.x > 0`
- [ ] **Endurance evidence:** one clean 20+ min integrated unarmed run recorded and analyzed
- [ ] **Safety rehearsal evidence:** RC override test + emergency stop sequence rehearsed and logged

**If any gate is open:** remain `NO-GO` for flight authority and continue ground validation only.

---

## Session Plan (4h)

### Hour 1 — Pre-Flight and Safety Brief
- [ ] Final hardware check (battery, props, links, telemetry)
- [ ] Launch stack and verify critical topics
- [ ] Close remaining pre-flight closure gates above
- [ ] Supervisor confirms flight envelope and abort triggers

### Hour 2 — Controlled Flight Window A
- [x] Proceed only if all pre-flight gates are green
	- Not satisfied in practice; weather and risk envelope forced NO-GO.
- [ ] Takeoff and stabilization under manual control
- [ ] Enable assisted behavior in short bursts
- [ ] Monitor command bounds and target stability
- [ ] Land and review immediately

### Hour 3 — Controlled Flight Window B (Conditional)
- [ ] Repeat only if Window A is clean
- [ ] Increase duration slightly (still conservative)
- [ ] Capture data for timing/control analysis

### Hour 4 — Debrief and Decision
- [x] Classify outcome: success / partial / aborted
- [x] Record root causes for any anomaly
- [x] Define Friday stabilization tasks

Outcome from session:
- Flight classification: **aborted (weather NO-GO)**
- Technical ground-testing outcome: **successful performance progress with clear next bottleneck direction**

---

## Hard Safety Rules

- [ ] RC pilot retains authority at all times
- [ ] Abort on any command instability or sensor ambiguity
- [ ] Stop if telemetry link quality degrades
- [ ] No schedule pressure overrides safety decision

---

## Outcome Template

**Flight outcome:** aborted (weather NO-GO)

**What worked:**
- Structured bottleneck isolation and instrumentation approach.
- Container service architecture refactor removed previous serialization-heavy behavior.
- Throughput improved from ~17.3 FPS to ~21.3 FPS in controlled runs.
- Logging and launch tunables now support fast, repeatable paired-comparison tests.

**What failed or degraded:**
- Flight attempt could not proceed due to bad weather conditions.
- Some residual throughput jitter remains upstream (camera/client pacing variance).

**Immediate corrective actions (Friday):**
- Run focused image-path comparison with frozen Baseline B settings and compare FPS, `lat_ms`, `pre_ms`, `resize_ms`, `pub_dt_p50_ms`, `pub_dt_p95_ms`.
- Re-test full stack (tracker + target) first without rosbag, then repeat as separate profiling run with recording enabled.
- Stop further micro-tuning unless direct `640x640` path materially improves toward mid/high-20s FPS; otherwise classify next bottleneck as camera/ROS transport overhead.

---

## Artefacts

- [x] Logs from ground validation and throughput experiments
- [x] Timing snapshots from inference client and container profiler
- [x] Short no-flight summary linked in weekly log

---

## Go/No-Go Decision

- Final decision for today: **NO-GO (weather)**
- Rationale: preserve safety envelope; continue with ground stabilization and evidence collection.
