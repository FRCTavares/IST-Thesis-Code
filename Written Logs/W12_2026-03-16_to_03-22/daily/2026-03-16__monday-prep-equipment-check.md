# Daily Log — 2026-03-16 (Day 16) — Monday Preparation and Equipment Check

## Overview

**Last day before IST sessions begin**
**Focus:** Final preparation, equipment packing, readiness verification

---

## Goals for Today

### 1. Pack All Equipment for IST
- [ ] Raspberry Pi 5
- [ ] Camera (TEVS-AR0234) with mount
- [ ] Laptop + charger
- [ ] **Ethernet cable (Pi5 ↔ Pixhawk)** - CRITICAL
- [ ] Backup Ethernet cable
- [ ] Camera connection cables
- [ ] Notebook and pen
- [ ] Water, snacks

### 2. Review Tuesday Session Plan
- [ ] Read through Tuesday timeline (4 hours)
- [ ] Understand each phase's objectives
- [ ] Review MAVROS launch command
- [ ] Review safety checklist
- [ ] Identify potential issues

### 3. Verify Supervisor Answers
- [ ] Check all safety questions answered
- [ ] Confirm battery ready at IST
- [ ] Confirm Pixhawk location
- [ ] Confirm field access Tuesday
- [ ] Note any missing information

### 4. Final Code Verification
- [ ] Test control_ref_node compiles
- [ ] Verify MAVROS integration code looks correct
- [ ] Check git status (all committed)
- [ ] Git push to ensure backup

### 5. Equipment Checklist Confirmation
- [ ] Verify all items at home
- [ ] Test laptop battery
- [ ] Verify camera functional
- [ ] Pack non-essential items today

---

## Work Sessions

### Morning Session (2-3 hours)

**Equipment gathering and packing:**
- Collect all items from checklist
- Test Pi5 boots correctly
- Test camera connection
- Verify laptop SSH setup
- Pack bag/case for transport

**Tuesday plan review:**
- Hour 1: MAVROS connection (setup, launch, validate)
- Hour 2: Perception + MAVROS coexistence
- Hour 3: Control integration (unarmed)
- Hour 4: Analysis, documentation, Thursday planning

### Afternoon Session (2-3 hours)

**Code and documentation review:**
```bash
# Verify code compiles
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_bringup

# Check git status
git status
git log --oneline -5
git push

# Review key commands
# MAVROS: ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@
# Control: ros2 run thesis_bringup control_ref_node --ros-args -p enable_mavros:=true
```

**Supervisor communication check:**
- Review answers from `supervisor_questions.md`
- Confirm Tuesday logistics (time, location)
- Verify contact method if issues arise
- Note any last-minute changes

### Evening Session (1-2 hours)

**Final preparation:**
- [ ] Charge laptop fully
- [ ] Print or save offline:
  - MAVROS integration guide
  - Safety checklist
  - Tuesday session plan
- [ ] Set alarms for tomorrow
- [ ] Review what to do Monday (Day 17)

**Mental preparation:**
- First time with real hardware
- Things may not work first try
- Debugging is normal
- Learning is the priority
- Stay calm and systematic

---

## Expected Deliverables

- [ ] All equipment packed and ready
- [ ] Tuesday plan reviewed and understood
- [ ] Code verified and backed up
- [ ] Supervisor logistics confirmed
- [ ] Mentally prepared for integration week

---

## Notes and Issues

**Equipment status:**
-

**Supervisor confirmations:**
-

**Code verification:**
-

**Questions or concerns:**
-

---

## End of Day Review

**Completed:**
- [ ] Equipment packed
- [ ] Plan reviewed
- [ ] Code verified
- [ ] Logistics confirmed

**Time spent:** ___ hours

**Confidence level:** _(high / medium / low)_

**Ready for Monday?** _(yes / needs work)_

**Get good sleep tonight!**
