# Week 10 Index (2026-03-03 to 2026-03-09)

## Week Theme
**From "baseline working" to "demo-ready system with frozen configuration"**

Move from proving the pipeline works to having a locked-down, reproducible baseline ready for outdoor testing when camera hardware arrives.

---

## Quick Links

- [Weekly Summary](weekly.md) — Goals, results, frozen baseline, camera plan
- [Artefacts](artefacts.md) — Code, configs, reports, datasets

---

## Daily Logs

### Day 03 (Monday, 2026-03-03)
**[Lock the Baseline + Clean Evaluation Suite](daily/2026-03-03__freeze-baseline-and-eval-suite.md)**

**Goal:** Single command produces comparison report, justify baseline decision

**Deliverables:**
- Baseline tracker decision locked (SORT / OC-SORT / ByteTrack)
- Scenario registry (`config/eval_scenarios.yaml`)
- Evaluation suite script (`tools/run_eval_suite.sh`)
- Standardized report structure

**Status:** *(Not started / In progress / Complete)*

---

### Day 04 (Tuesday, 2026-03-04)
**[Make Target Selection Robust and Measurable](daily/2026-03-04__target-selector-state-machine.md)**

**Goal:** Target selector survives ambiguity, reacquires correctly with minimal switches

**Deliverables:**
- Multi-feature score function (not just time_alive)
- State machine: SEARCH → LOCKED → LOST → REACQUIRED
- Events: lost_flag, reacquired_flag, lock_id_changes_total
- Ablation report: `reports/compare/W10_target_selector_ablation.md`

**Status:** *(Not started / In progress / Complete)*

---

### Day 05 (Wednesday, 2026-03-05)
**[Embedding v1 End-to-End (Cheap but Real)](daily/2026-03-05__embedding-v1-association.md)**

**Goal:** Association uses appearance term, measure effect on ID switches and reacquisition

**Deliverables:**
- Appearance descriptor v1 (HSV histogram + gradient, 16D)
- Integration into association cost with gating
- Comparison report: `reports/compare/W10_embedding_v1_compare.md`
- Quantified benefit or clear failure reason

**Status:** *(Not started / In progress / Complete)*

---

### Day 06 (Thursday, 2026-03-06)
**[Outdoor Readiness Without the Camera](daily/2026-03-06__outdoor-test-protocol.md)**

**Goal:** Written, executable outdoor protocol and checklist (zero hand-wavy)

**Deliverables:**
- 6 tennis court scenarios defined (distance, motion, persons, challenge)
- Success criteria with concrete numbers (pixel error, reacquire time, switches, latency)
- Pre-flight checklist (hardware, software, environment, personnel)
- Test runner template (`tools/run_outdoor_test.sh`)

**Status:** *(Not started / In progress / Complete)*

---

### Day 07 (Friday, 2026-03-07)
**[Control Interface Tightening and Failure Modes](daily/2026-03-07__control-ref-failure-modes.md)**

**Goal:** 30 Hz control_ref behaves correctly through target loss and reacquisition

**Deliverables:**
- Loss behavior implemented (hold / ramp / neutral)
- Prediction horizon with confidence clamping (200-500 ms)
- Control-relevant metrics logged (ex_px, ey_px, target_valid duty cycle)
- Stability report: `reports/compare/W10_control_ref_stability.md`

**Status:** *(Not started / In progress / Complete)*

---

### Day 08 (Saturday, 2026-03-08)
**[Integrate Tracker Timing into Full Latency Breakdown](daily/2026-03-08__latency-budget-with-tracker.md)**

**Goal:** Single report shows end-to-end budget with tracker split

**Deliverables:**
- Complete latency budget table (recv, json, track_ms, loop, lat, total)
- track_ms CDF plot
- Stacked summary (median and p95)
- Latency budget report: `reports/timing/W10_latency_budget.md`

**Status:** *(Not started / In progress / Complete)*

---

### Day 09 (Sunday, 2026-03-09)
**[Baseline Freeze and Camera Integration Plan](daily/2026-03-09__baseline-freeze-and-camera-plan.md)**

**Goal:** Freeze Phase 1 baseline, define what changes when camera arrives

**Deliverables:**
- Frozen baseline documented (tracker, target selector, control_ref)
- Frozen configs: `config/*_frozen.yaml`
- Camera integration checklist (topics, calibration, FPS, risks)
- Week 10 summary completed in `weekly.md`

**Status:** *(Not started / In progress / Complete)*

---

## Week Goals Tracking

- [ ] Lock baseline tracker decision with justification
- [ ] Standardize evaluation suite (single command → full report)
- [ ] Upgrade target selector with state machine and multi-feature scoring
- [ ] Implement embedding v1 end-to-end with measurable impact
- [ ] Write outdoor test protocol (flight-test style)
- [ ] Tighten control interface with loss/reacquisition handling
- [ ] Integrate tracker timing into full latency breakdown
- [ ] Freeze Phase 1 baseline and define camera integration plan

---

## Key Decisions

### Baseline Tracker
**Decision:** *(SORT / OC-SORT / ByteTrack)*  
**Date:** 2026-03-03 (Day 03)  
**Rationale:** *(To be filled)*

### Target Selector Approach
**Decision:** Multi-feature scoring + explicit FSM  
**Date:** 2026-03-04 (Day 04)  
**Rationale:** "Time alive only" insufficient for multi-person outdoor scenarios

### Embedding Strategy
**Decision:** HSV histogram + gradient descriptor (v1)  
**Date:** 2026-03-05 (Day 05)  
**Rationale:** Cheap baseline with clear interface for future learned embeddings

### Control Loss Behavior
**Decision:** *(hold / ramp / neutral)*  
**Date:** 2026-03-07 (Day 07)  
**Rationale:** *(To be filled)*

---

## Metrics Summary (End of Week)

**Baseline Tracker Performance:**
- track_ms p95: *(value)* ms
- Switches per minute: *(value)*
- Reacquire time p95: *(value)* s

**Target Selector Improvement:**
- Lock stability: *(before)* % → *(after)* %
- False reacquisitions: *(before)* → *(after)* count

**Embedding v1 Impact:**
- ID switches reduction: *(with vs without)* %
- Runtime overhead: *(value)* ms

**Control Stability:**
- Control rate: *(value)* Hz (target: 30 Hz)
- target_valid duty cycle: *(value)* %

**Latency Budget:**
- End-to-end p95: *(value)* ms (target: < 150 ms)
- End-to-end p99: *(value)* ms (target: < 200 ms)
- Budget compliance: ✓ PASS / ✗ FAIL

---

## Camera Integration Readiness

**Frozen baseline:** ✓ YES / ✗ NO  
**Outdoor protocol:** ✓ YES / ✗ NO  
**Integration checklist:** ✓ YES / ✗ NO  
**Camera hardware:** ✗ NO (expected Week 11)

**Confidence for Week 11:** *(High / Medium / Low)*

---

## Related Weeks

- **Previous:** [Week 09 (2026-02-24 to 03-02)](../W09_2026-02-24_to_03-02/index.md) — Tracker benchmarking, occlusion tests, 30 Hz control stub
- **Next:** [Week 11 (2026-03-10 to 03-16)](../W11_2026-03-10_to_03-16/index.md) — Camera integration, first outdoor tests (to be created)

---

## Notes
*(Add any week-level observations, blockers, or insights)*
