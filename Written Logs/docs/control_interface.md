# Control Interface

## Purpose

This document freezes the perception-to-control contract between `/target` and `control_ref_node`.

The objective is to support safe ground-only validation first, then controlled outdoor integration later.

**Status:** Ground-only control integration completed on 2026-03-11.

---

## Input Topic

`/target` with type `thesis_msgs/msg/TargetState`

### Message Fields

```
std_msgs/Header header
uint32 id
float32 cx
float32 cy
float32 w
float32 h
float32 score
float32 quality
```

### Important: Coordinate System

**As of 2026-03-11, `/target` uses pixel coordinates, not normalized [0,1]:**

- `cx, cy` are in pixel space: [0, img_w] and [0, img_h]
- `w, h` are in pixel space: bbox dimensions in pixels
- Image dimensions: `img_w = 640`, `img_h = 640`

This is the current reality. The control node handles this by normalizing internally.

---

## Control Node Internal Normalization

`control_ref_node` normalizes pixel-space inputs internally:

```python
cx_norm = cx / img_w
cy_norm = cy / img_h
h_norm = h / img_h
```

Parameters:
- `img_w`: Image width in pixels (default: 640.0)
- `img_h`: Image height in pixels (default: 640.0)

---

## Frozen Derived Variables

The control node derives:
- `ex = cx_norm - 0.5` (image-space horizontal error)
- `ey = cy_norm - 0.5` (image-space vertical error)

Range proxy:
- `h_norm` (normalized bbox height)

Interpretation:
- Larger `h_norm` means closer
- Smaller `h_norm` means farther

---

## Valid Target Rule

A target is considered valid only if:
- A fresh `/target` message has arrived within 0.2 s
- `cx` and `cy` are within image bounds [0, img_w] and [0, img_h]
- `w > 0` and `h > 0`
- `score >= min_score_valid` (default: 0.30)
- `quality >= min_quality_valid` (default: 0.50)

If any of these fail, the control node publishes safe zero commands.

---

## Current Limitation

This message does not yet contain explicit visibility, lost-target, or reacquired flags.

For the current ground-only phase, loss is inferred from:
- Timeout (no update within 0.2 s)
- Invalid geometry (out of bounds or zero size)
- Low score or quality

---

## Timing Assumptions

**Perception update rate:**
- About 15 to 17 Hz in validated lean mode
- Perception publishes `/target` whenever tracks are available

**Control output rate:**
- 30 Hz target loop (fixed timer)
- Control node publishes at 30 Hz regardless of `/target` update rate

**Target reuse:**
- Control safely reuses most recent valid target measurement
- Freshness timeout ensures stale targets are rejected

---

## Target Freshness Rule

A target sample is stale if:
- No valid update has arrived for more than 0.2 s

If stale, the control node behaves as if the target were lost (publishes zero commands).

---

## Frozen Ground-Only Control Behaviour

### Yaw Control

Uses `ex` to generate yaw correction.

**Objective:** Keep `ex → 0` (center target horizontally)

**Control law:**
```python
yaw_raw = yaw_kp * ex
yaw_clamped = clamp(yaw_raw, -yaw_max, yaw_max)
yaw_output = slew_limit(yaw_clamped, yaw_slew_rate, dt)
```

**Validated signs:**
- Target left of center (ex < 0) → negative yaw ✓
- Target right of center (ex > 0) → positive yaw ✓
- Target centered (ex ≈ 0) → near-zero yaw ✓

### Forward Control

Uses `h_norm` relative to desired reference height.

**Objective:** Maintain approximate target distance

**Control law:**
```python
h_error = h_norm - desired_h_norm
forward_raw = forward_kp * h_error
forward_clamped = clamp(forward_raw, -forward_max, forward_max)
forward_output = slew_limit(forward_clamped, forward_slew_rate, dt)
```

**Validated signs:**
- Target far, small h_norm → positive forward (move forward) ✓
- Target close, large h_norm → negative forward (move back) ✓
- Target at desired distance → near-zero forward ✓

### Lateral Control

Not yet implemented in first integration. Set to zero.

### Vertical Control

Not yet implemented in first integration. Set to zero.

---

## Safety Bounds

All generated commands are bounded before output.

**Current limits (ground-only tuning):**
- `yaw_max = 0.1`
- `forward_max = 0.1`
- `lateral_max = 0.0` (not used yet)
- `vertical_max = 0.0` (not used yet)

**Slew rate limits (smooth ramping):**
- `yaw_slew_rate = 0.05` per timestep
- `forward_slew_rate = 0.05` per timestep

**Zero deadbands:**
- `yaw_deadband = 0.02`
- `forward_deadband = 0.05`

---

## Lost-Target Behaviour

If any of the following is true:
- `id == 0` (no target selected)
- Target age exceeds stale timeout (0.2 s)
- Target fails validity checks (bounds, size, score, quality)

Then `control_ref_node`:
- Publishes zero commands on all axes
- Resets slew limiter state
- Continues publishing at 30 Hz (with zeros)

**No aggressive behavior on loss:**
- No sudden commands
- No yaw scan (not yet implemented)
- Clean transition to hold state

---

## Reacquisition Behaviour

When a valid target appears after loss:
- Resume normal bounded control
- Slew limiting ensures smooth ramp-up
- No aggressive transient boost

---

## Frozen Run Command

```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -p cmd_topic:=/control_ref/cmd_vel \
  -p img_w:=640.0 \
  -p img_h:=640.0 \
  -p desired_h_norm:=0.90
```

**Parameters validated on 2026-03-11:**
- `cmd_topic`: `/control_ref/cmd_vel` (private topic for ground testing)
- `img_w`, `img_h`: Must match camera/inference resolution (640x640)
- `desired_h_norm`: 0.90 for indoor close-range testing

---

## Ground-Only Validation Results (2026-03-11)

**Successfully validated:**
- ✓ `/target` subscription with BEST_EFFORT QoS
- ✓ Internal pixel → normalized coordinate conversion
- ✓ Yaw control sign correctness
- ✓ Forward control sign correctness
- ✓ Target validity logic
- ✓ Fail-safe zeroing on target loss
- ✓ Slew rate limiting (smooth ramping observed)
- ✓ Command saturation at limits
- ✓ Clean startup and shutdown

**Observations:**
- Commands ramp smoothly: 0.0 → -0.03 → -0.06 → -0.09 → -0.1
- Zero outputs when target invalid or stale
- No jumps or discontinuities in control outputs

---

## MAVROS First Bridge Freeze (2026-03-12)

**Installation completed:**
- MAVROS installed on ROS 2 Jazzy: `ros-jazzy-mavros`
- MAVROS extras installed: `ros-jazzy-mavros-extras`
- GeographicLib datasets installed successfully
- ArduPilot launch file confirmed: `apm.launch`
- Default FCU connection assumption: `/dev/ttyACM0:57600`

**First MAVROS bridge topic:**
- Topic: `/mavros/setpoint_velocity/cmd_vel`
- Message type: `geometry_msgs/msg/TwistStamped`

**Key decision:**
- `control_ref_node` already publishes `TwistStamped`, so **no message redesign is needed**
- Direct topic remapping from `/control_ref/cmd_vel` to `/mavros/setpoint_velocity/cmd_vel` is sufficient

**First mapping (ground-only validation):**
```
linear.x  = forward   (m/s in body frame)
linear.y  = 0.0       (lateral reserved for later)
linear.z  = 0.0       (vertical reserved for later)
angular.z = yaw_rate  (rad/s)
```

**Hardware test configuration:**
- Keep `use_lateral = False` for first tests
- Keep `use_vertical = False` for first tests
- Body frame: x=forward, y=left, z=up (NED or FRD depending on vehicle config)

**Topic remapping for hardware tests:**
```bash
ros2 run thesis_bringup control_ref_node --ros-args \
  -r /control_ref/cmd_vel:=/mavros/setpoint_velocity/cmd_vel \
  -p img_w:=640.0 \
  -p img_h:=640.0 \
  -p desired_h_norm:=0.90
```

---

## Next Integration Steps

### Control Topic Remapping

Current: `/control_ref/cmd_vel` (private testing topic)

For MAVROS hardware tests:
- Remap `cmd_topic` to `/mavros/setpoint_velocity/cmd_vel` at launch
- Message type compatibility: ✅ confirmed (`TwistStamped`)
- Test ground-only message flow before any flight authority

---

## Remaining Pre-Flight Blockers

Before any flight-related evaluation:
- [ ] MAVROS topic choice frozen
- [ ] Message format and coordinate frames aligned
- [ ] Ground-only MAVROS message flow tested
- [ ] Restart reliability validated
- [ ] Loss and reacquisition behavior tested systematically
- [ ] Command limits reviewed against actual vehicle
- [ ] Field-safe test procedure documented
- [ ] Emergency stop procedure defined and tested

---

## Known Limitations

**Coordinate system:**
- `/target` currently in pixel space, not normalized
- Control node handles this internally
- Future: Consider normalizing `/target` upstream for cleaner interface

**Control authority:**
- Only yaw and forward implemented
- Lateral and vertical not yet used
- 3D control capability planned for later

**Loss detection:**
- Currently implicit (timeout + validity checks)
- No explicit `target_lost` or `target_visible` flags in message
- Future: Add explicit state flags to TargetState message

**Tuning status:**
- Current gains are for indoor ground testing only
- Outdoor and flight gains will need separate tuning
- Slew rates may need adjustment for vehicle dynamics