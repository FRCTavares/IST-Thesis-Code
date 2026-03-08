# Daily Log — 2026-03-12 — Outdoor Test Protocol Execution and Refinement

## Goal

Execute the full outdoor test protocol with defined scenarios and success criteria, generating thesis-ready quantitative results.

**Target outcome:**
- 6 outdoor test scenarios executed (adapted from W10 Day 06 plan)
- All success criteria measured and documented
- Thesis-ready outdoor test report with figures and tables
- Protocol refinements documented for future tests
- Clear understanding of system outdoor performance limits

---

## Context

| Key | Value |
|-----|-------|
| Previous test | Day 11 exploratory outdoor test |
| Test location | Tennis court (same as Day 11) |
| Test type | Formal protocol execution |
| Protocol source | W10 Day 06 planning (adapted based on Day 11 learnings) |
| Personnel | *(List test participants and roles)* |
| Weather | *(Check and document)* |
| Success criteria | Quantitative metrics for each scenario |

---

## Outdoor Test Protocol

### Protocol Overview

Based on W10 Day 06 planning and adapted for Day 11 learnings.

**Test scenarios (6 total):**
1. Single target, static distance (10m)
2. Single target, distance variation (5m → 15m → 5m)
3. Multi-person (2), target selection and lock
4. Multi-person (3), ambiguity and ID consistency
5. Occlusion and reacquisition (person passes behind obstacle)
6. Dynamic motion (running, direction changes)

**Success criteria (thesis targets):**
- Detection rate: ≥90% when target in frame and visible
- Tracking continuity: ≥80% time locked in multi-person scenarios
- Target reacquisition: ≤1.0 s after temporary occlusion (p95)
- ID switches: ≤2 switches per minute
- FPS: ≥15 Hz sustained throughout all scenarios
- Latency: p95 ≤ 200 ms

---

## Work Plan

### A) Pre-Test Setup and Checklist

Ensure repeatable test conditions.

**Tasks:**
- [ ] Complete pre-test checklist from Day 11
- [ ] Set up consistent camera position and height
- [ ] Mark distance markers on court (5m, 10m, 15m)
- [ ] Note lighting conditions and time of day
- [ ] Configure bag recording for all relevant topics
- [ ] Brief test participants on each scenario
- [ ] Prepare scenario execution checklist

**Deliverables:**
- Pre-test checklist completed
- Test setup documented (camera position, lighting, markers)

---

### B) Scenario 1: Single Target, Static Distance (10m)

**Objective:** Baseline detection and tracking quality at typical target distance.

**Procedure:**
- [ ] Person stands at 10m distance, facing camera
- [ ] Person performs simple movements (shift left/right, turn around)
- [ ] Record for 2 minutes
- [ ] Bag: `bags/outdoor/2026-03-12__scenario1_static_10m/`

**Measurements:**
- [ ] Detection rate (% frames with detection when person visible)
- [ ] Tracking continuity (% time with stable track)
- [ ] FPS and latency throughout run
- [ ] Bbox size at 10m distance (for person sizing analysis)

**Success criteria:**
- Detection rate ≥95%
- Tracking continuity ≥95%
- FPS ≥15 Hz

**Deliverables:**
- Scenario 1 bag and metrics

---

### C) Scenario 2: Single Target, Distance Variation (5m → 15m → 5m)

**Objective:** Characterize detection and tracking vs. distance.

**Procedure:**
- [ ] Person starts at 5m
- [ ] Person walks slowly to 15m (taking ~30s)
- [ ] Person walks back to 5m (taking ~30s)
- [ ] Repeat 3 times
- [ ] Bag: `bags/outdoor/2026-03-12__scenario2_distance_variation/`

**Measurements:**
- [ ] Detection rate vs. distance (bin by 5m, 10m, 15m)
- [ ] Tracking continuity vs. distance
- [ ] Bbox size vs. distance
- [ ] Any distance where tracking becomes unreliable

**Success criteria:**
- Detection rate ≥90% at 5m and 10m
- Detection rate ≥70% at 15m (stretch goal: ≥80%)
- No tracking losses during continuous approach

**Deliverables:**
- Scenario 2 bag and metrics
- Plot: detection rate vs. distance

---

### D) Scenario 3: Multi-Person (2), Target Selection and Lock

**Objective:** Validate target selection and lock with multiple people.

**Procedure:**
- [ ] Two people enter frame from different sides
- [ ] Both approach to ~10m distance
- [ ] One person is "target" (e.g., wearing distinctive clothing)
- [ ] Monitor if target selector locks on intended target
- [ ] People move around, test if lock is maintained
- [ ] Record for 2 minutes
- [ ] Bag: `bags/outdoor/2026-03-12__scenario3_two_people/`

**Measurements:**
- [ ] Detection rate for both people
- [ ] Tracking continuity for both tracks
- [ ] Target lock on correct person (qualitative check)
- [ ] ID switches (should be minimal with 2 people)

**Success criteria:**
- Both people detected ≥90% of time
- Tracking continuity ≥80%
- Target lock switches ≤2 times in 2 minutes

**Deliverables:**
- Scenario 3 bag and metrics
- Qualitative notes on target selection behavior

---

### E) Scenario 4: Multi-Person (3), Ambiguity and ID Consistency

**Objective:** Stress-test tracking and target selection with crowding.

**Procedure:**
- [ ] Three people enter frame
- [ ] People walk around, some paths cross
- [ ] Include brief moments of close proximity (but not full occlusion)
- [ ] Target person (one of three) performs specific path
- [ ] Record for 2 minutes
- [ ] Bag: `bags/outdoor/2026-03-12__scenario4_three_people/`

**Measurements:**
- [ ] Detection rate for all three people
- [ ] Tracking continuity per track
- [ ] ID switches total across all tracks
- [ ] Target lock stability (if target selector is monitoring one specific person)

**Success criteria:**
- Detection rate ≥85% for each person
- Tracking continuity ≥70% per track
- Total ID switches ≤3 per minute across all tracks

**Deliverables:**
- Scenario 4 bag and metrics
- Notes on tracking failures: where and why?

---

### F) Scenario 5: Occlusion and Reacquisition

**Objective:** Validate reacquisition after temporary occlusion.

**Procedure:**
- [ ] Target person walks behind an obstacle (e.g., post, tree, another person)
- [ ] Occlusion duration: ~1-2 seconds
- [ ] Person re-emerges on other side
- [ ] Repeat occlusions 5 times
- [ ] Bag: `bags/outdoor/2026-03-12__scenario5_occlusion_reacq/`

**Measurements:**
- [ ] Track loss count (does track break during occlusion?)
- [ ] Reacquisition time (from occlusion end to track reappears)
- [ ] ID consistency (same track_id after reacquisition or new ID?)

**Success criteria:**
- Reacquisition time: p95 ≤1.0 s
- ID consistency: ≥80% (same ID after reacquisition)
- No permanent track loss

**Deliverables:**
- Scenario 5 bag and metrics
- Reacquisition time histogram: `figures/outdoor/W11_reacquisition_histogram.png`

---

### G) Scenario 6: Dynamic Motion

**Objective:** Validate tracking under fast motion and direction changes.

**Procedure:**
- [ ] Person runs across field (moderate speed)
- [ ] Person performs direction changes (zigzag)
- [ ] Person does sudden stops and starts
- [ ] Record for 1-2 minutes
- [ ] Bag: `bags/outdoor/2026-03-12__scenario6_dynamic_motion/`

**Measurements:**
- [ ] Detection rate during motion (vs. static)
- [ ] Tracking continuity during fast motion
- [ ] Any motion blur or detection drops
- [ ] Tracker ability to follow fast direction changes

**Success criteria:**
- Detection rate ≥80% during motion
- Tracking continuity ≥75%
- No track losses during continuous motion

**Deliverables:**
- Scenario 6 bag and metrics
- Notes on motion-related issues (blur, lag)

---

### H) Offline Analysis and Report Generation

Analyze all scenario bags and generate thesis-ready report.

**Tasks:**
- [ ] Run timing analysis on all scenario bags
- [ ] Run tracking analysis on all scenario bags
- [ ] Extract metrics for each scenario
- [ ] Generate comparison plots:
  - Detection rate by scenario
  - Tracking continuity by scenario
  - FPS and latency across scenarios
  - Reacquisition time CDF
- [ ] Generate thesis-ready tables:
  - Success criteria evaluation (pass/fail per scenario)
  - Quantitative metrics summary
- [ ] Write outdoor test report with context, results, discussion

**Deliverables:**
- Outdoor test report: `reports/outdoor/W11_tennis_court_scenarios.md`
- Figures: `figures/outdoor/W11_*`
- Tables: success criteria evaluation, metrics summary

---

### I) Protocol Refinement and Lessons Learned

Document what to improve for future outdoor tests and final demo.

**Tasks:**
- [ ] Review test execution: what went well, what didn't?
- [ ] Identify protocol improvements:
  - Scenario definitions (clearer instructions?)
  - Success criteria (realistic? too strict?)
  - Test logistics (setup, timing, personnel)
- [ ] Document lessons learned for final thesis demo
- [ ] Update outdoor test checklist with improvements

**Deliverables:**
- Protocol refinement notes in outdoor test report
- Updated test protocol for future use

---

## Expected Outcomes

By end of Day 12, you should have:

1. **Complete outdoor test dataset**
   - 6 scenario bags with full coverage
   - Quantitative metrics for all scenarios

2. **Thesis-ready outdoor test report**
   - Success criteria evaluation (which passed, which failed)
   - Figures and tables ready for thesis
   - Discussion of results and outdoor challenges

3. **Clear understanding of outdoor performance**
   - Know where system excels and where it struggles
   - Quantified limits: distance, lighting, motion, crowding

4. **Confidence for flight test planning**
   - Know what to expect during actual flight demo
   - Understand what scenarios are feasible vs. risky

5. **Improved test protocol**
   - Lessons learned documented
   - Protocol ready for final demo runs or thesis validation

---

## Issues and Risks

### Potential Issues
- Weather may prevent testing (rain, wind, extreme conditions)
- Test personnel may not be available
- Some scenarios may be infeasible (e.g., 15m detection too poor)
- System may not meet all success criteria (this is OK, document it)

### Adaptation Strategy
- If weather bad: defer to Day 13 or later, use Day 12 for analysis/fixes
- If personnel limited: prioritize Scenarios 1, 2, 5 (single person)
- If detection range insufficient: adjust scenarios to work at closer distances
- If success criteria too strict: document actual performance and adjust criteria

---

## Notes

- This is the formal outdoor validation: results go in thesis
- Data quality matters: ensure bags have all topics, good timestamps
- If scenarios don't work as planned, adapt on the fly and document changes
- Failures are valuable data: document what didn't work and why
- Outdoor performance may be worse than indoors: accept reality, don't force it
- This test builds the evidence base for claims about system outdoor capability
