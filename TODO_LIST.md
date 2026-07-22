# TIM-MARS Active Task Queue

This file contains only open executable work.

Detailed scope, acceptance criteria, commands, experiments, and closing
evidence are maintained in the linked GitHub Issues.

## Execution rules

1. Work from the top of this file downward.
2. Finish P0 work before P1, P1 before P2, and P2 before P3.
3. Within a priority group, follow the listed dependency order.
4. Do not start a lower item merely because it is easier.
5. Wrong-target degradation blocks TIM-MARS promotion.
6. Completed or rejected issues are removed from this file.
7. Historical roadmap material is archived under `docs/roadmap/archive/`.

Active executable issues: **38**.

## P0 — Critical evidence, safety, thesis-claim, or flight-blocking work

1. [x] [#2 — P0.3 Freeze the canonical evidence set](https://github.com/FRCTavares/IST-Thesis-Code/issues/2)
   - phase 1; experiment; closed after implementation commit `39503a79be2bb86a389d0ad0062e51d700a0a860`; closure evidence recorded in GitHub Issue #2.

3. [x] [#3 — P0.4 Freeze one canonical preset — CONFIGURATION DONE; CLEAN RESULT FREEZE PENDING](https://github.com/FRCTavares/IST-Thesis-Code/issues/3)
   - phase 2; experiment; closed after implementation commit `1b7dc4002c19e5235703913826e174df1025f1d0` and evidence commit `b02d1d01fc48ec10cda1110da57d8568fb0354a2`; clean replay, resolved-runtime provenance, compact reports, evidence catalogue, and thesis-facing claims verified; closure evidence recorded in GitHub Issue #3.

4. [x] [#4 — P0.5 Prove paper-code-runner equivalence](https://github.com/FRCTavares/IST-Thesis-Code/issues/4)
   - phase 2; documentation; retired as obsolete because the referenced paper is no longer authoritative and no current thesis source is tracked in this repository; the canonical implementation, configuration, deterministic runner provenance, and clean P0.4 evidence remain the source of truth; closure rationale recorded in GitHub Issue #4.

5. [x] [#5 — P0.6 Replace parallel acceptance paths with one transactional safety gate](https://github.com/FRCTavares/IST-Thesis-Code/issues/5)
   - phase 2; experiment; completed and closed 20 July 2026; transactional candidate acceptance implemented in `bc36e553` and clean eight-run evidence recorded in `5d02c6f2`; all proposal paths share one final safety gate before state or memory mutation; provenance, evaluator, repeatability, wrong-target, and target-absence regression checks passed against canonical P0.4; ByteTrack intentionally shifts 0.200 s from correct output to LOST because the gate rejects the former rank-aware ambiguity bypass; GitHub Issue #5 closure recorded (reports/p005_transactional_gate_bc36e553_2026_07_20/candidate_comparison.json).

6. [x] [#6 — P0.6b Identify why structural safety heuristics are required](https://github.com/FRCTavares/IST-Thesis-Code/issues/6)
   - phase 2; experiment; completed and closed 21 July 2026. Implementation
     commit `03409564f5107d6808054dac12294b004d9d4381` moves hard-negative mutation after accepted role resolution,
     stages one-frame evidence outside reject-capable memory, requires
     consecutive trusted continuity observations, expires pending evidence
     after missed observations or continuity breaks, reconciles selected
     identities, and exposes auditable lifecycle events.
   - clean evidence commit `4a6b035250136ab1104dc8dc125a18e4c37e6f68` records May, Seq01, Seq03, and Seq04 comparisons
     with no wrong-target increase. The lifecycle audit recorded 49 committed
     insertions and zero invalid insertions. The existing
     `hard_negative_max_positive_similarity=1.01` safeguard remains unchanged;
     closure evidence is recorded under
     `reports/p006b_hard_negative_03409564_2026_07_21/`.

7. [x] [#7 — P0.7 Fix rank-aware bypass risks](https://github.com/FRCTavares/IST-Thesis-Code/issues/7)
   - phase 2; engineering; completed 21 July 2026.
   - Candidate-belief confirmation is composed when every candidate proposal
     is created, preventing rank-aware and future proposal sources from
     bypassing an enabled confirmation policy.
   - Implementation commit: `add2b8b87963ac26ae2551762ecccfaf119a7780`.
   - Focused validation passed 13 tests with one expected xfail; the package
     suite passed 166 tests with three expected xfails, the deterministic
     runner suite passed 40 tests, and `thesis_bringup` built successfully.
   - May, Seq01, Seq03, and Seq04 preserved all headline metrics with no
     wrong-target increase. Seq03 and Seq04 preserved replay and parsed
     event-table semantic digests exactly.
   - Closure evidence: `reports/p007_rank_aware_add2b8b8_2026_07_21/`.

8. [x] [#10 — P0.8 Fix live appearance wiring](https://github.com/FRCTavares/IST-Thesis-Code/issues/10)
   - phase 3; live-system; completed 21 July 2026.
   - Repository history confirmed that the original hardcoded `appearance_enabled:=true` defect was already absent: the live launcher passes the resolved `TARGET_MEMORY_APPEARANCE_BOOL` value.
   - Added launcher-contract regression coverage and removed obsolete HSV residue plus parsed-but-unused live appearance options. Canonical YAML remains the source of algorithm and crop-quality thresholds.
   - Validation: 3 focused launcher tests passed; 56 tooling tests passed; the functional `thesis_bringup` suite passed with 166 passed, 3 deselected, and 3 expected failures; and the package build succeeded.
   - No algorithm, threshold, annotation, replay-result, wrong-target, camera, or Hailo behavior changed as part of this launcher-only correction.

9. [ ] [#50 — P0.23 Complete flight-readiness gate and record held-out UAV-motion evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/50)
   - phase 10; live-system.

10. [ ] [#16 — P0.11 Move hard-negative updates after trusted acceptance](https://github.com/FRCTavares/IST-Thesis-Code/issues/16)
   - phase 4; experiment.

11. [ ] [#19 — P0.12 Separate ranking from validation](https://github.com/FRCTavares/IST-Thesis-Code/issues/19)
   - phase 5; engineering.

12. [ ] [#22 — P0.13 Add evaluator tests](https://github.com/FRCTavares/IST-Thesis-Code/issues/22)
   - phase 6; engineering.

13. [ ] [#23 — P0.14 Add output freshness](https://github.com/FRCTavares/IST-Thesis-Code/issues/23)
   - phase 6; engineering.

14. [ ] [#24 — P0.15 Unify evaluator semantics](https://github.com/FRCTavares/IST-Thesis-Code/issues/24)
   - phase 6; experiment.

15. [ ] [#27 — P0.16 Freeze tuning and test data](https://github.com/FRCTavares/IST-Thesis-Code/issues/27)
   - phase 7; experiment.

16. [ ] [#28 — P0.17 Run component ablations](https://github.com/FRCTavares/IST-Thesis-Code/issues/28)
   - phase 7; experiment.

17. [ ] [#29 — P0.18 Validate across trackers](https://github.com/FRCTavares/IST-Thesis-Code/issues/29)
   - phase 7; experiment.

18. [ ] [#33 — P0.19 Update stale tooling documentation](https://github.com/FRCTavares/IST-Thesis-Code/issues/33)
   - phase 8; documentation.

19. [ ] [#34 — P0.20 Synchronize TIM documentation](https://github.com/FRCTavares/IST-Thesis-Code/issues/34)
   - phase 8; experiment.

20. [ ] [#38 — P0.21 Freeze the research question](https://github.com/FRCTavares/IST-Thesis-Code/issues/38)
   - phase 9; experiment.

21. [ ] [#39 — P0.22 Freeze the claim only after final evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/39)
   - phase 9; experiment.

## P1 — Major algorithmic, scientific, engineering, and documentation work

22. [ ] [#8 — P1.1 Simplify recovery confirmation](https://github.com/FRCTavares/IST-Thesis-Code/issues/8)
   - phase 2; experiment.

23. [ ] [#9 — P1.2 Reduce `target_memory.py`](https://github.com/FRCTavares/IST-Thesis-Code/issues/9)
   - phase 2; documentation.

24. [ ] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15)
   - phase 3; experiment.

25. [ ] [#17 — P1.6 Prevent target fragments becoming negatives](https://github.com/FRCTavares/IST-Thesis-Code/issues/17)
   - phase 4; engineering.

26. [ ] [#18 — P1.7 Add hard-negative lifecycle](https://github.com/FRCTavares/IST-Thesis-Code/issues/18)
   - phase 4; engineering.

27. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

28. [ ] [#21 — P1.9 Add motion evidence only if it helps](https://github.com/FRCTavares/IST-Thesis-Code/issues/21)
   - phase 5; experiment.

29. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25)
   - phase 6; experiment.

30. [ ] [#26 — P1.11 Add event and recovery metrics](https://github.com/FRCTavares/IST-Thesis-Code/issues/26)
   - phase 6; experiment.

31. [ ] [#30 — P1.12 Add broader sequences](https://github.com/FRCTavares/IST-Thesis-Code/issues/30)
   - phase 7; experiment.

32. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31)
   - phase 7; experiment.

33. [ ] [#32 — P1.14 Runtime and onboard cost](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
   - phase 7; live-system.

34. [ ] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35)
   - phase 8; experiment.

35. [ ] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36)
   - phase 8; documentation.

36. [ ] [#48 — Flake8 test hangs in multiprocessing during full thesis_bringup suite](https://github.com/FRCTavares/IST-Thesis-Code/issues/48)
   - phase 8; engineering.
   - Audit on 21 July 2026 confirmed that both generated lint tests resolve their source paths from the process working directory, causing repository-root runs to traverse `thesis_env` and unrelated runtime outputs.
   - Package-scoped runs terminated normally with no lingering workers. The scoped baseline is 2,589 Flake8 and 108 PEP 257 findings in `thesis_bringup`, plus 246 Flake8 and 33 PEP 257 findings in `thesis_tracker`.
   - Of the 2,835 Flake8 findings, 2,495 are the cosmetic `Q000` quote-style rule. Quote and multiline-docstring placement policy must be resolved explicitly before broad mechanical cleanup.
   - Current work makes both packages’ Flake8 and PEP 257 tests independent of the pytest working directory. Genuine repository-owned findings remain visible and will be addressed before closure.
   - Correctness-first cleanup resolved all 16 correctness-sensitive findings: missing imports and helpers, dead imports and variables, and the ambiguous Kalman identity-matrix name. Both functional package suites and both package builds passed; no TIM or tracker thresholds changed.
   - The first `thesis_tracker` cleanup batch removed all import-order, imported-name-order, grouping, trailing-whitespace, missing-final-newline, and class-docstring-spacing findings. The functional suite and package build passed; line wrapping and substantive public API docstrings remain separate work.
   - The second `thesis_tracker` cleanup batch removed all `C401`, `E203`, and `E501` findings. The functional suite and package build passed; only the three Flake8 docstring-style findings and the broader PEP 257 documentation batch remain.
   - The ByteTrack documentation batch resolved all 32 ByteTrack PEP 257 targets with implementation-specific docstrings covering lifecycle states, geometry conversions, Kalman operations, tracklet transitions, collection helpers, and backend behavior. Package-wide PEP 257 findings fell from 103 to 71, ByteTrack Flake8 and PEP 257 are clean, and the functional suite and package build passed. DeepSORT, OC-SORT, SORT core, and tracker-node documentation remain.
   - The DeepSORT documentation batch resolved all 28 DeepSORT PEP 257 targets with implementation-specific docstrings covering its motion model, detection and track representations, lifecycle logic, appearance metric, MARS feature extractor, image ingestion, and association behavior. Package-wide PEP 257 findings fell from 71 to 43, DeepSORT Flake8 and PEP 257 are clean, and the functional suite and package build passed. OC-SORT, SORT core, and tracker-node documentation remain.
   - The OC-SORT documentation batch resolved all 15 OC-SORT PEP 257 targets with implementation-specific docstrings covering box-state conversion, assignment, observation-centric Kalman freezing and re-update, per-object state, lifecycle handling, and association behavior. Package-wide PEP 257 findings fell from 43 to 28, OC-SORT Flake8 and PEP 257 are clean, package-wide Flake8 has only the tracker-node `D401` finding left, and the functional suite and package build passed. SORT core and tracker-node documentation remain.
   - The SORT-core documentation batch resolved all 16 SORT-core PEP 257 targets with implementation-specific docstrings covering bounding-box geometry, the seven-state Kalman model, per-track lifecycle state, gated IoU assignment, and frame updates. Package-wide PEP 257 findings fell from 28 to 12, SORT-core Flake8 and PEP 257 are clean, the single tracker-node `D401` Flake8 finding remains, and the functional suite and package build passed. Package metadata and tracker-node documentation remain.
   - The final `thesis_tracker` lint-contract batch resolved the remaining 12 package and tracker-node documentation targets and repaired all 20 malformed public argument and return-section findings. The scoped Flake8 test now merges the ament defaults with only `Q000` and `D213` ignored and forces single-process execution; the PEP 257 test records the matching `D213` exception. Both lint tests pass from the repository root and package directory, the complete package test suite and build pass, and no tracker thresholds or runtime behavior changed. Package-wide Flake8 and PEP 257 are clean under the recorded policy.

37. [ ] [#37 — P1.17 Create a single reproducibility command](https://github.com/FRCTavares/IST-Thesis-Code/issues/37)
   - phase 8; experiment.

38. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
   - phase 9; experiment.

39. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
   - phase 9; experiment.

40. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
   - phase 9; experiment.

41. [ ] [#44 — P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)](https://github.com/FRCTavares/IST-Thesis-Code/issues/44)
   - phase 10; live-system.

## P2 — Useful work after the critical path

42. [ ] [#45 — P2.x Detector (perception upgrade behind TIM — additive, low priority)](https://github.com/FRCTavares/IST-Thesis-Code/issues/45)
   - phase 10; live-system.

43. [ ] [#49 — P2: Consolidate replay bags and define evidence retention policy](https://github.com/FRCTavares/IST-Thesis-Code/issues/49)
   - phase 8; engineering.

## P3 — Optional or stretch work

44. [ ] [#46 — P3.x Orientation gating (stretch; needs pose keypoints)](https://github.com/FRCTavares/IST-Thesis-Code/issues/46)
   - phase 10; engineering.
