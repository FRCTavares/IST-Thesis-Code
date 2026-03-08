# Daily Log — 2026-03-13 — Control Interface Integration and Ground Control Demo

## Goal

Integrate the control reference node with MAVROS and validate the full control pipeline on the ground (no flight).

**Target outcome:**
- `control_ref_node` outputs MAVROS setpoint messages
- Ground-based control validation confirms message flow and timing
- MAVROS interface fully documented (topics, frames, safety bounds)
- Control demo script enables repeatable ground testing
- Control integration report documents performance and readiness

---

## Context

| Key | Value |
|-----|-------|
| Autopilot | Pixhawk 4 running ArduPilot |
| ROS bridge | MAVROS2 (installed and configured) |
| Control inputs | `/target` topic from target_selector_node |
| Control outputs | MAVROS setpoint topics (position, velocity, or attitude) |
| Control rate | 30 Hz target |
| Test type | Ground validation only (no motors armed, no flight) |
| Safety priority | All safety mechanisms must be implemented before flight |

---

## Work Plan

### A) MAVROS Setup and Validation

Ensure MAVROS is connected to Pixhawk and topics are flowing.

**Tasks:**
- [ ] Connect Pixhow 4 to Pi 5 via USB or UART
- [ ] Launch MAVROS: `ros2 launch mavros apm.launch.py fcu_url:=<connection_string>`
- [ ] Verify MAVROS connection: `ros2 topic list | grep mavros`
- [ ] Check key topics:
  - `/mavros/state` (FCU connection status)
  - `/mavros/local_position/pose` (position feedback)
  - `/mavros/setpoint_position/local` or `/setpoint_velocity/cmd_vel_unstamped` (command topics)
- [ ] Confirm GPS status: `/mavros/global_position/global`
- [ ] Test MAVROS publishing: manually publish a setpoint, check it's received
- [ ] Document MAVROS configuration: connection, topics, message types

**Deliverables:**
- MAVROS connection validated
- MAVROS configuration documented: `docs/mavros_interface.md`

---

### B) Control Reference Node MAVROS Integration

Modify `control_ref_node` to output MAVROS setpoint messages.

**Tasks:**
- [ ] Choose control mode:
  - Position setpoints: `/mavros/setpoint_position/local` (easier, safer for first tests)
  - Velocity setpoints: `/mavros/setpoint_velocity/cmd_vel_unstamped` (better for dynamic control)
  - Attitude setpoints: `/mavros/setpoint_raw/attitude` (most direct, but requires careful tuning)
  - **Recommendation:** Start with velocity setpoints for target-relative control
- [ ] Implement coordinate frame transforms:
  - `/target` outputs: `target_bbox_cx`, `target_bbox_cy` (normalized image coords)
  - MAVROS expects: body frame or local frame (NED or ENU)
  - Define transform: image coords → desired control velocity
- [ ] Implement control law (simple proportional control for now):
  - Lateral error: `ex = target_cx - 0.5` (target off-center)
  - Forward/backward control based on bbox size or distance estimate
  - Yaw control to keep target centered
  - Example: `vel_y = K_lat * ex`, `vel_x = K_fwd * (desired_size - bbox_area)`
- [ ] Implement 30 Hz control loop:
  - Subscribe to `/target` at ~30 Hz
  - Publish setpoints to MAVROS at 30 Hz
  - Use latest target data with prediction if needed
- [ ] Add target validity check:
  - Only send control commands if target is visible and locked
  - If target lost: transition to safety behavior (next section)

**Deliverables:**
- Updated `control_ref_node.py` with MAVROS publishing
- Control law documented: `docs/control_law.md`
- Configuration: `config/control_ref_frozen.yaml`

---

### C) Safety Mechanisms Implementation

Implement all critical safety mechanisms before any flight testing.

**Tasks:**
- [ ] **Velocity limits:** Clamp all setpoint velocities to safe max
  - Max lateral velocity: e.g., 2 m/s
  - Max forward velocity: e.g., 3 m/s
  - Max vertical velocity: e.g., 1 m/s (if altitude control used)
  - Max yaw rate: e.g., 30 deg/s
- [ ] **Loss-of-target behavior:** Define what happens when target is lost
  - Option 1: HOLD (maintain last known position/velocity)
  - Option 2: RAMP DOWN (gradually reduce velocity to 0)
  - Option 3: RETURN (activate RTL mode)
  - Option 4: LAND (initiate landing)
  - **Recommendation for first tests:** HOLD for X seconds, then RAMP DOWN to 0
- [ ] **Timeout logic:** If target lost for >N seconds, trigger failsafe
  - Configurable timeout: e.g., 3 seconds
  - Log event and trigger safety behavior
- [ ] **Emergency stop:** Ability to immediately stop control output
  - Subscribe to emergency topic or keyboard command
  - On trigger: send zero velocity or switch to manual mode
- [ ] **Geofence (future):** Define allowed flight area
  - For now: simple max distance from takeoff point
  - Later: full geofence with GPS coordinates
- [ ] **Mode awareness:** Only send setpoints if FCU is in right mode
  - Check `/mavros/state` for current mode
  - Only command if in GUIDED or similar mode

**Deliverables:**
- Safety mechanisms implemented in `control_ref_node.py`
- Safety configuration: `config/safety_bounds.yaml`
- Safety documentation: `docs/safety_mechanisms.md`

---

### D) Ground Control Validation (No Flight)

Test the full control pipeline on the ground without arming motors.

**Tasks:**
- [ ] Launch full system: camera → detections → tracks → target → control → MAVROS
- [ ] Use outdoor test bags or live person as target input
- [ ] Monitor control outputs:
  - Check `/mavros/setpoint_*` topics: are commands being sent at 30 Hz?
  - Verify setpoint values are reasonable (not NaN, not extreme)
  - Check velocity limits are respected
- [ ] Test loss-of-target behavior:
  - Simulate target loss (cover camera or person leaves frame)
  - Verify timeout and safety behavior trigger correctly
  - Check logs: are events recorded?
- [ ] Test emergency stop:
  - Trigger emergency while control running
  - Verify control output stops immediately
- [ ] Record bag with full control pipeline: `bags/control/2026-03-13__ground_control_demo/`
- [ ] Measure control timing:
  - Perception latency (camera → `/target`)
  - Control latency (` /target` → MAVROS setpoint)
  - Total latency: camera → MAVROS setpoint
  - Update rate: actual Hz of setpoint publishing

**Deliverables:**
- Ground control demo bag: `bags/control/2026-03-13__ground_control_demo/`
- Control timing analysis: `reports/control/W11_control_timing.md`
- Qualitative validation notes: does control respond sensibly?

---

### E) Control Integration Report

Document the control interface and ground validation results.

**Tasks:**
- [ ] Write control integration report: `reports/control/W11_control_integration.md`
- [ ] Include:
  - MAVROS interface specification
  - Control law and gains used
  - Safety mechanisms implemented
  - Ground validation results (timing, behavior)
  - Plots: control update rate, latency breakdown
  - Issues found and resolutions
- [ ] Document control parameters that were frozen
- [ ] Recommend any tuning needed before flight

**Deliverables:**
- Control integration report: `reports/control/W11_control_integration.md`
- Control update rate plot: `figures/control/W11_control_update_rate.png`
- Control latency plot: `figures/control/W11_control_latency.png`

---

### F) Control Demo Script

Create a reusable script for ground control testing.

**Tasks:**
- [ ] Write `tools/run_control_demo.sh`:
  - Launch MAVROS
  - Launch perception pipeline
  - Launch control_ref_node
  - Start bag recording with control topics
  - Display monitoring info (FPS, target status, control rate)
- [ ] Test script: run full demo from scratch
- [ ] Document usage in script header

**Deliverables:**
- Control demo script: `tools/run_control_demo.sh`
- Usage documented

---

## Expected Outcomes

By end of Day 13, you should have:

1. **MAVROS integration complete**
   - `control_ref_node` sends setpoints to MAVROS
   - Ground validation confirms message flow

2. **Safety mechanisms implemented**
   - Velocity limits enforced
   - Loss-of-target behavior defined and tested
   - Emergency stop functional

3. **Control pipeline validated on ground**
   - 30 Hz control rate achieved
   - Timing and latency documented
   - Behavior is sensible and safe

4. **Thesis-ready control report**
   - MAVROS interface documented
   - Control performance quantified
   - Ground validation logged

5. **Confidence for flight test planning**
   - Control is ready for flight (pending Day 14 safety validation)
   - Know what to expect during first flight test

---

## Issues and Risks

### Potential Issues
- MAVROS connection problems (USB/UART, baud rate, permissions)
- Coordinate frame confusion (image coords → body frame → MAVROS frame)
- Control loop timing issues (not achieving 30 Hz)
- Safety mechanisms not triggering correctly
- Pixhawk not accepting setpoints (mode issue, safety checks)

### Mitigation Strategies
- If MAVROS issues: test MAVROS first in isolation, check logs
- If coordinate frame issues: test with simple manual setpoints first
- If timing issues: profile control node, optimize bottlenecks
- If safety issues: add logging and test each mechanism in isolation
- If Pixhawk rejects commands: check mode, parameters, safety switches

---

## Notes

- Ground validation only: motors should NOT be armed today
- This is integration day: connect perception to control
- Safety first: all safety mechanisms must work before flight
- Control doesn't need to be perfect, just safe and functional
- Fine-tuning of control gains can wait until actual flight tests
- Focus today is on pipeline integration and safety validation, not performance optimization
- If control pipeline works today, Day 14 focuses on comprehensive safety testing
