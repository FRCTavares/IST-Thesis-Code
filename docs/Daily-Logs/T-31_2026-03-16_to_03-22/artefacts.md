# T-31 Artefacts (2026-03-16 to 2026-03-22)

## Overview
This document tracks all deliverables, code, configurations, reports, and datasets produced during T-31.

**T-31 theme:** "Integration Week" — First MAVROS hardware integration and outdoor validation

---

## Code and Configuration

### Live Stack Integration and Operations (Days 16-17)
- **One-command live startup script:** `tools/start_live_stack.sh`
- **Inference client timing instrumentation:** `ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py`
- **Tracker timing publishers:** `ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py`
- **Target timing and context fallback:** `ros2_ws/src/thesis_target_selector/thesis_target_selector/thesis_target_selector.py`
- **Container timing fields:** `infer_service/detection_zmq.py`

**Status:** In progress (operationally validated, further optimization pending)

**Notable updates:**
- Dashboard/no-dashboard startup modes and optional component toggles added.
- No-dashboard mode disables dashboard transmission path.
- Startup process checks and stop cleanup improved.

### MAVROS Integration
- **Control node with MAVROS:** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py`
- **MAVROS integration guide:** `docs/written_logs/docs/mavros_integration_guide.md`

**Status:** *(Coded T-32 / Validated T-31 / Has issues)*

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
- **Safety checklist:** `docs/written_logs/T-32_2026-03-09_to_03-15/supervisor_questions.md`
- **IST session plans:** Documented in daily logs

**Status:** *(Complete / In progress)*

---

## Datasets and Test Runs

### Tuesday IST Session (Day 18)
- **Diagnostic bags:** `artifacts/bags/ist/2026-03-18__session1_mavros_integration/`

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
- **Session bags:** `artifacts/bags/ist/2026-03-20__session2_outdoor_validation/`
  OR `artifacts/bags/ist/2026-03-20__session2_debug/`

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

### Timing Ablation and Bottleneck Analysis (Day 17)
- **Bottleneck summary report:** `artifacts/reports/timing/2026-03-17__live-bottlenecks-summary.md`
- **Live baseline stats:** `artifacts/reports/timing/baseline_current_live.json`
- **Post target-context-fix stats:** `artifacts/reports/timing/post_target_context_fix_live.json`
- **Ablation stats:**
  - `artifacts/reports/timing/r2_inference_tracker_target.json`
  - `artifacts/reports/timing/r3_plus_dashboard_bridge.json`
  - `artifacts/reports/timing/r4_plus_web_video.json`
  - `artifacts/reports/timing/r5_plus_rosbag.json`

**Utilities added:**
- `tools/check_live_timing_invariants.py`
- `tools/collect_live_timing_stats.py`

### MAVROS Integration Report
- **Tuesday session report:** `artifacts/reports/system/T-31_tuesday_mavros_integration.md`

**Contents:**
- Connection procedure and issues
- Setpoint validation results
- Control sign verification
- Integration issues encountered
- Lessons learned

### Thursday Session Report
- **Session report:** `artifacts/reports/system/T-31_thursday_session.md`

**Contents:**
- Session goals and outcomes
- Outdoor performance (if applicable)
- Debug results (if applicable)
- Field operation lessons

### T-31 Summary
- **Final report:** `artifacts/reports/system/T-31_integration_week_summary.md`

**Contents:**
- Overall integration success level
- Hardware setup validated
- MAVROS connection procedure frozen
- Outdoor operation characterized
- Next steps identified

---

## Figures and Plots

### MAVROS Integration Validation
- Setpoint rate over time: `artifacts/figures/control/T-31_setpoint_rate.png`
- Command values over time: `artifacts/figures/control/T-31_command_values.png`
- Target → setpoint correlation: `artifacts/figures/control/T-31_target_setpoint_correlation.png`

### Outdoor Performance (if applicable)
- Detection rate vs distance: `artifacts/figures/outdoor/T-31_detection_vs_distance.png`
- FPS over time outdoor: `artifacts/figures/outdoor/T-31_outdoor_fps.png`
- Outdoor vs indoor latency: `artifacts/figures/outdoor/T-31_outdoor_vs_indoor_latency.png`

---

## Documentation Updates

### Updated Documents
- **Control interface:** `docs/written_logs/docs/control/control_interface.md`
  - MAVROS integration details
  - Validated connection procedure
  - Safety procedures confirmed

- **MAVROS guide:** `docs/written_logs/docs/mavros_integration_guide.md`
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

### Immediate (Post-T-31)
- [ ] *(To be determined based on T-31 results)*

### Short-term (T-30)
- [ ] *(To be determined)*

### Blockers Identified
- [ ] *(To be filled)*

---

## Status Summary

**Tuesday Session:** *(Success / Partial / Issues)*

**Thursday Session:** *(Success / Partial / Not attempted)*

**Overall T-31:** *(Successful integration / Needs more work / Blocked)*

**Ready for next phase:** *(Yes / No / Conditional)*

---

**Last updated:** *(Fill in at end of week)*  
**Review status:** *(Draft / In progress / Complete)*
