# Daily Log — 2026-03-12 (Day 12) — MAVROS Learning + Indoor Baseline

> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

## Reality Check

**Constraints today:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk at IST)
- ❌ No MAVROS hardware (no Pixhawk access)
- ✅ Indoor perception validation possible
- ✅ MAVROS learning and preparation possible

**Focus:** Learn MAVROS fundamentals and establish indoor perception baseline

---

## Goals for Today

### 1. MAVROS Learning (Critical Path)
- [ ] Read `docs/mavros_integration_guide.md` thoroughly
- [ ] Install MAVROS if not already present
- [ ] Understand topics and coordinate frames
- [ ] Note key commands and procedures
- [ ] Identify questions for supervisors

### 2. First Indoor Perception Session
- [ ] Run 10-minute sustained perception session
- [ ] Test target lock with movement
- [ ] Monitor system health (CPU, memory, temps)
- [ ] Record bag: `bags/live_camera/2026-03-12__indoor_baseline_10min/`

### 3. MAVROS Code Design
- [ ] Review current `control_ref_node.py`
- [ ] Plan MAVROS publisher integration
- [ ] Sketch `enable_mavros` parameter logic

### 4. Contact Supervisors ⚠️ CRITICAL
- [ ] Review `supervisor_questions.md`
- [ ] Email supervisors with safety questions
- [ ] Request answers before Monday evening

---

## Work Sessions

### Morning Session (3-4 hours)

**MAVROS learning:**
```bash
# Install MAVROS
sudo apt install ros-jazzy-mavros ros-jazzy-mavros-extras
wget https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh
sudo bash ./install_geographiclib_datasets.sh

# Verify installation
ros2 pkg list | grep mavros
```

**Read and understand:**
- Topics: `/mavros/setpoint_velocity/cmd_vel`, `/mavros/state`
- Coordinate frames: body frame (x=forward, y=left, z=up)
- Launch command for Ethernet: `ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@`

### Afternoon Session (3-4 hours)

**Indoor perception session:**
```bash
# Launch lean perception stack
# Terminal 1: camera_init_node
# Terminal 2: camera_capture_node  
# Terminal 3: detection_zmq.py (container)
# Terminal 4: inference_client_node
# Terminal 5: tracker_node
# Terminal 6: target_selector_node
# Terminal 7: bag record

# Record 10 minutes
cd $THESIS_ROOT/ros2_ws
ros2 bag record --storage mcap \
  -o ../bags/live_camera/2026-03-12__indoor_baseline_10min \
  /camera/fps /detections /timing /target
```

**During run:**
- Move in front of camera to test target lock
- Note any anomalies or crashes
- Monitor temperatures

### Evening Session (2-3 hours)

**Quick analysis:**
```bash
# Check bag stats
ros2 bag info bags/live_camera/2026-03-12__indoor_baseline_10min

# Verify ~16 Hz on /target
# Note any issues
```

**Email supervisors:**
- Send questions from `supervisor_questions.md`
- Request answers before Monday
- Emphasize Tuesday IST session importance

**Plan tomorrow:**
- Review what worked/didn't work today
- Adjust Day 13 tasks if needed

---

## Expected Deliverables

- [x] MAVROS installed and verified
- [x] Understanding of MAVROS basics (topics, frames, launch)
- [x] 6-minute indoor perception bag recorded (9.57 Hz, stable)
- [x] MAVROS bridge frozen (`/mavros/setpoint_velocity/cmd_vel`, `TwistStamped`)
- [x] Field checklist created (`docs/outdoor_field_checklist.md`)
- [x] Scenario sheet created (`docs/outdoor_scenario_sheet.md`)
- [x] GO/NO-GO gate defined and assessed
- [ ] Supervisors contacted with safety questions (pending)
- [x] Day 13 plan adjusted based on progress

---

## Notes and Issues

**MAVROS learning:**
- `mavros` installed (ROS 2 Jazzy)
- `mavros_extras` installed
- GeographicLib datasets installed successfully
- `apm.launch` exists and confirmed
- Default FCU URL: `/dev/ttyACM0:57600`
- **First bridge topic frozen:** `/mavros/setpoint_velocity/cmd_vel`
- **First message type frozen:** `geometry_msgs/msg/TwistStamped`
- **No control-node redesign needed** — `control_ref_node` already publishes `TwistStamped`

**Indoor session:**
- **Run completed:** 6-minute lean indoor perception session (not 10 min as planned)
- **Bag location:** `bags/live_camera/2026-03-12__indoor_baseline_10min/`
- **Duration:** 360.364 s
- **Message counts:** `/detections`: 3449, `/target`: 3449, `/timing`: 3449
- **System stability:** No crashes, full topic chain remained alive and aligned
- **Performance metrics (full-window):**
  - `lat_ms` mean: 69.709 ms
  - `lat_ms` p95: 111.394 ms
  - `lat_ms` p99: 134.229 ms
  - `pub_dt_ms`: mean 104.5 ms, p95 158.8 ms
  - **Achieved rate: 9.57 Hz** (below 10 Hz minimum target)
  - P95 latency target ≤ 200 ms: ✅ **passed**
  - Stretch p95 ≤ 100 ms: ❌ slightly missed (111.4 ms)
  - Minimum acceptable 10 FPS: ❌ slightly missed (9.57 Hz)
  - Desired 15 FPS sustained: ❌ not met

**Key findings:**
- **Latency is not the problem** — end-to-end delay remained acceptable
- **Issue is cadence irregularity** — bursty/gap-heavy publishing, not slow pipeline
- Active-only analysis shows system *can* produce ~15.5 Hz bursts, but with heavy interruptions (2087 gaps in 360.4s)
- **Active-only metrics should NOT be used as headline** — they exclude 92.5% of the session

**Conclusion:**
- This run is **stable and usable**, but not a "ready to claim 15 FPS sustained" result
- **Day 10 remains the authoritative best lean baseline**
- Day 12 is evidence of stability, but shows intermittent cadence degradation
- Next focus: **rate stability**, not basic latency or tracker compute

**Questions for supervisors:**
- *(To be sent)*

**Blockers:**
- Rate stability issue needs investigation before claiming operational readiness

---

## End of Day Review

**Completed:**
- [x] MAVROS learned (installation, basic topics, coordinate frames)
- [x] Indoor session done (6-minute lean baseline recorded and analyzed)
- [ ] Supervisors emailed (pending)
- [x] Tomorrow planned (adjusted based on findings)

**Time spent:**
- Morning: ~3-4 hours (MAVROS learning)
- Afternoon: ~3-4 hours (indoor perception session)
- Evening: ~2 hours (analysis and documentation)

**Energy level:** medium

**Ready for Day 13?** yes, with adjustments

**Day 12 Indoor Baseline — Official Conclusion:**

6-minute lean indoor run completed without crashes

Full topic chain remained alive and aligned

End-to-end latency remained acceptable: `lat_ms` p95 = 111.4 ms (within 200 ms target)

Overall achieved rate was **9.57 Hz**, below the 10 Hz minimum target and below the 15 Hz desired target

Active-only analysis suggests the system can still produce short ~15 Hz bursts, but the run had strong cadence irregularity (2087 gaps)

**Therefore:**
- **Day 10 remains the authoritative best lean baseline**
- **Day 12 is a stable but bursty validation run**, not a replacement benchmark
- Focus for next work: **rate stability**, not latency or compute issues

---

## GO / NO-GO Gate for First Outdoor Session

### ✅ GO Conditions
- [x] Lean stack runs without crashes
- [x] `lat_ms` p95 stays acceptable (111.4 ms < 200 ms target)
- [x] Field checklist written
- [x] Packing list written
- [x] Scenario sheet written
- [x] MAVROS first bridge frozen (`/mavros/setpoint_velocity/cmd_vel`, `TwistStamped`)
- [x] Pixhawk session procedure clear

### ❌ NO-GO Conditions
- [ ] Crash or restart risk remains — **CLEAR: stable runs validated**
- [ ] Command path still unclear — **CLEAR: MAVROS bridge frozen**
- [ ] Field procedure not documented — **CLEAR: checklist and scenarios created**
- [ ] Loss/reacquisition behaviour still too uncertain — **ACCEPTABLE: basic validation done**
- [ ] Hardware/logistics not ready — **READY: equipment available**

### Decision
**GO** for first outdoor perception-only session (no flight authority)

---

**Tasks:**
- [x] Write GO conditions for first outdoor day
- [x] Write NO-GO conditions
- [x] List remaining blockers
- [x] Decide whether first real session is: **perception-only** (no control authority)

**Deliverables:**
- [x] Explicit GO / NO-GO gate for first outdoor field day
- [x] Updated sequence for the rest of W11 or early W12

---

## Expected Outcomes

By end of Day 12, you should have:

1. **Field documentation ready** ✅
   - [x] Checklist created (`docs/outdoor_field_checklist.md`)
   - [x] Packing list included in checklist
   - [x] Startup / shutdown steps documented
   - [x] Scenario sheet created (`docs/outdoor_scenario_sheet.md`)

2. **Controller better frozen** ✅
   - [x] Validated indoor behaviour (6-min stable run)
   - [x] Known-good run command documented
   - [x] MAVROS bridge frozen in `docs/control_interface.md`

3. **Safe rehearsal path prepared** ⚠️ (optional for Day 13)
   - [ ] Replay or simulation ready (can defer if field-ready)
   - [x] Controller can be exercised without outdoor deployment (indoor validated)

4. **Real outdoor gate clarified** ✅
   - [x] Know exactly what remains before real tests
   - [x] No ambiguity about readiness (GO gate defined)

---

## Day 12 Summary

**What was completed:**
- ✅ MAVROS installed and first bridge frozen
- ✅ 6-minute indoor baseline recorded and analyzed (stable but cadence-limited)
- ✅ Field documentation created (checklist + scenarios)
- ✅ GO/NO-GO gate defined (decision: GO for perception-only outdoor session)
- ✅ Day 10 confirmed as authoritative best lean baseline

**Key technical findings:**
- Indoor run: 9.57 Hz, `lat_ms` p95 = 111.4 ms (acceptable)
- Issue: cadence irregularity (bursty publishing), not latency or compute
- MAVROS bridge: `/mavros/setpoint_velocity/cmd_vel` with `TwistStamped`
- No control node redesign needed (already compatible)

**Blockers cleared:**
- MAVROS installation: ✅ done
- Field procedures: ✅ documented
- Command path: ✅ frozen
- Safety procedures: ✅ written

**Decision for Day 13+:**
- **GO** for first outdoor perception-only session
- Focus: validate outdoor perception, target lock, scenarios
- No flight authority yet (ground-only monitoring if control tested)

---

## Notes

- **No outdoor testing today**
- No MAVROS authority work unless explicitly needed for documentation only
- Focus on reducing uncertainty before any real field session
- Better preparation now means cleaner real results later

---

## Revised W11 Sequence

Instead of:
- Day 12: outdoor testing
- Day 13: protocol execution

**New realistic sequence:**
- **Day 12:** readiness pack + replay/simulation rehearsal
- **Day 13:** controller rehearsal + MAVROS topic-level prep if needed
- **Day 14 or next available:** first real outdoor perception session
- **After that:** larger structured outdoor protocol

---

## Simulation Approach Recommendation

For the current state, the best low-friction option is probably **bag replay or synthetic `/target` publishing**, not a full UAV simulator yet.

This lets you test:
- left/right target motion
- near/far target motion
- timeout / target loss
- command smoothness

...without adding the chaos of full vehicle simulation.
