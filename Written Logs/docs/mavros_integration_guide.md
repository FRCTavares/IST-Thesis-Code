# MAVROS Integration Guide

**Status:** Learning phase - untested until W12 hardware access

**Purpose:** Integrate perception pipeline with ArduPilot autopilot via MAVROS for velocity-based target tracking.

---

## Quick Reference

### Key MAVROS Topics

| Topic | Message Type | Purpose | Status |
|-------|--------------|---------|--------|
| `/mavros/state` | `mavros_msgs/State` | FCU connection, armed, mode | Monitor only |
| `/mavros/setpoint_velocity/cmd_vel` | `geometry_msgs/Twist` | Velocity setpoints (body frame) | **Target for control** |
| `/mavros/local_position/pose` | `geometry_msgs/PoseStamped` | Current position feedback | Future use |
| `/mavros/local_position/velocity_body` | `geometry_msgs/TwistStamped` | Current velocity | Future use |
| `/mavros/rc/in` | `mavros_msgs/RCIn` | RC receiver inputs | Safety monitor |

### Coordinate Frames

**Body Frame (for velocity control):**
- `linear.x` = forward velocity (m/s)
- `linear.y` = left velocity (m/s) 
- `linear.z` = up velocity (m/s)
- `angular.z` = yaw rate (rad/s, CCW positive)

**Our mapping:**
- Yaw control → `angular.z`
- Forward control → `linear.x`
- Lateral control → `linear.y` (currently disabled)

---

## MAVROS Installation and Setup

### Check if MAVROS is installed
```bash
ros2 pkg list | grep mavros
```

### Install MAVROS for ROS 2 Jazzy (if needed)
```bash
sudo apt install ros-jazzy-mavros ros-jazzy-mavros-extras
```

### Install GeographicLib datasets (required for GPS)
```bash
wget https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh
sudo bash ./install_geographiclib_datasets.sh
```

---

## Launching MAVROS

### For Ethernet Connection (CONFIRMED FOR YOUR SETUP) ✅

**Primary command (adjust IP if different):**
```bash
ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@
```

**Alternative (listens on all network interfaces):**
```bash
ros2 launch mavros apm.launch fcu_url:=udp://:14550@
```

**Notes:**
- Pixhawk default IP is typically `192.168.1.1`, but verify with your setup
- Port `14550` is standard MAVLink port
- Ethernet connection uses UDP MAVLink protocol
- May need to check Pi5 network interface: `ip addr`

### For Serial Connection (NOT YOUR SETUP - For Reference Only)
```bash
ros2 launch mavros apm.launch fcu_url:=/dev/ttyACM0:57600
```

**Notes:**
- `/dev/ttyACM0` might be `/dev/ttyUSB0` or different - check with `ls /dev/tty*`
- Baud rate `57600` is ArduPilot default, might need `115200`
- Add `gcs_url:=udp://@` if you want ground station connection

### For UDP Connection (if using MAVProxy or simulator)
```bash
ros2 launch mavros apm.launch fcu_url:=udp://:14550@127.0.0.1:14555
```

### Verify MAVROS Connection
```bash
# Check if topics appear
ros2 topic list | grep mavros

# Monitor connection state
ros2 topic echo /mavros/state

# You should see:
# connected: True
# armed: False
# mode: "STABILIZE" (or similar)
```

---

## Control Node MAVROS Integration

### Current State
- `control_ref_node.py` publishes to `/control_ref/cmd_vel` (TwistStamped)
- This is a **safe test topic** - not connected to autopilot

### Required Changes

**Add MAVROS publisher:**
```python
from geometry_msgs.msg import Twist  # Note: Twist, not TwistStamped

# In __init__:
self.pub_mavros = self.create_publisher(
    Twist,
    '/mavros/setpoint_velocity/cmd_vel',
    10
)

# Publish method:
def publish_mavros_cmd(self, vx: float, vy: float, yaw_z: float) -> None:
    msg = Twist()
    msg.linear.x = vx
    msg.linear.y = vy
    msg.linear.z = 0.0  # No vertical velocity for now
    msg.angular.x = 0.0
    msg.angular.y = 0.0
    msg.angular.z = yaw_z
    self.pub_mavros.publish(msg)
```

**Safety parameter:**
```python
self.declare_parameter('enable_mavros', False)  # Explicitly enable for safety
self.enable_mavros = bool(self.get_parameter('enable_mavros').value)

# In on_timer():
if self.enable_mavros:
    self.publish_mavros_cmd(self.prev_vx, self.prev_vy, self.prev_yaw_z)
else:
    # Keep publishing to test topic
    self.publish_cmd(self.prev_vx, self.prev_vy, self.prev_yaw_z)
```

---

## Safety Considerations

### Before First MAVROS Test

**Hardware safety checklist:**
- [ ] Propellers REMOVED or motors physically blocked
- [ ] Vehicle secured (can't move or tip over)
- [ ] Battery connected with easy disconnect access
- [ ] Kill switch / RC transmitter in hand with known failsafe behavior
- [ ] Clear space around vehicle (no people, obstacles)
- [ ] Fire extinguisher nearby (LiPo safety)

**Software safety checklist:**
- [ ] MAVROS connects successfully (`/mavros/state` shows `connected: True`)
- [ ] RC override tested (can take control from perception)
- [ ] Arming procedure understood but NOT executed
- [ ] Emergency stop procedure defined (kill switch, RC override, power disconnect)
- [ ] Command limits validated (max velocities reasonable)
- [ ] Setpoint rate verified (30 Hz target)

### ArduPilot Safety Features to Understand

**Failsafes:**
- RC failsafe (what happens if RC signal lost)
- Battery failsafe (low voltage behavior)
- GCS failsafe (what happens if MAVLink lost)

**Flight modes:**
- STABILIZE: Manual control, autopilot stabilizes
- GUIDED: Accepts MAVROS commands (required for velocity control)
- RTL: Return to launch (emergency)
- LAND: Controlled landing

**Critical:** Vehicle must be in GUIDED mode to accept MAVROS velocity commands.

---

## Testing Procedure (W12 Tuesday)

### Phase 1: Connection Validation (30 min)
1. Connect Pixhawk via USB
2. Launch MAVROS
3. Verify `/mavros/state` shows connection
4. Check topic list for expected MAVROS topics
5. Record connection parameters that work

### Phase 2: Perception + MAVROS Coexistence (1 hour)
1. Keep MAVROS running
2. Launch perception pipeline (camera, inference, tracker, selector)
3. Launch control_ref_node with `enable_mavros:=false`
4. Verify all nodes running simultaneously
5. Check for resource issues (CPU, memory)

### Phase 3: Control Output to MAVROS (1 hour)
1. Enable `enable_mavros:=true` in control_ref_node
2. **DO NOT ARM VEHICLE**
3. Monitor `/mavros/setpoint_velocity/cmd_vel` 
4. Verify setpoints published at 30 Hz
5. Verify setpoint values look reasonable
6. Wave hand in front of camera, observe setpoint changes
7. Remove target, verify zero commands

### Phase 4: Recording and Analysis (1 hour)
1. Record diagnostic bag with all topics
2. Shutdown cleanly
3. Analyze setpoint values offline
4. Document any issues
5. Plan Thursday session based on results

---

## Common Issues and Debugging

### MAVROS won't connect
- Check USB cable and port (`ls /dev/tty*`)
- Try different baud rates (57600, 115200)
- Check Pixhawk is powered
- Look for errors in MAVROS output

### Topics not appearing
- MAVROS might not be fully started (wait 10-15 seconds)
- Check with: `ros2 node list` (should see `/mavros` node)

### Setpoints not reaching Pixhawk
- Vehicle might not be in GUIDED mode
- Check `/mavros/state` for current mode
- May need to set mode via RC or GCS first

### Coordinate frame confusion
- Test with known target position (e.g., target on left → expect negative angular.z)
- Plot setpoints vs target position to verify mapping

---

## Future Enhancements (Post-W12)

**After ground testing succeeds:**
- Add vertical velocity control (`linear.z`)
- Switch to position setpoints for hovering
- Add feedforward from velocity estimates
- Implement prediction for smoother control
- Add explicit state machine (SEARCH, TRACK, LOST)
- Integrate with mission planner for geofencing

**For flight testing:**
- Tune gains for actual vehicle dynamics
- Add altitude hold during tracking
- Implement loss recovery (hover in place, yaw scan)
- Add logging of IMU and position for analysis
- Safety pilot with RC override always ready

---

## Resources

### MAVROS Documentation
- ROS 2 MAVROS: https://github.com/mavlink/mavros/tree/ros2
- API documentation: https://docs.px4.io/main/en/ros/mavros_installation.html

### ArduPilot Resources
- Guided mode: https://ardupilot.org/copter/docs/ac2_guidedmode.html
- Velocity control: https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED
- Failsafe documentation: https://ardupilot.org/copter/docs/common-failsafe-landingpage.html

### Example Code
- MAVROS offboard examples: https://github.com/Jaeyoung-Lim/mavros_controllers
- ROS 2 + MAVROS: https://github.com/ros2/examples

---

## Integration Checklist

### W11 Tasks (Before Hardware)
- [ ] Read this document thoroughly
- [ ] Install MAVROS if not present
- [ ] Understand topics and coordinate frames
- [ ] Update control_ref_node.py with MAVROS output
- [ ] Add `enable_mavros` safety parameter
- [ ] Test code compiles (no syntax errors)
- [ ] Document launch sequence
- [ ] Create safety checklist

### W12 Tuesday Tasks (With Hardware)
- [ ] Connect Pixhawk and launch MAVROS
- [ ] Verify connection and topics
- [ ] Run perception + MAVROS together
- [ ] Enable MAVROS output (unarmed only)
- [ ] Validate setpoint flow and values
- [ ] Record diagnostic bags
- [ ] Document issues for Thursday

### W12 Thursday+ Tasks (If Tuesday Succeeds)
- [ ] Test outdoor with MAVROS
- [ ] Validate setpoints respond to real targets
- [ ] Test loss behavior outdoors
- [ ] Prepare for armed ground test (props removed)
- [ ] Build toward first flight test

---

**Last updated:** 2026-03-12  
**Next review:** After W12 Tuesday session
