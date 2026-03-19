# Daily Log — 2026-03-19 (Day 19) — First Flight Attempt

## Overview

**Focus:** First supervised flight attempt with strict safety envelope and immediate rollback path.

**Gate rule:** No flight authority handover until all pre-flight closure gates below are green.

---

## Mission Objective

- Execute first controlled flight attempt.
- Keep risk low: short windows, clear abort criteria, RC-first authority.
- End with actionable evidence for next iteration regardless of outcome.

---

## Pre-Flight Closure Gates (Must Pass First)

- [ ] **Sign matrix complete:**
	- right target (`cx > 339`) produces `angular.z > 0`
	- far target (`h < 160`) produces `linear.x > 0`
- [ ] **Endurance evidence:** one clean 20+ min integrated unarmed run recorded and analyzed
- [ ] **Safety rehearsal evidence:** RC override test + emergency stop sequence rehearsed and logged

**If any gate is open:** remain `NO-GO` for flight authority and continue ground validation only.

---

## Session Plan (4h)

### Hour 1 — Pre-Flight and Safety Brief
- [ ] Final hardware check (battery, props, links, telemetry)
- [ ] Launch stack and verify critical topics
- [ ] Close remaining pre-flight closure gates above
- [ ] Supervisor confirms flight envelope and abort triggers

### Hour 2 — Controlled Flight Window A
- [ ] Proceed only if all pre-flight gates are green
- [ ] Takeoff and stabilization under manual control
- [ ] Enable assisted behavior in short bursts
- [ ] Monitor command bounds and target stability
- [ ] Land and review immediately

### Hour 3 — Controlled Flight Window B (Conditional)
- [ ] Repeat only if Window A is clean
- [ ] Increase duration slightly (still conservative)
- [ ] Capture data for timing/control analysis

### Hour 4 — Debrief and Decision
- [ ] Classify outcome: success / partial / aborted
- [ ] Record root causes for any anomaly
- [ ] Define Friday stabilization tasks

---

## Hard Safety Rules

- [ ] RC pilot retains authority at all times
- [ ] Abort on any command instability or sensor ambiguity
- [ ] Stop if telemetry link quality degrades
- [ ] No schedule pressure overrides safety decision

---

## Outcome Template

**Flight outcome:** _(success / partial / aborted)_

**What worked:**
-

**What failed or degraded:**
-

**Immediate corrective actions (Friday):**
-

---

## Artefacts

- [ ] Logs and bag from attempt windows
- [ ] Timing snapshot before and during flight windows
- [ ] Short post-flight summary linked in weekly log
