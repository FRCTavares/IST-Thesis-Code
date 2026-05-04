# MAVROS Integration Guide

**Status:** Bridge frozen (Day 13) — code validated via offline replay bag; hardware authority deferred to W12 Guided-mode bench session

**Purpose:** Integrate perception pipeline with ArduPilot autopilot via MAVROS for velocity-based target tracking.

---

## Quick Reference

### Key MAVROS Topics

| Topic | Message Type | Purpose | Status |
|-------|--------------|---------|--------|
| `/mavros/state` | `mavros_msgs/State` | FCU connection, armed, mode | Monitor only |
| `/mavros/setpoint_velocity/cmd_vel` | `geometry_msgs/msg/TwistStamped` | Velocity setpoints via MAVROS setpoint velocity plugin | **Target for control** |
| `/mavros/setpoint_velocity/cmd_vel_unstamped` | `geometry_msgs/msg/Twist` | Unstamped velocity alternative | Not used in this project |
| `/mavros/local_position/pose` | `geometry_msgs/PoseStamped` | Current position feedback | Future use |
| `/mavros/local_position/velocity_body` | `geometry_msgs/TwistStamped` | Current velocity | Future use |
| `/mavros/rc/in` | `mavros_msgs/RCIn` | RC receiver inputs | Safety monitor |

### Coordinate Frames

**Frozen Day 13 assumption:**
- MAVROS bridge topic stays on `/mavros/setpoint_velocity/cmd_vel` with `geometry_msgs/msg/TwistStamped`
- MAVROS `setpoint_velocity` frame is frozen to `BODY_NED` for planning and documentation
- The MAVROS plugin performs frame transforms according to `mav_frame`; do not improvise axis sign changes in the field
- Real authority testing is deferred until a Guided-mode bench session with the vehicle physically secured

**Control mapping at the ROS node output:**
- Forward command → `twist.linear.x`
- Lateral command → `twist.linear.y` (currently disabled)
- Vertical command → `twist.linear.z = 0.0`
- Yaw-rate command → `twist.angular.z`

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
### Implementation (Day 13 — frozen)

**Parameters added to `__init__`:**
```python
from geometry_msgs.msg import TwistStamped

self.declare_parameter('enable_mavros', False)
self.enable_mavros = bool(self.get_parameter('enable_mavros').value)

self.declare_parameter('mavros_topic', '/mavros/setpoint_velocity/cmd_vel')
self.mavros_topic = str(self.get_parameter('mavros_topic').value)

self.pub_mavros = self.create_publisher(
    TwistStamped,
    self.mavros_topic,
    10,
)
```

**Shared-stamp helper and dual-publish method:**
```python
def _make_twist_msg(
    self, stamp, vx: float, vy: float, yaw_z: float, frame_id: str = ''
) -> TwistStamped:
    msg = TwistStamped()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.twist.linear.x = float(vx)
    msg.twist.linear.y = float(vy)
    msg.twist.linear.z = 0.0
    msg.twist.angular.x = 0.0
    msg.twist.angular.y = 0.0
    msg.twist.angular.z = float(yaw_z)
    return msg

def publish_pair(self, stamp, vx: float, vy: float, yaw_z: float) -> None:
    """Publish the same command to both the debug topic and (if enabled)
    the MAVROS topic.  Both messages share the exact same header.stamp
    to make offline topic-diff checks reliable."""
    msg = self._make_twist_msg(stamp, vx, vy, yaw_z)
    self.pub_cmd.publish(msg)
    if self.enable_mavros:
        self.pub_mavros.publish(self._make_twist_msg(stamp, vx, vy, yaw_z))

def publish_zero(self) -> None:
    self.prev_vx = 0.0
    self.prev_vy = 0.0
    self.prev_yaw_z = 0.0
    self.publish_pair(self.get_clock().now().to_msg(), 0.0, 0.0, 0.0)

# In on_timer:
self.publish_pair(self.get_clock().now().to_msg(), self.prev_vx, self.prev_vy, self.prev_yaw_z)
```

**Design notes:**
- A single `get_clock().now().to_msg()` call is made per publish event; the same stamp object is passed to `_make_twist_msg` for both topics, making offline comparison trivial
- `/control_ref/cmd_vel` remains the internal/debug output always; the MAVROS mirror is silently gated by `enable_mavros`
- `cmd_topic` and `mavros_topic` stay separate so replay and field monitoring are unambiguous

**Offline validation (Day 13 — PASS):**
- Bag: `artifacts/bags/tmp/2026-03-13__cmd_mirror_check` (297 s, 86 754 debug / 86 753 mirror messages)
- Script: `tools/compare_cmd_mirror_bag.py` — multiset comparison of `(stamp, payload)` keys
- Result: multisets match; one extra zero-velocity debug message at startup (expected)
- Run with: `python3 tools/compare_cmd_mirror_bag.py`
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

**Critical:** ArduPilot movement commands are intended for Guided mode and are forwarded via `SET_POSITION_TARGET_LOCAL_NED`. Day 13 does not include real authority testing.

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

### Phase 3: Day 13 Scope Freeze
1. Implement the MAVROS mirror path in code
2. Compile-check `control_ref_node.py`
3. Rebuild `thesis_bringup`
4. Validate command behavior with replay or synthetic targets only
5. Monitor `/mavros/setpoint_velocity/cmd_vel` only as a topic-level interface check
6. Defer any real vehicle authority testing to a later Guided-mode bench session

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
- Freeze `mav_frame` to `BODY_NED` in docs and launch configuration before hardware work
- Do not hand-tune sign conventions in the field
- Verify setpoint signs with replay logs and bench monitoring before any Guided-mode test

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
- [x] Read this document thoroughly
- [ ] Install MAVROS if not present (deferred — no Pixhawk until W12)
- [x] Understand topics and coordinate frames
- [x] Update control_ref_node.py with MAVROS output
- [x] Add `enable_mavros` safety parameter
- [x] Test code compiles (no syntax errors)
- [x] Validate with offline replay bag (`tools/compare_cmd_mirror_bag.py` → PASS)
- [ ] Create safety checklist (deferred to W12 prep)

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

**Last updated:** 2026-03-13  
**Next review:** Before W12 Tuesday hardware session
