# Daily Log — 2026-03-13 (Day 13) — MAVROS Code Implementation + Control Refinement

## Reality Check

**Constraints today:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk at IST)
- ❌ No MAVROS hardware (no Pixhawk access until W12)
- ✅ Can implement MAVROS integration code
- ✅ Can test control logic with replay/synthetic targets

**Focus:** Implement MAVROS integration and refine control logic

---

## Goals for Today

### 1. MAVROS Integration Implementation (Critical)
- [ ] Update `control_ref_node.py` with MAVROS publisher
- [ ] Add `geometry_msgs/Twist` publisher to `/mavros/setpoint_velocity/cmd_vel`
- [ ] Add `enable_mavros` safety parameter (default False)
- [ ] Implement conditional publishing logic
- [ ] Test code compiles (no syntax errors)
- [ ] Git commit changes

### 2. MAVROS Documentation
- [ ] Document MAVROS launch procedure
- [ ] Write down Ethernet connection command
- [ ] Note topic checking steps
- [ ] Update control_interface.md

### 3. Second Indoor Perception Session (Extended)
- [ ] Run 15-20 minute session
- [ ] Test sustained performance over time
- [ ] Monitor thermal behavior
- [ ] Record bag: `bags/live_camera/2026-03-13__indoor_extended_15min/`

### 4. Control Logic Testing
- [ ] Test control with replayed bag or synthetic targets
- [ ] Validate target-loss behavior
- [ ] Test edge cases (stale, out-of-bounds, low confidence)
- [ ] Document control response

### 5. Safety Documentation
- [ ] Create pre-test safety checklist
- [ ] Document emergency stop procedures
- [ ] Research ArduPilot failsafes
- [ ] Start Tuesday session plan

---

## Work Sessions

### Morning Session (3-4 hours)

**MAVROS code implementation:**

Edit `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py`:

```python
from geometry_msgs.msg import Twist  # Add this import

# In __init__:
self.declare_parameter('enable_mavros', False)
self.enable_mavros = bool(self.get_parameter('enable_mavros').value)

# Add MAVROS publisher
self.pub_mavros = self.create_publisher(
    Twist,
    '/mavros/setpoint_velocity/cmd_vel',
    10
)

# New method:
def publish_mavros_cmd(self, vx: float, vy: float, yaw_z: float) -> None:
    msg = Twist()
    msg.linear.x = vx
    msg.linear.y = vy
    msg.linear.z = 0.0
    msg.angular.x = 0.0
    msg.angular.y = 0.0
    msg.angular.z = yaw_z
    self.pub_mavros.publish(msg)

# In on_timer(), add:
if self.enable_mavros:
    self.publish_mavros_cmd(self.prev_vx, self.prev_vy, self.prev_yaw_z)
```

**Test compilation:**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select thesis_bringup
```

**Git commit:**
```bash
git add ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py
git commit -m "Add MAVROS velocity setpoint integration (untested)"
git push
```

### Afternoon Session (3-4 hours)

**Extended indoor perception session:**
```bash
# Launch full lean stack
# Run for 15-20 minutes
# Record bag

ros2 bag record --storage mcap \
  -o ../bags/live_camera/2026-03-13__indoor_extended_15min \
  /camera/fps /detections /timing /target
```

**Control logic testing:**
- Option A: Replay previous bag, run control_ref_node separately
- Option B: Create simple synthetic target publisher
- Test target-loss → zero behavior
- Test boundary conditions

### Evening Session (2-3 hours)

**Safety documentation:**
- Create safety checklist (based on supervisor answers)
- Emergency stop procedure
- ArduPilot failsafe research
- Note questions for supervisors

**Tuesday session planning:**
- Hour-by-hour timeline
- Equipment checklist
- Success criteria
- Backup plans

---

## Expected Deliverables

- [ ] MAVROS integration coded and compiles
- [ ] 15-20 min indoor perception bag recorded
- [ ] Control logic tested with replay/synthetic
- [ ] Safety documentation started
- [ ] Tuesday session outline drafted
- [ ] Code committed to git

---

## Notes and Issues

*(Fill in as you work)*

**MAVROS coding:**
- 

**Indoor session:**
-

**Control testing:**
-

**Safety planning:**
-

**Blockers:**
-

---

## End of Day Review

**Completed:**
- [ ] MAVROS code implemented
- [ ] Extended session done
- [ ] Control testing done
- [ ] Safety docs started

**Time spent:**
- Morning: ___ hours
- Afternoon: ___ hours
- Evening: ___ hours

**Code status:** _(compiles / has errors / untested)_

**Ready for Day 14?** _(yes / needs adjustment)_
   - packing list
   - scenario sheet

2. **Controller rehearsed safely**
   - replay or synthetic target testing done
   - behaviour validated again without field risk

3. **MAVROS prep clarified**
   - topic choice known
   - interface path documented
   - no authority testing yet

4. **Real outdoor gate defined**
   - know exactly what remains before real tests
   - no ambiguity about readiness

---

## Remaining Blockers Before Real Outdoor Testing

- [ ] Outdoor checklist complete
- [ ] Scenario sheet complete
- [ ] Field packing list complete
- [ ] MAVROS topic path understood
- [ ] Restart reliability still needs validation
- [ ] Real-test safety rules need to be frozen

---

## Notes

- **No real outdoor testing on Day 13** unless everything is unexpectedly finished early
- No armed vehicle behaviour
- No flight-like control testing
- Focus on reducing uncertainty before the first field session
- Better rehearsal now means cleaner real results later
