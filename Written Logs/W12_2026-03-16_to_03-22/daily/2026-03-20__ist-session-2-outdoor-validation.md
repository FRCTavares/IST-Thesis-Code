# Daily Log — 2026-03-20 (Day 20) — IST Session 2: Outdoor Validation or Debug

## Overview

**SECOND IST SESSION — 4 HOURS**
**Location:** IST field/lab
**Focus:** Based on Option A/B/C from Wednesday planning
**Equipment:** Pi5, Pixhawk 4, camera, laptop, Ethernet cable, battery, (props if approved)

---

## Session Goals (4 Hours)

**This session's approach:** _(Option A / B / C)_

### Option A: Outdoor Validation (if Tuesday was success)
- Hour 1: Indoor review, RViz setup, final checks
- Hour 2: Outdoor setup, safety checks, unarmed testing
- Hour 3: Armed testing (if supervisor approved)
- Hour 4: Analysis, documentation, log collection

### Option B: Debug and Validate (if Tuesday was partial)
- Hour 1: Deploy fixes, test problematic components
- Hour 2: Full stack validation indoor
- Hour 3: Extended integration testing
- Hour 4: Documentation and next week planning

### Option C: Fundamental Debugging (if Tuesday failed)
- Hour 1: Isolate problem layer
- Hour 2: Fix and re-test incrementally
- Hour 3: Simplified integration
- Hour 4: Regroup and replanning

---

## Safety Checklist (Read BEFORE Starting)

**CRITICAL RULES (same as Tuesday + outdoor additions):**
- [ ] **NEVER ARM** without explicit supervisor approval
- [ ] **PROPS REMOVED** until supervisor approves installation
- [ ] **RC TRANSMITTER OVERRIDE** tested and verified
- [ ] **SUPERVISOR PRESENT** at all times
- [ ] **WEATHER CHECKED** (if outdoor): wind < 5 m/s, no rain
- [ ] **AREA CLEAR** of people not involved in test
- [ ] **EMERGENCY PROCEDURE** reviewed with all present

**Outdoor-specific (if Option A):**
- [ ] Clear takeoff/landing zone (5m radius minimum)
- [ ] No obstacles in flight area
- [ ] GPS signal checked (if using GPS modes)
- [ ] Battery voltage verified (full charge)
- [ ] Pre-flight checklist completed
- [ ] Flight boundaries established
- [ ] Emergency landing spots identified

**Arming conditions (if reached):**
- [ ] All unarmed tests passed
- [ ] All safety checks completed
- [ ] Supervisors explicitly approve
- [ ] RC pilot ready for immediate takeover
- [ ] Everyone briefed on emergency procedure
- [ ] Props verified secure
- [ ] Battery voltage good
- [ ] Weather suitable

---

## Option A: Outdoor Validation (if Tuesday success)

### Hour 1: Indoor Review and Preparation (Time: ___ to ___)

**Quick stack verification:**
```bash
# Launch full stack following Tuesday's successful sequence
# Terminal 1: MAVROS
ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@

# Terminals 2-7: Perception stack (camera, inference, tracker, selector)
# Terminal 8: Control node with MAVROS enabled
ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=true

# Verify all working as Tuesday
```

**Add RViz visualization (optional):**
```bash
# Terminal 9: RViz
ros2 run rviz2 rviz2

# Add displays:
# - /thesis/tracks (visualization_msgs/MarkerArray)
# - /thesis/target_selector/target_state
# - Camera image if needed
```

**Pre-outdoor checklist:**
- [ ] Indoor test successful
- [ ] All fixes from Wednesday working
- [ ] Performance as expected
- [ ] Commands reasonable magnitude
- [ ] Safety behaviors verified
- [ ] Ready for outdoor

---

### Hour 2: Outdoor Setup and Safety (Time: ___ to ___)

**Physical setup:**
- [ ] Transport equipment to outdoor location
- [ ] Set up drone on level surface
- [ ] Install props (if supervisor approves)
- [ ] Connect Ethernet cable
- [ ] Connect battery
- [ ] Position laptop/monitor
- [ ] Set up RC transmitter

**Area preparation:**
- [ ] Clear takeoff zone (5m radius)
- [ ] Establish flight boundaries
- [ ] Identify emergency landing spots
- [ ] Brief all personnel on positions
- [ ] Test RC override (before launching stack)

**System startup outdoor:**
```bash
# Same launch sequence as indoor
# Monitor for outdoor-specific issues:
# - Lighting changes affecting camera
# - GPS interference
# - Network stability
```

**Unarmed outdoor testing:**
- [ ] Launch full stack
- [ ] Test person detection outdoors
- [ ] Verify tracking in outdoor lighting
- [ ] Check control commands
- [ ] Monitor MAVROS stability
- [ ] Verify safety behaviors

**Go/No-go decision for arming:**
- Unarmed tests passed: _(yes / no)_
- All safety checks complete: _(yes / no)_
- Supervisors approve: _(yes / no)_
- Weather suitable: _(yes / no)_
- Equipment status good: _(yes / no)_

**Decision:** _(ARM / DO NOT ARM)_

---

### Hour 3: Testing (Armed if approved) (Time: ___ to ___)

**If APPROVED TO ARM:**

**Pre-arm final checks:**
- [ ] Props secure
- [ ] Battery voltage: ___ V (> 14.8V for 4S)
- [ ] RC transmitter tested
- [ ] MAVROS connected
- [ ] All personnel ready
- [ ] Area clear

**Arming procedure:**
```bash
# Supervisor arms via RC or ground station
# NOT via MAVROS initially

# Monitor MAVROS state
ros2 topic echo /mavros/state

# Should show:
# armed: True
# mode: "STABILIZE" or approved mode
```

**Test progression (if armed):**

**Test 1: Hover with manual control (no perception)**
- Supervisor controls via RC
- Verify basic flight stable
- Land if any issues

**Test 2: Hover with perception running**
- Supervisor controls via RC
- Perception stack running
- Control node NOT sending commands yet
- Verify CPU stable, no crashes
- Land

**Test 3: Minimal autonomous control (if Tests 1-2 ok)**
- Launch control_ref_node
- Person stands in view
- Expect small position adjustments
- RC pilot ready for instant takeover
- Monitor commands
- Test for 10-30 seconds max
- Land

**Emergency procedure:**
- RC pilot takes over immediately if anything unexpected
- Any personnel can call "STOP"
- Land immediately, do not continue test

**If NOT APPROVED TO ARM:**

Continue unarmed testing:
- Extended perception validation outdoor
- Different lighting conditions
- Multiple test scenarios
- Collect data for analysis
- Focus on perception performance outdoor

---

### Hour 4: Analysis and Documentation (Time: ___ to ___)

**Graceful shutdown and packup:**
- [ ] Land (if flying)
- [ ] Disarm
- [ ] Stop all ROS nodes
- [ ] Disconnect battery
- [ ] Remove props (if installed)
- [ ] Pack equipment

**Data collection:**
```bash
# Save logs
cd $THESIS_ROOT
mkdir -p logs/2026-03-20_IST_session2

# Save ROS logs, terminal outputs, etc.
```

**Session debrief:**

**What worked:**
-

**What didn't work:**
-

**Outdoor-specific findings:**
- Perception outdoor: ___
- Lighting impact: ___
- Network stability: ___
- Control performance: ___

**If armed testing conducted:**
- Flight stability: ___
- Control integration: ___
- Safety systems: ___
- Issues observed: ___
- Maximum test duration: ___ seconds
- Supervisor feedback: ___

**Key learnings:**
-

**Next steps for Week 13:**
-

---

## Option B: Debug and Validate (if Tuesday partial)

### Hour 1: Fix Deployment (Time: ___ to ___)

**Deploy Wednesday's fixes:**
```bash
# Pull latest code
cd $THESIS_ROOT/ros2_ws
git pull

# Rebuild
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_bringup
```

**Test fixed components:**
- Component 1: ___
  - Issue was: ___
  - Fix applied: ___
  - Test result: ___

- Component 2: ___
  - Issue was: ___
  - Fix applied: ___
  - Test result: ___

---

### Hour 2: Full Stack Validation (Time: ___ to ___)

**Launch complete stack:**
```bash
# Full 8-terminal launch
# Monitor all topics
# Check performance metrics
```

**Validation checklist:**
- [ ] MAVROS connected and stable
- [ ] Perception at ~16 Hz
- [ ] Tracking working
- [ ] Target selector correct states
- [ ] Control commands reasonable
- [ ] Safety behaviors correct
- [ ] CPU usage acceptable
- [ ] No crashes or errors

---

### Hour 3: Extended Testing (Time: ___ to ___)

**Test scenarios:**

**Scenario 1: Target enters and exits:**
- Start with no person
- Person enters view
- Track for 30 seconds
- Person exits view
- Verify LOST state and zero commands

**Scenario 2: Multiple people:**
- Two people visible
- Verify single target selected
- Verify stable tracking

**Scenario 3: Occlusion:**
- Person behind obstacle
- Verify continued tracking or LOST
- Verify recovery when visible again

**Results:**
- Scenario 1: ___
- Scenario 2: ___
- Scenario 3: ___

---

### Hour 4: Documentation and Planning (Time: ___ to ___)

**Results summary:**
- Fixes successful: _(yes / partial / no)_
- System validated: _(yes / partial / no)_
- Ready for outdoor W13: _(yes / needs work)_

**Next week planning:**
-

---

## Option C: Fundamental Debugging (if Tuesday failed)

### Hour 1: Problem Isolation (Time: ___ to ___)

**Test each layer independently:**

**Layer 1: MAVROS only**
```bash
ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@
ros2 topic echo /mavros/state
# Result: ___
```

**Layer 2: Perception only (no MAVROS)**
```bash
# Launch camera, inference, tracker, selector
# No MAVROS running
# Result: ___
```

**Layer 3: Control only (test topic, no MAVROS)**
```bash
ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=false
# Result: ___
```

**Problem identified:** ___

---

### Hour 2: Targeted Fix (Time: ___ to ___)

**Fix implementation:**
- Edit code
- Test fix
- Verify incrementally

---

### Hour 3: Minimal Integration (Time: ___ to ___)

**Build up layer by layer:**
- Start with working layers
- Add one layer at a time
- Verify stability at each step

---

### Hour 4: Regroup (Time: ___ to ___)

**Assess situation:**
- What's working: ___
- What's blocked: ___
- Need supervisor help: ___
- Plan for W13: ___

---

## Equipment and Environment

**Hardware setup:**
- Raspberry Pi 5: ___
- Pixhawk 4: ___
- Camera: ___
- Battery: ___ V (start), ___ V (end)
- Props: _(installed: yes/no)_ _(armed: yes/no)_

**Environment:**
- Location: ___
- Indoor/outdoor: ___
- Weather (if outdoor): ___ (temp, wind, clouds)
- Lighting: ___
- People present: ___

---

## Issues Log

**Issue 1:**
- Time: ___
- Phase: ___
- Description: ___
- Resolution: ___
- Status: ___

**Issue 2:**
- Time: ___
- Phase: ___
- Description: ___
- Resolution: ___
- Status: ___

---

## Test Results

**Test:** ___
- Expected: ___
- Actual: ___
- Result: _(pass / fail)_
- Notes: ___

**Test:** ___
- Expected: ___
- Actual: ___
- Result: _(pass / fail)_
- Notes: ___

---

## Deliverables

- [ ] Session plan executed
- [ ] Tests conducted
- [ ] Results documented
- [ ] Issues logged
- [ ] Data collected
- [ ] W13 plan outlined

---

## Supervisor Feedback

**From supervisors:**
-

**Approvals/decisions:**
-

**Safety concerns raised:**
-

**Recommendations for W13:**
-

---

## End of Session Review

**Session outcome:** _(exceeded / met / below)_ expectations

**Time spent:** 4 hours

**Armed testing conducted:** _(yes / no)_

**If yes, flight duration:** ___ seconds/minutes

**System readiness for W13:** _(ready / needs work / major issues)_

**Critical takeaway from W12:**
-

**Most important lesson learned:**
-

---

## W13 Planning Preview

**Primary goal for next week:**
-

**Required before next session:**
-

**Equipment/setup changes needed:**
-

**Questions for supervisors before W13:**
-
