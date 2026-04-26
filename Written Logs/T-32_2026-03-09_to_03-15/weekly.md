# Weekly Summary — T-32 (2026-03-09 to 2026-03-15)

> Note (updated 2026-03-16): This weekly summary preserves the week's in-time planning and execution context. Startup commands and orchestration notes inside this file may be historical. Current operational startup/stop procedure is documented in `RUNBOOK.md` and implemented in `tools/start_live_stack.sh`.

## T-32 Reality Check

**Constraints this week:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk/drone at IST - separated)
- ❌ No MAVROS hardware testing (no Pixhawk access until T-31)
- ❌ No battery/portable operation (wall-powered only)
- ✅ Indoor perception validation possible
- ✅ MAVROS learning and code preparation possible
- ✅ Full T-31 field session planning possible

**Days remaining:** 4 (Days 12-15, March 12-15)

---

## T-32 Revised Objectives — "Preparation Week"

**Theme:** Learn, code, document, and validate everything at home to maximize IST field time in T-31.

By end of Day 15 (March 15), you should have:

### 1. **MAVROS Integration Designed and Coded** ⚠️ Critical Path
   - Learn MAVROS basics (ArduPilot topics, coordinate frames)
   - Identify correct setpoint topics for velocity control
   - Update `control_ref_node` with MAVROS output (untested but ready)
   - Document MAVROS launch procedure for ground testing
   - Create safety checklist for first Pixhawk connection
   - Understand emergency stop and failsafe behavior

**Why critical:** This is NEW territory. Learning curve needs buffer time before field testing.

### 2. **Indoor Perception Validated and Analyzed**
   - Run 3+ sustained perception sessions (5-10 min each) indoors
   - Analyze timing, FPS stability, thermal behavior
   - Generate thesis-ready timing plots and statistics
   - Test multi-person scenarios if possible
   - Document baseline performance for outdoor comparison

**Deliverable:** Solid numbers to know if outdoor degrades performance

### 3. **Control Logic Refined and Tested**
   - Test control with synthetic/replayed targets
   - Validate target-loss behavior systematically
   - Tune gains conservatively for first field tests
   - Add explicit state logging for debugging
   - Test edge cases: stale target, out-of-bounds, low confidence

**Deliverable:** Robust control ready for hardware integration

### 4. **T-31 IST Field Sessions Planned**
   - Design Tuesday session plan (4 hours)
   - Design Thursday session plan (4 hours)
   - Create equipment checklist (what to bring to IST)
   - Define success criteria for first MAVROS test
   - Define success criteria for first outdoor perception test
   - Create startup/shutdown procedures for field operation

**Deliverable:** Complete field-ready operation manual

### 5. **Safety Protocol Documented**
   - Research ArduPilot safety features
   - Document emergency stop procedure
   - Create pre-test safety checklist
   - Understand motor arming requirements and RC override
   - Plan contingencies for common failure modes

**Deliverable:** Safety-first field test protocol

---

## T-31 Preview — "Integration Week"

**Available:** Tuesday + Thursday at IST, 4 hours each = 8 total integration hours

**Equipment status T-31:**
- ✅ Pi5 + Pixhawk + drone together at IST
- ✅ Battery available (4-cell LiPo) - CONFIRMED
- ✅ Outdoor football field access (weather permitting)
- ✅ SSH operation via laptop (no monitor)
- ✅ Ethernet connection (Pi5 ↔ Pixhawk) - CONFIRMED
- ❌ No indoor backup space available

### Tuesday Session Goal (4 hours)
**Focus:** First MAVROS ground integration (no outdoor, no flight)

- Set up Pi5 + Pixhawk connection
- Launch MAVROS and verify connectivity
- Launch perception + control pipeline
- Verify perception → control → Pixhawk message flow
- Record diagnostic bags (DO NOT ARM motors)
- Debug integration issues

**Success metric:** Pixhawk receiving valid setpoints from perception

### Thursday Session Goal (4 hours)
**Focus:** Depends on Tuesday results

**Option A** (if Tuesday had issues): Perception-only outdoor test
- Validate detection/tracking outdoors without control
- Characterize outdoor-specific challenges
- Record outdoor perception bags

**Option B** (if Tuesday succeeded): Integrated outdoor ground test
- Full pipeline: perception + control + Pixhawk outdoors
- Motors disarmed or props removed
- Validate setpoints respond to real targets
- Record integrated bags

**Success metric:** Evidence of system operation in target environment

---

## T-32 Goals (Achievable at Home)

### MAVROS Learning and Integration (Critical)
- [ ] Learn MAVROS basics: topics, coordinate frames, ArduPilot specifics
- [ ] Identify correct velocity control topics
- [ ] Update `control_ref_node.py` with MAVROS publisher (untested)
- [ ] Document MAVROS launch procedure and connection string
- [ ] Research ArduPilot safety features and failsafes
- [ ] Create safety checklist for first Pixhawk connection

### Indoor Perception Validation
- [ ] Run 3+ sustained indoor perception sessions (5-10 min each)
- [ ] Analyze timing, FPS, thermal stability
- [ ] Generate timing plots and statistics for thesis
- [ ] Test multi-person scenarios indoors
- [ ] Document baseline performance metrics

### Control Logic Refinement
- [ ] Test control with synthetic or replayed targets
- [ ] Validate target-loss and reacquisition behavior
- [ ] Tune gains conservatively for field testing
- [ ] Add detailed state logging for debugging
- [ ] Test edge cases: stale, out-of-bounds, low confidence

### T-31 Field Planning
- [ ] Design Tuesday IST session plan (4 hours)
- [ ] Design Thursday IST session plan (4 hours)
- [ ] Create equipment checklist for IST
- [ ] Write field startup/shutdown procedures
- [ ] Define success criteria for MAVROS integration
- [ ] Define success criteria for outdoor perception

### Safety and Risk Management
- [ ] Document emergency stop procedure
- [ ] Create pre-test safety checklist
- [ ] Research motor arming and RC override
- [ ] Plan failure mode contingencies

---

## Daily Progress (to be filled during the week)

### Day 09 (Sunday, 2026-03-09)
**Focus:** Complete T-33 freeze, validate live camera

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

### Day 12 (Wednesday, 2026-03-12) — TODAY
**Focus:** MAVROS learning, indoor perception validation baseline

**Planned:**
- Learn MAVROS fundamentals (topics, frames, ArduPilot)
- Run first sustained indoor perception session
- Begin MAVROS integration code design
- Start T-31 field planning

**Completed:**
- *(To be filled at end of day)*

**Issues:**
- *(To be filled)*

---

### Day 13 (Thursday, 2026-03-13)
**Focus:** Control refinement, MAVROS code implementation, safety planning

**Planned:**
- Complete MAVROS integration in control_ref_node
- Test control logic with replay/synthetic targets
- Document safety procedures
- Define Tuesday IST session plan

**Completed:**
- *(To be filled at end of day)*

**Issues:**
- *(To be filled)*

---

### Day 14 (Friday, 2026-03-14)
**Focus:** Indoor validation completion, field logistics finalization

**Planned:**
- Complete remaining indoor perception sessions
- Generate timing analysis and plots
- Finalize equipment checklist for IST
- Define Thursday IST session plan
- Complete documentation pack

**Completed:**
- *(To be filled at end of day)*

**Issues:**
- *(To be filled)*

---

### Day 15 (Saturday, 2026-03-15)
**Focus:** T-32 review, T-31 readiness verification

**Planned:**
- Review all T-32 deliverables
- Verify T-31 blockers resolved
- Final equipment/logistics check
- Identify any remaining risks
- Test MAVROS code compiles (if possible without hardware)

**Completed:**
- *(To be filled at end of day)*

**Issues:**
- *(To be filled)*

---

## Key Results (to be filled at end of week)

### MAVROS Integration Readiness
- Learning completed: *(yes / partial / no)*
- Topics identified: *(list topics)*
- Control node updated: *(yes / no)*
- Safety checklist created: *(yes / no)*
- Launch procedure documented: *(yes / no)*

### Indoor Perception Baseline
- Sessions completed: *(count)* sessions, *(total)* minutes
- FPS sustained: *(value)* Hz average over *(duration)* min
- End-to-end latency: mean *(value)* ms, p95 *(value)* ms
- Thermal stability: max temp *(value)*°C, throttling *(yes/no)*
- Multi-person tested: *(yes / no)*

### Control Logic Refinement
- Synthetic/replay testing: *(completed / not done)*
- Target-loss behavior: *(validated / needs work)*
- Gains tuned: *(yes / no)*
- Edge cases tested: *(list cases)*
- Debug logging added: *(yes / no)*

### T-31 Field Planning
- Tuesday session plan: *(complete / in progress)*
- Thursday session plan: *(complete / in progress)*
- Equipment checklist: *(complete / in progress)*
- Startup procedures: *(documented / not ready)*
- Success criteria defined: *(yes / no)*

### T-31 Readiness Assessment
- Blockers for Tuesday IST: *(none / list)*
- Equipment ready to transport: *(yes / no)*
- Code ready for hardware test: *(yes / untested / has issues)*
- Safety protocols: *(documented / partial)*
- Confidence level: *(high / medium / low)*

---

## Issues and Risks

### Current Blockers for T-32
- ✅ None (all T-32 work can be done at home)

### Known Blockers for T-31
- Equipment separated (Pi5 at home, Pixhawk at IST) → **Resolved Tuesday**
- MAVROS untested (no hardware access) → **Validation Tuesday**
- Outdoor operation untested → **First test Tuesday or Thursday**
- Battery/portable setup unknown → **To confirm with supervisors**
- Indoor space at IST unavailable → **Using outdoor football field**

### Technical Risks
- **MAVROS integration complexity** (new territory)
  - Mitigation: Learn thoroughly in T-32, conservative first tests
- **Coordinate frame confusion** (body vs NED vs camera)
  - Mitigation: Document frame conventions clearly
- **First hardware connection failure modes**
  - Mitigation: Safety checklist, emergency procedures
- **Outdoor perception degradation** (lighting, distance)
  - Mitigation: Indoor baseline for comparison
- **Weather dependency** for Thursday outdoor test
  - Mitigation: Flexible session goals (indoor/outdoor options)

### Risk Updates
*(Update as issues are discovered or mitigated during the week)*

---

## T-32 Retrospective (to be filled at end of week)

### What Worked Well
- *(To be filled at end of week)*

### What Didn't Work
- *(To be filled at end of week)*

### Key Learnings
- *(To be filled at end of week)*

### Critical Adjustments for T-31
- *(To be filled at end of week - e.g., if MAVROS learning revealed surprises)*

### Surprises and Unexpected Issues
- *(To be filled at end of week)*

---

## T-31 Success Criteria (Defined in T-32)

### Tuesday Session — Minimum Success
- [ ] MAVROS launches and connects to Pixhawk
- [ ] Perception pipeline runs simultaneously
- [ ] Control node publishes to MAVROS topics
- [ ] No crashes, clean startup/shutdown
- [ ] Diagnostic bags recorded

### Tuesday Session — Stretch Success
- [ ] Pixhawk receives and acknowledges setpoints
- [ ] Setpoint values look reasonable (not NaN, in expected range)
- [ ] Target detection triggers control response
- [ ] Safety bounds working (command saturation)

### Thursday Session — Depends on Tuesday
- **If Tuesday partial:** Focus on debugging, second integration attempt
- **If Tuesday successful:** Outdoor perception test or integrated ground test
- **If Tuesday failed:** Perception-only outdoor validation, defer MAVROS

---

## Next Week Logistics Checklist

### To Bring to IST (Tuesday & Thursday)
- [ ] Raspberry Pi 5 + power supply
- [ ] Camera (TEVS-AR0234)
- [ ] Laptop for SSH
- [ ] Ethernet cable (if needed for Pixhawk)
- [ ] USB cables
- [ ] Extension cord / power strip
- [ ] Notebook for hand-written notes
- [ ] Backup SD card (if something goes wrong)

### To Confirm Before Tuesday
- [ ] Battery charged and available
- [ ] Pixhawk/drone location confirmed at IST
- [ ] Outdoor football field access confirmed
- [ ] Contact info for supervisors if emergency
- [ ] Weather forecast for Thursday

### To Have Ready in Code
- [ ] `control_ref_node.py` with MAVROS output
- [ ] MAVROS launch command documented
- [ ] Startup script or procedure doc
- [ ] Safety checklist printed or accessible

---
