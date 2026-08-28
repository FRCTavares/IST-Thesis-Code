# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **28 August 2026**.

Open executable issues: **20**.

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
      #58, and the final embedded-deployment evidence under #32 are complete.
      The dedicated Hailo appearance-offload work under #44 is already closed
      and must be incorporated as completed evidence rather than treated as an
      open dependency. Retain the evidence-backed rejection of universal safety
      portability and do not claim an efficiency advantage without measured
      safety–availability–cost evidence. Final claim freeze must also include a
      literature-gap audit against the completed dissertation literature matrix,
      separating established target-person tracking, ReID/reacquisition,
      distractor reasoning, appearance-aware MOT, open-set identity rejection,
      online continual Target-ReID, selective ReID, reject/abstain concepts,
      supervisory runtime/perception-assurance architectures, and task-aware
      perception-risk reasoning from the controller-facing authority, evaluation,
      and embedded-system contributions actually demonstrated by the thesis.

## P1 — Major algorithmic, scientific, engineering, and documentation work


**Immediate thesis-critical implementation and evaluation path (target 7 September 2026):** complete or explicitly reject #25 → #64 → #21 → #58 → #74 → #32. Issue #74 completes the final state-aware controller-facing architecture before #32 measures the promoted onboard system. Thesis writing continues in parallel through #66–#68; #40–#42 remain the final method, limitations, and figure workstream.

**Parallel thesis-writing workstream:** the thesis is not postponed until the code is finished. Complete the architecture and evidence-safe method catch-up by 7 September, the supervisor-ready full draft by 30 September, and the review/submission work by 31 October alongside the algorithm and evaluation schedule.

**Planned travel pause and restart:** thesis and repository work pauses after 10 August 2026 and resumes on 25 August 2026. No thesis or algorithm progress is assumed during 11--24 August. The first writing task on return is Chapter 3 Section 3.3, Software and ROS 2 Architecture; Sections 3.1 System Requirements and 3.2 Hardware Platform already have a clean compiled pre-travel working draft. From 25 August, prioritise completion of Chapter 3, the evidence-safe Chapter 4 method draft, and the remaining thesis-critical algorithm freeze. The algorithm-freeze target is rebaselined to 7 September to account for the planned pause. The September supervisor-ready full-draft milestone and 31 October final-submission deadline remain unchanged unless later evidence requires another explicit replan.

1. [ ] [#66 — P1.T1 Write thesis background, related work, architecture, and method draft by 7 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM — IN PROGRESS
   - thesis writing formally started on 9 August 2026. Official IST/MEEC directives, the current Técnico LaTeX template, three recent Técnico dissertations, and PIC2 as pre-thesis source material have been audited. The seven-chapter dissertation architecture, page budget, writing style, figure/table plan, claim-evidence plan, and local dissertation workspace are established.
   - the official Técnico v13 LaTeX base has now been integrated into the local-only dissertation workspace and the seven-chapter skeleton successfully compiles with TeX Live 2026. Structure PDF v0.1 was visually checked and the resulting front-matter corrections were incorporated in successfully compiled later structure builds; cover/front-matter flow, page numbering, acronym list, margins and chapter structure are operational. A concise AI-use declaration working version and the currently assigned Fénix title are now integrated; jury metadata, defence date, final title confirmation, and final declaration review remain pending.
   - target approximately 35–45 complete pages by 7 September covering the introduction, background/related work, system architecture, and current TIM-MARS method draft. Final method wording remains gated by #40 and the final implementation.
   - Chapter 1 writing is now underway. Section 1.1 Motivation has a compiled two-page working draft aligned with the frozen dissertation research framing rather than the obsolete PIC2 research question. Its initial bibliography entries were checked against publication metadata and corrected where necessary. Section 1.2 Problem Statement now also has a compiled working draft, defining the selected physical target, tracker identity, raw and controller-facing outputs, recoverable identity instability, offline-only ground truth, asymmetric safety–availability objective, and fully onboard constraint. Sections 1.3 Research Questions and 1.4 Objectives now also have compiled working drafts. The original official Fénix assignment has also been recovered: proposal #36044, titled “Efficient Real-Time Vision-Based Object Perception and Tracking for Micro Aerial Robots”. It is treated as the official umbrella theme, with the current TIM-MARS selected-person research framing representing the dissertation's later scientific specialisation. The frozen main question and both subquestions are reproduced exactly, and the objectives map the algorithmic and embedded-deployment questions to concrete implementation and evaluation tasks. Sections 1.6 Scope and Claim Boundaries and 1.7 Thesis Organisation now also have compiled working drafts. All currently evidence-safe Introduction sections are drafted and the compiled chapter has now been visually reviewed as a whole. The empty Contributions heading is hidden from the working PDF until evidence is available, and the scope section was compacted after the visual review. The Research Questions remain frozen. Contributions remain intentionally evidence-gated until the final held-out and onboard results are available.
   - Chapter 2 Background and Related Work now has a complete first working draft. Sections 2.1--2.8 cover RGB UAV person following, embedded person detection, tracking-by-detection, motion- and appearance-assisted MOT, identity switches and fragmentation, person ReID and appearance embeddings, selected-target identity validation and recovery, edge AI and fully onboard perception, a related-systems comparison, and the evidence-derived research gap. Following the 22 August literature and novelty refresh, the chapter is supported by a verified 30-paper literature backbone. The close-precedent set now explicitly covers target-person tracking, designated-person ReID and reacquisition, persistent appearance reasoning, distractor-aware recovery, integrated appearance-aware MOT, reject-option/selective-classification theory, open-set identity rejection, selective ReID, supervisory perception-assurance architectures, and task-aware perception-risk reasoning. The resulting research gap no longer treats those mechanisms or broader supervisory/task-aware principles individually as thesis novelty. The updated chapter compiles successfully with all citation keys resolved; one non-blocking underfull table-cell warning remains in the related-systems table. Figures F04--F08 remain intentionally pending for the final figure pass, and the chapter remains subject to later supervisor review and polishing.
   - Chapter 3 drafting started before the planned August travel pause. Sections 3.1 System Requirements and 3.2 Hardware Platform have clean compiled working drafts covering the fully onboard requirement, controller-authority separation, Raspberry Pi 5/Hailo-8 execution split, TEVS CSI capture path, and Pixhawk 6X/MAVROS hardware interface. A clean pre-travel dissertation checkpoint was compiled on 10 August. Section 3.3 Software and ROS 2 Architecture is the exact writing restart point for 25 August; Sections 3.3--3.8 remain to be drafted.

2. [ ] [#67 — P1.T2 Complete thesis experiments, results, and discussion draft by 30 September 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM
   - deliver a complete supervisor-ready dissertation draft within the current MEEC 80-page dissertation limit, including datasets, evaluation, results, discussion, limitations and figures. Supplementary material may be moved to the permitted annex where appropriate; do not target page count for its own sake.

3. [ ] [#68 — P1.T3 Complete thesis review, formatting, and final submission by 31 October 2026](https://github.com/FRCTavares/IST-Thesis-Code/issues/68) — HIGHEST PRIORITY — PARALLEL THESIS WORKSTREAM
   - own supervisor revisions, proofreading, current IST/MEEC formatting compliance, originality and AI-use declarations, Portuguese and English abstracts, extended abstract, final reproducibility checks, release archival and submission.

4. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25) — HIGHEST PRIORITY
   - phase 6; experiment; use the transform contract from #53.
   - 19 August priority boundary: #25 remains thesis-critical for the identity-independent evaluator, physical-target reference contract, and valid physical-target annotations. Further annotation-UI feature work, refactoring, convenience work, bag-browser improvements, and visual polish are paused. The current UI is an annotation instrument, not a thesis contribution; modify it again only when a concrete defect blocks scientifically valid #25 evidence. Manual annotation may proceed in parallel once the existing tool is sufficient.
   - resumed on 25 August on `issue-25-bbox-evaluation-continuation-20260825`, based on current `origin/main` while preserving the parked `issue-25-improve-bbox-evaluation` checkpoint. The v1/v2 physical-reference contracts, identity-independent evaluators, and v2 annotation workspace are present. The machine-doable M4A-v2 workload re-plan is recorded in `docs/issues/p1-10-physical-reference-annotation-plan.md`, including exact source-frame horizons and the requirement to regenerate M5 outputs from the same annotated captures. Francisco completed the six-item M3-v2 human browser acceptance checkpoint on 25 August against June Seq01 raw bag `2026-06-19__12-48-17`. Real playback of the initial Seq01 endpoint anchors exposed nonlinear motion around 7.8 s that endpoint-linear evaluator interpolation cannot represent. The custom annotation instrument and its assisted-propagation work remain available for schema/debug/evaluator inspection, but CVAT is now the preferred M4B human annotation frontend. June Seq01 M4B human annotation is complete: the reviewed ordered-PNG task exported as CVAT for images 1.1 and converted/validated as 1520 per-frame v2 samples with zero missing frames and complete target plus `phys_d001`--`phys_d003` coverage. `physical_ref`, never numeric CVAT IDs or drawing order, defines identity; exact times come from `frame_manifest.json`, never nominal FPS. The validated 1,520-sample artifact is promoted at `docs/data/physical_target_references/seq01_clean.json` (SHA-256 `c0d7c2a3c7471cd9ae2d1a16868110e5f1f30320cf15c21f32ffef2d8d23833d`); the superseded two-anchor draft SHA-256 is recorded in the Issue #25 annotation plan. May hard re-entry M4B is also complete: Francisco's reviewed CVAT for images 1.1 export converted and validated as 974 per-frame `present_scored` / `distractors_complete` samples with zero gaps, exact `target` plus `phys_d001` coverage, the header-derived `[0.0, 67.864909774]` s window, and zero duration-reconciliation residual. The promoted canonical artifact is `docs/data/physical_target_references/dev_may_hard_reentry.json` (SHA-256 `45d620d97e6488fb174e4ce66c49403079e084bc577d6d621c8365265f0d238c`). June Seq03 M4B is now also complete: the reviewed CVAT for images 1.1 export was converted and validated as 1,931 per-frame `present_scored` / `distractors_complete` samples with target coverage on all frames, `phys_d001` on frames 0--1930, `phys_d002` on frames 350--1930 and `phys_d003` on frames 400--1930. Exact positive `Image.header.stamp` timing gives `[0.0, 83.867251154] s`; the `83.866288839 s` rosbag metadata duration is bag-record-time duration and is not the reference clock. The promoted canonical artifact is `docs/data/physical_target_references/seq03_crossing.json` (SHA-256 `9e03fedc8076638bfb300cf131672aef38927252c09ac48174fa79bd2aa17f71`). Global M4B and M5 remain incomplete because Seq04 is still unannotated and matching same-capture v2 evaluation evidence has not yet been generated.

5. [ ] [#64 — P1.9+ Evaluate higher-resolution source frames for appearance crops while retaining 640x640 Hailo detection](https://github.com/FRCTavares/IST-Thesis-Code/issues/64) — HIGHEST PRIORITY
   - **PAUSED — representative drone-POV footage required.** Stage-A live feasibility on 27 August 2026 kept Hailo detector inference fixed at 640x640: VGA 640x480 PASS, HD 1280x720 PASS, while FHD 1920x1080 FAILS the current appearance-image freshness requirement despite adequate detector/tracker throughput. The controlled R3 comparison was audited and corrected before acceptance: CVAT frames 93--96 are now `present_reference_unavailable`; the deterministic tracker replay now parses the versioned `;frame=<n>;` coordinate contract instead of emitting numeric `frame_id=0`; corrected candidate-stream SHA-256 is `615ed6abf0083f8cbe86a47257fdc71f4c62c2e16fa314997c57ed34a1a99578`; and the promoted physical reference is `docs/data/physical_target_references/p064_gate2_hd_master_r3.json` with SHA-256 `0d9f4148f67b610d5cd012db4d3613f6fc559aec63c2ae705adc50595e8db147`.
   - Corrected native 1280x720 and deterministic 640x360 appearance replays use identical detector/tracker evidence and produce different TIM semantic digests, proving that the appearance-pixel condition reaches TIM, but their v2 physical-target reports are byte-identical: 18.600459426 s correct-target output, 0 wrong-person output, 9.100239419 s lost/suppressed, 0 target-absent duration, 0.133160003 s reference-unavailable and 0.066408595 s reference-gap over 27.900267443 s total evaluated duration. The resolution-specific material benefit is therefore 0 percentage points and the predeclared Stage-B repeat gate is not reached for R3.
   - This R3 result is intentionally not generalized to airborne operation: target height is 534.64--561.11 px (median 549.72 px), far larger than the intended distant/small-person drone distribution. Issue #64 remains open but paused until one representative native-HD drone-POV sequence is recorded. Future representative capture uses the already established live `YOLOv8s + ByteTrack + TIM-MARS` path while keeping detector inference at 640x640; this does not retrospectively alter the completed R3 experiment, which remains frozen on YOLOv6n. Field command: `tools/experiments/record_p064_drone_sequence.sh small_target_r1`.
6. [ ] [#58 — P1.13+ Compare lightweight tracker + TIM-MARS against integrated appearance-aware tracking](https://github.com/FRCTavares/IST-Thesis-Code/issues/58) — HIGHEST PRIORITY — IN PROGRESS
    - phase 7; experiment; compare separately calibrated lightweight
      appearance-free tracker + TIM-MARS systems against integrated
      appearance-aware tracker references using held-out controller-facing
      safety metrics and the canonical Issue #32 safety–availability–cost
      methodology. DeepSORT + TIM-MARS is diagnostic rather than the intended
      architecture.
    - add one deliberately simple literature-aligned post-MOT Target-ReID baseline: ByteTrack candidates; the same MARS model and crop/preprocessing contract used by TIM-MARS; highest target-appearance similarity above a development-calibrated threshold; LOST otherwise. Exclude TIM-MARS geometry fusion, hard-negative policy, temporal recovery confirmation, state-machine authority, and trusted-only memory-update logic. This isolates whether full TIM-MARS provides controller-facing value beyond ordinary Target-ReID rather than merely beyond the raw tracker.
   - Simple Target-ReID development calibration is now frozen on `dev_may_hard_reentry`. The threshold grid `0.00:0.05:0.95` and historical Issue #58 safety-first selector were fixed before outcome review. The selected threshold is `0.90`: physical-v2 gives `23.152773497 s` correct-target output, `0 s` wrong-person output, `0 s` identity-unresolved and `44.712136277 s` lost/suppressed over `67.864909774 s`. This is development-only evidence and demonstrates the availability cost of a conservative fixed-template ReID baseline; held-out comparison remains required.
   - The first physical-v2 four-cell development architecture matrix is now frozen for May hard re-entry: ByteTrack raw `38.530771128 / 7.595021755 / 21.739116891 s`, simple Target-ReID `23.152773497 / 0 / 44.712136277 s`, canonical ByteTrack + TIM-MARS `62.594003990 / 0.033394241 / 5.237511543 s`, and DeepSORT raw `51.356019855 / 0.033394241 / 16.475495678 s` for correct / wrong / lost. TIM-MARS therefore matches DeepSORT wrong-person duration on this development sequence while providing `11.237984135 s` more correct-target output. This remains development-only evidence; remaining architecture cells and held-out physical-v2 evaluation are required before the final Issue #58 claim.
   - The minimal appearance-free SORT arm has also been re-audited against the corrected May physical-v2 reference using exactly the 29 pre-frozen SORT+TIM calibration configurations. Raw SORT gives `29.398778016 / 0.049512077 / 38.416619681 s` correct / wrong / lost. With the historical `+0.05 s` asymmetric safety tolerance, the maximum permitted wrong-person duration is `0.099512077 s`; zero of 29 SORT+TIM configurations pass. The lowest-wrong candidate `confirmation_time_higher_3` still produces `0.694389678 s` wrong-person output. SORT+TIM is therefore a documented development negative result, not a promotable architecture cell.
   - June Seq03 now provides a second frozen physical-v2 development architecture comparison from the exact canonical `2026-06-19__12-55-58` raw capture. One YOLOv8s detection stream was frozen with exact 1,931/1,931 image-to-detection header-timestamp equality and then fanned out deterministically to all tracker architectures with no Seq03 retuning. Results for correct / wrong / lost are: ByteTrack raw `33.831624313 / 0.100206111 / 49.834967359 s`; SORT raw `27.432422908 / 0 / 56.334374875 s`; frozen Target-ReID 0.90 `13.962779010 / 0 / 69.804018773 s`; canonical ByteTrack + TIM-MARS `22.532686264 / 0 / 61.234111519 s`; and DeepSORT raw `27.547623858 / 35.350991550 / 20.868182375 s`. TIM-MARS removes ByteTrack's residual `0.100206111 s` wrong-person output but sacrifices `11.298938049 s` correct-target availability; relative to simple Target-ReID it preserves the same zero measured wrong-person duration while adding `8.569907254 s` correct-target output. DeepSORT produces `35.350991550 s` wrong-person output despite identical detector evidence, correct physical-target bootstrap, and zero appearance-image age. Seq03 has zero target-absent duration, so open-set target-absence evidence remains outstanding.
    - Target-absence false publication must be reported explicitly for this baseline,       together with confirmed reacquisition delay after the physical target returns.       Treat genuine target absence as an open-set case in which LOST is a valid outcome;       do not force publication of the highest-ranked visible candidate. Liao et al.       (2014), Ye et al. (2024), TPT-Bench, and Bayar and Aker (2024) are prior-art       boundaries rather than standalone TIM-MARS novelty claims.

7. [ ] [#74 — P1.x State-aware selected-person following and bounded visual recovery](https://github.com/FRCTavares/IST-Thesis-Code/issues/74) — HIGHEST PRIORITY
    - phase 10; live-system; execute after #25 → #64 → #21 → #58 and before #32.
    - TIM-MARS remains the sole selected-person identity authority. Add only a conservative state-aware following policy plus tightly bounded yaw-only visual recovery from trusted TIM-MARS history; raw `/target`, `/tracks`, detector candidates, and unconfirmed candidates must never obtain controller authority.
    - retain the extension only if deterministic safety tests and closed-loop evidence show useful recovery without unacceptable wrong-person non-zero command duration. Physical-aircraft validation remains owned by #50/#51.

8. [ ] [#32 — P1.14 End-to-end runtime, compute budget, and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; owns the canonical per-stage latency and queueing
      timebase, wall-clock versus CPU-service-time separation, p50/p90/p95/p99
      and maximum distributions, cadence/jitter/drop accounting, selective-ReID
      invocation and cache statistics, per-process/thread CPU, memory, raw-image
      DDS/QoS bandwidth, Hailo contention, sustained thermal/throttling evidence,
      and reproducible power measurements where available. It also measures the
      incremental cost of TIM-MARS and supplies the runtime contract for the
      lightweight-versus-integrated tracker comparison.

10. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

11. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

12. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

13. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

14. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
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
   - 28 August 2026: the model-artifact inventory is drafted in `models/README.md` (family, purpose, consumers, SHA-256, tracked/ignored state; provenance recorded as unknown where not established). The `reports/` promoted-package register is drafted in `reports/PROMOTED.md`. The 2026-07-09 bag-deletion audit trail (removed 2026-07-20) is restored to tracked provenance at `docs/archive/bag_cleanup_2026_07_09/`. The tracked-vs-untracked model decision, bag consolidation, retention policy, and any pack migration remain open.

## P3 — Optional or stretch work

1. [ ] [#46 — P3.x Orientation gating (stretch; needs pose keypoints)](https://github.com/FRCTavares/IST-Thesis-Code/issues/46)
   - phase 10; engineering; requires pose keypoints.
