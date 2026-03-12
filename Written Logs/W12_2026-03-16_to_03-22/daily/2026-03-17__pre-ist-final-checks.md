# Daily Log — 2026-03-17 (Day 17) — Pre-IST Final Checks

## Overview

**Day before first IST session**
**Focus:** Final verification, transport preparation, readiness confirmation

---

## Goals for Today

### 1. Final Equipment Verification
- [ ] Test Pi5 boots correctly
- [ ] Test camera capture (local test if possible)
- [ ] Verify Ethernet cable functionality
- [ ] Check laptop SSH keys/setup
- [ ] Confirm all items in transport bag

### 2. Final Code Review
- [ ] Re-read MAVROS integration guide
- [ ] Review safety procedures
- [ ] Understand coordinate frames (body frame)
- [ ] Review /mavros/state checking
- [ ] Test code compilation once more

### 3. Session Timeline Finalization
- [ ] Print/save Tuesday timeline
- [ ] Prepare notebook with sections:
  - Phase checklists
  - Command log
  - Issue tracking
  - Notes section
- [ ] Prepare offline resources

### 4. Mental and Physical Preparation
- [ ] Get sleep schedule right
- [ ] Prepare food/water for tomorrow
- [ ] Plan transport method
- [ ] Estimate travel time
- [ ] Set alarms

---

## Work Sessions

### Morning Session (2-3 hours)

**Equipment and code verification:**

```bash
# Test Pi5 boot
ssh pi5
uptime

# Test camera (if setup allows)
cd $THESIS_ROOT/infer_service
python3 camera/camera_test.py  # If you have test script

# Test code compilation
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_bringup thesis_target_selector

# Verify MAVROS commands known
echo "ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@" > /tmp/mavros_cmd.txt
echo "ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=true" >> /tmp/mavros_cmd.txt
cat /tmp/mavros_cmd.txt
```

**Key commands to remember:**
```bash
# MAVROS state check
ros2 topic echo /mavros/state

# Safety monitor
ros2 topic echo /mavros/setpoint_velocity/cmd_vel

# Target selector state
ros2 topic echo /thesis/target_selector/target_state
```

### Afternoon Session (2-3 hours)

**Session preparation and documentation:**

Create notebook sections:
1. **Phase 1 (Hour 1): MAVROS Connection**
   - [ ] Connect Ethernet
   - [ ] Launch MAVROS
   - [ ] Verify /mavros/state
   - [ ] Check Pixhawk responds
   - Issues/notes:

2. **Phase 2 (Hour 2): Perception Coexistence**
   - [ ] Launch perception
   - [ ] Monitor CPU/performance
   - [ ] Verify MAVROS stable
   - Issues/notes:

3. **Phase 3 (Hour 3): Control Integration**
   - [ ] Launch control_ref_node (MAVROS disabled)
   - [ ] Verify publishing works
   - [ ] Enable MAVROS parameter
   - [ ] Monitor /mavros/setpoint_velocity/cmd_vel
   - Issues/notes:

4. **Phase 4 (Hour 4): Analysis & Planning**
   - Summary
   - Issues encountered
   - Thursday planning

**Review safety priorities:**
- Never arm without supervisor approval
- Props removed for initial testing
- RC transmitter override ready
- Monitor all topics continuously
- Stop immediately if anything unexpected

### Evening Session (1-2 hours)

**Final preparation:**
- [ ] Pack laptop, chargers
- [ ] Pack Pi5, camera, Ethernet cables
- [ ] Pack water bottle, snacks
- [ ] Pack notebook, pens
- [ ] Pack offline docs (printed or PDF)

**Transport planning:**
- Departure time: ___
- Travel time: ___ minutes
- Arrival target: ___ (15-30 min before session)
- Equipment transport method: ___

**Tomorrow's schedule:**
- Wake up: ___
- Depart: ___
- Arrive IST: ___
- Session start: ___
- Session end: ___

**Mental checklist:**
- This is a learning experience
- Debugging is expected
- Supervisors are there to help
- Safety is paramount
- Take notes continuously
- Ask questions when unsure

---

## Expected Deliverables

- [ ] Equipment verified and packed
- [ ] Code tested and ready
- [ ] Notebook prepared with phase sections
- [ ] Commands memorized/saved
- [ ] Transport planned
- [ ] Physically and mentally ready

---

## Notes and Issues

**Equipment verification:**
-

**Code verification:**
-

**Transport plan:**
-

**Questions to ask supervisors tomorrow:**
-

---

## End of Day Review

**Completed:**
- [ ] Equipment ready
- [ ] Code ready
- [ ] Documentation ready
- [ ] Notebook prepared
- [ ] Transport planned

**Time spent:** ___ hours

**Confidence level:** _(high / medium / low)_

**Ready for Tuesday?** _(yes / needs work)_

**Tomorrow is the big day. Get good sleep.**
