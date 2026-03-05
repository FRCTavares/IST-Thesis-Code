# Daily Log — 2026-03-09 — Baseline Freeze and Camera Integration Plan (Week 10, Day 7)

## Goal
Decision week: freeze baseline and plan camera integration. By end of day, you freeze what is "Phase 1 baseline" and define what changes when camera arrives.

**Target outcome:**
- Frozen baseline fully documented (tracker, params, target selector, control_ref)
- Camera integration checklist defined (topic changes, calibration, FPS expectations)
- Clear handoff to Week 11 (camera integration week)
- Week 10 summary complete with all results

**Philosophy:** Lock down what works, document what's frozen, plan the transition.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware arriving Week 11**. Today is planning day for integration. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Phase 1 | Indoor/bag-based testing, frozen baseline |
| Phase 2 | Outdoor testing with camera (Week 11+) |
| Week 10 status | Baseline selected, evaluation suite ready, control stable |

---

## Work Plan

### A) Freeze baseline tracker + parameters
Lock down the tracker configuration that will be used for outdoor testing.

- [ ] **Review Week 10 results:**
  - Day 03: Baseline decision (SORT / OC-SORT / ByteTrack)
  - Day 05: Embedding v1 impact (with/without appearance)
  - Overall: Runtime, tracking quality, robustness
  
- [ ] **Freeze tracker:**
  - Name: *(fill - e.g., OC-SORT)*
  - Version/commit: *(if using external library)*
  - Config file: `config/tracker_baseline_frozen.yaml`
  
- [ ] **Lock parameters:**
  - IoU threshold: *(value)*
  - Track buffer / max age: *(value)*
  - Min hits: *(value)*
  - Appearance weight (w_app): *(value, or 0.0 if disabled)*
  - *(Other tracker-specific params)*
  
- [ ] **Backup tracker:**
  - Name: *(fill)*
  - Rationale: *(why keep as backup - e.g., simpler, more stable, etc.)*
  
- [ ] Document in `weekly.md` "Frozen Baseline" section
  
- **Deliverable:** Frozen tracker config documented
- Notes: *(fill)*

**Frozen tracker configuration:**
```yaml
# config/tracker_baseline_frozen.yaml
tracker:
  name: <OC-SORT / ByteTrack / SORT>
  version: <commit hash or version number>
  
  parameters:
    iou_threshold: <value>
    track_buffer: <value>
    min_hits: <value>
    
    # Appearance (if enabled)
    use_appearance: <true/false>
    appearance_weight: <value>
    appearance_gate_low: <value>
    appearance_gate_high: <value>
    
    # Other params
    # ...
```

### B) Freeze target selector state machine + scoring
Lock down target selector configuration.

- [ ] **State machine:**
  - States: SEARCH, LOCKED, LOST, REACQUIRED ✓
  - Transitions: *(document FSM)*
  - Timeouts:
    - lost_timeout_s: *(value)*
    - reacquire_window_s: *(value)*
  
- [ ] **Score function:**
  - Features: time_alive, freshness, distance, motion, appearance
  - Weights:
    - w_time: *(value)*
    - w_fresh: *(value)*
    - w_dist: *(value)*
    - w_motion: *(value)*
    - w_app: *(value)*
  - Lock threshold: *(value)*
  
- [ ] Document in `config/target_selector_frozen.yaml`
  
- **Deliverable:** Frozen target selector config
- Notes: *(fill)*

**Frozen target selector configuration:**
```yaml
# config/target_selector_frozen.yaml
target_selector:
  state_machine:
    states: [SEARCH, LOCKED, LOST, REACQUIRED]
    lost_timeout_s: <value>
    reacquire_window_s: <value>
  
  scoring:
    features:
      - time_alive
      - freshness
      - distance
      - motion_consistency
      - appearance_similarity  # if available
    
    weights:
      w_time: <value>
      w_fresh: <value>
      w_dist: <value>
      w_motion: <value>
      w_app: <value>
    
    lock_threshold: <value>
```

### C) Freeze control_ref behavior
Lock down control interface configuration.

- [ ] **Rate:** 30 Hz ✓
  
- [ ] **Prediction:**
  - Method: Constant velocity
  - Horizon: *(min, max values)*
  - Confidence decay: *(linear / exponential)*
  - Confidence threshold: *(value)*
  
- [ ] **Loss behavior:**
  - Mode: *(hold / ramp / neutral)*
  - Parameters: *(ramp tau, etc.)*
  
- [ ] **Inputs:**
  - ex_px: cx - W/2
  - ey_px: cy - H/2
  - ez_px: desired_area - area_px
  - target_valid: bool
  
- [ ] Document in `config/control_ref_frozen.yaml`
  
- **Deliverable:** Frozen control_ref config
- Notes: *(fill)*

**Frozen control_ref configuration:**
```yaml
# config/control_ref_frozen.yaml
control_ref:
  rate_hz: 30
  
  prediction:
    method: constant_velocity
    horizon_min_ms: <value>
    horizon_max_ms: <value>
    confidence_decay: <linear/exponential>
    confidence_threshold: <value>
  
  loss_behavior:
    mode: <hold/ramp/neutral>
    ramp_tau_s: <value>  # if ramp mode
  
  inputs:
    coordinate_frame: pixels
    origin: image_center
    ex_px: cx - W/2
    ey_px: cy - H/2
    ez_px: desired_area - area_px
    desired_area_px2: <value>
```

### D) Define camera integration checklist
Plan what changes when camera hardware arrives.

- [ ] **Topics that will change:**
  - `/image_raw` (new): Camera publishes raw images
  - `/camera_info` (new): Camera intrinsics and distortion
  - `/detections`: May have different timestamp source (camera hardware time)
  - `/timing`: Add camera capture time (t_capture)
  
- [ ] **Calibration needs:**
  - Intrinsic calibration: focal length, principal point, distortion coefficients
  - Method: ROS camera_calibration package with checkerboard
  - Output: `camera_info.yaml`
  - Mounting: Pan/tilt angles relative to drone body frame (for control mapping)
  
- [ ] **Expected FPS:**
  - Camera native: *(e.g., 30 FPS at 1920×1080, or 60 FPS at 1280×720)*
  - Inference input: 640×640 @ *(15-30 FPS target)*
  - Considerations: Exposure time (outdoor lighting), motion blur
  
- [ ] **Integration risks:**
  - Image transport bandwidth (USB / CSI)
  - Encoding/decoding overhead
  - Synchronization: camera time vs ROS time
  - Outdoor lighting: exposure, white balance, auto vs manual
  - Thermal: camera + Hailo under sustained load
  
- [ ] **Integration steps (Week 11 plan):**
  1. Connect camera hardware (CSI ribbon or USB)
  2. Test camera driver, verify image publish
  3. Run intrinsic calibration, save camera_info
  4. Integrate camera with inference pipeline (replace file/bag source)
  5. Verify latency budget with camera in loop
  6. Test auto-exposure and FPS lock for outdoor
  7. Run evaluation suite with live camera
  8. First outdoor test (scenario 1: close lateral)
  
- [ ] Document checklist in `artefacts.md` and `weekly.md`
  
- **Deliverable:** Camera integration checklist
- Notes: *(fill)*

**Camera integration checklist:**
```markdown
## Camera Integration Checklist (Week 11)

### Hardware setup
- [ ] Camera physically connected (CSI ribbon / USB)
- [ ] Camera secured and focused
- [ ] Camera mounting angle measured (for control frame transform)

### Driver and topics
- [ ] Camera driver installed and configured
- [ ] `/image_raw` topic publishing at expected rate
- [ ] `/camera_info` topic publishing with valid intrinsics
- [ ] Image format verified (resolution, encoding)

### Calibration
- [ ] Intrinsic calibration completed (checkerboard pattern)
- [ ] `camera_info.yaml` saved and loaded by driver
- [ ] Distortion coefficients validated (undistortion test)

### Pipeline integration
- [ ] Inference node reads from `/image_raw` instead of file/bag
- [ ] Timestamp synchronization verified (camera time → ROS time)
- [ ] Image preprocessing (resize, color conversion) working
- [ ] Detection output quality validated (compare to bag baseline)

### Performance validation
- [ ] Latency budget re-measured with camera in loop
- [ ] FPS achieved: *(target vs actual)*
- [ ] Thermal stability tested (10+ min sustained run)

### Outdoor readiness
- [ ] Auto-exposure tested in outdoor lighting
- [ ] Manual exposure tuning (if auto insufficient)
- [ ] FPS lock configured (avoid variable rate)
- [ ] First outdoor test run (scenario 1)

### Known risks
- Image transport bandwidth: *(mitigation)*
- Lighting variation: *(mitigation)*
- Thermal throttling: *(mitigation)*
```

### E) Complete Week 10 summary
Fill in `weekly.md` with final results and conclusions.

- [ ] Update "What shipped" section with all deliverables
- [ ] Fill in "Numbers" section with metrics from all days
- [ ] Complete "Frozen Baseline" section with locked configs
- [ ] Complete "Camera Integration Plan" section with checklist
- [ ] Write conclusions and next week priorities
  
- **Deliverable:** Complete `weekly.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] Frozen tracker config documented (`config/tracker_baseline_frozen.yaml`)
- [ ] Frozen target selector config documented (`config/target_selector_frozen.yaml`)
- [ ] Frozen control_ref config documented (`config/control_ref_frozen.yaml`)
- [ ] Camera integration checklist created (in `artefacts.md`, `weekly.md`)
- [ ] Week 10 `weekly.md` summary completed

### Frozen Baseline Summary (Phase 1)

**Tracker:**
- Name: *(fill)*
- Key parameters: *(fill)*
- Performance: track_ms p95 = *(value)* ms, switches/min = *(value)*

**Target selector:**
- State machine: SEARCH → LOCKED → LOST → REACQUIRED
- Score weights: *(fill)*
- Performance: lock stability = *(value)* %, reacquire time p95 = *(value)* s

**Control interface:**
- Rate: 30 Hz
- Prediction: constant velocity, horizon = *(value)* ms
- Loss behavior: *(hold / ramp / neutral)*
- Performance: target_valid duty cycle = *(value)* %

**Embedding:**
- Type: *(HSV histogram + gradient / disabled)*
- Impact: *(positive / neutral / not used)*

**Overall system:**
- Latency p95: *(value)* ms (budget: 150 ms)
- Latency p99: *(value)* ms (budget: 200 ms)
- Budget compliance: ✓ PASS / ✗ FAIL

**Baseline locked:** ✓ YES / ✗ NO

### Camera Integration Plan

**Hardware expected:** *(Camera model, connection type)*

**Integration week:** Week 11 (March 10-16, 2026)

**Critical path items:**
1. *(fill - e.g., "Intrinsic calibration")*
2. *(fill - e.g., "Latency validation with camera")*
3. *(fill - e.g., "First outdoor test")*

**Risk mitigation:**
- *(fill)*

**Confidence level:** *(High / Medium / Low)* that outdoor testing will proceed on schedule

---

## Week 10 Retrospective

### What went well
- *(Fill at end of day or week)*

### What was challenging
- *(Fill)*

### Key learnings
- *(Fill)*

### Decisions made
1. Baseline tracker: *(locked)*
2. Target selector: *(state machine + multi-feature scoring)*
3. Control interface: *(30 Hz with prediction and loss handling)*
4. Embedding: *(v1 implemented, impact: ___)*

### What's ready for outdoor
- ✓ Frozen baseline configuration
- ✓ Evaluation suite and metrics
- ✓ Outdoor test protocol
- ✓ Camera integration plan
- ✗ Camera hardware (arriving Week 11)

---

## Issues / Risks
- *(Fill as they arise)*

**Key risks for Week 11:**
- Camera hardware delays
- Calibration issues (distortion, focus)
- Latency increase with camera in loop
- Outdoor performance different from indoor baseline
- Weather (rain, extreme lighting)

---

## Next week plan (Week 11: Camera Integration)
- [ ] Day 10 (03-10): Camera hardware setup, driver install, topic verification
- [ ] Day 11 (03-11): Intrinsic calibration, camera_info validation
- [ ] Day 12 (03-12): Pipeline integration, replace bag source with live camera
- [ ] Day 13 (03-13): Latency validation, FPS lock, thermal test
- [ ] Day 14 (03-14): Auto-exposure tuning, outdoor lighting tests
- [ ] Day 15 (03-15): First outdoor test (scenario 1: close lateral)
- [ ] Day 16 (03-16): Outdoor test suite (scenarios 2-6), results analysis

---

## Links
- Week summary: `../weekly.md` (complete)
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Frozen configs: `../../config/tracker_baseline_frozen.yaml`, etc.
- Camera integration checklist: (in `artefacts.md`)
- Next week: `../W11_2026-03-10_to_03-16/weekly.md` (to be created)
