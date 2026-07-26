# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **25 July 2026**.

Open executable issues: **25**.

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

1. [x] [#8 — P1.1 Simplify recovery confirmation](https://github.com/FRCTavares/IST-Thesis-Code/issues/8)
   - completed on 24 July 2026. One observation-based persistence tracker now owns recovery confirmation; probationary lineage remains separate from trusted selected memory until atomic acceptance; broken continuity expires staged hard-negative evidence; and validated identity evidence is retained only for the same pending candidate. Deterministic validation passed with 219 tests passed and 1 skipped.

2. [x] [#9 — P1.2 Reduce `target_memory.py`](https://github.com/FRCTavares/IST-Thesis-Code/issues/9) — DONE
   - completed on 26 July 2026 in implementation commit `931f13b63226a88cee67c1d9e391eb1dee1d7b8a`.
   - extracted mutation-free candidate acceptance policies into `candidate_safety_policy.py` and reorganized `TargetIdentityMemory` around explicit proposal evaluation, confirmation persistence, atomic trusted-state commit, selected-memory transition, appearance adaptation, and output construction.
   - reduced the candidate evaluator and acceptance path to orchestration while preserving rejection priority, diagnostics, trusted-memory provenance, and the intended evaluate–confirm–commit–adapt–output transaction.
   - validation passed with 223 tests passed and 1 skipped, successful flake8 validation, and a successful `thesis_bringup` package build.
   - deterministic development replay and the complete seven-row ablation matrix were rerun from the clean committed implementation under canonical configuration SHA-256 `e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff`.
   - the final row exactly reproduced the current P0.17 dual-oracle authority: May `0.000/0.100 s`, June Seq01 `0.000/0.000 s`, June Seq03 `0.000/0.950 s`, June Seq04 `0.000/0.250 s`, and aggregate `0.000/1.300 s` spatial/annotated-ID wrong-target duration.
   - the historical P0.28 component-matrix semantic digests remain versioned diagnostic evidence and are not used as the regression authority for the current canonical configuration.

3. [ ] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15) — CORRECTIVE IMPLEMENTED; EVIDENCE PENDING
   - started on 26 July 2026 from clean merge commit `055984a3867b5fb1bfc22615f052bc17831e61a3`; implementation checkpoint `b4c80c2b35da90e0edb765657517f6647dcec02a` added lineage-gated bootstrap and auditable `PositiveMemoryBootstrapEvent` provenance.
   - the first clean four-sequence A/B replay blocked promotion: `may_hard_reentry` produced no protected anchor, correct visible time fell from 62.513 s to 21.300 s, and wrong visible time increased from 0.100 s to 2.300 s.
   - diagnosis showed that a transient same-ID hijack-policy suppression was treated like actual tracker-ID loss: although the operator-selected ID remained continuously present, recovery reset the pre-anchor lineage to unsupported.
   - corrective work now distinguishes continuous usable operator-ID presence from true absence. Policy suppression may preserve the original pre-anchor authorization, but any prepared frame without the operator ID permanently invalidates delayed bootstrap; a later same-ID reassignment still cannot define immutable operator identity memory.
   - corrective local verification passed: the new regression was RED before implementation; 3 focused regressions, 10 protected-memory tests, 4 identity-lineage tests, the runtime-provenance regression, 224 non-linter `thesis_bringup` tests, 29 deterministic replay-runner tests, changed-file compilation, diff hygiene, and the `thesis_bringup` package build all passed.
   - a new clean committed four-sequence A/B replay, wrong-target nonincrease comparison, bootstrap-provenance audit, repeatability, and promoted evidence remain required before marking this item DONE and closing Issue #15.

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
    - phase 7; experiment; includes properly qualified held-out live evidence
      from #50 when available and must expose the event types needed to compare
      candidate loss, identity confusion, tracker fragmentation, integrated
      appearance association, and selective TIM-MARS recovery fairly.

11. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31)
    - phase 7; experiment.

12. [ ] [#58 — P1.13+ Compare lightweight tracker + TIM-MARS against integrated appearance-aware tracking](https://github.com/FRCTavares/IST-Thesis-Code/issues/58)
    - phase 7; experiment; compare separately calibrated lightweight
      appearance-free tracker + TIM-MARS systems against integrated
      appearance-aware tracker references using held-out controller-facing
      safety metrics and the canonical Issue #32 safety–availability–cost
      methodology. DeepSORT + TIM-MARS is diagnostic rather than the intended
      architecture.

13. [ ] [#54 — P1.21 Make raw-image transport, dataset recording, and live provenance explicit](https://github.com/FRCTavares/IST-Thesis-Code/issues/54)
    - phase 10; live-system; feeds #32, #37, and #50; owns the missing integrated-camera `/camera/fps` publisher and recording-contract repair, deferred until the P0 authority/coordinate/freshness blockers are complete.

14. [ ] [#32 — P1.14 End-to-end runtime, compute budget, and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; owns the canonical per-stage latency and queueing
      timebase, wall-clock versus CPU-service-time separation, p50/p90/p95/p99
      and maximum distributions, cadence/jitter/drop accounting, selective-ReID
      invocation and cache statistics, per-process/thread CPU, memory, raw-image
      DDS/QoS bandwidth, Hailo contention, sustained thermal/throttling evidence,
      and reproducible power measurements where available. It also measures the
      incremental cost of TIM-MARS and supplies the runtime contract for the
      lightweight-versus-integrated tracker comparison.

15. [x] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35) — DONE
    - Completed on 25 July 2026.
    - The obsolete anchor-drift and group-split overrides were removed from the final replay runner when the canonical TIM-MARS configuration was frozen.
    - Added a process-aware regression test that verifies each ROS parameter override is declared by its receiving node and rejects reintroduction of the obsolete experimental parameter names.

16. [x] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36) — DONE
    - Completed on 25 July 2026.
    - Replaced the generated `thesis_bringup` version, description, maintainer, and license placeholders with a consistent `0.1.0` MIT package identity.
    - Declared the package's ROS and system-Python runtime dependencies, documented the platform-specific Hailo boundary, and added a clean-checkout rosdep/build procedure.
    - Added a package-metadata regression contract and validated the complete `thesis_bringup` test suite and package build.

17. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

18. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

19. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

20. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
    - phase 9; experiment/documentation.

21. [ ] [#44 — P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)](https://github.com/FRCTavares/IST-Thesis-Code/issues/44)
    - phase 10; live-system; does not block the validated baseline flight
      profile. It must quantify CPU displacement, selective versus
      forced-frequent ReID load, detector/ReID Hailo contention, causal queueing,
      quantised-ranking equivalence, and sustained system behaviour required by
      the modular efficiency claim.

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
