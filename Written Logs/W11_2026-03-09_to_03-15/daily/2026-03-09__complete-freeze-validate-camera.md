# Daily Log — 2026-03-09 — Complete W10 Freeze and Live Camera Validation

> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

## Goal

Close out Week 10 deliverables and validate that the live camera integration meets thesis performance targets.

**Target outcome:**
- W10 `weekly.md` and `artefacts.md` completed and frozen
- Live camera validated at ≥15 Hz with end-to-end detections
- Full latency breakdown with live camera, compared to file-based baseline
- Issues log documenting any camera/inference stability problems

---

## Context

| Key | Value |
|-----|-------|
| Week transition | W10 → W11 |
| Camera status | Live integration completed on Day 08 (2026-03-08) |
| Remaining W10 work | Baseline freeze documentation incomplete |
| Next milestone | Outdoor testing |
| Hardware | Pi 5 + Hailo AI HAT+ + TEVS-AR0234 |
| Software | ROS 2 Jazzy, live camera → ZMQ → container → detections |
| Thesis FPS target | ≥15 Hz |
| Latency budget | p95 ≤ 200 ms |

---

## Work Plan Status

### A) Complete W10 Documentation

Close out all W10 deliverables properly before moving to outdoor tests.

**Tasks:**
- [ ] Review W10 daily logs (Days 03-08) and mark completion status
- [ ] Complete W10 `weekly.md` with final results and key learnings
- [ ] Update W10 `artefacts.md` with all code/configs/reports from the week
- [ ] Document baseline tracker decision (if made) or defer decision with rationale
- [ ] Document target selector state and embedding v1 status
- [ ] Note what was deferred from W10 plan and why

**Deliverables:**
- [ ] `W10_2026-03-02_to_03-08/weekly.md`
- [ ] `W10_2026-03-02_to_03-08/artefacts.md`

---

### B) Live Camera Performance Validation

Prove the live camera meets minimum thesis targets before outdoor testing.

**Tasks:**
- [x] Run full pipeline with live camera for at least 2 minutes
- [x] Record bag: `bags/live_camera/2026-03-09__camera_validation/`
- [x] Measure sustained FPS from bag inspection
- [x] Fix metadata propagation issues before clean validation:
  - track score propagation
  - target header propagation
  - target score propagation
- [x] Generate timing analysis:
  - `reports/timing/W11_live_camera_initial_validation.md`
  - `reports/timing/W11_live_camera_initial_validation_gap_filtered.md`
- [x] Extract and summarise full latency breakdown from timing report
- [ ] Compare timing to file-based baseline from W09-W10
- [ ] Check for frame drops or timing drift over the run

**Success criteria:**
- [x] Sustained ≥15 Hz for full 2-3 minute run
- [x] Mean latency < 150 ms, p95 < 200 ms, confirm from report
- [ ] No obvious FPS degradation or frame drops, confirm from report
- [ ] Detections quality similar to file-based runs, qualitative note still needed

**Deliverables:**
- [x] Bag: `bags/live_camera/2026-03-09__camera_validation/`
- [x] Timing analysis: `reports/timing/W11_live_camera_initial_validation.md`
- [ ] Comparison plot / comparison section: file vs live latency CDF

---

### C) Document Live Camera Issues

Real-time camera brings new issues not seen in file replay.

**Tasks:**
- [ ] Document any FPS instability or drops
- [ ] Note any quality issues (exposure, focus, motion blur)
- [ ] Check CPU/memory usage during live runs
- [ ] Test restart behaviour, does camera recover after ROS restart?
- [ ] Document any Hailo/ZMQ issues under live load

**Deliverables:**
- [ ] Issues log: `reports/system/W11_live_camera_issues.md`
- [ ] Recommendations for Day 10 stability testing

---

### D) Plan Week 11 Focus

Clarify the main objectives for W11 based on current system state.

**Tasks:**
- [ ] Review W11 `index.md` and confirm daily plan makes sense
- [ ] Identify any W10 carryover work that blocks outdoor testing
- [ ] Draft outdoor test scenarios, to refine on Day 11 in the field
- [ ] Confirm hardware readiness, battery, mounting, portability

**Deliverables:**
- [ ] Updated W11 `index.md` if needed
- [ ] Outdoor test scenario draft

---

## What was done today

### 1. Fixed tracker and target metadata propagation

Two metadata bugs from Day 08 were fixed before the clean validation run:

- `tracker_node.py`
  - recovered per-track score using best-IoU detection when backend score was zero
  - this was necessary because SORT and OC-SORT backends returned `score = 0.0`
- `thesis_target_selector.py`
  - now copies `msg.header` into `TargetState.header`

**Result after patch and rebuild:**
- `/tracks.score` no longer stuck at `0.0`
- `/target.header` is no longer empty
- `/target.score` is now propagated correctly

---

### 2. Rebuilt and re-ran the full live stack

The full live stack was brought up successfully:

1. `camera_init_node`
2. `camera_capture_node`
3. container live inference service on `tcp://0.0.0.0:5556`
4. `inference_client_node`
5. `tracker_node`
6. `target_selector_node`

One-shot topic checks confirmed the chain was healthy.

**Observed one-shot values before clean bag:**
- `/camera/fps`: about **46.81 Hz**
- `/timing.lat_ms`: sample about **97.30 ms**
- `/detections`: present
- `/tracks`: present with non-zero scores
- `/target`: present with valid header and non-zero score

---

### 3. Recorded the clean live validation bag

A minimally observed run was recorded without leaving extra CLI subscribers attached.

**Bag:**
- `bags/live_camera/2026-03-09__camera_validation`

**Bag info:**
- Duration: **139.48 s**
- Total messages: **11382**

**Counts:**
- `/camera/fps`: **137**
- `/detections`: **2234**
- `/tracks`: **2264**
- `/target`: **2249**
- `/timing`: **2234**
- `/timing_tracker`: **2264**

---

### 4. Proven sustained full-pipeline rate

Using the clean bag counts over 139.48 s:

- `/detections`: about **16.02 Hz**
- `/tracks`: about **16.23 Hz**
- `/target`: about **16.12 Hz**
- `/timing`: about **16.02 Hz**

**Conclusion so far:**  
The live full perception chain **cleared the thesis minimum target of 15 Hz** in a clean recorded run.

---

### 5. Generated timing reports

Generated:

- `reports/timing/W11_live_camera_initial_validation.md`
- `reports/timing/W11_live_camera_initial_validation_gap_filtered.md`

These were read and summarised. The live run met both the throughput target and the latency budget.

### 6. Timing validation result

From `reports/timing/W11_live_camera_initial_validation.md`:

**Base window, full clean run:**
- Duration: **136.801 s**
- `/detections` achieved rate: **16.323 Hz**
- `/tracks` achieved rate: **16.323 Hz**
- `/target` achieved rate: **16.323 Hz**

**End-to-end latency (`lat_ms`):**
- Mean: **76.733 ms**
- p50: **75.739 ms**
- p95: **102.414 ms**
- p99: **116.896 ms**
- Max: **139.998 ms**

**Loop timing (`loop_ms`):**
- Mean: **32.850 ms**
- p50: **30.120 ms**
- p95: **48.907 ms**
- p99: **60.849 ms**
- Max: **85.175 ms**

**Tracker runtime:**
From `/timing_tracker`:
- Mean: **0.320 ms**
- p50: **0.041 ms**
- p95: **0.451 ms**
- p99: **8.785 ms**
- Max: **20.087 ms**

**Gap-filtered active-only view:**
- Active-only duration: **94.723 s**
- Gap count: **253**
- Gap removed: **42.078 s**
- Active-only `/detections` rate: **18.707 Hz**
- Active-only `/tracks` rate: **18.665 Hz**
- Active-only `/target` rate: **18.707 Hz**
- Active-only `lat_ms` mean: **76.214 ms**
- Active-only `lat_ms` p95: **101.574 ms**

**Interpretation:**
- The live full pipeline cleared the thesis minimum throughput target of **15 Hz**
- The latency budget was met comfortably:
  - target: **p95 ≤ 200 ms**
  - measured: **p95 = 102.414 ms**
- Mean latency also remained well below the informal success threshold of **150 ms**
- Tracker cost is negligible relative to the full pipeline
- The main remaining uncertainty is not indoor latency, but restart robustness, longer-run stability, and outdoor behaviour

**Important note:**
- `track_ms` inside `/timing` remains `0.0`, so actual tracker runtime should be read from `/timing_tracker`, not from `/timing`

---

## Results So Far

### Deliverables completed so far

- [x] Metadata propagation fixed in tracker and target selector
- [x] Clean live validation bag recorded
- [x] Achieved full-pipeline rate above thesis minimum
- [x] Timing reports generated

### Main confirmed result

The live camera path is no longer just integrated, it is now **validated at the thesis minimum throughput level** in a clean recorded run.

---

## Remaining work today

### Still needed before closing the day
- Write `reports/system/W11_live_camera_issues.md`
- Run one restart-recovery test
- Freeze:
  - `W10_2026-03-02_to_03-08/weekly.md`
  - `W10_2026-03-02_to_03-08/artefacts.md`
- Add a short live vs file-based comparison section

---

## Updated Issues and Risks

### Known issues now
- Live full-pipeline rate is validated, but restart robustness is still not yet documented
- Full latency interpretation still depends on extracting the report values cleanly
- Camera quality under real outdoor lighting is still unknown
- Longer-distance detection performance is still unknown
- Container live launch path remains delicate and depends on the correct Hailo environment

### Risks for outdoor testing
- Auto-exposure behaviour in sunlight remains unvalidated
- Detection range at 10 m+ remains unvalidated
- Thermal behaviour over longer outdoor runs remains unvalidated
- Restart behaviour under field use remains unvalidated

---

## Current conclusion

Today already changed the status of the project in a meaningful way.

**What is now true:**
- metadata propagation bugs are fixed
- the clean live bag proves sustained full-pipeline throughput above 15 Hz
- the live path is now a credible baseline for outdoor testing

**What is not yet fully closed:**
- issues log
- restart test
- W10 documentation freeze
- short live vs file-based comparison note

---

## Notes

- This is no longer an integration day, it is a validation and freeze day
- The key uncertainty is no longer whether live camera works
- The key uncertainty is now outdoor robustness and longer-run stability