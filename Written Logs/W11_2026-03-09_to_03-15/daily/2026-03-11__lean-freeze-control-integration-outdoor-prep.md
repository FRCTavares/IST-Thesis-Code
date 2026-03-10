# Daily Log — 2026-03-11 — Lean-Mode Freeze, Control Interface Integration, and Outdoor Readiness

## Goal

Freeze the validated lean perception configuration, advance ground-only control integration, and prepare the full outdoor test pack for the next available field day.

**Target outcome:**
- Lean perception mode frozen and documented
- `control_ref_node` integrated against the validated `/target` interface
- Ground-only MAVROS/control message flow verified
- Safety logic and fail-safe behaviour reviewed
- Outdoor checklist, scenario plan, and bag naming prepared
- One short indoor smoke run confirms the frozen setup still works

---

## Context

| Key | Value |
|-----|-------|
| Previous validation | Lean live stack validated on Day 10 |
| Day 10 performance | 10 minute lean run: 16.644 Hz, lat_ms p95 = 91.296 ms, throttled = 0x0 |
| Constraint | Outdoor session cannot happen on Day 11 |
| Best use of Day 11 | Freeze what works, push control integration (ground-only), reduce risk before first field session |
| Test location | Indoor lab only (no outdoor access today) |
| Control scope | Ground validation only: no flight authority, no risky actuator behaviour |

---

## Work Plan

### A) Freeze the Validated Lean Perception Mode

Save the final tracker live-mode configuration as the current operational standard.

**Tasks:**
- [ ] Document the exact lean configuration:
  - Fast score path enabled (no per-track Python IoU score recovery)
  - `/timing_tracker` disabled in live mode
  - Lean recording topics: `/camera/fps`, `/detections`, `/timing`, `/target`
  - `/tracks` not recorded in operational bags
- [ ] Record the exact startup commands used for the validated 10 minute run
- [ ] Update runbook/notes so live mode and profiling mode are clearly separated
- [ ] Save the lean configuration as the default for outdoor field sessions
- [ ] Document when to switch back to profiling mode (dedicated debug sessions only)

**Deliverables:**
- Frozen lean configuration note: `docs/lean_operational_mode.md` or in runbook
- Final live startup command sequence
- Live mode vs profiling mode comparison table

---

### B) Control Integration — Ground-Only

Review and freeze the perception-to-control contract, then verify MAVROS message flow on the ground.

**Tasks:**
- [ ] Review and freeze the perception-to-control contract from `/target`:
  - `ex`, `ey` (normalized image coordinates)
  - `bbox_area` or bbox size as range proxy
  - `target_visible`, `target_lost`, `reacquired` (status flags)
  - Message rate and timing assumptions
- [ ] Bring up MAVROS and verify connection to Pixhawk:
  - Launch MAVROS: `ros2 launch mavros apm.launch.py fcu_url:=<connection_string>`
  - Verify `/mavros/state` (FCU connection status)
  - Check `/mavros/local_position/pose` (position feedback)
- [ ] Integrate `control_ref_node` against `/target`:
  - Subscribe to `/target`
  - Generate control setpoints (position, velocity, or attitude)
  - Publish to MAVROS setpoint topics
  - Verify message flow without needing outdoor testing
- [ ] Verify control outputs are bounded and safe:
  - Check setpoint rate matches target (30 Hz typical)
  - Confirm command limits are reasonable (e.g., max velocity, max position error)
  - Verify fail-safe behaviour when target is lost
  - Confirm safety bounds prevent risky commands
- [ ] If useful, test with live indoor target movement or bag replay

**Important limit:**
- Ground validation only
- No flight authority assumptions
- No armed motors or risky actuator behaviour

**Deliverables:**
- `control_ref_node` message flow validated
- Notes on setpoint contract and safety bounds: `docs/control_interface.md`
- List of remaining blockers before any flight-related test

---

### C) Indoor Smoke Validation in Final Operational Setup

Launch lean perception stack + control-side nodes and confirm coexistence.

**Tasks:**
- [ ] Launch lean perception stack:
  - camera_init_node, camera_capture_node
  - Live inference service (port 5556, HAILO_FRAME_SOURCE=ros)
  - thesis_inference_client, thesis_tracker (lean config)
  - thesis_target_selector
- [ ] Launch control-side nodes:
  - MAVROS (if available)
  - `control_ref_node`
- [ ] Run a short indoor smoke test (2-3 minutes):
  - Verify `/target` is stable enough for control consumption
  - Check control node processes `/target` correctly
  - Verify no regressions after freezing the configuration
  - Confirm timing and rates are consistent with Day 10
- [ ] Record one short lean bag if needed for validation

**Deliverables:**
- Short confirmation run (2-3 minutes)
- Short note confirming perception and control interface coexist cleanly

---

### D) Outdoor Readiness Pack

Prepare all logistics, checklists, and documentation for the next outdoor field day.

**Tasks:**
- [ ] Prepare outdoor checklist:
  - Pre-test checks (battery, connections, golden state)
  - Startup procedure for field use
  - Bag recording commands
  - Shutdown procedure
- [ ] Prepare participant scenario sheet:
  - Scenario 1: Single person, distance variation
  - Scenario 2: Two people, simultaneous tracking
  - Scenario 3: Three people, occlusion
  - Scenario 4: Dynamic motion
  - Instructions for each scenario
- [ ] Prepare bag naming scheme for outdoor runs:
  - Format: `2026-MM-DD__outdoor__scenario<N>__<descriptor>/`
  - Examples: `2026-03-12__outdoor__scenario1__single_distance/`
- [ ] Check hardware and logistics:
  - Disk space on Pi 5 (need ~10 GB free for outdoor bags)
  - Batteries charged (Tattu 6S 4500 mAh)
  - Cables, mounting, monitor/laptop
  - Confirm what must be carried to the court
- [ ] Write startup and shutdown checklist for field use

**Deliverables:**
- Outdoor checklist: `docs/outdoor_field_checklist.md`
- Scenario sheet for participants
- Field packing list
- Outdoor bag naming plan

---

### E) Reschedule Field Plan

Move first outdoor perception test to the next available day.

**Tasks:**
- [ ] Identify next available outdoor day (weather, personnel, location)
- [ ] Update W11 daily log sequence:
  - Day 11 (today): lean freeze + control integration + outdoor prep
  - Day 12 (or next available): first outdoor perception test
  - Day 13 (or next available): formal outdoor protocol
- [ ] Keep rest of week flexible depending on when outdoor access happens
- [ ] Update weekly plan if needed

**Deliverables:**
- Updated W11 sequence with new outdoor dates
- Clear next field day target

---

## Expected Outcomes

By end of Day 11, you should have:

1. **Frozen lean perception configuration**
   - Exact lean mode parameters documented
   - Startup commands saved
   - Live vs profiling mode clearly separated

2. **Control interface validated (ground-only)**
   - `/target` contract frozen
   - MAVROS message flow verified
   - `control_ref_node` integrated and tested on the ground
   - Safety bounds confirmed

3. **Indoor smoke run confirms no regressions**
   - Perception + control nodes coexist cleanly
   - Timing consistent with Day 10 validation

4. **Outdoor readiness pack complete**
   - Checklists, scenarios, bag naming ready
   - Hardware checked and prepared
   - Field day can execute smoothly when weather/logistics allow

5. **Clear plan for first outdoor day**
   - Next field day identified
   - Sequence updated accordingly

---

## Decision for Tomorrow

**Yes, tomorrow should deal with control, but only in the right way:**

✓ **Yes to:**
- Control interface integration
- MAVROS message-flow checks
- Loss behaviour and safety logic
- Ground-only validation

✗ **No to:**
- Pretending this replaces the first outdoor perception check
- Jumping to flight-like behaviour before restart and field behaviour are better characterised

**Recommended order:**
1. First freeze lean perception mode
2. Spend main block on control integration (ground-only)
3. Finish with outdoor prep
4. End with one short indoor smoke run

---

## Notes

- Outdoor cannot happen today, so use the day to strengthen foundations
- Control integration is valuable, but only at ground level (no flight assumptions)
- Restart reliability still not validated: remains a known limitation
- Full debug/profiling mode optimization deferred: lean mode sufficient for operations
- Day 11 allows first outdoor day to be clean, well-prepared, and low-risk
