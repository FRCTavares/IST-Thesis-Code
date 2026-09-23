# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Open executable issues: **7**.

Last reconciled with GitHub: **23 September 2026**.

**Issue #64 closed on 22 September 2026 with VGA retained.** HD was not
promoted after the primary matched TIM-MARS comparison exceeded the frozen
appearance-freshness rejection ceiling, while the earlier controlled R3 study
showed no material native-HD identity benefit. The remaining eight-cell matrix
rows are explicitly retired rather than claimed as completed. Proceed with #50
physical flight-readiness/controller evidence, then #32 final mounted
characterization after the #50 controller retain/reject decision. #39 still
waits for the retained physical decisions and final runtime evidence.

The authoritative open-issue count is maintained in GitHub; this file keeps the ordered active queue.

## Execution rules

1. Work from the top of each priority group unless an issue explicitly names a
   different dependency.
2. Resolve prerequisites before downstream work; the #64 source-resolution prerequisite is complete with VGA retained. #50 is now the physical prerequisite before final #32 characterization. Thesis writing proceeds in parallel.
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
   - 22 September home preparation: Friday 25 September canonical sheet reconciled with #64 VGA decision, exact operator-event CLI, process-loss gate, three-pair comparison, DataFlash and per-run evidence checks. Passive field preflight now explicitly launches VGA. Focused software tests/build are preparation only; no physical gate was executed.
   - Post-flight reconstruction checklist and pending-only matched-pair/result tables are prepared in `docs/flight/postflight_analysis.md` and `docs/results/live/templates/`. A 22 September targeted audit added conditional ffmpeg packet-receipt bounds from existing visual timestamps and preserved finalized-file mtime in future visual status. The dashboard camera-source stamp is still absent from MKV/field MCAP, so capture-to-command identity attribution is not automatically resolved; any unresolved non-zero overlap blocks candidate promotion. No flight recorder, detector, tracker, TIM-MARS or controller behavior changed.
   - 23 September operator/readiness audit: the Friday sheet now identifies the frozen stack by full base SHA while allowing documented follow-on commits. A non-Friday VGA package rehearsal passed runtime verification, field summary, topic analysis and conditional visual packet-receipt bounds using temporary outputs. It did not supply Friday operator events, DataFlash, physical-person annotation or camera-capture-to-command alignment. The physical gates remain unchanged.
   - Remaining physical work in order: approved AERONEXT fallback provision/primary-fallback-fail-closed validation; real Pixhawk static/passive gates; controller compute-only and restrained BODY_NED/process-loss/takeover gates; pilot go/no-go; baseline and eligible matched flight trials; exact DataFlash, physical-person annotation and retain/reject decision. #50 stays open.
   - 23 September field-document compaction: `docs/flight/field_day_runbook.md` is the single compact #50 operator sheet; the previous detailed sheet is archived. Reference records are not operator instructions. Small helpers centralize exact process-loss and run verification without changing runtime behaviour.

2. [ ] [#32 — Complete end-to-end runtime and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
   - Reusable timing, provenance, selective-ReID workload and cache instrumentation is complete; the pre-#58 retained evidence gate is complete. Final live PID-tree CPU/RSS attachment and analysis tooling is implemented and locally validated, without changing production process ownership.
   - Final closure still requires the sustained integrated LIVE characterization of the mounted final Pi/camera/Hailo/controller system after a nominal 60 s warm-up and 20-minute active measurement, with complete intervals rather than active-only statistics hiding stalls. Tooling validation is not final system evidence.
   - Report final latency semantics, cadence/jitter/drop behavior, selective-ReID workload, CPU/RSS, raw-image/transport cost, temperature/clocks/throttling, accelerator contention and power where reproducibly available.
   - Final characterization must use the controller configuration retained after #50 and the appearance-source resolution retained after #64.
   - Home-side #32 runbook now has exact baseline/yaw branches, 1260 s sampler attachment, complete-interval timing, selective-ReID/cache, package/DataFlash checks and a pending-only thesis table. No final #32 measurement was run.
   - Freeze the thesis-facing runtime/resource table before closing this issue.
   - #64 prerequisite satisfied on 22 September: VGA 640x480 retained and HD not promoted. Final #32 execution now waits on the #50 controller retain/reject decision.

3. [ ] [#39 — Freeze final thesis claims after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39) — BLOCKED BY FINAL SYSTEM EVIDENCE
   - Final claim freeze remains blocked until the final embedded-deployment evidence under #32 is complete. The prospective H01/H02/H03 capture/annotation under #27 remains frozen. The #58 source-time repair, 12-cell comparison, thesis table and F19/F20 labels have been reconciled and integrated; retain the protected-first-run and repair qualifications. Hailo appearance-offload work under #44 is already closed and must be treated as completed evidence rather than an open dependency.
   - H01/H02/H03 architecture outputs have now been reproduced from the exact 16 September authority commit (`dc4c5c39`): ByteTrack, TIM-MARS and DeepSORT match their retained semantic fingerprints, all 12 frozen-v2 evaluations match, and independent Target-ReID repeats match every message timestamp and deserialised field (1,865/1,544/1,485 messages). The original Target-ReID MCAPs were pruned; retain that direct-comparison limit and the raw hash differences in provenance. All 12 corrected source-time evaluations reconcile. The old/corrected/delta tables and F19/F20 timing impact are in `docs/results/selected_target_tracking/p058_source_time_repair_20260922.*` and `p058_source_time_repair_interpretation_20260922.md`; durable reproduction/run provenance is tracked under `p058_source_time_repair_provenance_20260922/`. The frozen physical-v2 reference, scoring core and original evaluator remain unchanged.
   - Do not claim universal TIM-MARS dominance: the final held-out evidence shows a scenario-dependent comparison with DeepSORT, while TIM-MARS substantially improves safety over raw ByteTrack and retains substantially more availability than the conservative fixed-template Target-ReID baseline.
   - Remaining evidence dependencies are the #50 physical controller decision and the final sustained onboard evidence under #32. The #64 resolution decision is complete with VGA retained.
   - Final claim freeze must reconcile implementation/configuration authority, held-out evidence, embedded evidence, explicit limitations and the dissertation literature-gap matrix.
   - Preserve the existing claim boundary: controller-facing authority/evaluation and demonstrated embedded-system contributions may be discussed; established ReID/reacquisition, appearance-aware MOT, distractor reasoning, reject/abstain concepts, supervisory architectures and task-aware perception-risk principles are not standalone thesis novelty claims.

## P1 — Major scientific, thesis, and system-completion work

**Parallel thesis workstream:** thesis writing proceeds alongside the remaining field and runtime evidence work. Do not postpone evidence-safe writing while waiting for field work.

1. [ ] [#66 — Complete thesis background, related work, architecture, and evidence-safe method draft by 7 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — OVERDUE MILESTONE / IN PROGRESS
   - The original 7 September milestone has passed; retain it as historical scheduling context rather than pretending it is still a future deadline.
   - Chapters 1 and 2 have complete working drafts and have undergone visual review.
   - Chapter 3 Sections 3.1–3.8 have complete working drafts; F06 and the corrected F07 architecture figure are present, and the status QoS interface has remote actual-node validation.
   - F08 processing-sequence artwork is complete. Add the F05 platform photograph after physical access, complete final editorial review, publish the reviewed report revision, and keep a supervisor-ready compiled PDF.
   - Use the published Chapter 4 method completed under #40 as the implementation authority for remaining architecture prose; keep physical and runtime conclusions evidence-gated.

2. [ ] [#67 — Complete thesis experiments, results, and discussion draft by 30 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — ACTIVE THESIS DEADLINE
   - Produce the complete supervisor-ready dissertation draft by 30 September within the applicable MEEC page limit.
   - #27 held-out source/annotation evidence remains frozen. The #58 source-time evaluator repair has 12/12 reproduced historical cells and 12/12 reconciled corrected evaluations, with old/corrected/delta tables retained side by side. The corrected duration table and F19/F20 exact timing labels are already integrated in the Mac report checkout; preserve the repair qualification and do not propagate old values.
   - Remaining evidence-dependent results/discussion include #50 physical system evidence and #32 final onboard characterization. The #64 resolution decision is complete with VGA retained.
   - Integrate explicit limitations through #41 and final figures/evidence tables from the dissertation plan. The former #42 checklist is closed as subsumed by this issue and #39.
   - Do not invent conclusions for evidence that is still pending.

3. [ ] [#41 — Write explicit thesis limitations from final evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/41) — EVIDENCE DEPENDENT
   - Maintain explicit limitations covering small/poor-quality crops, tracker dependence, appearance-domain gap, finite held-out scope, calibration dependence, target absence, long-gap recovery limits, embedded resource constraints and the absence of formal safety guarantees.
   - #27 capture/annotation evidence remains frozen; #58 corrected source-time quantitative evidence is integrated in the Mac report with its repair qualification. The #64 retained-resolution decision is complete; final wording still depends on #50 and #32.
   - Report negative results and rejected mechanisms rather than hiding them.

4. [ ] [#68 — Complete thesis review, formatting, and final submission by 31 October 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/68)
   - Begins in earnest once the complete supervisor-ready draft exists.
   - Own supervisor revisions, proofreading, current IST/MEEC formatting compliance, abstracts/keywords, extended abstract, required declarations, final reproducibility checks, release archival and submission.
   - Do not reopen completed algorithm work unless a genuine correctness or evidence defect is found.
