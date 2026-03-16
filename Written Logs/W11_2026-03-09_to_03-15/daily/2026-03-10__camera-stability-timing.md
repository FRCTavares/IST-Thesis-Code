# Daily Log — 2026-03-10 — Live Camera Stability and Timing Under Load

> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

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
| Outdoor readiness | GO in lean operational mode only |

---

## Work Plan

**Important notes:**
- Live path uses camera stack + live inference service (port 5556)
- Do NOT run extra long-running `ros2 topic hz` subscribers during bag recording
- Frozen golden-state checks first, then live-specific checks

---

## PRIORITY 1 — Must Finish Today

### Step 1: Pre-Run Golden-State Checks

**Tasks:**
- [x] Run frozen golden-state checks (inference service 5556 health, camera permissions, etc.)
- [x] Verify live inference service is running on port 5556 (not 5555 file-based path)
- [x] Check camera capture node is ready and streaming
- [x] Verify `/detections`, `/tracks`, `/target` topics are active
- [x] Quick spot-check: all topics publishing at expected rates
- [x] Note baseline temperature: `vcgencmd measure_temp`
- [x] Note baseline memory: `free -h`

---

### Step 2: Run 1 — Main Stress Test (8-10 minutes)

**Tasks:**
- [x] Start thermal logging in parallel: record `vcgencmd measure_temp` every 30 seconds
- [x] Start resource logging in parallel: `top -b -d 30 -n 20 > resource_log.txt`
- [x] Record bag: `bags/live_camera/2026-03-10__stability_10min/`
- [x] Duration: 8-10 minutes continuous (602.857 seconds achieved)
- [x] Do NOT run extra `ros2 topic hz` during recording (causes load)
- [x] Monitor system stability passively (htop in another terminal OK)
- [x] After run, check for throttling: `vcgencmd get_throttled`
- [x] After run, note final temperature and memory

**Results:**
- Duration: 602.857 seconds (10.05 minutes)
- Final temperature: 59.3°C
- Throttling status: `0x0` (no throttling)
- Memory: normal, no leaks observed

**Deliverables:**
- Bag: `bags/live_camera/2026-03-10__stability_10min/` ✓
- Thermal log file ✓
- Resource log file ✓

---

### Step 3: Post-Run Analysis

**Tasks:**
- [x] Generate normal timing report using `analyse_bag_timing.py`
- [x] Generate gap-filtered timing report (filter out large gaps)
- [x] Inspect achieved rates for `/detections`, `/tracks`, `/target`
- [x] Inspect `lat_ms`, `loop_ms`, `track_ms` distributions (mean, median, p95, p99)
- [x] Check for rate decay over time (plot FPS vs. time)
- [x] Check for memory drift in resource log
- [x] Check for temperature drift in thermal log
- [x] Check for throttling events

**Results:**

**Base window (authoritative):**
- `/detections`: **10.407 Hz** ❌ (fails 15 Hz target)
- `/tracks`: **10.405 Hz** ❌
- `/target`: **10.405 Hz** ❌
- `lat_ms` p95: **101.9 ms** ✓ (excellent, well under 200 ms budget)
- `lat_ms` p50: 61.0 ms, mean: 66.8 ms
- `pub_dt_ms` mean: 96.1 ms, p50: 99.2 ms, p95: 158.1 ms
- `loop_ms` mean: 35.5 ms, p50: 32.9 ms
- `recv_ms` mean: 16.9 ms, p50: 15.3 ms
- `json_ms` mean: 16.9 ms, p50: 15.3 ms

**Tracker runtime (from /timing_tracker):**
- `track_ms` p50: **0.318 ms** ✓ (very fast)
- `track_ms` p95: **11.636 ms** ✓
- `track_ms` mean: 2.533 ms
- Tracker is NOT the bottleneck

**Active-only window (gap-filtered, pub_dt_ms ≤ 100 ms):**
- ⚠️ **Note:** Active-only shows 17.2 Hz but this is misleading
- Filter threshold (100 ms) sits almost exactly on normal operating point (96-99 ms)
- Active-only overstates real performance
- **Authoritative rate is base-window: 10.4 Hz**

**Thermal and resource:**
- No throttling events (`0x0`)
- Temperature: 59.3°C (well below throttle threshold)
- Memory: normal, no leaks
- No rate decay over 10 minute run

**Assessment against success criteria:**

**PASS criteria:**
- ✓ `lat_ms` p95 ≤120 ms (excellent) or ≤200 ms (acceptable): **101.9 ms**
- ✓ No throttling flags in `get_throttled`: **0x0**
- ✓ No monotonic memory growth that looks like leak
- ✓ No obvious rate decay over the run

**FAIL criteria:**
- ❌ `/detections`, `/tracks`, `/target` all ≥15 Hz sustained: **only 10.4 Hz achieved**
- ✓ `lat_ms` p95 >200 ms: no, 101.9 ms is fine
- ✓ Temperature approaches throttle range + events: no, 59.3°C is safe
- ✓ Memory keeps climbing: no, stable

**Overall for initial full-debug style run: PARTIAL PASS**
- Latency, thermals, and memory were all acceptable
- Sustained rate failed the 15 Hz target in the initial configuration
- This triggered further isolation and bottleneck analysis rather than an immediate outdoor NO-GO

**Bottleneck identified:**
- Tracker runtime is negligible (p50 = 0.3 ms)
- System is NOT compute-bound in downstream processing
- System is NOT thermally throttled
- Issue is in **live camera → inference_client → ZMQ/REQREP → container → JSON/response path**
- Suspects:
  - Camera frame delivery cadence
  - ZMQ request/response overhead (recv_ms, json_ms both ~16.9 ms)
  - Container inference service throughput
  - Network serialization/deserialization

**Deliverables:**
- Timing report: `reports/timing/W11_2026-03-10__stability_10min.md` ✓
- Gap-filtered report: `reports/timing/W11_2026-03-10__stability_10min_active_only.md` ✓
- FPS over time plot: `figures/timing/W11_2026-03-10_fps_over_time.png` ✓
- Latency CDF: `figures/timing/W11_2026-03-10_latency_cdf.png` ✓
- Resource and thermal summary: documented above ✓

---

### Step 3B: Isolation Tests and Lean-Mode Recovery

**Status: COMPLETED**

After the initial 10 minute run failed the 15 Hz target, a sequence of isolation tests was used to identify the real bottleneck.

**Isolation results:**

**Live inference only:**
- Bag: `bags/live_camera/2026-03-10__live_inference_only/`
- `/detections`: **19.654 Hz**
- `lat_ms` p95: **91.833 ms**
- Conclusion: camera + live inference path alone was healthy and above target

**Tracker present, original behaviour:**
- Bag: `bags/live_camera/2026-03-10__tracker_present_minrec/`
- `/detections`: **11.874 Hz**
- Conclusion: the rate collapse appeared when `tracker_node` was present

**Tracker fast-path test:**
- Removed expensive per-track Python IoU score-recovery in `tracker_node.py`
- Disabled `/timing_tracker` publish during live operational tests
- Bag: `bags/live_camera/2026-03-10__tracker_fastpath_minrec/`
- `/detections`: **16.794 Hz**
- Conclusion: per-track score recovery was a major avoidable bottleneck

**Tracker with timing publish enabled but minimal recording:**
- Bag: `bags/live_camera/2026-03-10__tracker_timing_on_minrec/`
- `/detections`: **15.056 Hz**
- Conclusion: timing publication alone was not the main problem when minimally subscribed

**Key finding:**
- The main operational bottleneck was not raw detector throughput
- The main avoidable costs were:
  - tracker-side Python score-recovery work after tracking
  - transporting and recording tracker debug outputs, especially `/tracks` and `/timing_tracker`

**Lean operational configuration adopted:**
- fast score path in tracker
- `/timing_tracker` disabled
- do not record `/tracks` during operational validation
- record only:
  - `/camera/fps`
  - `/detections`
  - `/timing`
  - `/target`

---

### Step 4: Run 2 — Restart Reliability Test

**Status: DEFERRED**

Run 2 deferred until live path throughput issue is resolved. No point testing restart reliability when baseline performance fails target rate.

**Tasks:**
- [ ] Stop all ROS nodes cleanly (`Ctrl+C` on launch files)
- [ ] Restart full live stack (camera + inference + tracker + target selector)
- [ ] Do shorter 2-3 minute validation run
- [ ] Record bag: `bags/live_camera/2026-03-10__restart_recovery/`
- [ ] Confirm camera recovery works automatically
- [ ] Confirm `/detections`, `/tracks`, `/target` all appear and sustain ≥15 Hz
- [ ] Spot-check timing with quick analysis

**Success criteria:**
- Camera recovery is automatic and fast (no manual intervention)
- All topics resume at ≥15 Hz
- Timing comparable to Run 1

**Failure criteria:**
- Manual intervention needed to recover camera
- Topics don't resume or rate is degraded
- Timing significantly worse than Run 1

**Deliverables:**
- Bag: `bags/live_camera/2026-03-10__restart_recovery/`
- Quick timing spot-check confirming recovery

---

## PRIORITY 2 — Do Only if Run 1 is Clean

**Status: DEFERRED — Run 1 failed rate target (10.4 Hz vs 15 Hz)**

Focus must remain on identifying and fixing upstream throughput bottleneck.

### Optional: Live vs File Comparison

**Status: DEFERRED**

**Tasks:**
- [ ] Compare Run 1 timing to W09 primary baseline (`2026-02-25__slice__primary`)
- [ ] Document live camera overhead (if any)
- [ ] Identify any new bottlenecks introduced by live path

**Deliverables:**
- Short comparison section in timing report

---

### Optional: Changed Cooling Condition

**Only if thermals are suspicious in Run 1:**

**Tasks:**
- [ ] Add active cooling (fan) or move to cooler environment
- [ ] Repeat 5-minute run: `bags/live_camera/2026-03-10__stability_fan_on/`
- [ ] Compare thermal behavior to Run 1

**Deliverables:**
- Bag: `2026-03-10__stability_fan_on/` (if needed)
- Thermal comparison in report

---

### Issues Log and GO/NO-GO Decision

**Status: UPDATED AFTER ISOLATION TESTS**

**Tasks:**
- [x] Document issues from initial 10 minute run
- [x] Isolate bottlenecks with targeted live tests
- [x] Identify operationally acceptable live configuration
- [x] Make GO/NO-GO decision for Day 11 outdoor test

**Decision: GO for outdoor testing in lean operational mode only**

**Operational mode constraints for tomorrow:**
- use fast tracker score path
- `/timing_tracker` disabled
- do not bag-record `/tracks`
- do not run extra long-lived debug subscribers such as `ros2 topic hz`

**What remains open:**
- restart reliability was deferred
- full debug/profiling mode still drops below operational target

**Deliverables:**
- Issues log: `reports/system/W11_issues_2026-03-10.md` ✓
- GO/NO-GO decision: **GO (lean mode only)** (documented) ✓

---

## PRIORITY 3 — Skip Unless Everything is Done

**Status: SKIPPED — Priority 1 failed rate target**

### Three Full 5-Minute Runs

**Status: SKIPPED**

**Tasks:**
- [ ] Run 3 consecutive 5-minute tests with restart between each
- [ ] Compare consistency across runs

**Deliverables:**
- 3 bags (skip unless P1 and P2 complete)

---

### Full Thesis-Polished Plots

**Tasks:**
- [ ] Generate thesis-ready plot suite
- [ ] Stage-by-stage latency breakdown
- [ ] Stacked latency waterfall

**Deliverables:**
- Polished plots (skip unless P1 and P2 complete)

---

### Outdoor Warm-Environment Test

**Tasks:**
- [ ] Replicate extended run outdoors in warm environment

**Deliverables:**
- Outdoor bag (skip unless P1 and P2 complete)

---

## Expected Outcomes

**Minimum defensible day (Priority 1 complete):**

1. **One clean 8-10 minute stress test**
   - Bag recorded: `2026-03-10__stability_10min/`
   - Thermal and resource logs captured
   - Timing report with normal and gap-filtered analysis
   - Rate, latency, and resource behavior documented

2. **Restart reliability validated**
   - Bag recorded: `2026-03-10__restart_recovery/`
   - Camera recovery confirmed as automatic
   - Timing spot-check confirms system health after restart

3. **Concrete system evidence**
   - Know whether system meets GO criteria (≥15 Hz, lat_ms p95 ≤200 ms, no drift/throttling)
   - If NO-GO, issues are documented with severity

**If Priority 2 completed:**

4. **Issues log and GO/NO-GO decision**
   - Clear decision for Day 11 outdoor test
   - Blockers identified with mitigation strategies

5. **Optional comparisons**
   - Live vs file timing overhead quantified
   - Thermal behavior under different cooling conditions characterized

---

## Success Criteria Summary

### GO Criteria
- `/detections`, `/tracks`, `/target` all stay at ≥15 Hz
- `lat_ms` p95 ≤120 ms (excellent) or ≤200 ms (acceptable)
- No obvious rate decay over the run
- No throttling flags in `vcgencmd get_throttled`
- No monotonic memory growth that looks like a leak
- Restart works once without manual intervention

### NO-GO Criteria
- Sustained rate drops below 15 Hz
- `lat_ms` p95 >200 ms
- Temperature approaches throttle range + events in `get_throttled`
- Memory keeps climbing across the run
- Restart recovery is flaky or requires manual intervention

---

## Execution Notes

- **Port awareness:** Live inference service runs on port 5556 (not 5555 file-based path)
- **Avoid extra load during recording:** Do NOT run `ros2 topic hz` subscribers during bag recording
- **Golden-state checks first:** Use frozen checks, then add live-specific validations
- **Bag naming convention:** Use descriptive names like `stability_10min`, `restart_recovery`, `stability_fan_on`
- **Don't drown in reporting:** Get system evidence first, polish plots later (Priority 3)

---

## Notes

- This is the "stress test + recovery" day: push the system but stay focused
- Priority 1 is the minimum defensible evidence for thesis
- Priority 2 adds confidence for outdoor testing
- Priority 3 can wait — better to have clean evidence than perfect plots
- If system is stable today, outdoor tests can proceed with confidence
- If issues found, document them clearly and decide on mitigation before Day 11

---

## RESULTS AND CONCLUSIONS

### Priority 1 Status: COMPLETED

The day produced two distinct outcomes:

1. **Initial full-debug style 10 minute run failed the rate target**
2. **Lean operational mode was later validated successfully over 10 minutes**

### Initial 10 minute run, useful failure

**Run 1:**
- Bag: `bags/live_camera/2026-03-10__stability_10min/`
- Duration: **602.857 s**
- `/detections`: **10.407 Hz**
- `/tracks`: **10.405 Hz**
- `/target`: **10.405 Hz**
- `lat_ms` p95: **101.9 ms**
- Final temperature: **59.3°C**
- `throttled = 0x0`

**Interpretation:**
- latency, thermals, and memory were good
- sustained rate failed the 15 Hz target
- this triggered deeper isolation rather than an immediate final NO-GO

### Root-cause investigation outcome

Isolation tests showed:

- **live inference only** reached **19.654 Hz**
- the major slowdown appeared when `tracker_node` was introduced
- the expensive part was not the tracker algorithm itself
- the main avoidable costs were:
  - Python per-track IoU score-recovery after tracking
  - debug-topic transport and recording overhead, especially `/tracks` and `/timing_tracker`

### Final validated operational configuration

**Lean operational mode:**
- fast score path enabled in tracker
- `/timing_tracker` disabled
- `/tracks` not recorded during performance validation
- lean recorded topics only:
  - `/camera/fps`
  - `/detections`
  - `/timing`
  - `/target`

### Final 10 minute validation, thesis-relevant result

**Bag:**
- `bags/live_camera/2026-03-10__full_stack_lean_10min/`

**Run summary:**
- Duration: **598.229 s**
- `/detections`: **16.644 Hz**
- `/target`: **16.629 Hz**
- `lat_ms` mean: **61.698 ms**
- `lat_ms` p95: **91.296 ms**
- `lat_ms` p99: **112.012 ms**
- `loop_ms` mean: **33.641 ms**
- Final temperature: **59.3°C**
- `throttled = 0x0`
- Memory stable

### Final decision for tomorrow

**GO for outdoor testing in lean operational mode only**

This means:
- operational live target met
- latency budget comfortably met
- 10 minute stability demonstrated
- thermal behaviour safe

### Important caveat

**Not yet validated for tomorrow:**
- restart reliability after full stack restart
- high-load debug/profiling mode with `/tracks` and `/timing_tracker` recorded

### Practical conclusion

The live system is ready for outdoor testing **provided that tomorrow uses the validated lean configuration** rather than the full profiling configuration.

### Next Steps

**For tomorrow's outdoor test:**
1. Use the validated lean operational configuration only
2. Do a short pre-test smoke run after startup
3. Avoid `/tracks` recording and avoid extra long-lived debug subscribers
4. Record only:
   - `/camera/fps`
   - `/detections`
   - `/timing`
   - `/target`

**After tomorrow:**
1. Add a parameterised split between live mode and profiling mode in `tracker_node.py`
2. Reintroduce tracker timing only for dedicated profiling sessions
3. Validate restart reliability in a separate controlled test
4. Document the tracker-side performance bug and fix in thesis/report text
