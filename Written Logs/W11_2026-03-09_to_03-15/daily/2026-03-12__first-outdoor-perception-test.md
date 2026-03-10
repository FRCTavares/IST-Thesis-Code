# Daily Log — 2026-03-12 — First Outdoor Perception Test

## Goal

Take the system outdoors and validate perception performance in real-world conditions.

**Target outcome:**
- Tennis court test run with live camera and multi-person scenarios
- Outdoor bag recorded with full topic coverage
- Initial outdoor perception quality assessed
- Real-world issues documented (lighting, distance, occlusions)
- Decision: are we ready for full protocol execution (Day 13) or do we need fixes?

---

## Context

| Key | Value |
|-----|-------|
| Test location | Tennis court (or similar outdoor open space) |
| Previous validation | Indoor stability confirmed on Day 10, lean mode frozen on Day 11 |
| Operational mode | Lean perception mode (16.6 Hz validated indoors) |
| Test type | Exploratory (not formal protocol yet) |
| Personnel | *(List who is available for testing)* |
| Weather | *(Check forecast and note conditions)* |
| Hardware | Full system portable, battery tested |
| Primary unknowns | Lighting, detection range, tracking in real motion |

---

## Work Plan

### A) Pre-Test Preparation and Checklist

Ensure system is ready before going outdoors.

**Tasks:**
- [ ] Charge battery fully (Tattu 6S 4500 mAh)
- [ ] Verify all hardware connections secure
- [ ] Test full system indoors one final time (quick validation)
- [ ] Use lean operational mode from Day 11 (16.6 Hz validated)
- [ ] Prepare bag recording: check disk space, test bag recording works
- [ ] Prepare portable setup: mounting, cables, monitor/laptop for monitoring
- [ ] Check weather: avoid rain, extreme wind, or very low sun angle
- [ ] Confirm test location availability
- [ ] Brief any test participants on scenarios

**Deliverables:**
- Pre-test checklist completed (use Day 11 outdoor checklist)
- System physically ready for transport

---

### B) Initial Outdoor System Validation (Static Test)

First confirm the system runs outdoors before testing perception.

**Tasks:**
- [ ] Set up system at tennis court
- [ ] Power on and launch full ROS pipeline in lean mode
- [ ] Verify camera is capturing (check `/camera/image_raw`)
- [ ] Verify detections are publishing (check `/detections`)
- [ ] Check FPS and basic timing (quick sanity check)
- [ ] Note any immediate issues: lighting, glare, exposure

**Success criteria:**
- System boots and runs without errors
- Camera captures clear images (not overexposed or too dark)
- Detections appear at reasonable rate
- No obvious hardware issues

**Deliverables:**
- Initial outdoor system validation notes
- Camera sample images: `figures/outdoor/W11_first_outdoor_camera_samples.png`

---

### C) Multi-Person Detection and Tracking Scenarios

Test perception with realistic outdoor scenarios.

**Scenario 1: Single person, various distances**
- [ ] Person walks from 5m → 10m → 15m → 10m → 5m
- [ ] Record bag: `bags/outdoor/2026-03-12__scenario1_single_distance/`
- [ ] Note detection quality at each distance
- [ ] Check tracking continuity throughout

**Scenario 2: Two people, simultaneous tracking**
- [ ] Two people stand/walk in frame simultaneously
- [ ] Record bag: `bags/outdoor/2026-03-12__scenario2_two_people/`
- [ ] Check if both are detected and tracked
- [ ] Note any ID switches or tracking failures

**Scenario 3: Three people, crowding and occlusion**
- [ ] Three people in frame, some closer together
- [ ] Include brief occlusions (people passing between each other)
- [ ] Record bag: `bags/outdoor/2026-03-12__scenario3_three_people_occlusion/`
- [ ] Check tracking continuity through occlusions
- [ ] Note any target selector issues (if monitoring `/target`)

**Scenario 4: Dynamic motion**
- [ ] Person runs or moves quickly
- [ ] Person changes direction
- [ ] Record bag: `bags/outdoor/2026-03-12__scenario4_dynamic_motion/`
- [ ] Check tracking under fast motion
- [ ] Note any motion blur or detection drops

**Deliverables:**
- 4 outdoor scenario bags
- Initial qualitative observations for each scenario

---

### D) Lighting and Environmental Effects

Characterize outdoor lighting challenges.

**Tasks:**
- [ ] Test in full sun (if possible)
- [ ] Test in shade (if available)
- [ ] Test with sun behind camera (best case)
- [ ] Test with sun behind target (backlight challenge)
- [ ] Test at different times if possible (morning vs. afternoon)
- [ ] Note any glare, lens flare, or saturation issues
- [ ] Check camera auto-exposure behavior

**Deliverables:**
- Lighting conditions log
- Camera sample images in different lighting: `figures/outdoor/W11_lighting_effects/`
- Recommendations for camera tuning (if needed)

---

### E) Offline Analysis and Initial Metrics

Analyze bags back at the lab and extract initial metrics.

**Tasks:**
- [ ] Copy all bags to lab storage: `bags/outdoor/2026-03-12__first_outdoor_test/`
- [ ] Run timing analysis on outdoor bags
- [ ] Extract basic tracking metrics:
  - Detection rate (detections per frame when person visible)
  - Tracking continuity (time locked %)
  - ID switches (count)
  - Lost target events
- [ ] Compare outdoor metrics to indoor baseline
- [ ] Generate initial plots: detection rate, tracking quality

**Deliverables:**
- Initial outdoor report: `reports/outdoor/W11_first_outdoor_test.md`
- Key findings and issues list
- Comparison: indoor vs. outdoor performance

---

### F) Assess Readiness for Full Protocol (Day 13)

Decide if system is ready for formal protocol execution or needs fixes.

**Tasks:**
- [ ] Review all qualitative and quantitative results
- [ ] Identify any blocking issues
- [ ] List what worked well and what didn't
- [ ] Decide: GO for Day 13 protocol or fix issues first?
- [ ] If fixes needed: prioritize and plan

**Deliverables:**
- GO/NO-GO decision for Day 13 outdoor protocol
- Issues list with severity
- Day 13 plan (protocol execution or fixes)

---

## Expected Outcomes

By end of Day 12, you should have:

1. **System validated outdoors**
   - Proof that system runs in real-world conditions
   - Camera and perception working (even if not perfectly)

2. **Real-world challenges identified**
   - Lighting effects documented
   - Detection range limits known
   - Tracking issues in real motion characterized

3. **Initial outdoor performance data**
   - 4 scenario bags with qualitative observations
   - Basic metrics: detection rate, tracking continuity
   - Comparison to indoor baseline

4. **Decision for Day 13**
   - GO: proceed with full protocol
   - NO-GO: fix critical issues first

5. **Realistic expectations for outdoor demo**
   - Know what the system can and cannot do outdoors
   - Understand limitations and workarounds

---

## Issues and Risks

### Potential Outdoor Issues
- Camera auto-exposure may not handle sun/shade transitions well
- Detection quality may drop significantly at 10m+ distance
- Tracking may become unreliable with real motion and occlusions
- FPS may drop due to outdoor load or thermal effects
- Battery life may be shorter than expected

### Backup Plans
- If lighting is terrible: test in shade only, retune camera exposure
- If detection range insufficient: test at closer distances for now
- If tracking fails badly: validate detections only, defer tracking outdoor validation
- If system unstable: shorter test runs, bring backup battery

### Safety and Logistics
- Have backup power (charged laptop or extra battery)
- Bring sun protection for equipment and personnel
- Have water and breaks planned for test participants
- Be prepared to abort if weather turns bad

---

## Notes

- This is an exploratory test: expect to learn, not to validate perfection
- Goal is to understand what "outdoor" means for this system
- Don't be discouraged if performance is worse than indoors: this is expected
- Document everything: issues found today guide improvements for rest of thesis
- If outdoor performance is very poor, may need to revisit system design (e.g., better camera, different detector)
- Tennis court is representative of final demo environment: results here matter
- Day 11 work (lean freeze + control integration + outdoor prep) enables this test to run smoothly
