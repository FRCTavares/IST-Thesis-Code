# First Outdoor Control Gate (GO / NO-GO)

Date: 2026-03-26
Owner: Thesis control chain validation

## Purpose

Define objective pass/fail criteria before first supervised outdoor Guided-mode control tests.

Control chain in scope:

`/target -> control_ref_node -> MAVROS -> ArduPilot Guided velocity behaviour`

## Gate Decision Outputs

- GO: all hard gates pass.
- CONDITIONAL-GO: no hard gate fails, but one or more soft gates fail with approved mitigation.
- NO-GO: any hard gate fails.

## Frozen Control Contract (Must Match Runtime)

- MAVROS publish topic: `/mavros/setpoint_velocity/cmd_vel`
- Message type: `geometry_msgs/msg/TwistStamped`
- Commanded axes in first outdoor phase:
  - linear.x: enabled (forward/back)
  - angular.z: enabled (yaw rate)
  - linear.y: disabled (0.0)
  - linear.z: disabled (0.0)
- Stale target timeout: 0.2 s
- Lost/stale behavior: publish safe zeros and hold
- Hold definition: zero body velocity and zero yaw-rate

## Hard Gates (Fail Any = NO-GO)

### G1 — Topic and Message Contract

- [ ] Observed publish topic exactly matches frozen topic.
- [ ] Message type is `TwistStamped` on MAVROS velocity path.
- [ ] Stamped stream is continuous during Guided-mode control window.

### G2 — Sign Semantics Validation

- [ ] Left/right target sweep confirms yaw-rate sign mapping.
- [ ] Near/far target change confirms forward velocity sign mapping.
- [ ] Sign results are consistent across at least 3 repeated trials per case.

### G3 — Stale/Lost Safety Behavior

- [ ] Target loss drives command outputs to safe zeros within stale timeout.
- [ ] Stale-target injection triggers same safe-zero behavior.
- [ ] No command spikes observed at valid->invalid or invalid->valid transitions.

### G4 — Saturation and Bounds

- [ ] Commands remain within frozen saturation limits during all ground cases.
- [ ] No persistent saturation bursts under centered/static target conditions.

### G5 — Command Refresh Continuity

- [ ] Guided-mode refresh stream remains continuous during command phase.
- [ ] No unplanned control dropouts in sustained ground run window.

### G6 — MAVROS Mirror Consistency

- [ ] Internal control command and MAVROS-published command are equivalent in sign and magnitude trend.
- [ ] Any transform/frame differences are documented and explained.

## Soft Gates (Can Be CONDITIONAL-GO)

### S1 — Perception Throughput

- Target threshold: perception/control-relevant stream >= 12 Hz sustained (preferred >= 15 Hz).
- Result: [ ] pass [ ] fail
- Mitigation if fail:

### S2 — End-to-End Latency

- Target threshold: p95 end-to-end detection latency <= 200 ms (preferred <= 150 ms).
- Result: [ ] pass [ ] fail
- Mitigation if fail:

### S3 — Operator Procedure Stability

- Startup/shutdown and emergency disable procedure executed cleanly in rehearsal.
- Result: [ ] pass [ ] fail
- Mitigation if fail:

## Immediate Disable Conditions During Ground or Outdoor Session

Disable MAVROS publication immediately if any of the following occurs:

- sign convention mismatch observed in live behavior
- stale/lost target does not produce safe-zero outputs
- sustained command oscillation not explained by input stimulus
- uncontrolled saturation or command runaway pattern
- repeated command refresh dropouts

## Required Evidence Pack

- [ ] rosbag or logs for all 7 ground validation cases
- [ ] signed sign-semantics table (image error -> command sign -> expected body motion)
- [ ] timing summary for sustained run
- [ ] MAVROS mirror comparison notes
- [ ] final gate decision line with rationale

## Final Decision

- Decision: [ ] GO  [ ] CONDITIONAL-GO  [ ] NO-GO
- Date:
- Reviewer(s):
- Blocking items (if any):
- Mitigations required before next test:
