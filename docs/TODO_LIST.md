# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **5 August 2026**.

Open executable issues: **24**.

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
    - phase 9; experiment; blocked until the September held-out evaluation
      under #27, the lightweight-versus-integrated tracker comparison under
      #58, and the required embedded-deployment evidence under #32
      and #44 are complete. Retain the evidence-backed rejection of universal
      safety portability and do not claim an efficiency advantage without
      measured safety–availability–cost evidence.

## P1 — Major algorithmic, scientific, engineering, and documentation work


**Immediate thesis-critical algorithm freeze (target 31 August 2026):** complete or explicitly reject #26 → #25 → #64 → #21 → #31 → #30 → #58 before lower-impact cleanup. #54 is the enabling image-transport dependency. Thesis writing proceeds in parallel now; after the algorithm freeze, prioritise #32 and the final method, limitations, and figure work in #40–#42.

**Parallel thesis-writing workstream:** the thesis is not postponed until the code is finished. Complete the August chapter draft, the September full draft, and the October review/submission work alongside the algorithm and evaluation schedule.

1. [ ] [#66 — P1.T1 Write thesis background, related work, architecture, and method draft by 31 August 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM
   - target 35–45 complete pages covering the introduction, literature review, problem, system architecture and TIM-MARS method.

2. [ ] [#67 — P1.T2 Complete thesis experiments, results, and discussion draft by 30 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM
   - deliver the complete 75–90-page first draft, including datasets, evaluation, results, discussion, limitations and figures.

3. [ ] [#68 — P1.T3 Complete thesis review, formatting, and final submission by 31 October 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/68) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM
   - own supervisor revisions, proofreading, formatting, final reproducibility checks, release archival and submission.

4. [x] [#8 — P1.1 Simplify recovery confirmation](https://github.com/FRCTavares/IST-Thesis-Code/issues/8)
   - completed on 24 July 2026. One observation-based persistence tracker now owns recovery confirmation; probationary lineage remains separate from trusted selected memory until atomic acceptance; broken continuity expires staged hard-negative evidence; and validated identity evidence is retained only for the same pending candidate. Deterministic validation passed with 219 tests passed and 1 skipped.

5. [x] [#9 — P1.2 Reduce `target_memory.py`](https://github.com/FRCTavares/IST-Thesis-Code/issues/9) — DONE
   - completed on 26 July 2026 in implementation commit `931f13b63226a88cee67c1d9e391eb1dee1d7b8a`.
   - extracted mutation-free candidate acceptance policies into `candidate_safety_policy.py` and reorganized `TargetIdentityMemory` around explicit proposal evaluation, confirmation persistence, atomic trusted-state commit, selected-memory transition, appearance adaptation, and output construction.
   - reduced the candidate evaluator and acceptance path to orchestration while preserving rejection priority, diagnostics, trusted-memory provenance, and the intended evaluate–confirm–commit–adapt–output transaction.
   - validation passed with 223 tests passed and 1 skipped, successful flake8 validation, and a successful `thesis_bringup` package build.
   - deterministic development replay and the complete seven-row ablation matrix were rerun from the clean committed implementation under canonical configuration SHA-256 `e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff`.
   - the final row exactly reproduced the current P0.17 dual-oracle authority: May `0.000/0.100 s`, June Seq01 `0.000/0.000 s`, June Seq03 `0.000/0.950 s`, June Seq04 `0.000/0.250 s`, and aggregate `0.000/1.300 s` spatial/annotated-ID wrong-target duration.
   - the historical P0.28 component-matrix semantic digests remain versioned diagnostic evidence and are not used as the regression authority for the current canonical configuration.

6. [x] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15) — DONE
   - completed on 26 July 2026 against baseline `055984a3867b5fb1bfc22615f052bc17831e61a3` with corrective implementation `f1fbb7994766080481fe8cf3b9acac9862867c9b`.
   - bootstrap is allowed only while the original operator-selected lineage remains supported. Transient policy suppression preserves pre-anchor authorization only while the usable operator ID remains continuously present; true absence permanently invalidates delayed bootstrap.
   - four baseline runs, four candidate runs, and one independent Seq04 repeat completed successfully. All eight correctness and event-type evaluations passed.
   - candidate results exactly matched baseline: May `62.513/0.100/5.087 s`, Seq01 `108.750/0.000/13.590 s`, Seq03 `73.892/6.053/15.782 s`, and Seq04 `39.593/0.000/17.229 s` for correct/wrong/lost duration.
   - all four candidate sequences emitted one valid auditable bootstrap event. The corrective May case accepted frame `106` using appearance sourced from frame `104`, with supported lineage, eligible crop provenance, no ambiguity, and no hard-negative rejection.
   - Seq04 repeatability passed with semantic SHA-256 `f5b6e14c8801e9f0286f2eb8971e4c2379fb0f4430e95018e6bc96bc385819f2`.
   - promoted evidence: `reports/p015_positive_memory_bootstrap_f1fbb799_2026_07_26/`.

7. [x] [#17 — P1.6 Prevent target fragments becoming negatives](https://github.com/FRCTavares/IST-Thesis-Code/issues/17) — DONE
   - completed on 27 July 2026 from clean baseline `c32c01691e0c6281e92aeee8880fa9bf04ecb488`;
   - canonical regressions cover duplicate fragments, protected-anchor support, trusted-gallery history, and uninterrupted same-ID continuity;
   - protected positive support gates hard-negative admission; the canonical deterministic `0.95–1.01` four-sequence sweep selected `0.95`, and a second deterministic `0.95` pass reproduced identical semantic digests and evaluator metrics on all four sequences; promoted evidence is packaged under `reports/p017_fragment_safety_f1049263_2026_07_27`.
   - visual review confirmed the canonical May ByteTrack identity handover remains at `50.233 s`; `49.999–50.233 s` is now classified as `occlusion_ambiguity` with ID `1`, and annotation dropdown labels include filenames to distinguish canonical and autonomous CSVs.
   - phase 4; engineering; complete.

8. [x] [#18 — P1.7 Add hard-negative lifecycle](https://github.com/FRCTavares/IST-Thesis-Code/issues/18) — DONE
   - started on 27 July 2026 from clean synchronized baseline `bc71088ca4639f6bc75af98a5589fb246c6bff5d`.
   - read-only audit confirmed that staging, promotion, duplicate merging, bounded eviction, pending expiry, selected-lineage reconciliation, and serialized lifecycle events already exist.
   - implemented tracker-frame/time, crop-quality, confidence, full-geometry and appearance-source provenance for pending and committed prototypes; merge operations retain the earliest evidence and atomically advance the latest context.
   - status JSON now publishes committed/pending snapshots and lifecycle policy; finite expiry uses full-strength `none_until_expiry` semantics and may mutate only after uninterrupted trusted `LOCKED -> LOCKED` acceptance. The evidence-backed canonical maximum age is `247` tracker frames.
   - the live dashboard now exposes committed and pending prototype counts, tracker-frame age, maximum-age and decay policy, latest lifecycle action, lineage, observations, confidence, crop dimensions, geometry score, and expired-state warnings.
   - package validation passed with 238 tests and 1 skip; the ROS result set reported 252 tests, 0 errors and 0 failures; the `thesis_bringup` build, live-UI typecheck, and isolated production build also passed.
   - deterministic replay swept `62`, `93`, `247`, `394`, and `427` frames. The `247`-frame candidate exercised two committed expiries with zero change in correct, lost, annotated-ID wrong-target, and spatial wrong-target durations across the four frozen sequences.
   - an independent `247`-frame pass reproduced semantic digests, lifecycle payloads, evaluator metrics, source manifests, runtime resolution, and topic counts exactly.
   - the committed promoted-canonical replay at `6ba28c6133ff2e105ca6db4c17d0b0759c27b565` exactly matched the validated `247`-frame reference on semantic output, lifecycle payloads, topic counts, source manifests, runtime resolution, annotated-ID metrics, and spatial metrics.
   - final validation passed with 238 tests and 1 skip, 252 ROS tests with 0 failures and 0 errors, a successful package build, and a successful live-UI `tsc -b && vite build`.
   - completed on 28 July 2026; curated evidence is stored in `reports/p018_hard_negative_lifecycle_6ba28c61_2026_07_28`.

9. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

10. [ ] [#21 — P1.9 Add motion evidence only if it helps](https://github.com/FRCTavares/IST-Thesis-Code/issues/21) — HIGHEST PRIORITY
   - phase 5; experiment.

11. [ ] [#64 — P1.9+ Evaluate higher-resolution source frames for appearance crops while retaining 640x640 Hailo detection](https://github.com/FRCTavares/IST-Thesis-Code/issues/64) — HIGHEST PRIORITY

12. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25) — HIGHEST PRIORITY
   - phase 6; experiment; use the transform contract from #53.

13. [x] [#26 — P1.11 Add event and recovery metrics](https://github.com/FRCTavares/IST-Thesis-Code/issues/26) — DONE
    - completed and promoted for merge on 6 August 2026; the promotion commit is recorded in Git history.
    - added separate correctness, event-episode, recovery-latency, wrong-target burst, handover, recovery-attempt, suppression, state-occupancy and memory-lifecycle metrics without changing TIM-MARS runtime policy or canonical parameters.
    - canonical four-sequence evidence at `b50f914a` passed all stored hashes, an identical deterministic rerun and 81 focused tests.
    - tracked interpretation: `docs/results/selected_target_tracking/p026_event_recovery_metrics.md`.

14. [ ] [#30 — P1.12 Add broader sequences](https://github.com/FRCTavares/IST-Thesis-Code/issues/30) — IN PROGRESS — HIGHEST PRIORITY
    - started on 6 August 2026 from baseline `f1f02ebb` on branch
      `issue-30-broader-sequences`.
    - phase 7; experiment; includes properly qualified held-out live evidence
      from #50 when available and must expose the event types needed to compare
      candidate loss, identity confusion, tracker fragmentation, integrated
      appearance association, and selective TIM-MARS recovery fairly.
    - external benchmark scope: freeze a manageable subset of approximately four MOT17, four to six DanceTrack, and four VisDrone-MOT sequences; evaluate both oracle-candidate and detector–ByteTrack–TIM-MARS modes alongside the four ROS 2 sequences.
    - current milestone: define the dataset-neutral annotation, coordinate,
      target-selection, storage, provenance and manifest contracts before any
      dataset download or outcome review.
    - implementation plan: `docs/issues/p1-12-broader-sequences.md`.
    - adapter slice 1: dataset-neutral MOTChallenge and VisDrone annotation
      parsing with source-row and source-geometry provenance, explicit
      exclusions, geometric-edge clipping, frame–identity uniqueness and
      synthetic tests; no external data has been downloaded.
    - evaluation invariant: TIM-MARS is not treated as another tracker; every
      run must remain anchored to the physical person selected during the
      frozen initialization frames, even when tracker IDs later change.
    - initialization slice 2: map the frozen physical dataset identity to a
      unique tracker candidate using IoU, ambiguity margin and consecutive
      confirmation; fix that tracker ID after initialization and never
      reselect a different physical person.
    - adapter slice 3: explicit DanceTrack sequence metadata and annotation
      compatibility using deterministic MOT-style normalization and synthetic
      fixtures; no DanceTrack data has been downloaded.
    - selection slice 4: deterministic annotation-derived target-candidate
      analysis covering visibility, initialization quality, border contact and
      person competition without using TIM-MARS outcomes.
    - acquisition slice 5: tracked official-source, admissible-split, storage,
      free-space, archive-hash and MOT17 scene-deduplication contract; downloads
      remain manual and no archive has been acquired.


15. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31) — HIGHEST PRIORITY
    - phase 7; experiment.

16. [ ] [#58 — P1.13+ Compare lightweight tracker + TIM-MARS against integrated appearance-aware tracking](https://github.com/FRCTavares/IST-Thesis-Code/issues/58) — HIGHEST PRIORITY
    - phase 7; experiment; compare separately calibrated lightweight
      appearance-free tracker + TIM-MARS systems against integrated
      appearance-aware tracker references using held-out controller-facing
      safety metrics and the canonical Issue #32 safety–availability–cost
      methodology. DeepSORT + TIM-MARS is diagnostic rather than the intended
      architecture.

17. [ ] [#54 — P1.21 Make raw-image transport, dataset recording, and live provenance explicit](https://github.com/FRCTavares/IST-Thesis-Code/issues/54) — THESIS-CRITICAL DEPENDENCY
    - phase 10; live-system; feeds #32, #37, and #50; owns the missing integrated-camera `/camera/fps` publisher and recording-contract repair, deferred until the P0 authority/coordinate/freshness blockers are complete.

18. [ ] [#32 — P1.14 End-to-end runtime, compute budget, and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; owns the canonical per-stage latency and queueing
      timebase, wall-clock versus CPU-service-time separation, p50/p90/p95/p99
      and maximum distributions, cadence/jitter/drop accounting, selective-ReID
      invocation and cache statistics, per-process/thread CPU, memory, raw-image
      DDS/QoS bandwidth, Hailo contention, sustained thermal/throttling evidence,
      and reproducible power measurements where available. It also measures the
      incremental cost of TIM-MARS and supplies the runtime contract for the
      lightweight-versus-integrated tracker comparison.

19. [x] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35) — DONE
    - Completed on 25 July 2026.
    - The obsolete anchor-drift and group-split overrides were removed from the final replay runner when the canonical TIM-MARS configuration was frozen.
    - Added a process-aware regression test that verifies each ROS parameter override is declared by its receiving node and rejects reintroduction of the obsolete experimental parameter names.

20. [x] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36) — DONE
    - Completed on 25 July 2026.
    - Replaced the generated `thesis_bringup` version, description, maintainer, and license placeholders with a consistent `0.1.0` MIT package identity.
    - Declared the package's ROS and system-Python runtime dependencies, documented the platform-specific Hailo boundary, and added a clean-checkout rosdep/build procedure.
    - Added a package-metadata regression contract and validated the complete `thesis_bringup` test suite and package build.

21. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

22. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

23. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

24. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
    - phase 9; experiment/documentation.

## P2 — Useful work after the critical path

1. [ ] [#51 — P2 Complete deferred physical validation for unattended Pi recovery (September)](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)
   - the software recovery defect demonstrated on 25 July 2026 is repaired and validated.
   - unattended mode now separates configured connectivity from verified default-gateway reachability.
   - three consecutive reachability failures trigger one bounded `wlan0` reconnect; six failures trigger one bounded NetworkManager restart with an independent cooldown.
   - real installed-system tests proved Tailscale restart, Wi-Fi reconnect, NetworkManager escalation, network recovery, SSH recovery, Tailscale recovery, timer restoration, and production-state isolation.
   - 15 focused host-health tests pass, the repository and deployed monitor checksums match, and the production timer reports healthy gateway, network, SSH, and Tailscale state.
   - the issue remains open only for the previously deferred September gates: physical power restoration, watchdog or independent-power mitigation, genuinely external Tailnet SSH, key-expiry confirmation, and physical Pixhawk/AERONEXT mode validation.

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
