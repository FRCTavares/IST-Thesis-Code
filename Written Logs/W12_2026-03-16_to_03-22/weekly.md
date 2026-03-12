# Weekly Summary — W12 (2026-03-16 to 2026-03-22)

## Week 12 Theme: Integration Week

**Move from "preparation complete" to "MAVROS hardware integration validated and outdoor operation characterized."**

W11 was learning and indoor validation. W12 is execution: 8 hours of field time at IST to integrate perception + control + Pixhawk and validate in the target environment.

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
**Focus:** Monday preparation and equipment check

**Planned:**
- Pack equipment
- Review Tuesday session plan
- Verify code ready
- Final checks

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 17 (Monday, 2026-03-17)
**Focus:** Pre-IST final checks and transport prep

**Planned:**
- Git sync
- Equipment verification
- MAVROS procedure review
- Confirm field access

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

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

### Day 19 (Wednesday, 2026-03-19)
**Focus:** Tuesday analysis and Thursday planning

**Planned:**
- Analyze Tuesday bags
- Document issues
- Implement fixes if needed
- Finalize Thursday plan

**Completed:**
- *(To be filled)*

**Issues:**
- *(To be filled)*

---

### Day 20 (Thursday, 2026-03-20)
**Focus:** IST Session 2 — Outdoor validation or debug (4 hours)

**Session goals:**
- *(Depends on Tuesday results)*
- Option A: Debug integration
- Option B: Outdoor perception
- Option C: Integrated outdoor test

**Completed:**
- *(To be filled at end of session)*

**Issues:**
- *(To be filled)*

**Thursday success level:** *(Minimum / Target / Stretch)*

---

### Day 21 (Friday, 2026-03-21)
**Focus:** Week 12 analysis and documentation

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

### Day 22 (Saturday, 2026-03-22)
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

**If Tuesday/Thursday successful:**
- W13 focus: *(refine control, extend outdoor testing, prepare for armed ground test)*

**If integration issues:**
- W13 focus: *(resolve blockers, additional integration sessions)*

**If outdoor deferred:**
- W13 focus: *(outdoor validation priority, weather-dependent planning)*

---

**Week status:** *(In progress / Complete)*  
**Overall success:** *(To be assessed at end of week)*
