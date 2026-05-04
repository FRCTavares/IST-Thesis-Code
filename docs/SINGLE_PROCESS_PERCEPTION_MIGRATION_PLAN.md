# Single-Process Perception Pipeline Migration Plan

## Single-Process Perception Pipeline (No Frame ZMQ)

Date: 2026-04-13 (updated after live validation)

Owner: Thesis-Code runtime pipeline

## 0. Current Operational Status (2026-04-15)

- Launcher default is single-process mode (`tools/start_live_stack.sh` defaults to `--perception-mode single-process`).
- Legacy ZMQ mode remains intentionally available as rollback (`--perception-mode legacy`).
- Queue-buffer operating-point decision and sustained full-stack tail-latency improvements are still active work.
- Phase-2 test with concurrent in-flight calls on a single engine (`async_max_inflight=2`) failed to improve throughput and significantly worsened latency tails; this path is not viable as a live default.
- Safe live baseline is now frozen at: `async_max_inflight=1`, `allow_stub_fallback=false`, tracker timing topic off, camera publish `640x640`.
- This document remains the optimization and validation ledger, while `RUNBOOK.md` is the command source of truth.

## 1. Executive Summary

Goal: remove per-frame host-to-container ZMQ request/reply transport and move to a single-process perception pipeline where camera capture and Hailo detection run in the same runtime path.

Expected outcome:

- lower frame-to-detection jitter
- fewer timeout and retry events
- higher sustained detection throughput
- simpler timing model and easier bottleneck attribution

Current evidence from latest validated runs (single-process mode):

- camera startup now succeeds in healthy cycles with sensor trigger/rate controls applied
- internal camera publish cadence recovered near 30 FPS in full stack runs
- completed 10-minute three-run ablation matrix (full stack, no dashboard, no tracker/target/control) identifies tracker/target/control as dominant bottleneck
  - A (full stack): `/timing` 8.40 Hz, `e2e_det_ms` p95 124.59, `pub_dt_ms` p95/p99 162.93/267.70
  - B (no dashboard): `/timing` 8.01 Hz, `e2e_det_ms` p95 127.62, `pub_dt_ms` p95/p99 159.81/229.70
  - C (no tracker/target/control): `/timing` 10.00 Hz, `e2e_det_ms` p95 94.15, `pub_dt_ms` p95/p99 111.05/120.05
- latency center improved materially and jitter tails improved when tracker/downstream path is removed
- TEVS control timeout (`Connection timed out`) is now fail-fast before opening `/dev/video0` to reduce wedge risk
- D-state camera failures remain reboot-required, with startup preflight detection now in place
- iterative tracker/perception tuning passes improved comparable full-stack performance to:
  - pass7 (`--perception-hailo-queue-buffers 2`, GC on): `/timing` 9.49 Hz, `e2e_det_ms` p95/p99 106.61/113.13, `pub_dt_ms` p95/p99 170.96/201.42
  - relative to baseline full-stack: throughput and p99 tails improved strongly; `pub_dt_ms` p95 remains above baseline target
- pass8 (`--perception-hailo-queue-buffers 1`) produced very large gains (`/timing` 11.20 Hz, `e2e_det_ms` p95 89.13, `pub_dt_ms` p95/p99 94.31/107.35), but log review showed long stretches with zero detections, so this run is treated as provisional pending controlled workload-matched reruns
- live timing collector now includes detection-stream load stats (`detections_per_msg` and `zero_ratio`) to enforce comparability between runs
- phase2-inflight2 validation (`--perception-async-max-inflight 2`, queue buffers 2, videoconvert on) showed no meaningful throughput gain (`/timing` ~9.8 Hz unchanged) and large latency regressions (`container_queue_ms` p95 ~113.68 -> ~197.46, `infer_ms` p95 ~9.62 -> ~108.15, `e2e_det_ms` p95 ~123.88 -> ~304.82), with invariants still clean and zero-detection ratio stable.
- recovery validation at frozen baseline (`recovery_inflight1_20260415_222443`, `async_max_inflight=1`, videoconvert on) restored latency close to pre-phase2 baseline and far below inflight2 regression (`container_queue_ms` p95 117.14, `infer_ms` p95 11.06, `e2e_det_ms` p95 130.00, `e2e_target_ms` p95 135.84, zero-detection ratio 0.0).
- recovery run throughput was lower than the earlier inflight1 baseline (`/timing` 8.63 Hz vs 9.80 Hz) and `pub_dt_ms` p95 was higher (181.91 vs 127.50), with modestly higher detection load (`detections_per_msg.mean` 1.07 vs 1.00), so backend-overhead ablations should continue under workload-matched reruns.
- paired same-session videoconvert ablation (`vc_ablation_20260415_223635`), with all other knobs frozen (`async_max_inflight=1`, fail-fast on, tracker timing off), showed workload comparability and no invariant failures but no material latency win from disabling videoconvert: `container_queue_ms` p95 worsened (106.80 -> 110.15), `e2e_det_ms` p95 worsened (115.65 -> 121.87), cadence dipped slightly (9.73 -> 9.60 Hz), and `pub_dt_ms` tails regressed strongly (p95 118.69 -> 160.00, p99 148.49 -> 196.54).
- first single-owner redesign smoke run (`owner_validate_20260415_230120`, frozen defaults, 45s) kept workload comparable and invariants clean, with stable `infer_ms` p95 (8.69 -> 8.54), but did not show material latency/cadence gains versus frozen baseline (`/timing` 9.73 -> 9.66, `container_queue_ms` p95 106.80 -> 107.50, `e2e_det_ms` p95 115.65 -> 117.30); 10-minute confirmation was deferred as no-go for this iteration.

Conclusion: the single-process architecture is implemented and materially faster than legacy in comparable runs, and recovery at `async_max_inflight=1` is now revalidated. The current single-engine backend path still does not tolerate concurrent in-flight Python callers, and paired A/B evidence rejects `hailo_use_videoconvert=false` as a default. Next gains should focus on backend-path redesign rather than repeated launch-flag toggling.

## 1.1 Status Snapshot (2026-04-13)

- Done: single-process mode path wired into launcher, rollback flag preserved, camera diagnostics expanded, sensor rate-control tuning integrated.
- Done: dashboard publishing decoupled from raw publish path with subscriber-aware gating.
- Done: camera publish cadence in healthy runs is back near 30 FPS (`Camera FPS ... publish=~30`).
- Done: 10-minute three-run ablation matrix completed (full stack, no dashboard, no tracker/target/control); tracker/target/control path ranked as top bottleneck.
- Done: tracker and target-selector hot-path trims, tracker publish gating option, SORT low-cardinality association fast path, and perception executor/queue tunables integrated.
- Done: live timing collector extended with `/detections` load comparability stats.
- Done: queue-buffer decision helper added (`tools/decide_queue_buffer_default.py`) with workload-comparability gates (`detections_per_msg.mean` and `zero_ratio`) and explicit pass/fail decision output.
- Done: tracker callback overhead trimmed when profiling logs are off (avoid per-frame GC-count polling and section-timing overhead in non-profiling runs).
- Done: launcher now exposes tracker tuning knobs (`--tracker-iou-threshold`, `--tracker-max-age`, `--tracker-min-hits`, `--tracker-centre-gate`) and explicit GC-probe control.
- Done: `/timing` now publishes pre-infer queue wait as `container_queue_ms` (`t_infer_start_ns - t_pre_end_ns`) and canonical timing contract includes it for standard JSON reports.
- Done: perception path now supports async latest-frame inference mode (`async_latest_frame=true` default) to decouple image callback from infer wait and prefer freshness over stale frame processing.
- Done: launcher exposes perception toggles for explicit baseline-vs-candidate comparisons (`--perception-async-latest-frame-{on,off}`, `--perception-hailo-videoconvert-{on,off}`) without code edits.
- Done: Phase-2 concurrent-caller experiment at `async_max_inflight=2` is now classified as failed for this backend path; live default is reverted/frozen to `async_max_inflight=1` pending redesign.
- Done: post-revert recovery validation at frozen baseline completed (`recovery_inflight1_20260415_222443`) with latency metrics returned near pre-phase2 inflight1 levels and invariants clean.
- Done: paired same-session videoconvert A/B (`vc_ablation_20260415_223635`) completed and rejected videoconvert-off (`hailo_use_videoconvert=false`) as non-beneficial for this backend path.
- In progress: controlled Hailo queue-buffer decision (`--perception-hailo-queue-buffers 1` vs `2`) with matched detection workload.
- In progress: reducing full-stack `pub_dt_ms` p95 and `container_queue_ms` tails with backend-overhead ablations while preserving detection stability.
- Pending: long soak stability gate and queue-buffer operating-point decision.

## 2. Current State and Problem Statement

Current deployment modes:

1. legacy mode (`--perception-mode legacy`) keeps frame ZMQ request/reply transport for rollback.
2. single-process mode (`--perception-mode single-process`) runs `perception_pipeline_node` in-process and skips frame ZMQ transport.

Legacy path (kept for rollback):

1. camera node captures frames and publishes ROS images.
2. inference client receives ROS images, converts/resizes, and sends each frame over ZMQ REQ to container service.
3. container service pushes frames into GStreamer appsrc and returns detections via ROUTER reply.
4. tracker and target selector consume detections.

Observed issues in this design:

- frame transport and reply semantics are coupled to queue behavior.
- timeout and retry behavior can introduce bursts and visible cadence collapse.
- per-stage timing attribution is harder when transport and compute compete for the same wall-time budget.
- appsrc and leaky queues can drop data while REQ/REP still assumes one reply per request lifecycle.

Resulting risk:

- low and unstable effective det_fps even when detector compute itself is not saturated.

## 3. Target Architecture

Target architecture (single-process perception pipeline):

- one perception runtime path owns:
  - camera capture
  - image preprocessing
  - Hailo inference
  - post-processing
  - detection publication
  - timing publication
- no per-frame ZMQ message path between host node and container service.
- ROS outputs remain stable for downstream compatibility:
  - /detections
  - /timing
  - /camera/fps
  - optional /camera/dashboard (for UI)

Downstream nodes unchanged initially:

- tracker node
- target selector node
- control node
- dashboard bridge node

## 4. Scope Boundaries

In scope:

- perception data path redesign
- startup flow updates
- instrumentation and benchmark updates
- compatibility validation with tracker, target, and dashboard

Out of scope (for first cut):

- tracker algorithm redesign
- control law redesign
- frontend UX redesign
- model retraining

## 5. Workstreams and Tasks

## Workstream A: Architecture and Interface Freeze

### A1. Freeze message contracts [DONE]

- Keep Detection2DArray fields and frame_id semantics compatible.
- Keep Timing message fields required by dashboard and reports.
- Keep /camera/fps publication behavior compatible.

Done criteria:

- Interface compatibility table approved.
- No required changes in tracker/target subscriber code paths.

### A2. Select deployment shape [DONE]

Two acceptable implementation shapes:

Shape H (preferred):

- single host ROS node with camera + Hailo inference in-process.

Shape C (fallback):

- single container process with direct camera access and ROS publication.

Decision criteria:

- operational simplicity
- measured throughput and jitter
- reproducibility on Pi target

Done criteria:

- one shape selected and documented.

## Workstream B: Single-Process Node Implementation

### B1. Create new node skeleton [DONE]

Proposed file:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py

Responsibilities:

- initialize camera media pipeline (reuse proven logic from camera_capture_node)
- ingest frames
- execute Hailo inference
- publish detections and timing
- publish optional dashboard image stream

Done criteria:

- node starts and runs with no dependencies on inference_client_node and detection_zmq.py data path.

### B2. Integrate camera handling [MOSTLY DONE]

Reuse from existing camera node:

- media device resolution and fallback behavior
- sensor entity discovery
- reopen loop and error handling
- fps publication logic

Done criteria:

- camera stability and reopen behavior equivalent to current camera node.

### B3. Integrate Hailo inference in-process [FUNCTIONAL DONE, PERF TUNING IN PROGRESS]

Requirements:

- no per-frame network serialization
- keep model selection support (yolov6n, yolov8s, yolov8m)
- preserve person-label filtering behavior

Done criteria:

- model loads and inference output parity confirmed on static test bag/video.

### B4. Detection mapping parity [IN PROGRESS]

Maintain output mapping:

- normalized or pixel conversion parity with current pipeline
- class label and score behavior
- min_score filtering behavior

Done criteria:

- tracker node behavior unchanged under same input scenes.

### B5. Timing instrumentation parity [DONE]

Need timing fields that preserve analysis compatibility:

- pre_ms
- infer_ms
- post_ms
- e2e_det_ms
- publication interval stats

Done criteria:

- timing analysis tools run without schema break.

## Workstream C: Startup and Operations Integration

### C1. Add perception mode switch in startup [DONE]

Update startup script to support:

- --perception-mode legacy
- --perception-mode single-process

Legacy mode:

- current camera + inference_client + detection_zmq route.

Single-process mode:

- new perception_pipeline_node route.

Done criteria:

- both modes selectable and logged in run config output.

### C2. Keep rollback path [DONE]

Rollback rule:

- single flag must restore legacy behavior with no code edits.

Done criteria:

- documented rollback command tested.

### C3. Update operational docs [DONE]

Update:

- RUNBOOK.md
- README.md

Content:

- how to run new mode
- baseline test commands
- rollback command

Done criteria:

- docs match runtime behavior and launcher defaults.

## Workstream D: Validation Matrix

### D1. Functional correctness [IN PROGRESS]

Scenarios:

- indoor static target
- moving target
- occlusion/reacquisition
- no-target periods

Checks:

- detections published continuously
- tracker IDs stay stable relative to baseline
- target selector behavior preserved

### D2. Performance validation [IN PROGRESS]

Run each mode for at least 10 minutes:

- lean mode
- full stack mode

Collect:

- camera fps mean, p5, p95
- det_fps mean, p5, p95
- e2e_det_ms mean, p95
- timeout count
- dropped frame count

Success thresholds (first cut):

- no recurring timeout storms
- det_fps median materially above legacy baseline
- reduced pub_dt jitter versus legacy mode

### D3. Stability validation [PENDING]

Long-run test:

- 30 minute run

Checks:

- no process crashes
- no progressive fps decay trend
- no runaway memory growth

### D4. Regression checks [IN PROGRESS]

Ensure unchanged behavior for:

- dashboard telemetry stream
- recordings and CSV export
- control tab model/tracker changes

## Workstream E: Cutover and Cleanup

### E1. Controlled hardening with single-process default [IN PROGRESS]

Step plan:

1. Keep single-process as launcher default.
2. Run repeated validation and workload-matched queue-buffer comparisons.
3. Keep legacy rollback path healthy while hardening single-process operation.

### E2. Legacy path deprecation [PENDING]

After sustained stability:

- mark inference_client_node + detection_zmq frame transport path as deprecated.
- keep one release window before full removal.

### E3. Final cleanup [PENDING]

Eventually remove:

- frame ZMQ request/reply transport code
- unused flags and dead metrics

## Workstream F: Backend Submission Redesign Experiment (Next)

### F1. Single-owner engine submission architecture [NEXT]

Target runtime shape:

1. latest-frame slot (overwrite policy)
2. one dedicated engine-owner submission thread
3. appsrc -> hailonet -> post path in the existing Gst backend
4. async result handling
5. ROS detections/timing publication

Key rule:

- many producers may overwrite the latest frame before submit, but only one owner submits to the engine.

### F2. Design rules [NEXT]

- one engine instance
- one submission owner
- latest-frame overwrite before submit
- no concurrent caller access to appsrc/engine
- no backlog growth
- stale frames dropped before infer, not after
- compact detections mapped back to ROS contracts

### F3. Closed branches (do not reopen until ownership model changes) [ACTIVE RULE]

- `async_max_inflight=2` branch is closed on current backend path
- `hailo_use_videoconvert=false` branch is closed on current backend path

### F4. Redesign success criteria [NEXT]

Compare against the frozen baseline only when workload comparability and invariants are satisfied.

Required outcomes:

- `/timing` Hz increases materially
- `container_queue_ms` p95 decreases materially
- `e2e_det_ms` p95 decreases materially
- `infer_ms` remains roughly stable
- detection workload remains comparable (`detections_per_msg.mean`, `zero_ratio`)
- invariant checks remain clean

## 6. File-Level Change Plan

Touched so far (confirmed):

Primary implementation and runtime:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py
- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py
- ros2_ws/src/thesis_bringup/launch/camera_bringup.launch.py

Startup/orchestration and diagnostics:

- tools/start_live_stack.sh
- tools/probe_camera_modes.sh
- tools/collect_live_timing_stats.py
- tools/decide_queue_buffer_default.py
- ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py

Compatibility and control:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py

Validation artifacts:

- artifacts/reports/timing/*.json

Docs:

- RUNBOOK.md
- README.md

Possibly deprecated later:

- ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py
- infer_service/detection_zmq.py

## 7. Risk Register

Risk 1: camera process enters kernel D-state (`vb2_fop_release`)

- Impact: process ignores SIGKILL; camera path unrecoverable without reboot
- Mitigation: preflight D-state detection in launcher and immediate reboot-required guidance

Risk 2: intermittent TEVS sensor control timeout during startup

- Impact: capture path can wedge if startup continues after timeout
- Mitigation: apply trigger/rate controls separately and fail-fast before opening `/dev/video0`

Risk 3: subscriber-side image rate under-reports true publish cadence

- Impact: misleading conclusions from `ros2 topic hz` on image topics
- Mitigation: use internal camera publish/capture FPS logs as primary source; treat CLI subscriber Hz as secondary

Risk 4: full-stack perception cadence bottleneck remains after camera recovery

- Impact: `/timing` and detection throughput stay below target despite 30 FPS camera publish
- Mitigation: profile perception/tracker stages and tune highest-cost stage first

Risk 5: dashboard/video overhead masking improvements

- Impact: misleading benchmark comparisons
- Mitigation: benchmark lean and full modes separately, then verify both; three-run ablation indicates dashboard is not the primary limiter

Risk 6: timing schema break

- Impact: analysis scripts and reports break
- Mitigation: preserve timing field contract for first cut

Risk 7: rollback path drift

- Impact: operations downtime during incident response
- Mitigation: keep legacy mode runnable via one startup flag and test rollback periodically

## 8. Acceptance Gates

Gate G1: functional parity [PARTIALLY MET]

- tracker/target/control/dashboard path runs in single-process mode without interface breaks

Gate G2: performance uplift [IN PROGRESS]

- camera-side publish cadence target is met in healthy runs; comparable full-stack runs now exceed baseline throughput and p99 tails, but `pub_dt_ms` p95 target is not yet consistently met

Gate G3: stability [IN PROGRESS]

- short/medium runs are successful; 30-minute soak with startup reliability gate still pending

Gate G4: operational readiness [PARTIALLY MET]

- startup mode switch and rollback flag exist; docs and repeated rollback validation still pending completion

## 9. Rollback Plan

Immediate rollback policy:

- restart stack in legacy mode via startup flag
- do not require code revert for emergency rollback

Rollback validation:

- verify detections, target, and dashboard telemetry within 2 minutes after switch

## 10. Suggested Execution Order (Remaining)

Step 1:

- run startup reliability soak (multiple cold starts, full stack, dashboard enabled)
- confirm no sensor timeout and no D-state preflight failures

Step 2:

- run 10-minute full-stack baseline in single-process mode
- collect timing artifact and camera internal FPS logs

Step 3:

- run a three-run ablation set (10 minutes each, same scene and model):
  - full-stack baseline: full stack with dashboard on
  - no-dashboard run: disable dashboard path (`--no-dashboard`)
  - no-tracker/target/control run: disable tracker-dependent path (`--no-tracker --no-target --no-control`)

Step 4:

- compare bottleneck deltas using the same metrics across the three runs:
  - `/timing` mean Hz
  - `e2e_det_ms` p95
  - `pub_dt_ms` p95 and p99
- choose next optimization target from the largest improvement:
  - if no-dashboard run >> full-stack baseline => prioritize dashboard path optimization
  - if no-tracker/target/control run >> full-stack baseline => prioritize tracker/downstream path optimization
  - if neither materially better => prioritize perception node hot path

Status:

- Completed. Result: no-tracker/target/control run >> full-stack baseline and no-dashboard run !> full-stack baseline, so tracker/downstream optimization is the highest-priority path.

Step 5:

- rerun 10-minute validation after each major change
- keep only changes that improve both center and tail metrics

Step 6:

- execute 30-minute stability run
- decide cutover readiness against gates G1-G4

## 11. Definition of Done

- single-process perception mode implemented and runnable
- measurable det_fps and cadence stability improvement over legacy path
- no blocking regressions in tracker/target/dashboard workflows
- startup script supports both legacy and new mode
- runbook and README updated
- rollback tested and documented

## 12. Historical Session Snapshot (2026-04-14)

This section is preserved as a dated execution log from the 2026-04-14 tuning session.

Primary objective:

- finalize the single-process full-stack queue-buffer operating point (`--perception-hailo-queue-buffers 1` vs `2`) under workload-matched conditions and lock a default that improves both throughput and jitter tails.

Constraints:

- keep single-process perception path enabled (`--perception-mode single-process`)
- keep dashboard enabled (no `--no-dashboard`)
- do not use legacy frame ZMQ path as the primary solution

Hard gates for tomorrow (full stack, dashboard on):

- 2 workload-matched 10-minute runs complete (`--perception-hailo-queue-buffers 1` and `2`)
- detection load comparability holds between the two queue-buffer settings:
  - `detections_per_msg.mean` within +/-10 percent
  - `detections_per_msg.zero_ratio` within +/-0.05 absolute
- no timeout storms in perception logs
- `/timing` mean >= 9 Hz in both runs

Stretch goals:

- `/timing` mean >= 10 Hz in workload-matched run
- `pub_dt_ms` p95 <= 160 ms and `pub_dt_ms` p99 <= 200 ms
- `e2e_det_ms` p95 <= 105 ms

Long-term target (unchanged):

- sustain 30 Hz across camera, detections, timing, and dashboard in full mode

Execution plan for tomorrow:

1. Build once and run controlled test with `--perception-hailo-queue-buffers 1` (GC on).
2. Capture 10-minute artifact with updated collector (includes detection load stats).
3. Run controlled test with `--perception-hailo-queue-buffers 2` (GC on) under the same scene/model.
4. Capture 10-minute artifact and compare queue-buffer settings (`1` vs `2`) with comparability gating.
5. If comparability gate fails, re-run the weaker side until load-matched.
6. Select default queue buffer value from load-matched results.
7. Execute one 30-minute soak using selected default.
8. Update this plan and runbook with the selected default and measured rationale.

Acceptance for tomorrow session:

- queue-buffer value decision (`--perception-hailo-queue-buffers 1` vs `2`) finalized with workload-matched evidence
- selected default passes one 30-minute soak without timeout storms
- no control instability attributable to stale target timing

### 12.1 Live Progress Update (2026-04-14)

Completed so far (full stack, dashboard on, single-process):

- q1 run completed and stored at `artifacts/reports/timing/q1_20260414_113923.json`
- run duration: 600.095 s
- invariants check passed (`tools/check_live_timing_invariants.py --duration 8.0`)
- canonical metrics schema validation passed

q1 measured metrics:

- `/timing` mean Hz: 8.075
- `e2e_det_ms` p95/p99: 131.279 / 140.887
- `pub_dt_ms` p95/p99: 177.471 / 229.368
- detection load baseline (`/detections`):
  - `detections_per_msg.mean`: 1.012
  - `detections_per_msg.zero_ratio`: 0.000

q2 attempts completed:

- q2 attempt 1: `artifacts/reports/timing/q2_20260414_120954.json`
  - `/timing` mean Hz: 7.666
  - `e2e_det_ms` p95: 133.045
  - `pub_dt_ms` p95/p99: 203.525 / 256.088
  - detection load: `detections_per_msg.mean` 1.122, `zero_ratio` 0.000
  - gate output (`artifacts/reports/timing/queue_decision_20260414_120954.json`): comparability PASS, min-Hz FAIL

- q2 attempt 2: `artifacts/reports/timing/q2_20260414_122044.json`
  - `/timing` mean Hz: 8.416
  - `e2e_det_ms` p95: 129.610
  - `pub_dt_ms` p95/p99: 180.401 / 237.636
  - detection load: `detections_per_msg.mean` 0.697, `zero_ratio` 0.313
  - gate output (`artifacts/reports/timing/queue_decision_20260414_122044.json`): min-Hz FAIL, comparability FAIL

Tracker-tuning attempt status:

- baseline tracker-tuning run (`artifacts/reports/timing/tracker_base_20260414_130952.json`) improved `/timing` to 9.687 Hz but had sparse detection workload (`zero_ratio` 0.805), so evidence is directionally useful but weak for cutover-quality comparisons.
- first tuned tracker run (`artifacts/reports/timing/tracker_tuned_20260414_132155.json`) is invalid for tracker analysis:
  - `/timing_tracker` and `/timing_target` samples are zero
  - tracker process crashed at startup with parameter type mismatch (`centre_gate` passed as integer literal)
  - root cause confirmed in tracker log: `InvalidParameterTypeException ... centre_gate ... expecting type 'DOUBLE'`
  - mitigation applied: launcher now normalizes float-valued tracker args, so integer inputs like `--tracker-centre-gate 320` are converted to `320.0` before ROS launch.
- second active-workload comparison pair completed after launcher normalization fix:
  - baseline: `artifacts/reports/timing/tracker_base_active_20260414_140437.json`
    - `/timing` 7.793 Hz, `e2e_det_ms` p95/p99 135.688/157.847, `pub_dt_ms` p95/p99 197.648/272.528, `track_ms` p95/p99 15.300/19.613
  - tuned: `artifacts/reports/timing/tracker_tuned_active_20260414_142832.json`
    - `/timing` 7.840 Hz, `e2e_det_ms` p95/p99 135.644/159.082, `pub_dt_ms` p95/p99 192.360/263.403, `track_ms` p95/p99 15.546/19.555
  - detection workload comparability passed (`detections_per_msg.mean` 1.001 vs 1.000, `zero_ratio` 0.000 vs 0.000)
  - keep/drop verdict for this tuned set: **drop for now** (mixed outcome: small throughput and `pub_dt_ms` tail gains, but tracker and target tails regressed with no material end-to-end win)

Current gate status:

- hard gate `/timing` mean >= 9 Hz is currently **not met** in both queue-buffer and active tracker-tuning runs
- workload comparability failed in the best-Hz q2 attempt due high zero-detection ratio
- queue-buffer default decision remains pending

Immediate next actions:

1. Keep baseline tracker settings (`--tracker-profile-off --tracker-gc-probe-off`) as the active reference and reject the current tuned variant from further rollout.
2. Run one additional optimization experiment on the perception hot path (pre/post/publication overhead) under the same active scene, then collect a fresh 10-minute report.
3. Re-attempt queue-buffer default decision only after a workload-matched run pair reaches `/timing` mean >= 9 Hz.

## 13. Optimization Playbook (All Levers)

This section enumerates all practical optimization levers, grouped by subsystem.
The order is prioritized by expected impact based on current ablation evidence.

### 13.1 Tracker and Downstream (Highest Priority)

Goals:

- reduce per-frame tracker and downstream CPU cost
- reduce long-tail stalls that inflate `pub_dt_ms` p99

Levers:

- simplify tracker association settings (tighten candidate set before expensive matching)
- reduce optional tracker outputs and per-frame payload size where not required
- reduce or gate expensive debug/profiling serialization paths in steady-state runs
- cap per-frame bookkeeping work and avoid repeated allocations in hot loops
- run tracker publication at a controlled cadence if full-rate publication is not required downstream
- ensure target selector/control consume only required fields and avoid redundant transforms

Validation signals:

- `/timing` Hz increases toward or above 10 in full stack
- `pub_dt_ms` p95/p99 decreases materially without detection regressions

### 13.2 Perception Pipeline Hot Path (Second Priority)

Goals:

- minimize preprocessing and postprocessing overhead
- keep detection cadence stable under load

Levers:

- preallocate reusable numpy buffers for resize/color/packing paths
- avoid unnecessary conversions and memory copies between ROS image and inference input
- reduce Python object churn in detection mapping and message creation paths
- trim log cadence and heavy string formatting in hot loops
- verify model/input configuration is fixed during experiments to avoid confounded runs

Validation signals:

- lower `pre_ms`/`infer_ms` p95 and reduced variance in `/timing`

### 13.3 Camera Path (Keep Stable, Avoid Regressions)

Goals:

- preserve validated ~30 FPS camera publish and startup reliability

Levers:

- keep current sensor control defaults unless repeated startup timeout appears
- maintain fail-fast on TEVS timeout and D-state preflight detection
- keep `device` fallback-to-openable-node behavior to avoid false startup failures

Validation signals:

- camera publish average remains in [29, 31] with stable startup logs

### 13.4 Dashboard and Web Video Path (Lower Priority)

Goals:

- prevent dashboard path from becoming a future limiter

Levers:

- keep subscriber-gated dashboard publish enabled
- tune dashboard resize quality/size only if dashboard becomes a measured limiter
- verify web stream settings do not induce extra load during benchmark runs

Validation signals:

- no significant regression in full-stack `/timing` when dashboard is enabled

### 13.5 ROS 2 and Messaging Layer

Goals:

- reduce middleware-induced queueing and callback contention

Levers:

- keep sensor-data QoS where appropriate and avoid depth inflation in hot image topics
- isolate heavy callbacks into separate callback groups/executors where beneficial
- minimize oversized message publication frequency when consumers do not need full rate

Validation signals:

- fewer bursty delays and improved tail metrics under identical workload

### 13.6 Host and Runtime Environment

Goals:

- reduce system jitter and thermal-related throttling risk

Levers:

- pin CPU governor/performance settings for benchmark consistency
- monitor thermal headroom and avoid benchmark runs under throttled states
- reduce background service noise during measurement windows

Validation signals:

- tighter run-to-run variance across repeated 10-minute tests

## 14. Optimization Experiment Backlog

Run one experiment at a time, then re-run 10-minute validation with the same scene and model.

1. [DONE] Tracker hot-loop allocation reduction and publish payload trim.
2. [DONE] Tracker low-cardinality association fast path.
3. [DONE] Target selector compute-path trim (single-pass ranking + sticky-ID preservation).
4. [DONE] Perception callback scheduling simplification (single-threaded executor).
5. [DONE] Detection-load comparability instrumentation in timing collector.
6. [IN PROGRESS] Hailo queue-buffer tuning with workload-matched `--perception-hailo-queue-buffers 1` vs `2` decision.
7. [PENDING] 30-minute soak validation on selected queue-buffer default.
8. [PENDING] Dashboard transport tuning only if measured as a limiter after queue decision.

Keep-change criteria:

- `/timing` Hz does not regress
- `e2e_det_ms` p95 decreases or holds
- `pub_dt_ms` p95 and p99 improve
- no functional regression in tracker/target/control behavior

Drop-change criteria:

- any throughput loss > 3 percent
- any significant p99 regression
- any startup reliability regression or increased timeout incidence
