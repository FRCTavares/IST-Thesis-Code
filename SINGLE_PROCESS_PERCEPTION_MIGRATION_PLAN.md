# Single-Process Perception Pipeline Migration Plan

## Single-Process Perception Pipeline (No Frame ZMQ)

Date: 2026-04-11

Owner: Thesis-Code runtime pipeline

## 1. Executive Summary

Goal: remove per-frame host-to-container ZMQ request/reply transport and move to a single-process perception pipeline where camera capture and Hailo detection run in the same runtime path.

Expected outcome:

- lower frame-to-detection jitter
- fewer timeout and retry events
- higher sustained detection throughput
- simpler timing model and easier bottleneck attribution

Current evidence from latest run:

- camera stream was not stable at 30 FPS (average around high teens)
- detector loop showed significant cadence jitter and timeout events
- per-frame request/reply behavior is currently sensitive to queue backpressure and drop policies

Conclusion: the current architecture can hide the real detector cost behind transport and queue dynamics. The single-process perception pipeline is the correct long-term architecture.

## 2. Current State and Problem Statement

Current path:

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

### A1. Freeze message contracts

- Keep Detection2DArray fields and frame_id semantics compatible.
- Keep Timing message fields required by dashboard and reports.
- Keep /camera/fps publication behavior compatible.

Done criteria:

- Interface compatibility table approved.
- No required changes in tracker/target subscriber code paths.

### A2. Select deployment shape

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

### B1. Create new node skeleton

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

### B2. Integrate camera handling

Reuse from existing camera node:

- media device resolution and fallback behavior
- sensor entity discovery
- reopen loop and error handling
- fps publication logic

Done criteria:

- camera stability and reopen behavior equivalent to current camera node.

### B3. Integrate Hailo inference in-process

Requirements:

- no per-frame network serialization
- keep model selection support (yolov6n, yolov8s, yolov8m)
- preserve person-label filtering behavior

Done criteria:

- model loads and inference output parity confirmed on static test bag/video.

### B4. Detection mapping parity

Maintain output mapping:

- normalized or pixel conversion parity with current pipeline
- class label and score behavior
- min_score filtering behavior

Done criteria:

- tracker node behavior unchanged under same input scenes.

### B5. Timing instrumentation parity

Need timing fields that preserve analysis compatibility:

- pre_ms
- infer_ms
- post_ms
- e2e_det_ms
- publication interval stats

Done criteria:

- timing analysis tools run without schema break.

## Workstream C: Startup and Operations Integration

### C1. Add perception mode switch in startup

Update startup script to support:

- --perception-mode legacy
- --perception-mode single-process

Legacy mode:

- current camera + inference_client + detection_zmq route.

Single-process mode:

- new perception_pipeline_node route.

Done criteria:

- both modes selectable and logged in run config output.

### C2. Keep rollback path

Rollback rule:

- single flag must restore legacy behavior with no code edits.

Done criteria:

- documented rollback command tested.

### C3. Update operational docs

Update:

- RUNBOOK.md
- README.md

Content:

- how to run new mode
- baseline test commands
- rollback command

Done criteria:

- docs match runtime behavior.

## Workstream D: Validation Matrix

### D1. Functional correctness

Scenarios:

- indoor static target
- moving target
- occlusion/reacquisition
- no-target periods

Checks:

- detections published continuously
- tracker IDs stay stable relative to baseline
- target selector behavior preserved

### D2. Performance validation

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

### D3. Stability validation

Long-run test:

- 30 minute run

Checks:

- no process crashes
- no progressive fps decay trend
- no runaway memory growth

### D4. Regression checks

Ensure unchanged behavior for:

- dashboard telemetry stream
- recordings and CSV export
- control tab model/tracker changes

## Workstream E: Cutover and Cleanup

### E1. Controlled default switch

Step plan:

1. Ship with legacy default.
2. Run repeated validation in single-process mode.
3. Flip default only after passing gates.

### E2. Legacy path deprecation

After sustained stability:

- mark inference_client_node + detection_zmq frame transport path as deprecated.
- keep one release window before full removal.

### E3. Final cleanup

Eventually remove:

- frame ZMQ request/reply transport code
- unused flags and dead metrics

## 6. File-Level Change Plan

Likely touched files:

Primary implementation:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py (new)
- ros2_ws/src/thesis_bringup/launch/camera_bringup.launch.py (or new launch path)

Startup/orchestration:

- tools/start_live_stack.sh

Compatibility and control:

- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py

Docs:

- RUNBOOK.md
- README.md

Possibly deprecated later:

- ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py
- infer_service/detection_zmq.py

## 7. Risk Register

Risk 1: camera init logic regressions

- Impact: startup failures, unstable camera path
- Mitigation: reuse existing camera media initialization logic with minimal change

Risk 2: Hailo runtime dependency mismatch in target deployment shape

- Impact: blocked implementation
- Mitigation: decide Shape H vs Shape C in Workstream A before coding deep path

Risk 3: dashboard/video overhead masking improvements

- Impact: misleading benchmarks
- Mitigation: always benchmark lean and full modes separately

Risk 4: timing schema break

- Impact: analysis scripts and reports break
- Mitigation: preserve timing field contract for first cut

Risk 5: rollback not immediate

- Impact: operations downtime
- Mitigation: keep legacy mode behind one startup flag until sign-off

## 8. Acceptance Gates

Gate G1: functional parity

- tracker/target pipeline behavior accepted in controlled scenes

Gate G2: performance uplift

- single-process mode beats legacy in sustained det_fps and jitter metrics

Gate G3: stability

- no crash and no severe decay in 30-minute run

Gate G4: operational readiness

- startup, docs, and rollback validated by command-line runbook tests

## 9. Rollback Plan

Immediate rollback policy:

- restart stack in legacy mode via startup flag
- do not require code revert for emergency rollback

Rollback validation:

- verify detections, target, and dashboard telemetry within 2 minutes after switch

## 10. Suggested Execution Order

Day 1:

- Workstream A complete
- node scaffold for Workstream B1

Day 2:

- Workstream B2/B3 initial implementation
- first detections out

Day 3:

- Workstream B4/B5 parity and instrumentation
- Workstream C startup integration

Day 4:

- Workstream D full benchmark matrix
- document outcomes and decide cutover readiness

## 11. Definition of Done

- single-process perception mode implemented and runnable
- measurable det_fps and cadence stability improvement over legacy path
- no blocking regressions in tracker/target/dashboard workflows
- startup script supports both legacy and new mode
- runbook and README updated
- rollback tested and documented

## 12. Tomorrow Focus (2026-04-14)

Primary objective:

- achieve and sustain 30 FPS end-to-end with dashboard enabled in single-process mode.

Constraints:

- keep single-process perception path enabled (`--perception-mode single-process`).
- keep dashboard enabled (no `--no-dashboard`).
- do not use legacy frame ZMQ path as the primary solution.

Target metrics (full stack, dashboard on):

- `/camera/image_raw`: mean >= 30 Hz
- `/detections`: mean >= 30 Hz
- `/timing`: mean >= 30 Hz
- `/camera/dashboard`: mean >= 30 Hz
- no recurring stale-target oscillation caused by timing stalls

Execution plan for tomorrow:

1. Lock the model during the run and avoid unintended heavy model switches.
2. Establish baseline with dashboard on and web video on, collect 10-minute metrics.
3. Profile per-node CPU and stage timing to isolate dominant bottleneck.
4. Apply highest-impact tuning first (camera format/rate path, perception publish cadence, tracker cost, dashboard transport path).
5. Re-run 10-minute validation after each major change; keep only changes that improve all target metrics.

Acceptance for tomorrow session:

- all four core topics sustain 30 Hz in full mode with dashboard enabled,
- no timeout storms in perception logs,
- no control instability attributable to stale target timing.
