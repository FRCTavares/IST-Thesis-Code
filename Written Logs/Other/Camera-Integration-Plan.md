# TEVS Camera Integration Plan
**Date:** 2026-03-08  
**Goal:** Integrate TEVS-AR0234 camera as ROS 2 sensor for real-time person perception  
**Status:** Architecture finalized, ready for implementation

---

## Executive Summary

**Current:** Video files → Container inference → ZMQ → ROS2 perception pipeline  
**Target:** Camera → ROS2 sensor nodes → Container inference → ROS2 perception pipeline

**Key Changes:**
- Camera owned by ROS2 (not container)
- Frame capture and timestamping in ROS
- Container receives frames via ZMQ, returns detections
- Inference-side queue control handled in `inference_client_node`

**Performance:** Camera: 58 FPS capable, Thesis target: ≥15 FPS sustained, p95 latency ≤200ms

---

## System Architecture

### Node Responsibilities

**camera_init_node** (Lifecycle)
- Configures TEVS media pipeline via `media-ctl` and `v4l2-ctl`
- Runs once at startup, validates `/dev/video0` and `/dev/media0`
- Publishes `/camera/status` diagnostic

**camera_capture_node** (Sensor Driver)
- Reads frames from `/dev/video0` using OpenCV/V4L2
- Assigns ROS timestamps immediately on capture
- Publishes frames to `/camera/image_raw`
- Publishes camera FPS diagnostics
- **Responsibility:** Sensor acquisition and timestamp origin

**inference_client_node** (Inference Boundary)
- Subscribes to `/camera/image_raw`
- Owns bounded queue (size 1-2) and oldest-drop policy
- Drops oldest unprocessed frame when inference lags
- Resizes and serializes frames for container
- Sends frames to container via ZMQ
- Receives detections with matched timestamps
- Publishes `/detections` and `/timing`
- **Responsibility:** Inference boundary, flow control, latency accounting

**Container (Hailo Inference Service)**
- Receives frames from ROS via ZMQ (no hardware access)
- Uses GStreamer `appsrc` (not `v4l2src` or `filesrc`)
- Runs Hailo accelerated inference
- Returns detections via ZMQ
- **Container never accesses `/dev/video0`**

### Communication Contract

**Request (ROS → Container):**
- Transport: ZMQ multipart message
  - Part 1: JSON metadata `{"timestamp_ns", "width", "height", "channels", "dtype", "encoding"}`
  - Part 2: Raw frame bytes (not base64)

**Response (Container → ROS):**
- JSON: `{"timestamp_ns", "infer_ms", "detections": [...]}`

---

## Data Flow

1. **Camera Init** - `camera_init_node` configures media pipeline
2. **Frame Capture** - `camera_capture_node` reads from `/dev/video0`, assigns `t_capture`, publishes to `/camera/image_raw`
3. **Inference Request** - `inference_client_node` subscribes, maintains bounded queue (size 1-2), drops oldest if busy, resizes frame, records `t_frame_sent`, sends metadata + raw bytes via ZMQ
4. **Containerized Inference** - Container receives frame, feeds to GStreamer `appsrc`, runs Hailo detection
5. **Detection Publication** - `inference_client_node` receives detections, records `t_infer_end`, publishes `/detections` and `/timing`
6. **Tracking** - `tracker_node` updates tracks, publishes `/tracks`
7. **Target Selection** - `target_selector_node` maintains target lock, publishes `/target`

**Frame dropping:** Occurs at inference boundary (not sensor boundary). `inference_client_node` drops oldest queued frame when newer frame arrives and inference is busy. This is expected and intentional to prevent latency growth.

---

## Timing Model

**Critical Timestamps (ROS Clock):**
- `t_capture` - Frame captured from camera
- `t_frame_sent` - Frame serialized and sent via ZMQ to container
- `t_infer_end` - Detections received from container
- `t_track_start` - Tracker begins processing
- `t_track_pub` - Tracks published

**Optional Debug Instrumentation:**
- `t_frame_received` - Container acknowledges receipt (for network latency isolation if needed)

**Latency Definitions:**
- End-to-end: `lat_e2e = t_track_pub - t_capture`
- Inference: `lat_infer = t_infer_end - t_frame_sent`
- Tracker: `lat_tracker = t_track_pub - t_track_start`

**Budget (Target p95 ≤ 200ms):**
- Camera capture: 0-2ms
- Image preprocessing: 5-10ms
- ZMQ send: 0.1-1ms
- Hailo inference: 20-35ms
- ZMQ receive: 0.1-1ms
- Tracker update: 5-15ms
- **Total expected: 35-75ms** (comfortable margin)

---

## Data Serialization

**Use raw bytes (not base64):**
- Raw bytes: 36 MB/s @ 30 FPS (1.2 MB/frame)
- Base64: 48 MB/s @ 30 FPS (33% overhead)
- Localhost ZMQ handles binary efficiently

**Implementation:**
```python
# ROS side
frame_bytes = frame_resized.tobytes()
zmq_socket.send_json(metadata, flags=zmq.SNDMORE)
zmq_socket.send(frame_bytes, flags=0, copy=False)

# Container side
metadata = zmq_socket.recv_json()
frame_bytes = zmq_socket.recv(copy=False)
frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((h, w, 3))
```

---

## Implementation Phases

### Phase 1: Camera Bring-Up (ROS-Side)
**Duration:** 1 day (6-8 hours)

**Deliverables:**
1. `camera_init_node.py` - Media pipeline configuration
2. `camera_capture_node.py` - Frame capture with blocking read
3. Verified `/camera/image_raw` publishing
4. Verified timestamps assigned immediately
5. Verified FPS diagnostics

**Key Points:**
- `camera_init_node` runs media-ctl commands, validates devices
- `camera_capture_node` uses blocking `cap.read()` in dedicated thread (not timer polling)
- Publishes to `/camera/image_raw` with immediate timestamping

**Phase 1 Success Condition:**
- Camera nodes run standalone, no container integration yet

---

### Phase 2: Modify Inference Client
**Duration:** 1 day (6-8 hours)

**Deliverables:**
1. Modified `inference_client_node.py` to send frames via ZMQ
2. Frame queue (size 1-2) with oldest-drop policy
3. Frame serialization (resize + raw bytes)
4. Timing measurements (`t_frame_sent`, `t_infer_end`)

**Key Changes:**
- Subscribe to `/camera/image_raw`
- Resize to 640×640
- Use ZMQ REQ/REP sockets
- Use multipart messages: Part 1 (metadata JSON), Part 2 (raw frame bytes)
- Receive detections with matched timestamps

---

### Phase 3: Container Frame Ingestion
**Duration:** 1 day (6-8 hours)

**Deliverables:**
1. Modified `detection_zmq.py` to receive frames from ROS
2. GStreamer `appsrc` integration
3. Backward compatibility (file mode for testing)

**Key Changes:**
- Add ZMQ server for frame ingestion
- Replace `filesrc`/`v4l2src` with `appsrc`
- Feed frames to GStreamer: `appsrc → videoconvert → hailonet → hailofilter`
- Env var: `HAILO_FRAME_SOURCE=ros|file`

---

### Phase 4: Launch Integration + Dry-Run Mode
**Duration:** 1 day (6-8 hours)

**Deliverables:**
1. `live_camera.launch.py` - Full pipeline launch
2. Dry-run mode: `use_camera:=false` uses video file
3. Parameter configuration

**Container Startup:**
- **For first implementation:** Start container inference service manually in separate terminal
- ROS launch file starts only ROS nodes
- This simplifies bring-up and debugging

**Launch Arguments:**
- `use_camera:=true|false` (default: true)
- `video_file:=<path>` (for dry-run)

**Launch Sequence (Live Mode):**
1. `camera_init_node` (lifecycle, configure media pipeline)
2. `camera_capture_node` (after init active)
3. `inference_client_node`
4. `tracker_node`
5. `target_selector_node`

**ROS Dry-Run Mode (use_camera:=false):**
- Video publisher node publishes to `/camera/image_raw` from file
- `inference_client_node` still sends frames to container (container in ROS frame mode)
- Same downstream pipeline (inference → tracker → selector)

**Container Service-Only Test (separate mode):**
- Container runs with `HAILO_FRAME_SOURCE=file` internally
- No ROS camera path involved
- For debugging container inference service independently

---

### Phase 5: End-to-End Validation
**Duration:** 1 day (6-8 hours)

**Tests:**
1. Camera-only validation (Hz check)
2. Inference integration (latency check)
3. Bag recording (60s test)
4. Offline analysis (FPS, p95 latency)
5. Stress test (10 minutes)

**Acceptance:**
- FPS sustained ≥15 Hz
- Latency p95 < 200ms
- System stable for ≥10 minutes

---

### Phase 6: Performance Evaluation
**Duration:** 4-6 hours

**Deliverables:**
1. Performance report (FPS, latency distributions)
2. Comparison: live camera vs video file
3. Bottleneck identification

**Metrics:**
- Frame rate (mean, std, min, max)
- Latency distribution (p50, p95, p99)
- Component breakdown (inference, tracker)
- Resource utilization (CPU, temp)

---

## Failure Modes

**Mode 1: Container Restart**
- Symptom: ZMQ timeout in `inference_client_node`
- Recovery: Automatic reconnect with ZMQ built-in retry
- Impact: 1-2 second gap in detections

**Mode 2: Camera Device Lost**
- Symptom: `cap.read()` returns false
- Recovery: `camera_capture_node` logs error, attempts reinit
- Fallback: Reseat ribbon cable, power cycle, reboot after checking overlay and connection

**Mode 3: Frame Rate Mismatch (Queue Overflow)**
- Symptom: Camera 58 FPS, inference 30 FPS
- Behavior: `inference_client_node` drops oldest frame (expected)
- Tuning: Adjust queue size (1-2 frames)

---

## Quick Reference

### Start Live Pipeline
```bash
ros2 launch thesis_bringup live_camera.launch.py
```

### Dry-Run Mode (Video File)
```bash
ros2 launch thesis_bringup live_camera.launch.py use_camera:=false video_file:=/path/to/test.mp4
```

### Monitor Performance
```bash
ros2 topic hz /camera/image_raw /detections /tracks
ros2 topic echo /timing --once
```

### Record Bag
```bash
cd ~/Desktop/Thesis-Code/bags/raw
timeout 60s ros2 bag record --storage mcap /detections /timing /tracks /target
```

### Analyze Latency
```bash
python3 tools/analyse_bag_timing.py bags/raw/<bag_name>
```

### Health Check
```bash
# Camera devices
ls -la /dev/video0 /dev/media0

# Camera format
v4l2-ctl -d /dev/video0 --get-fmt-video

# Camera status
ros2 topic echo /camera/status --once

# Camera publishing
ros2 topic hz /camera/image_raw

# Container running
docker ps | grep hailo

# ROS topics active
ros2 topic list
```

---

## Risk Mitigation

**High Risk:**
- GStreamer `appsrc` integration in container
- ZMQ request/response under sustained load
- Timestamp preservation across ROS → container → ROS
- Inference backlog causing stale-frame processing

**Medium Risk:**
- OpenCV colour format mismatch (UYVY → BGR/RGB)
- Serialization overhead and CPU cost
- Tracker timing drift if detections irregular

**Low Risk:**
- Camera bring-up (sensor already validated at 58 FPS)

---

## Success Criteria

**Functional:**
- ✅ Camera initializes reliably via `camera_init_node`
- ✅ `/camera/image_raw` publishes with monotonic ROS timestamps
- ✅ Container receives inference frames from ROS and returns detections with matched timestamps
- ✅ Detections published at ≥15 FPS sustained
- ✅ ROS pipeline processes live camera feed
- ✅ Can record rosbags with live camera input

**Performance:**
- ✅ Sustained FPS: ≥15 (target: 20-30)
- ✅ Latency p95: ≤200ms (stretch: ≤100ms)
- ✅ No unbounded latency growth over 5 minutes

**Operational:**
- ✅ Single command launch
- ✅ Dry-run mode for testing without camera
- ✅ Clear diagnostics and error messages

---

## Environment Variables

**Container:**
- `HAILO_FRAME_SOURCE=ros|file` - Frame source mode
- `HAILO_VIDEO_SOURCE` - Only used when `HAILO_FRAME_SOURCE=file`
- `HAILO_HEF_PATH` - Model file path
- `HAILO_INFER_WIDTH` / `HAILO_INFER_HEIGHT` - Inference resolution
- `HAILO_POST_SO` - Postprocess library
- `HAILO_ARCH` - Hailo architecture (hailo8)

**ROS Launch:**
- `use_camera:=true|false` - Enable live camera
- `video_file:=<path>` - Video file for dry-run mode

---

## Timeline

**Total effort:** 2-3 days (realistic, accounting for debugging)

**Day 1 (2026-03-08):**
- ✅ Camera validated (58 FPS)
- ✅ Plan finalized
- ⏳ Phase 1: Camera bring-up

**Day 2 (2026-03-09):**
- ⏳ Phase 2: Inference client modifications
- ⏳ Phase 3: Container frame ingestion

**Day 3 (2026-03-10):**
- ⏳ Phase 4: Launch integration
- ⏳ Phase 5: Validation
- ⏳ Phase 6: Performance evaluation

---

**Document Owner:** Francisco Tavares  
**Last Updated:** 2026-03-08  
**Status:** Ready for Implementation
