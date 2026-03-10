# Weekly Summary — W11 (2026-03-09 to 2026-03-15)

## Week 11 Ambition Targets (by end of Mar 15)

Move from "live camera validated indoors" to "lean operational perception validated outdoors and connected to the ground control interface."

By end of Day 15 (March 15), you should have:

1. **Live perception operational mode frozen and validated**
   - Lean live configuration frozen and documented
   - Sustained live performance demonstrated at or above 15 Hz over extended runs
   - End-to-end latency, thermal behaviour, and memory stability quantified

2. **First outdoor perception validation completed**
   - Tennis court exploratory tests completed with single-person and multi-person scenarios
   - Real-world issues documented: lighting, distance, occlusions, target size limits
   - Clear conclusion on what the current perception stack can reliably do outdoors

3. **Outdoor protocol either executed or made execution-ready**
   - Scenario definitions, bag naming, and field checklist finalized
   - At least one structured outdoor scenario set completed if logistics allow
   - If logistics do not allow, protocol pack fully prepared and blocked only by field access

4. **Control pipeline integrated at ground level**
   - `control_ref_node` consumes the validated `/target` interface
   - MAVROS message flow validated end-to-end on ground
   - Loss behaviour, bounds, and basic fail-safe logic checked without flight

5. **W12 readiness assessed honestly**
   - GO or NO-GO for first flight-related work based on evidence
   - Blocking issues listed clearly
   - Next-risk items prioritized

**System requirements for this week:**
- Outdoor tennis court target environment
- Fully online processing
- Lean operational perception mode for field use
- Perception target: at or above 15 Hz
- Latency budget: p95 at or below 200 ms
- Multi-person robustness with stable target lock where feasible

**Validation targets:**
- Lean live perception: 5+ minute runs at or above 15 Hz
- Outdoor detection and target output recorded successfully
- Outdoor tracking continuity characterized, even if not yet at final thesis target
- Control message flow validated on ground
- Safety behaviour reviewed before any flight-related escalation

---

## Goals for the week
- [ ] Freeze the validated lean live configuration for operational use
- [ ] Document live mode vs profiling mode clearly
- [ ] Execute first outdoor perception test when logistics allow
- [ ] Run structured outdoor scenarios or finish the full protocol pack if field access slips
- [ ] Integrate control_ref_node with MAVROS for ground-only validation
- [ ] Validate bounds, target-loss behaviour, and basic fail-safe handling
- [ ] Finalize pre-flight and field-operation checklist
- [ ] Generate outdoor and timing notes with thesis-usable evidence
- [ ] Assess W12 readiness with a clear GO or NO-GO decision

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
**Focus:** Lean-mode freeze, control integration (ground-only), outdoor prep

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 12 (Wednesday, 2026-03-12)
**Focus:** First outdoor perception test

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 13 (Thursday, 2026-03-13)
**Focus:** Outdoor test protocol execution

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

### Live Perception Operational Mode
- Lean configuration: *(frozen / in progress)*
- Sustained FPS: *(value)* Hz over *(duration)* min
- End-to-end latency: mean *(value)* ms, p95 *(value)* ms
- Thermal and memory stability: *(confirmed / issues noted)*

### Outdoor Perception Validation
- Test location: *(tennis court / other)*
- Scenarios tested: *(count and types)*
- Real-world issues documented: *(lighting, distance, occlusions, etc.)*
- Outdoor tracking continuity: *(characterized / not yet tested)*
- Conclusion on outdoor reliability: *(to be filled)*

### Control Integration (Ground-Only)
- control_ref_node status: *(integrated / in progress)*
- MAVROS message flow: *(validated / in progress)*
- Safety mechanisms checked: *(list items)*

### W12 Readiness Assessment
- Decision: *(GO / NO-GO for flight-related work)*
- Blocking issues: *(none / list)*
- Next-risk items: *(list)*

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
