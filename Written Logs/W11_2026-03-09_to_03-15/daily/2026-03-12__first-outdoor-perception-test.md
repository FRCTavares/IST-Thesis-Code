# Daily Log — 2026-03-12 (Day 12) — MAVROS Learning + Indoor Baseline

## Reality Check

**Constraints today:**
- ❌ No outdoor testing (Pi5 at home, Pixhawk at IST)
- ❌ No MAVROS hardware (no Pixhawk access)
- ✅ Indoor perception validation possible
- ✅ MAVROS learning and preparation possible

**Focus:** Learn MAVROS fundamentals and establish indoor perception baseline

---

## Goals for Today

### 1. MAVROS Learning (Critical Path)
- [ ] Read `docs/mavros_integration_guide.md` thoroughly
- [ ] Install MAVROS if not already present
- [ ] Understand topics and coordinate frames
- [ ] Note key commands and procedures
- [ ] Identify questions for supervisors

### 2. First Indoor Perception Session
- [ ] Run 10-minute sustained perception session
- [ ] Test target lock with movement
- [ ] Monitor system health (CPU, memory, temps)
- [ ] Record bag: `bags/live_camera/2026-03-12__indoor_baseline_10min/`

### 3. MAVROS Code Design
- [ ] Review current `control_ref_node.py`
- [ ] Plan MAVROS publisher integration
- [ ] Sketch `enable_mavros` parameter logic

### 4. Contact Supervisors ⚠️ CRITICAL
- [ ] Review `supervisor_questions.md`
- [ ] Email supervisors with safety questions
- [ ] Request answers before Monday evening

---

## Work Sessions

### Morning Session (3-4 hours)

**MAVROS learning:**
```bash
# Install MAVROS
sudo apt install ros-jazzy-mavros ros-jazzy-mavros-extras
wget https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh
sudo bash ./install_geographiclib_datasets.sh

# Verify installation
ros2 pkg list | grep mavros
```

**Read and understand:**
- Topics: `/mavros/setpoint_velocity/cmd_vel`, `/mavros/state`
- Coordinate frames: body frame (x=forward, y=left, z=up)
- Launch command for Ethernet: `ros2 launch mavros apm.launch fcu_url:=udp://192.168.1.1:14550@`

### Afternoon Session (3-4 hours)

**Indoor perception session:**
```bash
# Launch lean perception stack
# Terminal 1: camera_init_node
# Terminal 2: camera_capture_node  
# Terminal 3: detection_zmq.py (container)
# Terminal 4: inference_client_node
# Terminal 5: tracker_node
# Terminal 6: target_selector_node
# Terminal 7: bag record

# Record 10 minutes
cd $THESIS_ROOT/ros2_ws
ros2 bag record --storage mcap \
  -o ../bags/live_camera/2026-03-12__indoor_baseline_10min \
  /camera/fps /detections /timing /target
```

**During run:**
- Move in front of camera to test target lock
- Note any anomalies or crashes
- Monitor temperatures

### Evening Session (2-3 hours)

**Quick analysis:**
```bash
# Check bag stats
ros2 bag info bags/live_camera/2026-03-12__indoor_baseline_10min

# Verify ~16 Hz on /target
# Note any issues
```

**Email supervisors:**
- Send questions from `supervisor_questions.md`
- Request answers before Monday
- Emphasize Tuesday IST session importance

**Plan tomorrow:**
- Review what worked/didn't work today
- Adjust Day 13 tasks if needed

---

## Expected Deliverables

- [ ] MAVROS installed and verified
- [ ] Understanding of MAVROS basics (topics, frames, launch)
- [ ] 10-minute indoor perception bag recorded
- [ ] Supervisors contacted with safety questions
- [ ] Day 13 plan adjusted based on progress

---

## Notes and Issues

*(Fill in as you work)*

**MAVROS learning:**
- 

**Indoor session:**
- 

**Questions for supervisors:**
- 

**Blockers:**
- 

---

## End of Day Review

**Completed:**
- [ ] MAVROS learned
- [ ] Indoor session done
- [ ] Supervisors emailed
- [ ] Tomorrow planned

**Time spent:**
- Morning: ___ hours
- Afternoon: ___ hours  
- Evening: ___ hours

**Energy level:** _(high / medium / low)_

**Ready for Day 13?** _(yes / needs adjustment)_

**Tasks:**
- [ ] Write GO conditions for first outdoor day
- [ ] Write NO-GO conditions
- [ ] List remaining blockers
- [ ] Decide whether first real session is:
  - perception-only, or
  - perception + ground-only control monitoring

**Deliverables:**
- Explicit GO / NO-GO gate for first outdoor field day
- Updated sequence for the rest of W11 or early W12

---

## Expected Outcomes

By end of Day 12, you should have:

1. **Field documentation ready**
   - checklist
   - packing list
   - startup / shutdown steps
   - scenario sheet

2. **Controller better frozen**
   - validated indoor behaviour
   - known-good run command
   - updated control interface notes

3. **Safe rehearsal path prepared**
   - replay or simulation ready
   - controller can be exercised without outdoor deployment

4. **Real outdoor gate clarified**
   - know exactly what remains before real tests
   - no ambiguity about readiness

---

## Notes

- **No outdoor testing today**
- No MAVROS authority work unless explicitly needed for documentation only
- Focus on reducing uncertainty before any real field session
- Better preparation now means cleaner real results later

---

## Revised W11 Sequence

Instead of:
- Day 12: outdoor testing
- Day 13: protocol execution

**New realistic sequence:**
- **Day 12:** readiness pack + replay/simulation rehearsal
- **Day 13:** controller rehearsal + MAVROS topic-level prep if needed
- **Day 14 or next available:** first real outdoor perception session
- **After that:** larger structured outdoor protocol

---

## Simulation Approach Recommendation

For the current state, the best low-friction option is probably **bag replay or synthetic `/target` publishing**, not a full UAV simulator yet.

This lets you test:
- left/right target motion
- near/far target motion
- timeout / target loss
- command smoothness

...without adding the chaos of full vehicle simulation.
