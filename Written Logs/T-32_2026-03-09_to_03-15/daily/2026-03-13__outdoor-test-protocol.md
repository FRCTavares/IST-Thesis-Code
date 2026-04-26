# Daily Log — 2026-03-13 (Day 13) — Code, Replay, and MAVROS Bridge Freeze

> Note (updated 2026-03-16): Commands in this daily log are preserved as historical context. For current operational startup/stop commands, use `RUNBOOK.md` and `tools/start_live_stack.sh`.

## Reality Check

**Constraints today:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk at IST)
- ❌ No MAVROS hardware (no Pixhawk access until T-31)
- ✅ Can implement MAVROS integration code
- ✅ Can test control logic with replay/synthetic targets

**Focus:** Patch the MAVROS bridge, validate it with replay or synthetic targets, and freeze the interface docs.

---

## Goals for Today

### 1. MAVROS Integration Implementation (Critical)
- [x] Update `control_ref_node.py` with MAVROS publisher
- [x] Add `geometry_msgs/msg/TwistStamped` mirror publisher to `/mavros/setpoint_velocity/cmd_vel`
- [x] Add `enable_mavros` safety parameter (default False)
- [x] Add `mavros_topic` parameter for the stamped MAVROS topic
- [x] Mirror only the final safe command onto MAVROS
- [x] Test code compiles (no syntax errors)
- [x] Rebuild `thesis_bringup`

### 2. MAVROS Documentation
- [ ] Document MAVROS launch procedure (deferred — no hardware)
- [x] Freeze `/mavros/setpoint_velocity/cmd_vel` as the stamped bridge topic
- [x] Freeze `mav_frame=BODY_NED` in notes; no field sign improvisation
- [x] Note that ArduPilot movement commands are for Guided mode
- [x] Update `control_interface.md` and `mavros_integration_guide.md`

### 3. Control Logic Testing
- [ ] Test control with replayed bag or synthetic targets
- [ ] Validate target-loss behavior
- [ ] Test edge cases (stale, out-of-bounds, low confidence)
- [ ] Document control response

### 4. Safety Documentation
- [ ] Create pre-test safety checklist
- [ ] Document emergency stop procedures
- [ ] Research ArduPilot failsafes
- [ ] Start Tuesday session plan

### 5. Explicit Non-Goals for Today
- [x] No real vehicle authority testing
- [x] No arm/disarm experiments
- [x] No field-side frame/sign changes
- [x] No outdoor session required to close Day 13

---

## Work Sessions

### Morning Session (3-4 hours)

**Patch target in `control_ref_node.py`:**

Edit `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py`:

```python
from geometry_msgs.msg import TwistStamped

# In __init__:
self.declare_parameter('enable_mavros', False)
self.enable_mavros = bool(self.get_parameter('enable_mavros').value)

self.declare_parameter('mavros_topic', '/mavros/setpoint_velocity/cmd_vel')
self.mavros_topic = str(self.get_parameter('mavros_topic').value)

# Add MAVROS mirror publisher
self.pub_mavros = self.create_publisher(
   TwistStamped,
   self.mavros_topic,
   10,
)

# New method:
def publish_mavros_cmd(self, vx: float, vy: float, yaw_z: float) -> None:
   if not self.enable_mavros:
      return

   msg = TwistStamped()
   msg.header.stamp = self.get_clock().now().to_msg()
   msg.header.frame_id = ''
   msg.twist.linear.x = float(vx)
   msg.twist.linear.y = float(vy)
   msg.twist.linear.z = 0.0
   msg.twist.angular.x = 0.0
   msg.twist.angular.y = 0.0
   msg.twist.angular.z = float(yaw_z)
    self.pub_mavros.publish(msg)

# Zero helper:
def publish_zero_mavros_cmd(self) -> None:
   self.publish_mavros_cmd(0.0, 0.0, 0.0)

# Keep the existing debug publisher. Mirror the final safe command only.
```

**Test compilation:**
```bash
cd $THESIS_ROOT/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
python3 -m py_compile src/thesis_bringup/thesis_bringup/nodes/control_ref_node.py
colcon build --packages-select thesis_bringup
source install/setup.bash
```

### Afternoon Session (3-4 hours)

**Control logic testing:**
- Option A: Replay previous bag, run control_ref_node separately
- Option B: Create simple synthetic target publisher
- Test target-loss → zero behavior
- Test boundary conditions
- Confirm MAVROS mirror path matches the same post-clamp/post-slew command

### Evening Session (2-3 hours)

**Safety documentation:**
- Create safety checklist (based on supervisor answers)
- Emergency stop procedure
- ArduPilot failsafe research
- Note questions for supervisors

**Authority boundary:**
- Movement commands are for Guided mode through `SET_POSITION_TARGET_LOCAL_NED`
- Today stops at code, replay, and documentation
- No real platform authority testing on Day 13

**Tuesday session planning:**
- Hour-by-hour timeline
- Equipment checklist
- Success criteria
- Backup plans

---

## Expected Deliverables

- [x] MAVROS integration coded and compiles
- [x] Control logic tested with replay/synthetic
- [ ] Safety documentation started (deferred to T-31 prep)
- [ ] Tuesday session outline drafted (deferred)
- [x] MAVROS bridge contract frozen in docs

---

## Notes and Issues

*(Fill in as you work)*

**MAVROS coding:**
- Used `publish_pair(stamp, vx, vy, yaw_z)` with a shared stamp object to guarantee both topics carry identical header.stamp on every tick
- `_make_twist_msg` helper keeps construction DRY; `publish_zero` resets prev values then calls `publish_pair`
- `pub_mavros` publisher always created; gated by `self.enable_mavros` inside `publish_pair` only

**Indoor session:**
-

**Control testing:**
- Replayed bag `bags/tmp/2026-03-13__cmd_mirror_check` (297 s) with `enable_mavros:=true` and mirror topic remapped to `/mavros_mock/setpoint_velocity/cmd_vel`
- Offline comparison via `tools/compare_cmd_mirror_bag.py` (multiset strategy): **PASS** — 86 753 matched pairs, one extra zero-velocity debug message at startup

**Safety planning:**
-

**Blockers:**
-

---

## End of Day Review

**Completed:**
- [x] MAVROS code implemented (`publish_pair` + `_make_twist_msg` + `publish_zero`)
- [x] Build passed (`colcon build --packages-select thesis_bringup`)
- [x] Control testing done (replay bag, offline comparison PASS)
- [ ] Safety docs started (deferred — no hardware access today)

**Code status:** Compiles, validated offline.

**Ready for Day 14?** Yes — bridge is frozen, docs updated, offline check passed. Remaining items (safety checklist, MAVROS launch procedure) deferred to T-31 prep once Pixhawk is available.

## Day 13 Official Close-out

MAVROS mirror-path validation passed.

A bag-level comparison script (`tools/compare_cmd_mirror_bag.py`) was added and used to compare `/control_ref/cmd_vel` against `/mavros_mock/setpoint_velocity/cmd_vel` using a multiset `(stamp, frame_id, twist)` strategy rather than positional matching.

Result:
- debug topic: 86754 messages
- mirror topic: 86753 messages
- duration: ~297 s
- multisets matched except for one extra zero-velocity debug message at startup

Conclusion:
- the gated MAVROS `TwistStamped` mirror path is functioning correctly
- publication-level and payload-level validation both passed
- real authority testing remains deferred to a later Guided-mode bench session with Pixhawk
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
- Keep the dissertation direction unchanged: fully onboard RGB-only perception, bounded latency, and later closed-loop integration on the real platform
- Better rehearsal now means cleaner real results later
