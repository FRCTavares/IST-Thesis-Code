# Daily Log — 2026-03-10 — Live Camera Stability and Timing Under Load

## Goal

Prove the live camera can sustain thesis performance targets under extended runs and full system load.

**Target outcome:**
- 5+ minute continuous run with live camera at ≥15 Hz
- FPS stability confirmed (no degradation over time)
- Full latency breakdown documented and thesis-ready
- Memory/CPU profile if needed
- Thermal behavior characterized

---

## Context

| Key | Value |
|-----|-------|
| Previous validation | Day 09 initial 2-3 min test |
| Thesis FPS target | ≥15 Hz sustained |
| Latency budget | p95 ≤ 200 ms |
| Extended run target | 5+ minutes continuous |
| Hardware concerns | Pi 5 thermal throttling, memory leaks |
| Software concerns | Frame drops, timing drift, ZMQ stability |
| Outdoor readiness | Depends on today's stability results |

---

## Work Plan

### A) Extended Stability Run

Run the full system continuously and monitor for degradation.

**Tasks:**
- [ ] Run full pipeline (camera → inference → tracker → target selector) for 5+ minutes
- [ ] Record full bag: `bags/live_camera/2026-03-10__stability_5min/`
- [ ] Monitor FPS in real-time (use `/camera/fps` or timing topic)
- [ ] Check for frame drops or timing anomalies
- [ ] Monitor CPU usage: `htop` or `top` during run
- [ ] Monitor memory usage: check for leaks over 5 minutes
- [ ] Check Pi 5 temperature: `vcgencmd measure_temp` before/during/after
- [ ] Test system restart: does it recover cleanly?

**Success criteria:**
- FPS stays ≥15 Hz for entire 5+ minute run
- No timing drift or frame accumulation
- CPU usage stable (no runaway processes)
- Memory usage stable (no leaks)
- Temperature stays below throttling threshold (~80°C)

**Deliverables:**
- Bag: `bags/live_camera/2026-03-10__stability_5min/`
- FPS over time plot: `figures/timing/W11_live_camera_fps_over_time.png`
- System resource log

---

### B) Full Latency Breakdown with Live Camera

Decompose end-to-end latency into all stages and compare to file-based baseline.

**Tasks:**
- [ ] Analyze 5-minute bag with extended timing analysis
- [ ] Extract timing for each stage:
  - Camera capture latency (if instrumented)
  - Serialization time
  - ZMQ request/response time
  - Inference time (container reports this)
  - Deserialization time
  - Tracker time (`track_ms`)
  - Target selector time
  - Total end-to-end latency
- [ ] Generate CDF plots for each stage
- [ ] Compare live camera timing to file-based baseline:
  - W09 primary bag: `2026-02-25__slice__primary`
  - W10 bags if available
- [ ] Identify any new bottlenecks introduced by live camera
- [ ] Document overhead: camera path vs. file replay path

**Deliverables:**
- Latency report: `reports/timing/W11_live_camera_latency.md`
- Stage-by-stage breakdown table (mean, median, p95, p99)
- CDF comparison plots: `figures/timing/W11_live_vs_file_latency_cdf.png`
- Stacked latency breakdown: `figures/timing/W11_latency_breakdown_stacked.png`

---

### C) Thermal and Resource Profiling

Understand thermal behavior and resource limits for outdoor testing.

**Tasks:**
- [ ] Run extended test outdoors (if weather permits) or in warm environment
- [ ] Log temperature every 30 seconds during 5-minute run
- [ ] Check for thermal throttling events: `dmesg | grep -i thermal`
- [ ] Profile CPU usage by process: which nodes are heaviest?
- [ ] Profile memory usage: any leaks in camera_capture_node or inference_client_node?
- [ ] Test with active cooling (fan) if throttling occurs
- [ ] Document safe operating limits for outdoor use

**Success criteria:**
- No thermal throttling during 5-minute run
- CPU usage leaves headroom for MAVROS and control nodes
- Memory usage stable and predictable

**Deliverables:**
- Thermal profile: temperature over time
- Resource usage report: `reports/system/W11_resource_profile.md`
- Recommendations: cooling needed? Process priority tuning?

---

### D) Multi-Run Reliability Test

Prove the system can restart cleanly and maintain performance.

**Tasks:**
- [ ] Run 3 consecutive 5-minute tests with ROS restart between each
- [ ] Record separate bags for each run
- [ ] Compare FPS and latency across runs: any drift?
- [ ] Test camera recovery after each restart
- [ ] Check for any resource accumulation (memory leaks, file descriptors)
- [ ] Validate that camera_init_node is reliable across boots

**Success criteria:**
- All 3 runs meet ≥15 Hz target
- Performance consistent across runs (no degradation)
- Camera recovery is automatic and fast

**Deliverables:**
- 3 bags: `bags/live_camera/2026-03-10__run1/`, `run2/`, `run3/`
- Reliability report: `reports/system/W11_multi_run_reliability.md`
- Comparison plot: FPS and latency across 3 runs

---

### E) Prepare for Outdoor Testing

Based on today's results, assess readiness for outdoor tests.

**Tasks:**
- [ ] Review all stability and timing results
- [ ] Identify any blockers for outdoor testing
- [ ] List known issues and workarounds
- [ ] Draft outdoor test plan for Day 11 (exploratory first test)
- [ ] Check hardware readiness: battery charged, mounting secure, all cables OK

**Deliverables:**
- GO/NO-GO decision for Day 11 outdoor test
- Issues list with severity and mitigation
- Outdoor test plan draft (informal)

---

## Expected Outcomes

By end of Day 10, you should have:

1. **Confirmed sustained performance**
   - ≥15 Hz for 5+ minutes validated
   - Latency budget met or issues clearly documented

2. **Thesis-ready timing report**
   - Full latency breakdown with comparison to baseline
   - CDF plots and percentile tables ready for thesis

3. **Thermal and resource limits understood**
   - Know if cooling is needed for outdoor use
   - CPU/memory headroom confirmed for full system

4. **Confidence in system reliability**
   - System can restart cleanly
   - No drift or accumulation issues

5. **Clear GO/NO-GO for outdoor tests**
   - If GO: move to Day 11 outdoor test confidently
   - If NO-GO: document blockers and mitigation plan

---

## Issues and Risks

### Potential Issues
- FPS degradation over extended runs
- Thermal throttling without active cooling
- Memory leaks in camera or inference nodes
- ZMQ stability under continuous load
- Camera recovery issues after restart

### Mitigation Strategies
- If FPS drops: profile CPU, optimize bottlenecks, reduce resolution if needed
- If thermal issues: add active cooling, reduce inference rate
- If memory leaks: fix in camera_capture_node or inference_client_node
- If ZMQ issues: add retry logic, increase timeout
- If camera issues: improve camera_init_node robustness

---

## Notes

- This is the "stress test" day: push the system and find its limits
- Better to discover issues now in controlled environment than during outdoor tests
- If system is stable today, outdoor tests can proceed with confidence
- If issues found, use Day 11 to fix them instead of going outdoors
- Don't rush outdoor tests until stability is proven
