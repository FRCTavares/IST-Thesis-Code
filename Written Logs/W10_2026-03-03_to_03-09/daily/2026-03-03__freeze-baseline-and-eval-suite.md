# Daily Log — 2026-03-03 — Lock the Baseline + Clean Evaluation Suite (Week 10, Day 1)

## Goal
Lock the baseline tracker and create a clean evaluation suite. By end of day, a single command produces a comparison report, and you can justify why your baseline is baseline.

**Target outcome:**
- Baseline tracker decision locked with clear justification
- Standardized evaluation outputs (consistent report structure)
- Scenario registry defining all test cases
- Automated evaluation suite (`run_eval_suite.sh`)

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay. Camera integration planned for Week 11. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court |
| Perception target | 15 FPS |
| Control target | 30 Hz with prediction |
| Latency budget | 200 ms max |
| Week 9 results | 3 trackers tested: SORT, OC-SORT, ByteTrack (or transformer) |

---

## Work Plan

### A) Choose baseline tracker now
Decision time: pick the winner from Week 9 results.

- [ ] Review Week 9 comparison data:
  - Runtime performance (track_ms p95, p99)
  - Tracking quality (target switches, reacquire time, lock continuity)
  - Occlusion resilience
  - Implementation stability (crashes, edge cases)
- [ ] Make decision: *(likely OC-SORT or ByteTrack)*
- [ ] Lock parameters in `config/tracker_<name>.yaml`
- [ ] Document decision rationale
- **Deliverable:** Decision locked in `artefacts.md` with justification
- Notes: *(fill)*

**Decision criteria:**
| Criterion | Weight | SORT | OC-SORT | ByteTrack/Other | Winner |
|-----------|--------|------|---------|-----------------|--------|
| Runtime (track_ms p95 < 10ms) | High | — | — | — | — |
| Occlusion handling | High | — | — | — | — |
| ID consistency | High | — | — | — | — |
| Implementation stability | Medium | — | — | — | — |
| Parameter sensitivity | Medium | — | — | — | — |

**Baseline decision:** *(fill)*

**Locked parameters:**
```yaml
# config/tracker_<baseline>.yaml
# (fill with locked values)
```

### B) Standardise evaluation outputs
Ensure all runs produce consistent, comparable reports.

- [ ] Define standard report structure:
  - `reports/tracking/W10_<tracker>_<scenario>/summary.md`
  - Sections: Context, Metrics table, Plots, Conclusion
- [ ] Define standard figure naming:
  - `figures/tracking/W10_<tracker>_<scenario>_<metric>.png`
  - e.g., `W10_ocsort_occlusion1s_reacquire_cdf.png`
- [ ] Update analysis scripts to follow convention
- [ ] Create template: `tools/templates/eval_report_template.md`
- **Deliverable:** Consistent output format across all evaluations
- Notes: *(fill)*

**Report sections (template):**
1. Scenario description
2. Tracker configuration
3. Metrics table (runtime, quality)
4. Time-series plots
5. CDF plots (reacquire time, track_ms)
6. Conclusion and recommendations

### C) Create a "scenario registry"
A yaml file defining all test scenarios with exact parameters.

- [ ] Create `config/eval_scenarios.yaml`:
  - **clean:** No synthetic perturbations
  - **occlusion_1s:** Drop target detections for 1.0 s
  - **full_occlusion:** Simulate person walking in front (overlap-based)
  - **ambiguous_crossing:** Two persons crossing close
  - *(Add more as needed)*
- [ ] Each scenario includes:
  - Name, description
  - Input bag
  - Occluder parameters (if applicable)
  - Success criteria
- [ ] Document how to add new scenarios
- **Deliverable:** `config/eval_scenarios.yaml`
- Notes: *(fill)*

**Example scenario definition:**
```yaml
scenarios:
  clean:
    name: "Clean baseline"
    description: "No perturbations, baseline performance"
    bag: "bags/raw/2026-02-25__slice__primary"
    occluder: null
    success_criteria:
      track_ms_p95: 10.0  # ms
      switches_per_min: 0.5
      reacquire_p95: 0.5  # s
  
  occlusion_1s:
    name: "1 second occlusion"
    description: "Target hidden for 1.0 s, test reacquisition"
    bag: "bags/raw/2026-02-25__slice__primary"
    occluder:
      mode: "fixed_duration"
      duration_s: 1.0
      start_time: 30.0  # s into bag
    success_criteria:
      reacquire_p95: 1.5  # s
      id_switches: 1  # max acceptable
```

### D) Add a top-level evaluation command
Create `tools/run_eval_suite.sh` to automate the full evaluation.

- [ ] Script accepts arguments:
  - `--tracker <name>` (baseline, sort, ocs, bytetrack)
  - `--scenario <name>` (clean, occlusion_1s, etc.)
  - `--all` (run all scenarios for given tracker)
- [ ] Script performs:
  1. Launch replay with specified tracker and scenario
  2. Record output bag
  3. Run analysis scripts
  4. Generate markdown report and figures
  5. Save to standard locations
- [ ] Add usage documentation
- **Deliverable:** `tools/run_eval_suite.sh`
- Notes: *(fill)*

**Usage:**
```bash
# Run single evaluation
./tools/run_eval_suite.sh --tracker ocsort --scenario clean

# Run all scenarios for baseline
./tools/run_eval_suite.sh --tracker ocsort --all

# Compare all trackers on one scenario
./tools/run_eval_suite.sh --scenario occlusion_1s --all-trackers
```

---

## Results

### Deliverables checklist
- [ ] Baseline tracker decision locked with justification
- [ ] Standard report structure defined and documented
- [ ] `config/eval_scenarios.yaml` created
- [ ] `tools/run_eval_suite.sh` implemented and tested
- [ ] `tools/templates/eval_report_template.md` created

### Baseline decision

**Chosen baseline:** *(fill)*

**Justification:**
- *(Fill from Week 9 data analysis)*
- Runtime: track_ms p95 = *(value)* ms
- Occlusion handling: reacquire p95 = *(value)* s
- ID consistency: switches per minute = *(value)*
- Implementation: *(stable / minor issues / etc.)*

**Backup tracker:** *(fill)*
- Rationale: *(why keep this as backup)*

### Evaluation suite test

**Test run:**
```bash
# Example command
./tools/run_eval_suite.sh --tracker ocsort --scenario clean
```

**Output:**
- Report: `reports/tracking/W10_ocsort_clean/summary.md`
- Figures: `figures/tracking/W10_ocsort_clean_*.png`
- Status: *(Success / Errors)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Limited test scenarios without camera (no real outdoor data yet)
- Parameter tuning based on indoor/synthetic data may not generalize

---

## Next steps (Day 04)
- [ ] Implement multi-feature score function for target selector
- [ ] Add state machine: SEARCH → LOCKED → LOST → REACQUIRED
- [ ] Emit events: lost_flag, reacquired_flag, lock_id_changes_total
- [ ] Run ablation study comparing old vs new target selector

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Scenario registry: `../../config/eval_scenarios.yaml`
- Eval suite script: `../../tools/run_eval_suite.sh`
