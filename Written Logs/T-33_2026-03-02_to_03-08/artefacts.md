# T-33 Artefacts (2026-03-03 to 2026-03-09)

## Overview
This document tracks all deliverables, code, configurations, reports, and datasets produced during T-33.

**T-33 theme:** From "baseline working" to "demo-ready system with frozen configuration"

---

## Code and Configuration

### Tracker Implementation
- **Baseline tracker node:** `ros2_ws/src/thesis_bringup/nodes/tracker_<baseline>_node.py`
- **Frozen configuration:** `config/tracker_baseline_frozen.yaml`
- **Backup tracker:** `ros2_ws/src/thesis_bringup/nodes/tracker_<backup>_node.py`
- **Appearance module:** `thesis_vision_utils/appearance.py` (if implemented)

**Status:** *(In progress / Complete)*

**Key parameters (frozen):**
```yaml
# To be filled from Day 09 results
```

### Target Selector Upgrade
- **Enhanced target selector node:** `ros2_ws/src/thesis_bringup/nodes/target_selector_node.py`
- **State machine implementation:** SEARCH → LOCKED → LOST → REACQUIRED
- **Frozen configuration:** `config/target_selector_frozen.yaml`

**Status:** *(In progress / Complete)*

**Features added:**
- Multi-feature score function (time_alive, freshness, distance, motion, appearance)
- Explicit FSM with state transitions
- Events: lost_flag, reacquired_flag, lock_id_changes_total

### Control Interface
- **Control reference node:** `ros2_ws/src/thesis_bringup/nodes/thesis_control_ref_node.py`
- **Frozen configuration:** `config/control_ref_frozen.yaml`

**Status:** *(In progress / Complete)*

**Features implemented:**
- 30 Hz output with prediction
- Loss behavior: *(hold / ramp / neutral)*
- Prediction horizon with confidence clamping
- Control-relevant metrics logging

### Evaluation Suite
- **Evaluation runner script:** `tools/run_eval_suite.sh`
- **Scenario registry:** `config/eval_scenarios.yaml`
- **Analysis scripts:**
  - `tools/analyse_bag_timing.py` (updated)
  - `tools/analyse_bag_tracking.py` (updated/created)
  - `tools/analyse_control_ref.py` (created)
  - `tools/analyse_latency_budget.py` (created)
- **Report template:** `tools/templates/eval_report_template.md`

**Status:** *(In progress / Complete)*

**Scenarios defined:**
- clean: No perturbations
- occlusion_1s: 1 second synthetic occlusion
- full_occlusion: Overlap-based occlusion
- ambiguous_crossing: Multi-person crossing
- *(others)*

---

## Reports and Analysis

### Day 03: Baseline Decision
- **Comparison report:** `reports/compare/T-33_tracker_compare_baseline_decision.md`
- **Decision rationale:** *(To be filled)*
- **Baseline chosen:** *(SORT / OC-SORT / ByteTrack)*

**Key metrics:**
- Runtime: track_ms p95 = *(value)* ms
- Tracking quality: switches/min = *(value)*
- Occlusion resilience: reacquire time p95 = *(value)* s

### Day 04: Target Selector Ablation
- **Ablation report:** `reports/compare/T-33_target_selector_ablation.md`
- **Comparison:** time_alive only vs multi-feature + FSM

**Key findings:**
- Improvement in switches/min: *(before → after)*
- Lock stability improvement: *(before → after)*
- Reacquisition accuracy: *(before → after)*

### Day 05: Embedding v1 Impact
- **Comparison report:** `reports/compare/T-33_embedding_v1_compare.md`
- **Appearance descriptor:** HSV histogram + gradient, *(dimensions)*
- **Impact:** *(positive / neutral / negative)*

**Key findings:**
- ID switches reduction: *(with vs without)*
- Runtime overhead: *(track_ms increase)*
- Scenarios where appearance helps: *(list)*

### Day 06: Outdoor Test Protocol
- **Protocol document:** `docs/outdoor_test_protocol.md` or section below
- **Success criteria:** `config/outdoor_success_criteria.yaml`
- **Test runner script:** `tools/run_outdoor_test.sh`

**Status:** *(Complete / Draft)*

### Day 07: Control Stability
- **Stability report:** `reports/compare/T-33_control_ref_stability.md`
- **Loss behavior validation:** *(hold / ramp / neutral)*
- **Prediction performance:** *(stats)*

**Key findings:**
- Control rate achieved: *(value)* Hz
- target_valid duty cycle: *(value)* %
- Smooth transitions: *(yes / issues noted)*

### Day 08: Latency Budget
- **Latency budget report:** `reports/timing/T-33_latency_budget.md`
- **Full breakdown:** recv, json, track_ms, loop, total
- **Budget compliance:** p95 = *(value)* ms, p99 = *(value)* ms

**Key findings:**
- Bottleneck: *(dominant stage)*
- Headroom: *(ms or %)*
- Meets budget: ✓ PASS / ✗ FAIL

### Day 09: Baseline Freeze
- **Frozen baseline document:** Section in `weekly.md`
- **Camera integration plan:** Section in `weekly.md` and below

---

## Figures and Plots

### Tracker Comparison
- `figures/compare/T-33_tracker_compare_track_ms_cdf.png`
- `figures/compare/T-33_tracker_compare_reacquire_time.png`
- `figures/compare/T-33_tracker_compare_switches.png`

### Target Selector
- `figures/tracking/T-33_target_selector_lock_timeline.png`
- `figures/tracking/T-33_target_selector_state_distribution.png`

### Embedding
- `figures/tracking/T-33_embedding_v1_appearance_distance.png`
- `figures/compare/T-33_embedding_v1_id_switches_compare.png`

### Control
- `figures/compare/T-33_control_ref_error_distribution.png`
- `figures/compare/T-33_control_ref_timeline.png`
- `figures/compare/T-33_control_ref_target_valid.png`

### Latency
- `figures/timing/T-33_latency_budget_breakdown.png`
- `figures/timing/T-33_track_ms_cdf.png`
- `figures/timing/T-33_latency_total_cdf.png`

**Status:** *(To be generated)*

---

## Outdoor Test Protocol

### Scenarios Defined

| Scenario | Distance | Motion | Persons | Key Challenge | Duration | Success Criteria |
|----------|----------|--------|---------|---------------|----------|------------------|
| 1. Close lateral | 5 m | Lateral 2 m/s | 1 | Smooth tracking | 20-30 s | pixel error p95 < 20 px |
| 2. Medium approach | 10-20 m | Toward drone | 1 | Scale change | 20-30 s | continuous lock |
| 3. Net occlusion | 10 m | Behind net | 1 | Reacquisition | 15-20 s | reacquire p95 < 1 s |
| 4. Crossing | 5-10 m | Cross paths | 2 | ID consistency | 15-20 s | 0 ID switches |
| 5. Stop and turn | 10 m | Stop, turn 180° | 1 | Motion change | 20-30 s | maintain lock |
| 6. Clutter | 10 m | Lateral | 1 | Background | 20-30 s | no false positives |

### Success Criteria (Quantitative)

**Tracking:**
- Pixel error p50 < 10 px, p95 < 20 px

**Reacquisition:**
- Time p50 < 0.5 s, p95 < 1.0 s

**Robustness:**
- Switches per minute < 2
- Lock stability > 90%
- target_valid duty cycle > 85%

**Latency:**
- End-to-end p95 < 150 ms, p99 < 200 ms

**Control:**
- Output rate: 30 Hz ± 1 Hz
- Max gap < 50 ms

**Detection:**
- Detection rate > 95% (when visible)
- False positive rate < 5%

### Pre-flight Checklist

**Hardware:**
- [ ] Camera connected, secured, focused
- [ ] Hailo AI HAT+ temperature < 70°C
- [ ] Pixhawk armed, GPS lock (optional)

**Software:**
- [ ] All nodes launched, topics publishing
- [ ] Bag recording started
- [ ] Latency within budget (pre-flight test)

**Environment:**
- [ ] Lighting adequate (avoid direct sun)
- [ ] Wind < 5 m/s (if flying)
- [ ] Tennis court accessible, clear

**Personnel:**
- [ ] Target person briefed
- [ ] Safety observer designated
- [ ] Emergency stop ready

### Test Runner Commands

**Start test:**
```bash
./tools/run_outdoor_test.sh --scenario close_lateral
```

**Post-run analysis:**
```bash
python3 tools/analyse_bag_timing.py bags/outdoor_<scenario>_<date>/
python3 tools/analyse_bag_tracking.py bags/outdoor_<scenario>_<date>/
python3 tools/generate_outdoor_report.py bags/outdoor_<scenario>_<date>/ \
    --scenario <scenario> --criteria config/outdoor_success_criteria.yaml
```

**Check success:**
```bash
python3 tools/check_success.py reports/outdoor_<scenario>_<date>.md
```

---

## Camera Integration Plan (T-32)

### Topics That Will Change
- `/image_raw` (new): Camera publishes raw images
- `/camera_info` (new): Intrinsics and distortion
- `/detections`: Different timestamp source
- `/timing`: Add t_capture field

### Calibration Needs
- **Intrinsic calibration:** Focal length, principal point, distortion (ROS camera_calibration)
- **Output:** `camera_info.yaml`
- **Mounting:** Pan/tilt angles relative to drone body

### Expected FPS
- Camera native: *(30 FPS @ 1920×1080 or higher)*
- Inference input: 640×640 @ 15-30 FPS
- Considerations: Exposure (outdoor), motion blur

### Integration Checklist
See [2026-03-09 daily log](daily/2026-03-09__baseline-freeze-and-camera-plan.md) for complete checklist.

**Critical path:**
1. Hardware connection and driver
2. Intrinsic calibration
3. Pipeline integration (replace bag source)
4. Latency validation
5. Outdoor lighting tuning
6. First outdoor test

### Known Risks
- Image transport bandwidth
- Lighting variation (auto-exposure)
- Thermal throttling (camera + Hailo)
- Synchronization (camera time vs ROS time)

**Mitigation:**
- Pre-test bandwidth and encoding
- Manual exposure tuning if needed
- Thermal monitoring and cooling
- Timestamp synchronization validation

---

## Bags and Datasets

### Evaluation Bags (from T-34, reused)
- `bags/raw/2026-02-25__slice__primary/` — Primary evaluation bag
- `bags/raw/2026-02-26__slice__longrun/` — Long-run validation
- *(Others as used)*

### T-33 Test Runs
- `bags/T-33_clean_baseline/` — Clean scenario, baseline tracker
- `bags/T-33_occlusion_baseline/` — Occlusion scenario
- `bags/T-33_ambiguous_baseline/` — Multi-person crossing (if available)
- *(To be recorded)*

**Status:** *(To be created)*

---

## Configurations (Frozen)

### Tracker Baseline
**File:** `config/tracker_baseline_frozen.yaml`

```yaml
# To be filled from Day 09
```

### Target Selector
**File:** `config/target_selector_frozen.yaml`

```yaml
# To be filled from Day 04/09
```

### Control Reference
**File:** `config/control_ref_frozen.yaml`

```yaml
# To be filled from Day 07/09
```

### Evaluation Scenarios
**File:** `config/eval_scenarios.yaml`

```yaml
# To be filled from Day 03
```

### Outdoor Success Criteria
**File:** `config/outdoor_success_criteria.yaml`

```yaml
# To be filled from Day 06
```

---

## Dependencies and Versions

### ROS 2 Packages
- ROS 2 Jazzy
- `thesis_bringup` — Custom launch and nodes
- `thesis_msgs` — Custom message definitions (Track2DArray, Timing, etc.)

### Python Libraries
- OpenCV: *(version)*
- NumPy: *(version)*
- SciPy: *(version)* (for tracker implementations)
- Matplotlib: *(version)* (for plots)
- PyYAML: *(version)*

### Tracker Libraries
- SORT: *(source, commit)*
- OC-SORT: *(source, commit)* (if used)
- ByteTrack: *(source, commit)* (if used)

### Inference
- Hailo AI HAT+ with *(model name, version)*
- GStreamer pipeline
- ZMQ for detections transport

**Status:** *(To be documented)*

---

## Links
- Week summary: [weekly.md](weekly.md)
- Week index: [index.md](index.md)
- Previous week: [T-34 artefacts](../T-34_2026-02-24_to_03-02/artefacts.md)
- Next week: [T-32 artefacts](../T-32_2026-03-10_to_03-16/artefacts.md) (to be created)

---

## Notes
*(Add any additional notes, observations, or context throughout the week)*
