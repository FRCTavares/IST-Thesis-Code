# Repository Summary

Updated: 2026-03-26
Scope: active repository content only (deprecated folders intentionally excluded from status accounting)

## 1. Purpose and Current Shape

This repository implements a ROS 2 Jazzy, RGB-only perception and operator dashboard stack for thesis work on target-relative micro-UAV control. The active architecture is ROS-native for runtime integration, with a planned future extraction of backend responsibilities into a standalone service.

Primary architecture references:

- [README.md](README.md)
- [RUNBOOK.md](RUNBOOK.md)
- [backend/README.md](backend/README.md)

Active runtime flow:

- Camera capture and preprocessing in ROS nodes
- Hailo inference service over ZMQ
- Tracking and target selection in ROS
- Dashboard bridge exposing WebSocket telemetry + HTTP control API
- MJPEG stream through `web_video_server`
- React dashboard consuming video, telemetry, and control endpoints

## 2. Status Rubric Used in This Summary

Working:

- Implemented in code and documented as verified in logs/runbooks.

Partially Working:

- Implemented and verified for some scenarios, but explicit documented gaps remain.

Not Yet Working:

- Planned or scaffolded but not yet implemented/validated.

Unknown:

- Evidence is incomplete, stale, or template-only.

## 3. Active Component Inventory

### ROS workspace (ros2_ws)

Packages and role:

- `thesis_bringup`: orchestration/bridge/control nodes and launch/config packaging
  - Evidence: [ros2_ws/src/thesis_bringup/setup.py](ros2_ws/src/thesis_bringup/setup.py)
- `thesis_inference_client`: ZMQ inference client node
  - Evidence: [ros2_ws/src/thesis_inference_client/setup.py](ros2_ws/src/thesis_inference_client/setup.py)
- `thesis_tracker`: multi-backend tracker node (SORT/OC-SORT/ByteTrack)
  - Evidence: [ros2_ws/src/thesis_tracker/setup.py](ros2_ws/src/thesis_tracker/setup.py), [ros2_ws/src/thesis_tracker/README.md](ros2_ws/src/thesis_tracker/README.md)
- `thesis_target_selector`: target selector node
  - Evidence: [ros2_ws/src/thesis_target_selector/setup.py](ros2_ws/src/thesis_target_selector/setup.py)
- `thesis_msgs`: message contracts including detailed timing telemetry
  - Evidence: [ros2_ws/src/thesis_msgs/msg/Timing.msg](ros2_ws/src/thesis_msgs/msg/Timing.msg)

### Inference service (infer_service)

- ZMQ Hailo detection service with ROS request/reply mode and label filtering
- Evidence: [infer_service/detection_zmq.py](infer_service/detection_zmq.py)

### Dashboard frontend (user-interface)

- React + TypeScript + Vite dashboard
- Data modes: `mock`, `offline`, `backend` (default backend)
- Evidence: [user-interface/README.md](user-interface/README.md)

### Backend folder (backend)

- Placeholder only; runtime backend responsibilities are currently in ROS bridge node
- Evidence: [backend/README.md](backend/README.md)

### Tools and operational scripts (tools)

- Single-command live startup + cleanup and operational toggles
- Timing invariant checks, live timing stats, bag analysis scripts
- Evidence: [tools/start_live_stack.sh](tools/start_live_stack.sh), [RUNBOOK.md](RUNBOOK.md)

### Thesis logs and plans (Written Logs)

- Canonical thesis objectives, control contract, and weekly/daily evidence trail
- Evidence: [Written Logs/docs/planning/thesis_plan.md](Written%20Logs/docs/planning/thesis_plan.md), [Written Logs/docs/control/control_interface.md](Written%20Logs/docs/control/control_interface.md), [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

## 4. What Is Working

### 4.1 Live stack bring-up and operations

Status: Working (High confidence)

What works:

- One-command startup for host + container components
- Process health checks and stop/cleanup flow
- Log-per-run structure and latest symlink

Evidence:

- [tools/start_live_stack.sh](tools/start_live_stack.sh)
- [RUNBOOK.md](RUNBOOK.md)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-23__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-23__.md)

### 4.2 End-to-end perception chain (camera -> inference -> tracker -> target)

Status: Working (Medium-High confidence)

What works:

- Camera capture and dashboard stream topics integrated
- ZMQ inference client path active
- Tracker outputs and target selection integrated in live graph

Evidence:

- [README.md](README.md)
- [RUNBOOK.md](RUNBOOK.md)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-23__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-23__.md)

### 4.3 Dashboard runtime integration and reliability fixes

Status: Working (High confidence)

What works:

- MJPEG QoS compatibility fix (`qos_profile=sensor_data`)
- Overlay normalization aligned with inference basis (`640x640`)
- Frontend default mode aligned to backend/live behavior

Evidence:

- [RUNBOOK.md](RUNBOOK.md)
- [README.md](README.md)
- [user-interface/README.md](user-interface/README.md)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

### 4.4 Runtime model switching API

Status: Working (High confidence)

What works:

- `POST /api/model` endpoint in live bridge
- Model-to-HEF mapping and detector restart command path
- Operator-level validation documented

Evidence:

- [ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py](ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

### 4.5 Runtime tracker switching API

Status: Working (Medium-High confidence)

What works:

- `POST /api/tracker` endpoint in bridge
- Dynamic tracker backend switch through ROS parameter service
- Tracker node handles runtime `tracker_type` updates

Evidence:

- [ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py](ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py)
- [ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py](ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-26__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-26__.md)

### 4.6 Timing instrumentation and analysis tooling

Status: Working (High confidence)

What works:

- Rich timing message contract with per-stage timestamps and derived metrics
- Live timing checks and report tooling integrated in workflow

Evidence:

- [ros2_ws/src/thesis_msgs/msg/Timing.msg](ros2_ws/src/thesis_msgs/msg/Timing.msg)
- [RUNBOOK.md](RUNBOOK.md)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

### 4.7 Ground-only perception-to-control contract

Status: Working (Ground scope only, High confidence)

What works:

- `/target` contract consumption and internal normalization
- yaw/forward sign behavior validated
- stale/invalid target safety behavior documented

Evidence:

- [Written Logs/docs/control/control_interface.md](Written%20Logs/docs/control/control_interface.md)

## 5. What Is Partially Working

### 5.1 Latency tail reduction

Status: Partially Working (High confidence)

State:

- Throughput improved close to 15 Hz in latest reported run
- Main remaining issue is cadence jitter (`pub_dt_ms` p95/p99) dominating perceived lag

Evidence:

- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

### 5.2 MAVROS hardware integration and outdoor flight readiness

Status: Partially Working (Medium confidence)

State:

- MAVROS integration code path exists and has ground-level validation documents
- Full supervised outdoor flight validation is still incomplete/deferred in logs

Evidence:

- [Written Logs/W12_2026-03-16_to_03-22/artefacts.md](Written%20Logs/W12_2026-03-16_to_03-22/artefacts.md)
- [Written Logs/docs/control/control_interface.md](Written%20Logs/docs/control/control_interface.md)

### 5.3 Dashboard control UX validation under sustained switch load

Status: Partially Working (Medium confidence)

State:

- Runtime controls implemented and built successfully
- Next-day plan indicates additional load validation still pending

Evidence:

- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-26__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-26__.md)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-27__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-27__.md)

### 5.4 Control API documentation sync

Status: Partially Working (High confidence)

State:

- Runtime API includes `POST /api/tracker` in the bridge node.
- Main docs still emphasize `POST /api/model` and `POST /api/replay`, so documented control contract is not fully synchronized with implemented behavior.

Evidence:

- [ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py](ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py)
- [RUNBOOK.md](RUNBOOK.md)
- [README.md](README.md)
- [user-interface/README.md](user-interface/README.md)
- [backend/README.md](backend/README.md)

## 6. What Is Not Yet Working (or Not Yet Implemented)

### 6.1 Standalone backend extraction

Status: Not Yet Working (High confidence)

State:

- `backend/` is intentionally a placeholder
- Live backend behavior remains in ROS bridge node

Evidence:

- [backend/README.md](backend/README.md)

### 6.2 Thesis Deliverable 1 full learned appearance embedding path

Status: Not Yet Working (Medium confidence)

State:

- Plan defines learned embedding deliverable and reports placeholder history
- No current repository evidence in active runtime docs that this is completed end-to-end

Evidence:

- [Written Logs/docs/planning/thesis_plan.md](Written%20Logs/docs/planning/thesis_plan.md)
- [Written Logs/W09_2026-02-23_to_03-01/weekly.md](Written%20Logs/W09_2026-02-23_to_03-01/weekly.md)

### 6.3 Thesis Deliverable 2 selective tiny-person refine

Status: Not Yet Working (Medium confidence)

State:

- Explicitly planned in thesis plan
- No active completion evidence in current operational logs

Evidence:

- [Written Logs/docs/planning/thesis_plan.md](Written%20Logs/docs/planning/thesis_plan.md)

### 6.4 Mature automated test coverage (beyond lint checks)

Status: Not Yet Working (High confidence)

State:

- ROS package test folders are mainly linter templates (`flake8`, `pep257`, copyright)
- No broad unit/integration test evidence for live behavior guarantees

Evidence:

- [ros2_ws/src/thesis_bringup/test/test_flake8.py](ros2_ws/src/thesis_bringup/test/test_flake8.py)
- [ros2_ws/src/thesis_bringup/test/test_pep257.py](ros2_ws/src/thesis_bringup/test/test_pep257.py)
- [ros2_ws/src/thesis_target_selector/test/test_flake8.py](ros2_ws/src/thesis_target_selector/test/test_flake8.py)

### 6.5 Replay control endpoint in live mode

Status: Not Yet Working (High confidence)

State:

- The endpoint exists but currently returns a not-implemented response in live mode.
- Replay control remains a placeholder path and is not an active runtime capability.

Evidence:

- [ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py](ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py)
- [RUNBOOK.md](RUNBOOK.md)

## 7. Unknowns and Evidence Gaps

### 7.1 Week-level closure quality varies by file

Status: Unknown (High confidence in gap)

State:

- W13 weekly planning is now populated, but W13 index/artefacts closure files remain incomplete
- Some W12 artefacts and weekly files still contain template placeholders (`TBD`, `In progress`, option blocks)

Evidence:

- [Written Logs/W13_2026-03-23_to_03-29 /weekly.md](Written%20Logs/W13_2026-03-23_to_03-29%20/weekly.md)
- [Written Logs/W13_2026-03-23_to_03-29 /artefacts.md](Written%20Logs/W13_2026-03-23_to_03-29%20/artefacts.md)
- [Written Logs/W13_2026-03-23_to_03-29 /index.md](Written%20Logs/W13_2026-03-23_to_03-29%20/index.md)
- [Written Logs/W12_2026-03-16_to_03-22/artefacts.md](Written%20Logs/W12_2026-03-16_to_03-22/artefacts.md)

### 7.2 Current-day completion for 2026-03-27 is planned, not executed

Status: Unknown (High confidence in gap)

State:

- Day 27 file is explicitly a plan with unchecked tasks and TBD outcome

Evidence:

- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-27__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-27__.md)

## 8. Validation Infrastructure Snapshot

Strong points:

- Reproducible startup workflow and runbook commands
- Rich telemetry and timing instrumentation
- Frequent daily operational logging

Weak points:

- Limited automated functional tests
- Several planning/artefact files still template-like rather than finalized evidence records

Primary references:

- [RUNBOOK.md](RUNBOOK.md)
- [tools/start_live_stack.sh](tools/start_live_stack.sh)
- [Written Logs/W13_2026-03-23_to_03-29 /daily/2026-03-25__.md](Written%20Logs/W13_2026-03-23_to_03-29%20/daily/2026-03-25__.md)

## 9. Bottom-Line Assessment

The repository is operationally mature for ground-based live perception, dashboard monitoring, and runtime model/tracker control, with strong instrumentation and improved reproducibility.

The main remaining technical and thesis-deliverable gaps are:

- cadence jitter tail reduction (`pub_dt_ms` p95/p99),
- complete outdoor/MAVROS flight-readiness validation,
- completion evidence for planned novelty deliverables (learned appearance embedding and selective tiny-person refine),
- deeper automated test coverage.

## 10. Suggested Next Validation Priorities

1. Close Day-27 planned runtime switch stress validation and publish finalized W13 weekly/artefacts closure.
2. Run fixed-window A/B cadence experiments focused on `pub_dt_ms` tail reduction while preserving detector stability.
3. Finalize a flight-readiness gate document that converts current ground validation into explicit GO/NO-GO criteria.
4. Decide scope realism for Deliverable 1 and Deliverable 2 and log explicit implementation status in a canonical weekly closure file.
