# Weekly Summary — W11 (2026-03-09 to 2026-03-15)

## Week 11 Ambition Targets (by end of Mar 15)

Move from "frozen baseline with live camera" to "outdoor-validated system ready for flight control."

By end of Day 15 (March 15), you should have:

1. **Live camera validated and stable**
   - ≥15 Hz sustained for 5+ minute runs
   - End-to-end latency with live camera quantified
   - Thermal and memory stability confirmed

2. **Outdoor perception validated**
   - Tennis court test runs completed with multi-person scenarios
   - Real-world detection and tracking performance measured
   - Outdoor-specific issues identified and documented (lighting, distance, occlusions)

3. **Outdoor test protocol executed**
   - 6 tennis court scenarios run and analyzed
   - Success criteria measured: pixel error, reacquisition time, ID switches, latency
   - Thesis-ready outdoor test report generated

4. **Control pipeline integrated (ground validation)**
   - `control_ref_node` outputs MAVROS setpoints
   - Control message flow validated end-to-end
   - Safety mechanisms implemented and tested

5. **Flight test readiness assessed**
   - Pre-flight safety checklist finalized
   - All safety mechanisms validated
   - GO/NO-GO decision for W12 first flight

**System requirements (unchanged):**
- Outdoor tennis court target environment
- Full online processing
- 15 FPS perception, 30 Hz control
- Latency budget: p95 ≤ 200 ms
- Multi-person robustness with target lock

**New validation targets:**
- Live camera sustained performance: 5+ min at ≥15 Hz
- Outdoor detection rate: ≥90% when target in frame and visible
- Outdoor tracking continuity: ≥80% time locked in multi-person scenarios
- Target reacquisition: ≤1.0 s after temporary occlusion
- Control update rate: 30 Hz with <5% jitter

---

## Goals for the week
- [ ] Complete W10 freeze and validate live camera performance
- [ ] Prove live camera stability under extended runs (5+ min)
- [ ] Execute first outdoor perception test (tennis court, multi-person)
- [ ] Run full outdoor test protocol with quantified results
- [ ] Integrate control_ref with MAVROS (ground validation only)
- [ ] Implement and validate all safety mechanisms (bounds, loss behavior, emergency stop)
- [ ] Finalize pre-flight checklist with safety procedures
- [ ] Generate outdoor test reports with thesis-ready data
- [ ] Assess flight test readiness and plan W12

---

## Daily Progress (to be filled during the week)

### Day 09 (Sunday, 2026-03-09)
**Focus:** Complete W10 freeze, validate live camera

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 10 (Monday, 2026-03-10)
**Focus:** Live camera stability and timing under load

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 11 (Tuesday, 2026-03-11)
**Focus:** First outdoor perception test

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 12 (Wednesday, 2026-03-12)
**Focus:** Outdoor test protocol execution

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 13 (Thursday, 2026-03-13)
**Focus:** Control integration and ground demo

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 14 (Friday, 2026-03-14)
**Focus:** Pre-flight safety validation

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 15 (Saturday, 2026-03-15)
**Focus:** Week review and flight test planning

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

## Key Results (to be filled at end of week)

### Live Camera Performance
- Sustained FPS: *(value)* Hz over *(duration)* min
- End-to-end latency: mean *(value)* ms, p95 *(value)* ms
- Stability issues: *(none / describe)*

### Outdoor Perception
- Test location: *(tennis court / other)*
- Scenarios tested: *(count and types)*
- Detection rate: *(percentage)* when target visible
- Tracking continuity: *(percentage)* time locked
- Reacquisition time: median *(value)* s, p95 *(value)* s

### Control Integration
- MAVROS interface: *(completed / in progress)*
- Control update rate: *(value)* Hz
- Safety mechanisms: *(list validated items)*

### Flight Readiness
- Decision: *(GO / NO-GO for W12)*
- Blocking issues: *(none / list)*
- Remaining work: *(none / list)*

---

## Issues and Risks

### Critical Issues
*(To be filled if any critical blocking issues arise)*

### Risk Updates
*(Update risk register as issues are discovered or mitigated)*

---

## Week 11 Retrospective (to be filled at end of week)

### What Worked Well
- *(To be filled)*

### What Didn't Work
- *(To be filled)*

### Key Learnings
- *(To be filled)*

### Adjustments for W12
- *(To be filled)*
