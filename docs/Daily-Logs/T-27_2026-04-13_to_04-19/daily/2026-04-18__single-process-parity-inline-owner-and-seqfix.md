# Daily Log - 2026-04-18 (Day 18) - Single-Process Parity, Inline-Owner Scheduling, and Seq Fix

## Overview

Focus: explain and reduce the large latency gap between legacy and single-process perception by aligning preprocessing semantics, redesigning single-process frame ingress/ownership, and validating with repeated live timing runs.

## Goals for Today

- [x] Diagnose where the single-process path was losing latency versus legacy.
- [x] Align preprocessing logic between legacy and single-process code paths.
- [x] Replace staged queue behavior with container-like inline owner-worker behavior.
- [x] Validate with fresh timing reports and canonical metrics checks.
- [x] Improve launch and command UX for reproducible copy-paste runs.

## Work Completed

### 1) Root-cause confirmation and benchmark refresh

- Re-ran and compared legacy vs single-process timing artifacts under matched conditions.
- Confirmed the dominant delta was queue-wait before inference start (reported as `container_queue_ms`), not core inference compute (`infer_ms`).
- Added fresh comparison artifacts in `artifacts/reports/timing/fresh_cmp_20260418_135742__*.json` and post-refactor artifacts in `artifacts/reports/timing/live_post_refactor/*.json`.

### 2) Shared preprocessing parity across both paths

- Added shared preprocessing module:
  - `ros2_ws/src/thesis_inference_client/thesis_inference_client/preprocessing.py`
- Integrated shared preprocessing in:
  - `ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py`
  - `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py`
- Added dependency wiring for bringup package import access:
  - `ros2_ws/src/thesis_bringup/package.xml` now depends on `thesis_inference_client`.

### 3) Single-process backend redesign (inline owner-worker path)

- Refactored single-process ingress in `perception_pipeline_node.py`:
  - Replaced old callback/staged-flow behavior with queue + owner-worker execution.
  - Introduced `RawFrame` and explicit raw frame queueing.
  - Enforced single owner submission semantics to engine path.
  - Added fresh-frame overwrite behavior and explicit queue counters.
  - Added/used `frame_queue_size` and `num_workers` parameters.
  - Logging now states ingress mode as `inline_worker_owner`.
- Kept `async_max_inflight` effectively pinned to 1 in this ownership model.

### 4) Seq/frame-id timing fix for processed-frame parity

- Fixed sequence assignment timing in `perception_pipeline_node.py`:
  - `seq` and `frame_id` are now assigned when a frame is dequeued for processing (not on receive).
  - This avoids PTS jumps from dropped-received frames and reduces artificial queue delay risk.

### 5) Launcher and operator workflow updates

- Updated `tools/start_live_stack.sh`:
  - Added startup summary output.
  - Added resolution selector support (`--resolution`, `--list-resolutions`).
  - Removed obsolete async-latest-frame toggles from CLI.
  - Wired single-process launch args for `frame_queue_size` and `num_workers`.
  - Set single-process Hailo queue default to 6 buffers for the current path.
  - Unified camera publish defaults to capture dimensions unless explicitly overridden.
- Updated `tools/start_ui_stack.sh` output formatting for clearer runtime URLs/endpoints/log locations.

### 6) Validation and observed impact

- Built successfully after node refactors:
  - `colcon build --packages-select thesis_bringup --symlink-install`
- Mode confirmation in runtime logs showed:
  - `ingress_mode=inline_worker_owner frame_queue_size=1 prepared_queue_size=0`
- Key measured progression:
  - `single_process_r1` -> `single_process_inline_owner_r1`
    - `e2e_det_ms p95`: 229.195 -> 118.670
    - `container_queue_ms p95`: 207.830 -> 99.825
  - `single_process_inline_owner_r1` -> `single_process_inline_owner_seqfix_r1`
    - `e2e_det_ms p95`: 118.670 -> 117.158
    - `container_queue_ms p95`: 99.825 -> 97.912
    - frame-id continuity improved (no gaps in `/timing` for seqfix run).

## Validation Snapshot

- Canonical metric collection and validation tooling exercised repeatedly:
  - `tools/collect_live_timing_stats.py`
  - `tools/validate_canonical_metrics.py`
- Added operational protection file for local build tree handling:
  - `log/COLCON_IGNORE`

## Deliverables Produced

- [x] Shared preprocessing module and cross-path integration.
- [x] Single-process inline owner-worker redesign with queue observability.
- [x] Seq assignment fix tied to processed frames.
- [x] Updated launcher UX and parameter wiring for reproducible experiments.
- [x] Fresh timing artifacts proving large latency reduction from baseline single-process.

## End of Day Review

Completed:

- Closed the major architectural parity step between legacy and single-process preprocessing and scheduling semantics.
- Reduced single-process detection latency tails by about half versus pre-redesign baseline.

Open next step:

- Attack remaining queue delay gap to legacy (still concentrated in `container_queue_ms`) with targeted queue-buffer and videoconvert ablations under the same command discipline.

Outcome: single-process moved from high-latency baseline into a much lower-latency, cleaner, and reproducible inline-owner path, with one remaining queue-focused optimization cycle identified for next session.