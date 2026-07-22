# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **22 July 2026**.

Open executable issues: **39**.

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
7. Historical roadmap material remains under `docs/roadmap/archive/`.

## P0 — Safety, evidence integrity, thesis claims, and flight blockers

1. [ ] [#52 — P0.25 Restore TIM-MARS target authority and identity-safe live reconfiguration](https://github.com/FRCTavares/IST-Thesis-Code/issues/52)
   - phase 10; live-system; first flight blocker; makes TIM-MARS the only controller target authority and resets identity across runtime switches.

2. [ ] [#53 — P0.26 Unify live coordinate frames and causal image-time contracts](https://github.com/FRCTavares/IST-Thesis-Code/issues/53)
   - phase 10; live-system; flight blocker; unifies transforms and causal source-image selection across perception, tracking, TIM, UI, and evidence.

3. [ ] [#23 — P0.14 Add output freshness](https://github.com/FRCTavares/IST-Thesis-Code/issues/23)
   - phase 6; engineering; now includes source/header age and control fail-closed behavior, not only evaluator freshness.

4. [ ] [#50 — P0.23 Complete flight-readiness gate and record held-out UAV-motion evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/50)
   - phase 10; live-system; blocked by #52, #53, and the live source-age portion of #23.

5. [ ] [#51 — P0.24 Harden unattended Raspberry Pi remote access and crash recovery](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)
   - phase 10; live-system; starts only after #50; must never auto-start aircraft-affecting control.

6. [ ] [#19 — P0.12 Separate ranking from validation](https://github.com/FRCTavares/IST-Thesis-Code/issues/19)
   - phase 5; engineering; owns the unresolved incompatible-appearance/new-ID specification test.

7. [ ] [#22 — P0.13 Add evaluator tests](https://github.com/FRCTavares/IST-Thesis-Code/issues/22)
   - phase 6; engineering; complete the boundary, gap, validity, timestamp, and stale-output matrix.

8. [ ] [#24 — P0.15 Unify evaluator semantics](https://github.com/FRCTavares/IST-Thesis-Code/issues/24)
   - phase 6; experiment; depends on the tested semantics from #22 and freshness contract from #23.

9. [ ] [#27 — P0.16 Freeze tuning and test data](https://github.com/FRCTavares/IST-Thesis-Code/issues/27)
   - phase 7; experiment.

10. [ ] [#28 — P0.17 Run component ablations](https://github.com/FRCTavares/IST-Thesis-Code/issues/28)
    - phase 7; experiment; use only the frozen split and evaluator contract.

11. [ ] [#33 — P0.19 Update stale tooling documentation](https://github.com/FRCTavares/IST-Thesis-Code/issues/33)
    - phase 8; documentation; includes automated verification of UI launcher/README paths and supported commands.

12. [ ] [#34 — P0.20 Synchronize TIM documentation](https://github.com/FRCTavares/IST-Thesis-Code/issues/34)
    - phase 8; experiment; add an evidence-version map from config hashes and commits to promoted claims.

13. [ ] [#38 — P0.21 Freeze the research question](https://github.com/FRCTavares/IST-Thesis-Code/issues/38)
    - phase 9; experiment.

14. [ ] [#39 — P0.22 Freeze the claim only after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39)
    - phase 9; experiment; retain the evidence-backed rejection of universal safety portability.

## P1 — Major algorithmic, scientific, engineering, and documentation work

1. [ ] [#48 — P1.23 Restore the current thesis_bringup lint contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/48)
   - phase 8; engineering; reopened after current HEAD failed the scoped Flake8 test at `test_control_ref_safety.py:9`.

2. [ ] [#8 — P1.1 Simplify recovery confirmation](https://github.com/FRCTavares/IST-Thesis-Code/issues/8)
   - phase 2; experiment; keep reacquired lineage probationary until final confirmation.

3. [ ] [#9 — P1.2 Reduce `target_memory.py`](https://github.com/FRCTavares/IST-Thesis-Code/issues/9)
   - phase 2; documentation/refactor; preserve behavior with characterization tests.

4. [ ] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15)
   - phase 3; experiment; accepted-frame ordering is present, but complete provenance and same-ID hijack evidence remain.

5. [ ] [#17 — P1.6 Prevent target fragments becoming negatives](https://github.com/FRCTavares/IST-Thesis-Code/issues/17)
   - phase 4; engineering; prove the protection under the canonical profile and resolve the same-ID hard-negative xfail.

6. [ ] [#18 — P1.7 Add hard-negative lifecycle](https://github.com/FRCTavares/IST-Thesis-Code/issues/18)
   - phase 4; engineering; staging/merge/reconciliation exist; committed-entry age, decay decision, full provenance, and visual diagnostics remain.

7. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

8. [ ] [#21 — P1.9 Add motion evidence only if it helps](https://github.com/FRCTavares/IST-Thesis-Code/issues/21)
   - phase 5; experiment.

9. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25)
   - phase 6; experiment; use the transform contract from #53.

10. [ ] [#26 — P1.11 Add event and recovery metrics](https://github.com/FRCTavares/IST-Thesis-Code/issues/26)
    - phase 6; experiment; use the shared evaluator semantics from #24.

11. [ ] [#30 — P1.12 Add broader sequences](https://github.com/FRCTavares/IST-Thesis-Code/issues/30)
    - phase 7; experiment; includes properly qualified held-out live evidence from #50 when available.

12. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31)
    - phase 7; experiment.

13. [ ] [#32 — P1.14 Runtime and onboard cost](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; includes raw-image DDS/QoS bandwidth and sustained Pi thermal/cadence cost.

14. [ ] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35)
    - phase 8; experiment.

15. [ ] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36)
    - phase 8; documentation; now includes versions, license, ROS/Python dependencies, and clean-environment installation.

16. [ ] [#37 — P1.17 Create a single reproducibility command](https://github.com/FRCTavares/IST-Thesis-Code/issues/37)
    - phase 8; experiment; validate deterministic replay and versioned live-run provenance.

17. [ ] [#54 — P1.21 Make raw-image transport, dataset recording, and live provenance explicit](https://github.com/FRCTavares/IST-Thesis-Code/issues/54)
    - phase 10; live-system; feeds #32, #37, and #50.

18. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

19. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

20. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

21. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
    - phase 9; experiment/documentation.

22. [ ] [#44 — P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)](https://github.com/FRCTavares/IST-Thesis-Code/issues/44)
    - phase 10; live-system; does not block the validated baseline flight profile.

## P2 — Useful work after the critical path

1. [ ] [#45 — P2.x Detector (perception upgrade behind TIM — additive, low priority)](https://github.com/FRCTavares/IST-Thesis-Code/issues/45)
   - phase 10; live-system; additive and non-blocking.

2. [ ] [#49 — P2: Consolidate replay bags and define evidence retention policy](https://github.com/FRCTavares/IST-Thesis-Code/issues/49)
   - phase 8; engineering; includes the 4.52 GiB Git pack/model-artifact inventory; no history rewrite without a separate migration plan.

## P3 — Optional or stretch work

1. [ ] [#46 — P3.x Orientation gating (stretch; needs pose keypoints)](https://github.com/FRCTavares/IST-Thesis-Code/issues/46)
   - phase 10; engineering; requires pose keypoints.
