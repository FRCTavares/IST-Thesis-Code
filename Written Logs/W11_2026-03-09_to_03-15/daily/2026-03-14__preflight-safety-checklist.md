# Daily Log — 2026-03-14 (Day 14) — Indoor Validation Completion + Field Logistics

> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

## Reality Check

**Constraints today:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk at IST  until W12)
- ✅ Complete indoor validation possible
- ✅ Finalize all W12 preparation tasks

**Focus:** Complete indoor baseline validation and finalize W12 field logistics

---

## Goals for Today

### 1. Third Indoor Perception Session
- [ ] Run multi-person test if possible (recruit friend/housemate)
- [ ] Or test with video of multiple people
- [ ] Document target selection and switching
- [ ] Record bag: `bags/live_camera/2026-03-14__indoor_multiperson/`

### 2. Generate Timing Analysis
- [ ] Run analysis on all 3 indoor bags
- [ ] Create plots: FPS over time, latency distributions  
- [ ] Calculate statistics: mean, p50, p95, p99
- [ ] Document thermal behavior over time
- [ ] Save report: `reports/system/W11_indoor_baseline_validation.md`

### 3. Finalize IST Equipment Checklist
- [ ] List everything to bring to IST
- [ ] Verify you have all items at home
- [ ] Pack non-essential items ahead of time
- [ ] **Ethernet cable** (critical!)
- [ ] Laptop, camera, cables

### 4. Create Detailed Tuesday Session Plan
- [ ] Hour-by-hour timeline
- [ ] Specific tasks for each phase
- [ ] Success criteria defined
- [ ] Contingency plans for common issues

### 5. Define Thursday Session Options
- [ ] Option A: If Tuesday has issues (debug plan)
- [ ] Option B: If Tuesday succeeds (outdoor perception)
- [ ] Option C: If Tuesday succeeds (integrated outdoor test)

### 6. Test Control Response
- [ ] Run control node against recorded bags
- [ ] Test different scenarios if time permits
- [ ] Verify command saturation and slew limiting
- [ ] Document any improvements needed

### 7. Prepare Startup/Shutdown Procedures
- [ ] Step-by-step startup sequence
- [ ] MAVROS launch command
- [ ] Perception stack startup
- [ ] Control node startup with correct parameters
- [ ] Clean shutdown procedure

---

## Work Sessions

### Morning Session (3-4 hours)

**Multi-person indoor session:**
```bash
# Option 1: Recruit someone to help test
# Option 2: Play video with multiple people  
# Option 3: Use objects + yourself

# Launch full stack, run 10-15 min
ros2 bag record --storage mcap \
  -o ../bags/live_camera/2026-03-14__indoor_multiperson \
  /camera/fps /detections /timing /target
```

**Timing analysis:**
```bash
# Run analysis on all 3 bags
python tools/analyse_bag_timing.py bags/live_camera/2026-03-12__indoor_baseline_10min
python tools/analyse_bag_timing.py bags/live_camera/2026-03-13__indoor_extended_15min  
python tools/analyse_bag_timing.py bags/live_camera/2026-03-14__indoor_multiperson

# Generate plots and statistics
# Save to reports/system/W11_indoor_baseline_validation.md
```

### Afternoon Session (3-4 hours)

**Finalize equipment checklist:**

To bring to IST:
- [ ] Raspberry Pi 5
- [ ] Camera (TEVS-AR0234)
- [ ] Laptop + charger
- [ ] **Ethernet cable (Pi5 ↔ Pixhawk)** ⚠️ CRITICAL
- [ ] Backup Ethernet cable
- [ ] Camera connection cables
- [ ] Notebook and pen
- [ ] Water, snacks

Available at IST (confirm):
- [ ] Pixhawk 4 + drone
- [ ] 4-cell LiPo battery (CONFIRMED)
- [ ] RC transmitter
- [ ] Tools for prop removal

**Create Tuesday timeline:**

Hour 1: MAVROS connection
- Physical setup (15 min)
- MAVROS launch (15 min)
- Connection validation (20 min)
- Troubleshooting buffer (10 min)

Hour 2: Perception + MAVROS coexistence
- Launch perception (20 min)
- Resource monitoring (15 min)
- Validation (20 min)
- Recording (5 min)

Hour 3: Control integration
- Control node launch (10 min)
- Setpoint validation (20 min)
- Sign validation (20 min)
- Recording (10 min)

Hour 4: Analysis and planning
- Shutdown (5 min)
- Data transfer (10 min)
- Quick analysis (20 min)
- Documentation (15 min)
- Thursday planning (10 min)

### Evening Session (2-3 hours)

**Control testing:**
```bash
# Test control with replayed bags
# Verify smooth behavior
# Test edge cases
```

**Startup/shutdown procedures:**

Startup sequence:
1. Connect Pi5 to battery
2. Connect Pixhawk via Ethernet
3. Remove propellers
4. SSH into Pi5
5. Launch MAVROS: `ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@`
6. Verify connection: `ros2 topic echo /mavros/state`
7. Launch perception stack (6 nodes)
8. Launch control_ref_node with `enable_mavros:=true`

Shutdown sequence:
1. Ctrl-C all ROS nodes
2. Verify MAVROS shutdown
3. Disconnect Pixhawk
4. Power off Pi5
5. Secure equipment

**Confirm with supervisors:**
- [ ] Battery location and status
- [ ] Pixhawk/drone location  
- [ ] Field access Tuesday/Thursday
- [ ] Answers to safety questions received

---

## Expected Deliverables

- [ ] Third indoor session completed
- [ ] Timing analysis and plots generated
- [ ] Equipment checklist finalized
- [ ] Tuesday session plan detailed
- [ ] Thursday options defined
- [ ] Startup/shutdown procedures documented
- [ ] Supervisor confirmations received

---

## Notes and Issues

*(Fill in as you work)*

**Indoor session:**
-

**Timing analysis results:**
-

**Equipment status:**
-

**Tuesday plan:**
-

**Supervisor feedback:**
-

**Blockers:**
-

---

## End of Day Review

**Completed:**
- [ ] Third session done
- [ ] Analysis complete
- [ ] Equipment ready
- [ ] Tuesday planned
- [ ] Supervisors confirmed

**Time spent:**
- Morning: ___ hours
- Afternoon: ___ hours
- Evening: ___ hours

**W12 readiness:** _(high / medium / low)_

**Ready for Day 15?** _(yes / needs adjustment)_

---

## Post-Week Addendum (2026-03-16)

This day log has been updated with implementation work completed after W11 close, during final operational hardening.

### What Was Added

- Added and stabilized ROS dashboard telemetry bridge (`dashboard_bridge_node`) using a dedicated asyncio thread for WebSocket serving.
- Fixed bridge startup/runtime faults:
   - parameter type mismatch for `img_w`/`img_h` CLI overrides,
   - internal name collision with rclpy Node internals (`_clients` renamed to `_ws_clients`),
   - non-blocking WebSocket server startup callback path.
- Normalized dashboard tracks to image space (`x`, `y`, `w`, `h` normalized by image width/height).
- Added one-command live stack launcher:
   - `tools/start_live_stack.sh` starts container inference + ROS graph + dashboard bridge + web video service,
   - interactive shutdown in same terminal with `stop|quit|exit`.
- Added matching stop helper:
   - `tools/stop_live_stack.sh` (kept as optional fallback).
- Added web video service integration (`web_video_server` on port 8080) and explicit dashboard stream URL output.

### Operational Result

- Full stack now starts from a single command and reports concrete endpoints for dashboard video and telemetry.
- Startup sequence now includes dashboard bridge and web video as first-class components.

## Goal

Take the frozen lean perception stack to the real outdoor environment, verify that bring-up works reliably outside the lab, and record a small set of exploratory outdoor bags to assess detection, target selection, and optional ground-only control coexistence.

**Target outcome:**
- Outdoor checklist executed successfully
- Lean stack brought up outdoors without major issues
- At least 1 to 2 outdoor exploratory bags recorded
- Real-world issues documented: lighting, distance, target size, multi-person ambiguity
- Clear decision on whether a larger outdoor session is justified next

---

## Context

| Key | Value |
|-----|-------|
| Previous work | Day 11 lean freeze and control integration, Day 12-13 preparation and rehearsal |
| Operational mode | Lean perception mode only |
| Test mode | Outdoor, ground-only, no flight authority |
| Control status | `control_ref_node` validated indoors on `/control_ref/cmd_vel` |
| MAVROS status | Topic prep may exist, but no vehicle authority assumed |
| Main risk | Outdoor lighting and setup issues, not flight safety yet |
| Success definition | Clean outdoor bring-up and useful exploratory evidence |

---

## Work Plan

### A) Pre-Departure Checklist

Finish the field-ready setup before leaving.

**Tasks:**
- [ ] Run golden-state checks
- [ ] Verify lean startup sequence is available
- [ ] Confirm disk space for bags
- [ ] Confirm power setup, cables, monitor/laptop, mounts
- [ ] Bring printed or local copy of outdoor checklist
- [ ] Confirm participants and location availability
- [ ] Confirm lighting / weather conditions acceptable

**Deliverables:**
- Pre-departure checklist completed
- System ready for transport

---

### B) Outdoor Bring-Up Gate

Do not expand testing until the system proves it can run outdoors.

**Tasks:**
- [ ] Set up at test location
- [ ] Launch lean perception stack
- [ ] Verify `/camera/fps`
- [ ] Verify `/detections`
- [ ] Verify `/target`
- [ ] Check basic visual quality and exposure
- [ ] Optionally launch `control_ref_node` on `/control_ref/cmd_vel` only

**Proceed only if all are true:**
- ✓ camera feed usable outdoors
- ✓ detections alive
- ✓ target alive
- ✓ no major bring-up errors
- ✓ no obvious exposure failure

**If any fail:**
- record one short diagnostic bag
- document issue
- stop scenario expansion

**Deliverables:**
- Outdoor bring-up result
- GO / NO-GO for scenario recording

---

### C) Exploratory Scenario 1 — Single Person Distance Sweep

**Objective:** Check basic outdoor detectability and target quality versus distance.

**Procedure:**
- [ ] One person at about 5 m
- [ ] Then about 10 m
- [ ] Then about 15 m if feasible
- [ ] Then back inward
- [ ] Record short bag: `bags/live_camera/2026-03-14__outdoor__scenario1__single_distance`

**What to observe:**
- detection presence
- target stability
- bbox size changes with distance
- obvious range limit

**Deliverables:**
- Scenario 1 bag
- Short qualitative notes

---

### D) Exploratory Scenario 2 — Two People

**Objective:** Check whether multi-person outdoor scenes remain manageable.

**Procedure:**
- [ ] Two people in frame
- [ ] Change relative position slowly
- [ ] Include mild crossing or ambiguity
- [ ] Record short bag: `bags/live_camera/2026-03-14__outdoor__scenario2__two_people`

**What to observe:**
- both people detected
- target stability
- obvious confusion or switching
- whether outdoor clutter affects selection

**Deliverables:**
- Scenario 2 bag
- Short qualitative notes

---

### E) Optional Ground-Only Control Coexistence

Only do this if outdoor perception is already stable.

**Tasks:**
- [ ] Launch `control_ref_node` on `/control_ref/cmd_vel`
- [ ] Verify it consumes outdoor `/target`
- [ ] Do not connect vehicle authority
- [ ] Optionally record: `/control_ref/cmd_vel`

**Deliverables:**
- Outdoor perception-to-control coexistence note
- Optional bag evidence

---

### F) Quick Post-Run Review

Do a fast evidence review after returning.

**Tasks:**
- [ ] Run `ros2 bag info` on recorded bags
- [ ] Confirm expected topics exist
- [ ] Write immediate findings:
  - lighting / exposure
  - distance limit
  - target size issues
  - multi-person issues
  - outdoor setup issues
- [ ] Decide next step:
  - larger outdoor session
  - targeted fixes first
  - repeat exploratory session

**Deliverables:**
- Short outdoor notes
- Decision for next real-world session

---

## Expected Outcomes

By end of Day 14, you should have:

1. **Proof the stack can be brought outdoors**
   - or a documented reason why not

2. **At least 1 to 2 useful outdoor bags**
   - single-person distance sweep
   - two-person exploratory case

3. **Real outdoor observations**
   - lighting behaviour
   - distance limit
   - target quality
   - multi-person behaviour

4. **A grounded next-step decision**
   - expand outdoor testing
   - fix issues first
   - repeat controlled exploratory run

---

## Not the Goal of Day 14

Do not make Day 14 about:
- pre-flight safety validation
- geofence enforcement
- altitude limit validation
- emergency stop latency claims
- battery-to-flight endurance claims
- flight readiness GO / NO-GO

Those belong later, after:
- outdoor perception is stable
- MAVROS path is better understood
- vehicle authority path is actually integrated

---

## Issues and Risks

### Likely issues
- outdoor exposure / glare
- weaker detection at long range
- target instability in clutter
- setup friction in the field
- lower-than-expected rate outdoors

### Adaptation strategy
- if lighting is poor, move to shade or adjust orientation
- if range is poor, keep exploratory distances shorter
- if multi-person is unstable, treat that as evidence, not failure
- if bring-up is flaky, record one diagnostic bag and stop expanding scope

---

## Notes

- This is the first real outdoor evidence day, not the final protocol
- Keep bags short and purposeful
- Do not revert to heavy profiling mode
- Do not claim flight readiness from this day
- The purpose is to learn what the outdoor environment actually does to your stack
