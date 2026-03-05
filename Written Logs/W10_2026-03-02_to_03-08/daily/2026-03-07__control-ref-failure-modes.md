# Daily Log — 2026-03-07 — Control Interface Tightening and Failure Modes (Week 10, Day 5)

## Goal
Control interface tightening and failure modes. By end of day, 30 Hz control_ref behaves correctly through target loss and reacquisition.

**Target outcome:**
- Loss behavior defined and implemented (hold/ramp setpoints, target_lost flag)
- Prediction horizon with confidence clamping (200-500 ms)
- Control-relevant metrics logged and analyzed
- Stability report showing control_ref behavior through loss/reacquisition events

**Philosophy:** Control must be rock-solid and predictable, especially during failures.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, testing with bag replay. Camera integration Week 11. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Control node | `thesis_control_ref_node` (implemented Day 02, Week 9) |
| Current status | 30 Hz output, basic constant velocity prediction |
| Upgrade goal | Robust loss handling, confidence-based prediction clamping |

---

## Work Plan

### A) Implement loss behavior
Define and implement control behavior when target is LOST.

- [ ] **Option 1: Hold last known setpoint**
  - When target_valid = False, freeze control outputs at last known values
  - Pros: Simple, no unexpected motion
  - Cons: May drift if vehicle already moving
  - Best for: Stationary or slow-moving scenarios
  
- [ ] **Option 2: Ramp down velocity**
  - Gradually reduce velocity command to zero over N seconds
  - Exponential decay: `v_t = v_0 * exp(-t / tau)`
  - Pros: Smooth stop, safer for moving scenarios
  - Cons: More complex, requires velocity state
  - Best for: Dynamic scenarios, outdoor with motion
  
- [ ] **Option 3: Return to neutral**
  - Command return to center position (ex=0, ey=0, ez=0)
  - Pros: Predictable, easy for higher-level control
  - Cons: May cause sudden motion if far from center
  - Best for: Known setpoint scenarios
  
- [ ] **Decision:** *(fill - likely Option 1 or 2)*
  
- [ ] Implement chosen behavior:
  ```python
  if target_valid:
      # Normal prediction-based control
      control_ref = predict_and_publish(target_state)
  else:
      if loss_behavior == "hold":
          control_ref = last_valid_control_ref
      elif loss_behavior == "ramp":
          control_ref = ramp_down(last_valid_control_ref, time_since_loss)
      elif loss_behavior == "neutral":
          control_ref = neutral_setpoint
  ```
  
- [ ] Publish `target_lost` flag in `/control_ref` message
  
- [ ] Add parameter: `loss_behavior` = "hold" | "ramp" | "neutral"
  
- [ ] Test with occlusion scenario (target goes LOST)
  
- **Deliverable:** Updated `thesis_control_ref_node` with loss handling
- Notes: *(fill)*

**Loss behavior decision:**
- Chosen: *(hold / ramp / neutral)*
- Rationale: *(fill)*
- Parameter: `loss_tau` = *(value)* s (if ramp)

### B) Add prediction horizon
Implement confidence-based prediction with clamping.

- [ ] Define prediction horizon parameters:
  - `prediction_horizon_min`: 50 ms (use fresh data if available)
  - `prediction_horizon_max`: 500 ms (don't predict beyond this)
  - `confidence_threshold`: 0.5 (below this, reduce confidence in prediction)
  
- [ ] Implement confidence-based prediction:
  ```python
  time_since_update = now - last_tracker_update_time
  
  if time_since_update < prediction_horizon_min:
      # Fresh data, use directly
      control_ref = compute_from_track(target_track)
      prediction_confidence = 1.0
  
  elif time_since_update < prediction_horizon_max:
      # Predict with decaying confidence
      predicted_state = constant_velocity_predict(target_track, time_since_update)
      prediction_confidence = 1.0 - (time_since_update / prediction_horizon_max)
      
      if prediction_confidence < confidence_threshold:
          # Clamp: reduce gain or switch to loss behavior
          control_ref = apply_gain(predicted_state, gain=prediction_confidence)
      else:
          control_ref = compute_from_predicted(predicted_state)
  
  else:
      # Too old, switch to loss behavior
      target_valid = False
      control_ref = loss_behavior_output()
  ```
  
- [ ] Add `prediction_age_ms` and `prediction_confidence` to `/control_ref` message
  
- [ ] Log prediction statistics:
  - Distribution of prediction ages
  - % of outputs using prediction vs fresh data
  - Confidence distribution
  
- [ ] Test with various detection rates (15 FPS, 10 FPS, 5 FPS via synthetic drop)
  
- **Deliverable:** Prediction with confidence clamping
- Notes: *(fill)*

**Prediction parameters:**
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| horizon_min | 50 ms | 2 control cycles, always predict slightly |
| horizon_max | 500 ms | Beyond this, data too stale |
| confidence_threshold | 0.5 | Below half confidence, reduce trust |
| confidence_decay | Linear | *(or exponential)* |

### C) Log control-relevant metrics
Capture metrics needed to validate control stability.

- [ ] **Error distributions:**
  - ex_px: Mean, std, p95, p99, min, max
  - ey_px: Mean, std, p95, p99, min, max
  - ez_px: Mean, std, p95, p99, min, max
  - Combined error: `sqrt(ex^2 + ey^2)`
  
- [ ] **target_valid duty cycle:**
  - % of time with target_valid = True
  - Continuous lock duration: longest segment without loss
  - Loss event frequency: events per minute
  
- [ ] **Prediction usage:**
  - % of outputs using prediction (age > horizon_min)
  - % of outputs with low confidence (< threshold)
  - Mean prediction age when predicting
  
- [ ] **Output stability:**
  - Control setpoint velocity: `d(control_ref)/dt`
  - Jerk: acceleration changes (smoothness indicator)
  - Gaps in output: any missed 30 Hz cycles
  
- [ ] Extend analysis script or create `tools/analyse_control_ref.py`
  
- [ ] Generate plots:
  - ex_px, ey_px time series
  - Error distribution (histogram or CDF)
  - target_valid timeline
  - Prediction age vs confidence
  
- **Deliverable:** Control metrics logged and analyzed
- Notes: *(fill)*

**Analysis outputs:**
```bash
python3 tools/analyse_control_ref.py bags/test_bag/ --report reports/compare/W10_control_ref_stability.md
```

### D) Generate stability report
Document control_ref behavior with evidence.

- [ ] Run test bag through updated control node
- [ ] Extract all metrics from C
- [ ] Create report: `reports/compare/W10_control_ref_stability.md`
- [ ] Include:
  - Behavior during normal tracking (LOCKED)
  - Behavior during loss (LOST)
  - Behavior during reacquisition (LOST → LOCKED transition)
  - Prediction usage statistics
  - Evidence: plots showing smooth transitions
- **Deliverable:** `reports/compare/W10_control_ref_stability.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] Loss behavior implemented (hold/ramp/neutral)
- [ ] Prediction horizon with confidence clamping
- [ ] Control-relevant metrics logged
- [ ] `tools/analyse_control_ref.py` created or extended
- [ ] `reports/compare/W10_control_ref_stability.md` generated

### Loss behavior implementation
- Chosen behavior: *(hold / ramp / neutral)*
- Parameters: *(fill)*
- Tested on: *(occlusion scenario, synthetic loss, etc.)*
- Result: *(smooth transition / issues / etc.)*

### Prediction horizon performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| % fresh data (< 50 ms) | — % | > 60% | — |
| % predicted (50-500 ms) | — % | 20-40% | — |
| % stale (> 500 ms) | — % | < 5% | — |
| Mean prediction age | — ms | < 100 ms | — |
| Prediction confidence p50 | — | > 0.7 | — |

### Control-relevant metrics

**Error distributions (LOCKED state only):**
| Error | Mean | Std | p95 | p99 | Target |
|-------|------|-----|-----|-----|--------|
| ex_px | — | — | — | — | p95 < 20 |
| ey_px | — | — | — | — | p95 < 20 |
| combined | — | — | — | — | p95 < 20 |

**target_valid duty cycle:**
- % time valid: — % (target: > 85%)
- Continuous lock (longest): — s
- Loss events: — per minute (target: < 2)

**Output stability:**
- Control rate achieved: — Hz (target: 30 Hz)
- Max gap: — ms (target: < 50 ms)
- Setpoint jerk p95: — (lower is smoother)

**Plots:**
- *(Reference to generated plots)*

### Behavior through loss/reacquisition event

**Example event timeline:**
```
t=10.0s: LOCKED, ex=5px, ey=-3px, target_valid=True
t=10.5s: Occlusion starts, detections drop
t=10.6s: LOST, switch to hold behavior, ex=5px (frozen), target_valid=False
t=11.2s: Target reappears, REACQUIRED
t=11.3s: LOCKED, ex=8px, ey=2px, target_valid=True
```

**Observations:**
- *(fill - smooth transition? Spikes? Issues?)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Prediction accuracy depends on motion model (constant velocity may be poor for complex motion)
- Confidence decay tuning requires outdoor testing
- Loss behavior choice impacts higher-level control (e.g., ArduPilot integration)

---

## Next steps (Day 08)
- [ ] Integrate tracker timing (`track_ms`) into full latency breakdown
- [ ] Create complete latency budget table (recv, json, track, loop, lat)
- [ ] Generate track_ms CDF plot
- [ ] Produce stacked latency summary report

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Stability report: `../../reports/compare/W10_control_ref_stability.md`
- Control analysis script: `../../tools/analyse_control_ref.py`
- Config: `../../config/control_ref.yaml`
