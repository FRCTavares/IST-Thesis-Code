# Weekly Summary — T-31 (2026-03-16 to 2026-03-22)

## T-31 Theme: Integration Week

**Move from preparation to operational integration with measurable timing evidence.**

Early T-31 focus: integrate the full live ROS graph with dashboard tooling, harden one-command startup, and establish reliable timing ablation baselines before IST sessions.

---

## T-31 Objectives

By end of Day 22 (March 22), you should have:

### 1. **MAVROS Hardware Integration Validated**
   - Pi5 + Pixhawk connected via Ethernet
   - MAVROS launched and connected successfully
   - Perception + MAVROS + control running together
   - Setpoint flow to Pixhawk verified
   - Connection procedure documented and repeatable

### 2. **Control Pipeline Integrated End-to-End**
   - `control_ref_node` publishing to MAVROS topics
   - Setpoints respond to target detection/loss
   - Control signs validated with real hardware
   - Safety bounds working (command saturation, fail-safe zeroing)
   - Sustained operation without crashes

### 3. **Outdoor Operation Characterized** (weather/Tuesday-permitting)
   - Perception tested in outdoor environment
   - Detection performance vs distance documented
   - Environmental challenges identified (lighting, distance, occlusions)
   - Outdoor vs indoor performance comparison
   - Field operation experience gained

### 4. **Integration Lessons Documented**
   - What worked and what didn't
   - Setup time and logistics challenges
   - Hardware/software issues encountered
   - Solutions and workarounds documented
   - T-30 blockers identified

---

## Available Resources

**IST Field Sessions:**
- **Tuesday March 18:** 4 hours (primary MAVROS integration)
- **Thursday March 20:** 4 hours (outdoor validation or debugging)

**Equipment at IST:**
- Pixhawk 4 + drone frame
- 4-cell LiPo battery (confirmed ready)
- RC transmitter
- Tools for prop removal
- Outdoor football field access

**Bringing from home:**
- Raspberry Pi 5 + camera
- Laptop for SSH
- **Ethernet cable** (Pi5 ↔ Pixhawk) - CRITICAL
- All cables and accessories

---

## Weekly Goals Checklist

### Tuesday IST Session (Day 18)
- [ ] Physical setup: Pi5 + Pixhawk connected
- [ ] MAVROS launches and connects
- [ ] Perception pipeline runs alongside MAVROS
- [ ] Control node publishes setpoints (unarmed)
- [ ] Setpoints look reasonable and respond to targets
- [ ] Diagnostic bags recorded
- [ ] Integration issues documented

### Thursday IST Session (Day 20)
- [ ] Session plan finalized based on Tuesday
- [ ] Outdoor testing OR integration debugging
- [ ] Additional bags recorded
- [ ] Field operation experience documented

### Analysis and Documentation
- [ ] Tuesday bags analyzed
- [ ] Thursday bags analyzed (if applicable)
- [ ] Integration report written
- [ ] Outdoor performance characterized (if applicable)
- [ ] Lessons learned documented
- [ ] T-30 plan defined

---

## Daily Progress

### Day 16 (Sunday, 2026-03-16)
**Focus:** ROS graph + dashboard integration and one-command startup

**Planned:**
- Integrate live graph with frontend dashboard path
- Create one-command startup/stop flow
- Improve startup reliability and logging

**Completed:**
- Dashboard telemetry/video path integrated with live graph
- `tools/start_live_stack.sh` established as primary operational launch path
- Startup checks, port readiness checks, and cleanup behavior improved

**Issues:**
- Optional dashboard/video components add measurable runtime overhead for performance runs

---

### Day 17 (Monday, 2026-03-17)
**Focus:** Timing ablation and startup script hardening

**Planned:**
- Validate new timing instrumentation with live invariants
- Run first ablation matrix and identify bottlenecks
- Improve startup script mode controls and no-dashboard behavior

**Completed:**
- Added live timing invariant checker and timing stats collector
- Ran R1-R5 style ablation comparisons and produced bottleneck summary
- Improved startup script flags and no-dashboard transmission behavior
- Fixed target timing context fallback and confirmed e2e_target path

**Issues:**
- `pre_ms` remains too coarse for optimization targeting; requires sub-stage split
- tracker callback timing remains broad and should be split into compute/build/publish

---

### Day 18 (Tuesday, 2026-03-18)
**Focus:** IST Session 1 — MAVROS ground integration (4 hours)

**Session goals:**
- MAVROS connection validation
- Perception + MAVROS coexistence
- Control integration (unarmed)
- Diagnostic recording

**Completed:**
- *(To be filled at end of session)*

**Issues:**
- *(To be filled)*

**Tuesday success level:** *(Minimum / Target / Stretch)*

---

### Day 19 (Thursday, 2026-03-19)
**Focus:** First supervised flight attempt

**Planned:**
- Run final pre-flight and safety checks
- Execute short controlled assisted-flight windows
- Capture evidence and classify outcome
- Define immediate stabilization tasks

**Completed:**
- Weather risk decision held at NO-GO; no flight authority handover.
- Completed major ground-side throughput stabilization work:
   - container inference service refactor from REP to async ROUTER
   - inference client queue/worker tuning with runtime launch flags
   - blocking queue wakeup fix replacing deque polling + `sleep(0)`
- Established frozen Baseline B for next tests:
   - `queue_size=4`, `num_workers=3`, blocking queue behavior
- Captured live validation evidence and documented reproducible diagnostics in runbook.

**Issues:**
- Weather blocked supervised flight attempt.
- Remaining throughput variability appears upstream of container inference and needs isolated image-path comparison validation (`1920x1080->resize` vs direct `640x640`).

**Day 19 outcome:** aborted flight window (weather NO-GO), but successful ground stabilization with clear next bottleneck hypothesis.

---

### Day 20 (Friday, 2026-03-20)
**Focus:** Post-flight stabilization and blocker closure

**Session goals:**
- Build event timeline from first-flight logs
- Implement highest-impact fix(es)
- Re-validate on bench/unarmed
- Decide next-attempt scope with explicit gates

**Completed:**
- *(To be filled at end of session)*

**Issues:**
- *(To be filled)*

**Thursday success level:** *(Minimum / Target / Stretch)*

---

### Day 21 (Saturday, 2026-03-21)
**Focus:** Flight analysis and evidence packaging

**Planned:**
- Analyze all T-31 bags
- Generate reports
- Document lessons learned
- Update artefacts

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 22 (Sunday, 2026-03-22)
**Focus:** T-31 review and T-30 planning

**Planned:**
- Complete T-31 retrospective
- Assess readiness for next phase
- Identify blockers
- Plan T-30

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

## Key Results (to be filled at end of week)

### Throughput progression snapshot (Day 19)

| Stage | Main change | Typical outcome | Notes |
|---|---|---|---|
| Old broken state | serialized request/reply path and unstable client pacing | unstable with large jitter tails | poor consistency under live load |
| Async container refactor | REP -> ROUTER asynchronous in-flight handling | container `service_ms` moved to low-teens | server-side bottleneck removed |
| Multi-worker + deeper queue | increased client concurrency and queue depth | tuned runs reached ~21.3 FPS | meaningful throughput uplift from baseline |
| Blocking queue fix | replaced deque polling + `sleep(0)` with blocking timeout wakeup | idle behavior became bounded and less pathological | busy-yield contention removed |
| Final stable live baseline (Baseline B) | queue=4, workers=3, blocking queue behavior frozen | stable windows observed in high-teens to low-20s FPS range depending on load | next gate is single-variable image-path comparison (`1920x1080->resize` vs direct `640x640`) |

### MAVROS Integration
- Connection established: *(yes / no / partial)*
- Connection method: *(Ethernet UDP confirmed / other)*
- Pixhawk IP: *(value)*
- Setpoint rate achieved: *(value)* Hz
- Integration stability: *(stable / issues noted)*

### Control Pipeline
- Setpoints published to MAVROS: *(yes / no)*
- Target detection → control response: *(validated / issues)*
- Control signs validated: *(yes / no / partial)*
- Safety bounds working: *(confirmed / issues)*
- Sustained operation: *(duration)* minutes

### Outdoor Operation
- Outdoor testing completed: *(yes / no / deferred)*
- Location: *(IST football field / other)*
- Detection performance: *(characterized / not tested)*
- Environmental challenges: *(list)*
- Outdoor vs indoor comparison: *(completed / not applicable)*

### Integration Lessons
- Major challenges: *(list)*
- Solutions found: *(list)*
- Time spent: Tuesday *(hours)*, Thursday *(hours)*
- Setup efficiency: *(as expected / longer / issues)*

### T-30 Readiness
- Ready for next phase: *(yes / no / conditional)*
- Blockers identified: *(none / list)*
- Next priority: *(to be determined)*

---

## Issues and Risks

### Known Blockers Going Into T-31
- ❌ MAVROS untested (first time with real hardware)
- ⚠️ Ethernet connection untested
- ⚠️ No indoor backup (weather-dependent for Thursday)
- ⚠️ 4-hour sessions may be tight for debugging

### Issues Encountered During T-31
Documented through Day 19:

**Tuesday session:**
- MAVROS hardware integration outcomes still pending final weekly closure entry.

**Thursday session:**
- Weather blocked first supervised flight window (NO-GO maintained).
- Throughput remains below camera source-rate in some runs despite healthy container-side latency.
- `ros2 topic hz` under-reports BEST_EFFORT camera stream in this Jazzy setup; camera source-rate validation must rely on `/camera/fps`.

**Mitigation actions:**
- Freeze Baseline B and enforce one-variable-at-a-time paired comparison testing.
- Run image-path comparison (`1920x1080->resize` vs direct `640x640`) before additional tuning.
- Re-test full stack without rosbag first, then run separate profiling bag capture.

---

## T-31 Retrospective (to be filled at end of week)

### What Worked Well
- *(To be filled)*

### What Didn't Work
- *(To be filled)*

### Key Learnings
- *(To be filled)*

### Critical Insights for Future Work
- *(To be filled)*

### Adjustments for T-30
- *(To be filled)*

---

## T-30 Preview (to be defined after T-31)

**Depends on T-31 outcomes:**

**If first-flight attempt was successful:**
- T-30 focus: *(repeatability, robustness, gradual envelope expansion)*

**If first-flight was partial/aborted:**
- T-30 focus: *(blocker closure, fault containment, conservative re-attempt)*

**If field testing was deferred:**
- T-30 focus: *(readiness gate completion and supervised field window scheduling)*

---

**Week status:** In progress  
**Overall success:** Pending final T-31 closure (ground stabilization successful; flight window deferred by weather)
