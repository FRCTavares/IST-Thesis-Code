# Daily Log — 2026-03-12 — Outdoor Readiness Pack, Control Rehearsal, and Simulation Preparation

## Goal

Finish the field-readiness documentation, rehearse the perception-to-control interface safely, and prepare a simulation or replay workflow before attempting any real outdoor testing.

**Target outcome:**
- Outdoor field checklist completed
- Scenario sheet and bag naming frozen
- Portable bring-up procedure documented
- `control_ref_node` further validated indoors or via replay
- Safe simulation or bag-replay rehearsal path prepared
- Clear conditions defined for the first real outdoor test day

---

## Context

| Key | Value |
|-----|-------|
| Previous validation | Lean perception frozen on Day 11 |
| Control status | Ground-only `control_ref_node` validated on `/control_ref/cmd_vel` |
| Outdoor status | Not ready today, field session postponed |
| Current priority | Preparation, rehearsal, and simulation before real tests |
| Risk to avoid | Rushing into outdoor testing without full readiness |
| Test mode | Indoor only, ground-only, no flight authority |

---

## Work Plan

### A) Outdoor Readiness Pack

Prepare all logistics and field documentation before any real test day.

**Tasks:**
- [ ] Finalize outdoor field checklist
- [ ] Finalize startup procedure for field use
- [ ] Finalize shutdown procedure for field use
- [ ] Finalize field packing list
- [ ] Confirm disk space requirements and bag storage plan
- [ ] Confirm battery and cable checklist
- [ ] Freeze outdoor bag naming convention
- [ ] Prepare participant scenario sheet

**Deliverables:**
- `docs/outdoor_field_checklist.md`
- `docs/outdoor_scenarios.md`
- `docs/field_startup_shutdown.md`
- Frozen outdoor bag naming scheme

---

### B) Control Rehearsal — Indoor and Ground-Only

Continue validating the controller safely before any real-world vehicle integration.

**Tasks:**
- [ ] Re-run lean perception stack + `control_ref_node`
- [ ] Reconfirm yaw sign and forward sign
- [ ] Reconfirm zero-on-invalid behaviour
- [ ] Reconfirm smooth slew-limited commands
- [ ] Optionally record one more short indoor bag if needed
- [ ] Freeze the validated run command in documentation

**Deliverables:**
- Confirmed indoor ground-only control behaviour
- Finalized command-line invocation for `control_ref_node`
- Updated `docs/control_interface.md`

---

### C) Replay or Simulation Preparation

Prepare a safe way to rehearse controller behaviour without going outdoors.

**Tasks:**
- [ ] Decide whether tomorrow's rehearsal uses:
  - bag replay, or
  - lightweight simulation, or
  - both
- [ ] Identify which topic stream is easiest to replay into `control_ref_node`
- [ ] If using bag replay, confirm `/target` replay works
- [ ] If using simulation, define minimal synthetic target motion cases:
  - centred target
  - left/right motion
  - near/far motion
  - target loss
- [ ] Document the rehearsal method and commands

**Deliverables:**
- Safe replay or simulation rehearsal path
- Notes on what can be tested before real outdoor runs

---

### D) First Real-Test Gate Definition

Define exactly what must be true before the first outdoor session is allowed.

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
