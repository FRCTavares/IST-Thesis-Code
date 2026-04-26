# T-32 Artefacts (2026-03-09 to 2026-03-15)

> Note (updated 2026-03-16): This artefact register contains historical references from T-32 execution. Current operations use `ros2 launch thesis_bringup camera_bringup.launch.py` and one-command orchestration via `tools/start_live_stack.sh`.

## Overview
This document tracks all deliverables, code, configurations, reports, and datasets produced during T-32.

**T-32 theme:** From "frozen baseline" to "camera-live system ready for outdoor control"

---

## Code and Configuration

### Live Camera Integration
- **Camera init node (historical):** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_init_node.py`
- **Camera capture node:** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py`
- **Inference client (live mode):** `ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py`

Current startup path:
- `ros2 launch thesis_bringup camera_bringup.launch.py`
- `./tools/start_live_stack.sh` (preferred)

**Status:** Complete (Day 08-10)

**Key parameters:**
- Device: `/dev/video0`
- Resolution: 640x640
- FPS target: ≥15 Hz sustained
- Capture mode: V4L2 blocking
- ZMQ port: 5556 (live camera service)

### Control Interface
- **Control reference node:** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py`
- **Control interface specification:** `Written Logs/docs/control/control_interface.md`

**Status:** Complete ground-only version (Day 11)

**Features implemented:**
- `/target` subscription with BEST_EFFORT QoS
- Internal pixel-to-normalized coordinate conversion
- Yaw and forward control (validated signs)
- Target validity checking (freshness, bounds, score, quality)
- Fail-safe zeroing on target loss
- Slew rate limiting for smooth commands
- Bounded outputs with configurable saturation
- Clean startup and shutdown

**Frozen run command:**
```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -p cmd_topic:=/control_ref/cmd_vel \
  -p img_w:=640.0 \
  -p img_h:=640.0 \
  -p desired_h_norm:=0.90
```

**Features pending:**
- MAVROS integration (Day 12)
- Lateral and vertical control
- Explicit target state flags
- Flight-tuned gains

### Lean Operational Mode Configuration
- **Lean mode specification:** `Written Logs/docs/lean_operational_mode.md`
- **Frozen startup sequence:** historical multi-terminal sequence (superseded operationally by one-command launcher)
- **Recording topics:** `/camera/fps`, `/detections`, `/timing`, `/target`
- **Excluded topics:** `/tracks`, `/timing_tracker` (profiling-only)

**Status:** Complete (Day 11)

**Validated performance (Day 10 baseline):**
- Duration: 598.229 s
- `/detections`: 16.644 Hz
- `/target`: 16.629 Hz
- `lat_ms` p95: 91.296 ms
- Temperature: 59.3°C, no throttling
- Memory: stable

### Documentation Updates (Day 11)
- **RUNBOOK.md:** Updated with lean vs profiling modes
- **README.md:** Added operational modes section
- **useful_commands.md:** Marked `/timing_tracker` as profiling-only

---

### Day 11 Control Integration Milestone

**Key achievement:** First ground-only perception-to-control bridge working end-to-end

**End-to-end validated path:**
```
camera → inference → detections → tracker → tracks → target selector → /target → control_ref_node → /control_ref/cmd_vel
```

**Technical discoveries:**
- `/target` uses pixel coordinates (0-640), not normalized [0,1]
- QoS must be BEST_EFFORT to match target selector
- Internal normalization in control node avoids upstream redesign

**Validation results:**
- ✓ Yaw control sign correct (left → negative, right → positive)
- ✓ Forward control sign correct (far → positive, close → negative)
- ✓ Target validity logic working (freshness, bounds, score, quality)
- ✓ Fail-safe zeroing on target loss
- ✓ Slew rate limiting observed (0.0 → -0.03 → -0.06 → -0.09 → -0.1)
- ✓ Command saturation at configured limits
- ✓ Clean startup and shutdown

**What remains for control:**
- MAVROS topic integration (Day 12)
- Systematic loss/reacquisition testing (Day 13)
- Outdoor field validation (Day 14-15)

---

### Launch Files
- **Full system launch:** `ros2_ws/src/thesis_bringup/launch/full_system_live.launch.py`
- **Outdoor test launch:** `ros2_ws/src/thesis_bringup/launch/outdoor_test.launch.py`
- **Control demo launch:** `ros2_ws/src/thesis_bringup/launch/control_demo.launch.py`

**Status:** *(To be created during T-32)*

---

## Datasets and Test Runs

### Live Camera Validation Runs
- **Day 09 validation:** `bags/live_camera/2026-03-09__camera_validation/`
- **Day 10 stability test:** `bags/live_camera/2026-03-10__stability_5min/`

**Metrics to capture:**
- FPS over time
- Latency breakdown (capture → inference → tracker → target selector)
- Frame drops
- CPU/memory usage

### Outdoor Test Runs
- **Day 11 first outdoor:** `bags/outdoor/2026-03-11__first_outdoor_test/`
- **Day 12 protocol runs:** `bags/outdoor/2026-03-12__protocol_scenarios/`
  - Scenario 1: *(description)*
  - Scenario 2: *(description)*
  - Scenario 3: *(description)*
  - Scenario 4: *(description)*
  - Scenario 5: *(description)*
  - Scenario 6: *(description)*

**Metrics to capture:**
- Detection rate vs. distance
- Tracking continuity with occlusions
- ID switch count
- Reacquisition time after loss
- Lighting effects (time of day)

### Control Validation Runs
- **Day 13 ground demo:** `bags/control/2026-03-13__ground_control_demo/`
- **Day 14 safety tests:** `bags/control/2026-03-14__safety_validation/`

**Metrics to capture:**
- Control update rate
- Command latency (perception → control output)
- Safety mechanism trigger times
- Loss behavior validation

---

## Reports and Analysis

### Timing Reports
- **Live camera latency:** `reports/timing/T-32_live_camera_latency.md`
  - Full breakdown: capture, serialization, inference, deserialization, tracking, target selection
  - Comparison to file-based baseline from T-34-T-33
  - CDF plots for each stage

**Status:** *(Not started / In progress / Complete)*

### Outdoor Test Reports
- **First outdoor test:** `reports/outdoor/T-32_first_outdoor_test.md`
  - Initial observations and issues
  - Detection quality assessment
  - Tracking performance in real-world conditions

- **Protocol execution:** `reports/outdoor/T-32_tennis_court_scenarios.md`
  - All 6 scenarios with quantified metrics
  - Success criteria evaluation
  - Comparison to indoor baseline
  - Thesis-ready figures and tables

**Status:** *(Not started / In progress / Complete)*

### Control Reports
- **Control integration:** `reports/control/T-32_control_integration.md`
  - MAVROS interface specification
  - Control message flow validation
  - Ground-based control demo results

- **Safety validation:** `reports/control/T-32_safety_validation.md`
  - All safety mechanisms tested
  - Failure mode handling
  - Emergency procedures validated

**Status:** *(Not started / In progress / Complete)*

### System Readiness Assessment
- **Flight test readiness:** `reports/system/T-32_flight_readiness_assessment.md`
  - GO/NO-GO checklist evaluation
  - System stability summary
  - Outdoor performance summary
  - Safety validation summary
  - Remaining risks and mitigations
  - T-31 flight test plan

**Status:** *(Not started / In progress / Complete)*

---

## Documentation

### Procedures and Checklists
- **Outdoor test protocol:** `docs/outdoor_test_protocol.md`
  - 6 tennis court scenarios defined
  - Success criteria for each scenario
  - Test execution procedure
  - Data collection checklist

- **Pre-flight checklist:** `docs/preflight_checklist.md`
  - Hardware checks (battery, connections, camera, autopilot)
  - Software checks (ROS nodes, MAVROS, perception pipeline)
  - Environment checks (lighting, space, personnel)
  - Safety checks (geofence, emergency stop, loss behavior)
  - GO/NO-GO decision criteria

**Status:** *(Not started / In progress / Complete)*

### Technical Documentation
- **MAVROS interface spec:** `docs/mavros_interface.md`
  - Topic mappings (perception → control commands)
  - Coordinate frame conventions
  - Safety bounds implementation
  - Command rate and timing requirements

- **Safety mechanisms:** `docs/safety_mechanisms.md`
  - Loss-of-target behavior modes
  - Safety bounds (velocity, altitude, geofence)
  - Emergency stop procedure
  - Failsafe conditions

**Status:** *(Not started / In progress / Complete)*

---

## Tools and Scripts

### Test Execution
- **Outdoor test runner:** `tools/run_outdoor_test.sh`
  - Launches full system with outdoor configuration
  - Starts bag recording with appropriate topics
  - Monitors system health during test
  - Saves test metadata

- **Control demo runner:** `tools/run_control_demo.sh`
  - Ground-based control validation
  - Safety mechanism testing
  - MAVROS interface validation

**Status:** *(Not started / In progress / Complete)*

### Analysis Scripts
- **Live camera timing analysis:** `tools/analyse_live_camera_timing.py`
  - Extends existing timing analysis for live camera
  - Compares to file-based baseline
  - Generates timing breakdown plots

- **Outdoor performance analysis:** `tools/analyse_outdoor_performance.py`
  - Detection rate vs. distance/lighting
  - Tracking metrics in real-world conditions
  - Scenario-specific analysis

**Status:** *(Not started / In progress / Complete)*

---

## Figures

### Live Camera
- FPS over time: `figures/timing/T-32_live_camera_fps_over_time.png`
- Latency breakdown: `figures/timing/T-32_live_camera_latency_breakdown.png`
- Latency CDF comparison: `figures/timing/T-32_live_vs_file_latency_cdf.png`

### Outdoor Tests
- Detection rate vs. distance: `figures/outdoor/T-32_detection_vs_distance.png`
- Tracking continuity: `figures/outdoor/T-32_tracking_continuity.png`
- Reacquisition time histogram: `figures/outdoor/T-32_reacquisition_histogram.png`
- ID switch comparison: `figures/outdoor/T-32_id_switches.png`

### Control
- Control update rate: `figures/control/T-32_control_update_rate.png`
- Command latency: `figures/control/T-32_command_latency.png`
- Safety trigger events: `figures/control/T-32_safety_events.png`

---

## Configuration Snapshots

### System Configuration T-32
```yaml
# To be frozen after validation runs
camera:
  device: /dev/video0
  resolution: [width, height]
  fps_target: 15
  format: (to specify)

inference:
  hef: yolov6n_hailo8.hef
  confidence_threshold: (frozen value)
  nms_threshold: (frozen value)

tracker:
  type: (SORT / OC-SORT / ByteTrack)
  parameters: (frozen from T-33)

target_selector:
  state_machine: enabled
  scoring: multi-feature
  parameters: (frozen from T-33)

control:
  update_rate: 30
  prediction_horizon_ms: (200-500)
  loss_behavior: (hold / ramp / neutral)
  safety_bounds:
    max_velocity: (to define)
    max_altitude: (to define)
    geofence: (to define)
```

---

## Key Decisions Implemented

### Live Camera Configuration
**Decision:** *(Final camera settings after Day 09-10 validation)*  
**Rationale:** *(Based on FPS, latency, and stability results)*

### Outdoor Test Scenarios
**Decision:** *(Final 6 scenarios after Day 11 exploration)*  
**Rationale:** *(Adapted based on real-world constraints)*

### Control Safety Strategy
**Decision:** *(Safety bounds and loss behavior after Day 14 validation)*  
**Rationale:** *(Balance between demo effectiveness and flight safety)*

---

## Notes

- Live camera integration completed on Day 08 (2026-03-08) of T-33
- This week focuses on outdoor validation and control readiness
- All deliverables must be thesis-ready (reproducible, documented, figures)
- Safety is priority #1 before any flight testing
