# Daily Log — 2026-03-18 (Day 18) — Pre-Flight Integration and Control Closure

## Overview

**Focus:** Close all technical and control safety gates required for first flight attempt on Thursday (2026-03-19).

---

## Objectives (Updated Mid-Day)

### Priority 0 — Control Must Be Closed Today
- [ ] Validate control command signs and axis mapping end-to-end (target error -> command)
- [x] Enforce hard output saturation and minimum deadband on all control channels
- [x] Verify command frame convention consistency (camera/body/NED) with explicit test evidence
- [x] Confirm failsafe behavior on target loss, stale tracks, and tracker stop
- [x] Confirm command timeout behavior (no stale command persistence)
- [ ] Perform at least one 20+ min integrated unarmed run with control active and bounded
- [ ] Document final control limits for tomorrow's flight card

### 1. Full Stack Unarmed Validation at IST
- [ ] MAVROS connected and stable for entire session
- [x] Camera -> inference -> tracker chain optimized and validated in code
- [x] Tracker matching/gating improvements integrated
- [x] Control bridge publishes bounded commands only (field-validated)
- [ ] No crashes or watchdog resets in 20+ minute integrated run

### 2. Flight Readiness Gates
- [ ] RC override confirmed
- [ ] Emergency stop procedure rehearsed
- [ ] Command frame/sign sanity confirmed with recorded evidence
- [ ] Supervisor go/no-go criteria documented

### 3. Data Capture for Go/No-Go
- [x] Record short validation bag and logs (control active)
- [x] Timing instrumentation expanded for preprocessing split
- [x] Capture updated timing baseline under flight-intent setup
- [x] Produce one-page go/no-go summary for Thursday

---

## Work Completed So Far (Code + Integration)

### Camera and Image Pipeline
- Updated camera publisher path to publish packed RGB directly.
- Added reusable RGB buffer to avoid repeated allocations.
- Replaced conversion path to use cv2 color conversion into preallocated destination.

### Inference Client Performance Path
- Removed cv_bridge dependency from hot path.
- Added direct ROS image -> numpy view conversion with validation checks:
	- encoding check (`rgb8` expected)
	- row stride check (packed 8UC3)
	- payload size check
- Added preallocated resize buffer and in-place resize use.
- Switched payload send path to memoryview for lower copy overhead.
- Added fine-grained preprocessing timing breakdown:
	- `ros_to_np_ms`
	- `resize_ms`
	- `color_ms`
	- `pack_ms`

### Message Contract and Telemetry
- Extended timing message schema with new preprocessing stage metrics.
- Updated inference status printout to include the new timing fields.

### Tracking and Association
- Added optional axis-specific gating parameters (`gate_x`, `gate_y`) in tracker config path.
- Added vectorized pairwise IoU implementation for matching.
- Added vectorized association routine with optional gating mask.
- Added reusable matching buffers to reduce per-frame allocations.
- Kept compatibility path for other backends through Hungarian matcher API.

### What This Means for Flight Prep
- Perception and tracking path received meaningful latency/allocation optimization.
- Instrumentation now exposes preprocessing bottlenecks more clearly.
- Control closure is now the primary remaining blocker for tomorrow.

### Control Hardening Started (Implementation Delta)
- Added explicit command frame parameters in `control_ref_node`:
	- `cmd_frame_id` (default `base_link`) for `/control_ref/cmd_vel`
	- `mavros_frame_id` (default `base_link`) for MAVROS mirror output
- Added explicit invalid-target reason classification for safety diagnostics:
	- `id_zero`, stale target, invalid bounds/size, low score, low quality
- Added transition-aware logging:
	- Warn on invalid reason changes
	- Periodic reminder when invalid state persists
	- Info log when target becomes valid again
- Added control loop timer-slip warning to surface runtime scheduler drift under load.

---

## Remaining Session Plan (Control-First)

### Block A — Control Sanity and Safety Envelope
- Bring up MAVROS + perception + control unarmed.
- Validate topic continuity for state, target, and command outputs.
- Verify saturation, deadband, timeout, and target-loss behavior.
- Confirm no sign inversions on yaw/lateral channels.

### Block A Evidence Captured (Mid-Session)
- Control topic visibility confirmed in active graph:
	- `/control_ref/cmd_vel`
	- `/target`
	- `/mavros/setpoint_velocity/cmd_vel`
- Live command sample captured from `/control_ref/cmd_vel --once`:
	- `header.frame_id: base_link`
	- `twist.linear.x: -0.1`
	- `twist.angular.z: -0.0757`
- This confirms:
	- command frame labeling is active and explicit (`base_link`)
	- saturation boundary is active on forward axis (`vx` hit `-0.1` clamp)
- `ros2 topic echo` showed "A message was lost" warnings during subscription start; this did not block command publication and is consistent with transient BEST_EFFORT startup behavior.

### Block A Evidence Captured (Extended Stream)
- Extended `/control_ref/cmd_vel` stream confirms bounded and smooth command behavior:
	- repeated saturation at `linear.x = -0.1` (configured clamp)
	- `angular.z` remained within configured yaw bounds (about `-0.03` to `-0.098` in sampled stream)
	- slew-limited ramps repeatedly observed: `0.0 -> -0.03 -> -0.06 -> -0.09 -> -0.1`
- Timeout/freshness behavior confirmed in-stream:
	- command windows transition to full zero commands (`linear.x = 0.0`, `angular.z = 0.0`)
	- control resumes with smooth ramp-up after valid target updates
- Interpretation:
	- no stale command persistence observed through stale-target episodes
	- saturation + slew protection are active in the live unarmed loop

### Block A Evidence Captured (Sign/Axis - Partial)
- Combined `/target` + `/control_ref/cmd_vel` capture confirms these sign directions:
	- left-of-center target (`cx` well below image center) -> `angular.z < 0` (observed around `-0.03` to `-0.094`)
	- close-range target (`h` high versus reference) -> `linear.x < 0` with clamp at `-0.1`
	- no-target intervals (`id=0`) -> zero command outputs (`linear.x = 0`, `angular.z = 0`)
- Still pending for full sign matrix closure:
	- explicit right-of-center case with `angular.z > 0`
	- explicit farther-target case with `linear.x > 0`

### Block A Sign Test Attempt (Bag Replay Snapshot)
- Additional short sign-test bag recorded: `/tmp/sign_test_10s` (about 30 s, topics `/target` and `/control_ref/cmd_vel`).
- Result: inconclusive for the two remaining positive-direction checks.
- Why inconclusive:
	- sampled `cx` mostly remained left-of-center; the only near-center sample around `cx ~ 323` is inside the yaw deadband window, so positive yaw evidence was not forced.
	- sampled `h` stayed large (roughly `~390` to `~700` px), so forward command stayed in close-target regime (`linear.x <= 0`).
- Concrete thresholds for the next pass (640x640):
	- right-yaw evidence target: hold `cx > 339` px (center + deadband margin) and capture `angular.z > 0`
	- far-forward evidence target: hold `h < 160` px (below desired_h_norm 0.25) and capture `linear.x > 0`
- Decision at end of session:
	- sign-matrix closure intentionally deferred to next session to avoid over-extending bench time today.

### Block B — Integrated Target-Driven Unarmed Test
- Run target-driven command generation with props off.
- Step target across image quadrants; verify command direction/magnitude.
- Stop/restart tracker and ensure command stream safely drops/zeros.

### Block B Evidence Captured (Tracker Interruption)
- Tracker interruption test executed (unarmed): stop tracker, hold outage, restart tracker.
- Evidence artifact:
	- `Written Logs/T-31_2026-03-16_to_03-22/daily/2026-03-18__tracker-failsafe-check.md`
- Observed behavior:
	- sustained zero-command windows during interruption (`linear.x = 0.0`, `angular.z = 0.0`)
	- smooth slew-limited recovery after restart (`-0.03 -> -0.06 -> -0.09 -> -0.1`)

### Block C — Stability + Evidence Capture
- 20-30 minute continuous integrated run.
- Record bag + console logs + key timing summary.
- Note latency spikes, frame drops, and control anomalies.

### Block C Evidence Captured (Smoke Run)
- Recorded bag:
	- `bags/live_camera/2026-03-18__control_unarmed_2min_smoke`
- Bag metadata (`ros2 bag info`):
	- duration: `79.88 s`
	- messages: `4968`
	- `/control_ref/cmd_vel`: `2396`
	- `/target`: `500`
	- `/timing`: `497`
- Timing report generated:
	- `reports/timing/2026-03-18__control_unarmed_2min_smoke__timing.md`
	- figures: `figures/timing/2026-03-18__control_unarmed_2min_smoke/`
- Key timing summary (base window from `/timing`):
	- duration: `78.612 s`
	- `lat_ms`: p50 `31.27`, p95 `49.17`, p99 `58.50`
	- `loop_ms`: p50 `29.41`, p95 `47.68`, p99 `54.74`
	- achieved Hz: `/timing` `6.32`, `/target` `6.31`, `/detections` `6.31`
	- active-only detector/target rate around `14.8–15.3 Hz`
- Note:
	- This run closes smoke-level capture and baseline refresh.
	- The 20+ minute endurance gate remains open.

### Block C Evidence Captured (Full-Stack All-Topics Bag)
- Additional validation bag recorded:
	- `bags/live_camera/2026-03-19__full_stack_all_topics`
	- duration: `160.22 s`
	- size: `8.8 GiB`
	- messages: `9570`
- Topic counts (selected):
	- `/control_ref/cmd_vel`: `3898`
	- `/target`: `670`
	- `/timing`: `669`
	- `/tracks`: `667`
	- `/camera/image_raw`: `1527`
	- `/mavros/setpoint_velocity/cmd_vel`: `0`
- Timing report generated:
	- `reports/timing/2026-03-19__full_stack_all_topics__timing.md`
	- figures: `figures/timing/2026-03-19__full_stack_all_topics/`
- Timing highlights:
	- base-window duration: `159.56 s`
	- `lat_ms`: p50 `34.91`, p95 `54.70`, p99 `67.08`
	- `loop_ms`: p50 `32.90`, p95 `50.45`, p99 `57.17`
	- achieved Hz (base): around `4.18` on detections/target/timing
	- active-only detector/target rate around `15.47 Hz`
- Recorder warning observed during stop:
	- cache drops occurred under all-topics load, dominated by image-heavy capture path
	- bag remains usable for control/timing evidence but is not a clean low-loss profiling capture

### Block D — Go/No-Go Packaging
- Fill go/no-go checklist with observed evidence.
- Freeze control limits and emergency procedure.
- Document blockers and fallback plan for tomorrow.

### Block D Evidence Captured
- One-page summary created:
	- `Written Logs/T-31_2026-03-16_to_03-22/daily/2026-03-18__go-no-go-summary.md`
- Provisional decision in summary: `NO-GO` until open gates are closed (sign matrix, explicit tracker-stop failsafe evidence, and endurance-duration evidence).

---

## Thursday First-Flight Go/No-Go Checklist

- [ ] MAVROS stable with no disconnects under load
- [ ] Manual RC takeover tested live
- [ ] Control command magnitudes within agreed limits
- [ ] Kill-switch/stop sequence verified
- [ ] Control frame/sign verified with recorded test steps
- [ ] Supervisor approval recorded

**Decision:** _(GO / NO-GO)_

---

## Notes

**Issues found today:**
- Preprocessing overhead in inference path was not granularly observable.
- Potential avoidable allocation/copy overhead in camera/inference path.
- Tracker association path needed stronger performance for denser scenes.
- Control integration remains the highest operational risk before flight.

**Fixes applied today:**
- Camera path updated to RGB publish with reusable buffer.
- Inference client converted to direct numpy path with input integrity checks.
- Payload send path optimized with memoryview.
- Timing message expanded with preprocessing split metrics.
- SORT association improved with vectorized IoU/gating and reusable buffers.
- Tracker node/backend updated to support axis-specific gating parameters.

**Residual risk before first flight:**
- Control frame/sign mismatch risk until unarmed directional test is recorded.
- Need explicit evidence for timeout/failsafe behavior under target loss.
- Need integrated 20+ min run confirmation with no stale command publication.

---

## End of Day

**Readiness level for first flight (19th):** _(high / medium / low)_

**Blocked by:**
- Control closure and safety evidence still pending completion today.

**Next day focus:** Controlled first flight attempt only if control closure checklist is fully green.

---

## Final Consolidated Day-18 Decision

**Decision at close:** `NO-GO (provisional)`

**Closed today:**
- Control frame labeling confirmed (`base_link`) and bounded command behavior validated.
- Timeout/loss behavior validated with safe zeroing and smooth recovery.
- Tracker interruption failsafe validated (zero hold + slew-limited recovery).
- Smoke and extended full-stack bag evidence captured with timing reports generated.

**Still open for GO:**
- Full sign matrix closure: explicit right-target positive yaw and far-target positive forward evidence.
- Endurance gate: 20+ minute clean integrated unarmed run.
- Flight safety rehearsal evidence: RC override and emergency stop sequence logged.

## Tomorrow Gate Checklist (Before Any Flight Authority)

1. Close sign matrix with snapshot evidence:
- right case: `cx > 339` and `angular.z > 0`
- far case: `h < 160` and `linear.x > 0`

2. Record one clean 20+ min validation bag (prefer no `/camera/image_raw` to reduce cache drops).

3. Rehearse and log:
- RC override test (pass/fail + method)
- emergency stop sequence (pass/fail + exact sequence)

4. Promote decision to `GO` only if all three items above are green.
