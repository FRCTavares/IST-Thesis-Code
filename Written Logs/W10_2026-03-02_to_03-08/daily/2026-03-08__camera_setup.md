# Daily Log — 2026-03-08 — Live TEVS Camera Bring-Up and End-to-End ROS Inference

## Goal

Bring the TEVS-AR0234 camera into the ROS 2 pipeline as a real sensor, then replace the old file-based inference input with live ROS camera frames sent to the container over ZMQ.

**Target outcome:**
- `camera_init_node` configures the TEVS media graph reliably after boot
- `camera_capture_node` reads `/dev/video0` and publishes `/camera/image_raw` with ROS timestamps
- Container no longer depends on direct camera access for live inference
- `inference_client_node` consumes `/camera/image_raw`, sends frames to the container, and republishes live detections
- End-to-end live path works: camera → ROS → container → `/detections` → tracker → target selector
- Achieve at least the thesis minimum of **15 Hz** on live detections

This was the day the camera stopped being a side test and became part of the real perception stack.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 + F9P GNSS + TEVS-AR0234 |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy |
| Container | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Camera device | `/dev/video0` |
| Media device | `/dev/media0` |
| Sensor subdevice | `/dev/v4l-subdev2` |
| Sensor entity | `tevs 11-0048` |
| CSI entity | `csi2` |
| Working video link | `csi2:4 -> rp1-cfe-csi2_ch0:0` |
| Inference transport | ZMQ REQ/REP on `127.0.0.1:5556` |
| Old inference mode | file-based MP4 input |
| New live mode | ROS image input to container |
| HEF | `/root/thesis_service/resources/hefs/yolov6n_hailo8.hef` |
| Postprocess SO | `/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so` |
| Postprocess function | `filter` |
| Thesis FPS target | ≥15 Hz |
| Latency budget | p95 ≤ 200 ms |

---

## Work Plan

### A) Fix TEVS bring-up so ROS can own the camera

Turn the camera from an unreliable manual setup into a repeatable ROS bring-up step.

- ✅ Confirm correct media topology on `/dev/media0`
- ✅ Identify correct entities and working link
- ✅ Implement `camera_init_node.py`
- ✅ Remove fragile operations that blocked on this driver path
- ✅ Freeze the actual working media graph configuration
- ✅ Validate that the node publishes `/camera/status`

**Deliverables:**
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_init_node.py`

**Important finding:**  
The initial approach was wrong in a few key places. The camera did not become stable until the exact media entities and link were set correctly.

**Working recipe frozen today:**
- Sensor entity: `tevs 11-0048`
- CSI entity: `csi2`
- Source pad for capture path: `csi2:4`
- Video node: `rp1-cfe-csi2_ch0` as `/dev/video0`
- Trigger mode set on `/dev/v4l-subdev2`

---

### B) Implement live ROS camera capture

Make ROS read real frames and publish them continuously.

- ✅ Implement `camera_capture_node.py`
- ✅ Open `/dev/video0` with OpenCV V4L2 backend
- ✅ Use blocking capture in a dedicated thread
- ✅ Publish `/camera/image_raw`
- ✅ Publish `/camera/fps`
- ✅ Verify capture with real frames saved from test script

**Deliverables:**
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py`

**Validation:**
- `test_tevs_capture.py` captured 30 valid frames and saved `/tmp/tevs_first_frame.png`
- `camera_capture_node` initially reached about **60 FPS** locally, then dropped when extra subscribers and CLI tools were added

---

### C) Convert inference boundary from SUB-only file pipeline to live ROS frame request/response

Replace the old container-to-ROS detection pub/sub path with a live ROS-to-container frame path.

- ✅ Replace the old `inference_client_node` behaviour with live image subscription
- ✅ Subscribe to `/camera/image_raw`
- ✅ Resize to 640×640
- ✅ Serialize frames as raw bytes
- ✅ Send multipart ZMQ messages to container
- ✅ Receive JSON detections back
- ✅ Publish `/detections`
- ✅ Publish `/timing`

**Deliverables:**
- Updated `ros2_ws/src/thesis_inference_client/.../inference_client_node.py`

---

### D) Add ROS frame ingestion mode to the container inference service

Make the container accept ROS frames directly instead of pulling from camera or file.

- ✅ Extend `detection_zmq.py` with ROS frame ingestion mode
- ✅ Add REQ/REP server on port 5556
- ✅ Build live pipeline around `appsrc`
- ✅ Keep file mode intact
- ✅ Fix postprocess symbol mismatch
- ✅ Fix Hailo writable-buffer issue

**Deliverables:**
- Updated `/root/thesis_service/detection_zmq.py`

**Critical fixes needed before it worked:**
- Container had to run with the Hailo virtual environment Python
- `HAILO_POST_FUNC` had to be `filter`, not `yolov6n`
- `hailonet` needed `force-writable=true`
- Direct `python3 detection_zmq.py` was not enough, environment setup mattered

---

### E) Verify full live pipeline through tracker and selector

Once detections were live, reconnect the downstream ROS stack.

- ✅ Start `tracker_node`
- ✅ Start `target_selector_node`
- ✅ Confirm `/tracks` publishes
- ✅ Confirm `/target` publishes
- ✅ Record a full-pipeline bag

**Deliverables:**
- Bag: `bags/raw/2026-03-08__camera_full_pipeline_smoke`

---

## Results

### Deliverables checklist

- ✅ `camera_init_node.py`
- ✅ `camera_capture_node.py`
- ✅ Live camera frames on `/camera/image_raw`
- ✅ Live camera FPS diagnostics on `/camera/fps`
- ✅ Live REQ/REP inference path on `127.0.0.1:5556`
- ✅ `/detections` publishing from live camera
- ✅ `/timing` publishing from live camera inference path
- ✅ `/tracks` publishing
- ✅ `/target` publishing
- ✅ Full-pipeline smoke bag recorded

---

### TEVS camera bring-up result

The camera bring-up is now **reproducible**.

**Confirmed working sequence:**
1. Set sensor pad format on `tevs 11-0048:0`
2. Set CSI sink pad format on `csi2:0`
3. Set CSI source pad format on `csi2:4`
4. Enable link `csi2:4 -> rp1-cfe-csi2_ch0:0`
5. Set `trigger_mode=0` on `/dev/v4l-subdev2`

**What failed and was abandoned:**
- `media-ctl --reset` when the device was busy
- `v4l2-ctl --set-fmt-video` on `/dev/video0`
- `v4l2-ctl --get-fmt-video` on `/dev/video0`
- `v4l2-ctl --stream-mmap` as init verification

These were not reliable enough for this TEVS + RP1 path and caused blocking or misleading behaviour.

---

### Camera capture result

`camera_capture_node` worked with real frames.

**Observed behaviour:**
- Local node logs initially showed about **60 FPS**
- Later values dropped into the 30 to 40 FPS range when CLI subscribers were added
- This was treated as subscriber overhead, not sensor failure

**Key interpretation:**  
`/camera/fps` and internal node logs are the real camera-side indicators.  
`ros2 topic hz /camera/image_raw` is not trustworthy as the authoritative sensor-rate metric.

---

### Live inference result

The live ROS-to-container inference boundary is **working**.

**Direct evidence:**
- `inference_client_node` reported successful send/receive cycles
- Real person detections were published on `/detections`
- `/timing` was published continuously
- Tracker and target selector both received downstream messages successfully

**Example observed runtime from the live system:**
- `/detections` rate: about **16.2 Hz** ✅
- Sample `lat_ms`: about **127.6 ms** ✅
- This is above the minimum FPS target and under the latency budget

---

### Full-pipeline smoke bag

**Recorded:**
- `bags/raw/2026-03-08__camera_full_pipeline_smoke`

**Bag info:**
- Duration: about 28.49 s
- Total messages: 1070
- Counts:
  - `/detections`: 214
  - `/timing`: 214
  - `/tracks`: 214
  - `/timing_tracker`: 214
  - `/target`: 214

---

### Timing report from full-pipeline smoke bag

From `reports/timing/2026-03-08__camera_full_pipeline_smoke__timing.md`:

**Per-field stats from /timing:**
- `lat_ms`: mean 67.11, p50 63.92, p95 98.36, p99 124.24, max 140.85
- `recv_ms`: mean 16.00
- `json_ms`: mean 15.99
- `loop_ms`: mean 35.76, p95 48.76, p99 64.10
- `pub_dt_ms`: mean 135.62, p50 146.49, p95 208.50

**Interpretation:**
- Latency is already good enough for the thesis target
- Tracker runtime is small
- Full-pipeline achieved Hz during the bag was only about **7.5 Hz**, so throughput still needs cleanup before calling the full chain "done"

---

### Tracker and selector output

**`/tracks --once`:**
- Header correctly stamped and `frame_id` set to `camera`
- One live person track published
- Track ID present

**`/target --once`:**
- Target published successfully
- Selected target geometry present
- Target ID present

**But two data-quality issues remain:**
- `score` on `/tracks` was 0.0
- `/target.header` was empty and `/target.score` was 0.0

So the chain is alive, but metadata propagation still needs fixing.

---

## Issues / Risks

### 1) Driver path and media graph were much more fragile than expected

The main technical blocker was not camera detection, it was the exact graph configuration and which device each control belonged to.

### 2) Several standard V4L2 checks were misleading on this hardware path

Some commands that should normally be safe were hanging or unreliable on `/dev/video0`. Using them as formal success checks would have made the ROS node look broken even when the real capture path worked.

### 3) Container runtime setup is still delicate

The container service only worked after:
- Using the Hailo venv Python
- Setting postprocess function to `filter`
- Forcing writable buffers in `hailonet`

This path works now, but it is not yet cleanly wrapped in a single robust launcher.

### 4) Performance fell when the system was observed too heavily

CLI subscribers and inspection tools clearly affected throughput. This matters because naive live measurement can make the pipeline look worse than it really is.

### 5) Metadata propagation bug remains downstream

The chain publishes tracks and targets, but `score` and `header` fields are not being propagated correctly through tracker/selector.

---

## Clear conclusion

Today was a **major integration day**.

**What is now true:**
- The TEVS camera is no longer an isolated hardware test
- ROS now owns camera init and capture
- The container now accepts live ROS frames and returns detections
- The live perception chain is real, not simulated
- The minimum detection-rate target was achieved in direct live testing
- Tracker and target selector are already connected to live detections

**What is not yet true:**
- The full recorded pipeline is not yet cleanly sustaining the target rate during bagged end-to-end operation
- Tracker and selector metadata are not fully correct
- Timing instrumentation still needs refinement, especially the meaning of `recv_ms` and `json_ms`

**So the big risk changed today.**  
It is no longer "can the camera be integrated?"  
It is now "can the full live pipeline be cleaned up and stabilised at the target rate?"

---

## Next steps (Tomorrow)

- [ ] Fix `tracker_node` metadata propagation:
  - Preserve `score` from detections into tracks
  - Verify header remains correct

- [ ] Fix `target_selector_node` metadata propagation:
  - Copy incoming track header to target header
  - Propagate selected track score

- [ ] Re-run full live chain without extra CLI subscribers

- [ ] Record a new clean full-pipeline bag

- [ ] Re-check full-pipeline achieved Hz

- [ ] Review `recv_ms` and `json_ms` instrumentation in `inference_client_node`

- [ ] Decide whether container ROS frame-ingest mode is now frozen enough to be treated as the new baseline

---

## Links

- Timing report: `reports/timing/2026-03-08__camera_full_pipeline_smoke__timing.md`
- Figures: `figures/timing/2026-03-08__camera_full_pipeline_smoke/`
- Bag: `bags/raw/2026-03-08__camera_full_pipeline_smoke`

---

**Status at end of day:**  
Camera bring-up complete, live inference complete, downstream tracker/selector connected, full chain recorded.  
Main remaining work is metadata cleanup and proving sustained full-pipeline rate under clean measurement conditions.
