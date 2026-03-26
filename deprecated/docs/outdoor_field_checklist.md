# Outdoor Field Checklist

**Purpose:** Pre-flight and on-site validation procedure for outdoor perception and control tests.

**Status:** Ready for Day 13+ outdoor sessions.

---

## Before Leaving

### Hardware
- [ ] Pi 5 charged / powered correctly
- [ ] Pixhawk available
- [ ] Battery charged (check voltage)
- [ ] Props condition checked
- [ ] Frame and mounts checked

### Data / Storage
- [ ] SD card / storage checked
- [ ] At least 10 GB free space confirmed
- [ ] Previous bags backed up if needed

### Equipment
- [ ] Cables packed (USB-C, Ethernet, power)
- [ ] Laptop packed
- [ ] Monitor / hotspot / keyboard if needed
- [ ] Camera cables and mounts checked

---

## On Site, Before Power

### Safety
- [ ] Confirm test area is clear
- [ ] Confirm no obstacles or hazards
- [ ] Confirm pilot and observer roles
- [ ] Confirm emergency stop / takeover procedure

### Session Planning
- [ ] Confirm session scope: perception-only or ground-only monitoring
- [ ] Confirm bag name before start (see naming scheme below)
- [ ] Confirm scenario to execute (see scenario sheet)

---

## Startup Sequence

1. [ ] Power platform safely
2. [ ] Confirm camera node works (`/camera/fps` publishing)
3. [ ] Confirm inference service runs (`detection_zmq.py` container)
4. [ ] Confirm `/detections`, `/target`, `/timing` topics exist
5. [ ] If Pixhawk connected, confirm MAVROS `/mavros/state` OK
6. [ ] Start bag recording (`ros2 bag record`)
7. [ ] Run scenario (see scenario sheet)

---

## Shutdown Sequence

1. [ ] Stop bag recording (Ctrl+C)
2. [ ] Save bag name and scenario notes
3. [ ] Shutdown ROS nodes cleanly
4. [ ] Shutdown inference container
5. [ ] Power down hardware safely
6. [ ] Check bag exists and is readable (`ros2 bag info`)

---

## Outdoor Bag Naming Scheme

**Format:**
```
YYYY-MM-DD__outdoor__scenario<N>__<descriptor>
```

**Examples:**
- `2026-03-14__outdoor__scenario1__single_simple_motion`
- `2026-03-14__outdoor__scenario2__two_people`
- `2026-03-14__outdoor__scenario3__short_occlusion`
- `2026-03-14__outdoor__scenario4__dynamic_motion`

**Storage location:**
```
$THESIS_ROOT/bags/live_camera/YYYY-MM-DD__outdoor__scenario<N>__<descriptor>/
```

---

## Notes and Observations

**Session:**
- Date: ___________
- Session scope: perception-only / ground-only / other
- Scenario(s) executed: ___________
- Bag name(s): ___________

**Conditions:**
- Weather: ___________
- Lighting: bright / overcast / low light
- Temperature: ___________

**Observations:**
- System stability: ___________
- Lock quality: ___________
- Issues encountered: ___________
- Anomalies or crashes: ___________

---

## Emergency Procedures

**If system becomes unstable:**
1. Stop bag recording
2. Kill inference service
3. Kill ROS nodes
4. Power down safely

**If hardware issue detected:**
1. Abort test immediately
2. Note the issue and timestamp
3. Shutdown cleanly
4. Inspect hardware before retry

**If Pixhawk/flight controller active:**
1. Pilot takes manual override immediately
2. Land safely
3. Disarm motors
4. Investigate before retry
