# Daily Plan - 2026-04-27 (Day 27)

## Context Carry-Over

- Prior week close:
  - Live stack was already close to operational, but model, tracker, and target-selection workflows were still not convenient from the dashboard.
  - OC-SORT was the active practical tracker baseline.
  - Timing instrumentation was available, but full model × tracker comparison had not yet been run.

- Current baseline:
  - Live stack runs in single-process perception mode.
  - HEF models are now stored cleanly under `models/hef/`.
  - Dashboard can expose all available HEF models through `/api/models`.
  - Trackers available: `sort`, `ocsort`, `bytetrack`, `deepsort`.
  - Current practical live baseline: `yolov6n + ocsort`.

- Main unresolved gap:
  - Timing feasibility is now measured, but tracking quality is still not fully evaluated.
  - Need controlled replay or annotated evaluation for ID switches, fragmentation, reacquisition, and selected-target continuity.

## Primary Objective

Recover the live perception stack after the accidental `infer_service` deletion, clean up HEF model handling, expose all detectors and trackers in the dashboard, and run a complete live timing comparison across all detector and tracker combinations.

## Today's Plan

- [x] Diagnose why the live stack reported successful startup but produced no `/detections`.
- [x] Confirm camera was alive and perception was the failing stage.
- [x] Identify missing HEF path:
  - Old expected path: `infer_service/resources/hefs/yolov6n_hailo8.hef`
  - New intended path: `models/hef/yolov6n.hef`
- [x] Patch single-process perception to use `models/hef/`.
- [x] Patch dashboard model selection to use `models/hef/`.
- [x] Add all available HEF models to the dashboard API.
- [x] Add `deepsort` to dashboard tracker selection.
- [x] Add target-selection controls to the main dashboard card, below the tracker selector.
- [x] Verify target selection from the home dashboard works.
- [x] Fix tracker node crash during runtime tracker switching:
  - `_has_track_subscribers()` now handles invalid ROS publisher/context safely.
- [x] Create and run automatic live model × tracker timing matrix.
- [x] Run full 16 model × 4 tracker matrix.
- [x] Capture summary CSV for comparison.

## Evidence Captured

### Run labels

- Live stack recovery:
  - `2026-04-27__10-54-05`
- Tracker timing restart:
  - `2026-04-27__11-45-29`
- Small matrix:
  - `reports/timing/live_matrix_20260427_115114/summary.csv`
- Full matrix:
  - `reports/timing/live_matrix_20260427_120926/summary.csv`

### Files updated

- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py`
  - Changed default HEF path to `models/hef/yolov6n.hef`.

- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py`
  - Changed single-process HEF directory to `models/hef`.
  - Added all HEF models to supported model list.
  - Added `deepsort` to supported dashboard tracker list.

- `ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py`
  - Added defensive handling around `/tracks` subscriber count checks to avoid ROS context invalid crash during switching/shutdown.

- `user-interface/src/...`
  - Added `deepsort` to tracker type and validation.
  - Added target-to-follow controls below the tracker selector.
  - Updated model/tracker dashboard controls.

- `tools/run_live_model_tracker_matrix.py`
  - Added automatic model × tracker live timing comparison runner.

### Metrics watched

- `/detections` Hz
- `/timing` Hz
- `/timing_tracker` Hz
- `e2e_det_ms` p50/p95/p99
- `infer_ms` p50/p95/p99
- `track_ms` p50/p95/p99
- `pub_dt_ms` p95
- `det_zero_ratio`
- `det_per_msg_mean`
- health score

## Results

### Stack recovery

Problem:

- The stack started successfully, but `/detections` and `/timing` had zero publishers.
- Root cause was that `perception_pipeline_node` crashed because the expected HEF file was missing.

Fix:

- Restored model availability by placing HEFs under `models/hef/`.
- Updated code so single-process perception and dashboard model switching use the cleaner `models/hef/` layout.
- Verified:
  - `/perception_pipeline_node` alive
  - `/detections` publishing
  - `/timing` publishing
  - `/tracks` publishing
  - `/target` working after selection

### Dashboard improvements

Completed:

- Added all HEF models to dashboard model API.
- Added DeepSORT to tracker selector.
- Added target selection directly on the home operations panel, below the tracker selector.
- Verified dashboard target selection by checking `/target`.

Example verified target output:

```txt
id: 1
score: 0.9625
quality: 1.0

## Full Live Timing Matrix

Completed full live timing matrix:

16 models × 4 trackers = 64 combinations  
64 / 64 completed successfully

Summary artifact:

`reports/timing/live_matrix_20260427_120926/summary.csv`

### Best Practical Live Candidates

| Rank | Model | Tracker | Det Hz | e2e p95 | Track p95 | Notes |
|---:|---|---|---:|---:|---:|---|
| 1 | yolov6n | sort | 17.34 Hz | 19.61 ms | 8.56 ms | Fastest timing baseline |
| 2 | yolov6n | ocsort | 16.53 Hz | 20.21 ms | 9.03 ms | Best practical live baseline |
| 3 | yolov6n | bytetrack | 17.78 Hz | 20.33 ms | 9.37 ms | Good timing, but low-confidence path still needs care |
| 4 | yolov8n | ocsort | 15.50 Hz | 23.24 ms | 8.45 ms | Good alternative detector |
| 5 | yolov11n | bytetrack | 17.99 Hz | 28.86 ms | 10.05 ms | Worth further visual and quality testing |

### Main Conclusion

`yolov6n + ocsort` is the best operational live baseline for now.

`yolov6n + sort` is the fastest simple reference.

`yolov11n + bytetrack` is surprisingly strong and should be checked further with visual and tracking-quality tests.

DeepSORT works, but the current MARS/TensorFlow appearance path is too heavy for live control. Its typical `track_p95_ms` is around 70 to 85 ms, so it should remain a heavy appearance-based comparator rather than the operational tracker.

## End-Of-Day Notes

### What moved

- Recovered the live stack after the HEF path failure.
- Cleaned up model storage around `models/hef/`.
- Updated the dashboard so all HEF models are visible and selectable.
- Added all tracker options to the dashboard, including `deepsort`.
- Added target selection directly to the main dashboard page, below the tracker selector.
- Ran the full model × tracker live timing matrix successfully.

### What blocked

- Runtime switching to DeepSORT initially produced API errors.
- Root cause was a ROS publisher context race in the tracker node during subscriber-count checks.
- Fixed by making `_has_track_subscribers()` defensive against invalid ROS publisher/context state.

### What starts tomorrow

- Generate a clean ranked report from `reports/timing/live_matrix_20260427_120926/summary.csv`.
- Commit the benchmark runner, tracker crash fix, UI changes, and summary CSV.
- Freeze the current live baseline: `yolov6n + ocsort`.
- Start controlled tracking-quality evaluation:
  - ID switches
  - fragmentation
  - target lock continuity
  - reacquisition time
  - selected-target stability under occlusion