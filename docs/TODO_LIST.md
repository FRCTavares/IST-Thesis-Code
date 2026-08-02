# TIM-MARS Active Task Queue

This file is the ordered view of open executable GitHub Issues. Issue bodies are
the source of truth for scope, acceptance criteria, commands, experiments, and
closing evidence.

Last reconciled with GitHub: **27 July 2026**.

Open executable issues: **21**.

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

3. [x] [#15 — P1.5 Fix positive-memory bootstrap](https://github.com/FRCTavares/IST-Thesis-Code/issues/15) — DONE
   - completed on 26 July 2026 against baseline `055984a3867b5fb1bfc22615f052bc17831e61a3` with corrective implementation `f1fbb7994766080481fe8cf3b9acac9862867c9b`.
   - bootstrap is allowed only while the original operator-selected lineage remains supported. Transient policy suppression preserves pre-anchor authorization only while the usable operator ID remains continuously present; true absence permanently invalidates delayed bootstrap.
   - four baseline runs, four candidate runs, and one independent Seq04 repeat completed successfully. All eight correctness and event-type evaluations passed.
   - candidate results exactly matched baseline: May `62.513/0.100/5.087 s`, Seq01 `108.750/0.000/13.590 s`, Seq03 `73.892/6.053/15.782 s`, and Seq04 `39.593/0.000/17.229 s` for correct/wrong/lost duration.
   - all four candidate sequences emitted one valid auditable bootstrap event. The corrective May case accepted frame `106` using appearance sourced from frame `104`, with supported lineage, eligible crop provenance, no ambiguity, and no hard-negative rejection.
   - Seq04 repeatability passed with semantic SHA-256 `f5b6e14c8801e9f0286f2eb8971e4c2379fb0f4430e95018e6bc96bc385819f2`.
   - promoted evidence: `reports/p015_positive_memory_bootstrap_f1fbb799_2026_07_26/`.

4. [x] [#17 — P1.6 Prevent target fragments becoming negatives](https://github.com/FRCTavares/IST-Thesis-Code/issues/17) — DONE
   - completed on 27 July 2026 from clean baseline `c32c01691e0c6281e92aeee8880fa9bf04ecb488`;
   - canonical regressions cover duplicate fragments, protected-anchor support, trusted-gallery history, and uninterrupted same-ID continuity;
   - protected positive support gates hard-negative admission; the canonical deterministic `0.95–1.01` four-sequence sweep selected `0.95`, and a second deterministic `0.95` pass reproduced identical semantic digests and evaluator metrics on all four sequences; promoted evidence is packaged under `reports/p017_fragment_safety_f1049263_2026_07_27`.
   - visual review confirmed the canonical May ByteTrack identity handover remains at `50.233 s`; `49.999–50.233 s` is now classified as `occlusion_ambiguity` with ID `1`, and annotation dropdown labels include filenames to distinguish canonical and autonomous CSVs.
   - phase 4; engineering; complete.

5. [x] [#18 — P1.7 Add hard-negative lifecycle](https://github.com/FRCTavares/IST-Thesis-Code/issues/18) — DONE
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

6. [ ] [#44 — P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)](https://github.com/FRCTavares/IST-Thesis-Code/issues/44) — IN PROGRESS
    - Started on 28 July 2026 from audited baseline `ca5ac1601d1a5caa0e082b83b1524eefb8b749af` on branch `issue-44-selective-hailo-reid`.
    - Read-only repository, GitHub, runtime, model, Hailo, test, and hardware audits passed before branching.
    - The current CPU MARS path is synchronous and encodes every crop-quality-eligible tracker candidate at each eligible compute interval; `appearance_ambiguous_only` controls later score usage rather than crop selection.
    - Initial scope is to instrument the unchanged CPU baseline, then introduce a non-mutating CPU candidate-request policy before implementing or promoting any Hailo backend.
    - The tracked `repvgg_a0_person_reid_512.hef` is a Hailo-8 UINT8 256x128-to-512D model and remains unvalidated against the canonical 128D CPU MARS representation.
    - Baseline synchronous CPU workload telemetry now records encoding-eligible crops, backend calls, requested and returned crops, valid embeddings, and backend wall time; live ROS status publishes the measured duration while deterministic replay normalises it to `0.0`; the expanded request-policy status contract now uses semantic-digest schema `tim_mars_replay_generated_fields_v4`.
    - The May hard-reentry live pilot recorded 183 CPU MARS calls and 370 crops over 67.439 s. The 419.541 ms maximum was isolated to the first-call warm-up; steady-state backend latency was 46.598 ms mean, 56.666 ms p95, and 61.288 ms p99, while non-backend callback overhead was 1.205 ms mean and backend wall time correlated 0.999979 with total callback latency.
    - The unchanged-CPU four-sequence baseline covered 337.399 s, 1,069 synchronous backend calls, and 2,972 requested crops. Aggregate steady-state backend latency was 52.396 ms and occupied 16.539% of replay time; all requested crops returned valid embeddings.
    - The pure CPU candidate-request policy is wired through an encoder-only request mask, with the complete candidate list retained for crop quality, cache reuse, and tracker lifecycle accounting. ROS parameters, canonical configuration, live status diagnostics, and deterministic replay now expose `all_candidates` and `geometry_winner`; replay also supports a controlled compute-interval override. The live safety-replay wrapper resolves both controls from the canonical YAML or explicit environment overrides, normalises integer-form interval values such as `0` to double-valued ROS literals such as `0.0`, forwards them to the node, and records their effective values and sources in run provenance. The unchanged canonical default remains `all_candidates`, and the selective-versus-forced-frequent CPU matrix is complete.
    - The completed 16-run live CPU matrix compared `all_candidates` and `geometry_winner` at 250 ms and forced 0 ms intervals across the four canonical sequences. At 250 ms, `geometry_winner` reduced requested crops by 64.2% and steady backend wall time by 59.2%; at 0 ms, the corresponding reductions were 60.1% and 49.0%. However, material correctness regressions occurred on `seq03_crossing`, `seq04_occlusion`, and the worst correct-ratio change was -12.3 pp on `seq03_crossing`. Forced-frequency `all_candidates` increased requested crops by +64.1% and steady backend wall time by +50.4% relative to the 250 ms reference without a sufficient safety benefit to justify it as the default. Therefore `all_candidates` at 250 ms remains the CPU safety reference; `geometry_winner` is not accepted as the canonical policy, and the Hailo path must retain ambiguity-aware multi-candidate selection or a safe CPU fallback.
    - The Hailo architecture audit at `2147f624cb54caa7f8294951f8dcf73928ad4eec` confirmed a synchronous in-callback CPU encoder, HailoRT 4.23.0 with an available Hailo-8 device, and a `repvgg_a0_person_reid_512.hef` contract of UINT8 NHWC 256x128x3 input to UINT8 512D output. This representation is incompatible with the canonical 128D CPU MARS space, so MARS cannot silently act as an in-session RepVGG fallback or share its appearance memory. A hardware-independent causal request/result contract now defines embedding-space identity, compatible startup fallback, a bounded latest-data queue, deadline and lifecycle-generation checks, reordered-result rejection, explicit failures, and immutable normalised embedding acceptance. It is not yet wired into the live runtime or Hailo worker.
    - Building on causal-contract commit `148830da484c2e66b3a4f9d37302ff503cc52316`, the RepVGG host tensor boundary is now explicit. Copied BGR candidate crops are resized to the HEF VStream shape, converted to contiguous RGB UINT8 NHWC tensors, and host normalization is intentionally omitted because it is compiled into the model. The output boundary requires FLOAT32 host tensors, rejects quantized bytes and malformed vectors, and produces immutable L2-normalized 512D embeddings. A deterministic injected worker validates the complete queue-to-worker-to-causal-result flow, explicit backend failures, representation mismatch, and lifecycle staleness without importing HailoRT or changing the live runtime.
    - A hardware feasibility probe at `f9fb319b173888e17c346a7d3d5738149642c509` configured canonical `yolov6n.hef` and the tracked RepVGG ReID HEF on one `ROUND_ROBIN` Hailo-8 VDevice and alternated three detector/ReID cycles successfully. Mean synthetic detector latency was 13.528 ms and mean ReID latency was 7.431 ms; all ReID outputs were finite, immutable, L2-normalized 512D embeddings, and the device was released cleanly. The direct detector backend now uses one perception-owned shared runtime that preserves the existing detector `infer()` result contract, optionally configures RepVGG with FLOAT32 host output, serializes all device calls behind one lock, closes partial startup safely, and fails closed when ReID is unavailable. ROS request/result transport is still intentionally absent.
    - Building on shared-runtime commit `e08882833300bff93b10dcc26365479269836814`, the cross-process causal transport contract now defines dedicated request and result ROS messages plus strict conversion helpers. Requests preserve the complete backend descriptor, host-monotonic submission and deadline values, source timestamps, frame and track generations, candidate identity, source bounding box, and an owned contiguous `bgr8` crop. Results echo only the request and backend contract, host-monotonic worker timing, and one explicit success-with-embedding or failure-with-error state; the authoritative lifecycle provenance remains in the TIM-MARS in-flight queue. Round-trip tests prove message validation and queue-to-worker-to-result-gate acceptance without Hailo hardware. Live ROS publisher/subscriber and QoS wiring remain intentionally separate.
    - Building on causal-message commit `e8fdae4924eb43fd5022e87c59e5039e360ae679`, the perception process now owns an optional bounded RepVGG request executor. It is disabled by default and requires the direct Hailo backend plus an explicit ReID HEF. A volatile best-effort KEEP_LAST subscription performs only strict deserialization and bounded enqueueing; one dedicated worker executes RepVGG through the detector-owned shared VDevice and publishes explicit success, backend failure, malformed-request, supersession, overflow, expiry, or shutdown-cancellation results. The queue retains the newest pending crop per track, drops the oldest pending item on overflow, serializes service execution, and stops before the Hailo engine is closed. TIM-MARS request production, live lifecycle generations, causal result application, and appearance-cache integration remain intentionally separate.
    - Building on bounded-executor commit `2eb0458c48c0d9a3c68ae8a23cb3d77dfc6a208c`, the ROS-free TIM-MARS runtime can now stage disabled-by-default immutable RepVGG request crops only when the existing CPU scheduling and crop-quality path would perform fresh work. Each staged crop reuses the authoritative appearance frame and track generations, preserves candidate and source provenance, and owns a contiguous read-only BGR copy. CPU MARS scoring and its 128D memories remain unchanged; ROS publication, causal queue ownership, result validation, and RepVGG cache application remain separate.
    - Building on request-crop staging commit `e37cae71216f3b2f030299e27f66e012d19e783c`, TIM now owns a disabled-by-default causal RepVGG transport ledger. Staged crops become complete monotonic-ID requests, are admitted and moved to in-flight state before publication, and use volatile best-effort topics matching the perception executor. Returned messages are strictly decoded and validated against deadlines, backend identity, source ordering, and the current authoritative frame and track generations. Selection, clear, source-frame reset, publication failure, and shutdown cancel all outstanding work, so late results are rejected. Accepted 512D vectors are retained only as isolated diagnostic observations; CPU MARS candidate features, 128D memories, target scoring, and selection decisions remain unchanged. RepVGG cache, ranking, and decision integration remain separate.
    - Building on TIM causal-transport commit `b778644d07d0aac0925a24e1c42449f34bf292b4`, the perception process now exposes a periodic, versioned `/perception/reid/status` JSON snapshot for hardware evidence. The topic is published in both reference and treatment conditions and reports whether ReID is enabled, the active inference backend, malformed requests, shared-engine active calls, bounded queue depth and maximum depth, in-flight request identity, submitted and executed work, successful and failed results, rejections, emitted results, and reason counts. Detector latency remains available independently through `/timing`. The paired hardware evidence runner remains to be implemented.
    - Building on diagnostics commit `0b8916b685588d0200b33e58edf6381d5fdf50c1`, a dedicated paired Hailo evidence runner and ROS collector now define the detector-contention experiment. Each repetition replays the identical camera and `/tracks` streams twice: a direct-Hailo detector reference with both ReID endpoints disabled, followed by a treatment with the perception RepVGG executor and TIM causal transport enabled. Both conditions preserve CPU MARS `all_candidates` scheduling at 250 ms and fixed target selection. The collector records detector `/timing`, perception executor status, causal requests and results, and TIM status as JSONL, then derives detector, queue, worker, end-to-end, success, failure, and maximum-depth summaries. The runner records ROS bags, process resource samples, hardware metadata, and a paired comparison without enabling RepVGG ranking or memory updates. Hardware execution and evidence promotion remain outstanding.
    - A pre-smoke message-contract review at commit `2e27adc0395245bb9f190dad657d631e0a38e1ea` found and corrected an evidence-only schema mismatch: the ROS request defines flat `crop_height` and `crop_width` fields, while the first collector version attempted to read a nonexistent nested crop object. Runtime-shaped regression tests now enforce the generated request interface before any hardware evidence is collected. The one-repetition smoke pair remains outstanding.
    - The first hardware smoke at commit `a4e66a1cdaacb7415ab68c4cc278e52c62404632` completed both evidence conditions and produced 271 successful RepVGG results with zero backend failures. Preliminary detector inference increased from 6.037 ms to 9.677 ms mean and from 6.153 ms to 13.336 ms p95, while the executor queue reached a maximum depth of 2. The run is not yet promoted as accepted evidence because final hygiene found that `ros2 run` wrapper PIDs exited while their TIM and perception child executables remained active. The runner now starts every background job in its own session, signals the complete process group, waits through INT/TERM/KILL escalation, and verifies that no unmatched smoke process remains. A clean one-repetition rerun was therefore required before the matrix.
    - The clean rerun at commit `5903668335b3614fd9ff9fa40dec773c866b171d` passed process, Hailo-release, repository, and evidence hygiene, but exposed a causal-ledger defect under BEST_EFFORT request loss. TIM published 367 requests, the perception executor received and completed 240, 239 accepted results were visible in the final TIM snapshot, and 128 requests remained in flight after their 500 ms deadlines. The queue now expires only overdue in-flight requests, the transport removes matching registry entries and counts `expired_in_flight`, and a periodic TIM timer reconciles deadlines even after the final `/tracks` message. The timer republishes the latest base status with fresh transport diagnostics so evidence can observe a drained ledger; late results remain rejected as unknown and cannot restore state. CPU MARS scoring, 128D memories, RepVGG diagnostic isolation, BEST_EFFORT QoS, and disabled-by-default activation are unchanged. The reconciled clean hardware rerun passed; the repeated matrix remains required.
    - The reconciled hardware smoke at commit `52c84c2a8258d32127c124d39317b7af2f5ddf04` passed the complete acceptance gate. TIM constructed and published 370 requests, the perception executor completed 267 successfully with zero failures or rejections, TIM accepted 264, and 106 unresolved BEST_EFFORT requests expired explicitly. Request accounting closed exactly and final `in_flight` was zero. The detector inference delta was +3.518 ms mean and +6.729 ms p95, the executor queue reached depth 2, and the shared Hailo engine remained serialized at one active call. Process cleanup, Hailo release, repository cleanliness, and root-log hygiene passed. Compact promoted evidence is tracked at `reports/p044_reconciled_reid_smoke_52c84c2a_2026_08_02`. This accepts the smoke only; ranking equivalence, safety evaluation, sustained onboard evidence, and transport-policy justification remain outstanding.
    - The three-repetition paired hardware matrix at commit `c3b346330b4f67894ac07d69f2ea4dff3d7ed333` passed every causal, executor, shared-engine, process, and repository-hygiene gate. Across 1,113 constructed and published requests, the executor completed 766 with zero backend failures, TIM accepted 763, and 350 unresolved requests expired explicitly; every repetition ended with zero in flight. Detector inference increased by +3.645 ms mean and +7.075 ms p95. The per-run mean delta stayed within +3.602 to +3.694 ms, the executor queue reached depth 2, and Hailo remained serialized at one active call. Request delivery to the executor was only 64.69% to 71.70% (68.82% mean), while result delivery back to TIM was 99.25% to 100% (99.62% mean). Therefore the matrix validates repeatability and safe reconciliation but does not yet justify the final architecture: the low BEST_EFFORT request-delivery rate must be defended as intentional latest-data shedding or compared against another transport/admission policy. Promoted evidence is tracked at `reports/p044_hailo_reid_matrix_c3b34633_2026_08_02`.
    - Required evidence remains CPU displacement, selective versus forced-frequent load, causal asynchronous provenance, queueing and detector contention, quantised ranking and decision equivalence, safety and availability, and sustained onboard behaviour.
    - Complete this before final runtime/cost characterisation in #32, the architecture comparison in #58, and the final claim freeze in #39.

7. [ ] [#20 — P1.8 Rename misleading fields](https://github.com/FRCTavares/IST-Thesis-Code/issues/20)
   - phase 5; engineering.

8. [ ] [#21 — P1.9 Add motion evidence only if it helps](https://github.com/FRCTavares/IST-Thesis-Code/issues/21)
   - phase 5; experiment.

9. [ ] [#25 — P1.10 Improve bbox evaluation](https://github.com/FRCTavares/IST-Thesis-Code/issues/25)
   - phase 6; experiment; use the transform contract from #53.

10. [ ] [#26 — P1.11 Add event and recovery metrics](https://github.com/FRCTavares/IST-Thesis-Code/issues/26)
    - phase 6; experiment; use the shared evaluator semantics from #24.

11. [ ] [#30 — P1.12 Add broader sequences](https://github.com/FRCTavares/IST-Thesis-Code/issues/30)
    - phase 7; experiment; includes properly qualified held-out live evidence
      from #50 when available and must expose the event types needed to compare
      candidate loss, identity confusion, tracker fragmentation, integrated
      appearance association, and selective TIM-MARS recovery fairly.

12. [ ] [#31 — P1.13 Parameter sensitivity](https://github.com/FRCTavares/IST-Thesis-Code/issues/31)
    - phase 7; experiment.

13. [ ] [#58 — P1.13+ Compare lightweight tracker + TIM-MARS against integrated appearance-aware tracking](https://github.com/FRCTavares/IST-Thesis-Code/issues/58)
    - phase 7; experiment; compare separately calibrated lightweight
      appearance-free tracker + TIM-MARS systems against integrated
      appearance-aware tracker references using held-out controller-facing
      safety metrics and the canonical Issue #32 safety–availability–cost
      methodology. DeepSORT + TIM-MARS is diagnostic rather than the intended
      architecture.

14. [ ] [#54 — P1.21 Make raw-image transport, dataset recording, and live provenance explicit](https://github.com/FRCTavares/IST-Thesis-Code/issues/54)
    - phase 10; live-system; feeds #32, #37, and #50; owns the missing integrated-camera `/camera/fps` publisher and recording-contract repair, deferred until the P0 authority/coordinate/freshness blockers are complete.

15. [ ] [#32 — P1.14 End-to-end runtime, compute budget, and onboard resource characterisation](https://github.com/FRCTavares/IST-Thesis-Code/issues/32)
    - phase 7; live-system; owns the canonical per-stage latency and queueing
      timebase, wall-clock versus CPU-service-time separation, p50/p90/p95/p99
      and maximum distributions, cadence/jitter/drop accounting, selective-ReID
      invocation and cache statistics, per-process/thread CPU, memory, raw-image
      DDS/QoS bandwidth, Hailo contention, sustained thermal/throttling evidence,
      and reproducible power measurements where available. It also measures the
      incremental cost of TIM-MARS and supplies the runtime contract for the
      lightweight-versus-integrated tracker comparison.

16. [x] [#35 — P1.15 Remove unsupported experimental runner parameters](https://github.com/FRCTavares/IST-Thesis-Code/issues/35) — DONE
    - Completed on 25 July 2026.
    - The obsolete anchor-drift and group-split overrides were removed from the final replay runner when the canonical TIM-MARS configuration was frozen.
    - Added a process-aware regression test that verifies each ROS parameter override is declared by its receiving node and rejects reintroduction of the obsolete experimental parameter names.

17. [x] [#36 — P1.16 Clean package metadata](https://github.com/FRCTavares/IST-Thesis-Code/issues/36) — DONE
    - Completed on 25 July 2026.
    - Replaced the generated `thesis_bringup` version, description, maintainer, and license placeholders with a consistent `0.1.0` MIT package identity.
    - Declared the package's ROS and system-Python runtime dependencies, documented the platform-specific Hailo boundary, and added a clean-checkout rosdep/build procedure.
    - Added a package-metadata regression contract and validated the complete `thesis_bringup` test suite and package build.

18. [ ] [#55 — P1.22 Repair and test the live UI launch, build, and access-control contract](https://github.com/FRCTavares/IST-Thesis-Code/issues/55)
    - phase 10; engineering; coordinate target-control behavior with #52 and path documentation with #33.

19. [ ] [#40 — P1.18 Write the method from the final implementation](https://github.com/FRCTavares/IST-Thesis-Code/issues/40)
    - phase 9; experiment/documentation.

20. [ ] [#41 — P1.19 Add explicit limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41)
    - phase 9; experiment/documentation.

21. [ ] [#42 — P1.20 Build final figures](https://github.com/FRCTavares/IST-Thesis-Code/issues/42)
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
