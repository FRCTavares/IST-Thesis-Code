# Daily Log — 2026-03-18 (Day 18) — IST Session 1: MAVROS Integration

## Overview

**FIRST IST SESSION — 4 HOURS**
**Location:** IST field/lab
**Focus:** MAVROS connection, perception coexistence, control integration (unarmed)
**Equipment:** Pi5, Pixhawk 4, camera, laptop, Ethernet cable, battery

---

## Session Goals (4 Hours)

### Phase 1: MAVROS Connection and Validation (Hour 1)
**Goal:** Establish ROS 2 ↔ MAVROS ↔ Pixhawk communication
- [ ] Physical setup (Ethernet: Pi5 ↔ Pixhawk)
- [ ] Power on Pixhawk with battery
- [ ] SSH into Pi5 from laptop
- [ ] Launch MAVROS node
- [ ] Verify `/mavros/state` publishes
- [ ] Confirm connection status

### Phase 2: Perception + MAVROS Coexistence (Hour 2)
**Goal:** Verify perception stack runs without interfering with MAVROS
- [ ] Launch camera nodes
- [ ] Launch inference service
- [ ] Launch tracker (SORT)
- [ ] Launch target_selector
- [ ] Monitor CPU usage
- [ ] Check MAVROS connection stability
- [ ] Verify all topics publishing

### Phase 3: Control Integration (Unarmed) (Hour 3)
**Goal:** Integrate control_ref_node with MAVROS (props removed, never arm)
- [ ] Launch control_ref_node (MAVROS disabled)
- [ ] Verify reads from target_selector
- [ ] Verify publishes to test topic
- [ ] Enable MAVROS parameter
- [ ] Verify publishes to `/mavros/setpoint_velocity/cmd_vel`
- [ ] Monitor commands (echo topic continuously)
- [ ] Test static person scenario
- [ ] Verify coordinate frame (body frame)

### Phase 4: Analysis and Thursday Planning (Hour 4)
**Goal:** Document findings, identify issues, plan next session
- [ ] Stop all nodes gracefully
- [ ] Review logs
- [ ] Document issues encountered
- [ ] Identify fixes needed
- [ ] Plan Thursday session approach
- [ ] Backup logs and data

---

## Safety Checklist (Read BEFORE Starting)

**CRITICAL RULES:**
- [ ] **NEVER ARM THE DRONE** without explicit supervisor approval
- [ ] **PROPS REMOVED** for all initial testing
- [ ] **RC TRANSMITTER READY** with override capability
- [ ] **SUPERVISOR PRESENT** at all times
- [ ] **EMERGENCY STOP** = kill control_ref_node immediately

**Pre-flight checks (even unarmed):**
- [ ] Battery charged and connected properly
- [ ] Ethernet cable secure (Pi5 ↔ Pixhawk)
- [ ] Camera powered and connected
- [ ] All personnel aware system is active
- [ ] Clear workspace around drone

**During operation:**
- [ ] Monitor `/mavros/setpoint_velocity/cmd_vel` continuously
- [ ] Watch for unexpected commands
- [ ] Check MAVROS connection status
- [ ] Note any warnings in terminal
- [ ] Stop if anything looks wrong

---

## Hour-by-Hour Timeline

### Hour 1: MAVROS Connection (9:00 - 10:00, example time)

**Setup (15 min):**
```bash
# On Pi5
cd $THESIS_ROOT/ros2_ws
source install/setup.bash

# Check Pixhawk IP (should be 192.168.1.1)
ping 192.168.1.1
```

**Launch MAVROS (5 min):**
```bash
# Terminal 1 (Pi5)
source /opt/ros/jazzy/setup.bash
ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@
```

**Validation (20 min):**
```bash
# Terminal 2 (Pi5 or laptop)
source /opt/ros/jazzy/setup.bash

# Check state
ros2 topic echo /mavros/state

# Expected:
# connected: True
# armed: False
# mode: "STABILIZE" or similar

# List all MAVROS topics
ros2 topic list | grep mavros

# Check setpoint topic exists
ros2 topic info /mavros/setpoint_velocity/cmd_vel
```

**Debugging time (20 min):**
- If connection fails: check Ethernet, check IP, check ArduPilot params
- If topics not appearing: check MAVROS launch output
- Document all issues

---

### Hour 2: Perception Coexistence (10:00 - 11:00)

**Current 6-terminal lean stack:**

```bash
# Terminal 1: MAVROS (already running)

# Terminal 2: Camera init
cd $THESIS_ROOT/infer_service
source opt/hailo/setup_env.sh
python3 camera/init_camera.py

# Terminal 3: Camera capture
cd $THESIS_ROOT/infer_service
source opt/hailo/setup_env.sh
python3 camera/camera_capture.py

# Terminal 4: Container inference
cd $THESIS_ROOT/infer_service
source opt/hailo/setup_env.sh
./run_detection_zmq.sh

# Terminal 5: ROS 2 inference client
cd $THESIS_ROOT/ros2_ws
source install/setup.bash
ros2 run thesis_bringup inference_client_node

# Terminal 6: Tracker (SORT)
cd $THESIS_ROOT/ros2_ws
source install/setup.bash
ros2 run thesis_bringup tracker_node --ros-args -p tracker_type:=sort

# Terminal 7: Target selector
cd $THESIS_ROOT/ros2_ws
source install/setup.bash
ros2 run thesis_target_selector target_selector_node
```

**Validation:**
```bash
# Terminal 8: Monitor all topics
ros2 topic hz /thesis/detections
ros2 topic hz /thesis/tracks
ros2 topic hz /thesis/target_selector/target_state

# Check MAVROS still connected
ros2 topic echo /mavros/state --once

# Check CPU usage
htop
```

**Expected outcomes:**
- All perception topics at ~16 Hz
- MAVROS connection stable
- CPU usage < 80% (monitor Pi5 load)
- No crashes or freezes

---

### Hour 3: Control Integration (11:00 - 12:00)

**Launch control_ref_node (MAVROS disabled first):**
```bash
# Terminal 9: Control node
cd $THESIS_ROOT/ros2_ws
source install/setup.bash
ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=false

# Expected: Publishes to /control_ref/cmd_vel (test topic)
```

**Validation (MAVROS disabled):**
```bash
# Terminal 10: Monitor test topic
ros2 topic echo /control_ref/cmd_vel

# Verify reading from target selector
ros2 topic echo /thesis/target_selector/target_state

# Test: stand in front of camera
# Expected: target_state shows TRACKING
# Expected: cmd_vel shows velocities
```

**Enable MAVROS integration:**
```bash
# Stop control_ref_node (Ctrl+C in Terminal 9)

# Relaunch with MAVROS enabled
ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=true

# CRITICALLY monitor MAVROS topic
ros2 topic echo /mavros/setpoint_velocity/cmd_vel
```

**Safety checks:**
- [ ] Commands are reasonable magnitude (< 1.0 m/s for testing)
- [ ] Coordinate frame correct (body frame: x=forward, y=left, z=up)
- [ ] No commands when target lost
- [ ] Commands stop when control_ref_node stopped

**Test scenarios:**
1. **No person visible:** Should publish zero velocities or no commands
2. **Person detected:** Should publish non-zero commands
3. **Kill control_ref_node:** Commands should stop immediately

**Debugging:**
- If commands wrong frame: check control_ref_node coordinate transform
- If commands too large: check gain parameters
- If commands when no target: check target_state logic

---

### Hour 4: Analysis and Planning (12:00 - 13:00)

**Graceful shutdown:**
```bash
# Stop each node with Ctrl+C in order:
# 1. control_ref_node
# 2. target_selector_node
# 3. tracker_node
# 4. inference_client_node
# 5. Container inference (Ctrl+C in run_detection_zmq.sh terminal)
# 6. Camera capture
# 7. Camera init
# 8. MAVROS (last)
```

**Log collection:**
```bash
# On Pi5
cd $THESIS_ROOT
mkdir -p logs/2026-03-18_IST_session1

# Copy relevant logs if they exist
# ROS 2 logs typically in ~/.ros/log/

# Save terminal outputs (if captured)
# Save htop snapshots
# Save any error messages
```

**Session debrief:**

**What worked:**
-

**What didn't work:**
-

**Issues encountered:**
1. Issue: ___
   - Impact: ___
   - Potential fix: ___

2. Issue: ___
   - Impact: ___
   - Potential fix: ___

**Key learnings:**
-

**Thursday session planning:**

**Option A (if Hour 3 successful):**
- Add RViz visualization
- Test outdoor with props (if supervisors approve)
- Validate performance in real scenario

**Option B (if Hour 3 partial success):**
- Fix identified issues
- Re-test control integration
- Validate thoroughly before outdoor

**Option C (if Hour 3 failed):**
- Debug control_ref_node
- Simplify integration approach
- Re-test communication layer

**Chosen path:** _(decide with supervisors)_

---

## Equipment and Environment

**Hardware setup:**
- Raspberry Pi 5: ___
- Pixhawk 4: ___
- Camera: ___
- Battery: ___ (voltage, cells)
- Ethernet cable: ___
- Laptop: ___

**Network configuration:**
- Pi5 IP: ___
- Pixhawk IP: 192.168.1.1
- Connection type: UDP MAVLink
- Port: 14550

**Environment:**
- Location: ___
- Indoor/outdoor: ___
- Lighting: ___
- Space available: ___
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

**Issue 3:**
- Time: ___
- Phase: ___
- Description: ___
- Resolution: ___
- Status: ___

---

## Deliverables

- [ ] MAVROS connection validated
- [ ] Perception + MAVROS coexistence tested
- [ ] Control integration tested (unarmed)
- [ ] Issues documented
- [ ] Logs collected
- [ ] Thursday session plan drafted

---

## Supervisor Feedback

**From supervisors:**
-

**Questions asked:**
-

**Answers received:**
-

**Approvals granted:**
-

**Concerns raised:**
-

---

## End of Session Review

**Phase 1 (MAVROS) status:** _(success / partial / failed)_

**Phase 2 (Perception) status:** _(success / partial / failed)_

**Phase 3 (Control) status:** _(success / partial / failed)_

**Phase 4 (Analysis) status:** _(success / partial / failed)_

**Overall session outcome:** _(exceeded / met / below)_ expectations

**Time spent:** 4 hours

**Thursday readiness:** _(ready / needs work / major changes needed)_

**Critical takeaway:**
-

---

## Post-Session Actions

**Tonight/Wednesday:**
- [ ] Transfer logs to laptop
- [ ] Analyze issues in detail
- [ ] Implement fixes if simple
- [ ] Update Thursday plan
- [ ] Review with fresh mind

**Before Thursday:**
- [ ] Code fixes committed
- [ ] Thursday timeline finalized
- [ ] Equipment re-packed
- [ ] Mental preparation
