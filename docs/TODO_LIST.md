# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Open executable issues: **8**.

Last reconciled with GitHub: **19 September 2026**.

**Physical access blocked until 22 September 2026:** execute #64 → #50 →
#32 in that order using `docs/flight/22-september-evidence-plan.md`. #50 stays
P0, #64 stays P1 and is a prerequisite to #32. Remote writing for #66/
#67/#41 can proceed; #39 waits for the retained physical decisions and runtime
evidence.

The authoritative open-issue count is maintained in GitHub; this file keeps the ordered active queue.

## Execution rules

1. Work from the top of each priority group unless an issue explicitly names a
   different dependency.
2. Resolve prerequisites before downstream work; #64 is the P1 resolution decision required before P0 #32. Thesis writing proceeds in parallel.
3. Wrong-target degradation, raw-target control bypass, stale-source control,
   or coordinate/time ambiguity blocks flight and TIM-MARS promotion.
4. Runtime model or tracker switching is disabled in the frozen flight profile
   until its identity-reset contract is proved.
5. Completed, rejected, or superseded issues are closed in GitHub and removed
   from this file; closure evidence stays in the issue.
6. Do not mark a task complete from code presence alone: require the issue's
   tests, build, provenance, evidence, and clean-tree contract.
7. Historical roadmap material belongs under `docs/archive/` when retained.

## P0 — Safety, evidence integrity, thesis claims, and flight blockers

1. [ ] [#50 — Complete flight readiness and retained UAV closed-loop evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/50) — FIELD REQUIRED
   - Current live-system priority. H01/H02/H03 capture and fixed-input held-out evaluation are complete and are not part of the remaining flight work.
   - Real Pixhawk/MAVROS operation, `BODY_NED`, ISR-first field networking, passive retained recording, controller authority/freshness checks, and the current field tooling have been exercised. The TIM-MARS status QoS contract is now aligned and remotely validated with the actual ROS nodes; this does not replace the remaining physical gates.
   - Complete the remaining approved field-network fallback validation and the retained physical closed-loop comparison defined with #74.
   - Physical comparison contract: matched trusted-person following, baseline hover/zero after loss versus the bounded last-trusted-direction yaw-recovery candidate, with eligible loss opportunities and observation/censoring rules declared before result inspection. Retain failed attempts, aborts and manual takeovers. Wrong-person non-zero command duration is safety blocking.
   - #74 is closed after implementation and deterministic validation; #50 owns the physical retain/reject decision.
   - The restrained/props-off command-path gate must test controller process loss during a non-zero reference and retain the FCU/setpoint response before aircraft motion.

2. [ ] [#32 — Complete end-to-end runtime and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
   - Reusable timing, provenance, selective-ReID workload and cache instrumentation is complete; the pre-#58 retained evidence gate is complete. Final live PID-tree CPU/RSS attachment and analysis tooling is implemented and locally validated, without changing production process ownership.
   - Final closure still requires the sustained integrated LIVE characterization of the mounted final Pi/camera/Hailo/controller system after a nominal 60 s warm-up and 20-minute active measurement, with complete intervals rather than active-only statistics hiding stalls. Tooling validation is not final system evidence.
   - Report final latency semantics, cadence/jitter/drop behavior, selective-ReID workload, CPU/RSS, raw-image/transport cost, temperature/clocks/throttling, accelerator contention and power where reproducibly available.
   - Final characterization must use the controller configuration retained after #50 and the appearance-source resolution retained after #64.
   - Freeze the thesis-facing runtime/resource table before closing this issue.
   - #64 is P1 but a prerequisite for this P0 measurement; complete its bounded retain/reject decision first.

3. [ ] [#39 — Freeze final thesis claims after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39) — BLOCKED BY FINAL SYSTEM EVIDENCE
   - Final claim freeze remains blocked until the final embedded-deployment evidence under #32 is complete. The prospective H01/H02/H03 evaluation under #27 and tracker comparison under #58 are complete. Hailo appearance-offload work under #44 is already closed and must be treated as completed evidence rather than an open dependency.
   - Do not claim universal TIM-MARS dominance: the final held-out evidence shows a scenario-dependent comparison with DeepSORT, while TIM-MARS substantially improves safety over raw ByteTrack and retains substantially more availability than the conservative fixed-template Target-ReID baseline.
   - Remaining evidence dependencies are the #64 resolution decision, the #50 physical controller decision, and the final sustained onboard evidence under #32.
   - Final claim freeze must reconcile implementation/configuration authority, held-out evidence, embedded evidence, explicit limitations and the dissertation literature-gap matrix.
   - Preserve the existing claim boundary: controller-facing authority/evaluation and demonstrated embedded-system contributions may be discussed; established ReID/reacquisition, appearance-aware MOT, distractor reasoning, reject/abstain concepts, supervisory architectures and task-aware perception-risk principles are not standalone thesis novelty claims.

## P1 — Major scientific, thesis, and system-completion work

**Parallel thesis workstream:** thesis writing proceeds alongside the remaining field and runtime evidence work. Do not postpone evidence-safe writing while waiting for field work.

1. [ ] [#64 — Resolve high-resolution appearance crops on representative small-target UAV footage](https://github.com/FRCTavares/IST-Thesis-Code/issues/64) — FIELD DEPENDENT / #32 PREREQUISITE
   - VGA remains the verified live default. FHD failed appearance freshness and is excluded. The controlled R3 native-HD result showed no benefit for a large target.
   - Execute the predeclared bounded VGA-versus-HD live qualification with no aircraft authority. If HD fails, retain VGA. If it passes, require one matched small/distant appearance-pixel identity comparison before changing the default.
   - Do not alter the completed H01–H03 prospective result or frozen TIM-MARS/model parameters. Record a retain/reject decision before #32 final mounted-system characterization.

2. [ ] [#66 — Complete thesis background, related work, architecture, and evidence-safe method draft by 7 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — OVERDUE MILESTONE / IN PROGRESS
   - The original 7 September milestone has passed; retain it as historical scheduling context rather than pretending it is still a future deadline.
   - Chapters 1 and 2 have complete working drafts and have undergone visual review.
   - Chapter 3 Sections 3.1–3.8 have complete working drafts; F06 and the corrected F07 architecture figure are present, and the status QoS interface has remote actual-node validation.
   - Complete the F08 processing-sequence draft, add the F05 platform photograph after physical access, publish the reviewed report revision, and keep a supervisor-ready compiled PDF.
   - Use the published Chapter 4 method completed under #40 as the implementation authority for remaining architecture prose; keep physical and runtime conclusions evidence-gated.

3. [ ] [#67 — Complete thesis experiments, results, and discussion draft by 30 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — ACTIVE THESIS DEADLINE
   - Produce the complete supervisor-ready dissertation draft by 30 September within the applicable MEEC page limit.
   - #27 and #58 final evidence are now available and should be incorporated.
   - Remaining evidence-dependent results/discussion include the #64 VGA-versus-HD resolution decision, #50 physical system evidence and #32 final onboard characterization.
   - Integrate explicit limitations through #41 and final figures/evidence tables from the dissertation plan. The former #42 checklist is closed as subsumed by this issue and #39.
   - Do not invent conclusions for evidence that is still pending.

4. [ ] [#41 — Write explicit thesis limitations from final evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/41) — EVIDENCE DEPENDENT
   - Maintain explicit limitations covering small/poor-quality crops, tracker dependence, appearance-domain gap, finite held-out scope, calibration dependence, target absence, long-gap recovery limits, embedded resource constraints and the absence of formal safety guarantees.
   - #27/#58 evidence is complete; final wording still depends on the #64 retained-resolution decision, #50 and #32.
   - Report negative results and rejected mechanisms rather than hiding them.

5. [ ] [#68 — Complete thesis review, formatting, and final submission by 31 October 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/68)
   - Begins in earnest once the complete supervisor-ready draft exists.
   - Own supervisor revisions, proofreading, current IST/MEEC formatting compliance, abstracts/keywords, extended abstract, required declarations, final reproducibility checks, release archival and submission.
   - Do not reopen completed algorithm work unless a genuine correctness or evidence defect is found.
