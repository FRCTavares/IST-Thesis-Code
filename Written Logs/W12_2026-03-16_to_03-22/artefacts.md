# Week 12 Artefacts (2026-03-16 to 2026-03-22)

## Overview
This document tracks all deliverables, code, configurations, reports, and datasets produced during Week 12.

**Week 12 theme:** "Integration Week" — First MAVROS hardware integration and outdoor validation

---

## Code and Configuration

### MAVROS Integration
- **Control node with MAVROS:** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py`
- **MAVROS integration guide:** `Written Logs/docs/mavros_integration_guide.md`

**Status:** *(Coded W11 / Validated W12 / Has issues)*

**Features implemented:**
- MAVROS velocity setpoint publisher (`/mavros/setpoint_velocity/cmd_vel`)
- `enable_mavros` safety parameter
- Conditional publishing (test vs MAVROS output)
- Ethernet connection support

**MAVROS launch command:**
```bash
ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@
```

**Run command:**
```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -p enable_mavros:=true \
  -p cmd_topic:=/mavros/setpoint_velocity/cmd_vel \
  -p img_w:=640.0 \
  -p img_h:=640.0 \
  -p desired_h_norm:=0.25
```

### Field Operation Procedures
- **Safety checklist:** `Written Logs/W11_2026-03-09_to_03-15/supervisor_questions.md`
- **IST session plans:** Documented in daily logs

**Status:** *(Complete / In progress)*

---

## Datasets and Test Runs

### Tuesday IST Session (Day 18)
- **Diagnostic bags:** `bags/ist/2026-03-18__session1_mavros_integration/`

**Recorded topics:**
- `/camera/fps`
- `/detections`
- `/timing`
- `/target`
- `/mavros/state`
- `/mavros/setpoint_velocity/cmd_vel`

**Key metrics:**
- MAVROS connection status
- Setpoint rate (target 30 Hz)
- Perception → control latency
- System stability

### Thursday IST Session (Day 20)
- **Session bags:** `bags/ist/2026-03-20__session2_outdoor_validation/`
  OR `bags/ist/2026-03-20__session2_debug/`

**Depends on Tuesday results:**
- Option A: Debug and integration bags
- Option B: Outdoor perception bags
- Option C: Integrated outdoor ground test bags

**Key metrics:**
- Outdoor detection performance (if applicable)
- Distance vs detection rate (if applicable)
- Integration stability (if debugging)

---

## Reports and Analysis

### MAVROS Integration Report
- **Tuesday session report:** `reports/system/W12_tuesday_mavros_integration.md`

**Contents:**
- Connection procedure and issues
- Setpoint validation results
- Control sign verification
- Integration issues encountered
- Lessons learned

### Thursday Session Report
- **Session report:** `reports/system/W12_thursday_session.md`

**Contents:**
- Session goals and outcomes
- Outdoor performance (if applicable)
- Debug results (if applicable)
- Field operation lessons

### Week 12 Summary
- **Final report:** `reports/system/W12_integration_week_summary.md`

**Contents:**
- Overall integration success level
- Hardware setup validated
- MAVROS connection procedure frozen
- Outdoor operation characterized
- Next steps identified

---

## Figures and Plots

### MAVROS Integration Validation
- Setpoint rate over time: `figures/control/W12_setpoint_rate.png`
- Command values over time: `figures/control/W12_command_values.png`
- Target → setpoint correlation: `figures/control/W12_target_setpoint_correlation.png`

### Outdoor Performance (if applicable)
- Detection rate vs distance: `figures/outdoor/W12_detection_vs_distance.png`
- FPS over time outdoor: `figures/outdoor/W12_outdoor_fps.png`
- Outdoor vs indoor latency: `figures/outdoor/W12_outdoor_vs_indoor_latency.png`

---

## Documentation Updates

### Updated Documents
- **Control interface:** `Written Logs/docs/control_interface.md`
  - MAVROS integration details
  - Validated connection procedure
  - Safety procedures confirmed

- **MAVROS guide:** `Written Logs/docs/mavros_integration_guide.md`
  - Real hardware validation notes
  - Troubleshooting updates
  - Lessons learned section

### New Documents Created
- **Field operation checklist:** `docs/field_operation_checklist.md` *(if created)*
- **IST setup procedure:** `docs/ist_setup_procedure.md` *(if created)*

---

## Configuration and Parameters

### Validated Configuration
*(To be filled after Tuesday session)*

**MAVROS connection:**
- Connection type: Ethernet (UDP MAVLink)
- Pixhawk IP: *(to be confirmed)*
- Port: 14550 (MAVLink standard)
- Connection status: *(success / issues)*

**Control parameters:**
- Gains: *(validated values)*
- Command limits: *(validated values)*
- Safety bounds: *(confirmed)*

**System performance:**
- FPS achieved: *(value)*
- Setpoint rate achieved: *(value)*
- Latency: *(value)*

---

## Lessons Learned

### Integration Challenges
*(To be filled during week)*

**MAVROS connection:**
- *(issues encountered and solutions)*

**Hardware setup:**
- *(setup challenges and workarounds)*

**Perception coexistence:**
- *(resource conflicts and resolutions)*

### Outdoor Operation
*(To be filled if outdoor testing happens)*

**Environmental factors:**
- *(lighting, distance, occlusions)*

**System behavior:**
- *(performance differences vs indoor)*

### Field Operations
**Logistics:**
- *(equipment transport, setup time)*

**Time management:**
- *(what took longer than expected)*

**Preparation gaps:**
- *(what should have been prepared better)*

---

## Next Steps

### Immediate (Post-W12)
- [ ] *(To be determined based on W12 results)*

### Short-term (W13)
- [ ] *(To be determined)*

### Blockers Identified
- [ ] *(To be filled)*

---

## Status Summary

**Tuesday Session:** *(Success / Partial / Issues)*

**Thursday Session:** *(Success / Partial / Not attempted)*

**Overall W12:** *(Successful integration / Needs more work / Blocked)*

**Ready for next phase:** *(Yes / No / Conditional)*

---

**Last updated:** *(Fill in at end of week)*  
**Review status:** *(Draft / In progress / Complete)*
