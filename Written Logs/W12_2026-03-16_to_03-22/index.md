# Week 12 Index (2026-03-16 to 2026-03-22)

## Week Theme
**"Integration Week" — First MAVROS hardware integration and outdoor validation at IST**

W11 was preparation. W12 is execution: bring Pi5 + Pixhawk together, validate MAVROS integration, and test perception + control outdoors.

---

## Quick Links

- [Weekly Summary](weekly.md) — Goals, results, IST sessions, integration outcomes
- [Artefacts](artefacts.md) — Code, configs, reports, datasets, field test runs

---

## Daily Logs

### Day 16 (Sunday, 2026-03-16)
**[Monday Preparation and Equipment Check](daily/2026-03-16__monday-prep-equipment-check.md)**

**Goal:** Final preparation before Tuesday IST session

**Key Tasks:**
- Pack all equipment for IST
- Review Tuesday session plan
- Verify supervisor questions answered
- Final code verification
- Equipment checklist confirmation

**Status:** *(Not started / In progress / Complete)*

---

### Day 17 (Monday, 2026-03-17)
**[Pre-IST Final Checks](daily/2026-03-17__pre-ist-final-checks.md)**

**Goal:** Last checks before tomorrow's IST session, transport preparation

**Key Tasks:**
- Final git sync
- Verify all equipment packed
- Review MAVROS launch procedure
- Review safety checklist
- Confirm field access

**Status:** *(Not started / In progress / Complete)*

---

### Day 18 (Tuesday, 2026-03-18)
**[IST Session 1 — MAVROS Ground Integration](daily/2026-03-18__ist-session-1-mavros-integration.md)**

**Goal:** First MAVROS hardware integration (4 hours at IST)

**Key Tasks:**
- Physical setup: Pi5 + Pixhawk (Ethernet)
- MAVROS connection validation
- Perception + MAVROS coexistence
- Control integration (unarmed)
- Diagnostic bags recorded

**Deliverables:**
- MAVROS connection validated
- Full pipeline running together
- Setpoint flow to Pixhawk verified
- Bags recorded for analysis
- Thursday session plan updated

**Status:** *(Not started / In progress / Complete)*

---

### Day 19 (Wednesday, 2026-03-19)
**[Tuesday Session Analysis and Thursday Planning](daily/2026-03-19__session-analysis-thursday-planning.md)**

**Goal:** Analyze Tuesday results, plan Thursday session

**Key Tasks:**
- Analyze Tuesday bags
- Document issues encountered
- Implement fixes if needed
- Finalize Thursday session plan (Option A/B/C)
- Code updates if required

**Status:** *(Not started / In progress / Complete)*

---

### Day 20 (Thursday, 2026-03-20)
**[IST Session 2 — Outdoor Validation or Debug](daily/2026-03-20__ist-session-2-outdoor-validation.md)**

**Goal:** Outdoor testing or integration debugging (4 hours at IST)

**Depends on Tuesday results:**
- **Option A:** Debug integration issues
- **Option B:** Outdoor perception validation
- **Option C:** Integrated outdoor ground test

**Deliverables:**
- Outdoor bags recorded (if applicable)
- Integration issues resolved (if applicable)
- System validated in target environment
- Field operation experience documented

**Status:** *(Not started / In progress / Complete)*

---

### Day 21 (Friday, 2026-03-21)
**[Week 12 Analysis and Documentation](daily/2026-03-21__week-analysis-documentation.md)**

**Goal:** Analyze both IST sessions, generate reports

**Key Tasks:**
- Analyze all W12 bags
- Generate timing reports
- Document integration lessons learned
- Compare outdoor vs indoor performance (if applicable)
- Update artefacts.md

**Status:** *(Not started / In progress / Complete)*

---

### Day 22 (Saturday, 2026-03-22)
**[Week 12 Review and W13 Planning](daily/2026-03-22__week-review-w13-planning.md)**

**Goal:** Complete W12 review, assess next steps

**Key Tasks:**
- Fill out W12 retrospective
- Assess readiness for next phase
- Identify blockers for future work
- Plan W13 objectives
- Update weekly.md with final results

**Status:** *(Not started / In progress / Complete)*

---

## Key Milestones

**Tuesday Minimum Success:**
- MAVROS connects to Pixhawk
- Perception runs alongside MAVROS
- Control node publishes setpoints (unarmed)

**Tuesday Target Success:**
- Setpoints flow to Pixhawk and look reasonable
- Target detection triggers control response
- Sustained operation without crashes

**Thursday Success (depends on Tuesday):**
- Outdoor perception validated OR
- Integration issues resolved OR
- Full integrated ground test completed

---

## Notes

**Critical equipment:**
- Ethernet cable (Pi5 ↔ Pixhawk)
- Laptop for SSH
- Camera and all cables
- Battery confirmed ready at IST

**Safety priority:**
- Props removed at all times
- No arming during W12
- RC override ready
- Emergency procedures known
