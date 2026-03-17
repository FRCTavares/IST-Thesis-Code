# Weekly Summary — W12 (2026-03-16 to 2026-03-22)

## Week 12 Theme: Integration Week

**Move from preparation to operational integration with measurable timing evidence.**

Early W12 focus: integrate the full live ROS graph with dashboard tooling, harden one-command startup, and establish reliable timing ablation baselines before IST sessions.

---

## Week 12 Objectives

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
   - W13 blockers identified

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
- [ ] W13 plan defined

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
- *(To be filled)*

**Issues:**
- *(To be filled)*

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
- Analyze all W12 bags
- Generate reports
- Document lessons learned
- Update artefacts

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 22 (Sunday, 2026-03-22)
**Focus:** Week 12 review and W13 planning

**Planned:**
- Complete W12 retrospective
- Assess readiness for next phase
- Identify blockers
- Plan W13

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

## Key Results (to be filled at end of week)

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

### W13 Readiness
- Ready for next phase: *(yes / no / conditional)*
- Blockers identified: *(none / list)*
- Next priority: *(to be determined)*

---

## Issues and Risks

### Known Blockers Going Into W12
- ❌ MAVROS untested (first time with real hardware)
- ⚠️ Ethernet connection untested
- ⚠️ No indoor backup (weather-dependent for Thursday)
- ⚠️ 4-hour sessions may be tight for debugging

### Issues Encountered During W12
*(To be filled as discovered)*

**Tuesday session:**
- 

**Thursday session:**
-

**Mitigation actions:**
-

---

## Week 12 Retrospective (to be filled at end of week)

### What Worked Well
- *(To be filled)*

### What Didn't Work
- *(To be filled)*

### Key Learnings
- *(To be filled)*

### Critical Insights for Future Work
- *(To be filled)*

### Adjustments for W13
- *(To be filled)*

---

## W13 Preview (to be defined after W12)

**Depends on W12 outcomes:**

**If first-flight attempt was successful:**
- W13 focus: *(repeatability, robustness, gradual envelope expansion)*

**If first-flight was partial/aborted:**
- W13 focus: *(blocker closure, fault containment, conservative re-attempt)*

**If field testing was deferred:**
- W13 focus: *(readiness gate completion and supervised field window scheduling)*

---

**Week status:** *(In progress / Complete)*  
**Overall success:** *(To be assessed at end of week)*
