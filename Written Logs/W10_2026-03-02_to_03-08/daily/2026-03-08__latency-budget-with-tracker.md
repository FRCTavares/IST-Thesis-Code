# Daily Log — 2026-03-08 — Integrate Tracker Timing into Full Latency Breakdown (Week 10, Day 6)

## Goal
Integrate tracker timing into full latency breakdown. By end of day, single report shows end-to-end budget with tracker split.

**Target outcome:**
- Complete latency budget table showing all pipeline stages
- Tracker timing (`track_ms`) integrated with inference timing
- CDF plot for `track_ms`
- Stacked bar or table summary (median and p95)
- Clear view of where time is spent in the pipeline

**Philosophy:** You can't optimize what you don't measure. Complete transparency on latency budget.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, testing with bag replay. Camera integration Week 11. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Current timing | `/timing` has: recv_ms, json_ms, loop_ms, pub_dt_ms, lat_ms |
| New timing | `/timing_tracker` has: track_ms (added Week 9) |
| Target budget | < 200 ms end-to-end (p99), < 150 ms (p95) |

---

## Work Plan

### A) Modify analysis script to produce complete latency budget
Extend existing timing analysis to include tracker breakdown.

- [ ] Update `tools/analyse_bag_timing.py` (or create `tools/analyse_latency_budget.py`):
  - Read from both `/timing` and `/timing_tracker` topics
  - Match timestamps (sync by header or sequence)
  - Compute full breakdown:
    - **recv_ms:** Time from detection publish to inference client receive
    - **json_ms:** JSON deserialization time
    - **track_ms:** Tracker update time (from `/timing_tracker`)
    - **loop_ms:** Inference loop time (includes detection + prep)
    - **pub_dt_ms:** Time between publishes (rate indicator)
    - **lat_ms:** End-to-end latency (may be computed differently)
  - Compute statistics for each: mean, std, p50, p95, p99, min, max
  
- [ ] Define end-to-end latency clearly:
  - **Option 1:** Image capture → control_ref publish
  - **Option 2:** Detection → control_ref publish
  - **Option 3:** Sum of pipeline stages
  - **Decision:** *(fill - likely Option 2 for now, Option 1 when camera available)*
  
- [ ] Create latency budget table:
  ```markdown
  | Stage | Mean | p50 | p95 | p99 | % of p95 total |
  |-------|------|-----|-----|-----|----------------|
  | recv_ms | — | — | — | — | — % |
  | json_ms | — | — | — | — | — % |
  | track_ms | — | — | — | — | — % |
  | loop_ms | — | — | — | — | — % |
  | other | — | — | — | — | — % |
  | **Total** | — | — | — | — | 100% |
  ```
  
- [ ] Add checks against budget:
  - p95 < 150 ms: ✓ PASS / ✗ FAIL
  - p99 < 200 ms: ✓ PASS / ✗ FAIL
  
- **Deliverable:** Extended analysis script with latency budget table
- Notes: *(fill)*

**Latency budget formula:**
```
latency_total = recv_ms + json_ms + track_ms + loop_ms + publish_overhead
```
OR (if measured end-to-end):
```
latency_total = t_control_ref_pub - t_detection_timestamp
```

### B) Add plots
Visualize latency breakdown for thesis and debugging.

- [ ] **track_ms CDF plot:**
  - X-axis: time (ms)
  - Y-axis: cumulative probability
  - Show p50, p95, p99 lines
  - Compare across scenarios (clean, occlusion, ambiguous)
  
- [ ] **Stacked bar chart (optional, if not too complex):**
  - X-axis: scenarios (clean, occlusion_1s, etc.)
  - Y-axis: latency (ms)
  - Stacks: recv, json, track, loop (color-coded)
  - Show both median and p95 side-by-side
  
- [ ] **Alternative: Table with breakdown:**
  - If stacked bar is complex, use table with visual indicators
  - Example:
    ```
    Stage       p50    p95    p99
    ────────────────────────────
    recv_ms     1.2    2.5    3.8  ▓░░░░
    json_ms     0.8    1.5    2.1  ▓░░░░
    track_ms    4.5    8.2   12.3  ▓▓░░░
    loop_ms    25.3   32.1   35.8  ▓▓▓▓▓▓▓▓░░
    ────────────────────────────
    Total      31.8   44.3   54.0
    ```
  
- [ ] Save figures: `figures/timing/W10_latency_budget_*.png`
  
- **Deliverable:** CDF plot + stacked summary (table or chart)
- Notes: *(fill)*

### C) Run on all scenarios
Generate latency budget for each evaluation scenario.

- [ ] Run analysis on:
  - clean scenario
  - occlusion_1s scenario
  - ambiguous_crossing scenario (if available)
  - long-run bag (stability over time)
  
- [ ] Compare:
  - Does track_ms increase with more detections?
  - Does occlusion affect latency (fewer detections → faster?)?
  - Any latency spikes correlated with events?
  
- [ ] Document findings
  
- **Deliverable:** Latency comparison across scenarios
- Notes: *(fill)*

### D) Generate comprehensive latency budget report
Create final report with all breakdowns and analysis.

- [ ] Create `reports/timing/W10_latency_budget.md`:
  - Introduction: latency budget importance, target < 200 ms
  - Methodology: how latency is measured, which stages included
  - Results:
    - Latency budget table (all stages)
    - CDF plots for critical stages (track_ms, loop_ms, total)
    - Scenario comparison
    - Pass/fail against target budget
  - Analysis:
    - Bottleneck identification (which stage dominates?)
    - Headroom: how close to budget limit?
    - Recommendations for optimization (if needed)
  - Conclusion: system meets latency budget (or actions needed)
  
- [ ] Link to figures
  
- [ ] Add to `artefacts.md`
  
- **Deliverable:** `reports/timing/W10_latency_budget.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] Analysis script extended with full latency breakdown
- [ ] Latency budget table generated (all stages)
- [ ] track_ms CDF plot created
- [ ] Stacked summary (table or chart) created
- [ ] `reports/timing/W10_latency_budget.md` complete

### Latency budget (clean scenario)

**Full breakdown:**
| Stage | Mean | p50 | p95 | p99 | % of p95 total | Notes |
|-------|------|-----|-----|-----|----------------|-------|
| recv_ms | — | — | — | — | — % | Network + queue |
| json_ms | — | — | — | — | — % | Deserialization |
| track_ms | — | — | — | — | — % | Tracker update (SORT/OC-SORT) |
| loop_ms | — | — | — | — | — % | Inference loop (detection) |
| other | — | — | — | — | — % | Publish, misc |
| **Total** | — | — | — | — | 100% | |

**Budget compliance:**
- p95 total: — ms (target: < 150 ms) → ✓ PASS / ✗ FAIL
- p99 total: — ms (target: < 200 ms) → ✓ PASS / ✗ FAIL
- Headroom at p95: — ms (— %)

**Bottleneck analysis:**
- Dominant stage: *(fill - e.g., loop_ms at 70% of total)*
- Optimization target: *(fill - e.g., "inference resolution, model quantization")*

### Scenario comparison

| Scenario | Detections/frame | track_ms p95 | Total latency p95 | Notes |
|----------|------------------|--------------|-------------------|-------|
| clean | — | — | — | Baseline |
| occlusion_1s | — | — | — | Fewer detections during occlusion |
| ambiguous | — | — | — | More detections (multi-person) |
| long-run | — | — | — | Stability over time |

**Observations:**
- *(Does track_ms scale with number of detections?)*
- *(Any latency drift over long runs?)*
- *(Spikes correlated with events?)*

### Visualizations

**Generated plots:**
- `figures/timing/W10_latency_budget_breakdown.png` — Stacked bar or table
- `figures/timing/W10_track_ms_cdf.png` — CDF for track_ms across scenarios
- `figures/timing/W10_latency_total_cdf.png` — End-to-end latency CDF

**Key insights from plots:**
- *(fill)*

### Recommendations

**Optimization priorities (if needed):**
1. *(fill - e.g., "Reduce loop_ms by lowering inference resolution")*
2. *(fill - e.g., "Optimize tracker association (use KD-tree for large N)")*
3. *(fill - e.g., "Reduce json_ms by using binary serialization")*

**Current verdict:**
- System meets budget: *(Yes / No / Marginal)*
- Confidence for outdoor: *(High / Medium / Low)*
- Actions needed: *(none / minor tuning / major optimization)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Latency may increase with camera in loop (additional image transport, encoding)
- Outdoor detection count may be higher (more distractors) → higher track_ms
- GPU/NPU thermal throttling not tested in sustained outdoor scenarios

---

## Next steps (Day 09)
- [ ] Freeze baseline tracker decision and parameters
- [ ] Freeze target selector state machine and weights
- [ ] Freeze control_ref behavior
- [ ] Define camera integration checklist (topics, calibration, FPS)
- [ ] Document "Phase 1 baseline" in weekly.md

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Latency budget report: `../../reports/timing/W10_latency_budget.md`
- Analysis script: `../../tools/analyse_latency_budget.py`
- Figures: `../../figures/timing/W10_latency_*.png`
