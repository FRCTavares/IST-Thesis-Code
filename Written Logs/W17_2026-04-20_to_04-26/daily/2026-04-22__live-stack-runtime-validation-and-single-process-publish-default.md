# Daily Log - 2026-04-22 (Day 22) - Live Stack Runtime Validation and Single-Process Publish Default

## Overview

Focus: inspect the current uncommitted worktree, validate the live stack end to end after `thesis_target_selector` removal, identify the real source of the live throughput ceiling, and apply the smallest startup-default change that improves single-process runtime throughput without changing capture resolution.

## Goals for Today

- [x] Inspect the current uncommitted git worktree before writing logs.
- [x] Verify target selection is now strictly dashboard/API-driven.
- [x] Verify control stays safe before explicit target selection.
- [x] Identify the most likely reason live runtime was capped near `~9 Hz`.
- [x] Confirm or falsify the publish-size bottleneck hypothesis using live runtime changes only.
- [x] Apply the minimal one-file launcher patch if runtime evidence is strong enough.
- [x] Re-validate that the new default is active after reboot/startup recovery.

## Uncommitted Worktree Snapshot

`git status --short` showed the current worktree includes:

- documentation updates:
  - `README.md`
  - `REPO_DEEP_DIVE.md`
  - `RUNBOOK.md`
- runtime/startup and node changes:
  - `tools/start_live_stack.sh`
  - `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py`
  - `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py`
  - `ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py`
  - several launch files under `ros2_ws/src/thesis_bringup/launch/`
- target-selector removal:
  - full deletion of `ros2_ws/src/thesis_target_selector/...`
  - deletion of `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_resize_node.py`
- additional untracked/new artefacts:
  - `ros2_ws/src/thesis_bringup/config/mavros_pixhawk.yaml`
  - `tools/test_mavros_eth.sh`
  - `log/latest_list`

`git diff --stat` summary at time of logging:

- `27 files changed`
- `427 insertions`
- `796 deletions`

The dominant pending structural change in the worktree is the removal of `thesis_target_selector` and the migration of target selection responsibility to `dashboard_bridge_node`.

## Work Completed

### 1) End-to-end live runtime verification after target-selector removal

Confirmed live stack startup in `single-process` mode and verified the expected runtime topics are present:

- `/camera/image_raw`
- `/detections`
- `/tracks`
- `/target`
- `/timing`
- `/timing_tracker`
- `/timing_target`

Confirmed real runtime payloads rather than empty process startup:

- `/detections` published real `person` detections.
- `/tracks` published live tracked IDs.

### 2) Target API path validation

Validated the new target-selection contract driven by `dashboard_bridge_node`:

- Before clearing, `/target` was already active with a selected track (`id=31`), so the runtime was not in idle baseline.
- Cleared target via:
  - `POST /api/target` with `{"target": null}`
- Confirmed `/target` returned to the empty state:
  - `id=0`
  - zero geometry
  - zero score/quality
- Selected a live tracked person via:
  - `POST /api/target` with `{"target": 31}`
- Confirmed `/target` updated correctly to:
  - `id=31`
  - non-zero bbox
  - `quality=1.0`
- Cleared again and re-confirmed empty target state.

Conclusion:

- The target API path is working correctly.
- `thesis_target_selector` removal is not the current blocker.

### 3) Control safety validation

Validated control behavior before and after explicit target selection:

- After clearing target:
  - `/control_ref/cmd_vel` published all-zero safe output
- After selecting track `31`:
  - `/control_ref/cmd_vel` became active with non-zero command output
- After clearing again:
  - control returned to zero command output

Conclusion:

- Control is behaving safely before selection.
- Control activation is correctly gated by explicit target selection.

### 4) Initial bottleneck diagnosis from live evidence

Initial live measurements with default single-process startup at full publish size:

- `/camera/image_raw`: about `8.9 Hz`
- `/detections`: about `12.3 Hz`
- `/tracks`: about `12.0 Hz`
- `/timing`: about `11.6 Hz`
- `/camera/capture_fps`: about `46.1`
- `/camera/fps`: about `30.0`

Representative `/timing` sample before publish-size change:

- `image_width: 1280`
- `image_height: 720`
- `pre_ms: 2.58`
- `infer_ms: 6.87`
- `post_ms: 0.08`
- `det_pub_ms: 0.51`
- `e2e_det_ms: 10.92`
- `pub_dt_ms: 125.03`

Interpretation:

- Camera capture itself was not slow (`capture_fps` far above effective observed topic rate).
- Camera node self-reported publish remained near `30 Hz`.
- Hailo inference remained fast (`infer_ms` around `7 ms`).
- Effective live cadence was collapsing before or at ROS image transport/delivery of `/camera/image_raw`.

### 5) Runtime-only confirmation of the publish-size bottleneck hypothesis

Hypothesis tested:

- The main bottleneck is full-size `/camera/image_raw` publication (`1280x720 bgr8`) while single-process perception only needs `640x640`.

Runtime-only experiment:

- Changed camera publish dimensions at runtime, without editing code:
  - `publish_width = 640`
  - `publish_height = 640`

Observed rates after the runtime parameter change:

- `/camera/image_raw`: about `17.9 Hz`
- `/detections`: about `18.7 Hz`
- `/tracks`: about `14.8 Hz`
- `/timing`: about `18.7 Hz`

Representative `/timing` sample after runtime change:

- `image_width: 640`
- `image_height: 640`
- `pre_ms: 0.49`
- `infer_ms: 10.44`
- `post_ms: 0.07`
- `det_pub_ms: 0.42`
- `e2e_det_ms: 13.65`
- `pub_dt_ms: 39.47`

Interpretation:

- `/camera/image_raw` roughly doubled vs the `1280x720` publish-default case.
- `/timing.pub_dt_ms` dropped from roughly `125 ms` to roughly `39 ms`.
- Inference remained in the same general millisecond range; compute did not explain the earlier ceiling.
- This strongly confirmed the main bottleneck was the full-resolution ROS image publication/transport path, not raw capture and not Hailo infer compute.

### 6) Dashboard-off A/B check

To rule out dashboard/web-video overhead as the dominant explanation, a dashboard-off A/B run was checked separately with full publish size still active:

- `/camera/image_raw`: about `7.4 Hz`
- `/detections`: about `11.7 Hz`
- `/tracks`: about `12.7 Hz`
- `/timing`: about `10.9 Hz`
- `/camera/capture_fps`: about `56.0`
- `/camera/fps`: about `30.3`

Representative `/timing` sample in that A/B run:

- `image_width: 1280`
- `image_height: 720`
- `infer_ms: 5.98`
- `pub_dt_ms: 67.30`

Interpretation:

- Disabling dashboard/web-video did not produce the large gain seen from reducing publish size to `640x640`.
- Dashboard/video overhead is therefore not the main bottleneck.
- The main limiter remained full-size `/camera/image_raw` publication.

### 7) Minimal one-file patch applied

Applied the narrowest launcher change in:

- `tools/start_live_stack.sh`

Behavior change:

- only when `PERCEPTION_MODE=single-process`
- only when `CAMERA_PUBLISH_SHAPE_EXPLICIT == 0`
- default:
  - `CAMERA_PUBLISH_WIDTH=640`
  - `CAMERA_PUBLISH_HEIGHT=640`

Preserved:

- capture resolution defaults (`CAMERA_WIDTH`, `CAMERA_HEIGHT`)
- legacy mode behavior
- user-provided explicit publish dimensions
- publish resize mode (`letterbox`) unless overridden elsewhere

### 8) Startup freeze during verification and recovery

During the first restart after the patch, startup froze in preflight:

- blocked on `v4l2-ctl --stream-mmap ... --stream-count=10 --stream-to=/dev/null --stream-poll`
- process observed in `D` state

Interpretation:

- transient kernel/driver camera-probe wedge
- not attributable to the publish-size patch, because the hang occurred during camera preflight before ROS node startup

Recovery:

- host reboot
- restart after reboot succeeded

### 9) Post-reboot validation of the new default

After reboot and successful startup:

- `ros2 param get /camera_capture_node publish_width` -> `640`
- `ros2 param get /camera_capture_node publish_height` -> `640`

Observed live rates after clean restart with patched default:

- `/camera/image_raw`: about `14.5 Hz`
- `/detections`: about `20.2 Hz`
- `/tracks`: about `20.3 Hz`
- `/timing`: about `17.5 Hz`

Representative post-reboot `/timing` sample:

- `image_width: 640`
- `image_height: 640`
- `infer_ms: 7.09`
- `pub_dt_ms: 37.91`
- `e2e_det_ms: 22.53`

Conclusion:

- the new default is active
- the improved throughput is now the startup default for single-process mode
- the fix is minimal, local, and evidence-backed

## Deliverables Produced

- [x] Full live validation of target API path after `thesis_target_selector` removal.
- [x] Full live validation of safe control gating before/after target selection.
- [x] Runtime proof that full-size `/camera/image_raw` publish dimensions were the dominant throughput bottleneck.
- [x] Dashboard-off A/B check ruling out dashboard/video as the main factor.
- [x] Minimal one-file patch in `tools/start_live_stack.sh`.
- [x] Post-reboot validation that the new `640x640` single-process publish default is active.

## End of Day Review

Completed:

- Confirmed that the major pending architectural shift in the worktree is real and functioning: target selection now lives in `dashboard_bridge_node`, not `thesis_target_selector`.
- Identified the real source of the live throughput ceiling using runtime evidence rather than assumption.
- Verified that shrinking the single-process published image stream to `640x640` gives a large practical throughput improvement while preserving high-resolution capture.
- Applied and validated the smallest startup-default fix consistent with the live evidence.

Open next step:

- Record the change cleanly in operational docs (`README`, `RUNBOOK`, recovery notes) only if needed after the worktree stabilizes.
- If camera preflight `v4l2-ctl` wedges recur, isolate that as a separate robustness issue; it is adjacent to, but distinct from, today’s throughput fix.
