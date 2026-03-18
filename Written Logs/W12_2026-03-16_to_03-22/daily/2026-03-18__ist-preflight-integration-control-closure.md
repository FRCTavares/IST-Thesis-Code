# Daily Log — 2026-03-18 (Day 18) — Pre-Flight Integration and Control Closure

## Overview

**Focus:** Close all technical and control safety gates required for first flight attempt on Thursday (2026-03-19).

---

## Objectives (Updated Mid-Day)

### Priority 0 — Control Must Be Closed Today
- [ ] Validate control command signs and axis mapping end-to-end (target error -> command)
- [ ] Enforce hard output saturation and minimum deadband on all control channels
- [ ] Verify command frame convention consistency (camera/body/NED) with explicit test evidence
- [ ] Confirm failsafe behavior on target loss, stale tracks, and tracker stop
- [ ] Confirm command timeout behavior (no stale command persistence)
- [ ] Perform at least one 20+ min integrated unarmed run with control active and bounded
- [ ] Document final control limits for tomorrow's flight card

### 1. Full Stack Unarmed Validation at IST
- [ ] MAVROS connected and stable for entire session
- [x] Camera -> inference -> tracker chain optimized and validated in code
- [x] Tracker matching/gating improvements integrated
- [ ] Control bridge publishes bounded commands only (field-validated)
- [ ] No crashes or watchdog resets in 20+ minute integrated run

### 2. Flight Readiness Gates
- [ ] RC override confirmed
- [ ] Emergency stop procedure rehearsed
- [ ] Command frame/sign sanity confirmed with recorded evidence
- [ ] Supervisor go/no-go criteria documented

### 3. Data Capture for Go/No-Go
- [ ] Record short validation bag and logs (control active)
- [x] Timing instrumentation expanded for preprocessing split
- [ ] Capture updated timing baseline under flight-intent setup
- [ ] Produce one-page go/no-go summary for Thursday

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

---

## Remaining Session Plan (Control-First)

### Block A — Control Sanity and Safety Envelope
- Bring up MAVROS + perception + control unarmed.
- Validate topic continuity for state, target, and command outputs.
- Verify saturation, deadband, timeout, and target-loss behavior.
- Confirm no sign inversions on yaw/lateral channels.

### Block B — Integrated Target-Driven Unarmed Test
- Run target-driven command generation with props off.
- Step target across image quadrants; verify command direction/magnitude.
- Stop/restart tracker and ensure command stream safely drops/zeros.

### Block C — Stability + Evidence Capture
- 20-30 minute continuous integrated run.
- Record bag + console logs + key timing summary.
- Note latency spikes, frame drops, and control anomalies.

### Block D — Go/No-Go Packaging
- Fill go/no-go checklist with observed evidence.
- Freeze control limits and emergency procedure.
- Document blockers and fallback plan for tomorrow.

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
