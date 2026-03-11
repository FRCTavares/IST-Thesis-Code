# Daily Log — 2026-03-14 — First Real Outdoor Bring-Up and Exploratory Validation

## Goal

Take the frozen lean perception stack to the real outdoor environment, verify that bring-up works reliably outside the lab, and record a small set of exploratory outdoor bags to assess detection, target selection, and optional ground-only control coexistence.

**Target outcome:**
- Outdoor checklist executed successfully
- Lean stack brought up outdoors without major issues
- At least 1 to 2 outdoor exploratory bags recorded
- Real-world issues documented: lighting, distance, target size, multi-person ambiguity
- Clear decision on whether a larger outdoor session is justified next

---

## Context

| Key | Value |
|-----|-------|
| Previous work | Day 11 lean freeze and control integration, Day 12-13 preparation and rehearsal |
| Operational mode | Lean perception mode only |
| Test mode | Outdoor, ground-only, no flight authority |
| Control status | `control_ref_node` validated indoors on `/control_ref/cmd_vel` |
| MAVROS status | Topic prep may exist, but no vehicle authority assumed |
| Main risk | Outdoor lighting and setup issues, not flight safety yet |
| Success definition | Clean outdoor bring-up and useful exploratory evidence |

---

## Work Plan

### A) Pre-Departure Checklist

Finish the field-ready setup before leaving.

**Tasks:**
- [ ] Run golden-state checks
- [ ] Verify lean startup sequence is available
- [ ] Confirm disk space for bags
- [ ] Confirm power setup, cables, monitor/laptop, mounts
- [ ] Bring printed or local copy of outdoor checklist
- [ ] Confirm participants and location availability
- [ ] Confirm lighting / weather conditions acceptable

**Deliverables:**
- Pre-departure checklist completed
- System ready for transport

---

### B) Outdoor Bring-Up Gate

Do not expand testing until the system proves it can run outdoors.

**Tasks:**
- [ ] Set up at test location
- [ ] Launch lean perception stack
- [ ] Verify `/camera/fps`
- [ ] Verify `/detections`
- [ ] Verify `/target`
- [ ] Check basic visual quality and exposure
- [ ] Optionally launch `control_ref_node` on `/control_ref/cmd_vel` only

**Proceed only if all are true:**
- ✓ camera feed usable outdoors
- ✓ detections alive
- ✓ target alive
- ✓ no major bring-up errors
- ✓ no obvious exposure failure

**If any fail:**
- record one short diagnostic bag
- document issue
- stop scenario expansion

**Deliverables:**
- Outdoor bring-up result
- GO / NO-GO for scenario recording

---

### C) Exploratory Scenario 1 — Single Person Distance Sweep

**Objective:** Check basic outdoor detectability and target quality versus distance.

**Procedure:**
- [ ] One person at about 5 m
- [ ] Then about 10 m
- [ ] Then about 15 m if feasible
- [ ] Then back inward
- [ ] Record short bag: `bags/live_camera/2026-03-14__outdoor__scenario1__single_distance`

**What to observe:**
- detection presence
- target stability
- bbox size changes with distance
- obvious range limit

**Deliverables:**
- Scenario 1 bag
- Short qualitative notes

---

### D) Exploratory Scenario 2 — Two People

**Objective:** Check whether multi-person outdoor scenes remain manageable.

**Procedure:**
- [ ] Two people in frame
- [ ] Change relative position slowly
- [ ] Include mild crossing or ambiguity
- [ ] Record short bag: `bags/live_camera/2026-03-14__outdoor__scenario2__two_people`

**What to observe:**
- both people detected
- target stability
- obvious confusion or switching
- whether outdoor clutter affects selection

**Deliverables:**
- Scenario 2 bag
- Short qualitative notes

---

### E) Optional Ground-Only Control Coexistence

Only do this if outdoor perception is already stable.

**Tasks:**
- [ ] Launch `control_ref_node` on `/control_ref/cmd_vel`
- [ ] Verify it consumes outdoor `/target`
- [ ] Do not connect vehicle authority
- [ ] Optionally record: `/control_ref/cmd_vel`

**Deliverables:**
- Outdoor perception-to-control coexistence note
- Optional bag evidence

---

### F) Quick Post-Run Review

Do a fast evidence review after returning.

**Tasks:**
- [ ] Run `ros2 bag info` on recorded bags
- [ ] Confirm expected topics exist
- [ ] Write immediate findings:
  - lighting / exposure
  - distance limit
  - target size issues
  - multi-person issues
  - outdoor setup issues
- [ ] Decide next step:
  - larger outdoor session
  - targeted fixes first
  - repeat exploratory session

**Deliverables:**
- Short outdoor notes
- Decision for next real-world session

---

## Expected Outcomes

By end of Day 14, you should have:

1. **Proof the stack can be brought outdoors**
   - or a documented reason why not

2. **At least 1 to 2 useful outdoor bags**
   - single-person distance sweep
   - two-person exploratory case

3. **Real outdoor observations**
   - lighting behaviour
   - distance limit
   - target quality
   - multi-person behaviour

4. **A grounded next-step decision**
   - expand outdoor testing
   - fix issues first
   - repeat controlled exploratory run

---

## Not the Goal of Day 14

Do not make Day 14 about:
- pre-flight safety validation
- geofence enforcement
- altitude limit validation
- emergency stop latency claims
- battery-to-flight endurance claims
- flight readiness GO / NO-GO

Those belong later, after:
- outdoor perception is stable
- MAVROS path is better understood
- vehicle authority path is actually integrated

---

## Issues and Risks

### Likely issues
- outdoor exposure / glare
- weaker detection at long range
- target instability in clutter
- setup friction in the field
- lower-than-expected rate outdoors

### Adaptation strategy
- if lighting is poor, move to shade or adjust orientation
- if range is poor, keep exploratory distances shorter
- if multi-person is unstable, treat that as evidence, not failure
- if bring-up is flaky, record one diagnostic bag and stop expanding scope

---

## Notes

- This is the first real outdoor evidence day, not the final protocol
- Keep bags short and purposeful
- Do not revert to heavy profiling mode
- Do not claim flight readiness from this day
- The purpose is to learn what the outdoor environment actually does to your stack
