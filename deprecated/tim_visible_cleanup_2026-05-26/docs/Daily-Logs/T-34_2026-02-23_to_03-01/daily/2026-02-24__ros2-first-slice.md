# Daily Log — 2026-02-24 — First ROS 2 Slice (Week 2, Day 1)

## Goal
- Wire the existing standalone pipeline into a minimal ROS 2 node graph without changing the Docker service boundary.
- Create `thesis_msgs` package (Track2D, Track2DArray, TargetState, Timing) — done first to unblock everything else.
- Implement `inference_client_node`: ZMQ SUB → `vision_msgs/Detection2DArray` + `thesis_msgs/Timing`.
- Implement `tracker_node`: wrap existing SORT code → `thesis_msgs/Track2DArray`.
- Implement `target_selector_node`: highest-confidence confirmed track → `thesis_msgs/TargetState`.
- Bring up all three with a single launch file and validate with `ros2 topic hz` + `rosbag2`.

**Done today:** ROS 2 workspace scaffold created and `thesis_msgs` built successfully. `inference_client_node` ran and received detections when the container was healthy. The main effort shifted to restoring a deterministic, version-aligned Hailo container and inference service after a cascade of dependency and version mismatches. End of day: inference service fully stable again on HailoRT 4.20, tappas-core 3.31, correct postprocess library path, ROI extraction working and ZMQ publishing. Full ROS node graph (tracker + selector + launch + bag) deferred to 02-25.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| ROS 2 workspace | `~/ros2_ws/src` |
| New packages | `thesis_msgs`, `thesis_inference_client`, `thesis_tracker`, `thesis_target_selector`, `thesis_bringup` |
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
├── thesis_msgs/               # custom interfaces — build first
├── thesis_inference_client/   # ZMQ → Detection2DArray + Timing
├── thesis_tracker/            # SORT → Track2DArray
├── thesis_target_selector/    # latest-state → TargetState
└── thesis_bringup/            # launch file + params
```

---

## Work Done

### A) `thesis_msgs` package
- [x] Created ROS 2 interface package and added correct `rosidl` dependencies.
- [x] Hit initial build error: package missing `<member_of_group>rosidl_interface_packages</member_of_group>`.
- [x] Fixed `package.xml`, cleaned `build/thesis_msgs` `install/thesis_msgs` `log`, rebuilt successfully.
- [x] Verified with `ros2 interface show thesis_msgs/msg/Timing`.

Notes:
- `colcon` warnings from stale `AMENT_PREFIX_PATH` were resolved by deleting `build/thesis_msgs` `install/thesis_msgs` `log` and rebuilding.

### B) `inference_client_node`
- [x] Node ran and successfully received detections when inference service was active.
- [x] Confirmed `vision_msgs` already installed (`ros-jazzy-vision-msgs` present).
- [ ] **Ctrl-C shutdown bug remains:** double shutdown triggers `rcl_shutdown already called` error — fix deferred to 02-25.

Notes:
- Earlier timeouts were simply because the container inference service was not running, not a ZMQ bug.
- Printed runtime confirmed: stable cadence (prints every 60 frames) and normal `lat`/`pub_dt` when service ran.

### C) `tracker_node`
- [ ] Not implemented today. Blocked by time lost to recovering inference service stability.

### D) `target_selector_node`
- [ ] Not implemented today. Same reason as tracker node.

### E) `thesis_bringup` launch
- [ ] Not implemented today. Deferred until nodes exist.

### F) Validation
- [x] Partial: validated ZMQ → ROS node input path works when service is healthy.
- [ ] Full ROS graph `hz` + bag recording deferred to 02-25.

---

## Major Blockers / Issues and Fixes (the real work today)

### 1) Container / host environment drift broke previously working pipeline

**Symptom:**
- Container start, plugin load, or pipeline run would fail after rebuilds and package changes, often with misleading downstream errors (`hailonet missing`, `not-negotiated`, `cannot detect arch`, etc.)

**Fix:**
- Stop relying on ad-hoc runtime installs and revert to a deterministic image build (Dockerfile + stable entrypoint).
- Align host driver, container HailoRT, tappas-core, firmware, and HEF expectations.

---

### 2) Hailo stack version mismatch spiral (driver, HailoRT, firmware, plugin ABI)

We observed multiple failure modes caused by version skew:

- **Plugin dependency mismatch** — `libgsthailo.so` looking for `libhailort.so.4.17.0` while container had `4.20` or vice versa.
- **Architecture autodetect failure** — `Could not auto-detect Hailo architecture. Please specify --arch manually.` triggered when Hailo userland could not talk to device correctly.
- **Driver info query failures** — `Failed to query driver info, errno 25` and `HAILO_DRIVER_FAIL(36)` when host driver and container runtime were mismatched.
- **Firmware mismatch** — `Unsupported firmware operation. Host: 4.17.0, Device: 4.20.0`
- **HEF parse failure** — `HEF file length does not match` and `HAILO_INVALID_HEF(26)` when HEF compiled target did not match runtime/firmware expectations.

**Fix:**
- Installed DKMS properly and standardised on `4.20` end-to-end.
- Installed DKMS and used `make install_dkms` on `hailort-drivers` tags.
- Verified with `modinfo hailo_pci` that host driver is `4.20.0`.
- Rebuilt container to include `hailort 4.20.0-1` and `hailo-tappas-core 3.31.0+1-1` at build time.
- Removed runtime pinning logic from entrypoint that kept downgrading packages.

---

### 3) DKMS missing on host blocked driver control

**Symptom:**
- `make install_dkms` requires `dkms` to be installed.

**Fix:**
- Installed `dkms` on host (`sudo apt install dkms`) and re-ran `make install_dkms`.
- Confirmed DKMS module path: `/lib/modules/.../updates/dkms/hailo_pci.ko.zst`.

---

### 4) Entrypoint runtime package pinning killed the container

**Symptom:**
- Container exited immediately with:
  ```
  [entrypoint] Installing hailort=4.17.0...
  apt refuses downgrade without --allow-downgrades
  container exit code 100
  ```

**Fix:**
- Replaced `entrypoint.sh` with minimal "exec only" entrypoint (no runtime apt installs).
- Moved all dependency installs into `Dockerfile`.

---

### 5) Missing models and resources inside the container (HEF paths)

**Symptom:**
- Default resources expected under `/usr/local/hailo/resources/...` but were not present after image changes.
- `hef-path=None` or missing files caused GStreamer negotiation failures.

**Fix:**
- Adopted explicit HEF management:
  - Downloaded YOLOv6n HEF into `/root/thesis_service/resources/hefs/yolov6n_hailo8.hef`.
  - Pointed `hef-path` explicitly to that file.

---

### 6) Postprocess library path changed with tappas-core 3.31

**Symptom:**
- Pipeline failed with:
  ```
  Could not load lib .../usr/lib/aarch64-linux-gnu/post_processes/libyolo_hailortpp_post.so: No such file
  ```
- After installing tappas-core 3.31, postprocess libs moved location.

**Fix:**
- Discovered correct location:
  ```
  /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so
  ```
- Confirmed symbol exists (`nm -D` shows `filter` exported).
- Updated pipeline to use correct `so-path` with `function-name=filter`.

---

### 7) Video decoding and negotiation issues

**Symptom:**
- `streaming stopped, reason not-negotiated (-4)` when using certain MP4 encodes.
- Source video had high profile 4:2:2 10-bit characteristics.

**Fix:**
- Created a safe baseline clip — re-encoded to `yuv420p`, baseline H.264 profile:
  ```
  example_640_x10_safe.mp4
  ```
- Pipeline now runs with stable decode and caps negotiation.

---

## Results

### End-of-day stable system state
- **Host driver:** `hailo_pci 4.20.0` (DKMS)
- **Container:**
  - `hailort 4.20.0-1`
  - `hailo-tappas-core 3.31.0+1-1`
  - `hailonet` OK
  - correct postprocess `.so` path
- **Inference publisher:**
  - pipeline starts
  - `[roi]` extraction OK, first frame with dets: `frame_id=1, n=12`
  - ZMQ publishing restored and verified

### Rates / Timing
- Not re-measured at end of day (focus was stack recovery).
- Earlier in the day, `inference_client_node` showed steady `pub_dt_ms ~33 ms` when service ran.

---

## Next Actions (carry to 02-25)

**Must-do (to complete the "First ROS 2 Slice"):**
- [ ] Fix `inference_client_node` Ctrl-C shutdown bug (avoid double `rclpy.shutdown()`).
- [ ] Implement `tracker_node` (copy `sort_tracker.py`, subscribe `/detections`, publish `/tracks`).
- [ ] Implement `target_selector_node` (subscribe `/tracks`, publish `/target`).
- [ ] Add `thesis_bringup` launch file for the three nodes.
- [ ] Validate with:
  - `ros2 topic hz /detections /tracks /target`
  - `ros2 bag record /detections /tracks /target /timing`

**Clean-up / harden:**
- [ ] Keep `Dockerfile` pinned to meta packages (`hailo-tappas-core`, `hailort`) and avoid entrypoint installs.
- [ ] Document final postprocess path for tappas 3.31 and HEF path assumptions.

---

## Key Commands

```bash
# Host — build msgs
cd ~/Desktop/Thesis/ros2_ws
colcon build --packages-select thesis_msgs
source install/setup.bash
ros2 interface show thesis_msgs/msg/Timing

# Container — stable stack verification
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
hailortcli --version
dpkg -l | grep -E "hailort|hailo-tappas-core"
gst-inspect-1.0 hailonet >/dev/null 2>&1 && echo "hailonet OK"
'

# Container — run publisher
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
cd /root/thesis_service
./run_detection_zmq.sh
'

# Host — inference client node (when service is running)
cd ~/Desktop/Thesis/ros2_ws
source install/setup.bash
ros2 run thesis_inference_client inference_client_node --ros-args \
  -p addr:=tcp://127.0.0.1:5555 -p topic:=dets -p img_w:=640 -p img_h:=640 -p min_score:=0.35 -p conflate:=true
```

---

## Golden State Checklist

Run these after any container rebuild or host reboot to confirm the stack is sane before touching ROS 2.

```bash
# 1. Host driver
modinfo hailo_pci | grep "^version"
# expected: version: 4.20.0

# 2. Container runtime versions
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 hailortcli --version
# expected: 4.20.0

docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 dpkg -l | grep -E "hailort|hailo-tappas-core"
# expected: hailort 4.20.0-1, hailo-tappas-core 3.31.0+1-1

# 3. GStreamer plugin
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  gst-inspect-1.0 hailonet >/dev/null 2>&1 && echo "hailonet OK" || echo "hailonet MISSING"
# expected: hailonet OK

# 4. Postprocess SO (tappas 3.31 path)
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so
# expected: file present (no error)

# 5. HEF present
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /root/thesis_service/resources/hefs/yolov6n_hailo8.hef
# expected: file present

# 6. Safe test clip present
docker exec pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 \
  ls /root/thesis_service/example_640_x10_safe.mp4
# expected: file present
```

**All six checks must pass before running the inference service or ROS 2 graph.**

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
