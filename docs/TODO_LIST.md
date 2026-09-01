# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Open executable issues: **19**.

Last reconciled with GitHub: **31 August 2026**.

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

1. [ ] [#27 — P0.16 Freeze tuning and test data](https://github.com/FRCTavares/IST-Thesis-Code/issues/27)
   - phase 7; experiment; the historical 23 July `tim_mars_split_v1` is retained for provenance, while the active prospective final-evaluation authority is `tim_mars_split_v2`, frozen on 1 September before any H01–H03 capture or outcome access. Development/legacy inputs remain development/legacy only. The dedicated source-only H01–H03 capture procedure is now a compact common index plus separate H01/H02/H03 operator sheets under `docs/flight/`; it records frozen YOLOv8s detector evidence with raw imagery while tracker/TIM/control remain disabled. Actual H01–H03 capture, physical-v2 annotation, hashing, and people/clothing-overlap records remain pending; the release gate must stay fail-closed at `final_ready=0/3`, and no held-out outcome may influence thresholds, algorithm logic, tracker settings, or model selection.

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


**Immediate thesis-critical implementation and evaluation path:** #74 deterministic state-aware controller → #51 remaining physical readiness → #27 prospective held-out freeze/evaluation → #50 closed-loop ground/flight validation → #64 representative drone-POV resolution decision → #58 final held-out closure → #32 final sustained onboard characterisation → #39 final claim freeze. The pre-#58 #32 instrumentation/evidence gate and the #58 development architecture/embedded-cost comparison completed on 31 August 2026. Issue #58 remains open only for the prospective held-out H01--H03 architecture evidence required after #27; no additional development architecture experiment is currently justified. Issues #25 and #21 are closed. Paused #64 does not block the current #74 deterministic controller work.

**Parallel thesis-writing workstream:** the thesis is not postponed until the code is finished. Complete the architecture and evidence-safe method catch-up by 7 September, the supervisor-ready full draft by 30 September, and the review/submission work by 31 October alongside the algorithm and evaluation schedule.

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

4. [ ] [#64 — P1.9+ Evaluate higher-resolution source frames for appearance crops while retaining 640x640 Hailo detection](https://github.com/FRCTavares/IST-Thesis-Code/issues/64) — HIGHEST PRIORITY — PAUSED / FIELD DEPENDENT

   - Stage-A live feasibility retained 640x640 Hailo detector inference. VGA 640x480 and HD 1280x720 passed; FHD 1920x1080 failed the current appearance-image freshness requirement.
   - The corrected R3 experiment proved that native 1280x720 pixels reach TIM-MARS, but native-HD and deterministic 640x360 appearance conditions produced identical physical-target results. Measured benefit was therefore zero for that close, large-target sequence.
   - R3 does not answer the intended distant/small-person airborne case because the target was roughly 535--561 px tall. Resume only with one representative native-HD drone-POV sequence containing a substantially smaller target.
   - Prefer collecting that sequence during #50 physical validation. Keep detector inference at 640x640. Field helper: `tools/experiments/record_p064_drone_sequence.sh small_target_r1`.
   - #64 does not block the current #58 development comparison or #74 deterministic controller implementation. Resolve it before final #32 characterization and #39 claim freeze.

5. [ ] [#58 — P1.13+ Compare lightweight tracker + TIM-MARS against integrated appearance-aware tracking](https://github.com/FRCTavares/IST-Thesis-Code/issues/58) — HIGHEST PRIORITY — IN PROGRESS
    - phase 7; experiment; compare separately calibrated lightweight
      appearance-free tracker + TIM-MARS systems against integrated
      appearance-aware tracker references using held-out controller-facing
      safety metrics and the canonical Issue #32 safety–availability–cost
      methodology. DeepSORT + TIM-MARS is diagnostic rather than the intended
      architecture.
    - add one deliberately simple literature-aligned post-MOT Target-ReID baseline: ByteTrack candidates; the same MARS model and crop/preprocessing contract used by TIM-MARS; highest target-appearance similarity above a development-calibrated threshold; LOST otherwise. Exclude TIM-MARS geometry fusion, hard-negative policy, temporal recovery confirmation, state-machine authority, and trusted-only memory-update logic. This isolates whether full TIM-MARS provides controller-facing value beyond ordinary Target-ReID rather than merely beyond the raw tracker.
   - Simple Target-ReID development calibration is now frozen on `dev_may_hard_reentry`. The threshold grid `0.00:0.05:0.95` and historical Issue #58 safety-first selector were fixed before outcome review. The selected threshold is `0.90`: physical-v2 gives `23.152773497 s` correct-target output, `0 s` wrong-person output, `0 s` identity-unresolved and `44.712136277 s` lost/suppressed over `67.864909774 s`. This is development-only evidence and demonstrates the availability cost of a conservative fixed-template ReID baseline; held-out comparison remains required.
   - The first physical-v2 four-cell development architecture matrix is now frozen for May hard re-entry: ByteTrack raw `38.530771128 / 7.595021755 / 21.739116891 s`, simple Target-ReID `23.152773497 / 0 / 44.712136277 s`, canonical ByteTrack + TIM-MARS `62.594003990 / 0.033394241 / 5.237511543 s`, and DeepSORT raw `51.356019855 / 0.033394241 / 16.475495678 s` for correct / wrong / lost. TIM-MARS therefore matches DeepSORT wrong-person duration on this development sequence while providing `11.237984135 s` more correct-target output. This remains development-only evidence; the embedded-cost architecture comparison is now complete, while held-out physical-v2 evaluation remains required before the final Issue #58 claim.
   - The minimal appearance-free SORT arm has also been re-audited against the corrected May physical-v2 reference using exactly the 29 pre-frozen SORT+TIM calibration configurations. Raw SORT gives `29.398778016 / 0.049512077 / 38.416619681 s` correct / wrong / lost. With the historical `+0.05 s` asymmetric safety tolerance, the maximum permitted wrong-person duration is `0.099512077 s`; zero of 29 SORT+TIM configurations pass. The lowest-wrong candidate `confirmation_time_higher_3` still produces `0.694389678 s` wrong-person output. SORT+TIM is therefore a documented development negative result, not a promotable architecture cell.
   - June Seq03 now provides a second frozen physical-v2 development architecture comparison from the exact canonical `2026-06-19__12-55-58` raw capture. One YOLOv8s detection stream was frozen with exact 1,931/1,931 image-to-detection header-timestamp equality and then fanned out deterministically to all tracker architectures with no Seq03 retuning. Results for correct / wrong / lost are: ByteTrack raw `33.831624313 / 0.100206111 / 49.834967359 s`; SORT raw `27.432422908 / 0 / 56.334374875 s`; frozen Target-ReID 0.90 `13.962779010 / 0 / 69.804018773 s`; canonical ByteTrack + TIM-MARS `22.532686264 / 0 / 61.234111519 s`; and DeepSORT raw `27.547623858 / 35.350991550 / 20.868182375 s`. TIM-MARS removes ByteTrack's residual `0.100206111 s` wrong-person output but sacrifices `11.298938049 s` correct-target availability; relative to simple Target-ReID it preserves the same zero measured wrong-person duration while adding `8.569907254 s` correct-target output. DeepSORT produces `35.350991550 s` wrong-person output despite identical detector evidence, correct physical-target bootstrap, and zero appearance-image age. Seq03 has zero target-absent duration, so it does not itself test open-set target-absence behavior; that development evidence is now supplied separately by Seq04.
   - 31 Aug 2026: the canonical Issue #58 development architecture, embedded-cost, and timing comparison is complete on Raspberry Pi 5 at measurement commit `92d123e3`, using the same June Seq03 source, direct-Hailo YOLOv8s, real-time `1.0x` playback, three repetitions per architecture, rotated execution order, and the schema-v4 active timing window `pub_dt_ms <= 100 ms`. All 9/9 retained cells completed with zero hardware-sampler errors and zero observed throttling. Architecture-specific resource means are: ByteTrack raw `227.2 +/- 0.6%` CPU and `134.6 +/- 0.2 MiB` RSS; ByteTrack + TIM-MARS `243.3 +/- 10.3%` CPU and `919.6 +/- 7.8 MiB` combined tracker+TIM RSS; DeepSORT raw `267.0 +/- 3.0%` CPU and `767.2 +/- 1.9 MiB` RSS. TIM-MARS therefore uses about `8.9%` less architecture CPU than DeepSORT on this controlled workload but about `19.9%` more mean architecture RSS. Corrected timing aggregation gives ByteTrack raw tracker `18.612 +/- 0.403 Hz` with tracker p95 `6.218 +/- 0.362 ms`; ByteTrack + TIM-MARS tracker `18.100 +/- 0.351 Hz` with tracker p95 `22.841 +/- 2.001 ms`, and validated selected-target output `17.561 +/- 0.549 Hz` with end-to-end validated-target p95 `181.785 +/- 15.445 ms`; DeepSORT raw tracker throughput is `9.796 +/- 0.180 Hz` with tracker p95 `150.816 +/- 3.433 ms` and only `68.154 +/- 1.087%` active detector-to-tracker causal coverage. The ByteTrack + TIM-MARS controller-facing path satisfies the preferred `>=15 Hz` rate and the `<=200 ms` p95 latency target in `3/3` retained runs. The DeepSORT cell is intentionally tracker-stage only and has no TIM-MARS selected-target authority, so it must not be described as a controller-facing end-to-end latency measurement. Issue #58 development experimentation is now frozen; the issue remains OPEN only for held-out H01--H03 physical-v2 architecture evidence under Issue #27 before the final general claim. Do not rerun the frozen May/Seq03/Seq04 development matrices or add StrongSORT/BoT-SORT unless later evidence exposes a specific scientific deficiency.
   - June Seq04 now supplies the first frozen development-only open-set target-absence comparison for Issue #58. Over `72.500041772 s` of physically scored target-present time, correct / wrong / lost are: ByteTrack raw `26.567002669 / 37.500838682 / 8.432200421 s`; SORT raw `14.833643862 / 0 / 57.666397910 s`; frozen Target-ReID 0.90 `1.166866685 / 0 / 71.333175087 s`; canonical ByteTrack + TIM-MARS `35.068442774 / 0 / 37.431598998 s`; and DeepSORT raw `36.833999479 / 0 / 35.666042293 s`. During `13.900030159 s` of explicit physical target absence, ByteTrack publishes an output for `13.100381659 s`, whereas SORT, DeepSORT, Target-ReID and TIM-MARS remain clear throughout. Neither physical return yields a correct reacquisition for any architecture: return 1 is a failure before the next absence, while return 2 is right-censored at sequence end, so no finite reacquisition latency is reported. ByteTrack additionally publishes a wrong person for `4.166819295 s` and `2.699997183 s` in the two post-return windows. Seq04 therefore demonstrates TIM-MARS's conservative safety transformation relative to ByteTrack, but not an availability advantage over DeepSORT; held-out H01--H03 remain required for the final architecture comparison; the canonical embedded-cost development comparison is now complete.
    - Target-absence false publication must be reported explicitly for this baseline,       together with confirmed reacquisition delay after the physical target returns.       Treat genuine target absence as an open-set case in which LOST is a valid outcome;       do not force publication of the highest-ranked visible candidate. Liao et al.       (2014), Ye et al. (2024), TPT-Bench, and Bayar and Aker (2024) are prior-art       boundaries rather than standalone TIM-MARS novelty claims.

6. [ ] [#74 — P1.x State-aware selected-person following and bounded visual recovery](https://github.com/FRCTavares/IST-Thesis-Code/issues/74) — HIGHEST PRIORITY
    - phase 10; live-system; execute after the #58 development comparison and before final #32 characterization. Issues #25 and #21 are closed; paused #64 does not block deterministic controller implementation. Physical closed-loop validation is owned by #50 after the remaining #51 readiness gates.
    - TIM-MARS remains the sole selected-person identity authority. Add only a conservative state-aware following policy plus tightly bounded yaw-only visual recovery from trusted TIM-MARS history; raw `/target`, `/tracks`, detector candidates, and unconfirmed candidates must never obtain controller authority.
    - retain the extension only if deterministic safety tests and closed-loop evidence show useful recovery without unacceptable wrong-person non-zero command duration. Physical-aircraft validation remains owned by #50/#51.
    - 31 Aug 2026: the Issue #74 controller contract is frozen in `docs/control/p074_state_aware_control_contract.md`. Existing `zero_id_when_not_visible=true` fail-safe semantics are retained. Implementation will add TIM-MARS state/control-mode consumption plus a TIM-owned selection generation; generation changes cancel trusted-history recovery. Active yaw-only recovery remains default OFF until deterministic validation passes.
    - 31 Aug 2026: the first Issue #74 implementation slice adds a pure, ROS-independent state-aware control policy. Only causally paired `LOCKED` + `NORMAL` authority permits normal following; `UNCERTAIN`, `REACQUIRED`, `NO_TARGET`, stale/mismatched authority, and disabled recovery fail to hover/zero. Optional LOST recovery is translation-free, last-trusted-direction yaw only, and bounded by history age, duration, generation, yaw rate, and integrated yaw budget. ROS controller wiring and TIM-owned generation plumbing remain the next implementation slice.
    - 31 Aug 2026: controller-authority wiring now requires the validated `/target_memory_mars` target plus fresh `LOCKED` + `NORMAL` TIM status paired by frame ID and source timestamp. TIM-MARS owns a per-node `selection_session_id` plus monotonic `selection_generation`; generation rollback and retired-session status are rejected, while a genuine new TIM session causes a hard authority reset. Select/clear transactions revoke old authority and invalidate last-trusted history. Missing/malformed status fails closed. The controller standalone default is now the TIM-MARS target, not raw `/target`. Active recovery remains disconnected/default OFF.
    - 31 Aug 2026: bounded LOST yaw-recovery deterministic software is implemented and package-validated. Recovery consumes only current-generation last-trusted horizontal error, starts from a hard-zero command, keeps `vx=vy=0`, applies existing yaw saturation/slew limits, is bounded by 1.0 s duration, 0.10 rad/s requested yaw, 0.10 rad integrated yaw budget, and 1.0 s trusted-history age, and permits at most one attempt per trusted observation. A fresh trusted `LOCKED` + `NORMAL` observation re-arms recovery. The full `thesis_bringup` gate passed with 422 tests and 1 skip. Live recovery remains explicitly default-OFF pending #50 closed-loop validation and the retain/reject decision.
    - 31 Aug 2026: deterministic #74 controller diagnostics now report policy mode/reason, TIM state/control mode, selection generation/session, status freshness, recovery enabled/active state, trusted-history age, recovery direction, elapsed time, integrated yaw, remaining yaw budget, saturation state, and final post-shaping command. Recovery remains explicitly default-OFF in the live stack pending physical validation.

7. [ ] [#32 — P1.14 End-to-end runtime, compute budget, and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; owns the canonical per-stage latency and queueing
      timebase, wall-clock versus CPU-service-time separation, p50/p90/p95/p99
      and maximum distributions, cadence/jitter/drop accounting, selective-ReID
      invocation and cache statistics, per-process/thread CPU, memory, raw-image
      DDS/QoS bandwidth, Hailo contention, sustained thermal/throttling evidence,
      and reproducible power measurements where available. It also measures the
      incremental cost of TIM-MARS and supplies the runtime contract for the
      lightweight-versus-integrated tracker comparison.
    - 30 Aug 2026: pre-#58 instrumentation implementation now includes the
      direct-Hailo Timing schema v4, TIM-MARS ownership of `/timing_target`,
      exact selective-ReID cache lookup/hit/miss/expiry/invalidation telemetry,
      and the schema-v3 TIM-MARS ReID workload summary. Retired container/ZMQ
      timing compatibility fields remain intentionally unsupported. YOLOv8s is
      now the canonical Pi 5 + Hailo detector for current runtime defaults and
      new experiments; historical detector evidence retains its original model
      identity. The first current-schema smoke exposed a cross-topic delivery
      race: `/detections` could reach the tracker before its matching `/timing`,
      dropping the downstream camera-arrival monotonic timestamp. The detection
      contract now carries that causal timestamp directly, without a blocking
      tracker join, and tracker timing is enabled by default. The runner audit
      additionally exposed an incompatible duplicate BEST_EFFORT target command;
      the full-pipeline runner now uses only the dashboard authority API's RELIABLE
      TIM-MARS command path, explicitly enables tracker/target timing, and
      propagates input/setup/provenance/startup/playback/selection failures. The
      second dirty-tree smoke
      then confirmed causal camera timing on 1109/1109 detector, tracker, and
      validated-target samples, with positive validated target end-to-end latency
      on 1109/1109 samples. `/timing_target` intentionally owns TIM-MARS timestamps
      rather than duplicating `t_track_cb_*`; those tracker timestamps remain owned
      by `/timing_tracker`. That smoke also exposed PID-only cleanup as insufficient
      because `ros2 run` children survive their wrapper process. The runner now uses
      a runner-owned supervisor PID whose forked child creates an isolated process
      group and receives forwarded shutdown signals. Isolated validation confirmed
      that signalling only the supervisor terminates both the command leader and its
      descendants. The next dirty-tree run confirmed the lifecycle repair leaves
      zero runtime descendants and independently passed the schema-v4 causal timing
      audit on 1086 detector/tracker/target samples, but exposed repeated short-lived
      `ros2 topic echo /tracks --once` discovery as an unreliable target-resolution
      mechanism despite all 1086 recorded `/tracks` messages being non-empty. The
      full-pipeline runner now resolves the target through a persistent typed
      BEST_EFFORT, KEEP_LAST depth-1 `/tracks` subscriber matching the tracker
      publisher QoS; isolated ROS validation covers both largest-track and explicit-ID
      selection. The final dirty-tree canonical YOLOv8s full-pipeline smoke then
      confirmed typed target resolution, authoritative TIM-MARS selection, schema-v4
      detector/tracker/target causal timing, provenance generation, and zero surviving
      runner descendants. Replay documentation now distinguishes the persistent
      typed full-pipeline resolver from the older text-echo support path, and Hailo
      recovery guidance avoids broad process-name termination. A final active-runtime
      architecture audit also removed the retired dashboard Docker/container model-switch
      fallback and its launcher wiring; model switching now has only the direct in-process
      perception parameter-service path when runtime reconfiguration is explicitly enabled,
      while the frozen live profile continues to disable runtime reconfiguration. The
      dashboard WebSocket metrics schema remains independently versioned from Timing schema
      v4. The first post-promotion clean-tree replay then exposed three audit-contract issues
      before retained evidence could be accepted: the cross-topic
      `e2e_validated_target_ms >= e2e_det_ms` comparison incorrectly ordered two independent
      ROS publication-return endpoints; one immediate `operator_clear` status-only event was
      correctly non-frame control telemetry but was being interpreted as a malformed ReID
      workload sample; and replay provenance recorded the YOLOv8s/MARS model paths without
      their content hashes. The follow-up instrumentation patch removes the invalid
      cross-topic inequality while retaining per-topic causal timestamp checks, excludes only
      no-frame/no-workload control-status records while keeping partial workload records
      fail-closed, and records SHA-256 identities for both runtime models in the experiment
      provenance. The first retained clean-tree replay from follow-up commit
`5672d14995156ed24d8726a19567802968d70377` exposed one additional
cross-layer contract inconsistency: the live perception pipeline emitted
causal numeric `frame_id=0`, while tracker timing, TIM-MARS appearance
lifecycle handling, controller-facing target resets, and the accepted
deterministic replay contract reserve numeric zero for invalid, reset, or
otherwise noncausal lifecycle events. Inference sequencing therefore remains
zero-based for legacy Gst PTS compatibility, while published causal pipeline
frame IDs start at one.
    - 31 Aug 2026: the replacement retained clean-tree Seq03 replay from
      `67311f2097f6dbea54f98498a564bfc50463fc7c` completed the pre-#58
      instrumentation/evidence gate. Provenance records a clean repository,
      canonical YOLOv8s and CPU MARS identities, and the direct-Hailo runtime.
      Schema-v4 causal invariants pass with zero failures: `/timing` and
      `/timing_tracker` use causal frame IDs 1--1019, while `/timing_target`
      uses 92--1019; no causal timing path contains frame ID zero. The single
      controller-facing target frame zero is the expected noncausal
      `operator_clear` lifecycle event. Gap-filtered active results are
      detector e2e p95 35.184 ms, tracker p95 21.297 ms, target e2e p95
      192.727 ms and p99 235.360 ms at 15.732 Hz target timing. Selective
      CPU-MARS workload remains stable: cache hit rate 0.86837, 3.309 backend
      calls/s, 9.661 requested crops/s, steady-state backend p95 181.189 ms,
      with one first-call warm-up outlier at 676.132 ms. The runner and audit
      both leave zero surviving runtime descendants and no repository-root
      runtime noise.
    - Pre-#58 #32 work is therefore complete. Execution now proceeds
      #58 → #74 → #32 final sustained characterization. Do not close #32
      before the post-#74 sustained resource evidence.

8. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

9. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.
    - 1 Sep 2026: execution started on `issue-55-ui-repository-extraction-20260901` from clean main `8e88a471`. Repository extraction is governed by `docs/issues/ui-repository-extraction-master-plan.md`: Phase A moves only the tracked React/Vite `live-ui` frontend into `FRCTavares/IST-Thesis-UI`; ROS dashboard bridge, runtime API, target authority, TIM-MARS, control, scientific tooling, and annotation backend remain in `IST-Thesis-Code`.
    - The approved post-extraction frontend target is an iPhone-first field interface: live video, numbered tracks, numeric bootstrap target selection, explicit select/clear, TIM state/current TIM track ID, and connection status. Desktop charts/logging/metrics complexity and ordinary model/tracker switching are not required in the frozen flight UI.
    - 1 Sep 2026 M1 PASS: the exact committed `live-ui` tree `634754dd789c32ba1d75216855a9dd77e187774b` was exported into `~/Desktop/IST-Thesis-UI`; all 45 source paths and Git blob hashes matched, no `node_modules`, `dist`, `*.tsbuildinfo`, or generated config artifacts were transferred, and the independent local UI repository was initialized with 47 tracked files at commit `032041aabb9c43988b128434874f08237d52ad6c`. The original `Thesis-Code/live-ui` tree remains intact during the rollback-safe two-copy phase. M2 standalone validation is next.

10. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

11. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

12. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
    - phase 9; experiment/documentation.

## P2 — Deferred maintenance and physical-validation dependencies

Issue #51 is closed for the host-only unattended-recovery scope. Issue #50 retains its historical GitHub P2 label but is the active next live-system gate and inherits the mandatory AERONEXT/Pixhawk field-network checks before retained aircraft closed-loop evidence after #74. The other P2 items remain outside the immediate scientific critical path.

1. [x] [#51 — P2 Complete deferred physical validation for unattended Pi recovery (September)](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)
   - the software recovery defect demonstrated on 25 July 2026 is repaired and validated.
   - unattended mode now separates configured connectivity from verified default-gateway reachability.
   - three consecutive reachability failures trigger one bounded `wlan0` reconnect; six failures trigger one bounded NetworkManager restart with an independent cooldown.
   - real installed-system tests proved Tailscale restart, Wi-Fi reconnect, NetworkManager escalation, network recovery, SSH recovery, Tailscale recovery, timer restoration, and production-state isolation.
   - 18 focused host-health tests pass for the current repository policy. The previously deployed monitor remains the validated unattended baseline until this ISR-first fallback slice is deliberately installed; the production timer currently reports healthy gateway, network, SSH, and Tailscale state.
   - 31 Aug 2026: the Tailscale authentication gate was rechecked live; the node is online and now expires on 21 Feb 2027, so the previous 23 Aug 2026 expiry blocker is resolved. The field-network software now implements ordered ISR-first selection: `ISR Aero.Next GCS` is always attempted first, with one explicitly configured approved AERONEXT local-router fallback permitted only when ISR cannot be activated. Neither path may bypass fail-closed Pixhawk mode, the `pixhawk-apm` no-default-route contract, or the Tailscale-off requirement. The exact fallback profile is not yet provisioned and remains a physical field-validation item.
   - 31 Aug 2026: a spontaneous home-network data-plane outage provided additional real recovery evidence. Gateway reachability failed while NetworkManager still reported the expected Wi-Fi profile and default route; after the configured third consecutive failure, the host monitor performed one bounded Wi-Fi reconnect. DHCP/default routing returned at 19:45:48 WEST, Tailscale recovered immediately afterward, and a fresh SSH connection to `100.69.42.62` passed. This validates the repaired data-plane recovery path but does not satisfy the genuinely external-network SSH gate.
   - 31 Aug 2026: the genuinely external Tailnet SSH gate is resolved. The operator Mac was moved to a phone-hotspot network (`172.20.10.3`, gateway `172.20.10.1`) while the Pi remained on the home LAN (`192.168.1.110`, gateway `192.168.1.1`); a fresh SSH session passed from Mac Tailnet address `100.105.37.101` to Pi Tailnet address `100.69.42.62`. The temporary direct-LAN SSH UFW exception was also removed beforehand, and a fresh Tailnet SSH connection passed after that cleanup.
   - 31 Aug 2026: the storage-safe physical power-restoration gate is resolved. After a clean `sync`/systemd poweroff, input power was physically removed for at least 15 seconds and restored once. The boot ID changed from `7d547b68-11ad-49e1-8e00-266273014d15` to `98eeee9a-b2a2-45c1-baa8-156a308e4c38`; unattended mode and all remote-access services restored automatically, the ext4 root returned read-write without detected I/O errors, and fresh external Tailnet SSH passed. Remote access was confirmed no later than 22:20:28 WEST, 173 seconds after the recorded OS boot start; exact power-on-to-reachability latency was not instrumented and is therefore not claimed.
   - 31 Aug 2026 closure: the host-only unattended-recovery scope is complete. A second spontaneous data-plane outage independently exercised the same bounded recovery path: three consecutive gateway failures triggered one same-profile Wi-Fi reconnect, DHCP/default routing returned, and Tailscale recovered without a reboot. The 30-second hardware watchdog is live and actively fed by systemd. Destructive kernel-hang injection was deliberately not performed because the committed runbook requires a verified working smart plug or UPS before that test; hard-hang recovery is therefore retained as an explicit untested extreme-failure limitation. Exact AERONEXT fallback provisioning and physical Pixhawk field-network validation are transferred to #50 and remain mandatory before aircraft operation.

2. [ ] [#50 — P2 Complete flight-readiness gate and record held-out UAV-motion evidence (September)](https://github.com/FRCTavares/IST-Thesis-Code/issues/50)
   - inherits the remaining physical network gate from closed #51: provision/validate the exact approved AERONEXT fallback profile and, with the real Pixhawk connected, verify `pixhawk-apm` on `eth0`, approved field Wi-Fi/default route on `wlan0` with ISR preferred when available, and `tailscaled.service` disabled/inactive before aircraft operation.
   - phase 10; live-system; active next live-system gate after the #51 host-only closure.
   - 1 Sep 2026 documentation gate: the obsolete P023 flight procedure is archived and is no longer current operator authority. `docs/flight/P050_FLIGHT_VALIDATION.md` now fails closed: no retained aircraft launch command is approved until the current YOLOv8s + ByteTrack + TIM-MARS + #74 controller path, real Pixhawk/MAVROS link, ISR-first/AERONEXT-fallback networking, target-selection/control authority, abort procedure, and retained topic set are audited and frozen under #50.
   - owns retained physical closed-loop evidence for the promoted #74 controller: TIM-MARS remains the sole selected-person identity authority while the aircraft performs conservative following and any promoted bounded visual-recovery behaviour.

3. [ ] [#45 — P2.x Detector (perception upgrade behind TIM — additive, low priority)](https://github.com/FRCTavares/IST-Thesis-Code/issues/45)
   - phase 10; live-system; additive and non-blocking.

4. [ ] [#49 — P2: Consolidate replay bags and define evidence retention policy](https://github.com/FRCTavares/IST-Thesis-Code/issues/49)
   - phase 8; engineering; includes the 4.52 GiB Git pack/model-artifact inventory; no history rewrite without a separate migration plan.
   - 28 August 2026: the model-artifact inventory is drafted in `models/README.md` (family, purpose, consumers, SHA-256, tracked/ignored state; provenance recorded as unknown where not established). The `reports/` promoted-package register is drafted in `reports/PROMOTED.md`. The 2026-07-09 bag-deletion audit trail (removed 2026-07-20) is restored to tracked provenance at `docs/archive/bag_cleanup_2026_07_09/`. The tracked-vs-untracked model decision, bag consolidation, retention policy, and any pack migration remain open.

## P3 — Optional or stretch work

1. [ ] [#46 — P3.x Orientation gating (stretch; needs pose keypoints)](https://github.com/FRCTavares/IST-Thesis-Code/issues/46)
   - phase 10; engineering; requires pose keypoints.
