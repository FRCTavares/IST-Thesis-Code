# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Open executable issues: **13**.

Last reconciled with GitHub: **17 September 2026**.

The authoritative open-issue count is maintained in GitHub; this file keeps the ordered active queue.

## Execution rules

1. Work from the top of each priority group unless an issue explicitly names a
   different dependency.
2. Finish P0 before P1, P1 before P2, and P2 before P3.
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
   - Real Pixhawk/MAVROS operation, `BODY_NED`, ISR-first field networking, passive retained recording, controller authority/freshness checks, and the current field tooling have been exercised. Remaining aircraft work must still satisfy the current fail-closed flight-day contract.
   - Complete the remaining approved field-network fallback validation and the retained physical closed-loop comparison defined with #74.
   - Physical comparison contract: matched trusted-person following, baseline hover/zero after loss versus the bounded last-trusted-direction yaw-recovery candidate, with eligible loss opportunities and observation/censoring rules declared before result inspection. Retain failed attempts, aborts and manual takeovers. Wrong-person non-zero command duration is safety blocking.
   - #74 controller implementation and deterministic validation are complete; #50 owns the physical retain/reject decision.

2. [ ] [#32 — Complete end-to-end runtime and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
   - Reusable timing, provenance, selective-ReID workload, cache and resource instrumentation is complete, and the pre-#58 retained evidence gate is complete.
   - Final closure still requires sustained integrated LIVE characterization of the mounted final Pi/camera/Hailo/controller system, with complete intervals rather than active-only statistics hiding stalls.
   - Report final latency semantics, cadence/jitter/drop behavior, selective-ReID workload, CPU/RSS, raw-image/transport cost, temperature/clocks/throttling, accelerator contention and power where reproducibly available.
   - Final characterization must use the controller configuration retained after #50/#74 and the appearance-source resolution retained after #64.
   - Freeze the thesis-facing runtime/resource table before closing this issue.
   - Cross-priority dependency exception: the bounded #64 resolution decision may be completed before this P0 item because #32 depends on that result.

3. [ ] [#39 — Freeze final thesis claims after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39) — BLOCKED BY FINAL SYSTEM EVIDENCE
   - Final claim freeze remains blocked until the final embedded-deployment evidence under #32 is complete. The prospective H01/H02/H03 evaluation under #27 and tracker comparison under #58 are complete. Hailo appearance-offload work under #44 is already closed and must be treated as completed evidence rather than an open dependency.
   - Do not claim universal TIM-MARS dominance: the final held-out evidence shows a scenario-dependent comparison with DeepSORT, while TIM-MARS substantially improves safety over raw ByteTrack and retains substantially more availability than the conservative fixed-template Target-ReID baseline.
   - Remaining evidence dependencies are the #64 resolution decision, the #50/#74 physical controller decision, and the final sustained onboard evidence under #32.
   - Final claim freeze must reconcile implementation/configuration authority, held-out evidence, embedded evidence, explicit limitations and the dissertation literature-gap matrix.
   - Preserve the existing claim boundary: controller-facing authority/evaluation and demonstrated embedded-system contributions may be discussed; established ReID/reacquisition, appearance-aware MOT, distractor reasoning, reject/abstain concepts, supervisory architectures and task-aware perception-risk principles are not standalone thesis novelty claims.

## P1 — Major scientific, thesis, and system-completion work

**Parallel thesis workstream:** thesis writing proceeds alongside the remaining P0/P2 evidence work. Do not postpone evidence-safe writing while waiting for field work.

1. [ ] [#66 — Complete thesis background, related work, architecture, and evidence-safe method draft by 7 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — OVERDUE MILESTONE / IN PROGRESS
   - The original 7 September milestone has passed; retain it as historical scheduling context rather than pretending it is still a future deadline.
   - Chapters 1 and 2 have complete working drafts and have undergone visual review.
   - Chapter 3 Sections 3.1–3.8 have complete working drafts; the hardware and ROS 2 architecture figures are present.
   - Finish the remaining Chapter 3 visual/implementation-consistency pass and keep a supervisor-ready compiled PDF.
   - Draft only evidence-safe method material here. #40 remains the authority for final TIM-MARS method wording.

2. [ ] [#67 — Complete thesis experiments, results, and discussion draft by 30 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — ACTIVE THESIS DEADLINE
   - Produce the complete supervisor-ready dissertation draft by 30 September within the applicable MEEC page limit.
   - #27 and #58 final evidence are now available and should be incorporated.
   - Remaining evidence-dependent results/discussion include the bounded #64 study, #50/#74 physical system evidence and #32 final onboard characterization.
   - Integrate explicit limitations through #41 and final figures/evidence tables through #42.
   - Do not invent conclusions for evidence that is still pending.

3. [ ] [#74 — Validate state-aware selected-person following and bounded visual recovery](https://github.com/FRCTavares/IST-Thesis-Code/issues/74) — IMPLEMENTATION COMPLETE / PHYSICAL DECISION PENDING
   - Do not reopen controller design: state-aware authority wiring, controller diagnostics and bounded yaw-only recovery implementation/deterministic validation are complete.
   - TIM-MARS remains the sole selected-person identity authority; raw targets, tracks and unconfirmed candidates never gain controller authority.
   - The only remaining scientific question is the physical baseline-versus-bounded-yaw comparison owned operationally by #50.
   - If eligible physical trials show no defensible recovery benefit, reject active yaw recovery and retain conservative hover/zero behavior rather than redesigning the mechanism.
   - Close #74 only after the #50 physical retain/reject decision is documented.

4. [ ] [#40 — Write TIM-MARS method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40) — GITHUB STATUS: BLOCKED
   - The historical #89/#90 algorithm blocker is resolved and the final prospective TIM-MARS algorithm/configuration authority is frozen.
   - Final method prose must reflect the actual promoted implementation, including state transitions, trusted/protected appearance memory, hard-negative behavior, source-aware adaptive-memory update suppression, local/global reacquisition and controller-facing authority semantics.
   - Keep algorithmic TIM-MARS method claims separate from the later closed-loop #50/#74 systems experiment.
   - Reconcile the GitHub `status:blocked` label separately if the remaining method-writing dependency is judged resolved; do not silently reinterpret the live label here.

5. [ ] [#41 — Write explicit thesis limitations from final evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/41) — EVIDENCE DEPENDENT
   - Maintain explicit limitations covering small/poor-quality crops, tracker dependence, appearance-domain gap, finite held-out scope, calibration dependence, target absence, long-gap recovery limits, embedded resource constraints and the absence of formal safety guarantees.
   - #27/#58 evidence is complete; final wording still depends on #64, #50/#74 and #32.
   - Report negative results and rejected mechanisms rather than hiding them.

6. [ ] [#42 — Complete final thesis figures and evidence tables](https://github.com/FRCTavares/IST-Thesis-Code/issues/42) — IN PROGRESS
   - Chapter 1 and Chapter 2 visual passes are complete.
   - Chapter 3 hardware and ROS 2 architecture figures are complete.
   - Incorporate the final H01–H03 architecture-comparison evidence, failure-case illustrations and controller/system evidence as it becomes available.
   - Final runtime/resource tables depend on #32.
   - Keep figure values tied to promoted evidence and reproducible source paths.

7. [ ] [#68 — Complete thesis review, formatting, and final submission by 31 October 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/68)
   - Begins in earnest once the complete supervisor-ready draft exists.
   - Own supervisor revisions, proofreading, current IST/MEEC formatting compliance, abstracts/keywords, extended abstract, originality and AI-use declarations, final reproducibility checks, release archival and submission.
   - Do not reopen completed algorithm work unless a genuine correctness or evidence defect is found.

## P2 — Deferred maintenance and bounded supporting evidence

1. [ ] [#64 — Resolve high-resolution appearance crops on representative small-target UAV footage](https://github.com/FRCTavares/IST-Thesis-Code/issues/64) — SOURCE PREPARATION READY / MATCHED EVALUATION PENDING
   - The earlier controlled native-HD experiment showed no benefit for a close, large target and therefore did not answer the intended small/distant-person question.
   - A representative drone-POV native-FHD development master was captured on 15 September and independently backed up.
   - Exact source-frame timing can now be preserved from the MKV into a native-MCAP `zstd_fast` `/camera/image_raw` source bag; the adapter and matched-resolution variant storage path have focused tests and an end-to-end smoke, but the real FHD comparison has not yet been run.
   - Complete one bounded matched-resolution study from that unchanged master, comparing higher-resolution appearance evidence against its derived lower-resolution condition while keeping detector/tracker/TIM interpretation fixed.
   - Keep Hailo detector inference at 640x640. Do not turn this into detector redesign, a new ReID-model study or an outcome-driven change to the completed H01–H03 prospective evaluation.
   - If no material difficult-event identity benefit appears, record the negative result and close #64.
   - #64 must be resolved before final #32 characterization because the retained appearance-source resolution changes the final onboard resource profile.

2. [ ] [#20 — Rename misleading TIM-MARS geometry fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20) — MAINTENANCE / NON-BLOCKING
   - The terminology problem remains valid but is not a current scientific blocker.
   - Rename misleading geometry fields consistently across implementation, configuration, tests and documentation without changing behavior.
   - Prefer completing this before final method/documentation freeze if schedule permits.

## P3 — Optional or evidence-triggered work

1. [ ] [#45 — Evaluate detector upgrades only if final evidence shows a recall bottleneck](https://github.com/FRCTavares/IST-Thesis-Code/issues/45) — PAUSED
   - YOLOv8s remains the canonical detector.
   - Do not start a detector-upgrade experiment unless final evidence identifies detector recall as a material bottleneck relevant to the thesis conclusions.
   - If no such evidence appears, close the issue as `not planned`.
