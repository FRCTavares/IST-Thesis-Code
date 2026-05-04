# Daily Log — 2026-02-25 — First ROS 2 Slice Complete (Week 2, Day 2)

## Goal
- Fix `inference_client_node` Ctrl-C shutdown bug (avoid double `rclpy.shutdown()`).
- Implement `tracker_node`: wrap existing `sort_tracker.py` → subscribe `/detections`, publish `/tracks`.
- Implement `target_selector_node`: subscribe `/tracks`, publish `/target` (`thesis_msgs/TargetState`).
- Add `thesis_bringup` launch file for all three nodes.
- Validate full graph with `ros2 topic hz /detections /tracks /target` and `ros2 bag record` (recorded ~110 s per run due to server EOS).
- Harden: pin `Dockerfile` to meta packages; document final postprocess path + HEF assumptions.

**Done today:** Completed the full "First ROS 2 Slice" end-to-end: `inference_client_node` → `tracker_node` → `target_selector_node` launched via `thesis_bringup`. Fixed Ctrl-C shutdown bug. Implemented `tracker_node` wrapping existing `sort_tracker.py` API with correct message mapping. Implemented `target_selector_node` with sticky-ID, best-score, area tie-break policy. Validated live ~30 Hz rates on all topics and recorded two clean MCAP bags (~110 s each, ~3 290 messages per topic).

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| ROS 2 workspace | `~/Desktop/Thesis/ros2_ws/src` |
| Packages in progress | `thesis_inference_client`, `thesis_tracker`, `thesis_target_selector`, `thesis_bringup` |
| Package already built | `thesis_msgs` ✓ |
| Container | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` — client connects to `127.0.0.1:5555` |
| Test input | `example_640_x10_safe.mp4` (re-encoded baseline video) |
| ZMQ topic | `b"dets"` |
| Payload | `seq`, `frame_id`, `pts_ns`, `t_pub`, `dets[]` (normalised xywh) |
| Tracker | SORT — params frozen (`iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35`) |
| ZMQ backlog policy | `CONFLATE=1` on SUB socket, `recv_multipart()` throughout |
| ROS backlog policy | Subscriber QoS keep-last depth=1 (all nodes) |

---

## Workspace Structure

```
ros2_ws/src/
├── thesis_msgs/               # ✓ built — interfaces only
├── thesis_inference_client/   # ZMQ → Detection2DArray + Timing
├── thesis_tracker/            # SORT → Track2DArray
├── thesis_target_selector/    # latest-state → TargetState
└── thesis_bringup/            # launch file + params
```

---

## Work Done

### A) `inference_client_node` — Ctrl-C fix
- [x] Identified root cause: `shutdown()` called twice during teardown path.
- [x] Applied fix: guard shutdown with `rclpy.ok()` in a clean `finally` block; node destroy called once.
- [x] Verified: `Ctrl-C` ends `ros2 launch` cleanly — no `rcl_shutdown already called` error.

Notes:
- Expected behaviour after server EOS: node stays alive, logs `recv timeout, no messages` periodically — correct.

### B) `tracker_node`
- [x] Created `thesis_tracker` package.
- [x] Wrapped existing `sort_tracker.py` — zero algorithm changes.
- [x] Confirmed SORT API (differs from common Nx5 SORT): `Sort.update(dets: List[BBox], frame_id=None) -> List[SortTrack]`; confirmed tracks = hits ≥ `min_hits` and `time_since_update == 0`.
- [x] Subscribed `/detections` (`vision_msgs/Detection2DArray`) QoS keep-last depth=1.
- [x] Published `/tracks` (`thesis_msgs/Track2DArray`); `out.header` copied from detections header (not `now()`).
- [x] Fixed message mapping: `Track2D` has no `header` field — header lives on `Track2DArray` only.
- [x] Score and label propagation: best-IoU match to current detections per track (post-processing only, tracker unchanged).
- [x] Params declared: `iou_threshold`, `max_age`, `min_hits`, `min_score`.

Notes:
- Initial crash fixed: `AttributeError: 'Track2D' object has no attribute 'header'`.

### C) `target_selector_node`
- [x] Created `thesis_target_selector` package.
- [x] Subscribed `/tracks` QoS keep-last depth=1.
- [x] Policy implemented: sticky previous ID if still present → else highest score → tie-break by bbox area.
- [x] Note: no `confirmed` field in `Track2D` — confirmation is handled inside the tracker before publishing; selector works directly on published tracks.
- [x] Published `/target` (`thesis_msgs/TargetState`) every callback.
- [x] Fixed message mapping: `TargetState` has no `header` field; `id` is `uint32` so "no target" uses `id=0`; `quality=1.0` when selected, `0.0` when empty.
- [x] `TargetState` has no `header`, so target messages are evaluated by publish cadence and content, and aligned via the upstream track callback.

Notes:
- Initial crash fixed: `OverflowError: can't convert negative value to unsigned int`.

### D) `thesis_bringup` launch
- [x] Created `thesis_bringup` package.
- [x] Launch file: `first_ros2_slice.launch.py` starts `inference_client_node`, `tracker_node`, `target_selector_node`.
- [x] Parameters set in launch: inference (`addr=tcp://127.0.0.1:5555`, `topic=dets`, `640×640`, `min_score=0.35`, `conflate=True`); tracker (`iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35`).
- [x] Verified: `ros2 node list` shows all three nodes.

Notes:
- Launch file name is `first_ros2_slice.launch.py` — not `pipeline.launch.py`.

### E) Full build
- [x] `colcon build --packages-select thesis_inference_client thesis_tracker thesis_target_selector thesis_bringup` — clean.
- [x] Sourced `install/setup.bash`; no import errors.
- [x] Verified console script names in `setup.py` match launch executable names (`tracker_node`, `target_selector_node`).

### F) Validation
- [x] `ros2 topic echo /tracks --once` — non-empty track arrays with valid `id`, bboxes, `score`, `label`.
- [x] `ros2 topic echo /target --once` — selected target with `quality=1.0`.
- [x] `ros2 topic hz /tracks` — ~30 Hz (transient `topic does not appear` at start due to discovery; stabilises to 30 Hz).
- [x] `ros2 topic hz /target` — ~30 Hz.
- [x] `ros2 topic echo /timing --once` — fields populated and sane.
- [x] `/detections` and `/timing` confirmed at ~30 Hz during active stream (evidenced by bag counts over duration).
- [x] Two MCAP bags recorded successfully (see Results below).

---

## Results

### Rates
| Topic | Rate (Hz) |
|-------|-----------|
| `/detections` | ~30 |
| `/tracks` | ~30 |
| `/target` | ~30 |

*Rates refer to the active publish window before server EOS.*

### Bag evidence

| | `2026-02-25__slice__secondary` | `2026-02-25__slice__primary` |
|-|-------------------------------|-------------------------------|
| Duration | 109.837 s | 109.836 s |
| `/detections` | 3 295 msgs | 3 296 msgs |
| `/timing` | 3 295 msgs | 3 296 msgs |
| `/tracks` | 3 293 msgs | 3 282 msgs |
| `/target` | 3 293 msgs | 3 291 msgs |
| Size | 9.5 MiB (MCAP) | 9.5 MiB (MCAP) |

### Timing fields
- `/timing` publishes continuously at ~30 Hz; fields are populated and sane.
- No percentile summary computed today — needs offline bag parsing (carry to 02-26).

### Backlog checks
- No backlog growth observed during active stream.
- After server EOS, nodes stay alive; `inference_client_node` logs timeouts; no burst catch-up (CONFLATE=1 working correctly).

---

## Blockers / Issues

- **FastDDS SHM warning during `ros2 bag record`:**
  ```
  RTPS_TRANSPORT_SHM Error Failed init_port ... open_and_lock_file failed
  ```
  Did not prevent recording — bags are valid. Optional mitigation: `export RMW_FASTRTPS_USE_SHM=0` before recording.

- **Server EOS after ~110 s:** inference service exits at clip end; sustained recording requires a looping server. Acceptable for today's validation target; consistent between runs. Post-EOS timeout warnings are expected and excluded from "active stream" performance assessment.

---

## Next Actions (carry to 02-26)

- [ ] Parse recorded MCAP bags to compute avg/p95 for `lat_ms`, `recv_ms`, `json_ms`, `track_ms`, `loop_ms`, `pub_dt_ms`.
- [ ] Reduce post-EOS log spam: throttle `recv timeout, no messages` warnings (print every N timeouts).
- [ ] (Optional) Add `stream_alive` flag to `/timing` to mark valid publish window vs post-EOS idle, for clean offline analysis.
- [ ] Document final ROS graph, topic contracts, and message-mapping decisions in repo README.

---

## Key Commands

```bash
# Golden state check (run first)
modinfo hailo_pci | grep "^version"
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 hailortcli --version
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  gst-inspect-1.0 hailonet >/dev/null 2>&1 && echo "hailonet OK" || echo "MISSING"

# Terminal A (container) — inference service (runs to EOS ~110 s)
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
cd /root/thesis_service
./run_detection_zmq.sh
'

# Terminal B — build + launch
cd ~/Desktop/Thesis/ros2_ws
colcon build --packages-select thesis_inference_client thesis_tracker thesis_target_selector thesis_bringup
source install/setup.bash
ros2 launch thesis_bringup first_ros2_slice.launch.py

# Terminal C — validation while stream is active
ros2 topic echo /tracks --once
ros2 topic echo /target --once
ros2 topic hz /detections
ros2 topic hz /tracks
ros2 topic hz /target
ros2 topic echo /timing --once

# Bag record (MCAP) — optional: suppress SHM warning
cd ~/Desktop/Thesis/artifacts/bags/raw
export RMW_FASTRTPS_USE_SHM=0
ros2 bag record --topics /detections /tracks /target /timing
```

---

## Scope Boundary (what NOT to do today)

- No ByteTrack integration
- No MAVROS / Pixhawk commands
- No camera bring-up (CSI ribbon still not connected)
- No QoS tuning beyond depth=1
- No threshold changes — SORT params are frozen

---

## Environment Snapshot

| Component | Version / Value |
|-----------|----------------|
| Kernel | `6.8.0-1047-raspi` |
| Hailo driver | `hailo_pci 4.20.0` (DKMS) |
| Hailo firmware | `hailo8_fw 4.20.0` |
| HailoRT (container) | `4.20.0-1` |
| tappas-core (container) | `3.31.0+1-1` |
| ROS 2 distro | Jazzy |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (`127.0.0.1:5555`) |
| Postprocess SO | `/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so` (`filter`) |
| HEF | `/root/thesis_service/resources/hefs/yolov6n_hailo8.hef` |
| Test clip | `example_640_x10_safe.mp4` |
