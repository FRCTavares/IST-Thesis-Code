# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **24 July 2026**.

Open executable issues: **29**.

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

1. [ ] [#27 — P0.16 Freeze tuning and test data](https://github.com/FRCTavares/IST-Thesis-Code/issues/27)
   - phase 7; experiment; development/legacy inputs are frozen and hashed in `tim_mars_split_v1`. The remaining H01–H03 live capture, annotation, hashing, and people/clothing-overlap work was explicitly deferred by the operator on 23 July 2026 until September. The release gate must remain fail-closed at `final_ready=0/3`; no final held-out evaluation or threshold changes are permitted before that work resumes.

2. [ ] [#39 — P0.22 Freeze the claim only after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39)
    - phase 9; experiment; blocked until the September held-out evaluation under #27 and the required embedded-deployment evidence under #32 and #44 are complete; retain the evidence-backed rejection of universal safety portability.

## P1 — Major algorithmic, scientific, engineering, and documentation work

1. [ ] [#8 — P1.1 Simplify recovery confirmation](https://github.com/FRCTavares/IST-Thesis-Code/issues/8)
   - phase 2; experiment; keep reacquired lineage probationary until final confirmation.

2. [ ] [#9 — P1.2 Reduce `target_memory.py`](https://github.com/FRCTavares/IST-Thesis-Code/issues/9)
   - phase 2; documentation/refactor; preserve behavior with characterization tests.

3. [ ] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15)
   - phase 3; experiment; accepted-frame ordering is present, but complete provenance and same-ID hijack evidence remain.

4. [ ] [#17 — P1.6 Prevent target fragments becoming negatives](https://github.com/FRCTavares/IST-Thesis-Code/issues/17)
   - phase 4; engineering; prove the protection under the canonical profile and resolve the same-ID hard-negative xfail.

5. [ ] [#18 — P1.7 Add hard-negative lifecycle](https://github.com/FRCTavares/IST-Thesis-Code/issues/18)
   - phase 4; engineering; staging/merge/reconciliation exist; committed-entry age, decay decision, full provenance, and visual diagnostics remain.

6. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

7. [ ] [#21 — P1.9 Add motion evidence only if it helps](https://github.com/FRCTavares/IST-Thesis-Code/issues/21)
   - phase 5; experiment.

8. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25)
   - phase 6; experiment; use the transform contract from #53.

9. [ ] [#26 — P1.11 Add event and recovery metrics](https://github.com/FRCTavares/IST-Thesis-Code/issues/26)
    - phase 6; experiment; use the shared evaluator semantics from #24.

10. [ ] [#30 — P1.12 Add broader sequences](https://github.com/FRCTavares/IST-Thesis-Code/issues/30)
    - phase 7; experiment; includes properly qualified held-out live evidence from #50 when available.

11. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31)
    - phase 7; experiment.

12. [ ] [#54 — P1.21 Make raw-image transport, dataset recording, and live provenance explicit](https://github.com/FRCTavares/IST-Thesis-Code/issues/54)
    - phase 10; live-system; feeds #32, #37, and #50; owns the missing integrated-camera `/camera/fps` publisher and recording-contract repair, deferred until the P0 authority/coordinate/freshness blockers are complete.

13. [ ] [#32 — P1.14 Runtime and onboard cost](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; includes raw-image DDS/QoS bandwidth and sustained Pi thermal/cadence cost.

14. [ ] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35)
    - phase 8; experiment.

15. [ ] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36)
    - phase 8; documentation; now includes versions, license, ROS/Python dependencies, and clean-environment installation.

16. [ ] [#37 — P1.17 Create a single reproducibility command](https://github.com/FRCTavares/IST-Thesis-Code/issues/37)
    - phase 8; experiment; validate deterministic replay and versioned live-run provenance.

17. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

18. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

19. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

20. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
    - phase 9; experiment/documentation.

21. [ ] [#44 — P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)](https://github.com/FRCTavares/IST-Thesis-Code/issues/44)
    - phase 10; live-system; does not block the validated baseline flight profile.

22. [ ] [#57 — P1.23 Reorganize documentation hierarchy and promote canonical result tables](https://github.com/FRCTavares/IST-Thesis-Code/issues/57)
    - phase 8; documentation; the canonical authority map, current-result index, historical-result segregation, and initial broken-link repair are complete. Remaining work is promotion of the complete seven-row development ablation package with correction-aware interpretation and final repository-wide reference validation.

## P2 — Useful work after the critical path

1. [ ] [#51 — P2 Complete deferred physical validation for unattended Pi recovery (September)](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)
   - phase 10; live-system; deferred by the operator on 23 July 2026 until September. Remaining work is physical power/watchdog or independent-power mitigation, external-network access, key-expiry confirmation, and physical Pixhawk/AERONEXT validation.
   - Host protections already implemented remain active. This issue does not block the P0/P1 thesis-critical queue.

2. [ ] [#50 — P2 Complete flight-readiness gate and record held-out UAV-motion evidence (September)](https://github.com/FRCTavares/IST-Thesis-Code/issues/50)
   - phase 10; live-system; deferred by the operator on 23 July 2026 until September and depends on the remaining physical validation in #51.
   - No flight or retained UAV-motion evidence is required for the current P0/P1 critical path; the field procedure will be revalidated when this issue resumes.

3. [ ] [#45 — P2.x Detector (perception upgrade behind TIM — additive, low priority)](https://github.com/FRCTavares/IST-Thesis-Code/issues/45)
   - phase 10; live-system; additive and non-blocking.

4. [ ] [#49 — P2: Consolidate replay bags and define evidence retention policy](https://github.com/FRCTavares/IST-Thesis-Code/issues/49)
   - phase 8; engineering; includes the 4.52 GiB Git pack/model-artifact inventory; no history rewrite without a separate migration plan.

## P3 — Optional or stretch work

1. [ ] [#46 — P3.x Orientation gating (stretch; needs pose keypoints)](https://github.com/FRCTavares/IST-Thesis-Code/issues/46)
   - phase 10; engineering; requires pose keypoints.
