# T-31 Index (2026-03-16 to 2026-03-22)

## Week Theme
**"Integration Week" — First MAVROS hardware integration and outdoor validation at IST**

T-32 was preparation. T-31 is execution: bring Pi5 + Pixhawk together, validate MAVROS integration, and test perception + control outdoors.

---

## Quick Links

- [Weekly Summary](weekly.md) — Goals, results, IST sessions, integration outcomes
- [Artefacts](artefacts.md) — Code, configs, reports, datasets, field test runs

---

## Daily Logs

### Day 16 (Sunday, 2026-03-16)
**[ROS Graph + Dashboard Integration and One-Command Startup](daily/2026-03-16__ros-graph-dashboard-and-one-command-start.md)**

**Goal:** Integrate full live graph with frontend dashboard and simplify operations with one-command startup

**Key Tasks:**
- Integrate dashboard bridge + web video path with live ROS graph
- Build and harden `tools/start_live_stack.sh`
- Add startup checks and cleaner stop behavior
- Establish repeatable run/log workflow

**Status:** Complete

---

### Day 17 (Monday, 2026-03-17)
**[Timing Ablation and Startup Script Hardening](daily/2026-03-17__timing-ablation-and-start-script-hardening.md)**

**Goal:** Validate timing instrumentation, run ablation measurements, and improve startup modes

**Key Tasks:**
- Add timing invariant checker and live stats collector
- Run R1-R5 timing ablation set and summarize bottlenecks
- Improve startup script modes (`--no-dashboard`, tracker/web-video/rosbag toggles)
- Fix target timing context fallback and verify e2e_target

**Status:** Complete

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

### Day 19 (Thursday, 2026-03-19)
**[First Flight Attempt](daily/2026-03-19__first-flight-attempt.md)**

**Goal:** Execute first supervised flight attempt with strict safety gates

**Key Tasks:**
- Final pre-flight and RC override checks
- Run short, controlled assisted-flight windows
- Capture logs and timing evidence
- Debrief and classify outcome (success/partial/aborted)
- Define immediate stabilization actions

**Status:** *(Not started / In progress / Complete)*

---

### Day 20 (Friday, 2026-03-20)
**[Post-Flight Stabilization](daily/2026-03-20__ist-session-2-outdoor-validation.md)**

**Goal:** Triage first-flight evidence and close highest-priority blockers

**Key Tasks:**
- Build first-flight event timeline from logs
- Implement highest-impact safety/robustness fix
- Re-validate on bench/unarmed setup
- Decide retry scope and explicit gating criteria

**Deliverables:**
- Root-cause shortlist
- Stabilization fixes and validation notes
- Clear next-attempt decision

**Status:** *(Not started / In progress / Complete)*

---

### Day 21 (Saturday, 2026-03-21)
**[Flight Analysis and Evidence Packaging](daily/2026-03-21__week-analysis-documentation.md)**

**Goal:** Analyze both IST sessions, generate reports

**Key Tasks:**
- Analyze all T-31 bags
- Generate timing reports
- Document integration lessons learned
- Compare outdoor vs indoor performance (if applicable)
- Update artefacts.md

**Status:** *(Not started / In progress / Complete)*

---

### Day 22 (Sunday, 2026-03-22)
**[T-31 Review and T-30 Planning](daily/2026-03-22__week-review-w13-planning.md)**

**Goal:** Complete T-31 review, assess next steps

**Key Tasks:**
- Fill out T-31 retrospective
- Assess readiness for next phase
- Identify blockers for future work
- Plan T-30 objectives
- Update weekly.md with final results

**Status:** *(Not started / In progress / Complete)*

---

## Key Milestones

**Wednesday Pre-Flight Gate Success:**
- MAVROS and perception/control stack stable unarmed
- Safety/override checks validated
- Go/no-go criteria completed

**Thursday First-Flight Success:**
- At least one controlled assisted-flight window completed safely
- Commands remain bounded and recoverable
- Evidence captured for post-flight triage

**Friday Stabilization Success:**
- Top blocker identified and mitigated
- Bench/unarmed re-validation passes
- Clear next-attempt scope defined

---

## Notes

**Critical equipment:**
- Ethernet cable (Pi5 ↔ Pixhawk)
- Laptop for SSH
- Camera and all cables
- Battery confirmed ready at IST

**Safety priority:**
- RC override ready and tested before each run
- Supervisor-controlled arming decision only
- Abort criteria explicit and rehearsed
- Emergency procedures known
