# Daily Log — 2026-03-06 — Outdoor Readiness Without the Camera (Week 10, Day 4)

## Goal
Outdoor readiness without the camera. By end of day, you have a written, executable outdoor protocol and checklist (zero hand-wavy). This day is about "the demo is planned like a flight test."

**Target outcome:**
- Tennis court scenarios fully defined with distances, motions, persons
- Success criteria with concrete numbers (pixel error, reacquire time, switches, latency)
- Test runner template with pre-flight checklist
- Documented protocol ready for execution when camera arrives

**Philosophy:** Plan the outdoor demo with engineering rigor before hardware is available.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**. Protocol designed for Week 11+ execution when camera arrives. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Test environment | Real outdoor tennis court |
| System status | Frozen baseline (tracker, target selector, control ref) from Week 10 |
| Demo goal | Robust person tracking for control at 30 Hz |

---

## Work Plan

### A) Define tennis court scenarios
Specify concrete test scenarios with measurable parameters.

- [ ] **Scenario 1: Close range, lateral motion**
  - Distance: 5 m from drone
  - Target motion: Walking laterally across frame (2 m/s typical walking speed)
  - Duration: 20-30 s
  - Persons: 1 target, no distractors
  - Success: Continuous lock, smooth tracking
  
- [ ] **Scenario 2: Medium range, approaching**
  - Distance: 10-20 m from drone
  - Target motion: Walking toward drone (frontal)
  - Duration: 20-30 s
  - Persons: 1 target
  - Success: Scale change handled, continuous lock
  
- [ ] **Scenario 3: Occlusion by net**
  - Distance: 10 m from drone, target passes behind tennis net
  - Occlusion duration: ~1-2 s
  - Persons: 1 target
  - Success: Reacquire same ID within 1.5 s
  
- [ ] **Scenario 4: Multi-person crossing**
  - Distance: 5-10 m from drone
  - Target motion: Two persons cross paths, minimum separation < 1 m
  - Duration: 15-20 s
  - Persons: 2 (1 target, 1 distractor)
  - Success: No ID switch during crossing
  
- [ ] **Scenario 5: Target stops and turns**
  - Distance: 10 m from drone
  - Target motion: Walking → stop 3s → turn 180° → walk back
  - Duration: 20-30 s
  - Persons: 1 target
  - Success: Maintain lock through stop and turn
  
- [ ] **Scenario 6: Cluttered background**
  - Distance: 10 m, trees/buildings in background
  - Target motion: Lateral
  - Duration: 20-30 s
  - Success: No false positives, stable lock

- [ ] Document each scenario in `artefacts.md`
- **Deliverable:** Complete scenario definitions with parameters
- Notes: *(fill)*

**Scenario summary table:**
| Scenario | Distance | Motion | Persons | Key challenge | Duration |
|----------|----------|--------|---------|---------------|----------|
| 1. Close lateral | 5 m | Lateral 2 m/s | 1 | Smooth tracking | 20-30 s |
| 2. Medium approach | 10-20 m | Toward drone | 1 | Scale change | 20-30 s |
| 3. Net occlusion | 10 m | Behind net | 1 | Reacquisition | 15-20 s |
| 4. Crossing | 5-10 m | Cross paths | 2 | ID consistency | 15-20 s |
| 5. Stop and turn | 10 m | Stop, turn 180° | 1 | Motion change | 20-30 s |
| 6. Clutter | 10 m | Lateral | 1 | Background | 20-30 s |

### B) Define success criteria
Specify quantitative success criteria for each metric.

- [ ] **Pixel tracking error** (while locked):
  - p50 < 10 px (tight lock)
  - p95 < 20 px (acceptable deviation)
  - Computed as: `error = sqrt((ex_px)^2 + (ey_px)^2)`
  
- [ ] **Reacquisition time** (after occlusion):
  - p95 < 1.0 s (must reacquire within 1 second)
  - p50 < 0.5 s (typical case)
  
- [ ] **ID switches** (target selector):
  - < 2 switches per minute (0.033 Hz)
  - In crossing scenario: 0 switches (ideal)
  
- [ ] **Latency** (end-to-end):
  - p95 < 150 ms (target 150, budget 200)
  - p99 < 200 ms (hard limit)
  - Measured as: image capture → control_ref publish
  
- [ ] **Control output rate:**
  - Mean: 30 Hz ± 1 Hz
  - No gaps > 50 ms (2 cycles)
  
- [ ] **Lock stability:**
  - % time in LOCKED state > 90% (excluding initial search)
  - % time with target_valid = True > 85%
  
- [ ] **Detection rate:**
  - Target detected in > 95% of frames (when not occluded)
  - False positive rate < 5% (detections not matching any person)

- [ ] Document criteria in README or test protocol doc
- **Deliverable:** Success criteria table
- Notes: *(fill)*

**Success criteria summary:**
```yaml
success_criteria:
  tracking:
    pixel_error_p50: 10  # px
    pixel_error_p95: 20  # px
  
  reacquisition:
    time_p50: 0.5  # s
    time_p95: 1.0  # s
  
  robustness:
    switches_per_minute: 2  # max
    lock_stability: 0.90  # fraction
    target_valid_duty_cycle: 0.85  # fraction
  
  latency:
    end_to_end_p95: 150  # ms
    end_to_end_p99: 200  # ms
  
  control:
    output_rate_mean: 30  # Hz
    output_rate_std: 1  # Hz
    max_gap: 50  # ms
  
  detection:
    detection_rate: 0.95  # fraction (when visible)
    false_positive_rate: 0.05  # max
```

### C) Create a "test runner" template
Develop a structured protocol for executing outdoor tests.

- [ ] **Pre-flight checklist:**
  - [ ] Hardware: Camera connected, secured, focused
  - [ ] Hardware: Hailo AI HAT+ temperature < 70°C (cool start)
  - [ ] Hardware: Pixhawk armed, GPS lock (optional for tracking test)
  - [ ] Software: All nodes launched, topics publishing
  - [ ] Software: Bag recording started with all topics
  - [ ] Environment: Lighting adequate (avoid direct sun into camera)
  - [ ] Environment: Wind < 5 m/s (if flying, for stability)
  - [ ] Personnel: Target person briefed on scenario
  - [ ] Personnel: Safety observer designated
  - [ ] Scenario selected and parameters confirmed
  
- [ ] **Run steps:**
  1. Execute pre-flight checklist
  2. Start bag recording: `ros2 bag record -a -o outdoor_<scenario>_<date>`
  3. Launch system: `ros2 launch thesis_bringup outdoor_test.launch.py tracker:=<baseline>`
  4. Verify topics: `ros2 topic hz /detections /tracks /target /control_ref`
  5. Initiate scenario (target person begins motion)
  6. Monitor live: `ros2 topic echo /target_state` (verify LOCKED)
  7. Complete scenario duration
  8. Stop bag recording
  9. Safe shutdown: Ctrl-C launch, land drone (if flying)
  
- [ ] **Post-run extraction commands:**
  ```bash
  # Analyze bag
  python3 tools/analyse_bag_timing.py bags/outdoor_<scenario>_<date>/
  python3 tools/analyse_bag_tracking.py bags/outdoor_<scenario>_<date>/
  
  # Generate report
  python3 tools/generate_outdoor_report.py bags/outdoor_<scenario>_<date>/ \
      --scenario <scenario> \
      --criteria config/outdoor_success_criteria.yaml
  
  # Check against success criteria
  python3 tools/check_success.py reports/outdoor_<scenario>_<date>.md
  ```
  
- [ ] **Pass/fail decision:**
  - All success criteria met → PASS
  - Any criterion failed → FAIL (document which, investigate)
  - Edge cases → PARTIAL (document reasoning)
  
- [ ] Create template document
- **Deliverable:** `docs/outdoor_test_protocol.md` or in `artefacts.md`
- Notes: *(fill)*

**Test runner script structure:**
```bash
#!/bin/bash
# tools/run_outdoor_test.sh
# Usage: ./tools/run_outdoor_test.sh --scenario <name>

SCENARIO=$1
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BAG_DIR="bags/outdoor_${SCENARIO}_${DATE}"

# Pre-flight checks (automated where possible)
echo "=== Pre-flight checks ==="
check_camera_connected || exit 1
check_hailo_temperature || exit 1
check_ros_topics || exit 1

# Run test
echo "=== Running scenario: $SCENARIO ==="
ros2 bag record -a -o $BAG_DIR &
BAG_PID=$!
ros2 launch thesis_bringup outdoor_test.launch.py tracker:=baseline &
LAUNCH_PID=$!

echo "Scenario running... Press ENTER when complete."
read

# Cleanup
kill $BAG_PID
kill $LAUNCH_PID

# Analysis
echo "=== Analyzing results ==="
python3 tools/analyse_bag_timing.py $BAG_DIR/
python3 tools/analyse_bag_tracking.py $BAG_DIR/
python3 tools/generate_outdoor_report.py $BAG_DIR/ --scenario $SCENARIO

echo "=== Test complete. See reports/ for results. ==="
```

### D) Document in artefacts
Add outdoor test protocol to Week 10 artefacts.

- [ ] Create section "Outdoor Test Protocol" in `artefacts.md`
- [ ] Link to:
  - Scenario definitions
  - Success criteria yaml
  - Test runner script
  - Pre-flight checklist
  - Post-run analysis commands
- [ ] Include camera integration notes (for Week 11)
- **Deliverable:** Complete protocol documentation
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] 6 tennis court scenarios fully defined with parameters
- [ ] Success criteria specified with quantitative thresholds
- [ ] Pre-flight checklist created (hardware, software, environment, personnel)
- [ ] Test runner script template created
- [ ] Post-run analysis commands documented
- [ ] Protocol documented in `artefacts.md`

### Scenario definitions
*(Filled in Work Plan section A)*

### Success criteria
*(Filled in Work Plan section B)*

### Test protocol readiness
- Pre-flight checklist: *(Complete / Draft)*
- Run steps: *(Complete / Draft)*
- Post-run analysis: *(Complete / Draft)*
- Pass/fail criteria: *(Defined / Needs refinement)*

**Protocol status:** *(Ready for execution / Needs review / Incomplete)*

**Blockers for execution:**
- Camera hardware (expected Week 11)
- *(Any other blockers?)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Success criteria tuned on indoor/synthetic data may need adjustment for outdoor
- Weather dependency (rain, extreme sun, wind)
- Safety considerations for outdoor testing (people, obstacles)
- Limited access to tennis court (scheduling, availability)

**Risk mitigation:**
- Have backup indoor test scenarios if outdoor not accessible
- Weather contingency: test in morning (lighting) or overcast days
- Safety: always have observer, brief all participants, emergency stop ready

---

## Next steps (Day 07)
- [ ] Implement control interface loss behavior (hold/ramp, target_lost flag)
- [ ] Add prediction horizon with confidence clamping
- [ ] Log control-relevant metrics (ex_px, ey_px distributions, target_valid duty cycle)
- [ ] Generate control stability report

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md` (outdoor protocol section)
- Test protocol doc: `../../docs/outdoor_test_protocol.md`
- Success criteria: `../../config/outdoor_success_criteria.yaml`
- Test runner script: `../../tools/run_outdoor_test.sh`
