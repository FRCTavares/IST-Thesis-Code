# Daily Log — 2026-03-13 — Replay Rehearsal, MAVROS Topic Prep, and Real-Test Readiness Gate

## Goal

Rehearse the perception-to-control pipeline safely using replay or synthetic target inputs, prepare MAVROS topic-level integration on the ground, and define the final gate for the first real outdoor session.

**Target outcome:**
- Replay or synthetic `/target` rehearsal completed
- `control_ref_node` exercised in safe repeatable cases
- MAVROS topic-level message path prepared or verified, ground-only
- Outdoor readiness documents finalized
- Clear GO / NO-GO decision for the first real outdoor day

---

## Context

| Key | Value |
|-----|-------|
| Previous work | Day 11 lean mode freeze and control integration |
| Day 12 focus | Outdoor readiness pack, control rehearsal, simulation preparation |
| Control status | `control_ref_node` validated indoors on `/control_ref/cmd_vel` |
| `/target` status | Live message flow validated, pixel-space target fields understood |
| Outdoor status | Real outdoor testing postponed until preparation is complete |
| Test mode | Indoor only, ground-only, no flight authority |
| Current priority | Rehearsal, MAVROS topic prep, and readiness definition |

---

## Work Plan

### A) Finalize Outdoor Readiness Pack

Complete the documentation and logistics needed before any field session.

**Tasks:**
- [ ] Finalize outdoor field checklist
- [ ] Finalize field startup procedure
- [ ] Finalize field shutdown procedure
- [ ] Finalize packing list
- [ ] Freeze outdoor bag naming convention
- [ ] Finalize participant scenario sheet
- [ ] Confirm disk space and storage plan
- [ ] Confirm battery and cable checklist

**Deliverables:**
- `docs/outdoor_field_checklist.md`
- `docs/outdoor_scenarios.md`
- `docs/field_startup_shutdown.md`
- Frozen outdoor bag naming scheme

---

### B) Replay or Synthetic `/target` Rehearsal

Rehearse controller behaviour without needing an outdoor deployment.

**Tasks:**
- [ ] Choose rehearsal method:
  - bag replay, or
  - synthetic `/target` publisher, or
  - both
- [ ] Exercise these cases:
  - centred target
  - left target
  - right target
  - near target
  - far target
  - stale / missing target
- [ ] Verify command signs again
- [ ] Verify zero-on-invalid again
- [ ] Verify slew limiting again
- [ ] Record one short rehearsal bag if useful

**Deliverables:**
- Safe rehearsal method documented
- Rehearsal notes on command behaviour
- Optional bag with replay / synthetic control exercise

---

### C) MAVROS Topic-Level Preparation, Ground-Only

Prepare the interface to the autopilot without giving any control authority.

**Tasks:**
- [ ] Decide the MAVROS setpoint topic to target
- [ ] Confirm expected message type
- [ ] Check topic names and message flow requirements
- [ ] If possible, launch MAVROS and verify passive connectivity only
- [ ] Verify that `control_ref_node` output can be remapped or redirected cleanly
- [ ] Do not arm, do not command vehicle motion, do not test authority

**Deliverables:**
- MAVROS topic choice frozen
- Notes added to `docs/control_interface.md`
- Ground-only topic integration path documented

---

### D) Integrated Ground-Only Smoke Rehearsal

Run lean perception plus control-side nodes together again in a safe indoor setup.

**Tasks:**
- [ ] Launch lean perception stack
- [ ] Launch `control_ref_node`
- [ ] If ready, launch MAVROS passively
- [ ] Verify `/target` and control outputs coexist cleanly
- [ ] Record one short integrated smoke bag if needed

**Suggested bag topics:**
- `/camera/fps`
- `/detections`
- `/timing`
- `/target`
- `/control_ref/cmd_vel`
- optional MAVROS state topic if passive MAVROS is running

**Deliverables:**
- Short integrated rehearsal run
- Confirmation that perception and control coexist cleanly

---

### E) Real Outdoor GO / NO-GO Gate

Define exactly what must be true before the first real outdoor session is allowed.

**Tasks:**
- [ ] Write GO conditions
- [ ] Write NO-GO conditions
- [ ] List remaining blockers
- [ ] Decide whether first real outdoor session will be:
  - perception-only, or
  - perception + ground-only control monitoring

**Deliverables:**
- Explicit GO / NO-GO gate for first real outdoor day
- Updated next-step sequence

---

## Expected Outcomes

By end of Day 13, you should have:

1. **Field prep complete**
   - checklist
   - startup / shutdown procedure
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
- Better rehearsal now means cleaner real results later
