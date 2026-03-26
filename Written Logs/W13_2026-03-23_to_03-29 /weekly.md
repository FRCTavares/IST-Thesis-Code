# Weekly Plan — W13 (Control Closure Priority)

## Week Objective

Freeze and validate a thesis-defensible control chain:

`/target -> control_ref_node -> MAVROS -> ArduPilot Guided velocity behaviour`

Success is defined by:

- verified sign conventions
- bounded/safe stale and lost-target behaviour
- verified MAVROS topic/frame semantics
- repeatable ground validation evidence
- explicit GO / NO-GO gate for first supervised outdoor trials

---

## Block Plan

### Block 1 — Control Closure

1. Freeze control contract
2. Verify MAVROS frame/topic behaviour
3. Run ground sign/staleness/loss tests
4. Write GO / NO-GO gate document

**Deliverables:**

- frozen control contract checklist
- 7-case ground validation log
- frame semantics sign table
- first-outdoor control gate

### Block 2 — MAVROS Readiness

1. Verify Guided-mode command refresh behavior
2. Confirm body-frame semantics experimentally
3. Run one sustained ground test with logging
4. Decide readiness for supervised outdoor trial

**Deliverables:**

- sustained run evidence pack
- readiness decision: GO / NO-GO / CONDITIONAL-GO
- mitigation actions if not GO

## Frozen Priorities

Do now:

- control correctness and safety
- MAVROS semantic correctness
- repeatable ground validation
- gate-based decision making
- strict preparation for 2026-04-02 drone-only validation

Do not prioritize in this block:

- backend extraction
- replay endpoint implementation
- UI cosmetics
- novelty implementation or broad literature exploration
- broad test framework expansion

---

## Acceptance Criteria for This Week

- A single written control contract exists and matches runtime behavior.
- The 7-case ground validation campaign is complete and logged.
- A frozen sign semantics table is documented and validated.
- A one-page first-outdoor GO / NO-GO gate exists with measurable thresholds.
- A strict 2026-04-02 runbook and GO/NO-GO checklist are ready.
