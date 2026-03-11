# Week 11 Index (2026-03-09 to 2026-03-15)

## Week Theme
**From "frozen baseline" to "camera-live system ready for outdoor control"**

The camera is now in the ROS pipeline. This week transitions from indoor validation to outdoor testing with real control demonstrations in preparation for the final thesis demo.

---

## Quick Links

- [Weekly Summary](weekly.md) — Goals, results, outdoor tests, control readiness
- [Artefacts](artefacts.md) — Code, configs, reports, datasets, test runs

---

## Daily Logs

### Day 09 (Sunday, 2026-03-09)
**[Complete W10 Freeze and Live Camera Validation](daily/2026-03-09__complete-freeze-validate-camera.md)**

**Goal:** Close out W10 deliverables, validate live camera at thesis-target FPS

**Deliverables:**
- W10 weekly.md and artefacts.md completed
- Live camera validated at ≥15 Hz with end-to-end detections
- Latency breakdown with live camera (compare to file-based baseline)
- Issues log: any camera/inference stability problems

**Status:** *(Not started / In progress / Complete)*

---

### Day 10 (Monday, 2026-03-10)
**[Live Camera Stability and Timing Under Load](daily/2026-03-10__camera-stability-timing.md)**

**Goal:** Prove live camera can sustain thesis targets under extended runs

**Deliverables:**
- 5+ minute continuous run with live camera
- FPS log over time (detect any degradation)
- Latency report: `reports/timing/W11_live_camera_latency.md`
- Memory/CPU profile if needed
- Thermal throttling check on Pi 5

**Status:** *(Not started / In progress / Complete)*

---

### Day 11 (Tuesday, 2026-03-11)
**[Lean-Mode Freeze, Control Integration, and Outdoor Prep](daily/2026-03-11__lean-freeze-control-integration-outdoor-prep.md)**

**Goal:** Freeze validated lean perception config, advance ground-only control integration, prepare outdoor test pack

**Deliverables:**
- Lean perception mode frozen and documented
- `control_ref_node` integrated against validated `/target` interface
- Ground-only MAVROS/control message flow verified
- Safety logic and fail-safe behaviour reviewed
- Outdoor checklist, scenario plan, and bag naming prepared

**Status:** *(In progress)*

---

### Day 12 (Wednesday, 2026-03-12)
**[Outdoor Readiness Pack, Control Rehearsal, and Simulation Preparation](daily/2026-03-12__first-outdoor-perception-test.md)**

**Goal:** Finish field-readiness documentation, rehearse control interface safely, prepare simulation/replay workflow before real outdoor testing

**Deliverables:**
- Outdoor field checklist completed: `docs/outdoor_field_checklist.md`
- Scenario sheet and bag naming frozen: `docs/outdoor_scenarios.md`
- Field startup/shutdown procedures: `docs/field_startup_shutdown.md`
- `control_ref_node` further validated indoors or via replay
- Safe replay or simulation rehearsal path prepared
- GO/NO-GO gate defined for first real outdoor test day

**Status:** *(Not started / In progress / Complete)*

---

### Day 13 (Thursday, 2026-03-13)
**[Replay Rehearsal, MAVROS Topic Prep, and Real-Test Readiness Gate](daily/2026-03-13__outdoor-test-protocol.md)**

**Goal:** Rehearse perception-to-control pipeline safely using replay/synthetic inputs, prepare MAVROS topic integration, define outdoor gate

**Deliverables:**
- Replay or synthetic `/target` rehearsal completed
- `control_ref_node` exercised in safe repeatable cases (centred, left, right, near, far, stale)
- MAVROS topic choice frozen and documented
- Outdoor readiness documents finalized: `docs/outdoor_field_checklist.md`, `docs/outdoor_scenarios.md`, `docs/field_startup_shutdown.md`
- GO / NO-GO gate defined for first real outdoor day
- Integrated ground-only smoke rehearsal bag recorded

**Status:** *(Not started / In progress / Complete)*

---

### Day 14 (Friday, 2026-03-14)
**[First Real Outdoor Bring-Up and Exploratory Validation](daily/2026-03-14__preflight-safety-checklist.md)**

**Goal:** Take frozen lean perception stack to real outdoor environment, verify reliable outdoor bring-up, record exploratory bags

**Deliverables:**
- Outdoor checklist executed successfully
- Lean stack brought up outdoors without major issues
- At least 1-2 exploratory outdoor bags: single-person distance sweep, two-person scenario
- Real-world issues documented: lighting, distance, target size, multi-person behavior
- Optional ground-only control coexistence test
- Clear decision on whether larger outdoor session justified

**Status:** *(Not started / In progress / Complete)*

---

### Day 15 (Saturday, 2026-03-15)
**[Week 11 Review, Readiness Assessment, and Next-Step Planning](daily/2026-03-15__week-review-flight-planning.md)**

**Goal:** Close out W11 with evidence-based review, assess readiness for next phase, plan next sequence realistically

**Deliverables:**
- W11 weekly.md completed with actual results
- W11 artefacts.md updated with all deliverables
- Current system readiness report: `reports/system/W11_system_readiness.md`
- Evidence summary from Week 11
- Real blockers and deferred work clearly listed
- Next-phase plan drafted: replay rehearsal, outdoor validation, MAVROS topic prep
- Thesis timeline review and adjustment
- Realistic status framing: READY FOR REPLAY REHEARSAL / OUTDOOR EXPLORATORY / MAVROS TOPIC PREP (not flight-ready claims)

**Status:** *(Not started / In progress / Complete)*

---

## Week Goals Tracking

- [ ] Validate live camera at ≥15 Hz sustained performance
- [ ] Complete outdoor perception testing (tennis court, multi-person)
- [ ] Execute outdoor test protocol with quantified results
- [ ] Integrate control pipeline with MAVROS (ground validation)
- [ ] Implement and validate all safety mechanisms
- [ ] Finalize pre-flight checklist and safety procedures
- [ ] Generate outdoor test reports with thesis-ready figures
- [ ] Assess system readiness for first flight test

---

## Key Decisions

### Live Camera Performance
**Decision:** *(Accept as baseline / needs optimization / fallback to file replay)*  
**Date:** 2026-03-09-10 (Days 09-10)  
**Rationale:** *(To be filled based on stability and timing results)*

### Outdoor Test Scenarios
**Decision:** *(Final scenario list after Day 14 outdoor exploration)*  
**Date:** 2026-03-14 (Day 14)  
**Rationale:** *(Adapt based on real-world constraints and available test personnel)*

### Control Safety Strategy
**Decision:** *(Hold / return / land on target loss, safety bounds parameters)*  
**Date:** 2026-03-14 (Day 14)  
**Rationale:** *(Balance between demo effectiveness and flight safety)*

### Flight Test Readiness
**Decision:** GO / NO-GO for W12 first flight  
**Date:** 2026-03-15 (Day 15)  
**Rationale:** *(Based on outdoor perception results, safety validation, and system stability)*

---

## Risk Register

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| Live camera FPS < 15 Hz | Cannot meet thesis target | Optimize capture/inference pipeline, reduce resolution if needed | *Monitoring* |
| Outdoor lighting (overexposure/underexposure) | Poor detection quality | Camera auto-exposure tuning, test multiple times of day | *To assess* |
| Detection range insufficient at 10m+ | Cannot maintain target lock | Validate at multiple distances, may need GS camera upgrade | *To assess* |
| Thermal throttling on Pi 5 | FPS degradation over time | Monitor temps, add cooling if needed | *To assess* |
| GPS quality on tennis court | Cannot validate position hold | Use MAVROS local position for initial tests | *Accepted* |
| Target loss handling during outdoor tests | Unreliable reacquisition | Tune FSM thresholds with outdoor data | *To address* |
| MAVROS integration complexity | Delayed control demo | Start with simple open-loop commands, iterate | *Planned* |

---

## Notes

- **Camera went live on 2026-03-08**: End-to-end ROS → container → detections working
- **W10 baseline freeze incomplete**: Carry over completion to Day 09
- **First outdoor test is critical**: Will reveal real-world challenges not seen in indoor replay
- **Safety-first approach**: No flight until all safety mechanisms validated
- **This week bridges indoor validation → outdoor reality**
