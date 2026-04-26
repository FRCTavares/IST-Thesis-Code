# Daily Log — 2026-03-11 — Lean-Mode Freeze, Control Interface Integration, and Outdoor Readiness
> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

## Goal

Freeze the validated lean perception configuration, advance ground-only control integration, and prepare the full outdoor test pack for the next available field day.

**Target outcome:**
- Lean perception mode frozen and documented
- `control_ref_node` integrated against the validated `/target` interface
- Ground-only MAVROS/control message flow verified
- Safety logic and fail-safe behaviour reviewed
- Outdoor checklist, scenario plan, and bag naming prepared
- One short indoor smoke run confirms the frozen setup still works

---

## Context

| Key | Value |
|-----|-------|
| Previous validation | Lean live stack validated on Day 10 |
| Day 10 performance | 10 minute lean run: 16.644 Hz, lat_ms p95 = 91.296 ms, throttled = 0x0 |
| Constraint | Outdoor session cannot happen on Day 11 |
| Best use of Day 11 | Freeze what works, push control integration (ground-only), reduce risk before first field session |
| Test location | Indoor lab only (no outdoor access today) |
| Control scope | Ground validation only: no flight authority, no risky actuator behaviour |

---

## Work Plan

### A) Freeze the Validated Lean Perception Mode

Save the final tracker live-mode configuration as the current operational standard.

**Tasks:**
- [ ] Document the exact lean configuration:
  - Fast score path enabled (no per-track Python IoU score recovery)
  - `/timing_tracker` disabled in live mode
  - Lean recording topics: `/camera/fps`, `/detections`, `/timing`, `/target`
  - `/tracks` not recorded in operational bags
- [ ] Record the exact startup commands used for the validated 10 minute run
- [ ] Update runbook/notes so live mode and profiling mode are clearly separated
- [ ] Save the lean configuration as the default for outdoor field sessions
- [ ] Document when to switch back to profiling mode (dedicated debug sessions only)

**Deliverables:**
- Frozen lean configuration note: `docs/lean_operational_mode.md` or in runbook
- Final live startup command sequence
- Live mode vs profiling mode comparison table

---

### B) Control Integration — Ground-Only

Review and freeze the perception-to-control contract, then verify MAVROS message flow on the ground.

**Tasks:**
- [ ] Review and freeze the perception-to-control contract from `/target`:
  - `ex`, `ey` (normalized image coordinates)
  - `bbox_area` or bbox size as range proxy
  - `target_visible`, `target_lost`, `reacquired` (status flags)
  - Message rate and timing assumptions
- [ ] Bring up MAVROS and verify connection to Pixhawk:
  - Launch MAVROS: `ros2 launch mavros apm.launch.py fcu_url:=<connection_string>`
  - Verify `/mavros/state` (FCU connection status)
  - Check `/mavros/local_position/pose` (position feedback)
- [ ] Integrate `control_ref_node` against `/target`:
  - Subscribe to `/target`
  - Generate control setpoints (position, velocity, or attitude)
  - Publish to MAVROS setpoint topics
  - Verify message flow without needing outdoor testing
- [ ] Verify control outputs are bounded and safe:
  - Check setpoint rate matches target (30 Hz typical)
  - Confirm command limits are reasonable (e.g., max velocity, max position error)
  - Verify fail-safe behaviour when target is lost
  - Confirm safety bounds prevent risky commands
- [ ] If useful, test with live indoor target movement or bag replay

**Important limit:**
- Ground validation only
- No flight authority assumptions
- No armed motors or risky actuator behaviour

**Deliverables:**
- `control_ref_node` message flow validated
- Notes on setpoint contract and safety bounds: `docs/control/control_interface.md`
- List of remaining blockers before any flight-related test

---

### C) Indoor Smoke Validation in Final Operational Setup

Launch lean perception stack + control-side nodes and confirm coexistence.

**Tasks:**
- [ ] Launch lean perception stack:
  - camera_init_node, camera_capture_node
  - Live inference service (port 5556, HAILO_FRAME_SOURCE=ros)
  - thesis_inference_client, thesis_tracker (lean config)
  - thesis_target_selector
- [ ] Launch control-side nodes:
  - MAVROS (if available)
  - `control_ref_node`
- [ ] Run a short indoor smoke test (2-3 minutes):
  - Verify `/target` is stable enough for control consumption
  - Check control node processes `/target` correctly
  - Verify no regressions after freezing the configuration
  - Confirm timing and rates are consistent with Day 10
- [ ] Record one short lean bag if needed for validation

**Deliverables:**
- Short confirmation run (2-3 minutes)
- Short note confirming perception and control interface coexist cleanly

---

### D) Outdoor Readiness Pack

Prepare all logistics, checklists, and documentation for the next outdoor field day.

**Tasks:**
- [ ] Prepare outdoor checklist:
  - Pre-test checks (battery, connections, golden state)
  - Startup procedure for field use
  - Bag recording commands
  - Shutdown procedure
- [ ] Prepare participant scenario sheet:
  - Scenario 1: Single person, distance variation
  - Scenario 2: Two people, simultaneous tracking
  - Scenario 3: Three people, occlusion
  - Scenario 4: Dynamic motion
  - Instructions for each scenario
- [ ] Prepare bag naming scheme for outdoor runs:
  - Format: `2026-MM-DD__outdoor__scenario<N>__<descriptor>/`
  - Examples: `2026-03-12__outdoor__scenario1__single_distance/`
- [ ] Check hardware and logistics:
  - Disk space on Pi 5 (need ~10 GB free for outdoor bags)
  - Batteries charged (Tattu 6S 4500 mAh)
  - Cables, mounting, monitor/laptop
  - Confirm what must be carried to the court
- [ ] Write startup and shutdown checklist for field use

**Deliverables:**
- Outdoor checklist: `docs/outdoor_field_checklist.md`
- Scenario sheet for participants
- Field packing list
- Outdoor bag naming plan

---

### E) Reschedule Field Plan

Move first outdoor perception test to the next available day.

**Tasks:**
- [ ] Identify next available outdoor day (weather, personnel, location)
- [ ] Update T-32 daily log sequence:
  - Day 11 (today): lean freeze + control integration + outdoor prep
  - Day 12 (or next available): first outdoor perception test
  - Day 13 (or next available): formal outdoor protocol
- [ ] Keep rest of week flexible depending on when outdoor access happens
- [ ] Update weekly plan if needed

**Deliverables:**
- Updated T-32 sequence with new outdoor dates
- Clear next field day target

---

## Work Completed

### A) Lean Perception Mode Frozen ✓

**Status:** Complete

- [x] Created comprehensive `docs/lean_operational_mode.md`
- [x] Documented exact lean configuration with validated performance results
- [x] Recorded frozen startup command sequence (6 terminals)
- [x] Updated RUNBOOK.md with lean vs profiling mode distinction
- [x] Updated README.md with operational modes section
- [x] Clarified `/timing_tracker` as profiling-only throughout documentation

**Key frozen parameters:**
- Topics: `/camera/fps`, `/detections`, `/timing`, `/target` only
- No `/tracks` or `/timing_tracker` in operational bags
- Fast tracker score path enabled
- Manual startup sequence is the operational standard

---

### B) Control Integration — Ground-Only ✓

**Status:** Complete — First ground-only control reference node working

**Major accomplishments:**

1. **Created `control_ref_node`**
   - New ROS 2 node in `thesis_bringup` package
   - Subscribes to `/target` successfully
   - Publishes to `/control_ref/cmd_vel`
   - Clean startup and shutdown

2. **Fixed QoS matching**
   - Discovered `/target` uses BEST_EFFORT QoS
   - Matched subscriber QoS in control node
   - Message flow now working end-to-end

3. **Discovered `/target` coordinate system**
   - `/target` currently uses **pixel coordinates**, not normalized [0,1]
   - `cx, cy, w, h` are in pixel space (0-640)
   - Documented in `docs/control/control_interface.md`

4. **Implemented internal normalization**
   - Control node now normalizes internally: `cx_norm = cx / img_w`
   - Parameters: `img_w=640.0`, `img_h=640.0`
   - Maintains compatibility with current target selector output

5. **Validated control signs**
   - **Yaw:** Target left → negative yaw, target right → positive yaw ✓
   - **Forward:** Target far (small h) → positive forward, target close (large h) → negative forward ✓
   - Indoor tuning: `desired_h_norm=0.90` for close-range testing

6. **Safety features implemented**
   - Target validity logic (freshness timeout, bounds checking, min score/quality)
   - Fail-safe zeroing when target invalid or stale
   - Slew rate limiting (smooth ramping: 0.0 → -0.03 → -0.06 → -0.09 → -0.1)
   - Command saturation at configurable limits

7. **Frozen run command:**
```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -p cmd_topic:=/control_ref/cmd_vel \
  -p img_w:=640.0 \
  -p img_h:=640.0 \
  -p desired_h_norm:=0.90
```

**Deliverables completed:**
- [x] `control_ref_node.py` created and working
- [x] `/target` to control message flow validated
- [x] `docs/control/control_interface.md` updated with pixel-space reality
- [x] Control signs validated (yaw and forward)
- [x] Safety bounds and fail-safe zeroing working
- [x] Slew limiting implemented

---

### C) Documentation Updates ✓

**Status:** Complete

- [x] Created `docs/lean_operational_mode.md` with full frozen config
- [x] Created `docs/control/control_interface.md` with perception-to-control contract
- [x] Updated `RUNBOOK.md` with lean mode startup and recording commands
- [x] Updated `README.md` with operational modes section and clarifications
- [x] Fixed `/timing_tracker` marked as profiling-only everywhere

---

### D) Indoor Smoke Validation ✓

**Status:** Complete

**Integrated smoke bag recorded successfully:**
- Bag: `bags/live_camera/2026-03-11__indoor__lean_control_smoke_v2`
- Duration: **36.849 s**
- Messages: **2063**

**Recorded topics:**
- `/camera/fps` — 37 msgs
- `/detections` — 323 msgs
- `/timing` — 323 msgs
- `/target` — 325 msgs
- `/control_ref/cmd_vel` — 1055 msgs

**Observed rates:**
- `/control_ref/cmd_vel`: ~28.6 Hz (control loop running as expected)
- `/detections`: ~8.8 Hz
- `/target`: ~8.8 Hz
- `/timing`: ~8.8 Hz

**What this validates:**
- ✓ Lean perception stack and `control_ref_node` ran together successfully
- ✓ `/target` was published and consumed during the run
- ✓ `/control_ref/cmd_vel` was generated and recorded continuously
- ✓ End-to-end perception-to-control coexistence validated on the real stack
- ✓ Control node subscribed to `/target` and processed it correctly
- ✓ No crashes, no message flow issues, clean coexistence

**Important note:**
- This was a short integration smoke bag, not a new authoritative performance benchmark
- The purpose was interface and coexistence validation rather than final rate characterization
- Lower detection rate (~8.8 Hz vs Day 10's 16.6 Hz) likely due to different indoor conditions or participant movement
- Control loop maintained target ~30 Hz regardless of perception update rate (as designed)

---

### E) Outdoor Readiness Pack 📋

**Status:** Deferred to Day 12

Given the productive control integration work, outdoor prep tasks were deprioritized for today:
- [ ] Outdoor field checklist
- [ ] Participant scenario sheet
- [ ] Field packing list
- [ ] Hardware readiness check

**Decision:** Move outdoor prep to Day 12 morning, before first field test.

---

## Key Results

### Control Integration Milestone

**Today achieved the first ground-only perception-to-control bridge:**

End-to-end live path now working:
```
camera → inference → detections → tracker → tracks → target selector → /target → control_ref_node → /control_ref/cmd_vel
```

**Control node capabilities validated:**
- Live `/target` subscription with correct QoS
- Internal coordinate normalization (pixel → normalized)
- Yaw and forward control sign correctness
- Target validity checking
- Fail-safe zeroing on target loss
- Slew rate limiting for smooth commands
- Bounded outputs with configurable saturation
- Clean startup and shutdown

### Frozen Configuration Milestone

**Lean operational mode fully documented:**
- Exact startup sequence (6 terminals)
- Recording topics frozen: `/camera/fps`, `/detections`, `/timing`, `/target`
- Profiling-only topics excluded: `/tracks`, `/timing_tracker`
- Success criteria defined
- Known limitations documented

### What Changed from Plan

**Original Day 11 plan:**
1. Freeze lean mode ✓
2. Control integration (ground-only) ✓
3. Indoor smoke run ✓
4. Outdoor prep 📋 (deferred)

**Actual Day 11 execution:**
- Spent more time on control node implementation than planned
- Discovered and fixed pixel-space coordinate issue
- Validated control signs and safety features thoroughly
- Documentation updates more extensive than planned
- Outdoor prep deferred to maintain focus on control quality

**Result:** More substantive control progress at the cost of outdoor prep tasks.

---

## Remaining Blockers

### Before MAVROS Integration
- [ ] MAVROS topic choice not yet frozen
- [ ] MAVROS message format not yet selected
- [ ] Pixhawk connection not yet tested
- [ ] Coordinate frame conventions not yet aligned

### Before Outdoor Testing
- [ ] Outdoor field checklist
- [ ] Participant scenario definitions
- [ ] Field hardware packing list
- [ ] Bag naming scheme for outdoor runs

### Before Flight-Related Work
- [ ] Restart reliability not yet validated
- [ ] Loss/reacquisition behavior needs systematic testing
- [ ] Command limits not yet reviewed against actual vehicle
- [ ] Field-safe test procedure not yet documented

---

## Honest Assessment

### What Worked Well Today

1. **Control integration made real progress**
   - Not just planning, but actual working code
   - End-to-end message flow validated
   - Control signs confirmed correct

2. **Problem-solving was effective**
   - QoS mismatch identified and fixed
   - Pixel-space coordinates discovered and handled properly
   - Internal normalization avoided upstream redesign

3. **Documentation discipline maintained**
   - All changes documented as completed
   - Frozen configurations saved
   - Known limitations clearly stated

4. **Safety-first approach**
   - Validity checking implemented first
   - Fail-safe zeroing works
   - Slew limiting prevents jumps

### What Could Be Better

1. **Time estimation**
   - Control node took longer than planned
   - Outdoor prep not completed
   - No integrated bag recorded yet

2. **Scope management**
   - Could have stopped earlier with simpler controller
   - Tuning and sign validation took significant time
   - Perfect became enemy of good enough

3. **Testing completeness**
   - Should record one short integrated bag
   - Smoke test not formally documented
   - No systematic loss-of-target validation yet

### Learnings for Day 12

1. **Finish control integration first**
   - Record one 2-3 minute integrated bag with `/control_ref/cmd_vel`
   - Document the run as smoke test
   - Then move to outdoor prep

2. **MAVROS hookup is next control step**
   - Topic-level integration only
   - No vehicle authority yet
   - Ground validation before field

3. **Outdoor prep must happen before field day**
   - Cannot skip checklist preparation
   - Scenarios must be defined
   - Hardware must be verified

---

## Tomorrow's Priority Order

1. **Record integrated smoke run (15 min)**
   - 2-3 minute bag with lean perception + control ref
   - Topics: `/camera/fps`, `/detections`, `/timing`, `/target`, `/control_ref/cmd_vel`
   - Document as baseline integrated run

2. **MAVROS topic-level integration (2 hours)**
   - Choose MAVROS setpoint topic
   - Verify message format
   - Test ground-only message flow
   - Document in `docs/control/control_interface.md`

3. **Pre-flight safety validation (2 hours)**
   - Systematic loss-of-target testing
   - Command limit review
   - Fail-safe behavior documentation
   - Emergency stop logic

4. **Move to outdoor if Day 12 allows, otherwise Day 14**
   - Complete outdoor prep in morning
   - Execute first outdoor test in afternoon
   - Weather/logistics permitting

---

## Notes

**Today's biggest win:**
- Ground-only control integration is now real, not just planned
- You have a working perception-to-control bridge on the actual stack

**Today's biggest surprise:**
- `/target` uses pixel coordinates, not normalized
- This was discovered through actual implementation, not design review

**Today's best decision:**
- Implementing internal normalization in control node
- Avoided upstream message redesign churn today

**Today's deferred work:**
- Outdoor prep pushed to Day 12
- MAVROS integration not started

**Status for T-32 goals:**
- ✓ Lean perception mode frozen and validated
- ✓ Control interface integration complete (ground-only)
- ✓ Integration smoke bag recorded
- ⚠️ MAVROS hookup not yet started
- 📋 Outdoor testing moved to Day 14-15
- 📋 Safety validation moved to Day 13

**Recommendation:**
- Day 11 was productive but scope-expanded beyond plan
- Day 12 should focus on completing control integration (MAVROS hookup)
- Day 13 should focus on safety validation
- Day 14-15 should focus on outdoor testing
- This is a more realistic sequence than original T-32 plan
