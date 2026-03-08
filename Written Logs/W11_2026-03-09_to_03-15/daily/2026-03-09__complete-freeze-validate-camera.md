# Daily Log — 2026-03-09 — Complete W10 Freeze and Live Camera Validation

## Goal

Close out Week 10 deliverables and validate that the live camera integration meets thesis performance targets.

**Target outcome:**
- W10 weekly.md and artefacts.md completed and frozen
- Live camera validated at ≥15 Hz with end-to-end detections
- Full latency breakdown with live camera (compare to file-based baseline)
- Issues log documenting any camera/inference stability problems

---

## Context

| Key | Value |
|-----|-------|
| Week transition | W10 → W11 |
| Camera status | Live integration completed on Day 08 (2026-03-08) |
| Remaining W10 work | Baseline freeze documentation incomplete |
| Next milestone | Outdoor testing |
| Hardware | Pi 5 + Hailo AI HAT+ + TEVS-AR0234 |
| Software | ROS 2 Jazzy, live camera → ZMQ → container → detections |
| Thesis FPS target | ≥15 Hz |
| Latency budget | p95 ≤ 200 ms |

---

## Work Plan

### A) Complete W10 Documentation

Close out all W10 deliverables properly before moving to outdoor tests.

**Tasks:**
- [ ] Review W10 daily logs (Days 03-08) and mark completion status
- [ ] Complete W10 weekly.md with final results and key learnings
- [ ] Update W10 artefacts.md with all code/configs/reports from the week
- [ ] Document baseline tracker decision (if made) or defer decision with rationale
- [ ] Document target selector state and embedding v1 status
- [ ] Note what was deferred from W10 plan and why

**Deliverables:**
- Completed `W10_2026-03-02_to_03-08/weekly.md`
- Completed `W10_2026-03-02_to_03-08/artefacts.md`

---

### B) Live Camera Performance Validation

Prove the live camera meets minimum thesis targets before outdoor testing.

**Tasks:**
- [ ] Run full pipeline with live camera for at least 2-3 minutes
- [ ] Record bag: `bags/live_camera/2026-03-09__camera_validation/`
- [ ] Measure sustained FPS (use timing analysis or bag inspection)
- [ ] Extract full latency breakdown:
  - Camera capture → frame ready
  - Frame serialization
  - ZMQ round-trip
  - Inference time
  - Detection deserialization
  - Tracker processing
  - Target selector
  - End-to-end: camera timestamp → `/target` publish
- [ ] Compare timing to file-based baseline from W09-W10
- [ ] Check for frame drops or timing drift over the run

**Success criteria:**
- Sustained ≥15 Hz for full 2-3 minute run
- Mean latency < 150 ms, p95 < 200 ms
- No obvious FPS degradation or frame drops
- Detections quality similar to file-based runs

**Deliverables:**
- Bag: `bags/live_camera/2026-03-09__camera_validation/`
- Timing analysis: `reports/timing/W11_live_camera_initial_validation.md`
- Comparison plot: file vs. live latency CDF

---

### C) Document Live Camera Issues

Real-time camera brings new issues not seen in file replay.

**Tasks:**
- [ ] Document any FPS instability or drops
- [ ] Note any quality issues (exposure, focus, motion blur)
- [ ] Check CPU/memory usage during live runs
- [ ] Test restart behavior (does camera recover after ROS restart?)
- [ ] Document any Hailo/ZMQ issues under live load

**Deliverables:**
- Issues log: `reports/system/W11_live_camera_issues.md`
- Recommendations for Day 10 stability testing

---

### D) Plan Week 11 Focus

Clarify the main objectives for W11 based on current system state.

**Tasks:**
- [ ] Review W11 index.md and confirm daily plan makes sense
- [ ] Identify any W10 carryover work that blocks outdoor testing
- [ ] Draft outdoor test scenarios (to refine on Day 11 in the field)
- [ ] Confirm hardware readiness (battery, mounting, portability)

**Deliverables:**
- Updated W11 index.md if needed
- Outdoor test scenario draft (informal)

---

## Expected Outcomes

By end of Day 09, you should have:

1. **W10 properly closed**
   - All weekly and artefacts documentation complete
   - Clear record of what was achieved vs. deferred

2. **Live camera validated at thesis minimum**
   - ≥15 Hz sustained performance confirmed
   - Latency budget met or issues clearly documented

3. **Confidence in system readiness for outdoor tests**
   - No blocking issues that prevent taking system outside
   - Clear understanding of what might go wrong outdoors

4. **Week 11 focus confirmed**
   - Outdoor validation is the priority
   - Control integration comes after outdoor confidence is established

---

## Issues and Risks

### Known Issues from Day 08
- Camera FPS initially ~60 Hz but dropped with extra load (CLI tools, subscribers)
- Need to validate sustained FPS under full system load
- Latency breakdown not yet measured for live camera path

### Risks for Outdoor Testing
- Lighting conditions (auto-exposure behavior unknown)
- Detection range at 10m+ distance unknown
- Thermal throttling if running continuously outdoors
- Battery life under full system load unknown

### Mitigation
- Today's validation run will reveal any show-stoppers
- Day 10 will focus on extended stability if issues found
- Outdoor Day 11 test is exploratory: expect to learn, not validate yet

---

## Notes

- This is transition day: close W10, validate camera, enter W11 confidently
- Don't rush outdoor tests until camera performance is confirmed
- If live camera has serious issues, may need to defer outdoor tests or use file replay for initial outdoor data collection
- Week 11 is about outdoor reality check: the system that worked indoors must now work in real conditions
