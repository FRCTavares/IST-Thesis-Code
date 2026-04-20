# Daily Log - 2026-04-19 (Day 19) - Direct Runtime Cutover and Reboot Validation

## Overview

Focus: close the Hailo runtime compatibility blocker after reboot, cut over the single-process path to direct pyHailoRT execution, and validate live timing behavior with fresh evidence.

## Goals for Today

- [x] Complete post-reboot host/runtime verification.
- [x] Confirm direct pyHailoRT infer path is healthy on device.
- [x] Ensure single-process live launcher actually uses direct backend by default.
- [x] Capture and validate a fresh 120s direct-backend timing artifact.
- [x] Record closure status and remaining risk for next session.

## Work Completed

### 1) Post-reboot Hailo runtime verification

- Verified package alignment and kernel integration:
  - `hailort` = `4.23.0`
  - `hailort-pcie-driver` = `4.23.0`
  - `hailo_pci/4.23.0` DKMS present for current kernel and module loaded.
- Re-validated pyHailoRT basic infer in host venv (`HEF -> VDevice -> InferVStreams`) with successful execution.

### 2) Direct backend implementation (single-process node)

- Added in-process direct engine (`HailoDirectInferenceEngine`) in:
  - `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py`
- Engine behavior implemented:
  - persistent VDevice/network setup
  - network activation lifecycle management
  - HEF reload support
  - NMS-by-class output decode into existing detection contract
- Backend routing updated so direct runtime is selectable and active by default in node parameters.

### 3) Launcher plumbing fix (critical)

- Found and fixed launch-layer mismatch: launcher still forced `inference_backend:=hailo_gst`.
- Updated `tools/start_live_stack.sh` to:
  - default single-process backend to `hailo_direct`
  - add explicit CLI override `--perception-inference-backend <name>`
  - pass backend value through to perception node launch args
  - include backend in startup summary output
- Verified by launching single-process stack both with explicit direct backend and with default path; both report `backend=hailo_direct`.

### 4) Fresh live direct-backend validation

- Captured 120s artifact:
  - `reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_direct_r1.json`
- Validation results:
  - canonical validation: PASS
  - invariants: mostly pass; recurring `B.pub_dt_vs_det_out_fps_consistent` failures observed (jitter-related)
- Observed timing profile (direct run):
  - `/timing` hz: `28.989`
  - `container_queue_ms p95`: `0.951`
  - `infer_ms p95`: `2.302`
  - `e2e_det_ms p95`: `8.586`
  - `pub_dt_ms p95`: `36.298`

## Comparison Notes

- Versus `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r2`, direct run showed much lower queue and end-to-end latency.
- However, direct run had `detections_per_msg.mean = 0.0` and `zero_ratio = 1.0` (no detections during sample), so workload comparability is not yet satisfied for final parity closure.

## Deliverables Produced

- [x] Direct runtime engine integrated in perception node.
- [x] Live launcher updated to use/directly control backend selection.
- [x] Fresh direct-backend 120s timing artifact captured and validated.
- [x] Day-19 closure log recorded with quantitative evidence.

## End of Day Review

Completed:

- Closed runtime compatibility blocker and proved direct pyHailoRT path works post-reboot.
- Cut over live single-process startup to direct backend by default.
- Captured strong direct-run latency evidence under live stack.

Open next step:

- Run one more controlled direct capture with in-frame detection workload and verify detection-load comparability gates (`detections_per_msg.mean`, `zero_ratio`) before declaring final parity closure.
