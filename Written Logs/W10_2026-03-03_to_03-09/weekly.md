# Weekly Summary — W10 (2026-03-03 to 2026-03-09)

## Week 10 Ambition Targets (by end of Mar 9)

Move from "baseline working" to "demo-ready system with frozen configuration."

By end of Day 09 (March 9), you should have:

1. **One chosen baseline tracker** (decision locked) + 1 strong backup
   - Baseline tracker frozen with locked parameters
   - Backup tracker validated and documented

2. **Target selection logic upgraded** to handle multi-person scenes robustly
   - Not just "time alive only"
   - Explicit state machine: SEARCH → LOCKED → LOST → REACQUIRED
   - Score function using multiple features (time_alive, freshness, distance, motion, appearance)

3. **Outdoor test protocol ready** (even if no camera yet)
   - Scripted runs with checklists
   - Clear success criteria
   - Executable protocol like a flight test

4. **Embedding v1 running end-to-end** (even if simple)
   - Quantified benefit or clear failure reason
   - Appearance term in association cost

5. **Control interface demo**
   - 30 Hz control_ref stable
   - Loss handling and reacquisition events
   - Prediction with confidence clamping

**System requirements:**
- Outdoor tennis court target environment
- Full online processing
- 15 FPS perception, 30 Hz control
- Latency budget: 200 ms max
- Multi-person robustness

---

## Goals for the week
- [ ] Lock baseline tracker decision with justification
- [ ] Standardize evaluation suite (single command → full report)
- [ ] Upgrade target selector with state machine and multi-feature scoring
- [ ] Implement embedding v1 end-to-end with measurable impact
- [ ] Write outdoor test protocol (flight-test style)
- [ ] Tighten control interface with loss/reacquisition handling
- [ ] Integrate tracker timing into full latency breakdown
- [ ] Freeze Phase 1 baseline and define camera integration plan

---

## Daily Goals Summary

### Day 03 (03-03): Lock the baseline + clean evaluation suite
**Outcome:** A single command produces a comparison report, and you can justify why your baseline is baseline.

**Key deliverables:**
- Baseline tracker decision locked (likely OC-SORT or ByteTrack)
- Scenario registry (yaml) with clean, occlusion, ambiguity tests
- `tools/run_eval_suite.sh` for automated evaluation

### Day 04 (03-04): Make target selection robust and measurable
**Outcome:** Target selection survives ambiguity and reacquires correctly with minimal switches.

**Key deliverables:**
- Multi-feature score function (not just time_alive)
- State machine: SEARCH → LOCKED → LOST → REACQUIRED
- Events: lost_flag, reacquired_flag, lock_id_changes_total
- Ablation report showing improvement

### Day 05 (03-05): Embedding v1 end-to-end (cheap but real)
**Outcome:** Association uses appearance term, measure effect on ID switches and reacquisition.

**Key deliverables:**
- Appearance descriptor v1 (HSV histogram + gradient, 16D)
- Plugged into association cost with gating
- Comparison report: with vs without appearance

### Day 06 (03-06): Outdoor readiness without the camera
**Outcome:** Written, executable outdoor protocol and checklist (zero hand-wavy).

**Key deliverables:**
- Tennis court scenarios defined (5m, 10-20m, lateral, crossing, etc.)
- Success criteria with numbers (pixel error, reacquire time, switches, latency)
- Test runner template with pre-flight checklist

### Day 07 (03-07): Control interface tightening and failure modes
**Outcome:** 30 Hz control_ref behaves correctly through target loss and reacquisition.

**Key deliverables:**
- Loss behavior (hold/ramp, target_lost flag)
- Prediction horizon with confidence clamping
- Control-relevant metrics logged and reported

### Day 08 (03-08): Integrate /timing_tracker into full latency breakdown
**Outcome:** Single report shows end-to-end budget with tracker split.

**Key deliverables:**
- Complete latency budget table (recv, json, track_ms, loop, lat)
- track_ms CDF plot
- Stacked summary (median and p95)

### Day 09 (03-09): Decision week: freeze baseline and plan camera integration
**Outcome:** Freeze "Phase 1 baseline" and define what changes when camera arrives.

**Key deliverables:**
- Frozen baseline documented (tracker, params, target selector, control_ref)
- Camera integration checklist (topic changes, calibration, expected FPS)
- Clear handoff to Week 11 (camera integration week)

---

## What shipped (bulletproof facts)
*(Fill at end of week)*

---

## Numbers
*(Fill at end of week)*

**Baseline tracker performance:**

| Metric | Baseline | Backup | Notes |
|--------|----------|--------|-------|
| track_ms p95 | — | — | |
| Target switches | — | — | per minute |
| Reacquire time p95 | — | — | seconds |
| ID switch proxy | — | — | count per run |

**Target selector upgrade:**

| Metric | Before (time_alive only) | After (multi-feature) | Notes |
|--------|--------------------------|----------------------|-------|
| Switches per minute | — | — | |
| False reacquisitions | — | — | |
| Lock stability | — | — | % time locked |

**Embedding v1 impact:**

| Scenario | Without appearance | With appearance | Improvement |
|----------|-------------------|-----------------|-------------|
| Clean | — | — | — |
| Occlusion 1s | — | — | — |
| Ambiguous crossing | — | — | — |

**Control interface:**

| Metric | Target | Achieved | Notes |
|--------|--------|----------|-------|
| control_ref rate | 30 Hz | — | |
| target_valid duty cycle | — | — % | |
| Reacquire event latency | < 1s | — | p95 |

---

## Frozen Baseline (Phase 1)
*(Fill on Day 09)*

**Tracker:**
- Name: *(OC-SORT / ByteTrack / other)*
- Config: `config/tracker_<name>.yaml`
- Key parameters: *(list locked values)*

**Target selector:**
- State machine: SEARCH → LOCKED → LOST → REACQUIRED
- Score function: `w_time * time_alive + w_fresh * freshness - w_dist * distance + w_motion * consistency + w_app * appearance`
- Weights: *(list locked values)*

**Control interface:**
- Rate: 30 Hz
- Prediction horizon: 200-500 ms
- Loss behavior: *(hold / ramp)*
- Inputs: ex_px, ey_px, ez_px, target_valid

**Embedding:**
- Type: *(descriptor v1 / placeholder / none)*
- Dimensions: 16D
- Cost weight: w_app = *(value)*

---

## Camera Integration Plan (Week 11)
*(Fill on Day 09)*

**Topics that will change:**
- *(Fill - e.g., /image source, /detections timing, etc.)*

**Calibration needs:**
- *(Fill - intrinsics, distortion, mounting angle, etc.)*

**Expected FPS:**
- *(Fill - target 15-30 FPS at 640x640)*

**Integration risks:**
- *(Fill - exposure, motion blur, outdoor lighting, etc.)*

---

## Issues / risks
*(Fill throughout week)*

---

## Next week plan (Week 11)
- [ ] Camera hardware bringup (CSI ribbon, driver, format)
- [ ] Calibrate camera (intrinsics, distortion)
- [ ] First outdoor test runs with frozen baseline
- [ ] Validate latency budget with camera in loop
- [ ] Update embedding with real images if needed

---

## Links
- Week index: `index.md`
- Artefacts: `artefacts.md`
- Previous week: `../W09_2026-02-24_to_03-02/weekly.md`
