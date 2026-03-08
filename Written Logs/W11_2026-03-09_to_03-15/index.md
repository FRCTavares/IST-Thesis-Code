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
**[First Outdoor Test Run (Perception Only)](daily/2026-03-11__first-outdoor-perception-test.md)**

**Goal:** Take the system outside and validate perception outdoors (no flight yet)

**Deliverables:**
- Tennis court test run with live camera
- Multi-person scenarios: 1, 2, 3 people
- Outdoor bag recording: `bags/outdoor/2026-03-11__first_outdoor_test/`
- Outdoor perception report: detection rate, tracking continuity, lighting effects
- Issues log: sunlight, distance, real-world occlusions

**Status:** *(Not started / In progress / Complete)*

---

### Day 12 (Wednesday, 2026-03-12)
**[Outdoor Test Protocol Execution and Refinement](daily/2026-03-12__outdoor-test-protocol.md)**

**Goal:** Run full outdoor test protocol from W10 Day 06, measure against success criteria

**Deliverables:**
- 6 tennis court scenarios executed (or adapted based on Day 11 results)
- Success criteria measured: pixel error, reacquisition time, ID switches, latency
- Outdoor test report: `reports/outdoor/W11_tennis_court_scenarios.md`
- Protocol refinements documented
- Updated checklist for flight tests

**Status:** *(Not started / In progress / Complete)*

---

### Day 13 (Thursday, 2026-03-13)
**[Control Interface Integration and Ground Control Demo](daily/2026-03-13__control-integration-demo.md)**

**Goal:** Integrate control_ref with MAVROS, validate control pipeline on ground

**Deliverables:**
- `control_ref_node` outputs MAVROS setpoint messages
- Ground-based control validation (no flight, just message flow)
- MAVROS interface documented: topic mapping, coordinate frames, safety bounds
- Control demo script: `tools/run_control_demo.sh`
- Control integration report: `reports/control/W11_control_integration.md`

**Status:** *(Not started / In progress / Complete)*

---

### Day 14 (Friday, 2026-03-14)
**[Pre-Flight Safety Validation and Checklist](daily/2026-03-14__preflight-safety-checklist.md)**

**Goal:** Validate all safety mechanisms before first flight test

**Deliverables:**
- Safety bounds implemented and tested (max velocity, max altitude, geofence)
- Loss-of-target behavior validated (hold / return / land)
- Emergency stop procedure tested
- Battery test with full system load (validate Tattu 6S 4500 mAh)
- Pre-flight checklist finalized: `docs/preflight_checklist.md`
- Safety validation report: `reports/control/W11_safety_validation.md`

**Status:** *(Not started / In progress / Complete)*

---

### Day 15 (Saturday, 2026-03-15)
**[Week 11 Review and Flight Test Planning](daily/2026-03-15__week-review-flight-planning.md)**

**Goal:** Consolidate W11 learnings, plan first flight test for W12

**Deliverables:**
- W11 weekly.md completed with outdoor test results
- W11 artefacts.md updated with all deliverables
- Flight test plan v1: scenarios, risks, abort criteria, personnel
- System readiness assessment for first flight
- W12 goals drafted

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
**Decision:** *(Final scenario list after Day 11 outdoor exploration)*  
**Date:** 2026-03-11 (Day 11)  
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
