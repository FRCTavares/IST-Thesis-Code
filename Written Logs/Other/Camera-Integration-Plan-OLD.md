# TEVS Camera Integration Plan
**Date:** 2026-03-08  
**Goal:** Integrate TEVS-AR0234 camera as a ROS 2 sensor for real-time onboard person perception

---

## Executive Summary

**Current State:**
- Hailo inference service runs in Docker container `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1`
- Container reads MP4 video files, performs inference, publishes detections via ZMQ
- ROS 2 `inference_client_node` consumes detections and publishes to `/detections` topic
- Tracker and target selector operate downstream

**Target State:**
- Camera managed as **ROS 2 sensor** (not container device)
- ROS nodes handle: camera initialization, frame capture, timestamping, queue control
- Container responsibility: **inference only** (receives frames, returns detections)
- ROS maintains full timing control for thesis latency measurements
- Achieves thesis requirement: **15 FPS sustained** (camera capable of 58 FPS)

**Architectural Principle:** Sensor Layer → Perception Layer → Control Layer

---

## System Architecture

### ROS 2 Perception Pipeline (Host)

The ROS 2 host owns the complete perception pipeline and manages:
- Camera hardware initialization and configuration
- Frame capture with precise timestamping
- Inference request/response coordination
- Multi-object tracking and data association
- Target selection and state estimation
- Queue discipline and flow control
- Bag logging for offline analysis

**Key Nodes:**

1. **`camera_init_node`** (Lifecycle Node)
   - Configures TEVS media controller pipeline on startup
   - Validates device presence (`/dev/video0`, `/dev/media0`)
   - Runs once at system boot, then remains idle
   - Publishes `/camera/status` diagnostic topic

2. **`camera_capture_node`** (ROS 2 Sensor Driver)
   - Reads frames from `/dev/video0` using OpenCV
   - Assigns ROS timestamps (`rclcpp::Clock::now()`) on capture
   - Publishes to `/camera/image_raw` (or sends directly to inference)
   - Implements frame drop policy if inference is slower than capture
   - **Responsibility:** All timing measurements start here

3. **`inference_client_node`** (Perception Interface)
   - Subscribes to camera frames (or receives via internal queue)
   - Sends frames to container inference service via ZMQ
   - Receives detection results with matched timestamps
   - Publishes `/detections` with ROS timing metadata
   - Publishes `/timing` for latency analysis
   - **Responsibility:** Tracks end-to-end latency

4. **`tracker_node`** (Multi-Object Tracking)
   - Subscribes to `/detections`
   - Performs online tracking (SORT/ByteTrack/OC-SORT)
   - Publishes `/tracks` with track IDs and state
   - Publishes `/timing_tracker` for tracker-specific latency

5. **`target_selector_node`** (Decision Logic)
   - Subscribes to `/tracks`
   - Maintains target lock and reacquisition logic
   - Publishes `/target` for downstream control
   - Implements state machine for target management

**ROS Topics (Full Pipeline):**
```
/camera/status          [std_msgs/String]         Camera health status
/camera/image_raw       [sensor_msgs/Image]       Raw frames (optional intermediate)
/detections             [vision_msgs/Detection2DArray]  Person detections
/timing                 [thesis_msgs/Timing]      Frame-level latency data
/tracks                 [thesis_msgs/TrackArray]  Multi-object tracks
/timing_tracker         [thesis_msgs/Timing]      Tracker latency
/target                 [thesis_msgs/Target]      Selected target state
```

### Inference Service (Container)

The containerized inference service has **no hardware management responsibility**. Its sole purpose is compute-intensive inference using the Hailo accelerator.

**Container Responsibilities:**
- Load HEF model on startup (`yolov6n_hailo8.hef`)
- Receive inference requests via ZMQ (image data + timestamp)
- Run detection on Hailo hardware
- Return detection results (bboxes, scores, classes) via ZMQ
- Maintain reproducible Hailo SDK environment

**Container Does NOT:**
- Access camera hardware
- Assign timestamps
- Manage frame queues
- Make perception decisions
- Log data

**Communication Contract:**

*Request (ROS → Container):*
```json
{
  "timestamp_ns": 1234567890,
  "width": 640,
  "height": 640,
  "encoding": "rgb8",
  "data": "<base64 encoded image bytes>"
}
```

*Response (Container → ROS):*
```json
{
  "timestamp_ns": 1234567890,
  "infer_ms": 28.5,
  "detections": [
    {"x1": 120, "y1": 80, "x2": 240, "y2": 400, "score": 0.87, "class_id": 0},
    ...
  ]
}
```

**Design Rationale:**
- ROS controls timing → accurate latency measurement for thesis
- ROS controls queues → predictable frame dropping behavior
- ROS logs everything → complete rosbag2 traces
- Container is stateless → easy to restart, upgrade, or replace

---

## Data Flow

End-to-end frame processing sequence:

1. **Camera Initialization (Boot)**
   - `camera_init_node` configures TEVS media pipeline via `media-ctl` and `v4l2-ctl`
   - Pipeline: `tevs sensor → csi2 receiver → /dev/video0`
   - Node publishes "ready" to `/camera/status`

2. **Frame Capture (30-58 Hz)**
   - `camera_capture_node` calls `cv2.VideoCapture('/dev/video0').read()`
   - **Critical:** ROS timestamp `t_capture` assigned immediately
   - Frame stored in node's internal queue (max size: 5 frames)

3. **Inference Request (Async)**
   - `inference_client_node` receives frame from capture node
   - Converts frame to inference resolution (1920×1080 → 640×640)
   - Records `t_infer_start`
   - Sends frame + `t_capture` to container via ZMQ (`tcp://127.0.0.1:5555`)

4. **Containerized Inference (~30ms)**
   - Container receives frame via ZMQ
   - GStreamer pipeline processes the frame
   - Hailo accelerator runs detection
   - Postprocessing extracts bboxes
   - Container sends detections back via ZMQ with original `t_capture`

5. **Detection Publication**
   - `inference_client_node` receives detections
   - Records `t_infer_end`
   - Calculates latency: `lat_ms = (t_infer_end - t_capture) / 1e6`
   - Publishes `Detection2DArray` to `/detections`
   - Publishes `Timing` message with latency breakdown

6. **Tracking Update (~10ms)**
   - `tracker_node` receives detections
   - Updates Kalman filters and performs data association
   - Publishes tracked objects to `/tracks`
   - Publishes `timing_tracker` with tracker-specific latency

7. **Target Selection**
   - `target_selector_node` receives tracks
   - Applies selection policy (e.g., largest bbox, closest to center)
   - Maintains target lock across occlusions
   - Publishes active target to `/target`

8. **Logging (Continuous)**
   - All topics logged to rosbag2 (MCAP format)
   - Offline analysis tools process bags for FPS, latency distributions, tracking metrics

**Timing Sequence Diagram:**
```
t_capture ──────┬──────────────────────────────────┐
 (ROS)          │                                  │
                │                                  │
                v                                  v
        t_infer_start                     t_tracker_start
                │                                  │
                │  (Container inference)           │
                v                                  │
        t_infer_end                                │
                │                                  │
                v                                  v
        Detection2DArray                   TrackArray
             + Timing                      + Timing
```

**Key Insight:** Every timestamp originates from ROS clocks. The container is timing-agnostic, which ensures reproducible latency measurements regardless of container restarts or GStreamer buffering.

---

## Camera Integration Strategy

**Architectural Decision:** Who owns the camera hardware?

### ✅ Option A: ROS-Managed Camera (Recommended)

**Architecture:**
```
Camera Hardware → ROS Sensor Node → Inference Service → ROS Perception
```

**ROS Responsibilities:**
- Hardware initialization (media-ctl pipeline)
- Frame capture and timestamping
- Queue management (frame drop policy)
- Inference request/response coordination
- Timing measurement and logging

**Container Responsibilities:**
- Inference only (stateless compute service)

**Advantages:**
1. **Precise latency measurement:** Timestamps assigned at capture, preserved through pipeline
2. **ROS queue control:** Explicit frame dropping when inference lags camera
3. **Easier debugging:** Can test camera, inference, tracking independently
4. **Modular architecture:** Future features (ROI refine, embedding extraction) integrate cleanly
5. **Thesis alignment:** Matches "latency-bounded ROS 2 pipeline" deliverable (Deliverable 3)
6. **Standard robotics practice:** Sensors belong to robot middleware, not compute services

**Implementation:**
- Create `camera_capture_node` (ROS 2 sensor driver)
- Modify `inference_client_node` to send frames via ZMQ request/response
- Container remains unchanged (still uses GStreamer + Hailo, just receives frames differently)

### ❌ Option B: Container-Managed Camera (Not Recommended)

**Architecture:**
```
Camera Hardware → Container → Inference → ZMQ → ROS Perception
```

**Disadvantages:**
1. **Lost timestamp control:** Container assigns timestamps, ROS cannot verify capture time
2. **Harder latency measurement:** Cannot distinguish camera capture from inference latency
3. **Frame dropping unclear:** GStreamer buffering hides when frames are dropped
4. **Less modular:** Camera logic coupled to inference container
5. **Thesis risk:** "End-to-end latency" becomes ambiguous without capture timestamp
6. **Non-standard:** Unusual for ROS systems to not own sensors

**When Acceptable:**
- Quick prototyping only
- When latency measurement is not critical
- When camera drivers are container-specific

**Decision:** Implement Option A (ROS-managed camera) to maintain timing control and align with thesis requirements.

---

## Camera Hardware Overview

### Performance Validated (2026-03-08)
- **Measured FPS:** 58.4 FPS @ 1920×1080
- **Frame timing:** 17.1ms avg (±6.6ms std dev)
- **Worst-case latency:** 82.2ms (single frame outlier)
- **Thesis requirement:** 15 FPS minimum → **3.9× headroom**

### Hardware Details
- **Sensor:** e-con Systems TEVS-AR0234
- **Interface:** CSI-2 on CAM1 port (Raspberry Pi 5)
- **Driver:** `tevs-rpi22` device tree overlay
- **Chip ID:** 0x0A56, Firmware 25.10.0.1
- **V4L2 devices:**
  - `/dev/video0` (capture node)
  - `/dev/media0` (media controller)
  - `/dev/v4l-subdev2` (sensor subdevice)

### Supported Formats
- **Pixel format:** UYVY8_1X16 (packed YUV 4:2:2)
- **Resolutions:** 640×480, 1280×720, 1920×1080, 1920×1200
- **Colorspace:** sRGB, xfer:sRGB, ycbcr:601, quantization:full-range
- **Trigger mode:** 0 (continuous streaming, not trigger sync)

### Initialization Requirements
- **Pipeline setup:** Media controller links must be configured after boot
- **Command sequence:**
  ```bash
  media-ctl -d /dev/media0 --reset
  media-ctl -d /dev/media0 -l '"tevs 10-0048":0 -> "rp1-cfe-csi2_ch0":0[1]'
  media-ctl -d /dev/media0 -V '"tevs 10-0048":0 [fmt:UYVY8_1X16/1920x1080 colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range]'
  media-ctl -d /dev/media0 -V '"rp1-cfe-csi2_ch0":0 [fmt:UYVY8_1X16/1920x1080 colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range]'
  v4l2-ctl -d /dev/video0 --set-fmt-video=width=1920,height=1080,pixelformat=UYVY
  v4l2-ctl -d /dev/video0 --set-ctrl=trigger_mode=0
  ```
- **Persistence:** Configuration lost on reboot, requires reinitialization
- **Validation:** `v4l2-ctl -d /dev/video0 --list-formats-ext` should show UYVY formats

---

## Timing and Latency Model

Your thesis depends on accurate end-to-end latency measurement. This section defines the timing model explicitly.

### Timing Events

**Critical Timestamps (ROS Clock):**
1. **`t_capture`** - Frame captured from camera (`camera_capture_node`)
2. **`t_infer_start`** - Frame sent to inference service (`inference_client_node`) - DEPRECATED in favor of `t_frame_sent`
3. **`t_frame_sent`** - Frame serialized and sent via ZMQ to container (more precise than `t_infer_start`)
4. **`t_frame_received`** - Container acknowledges frame receipt (optional, for network latency isolation)
5. **`t_infer_end`** - Detections received from inference service
6. **`t_det_pub`** - Detections published to `/detections` topic
7. **`t_track_start`** - Tracker begins processing frame
8. **`t_track_pub`** - Tracks published to `/tracks` topic

**Container-Side Timing (Informational Only):**
- `infer_ms` - Time spent in Hailo inference (measured inside container)
- Note: Not used for end-to-end latency (container clock may drift)

**Timing Granularity (Optional):**
- `t_frame_sent` and `t_frame_received` enable isolation of:
  - **Serialization latency:** Time to convert frame to bytes
  - **Network latency:** Time for ZMQ message transit (localhost, ~0.1-1ms)
  - **Deserialization latency:** Time to reconstruct numpy array in container
- Useful for debugging outliers (e.g., "was this spike due to network or inference?")

### Latency Definitions

**End-to-End Perception Latency** (Primary Thesis Metric):
```
lat_e2e = t_track_pub - t_capture
```
This measures from physical event (photons hit sensor) to perception output (tracks available for control).

**Inference Latency** (Component Metric):
```
lat_infer = t_infer_end - t_frame_sent
```
Includes: ZMQ roundtrip + serialization + image preprocessing + Hailo execution + postprocessing.

**Frame Transmission Latency** (Diagnostic Metric):
```
lat_transmission = t_frame_received - t_frame_sent  # If t_frame_received implemented
```
Isolates network + serialization overhead (typically < 2ms for localhost ZMQ).

**Tracker Latency** (Component Metric):
```
lat_tracker = t_track_pub - t_track_start
```
Purely tracker computation (Kalman update, data association, state prediction).

### Latency Budget (Thesis Target: p95 ≤ 200ms)

| Component | Expected | Budget | Notes |
|-----------|----------|--------|-------|
| Camera capture | 0-2ms | 5ms | Negligible (V4L2 read) |
| Image preprocessing | 5-10ms | 15ms | Resize 1920×1080 → 640×640 on CPU |
| ZMQ send | 0.1-1ms | 2ms | Localhost, small overhead |
| Hailo inference | 20-35ms | 50ms | Model-dependent, GPU-accelerated |
| Postprocessing | 5-10ms | 15ms | NMS, bbox extraction |
| ZMQ receive | 0.1-1ms | 2ms | Localhost return trip |
| Tracker update | 5-15ms | 20ms | SORT: fast, ByteTrack: moderate |
| **Total** | **35-75ms** | **~110ms** | Comfortable margin under 200ms |

**Stretch Goal (p95 ≤ 100ms):**
- Requires optimization: faster preprocessing, batch size tuning, C++ tracker

### Timing Message Format

Published on `/timing` topic (type: `thesis_msgs/Timing`):
```yaml
header:
  stamp: t_capture          # Original capture timestamp
  frame_id: "camera"
lat_ms: 42.3                # End-to-end latency (ms)
pub_dt_ms: 33.1             # Time since last frame (ms)
breakdown:                   # Component latencies
  - name: "inference"
    duration_ms: 28.5
  - name: "tracker"
    duration_ms: 11.2
```

This message connects directly to your offline analysis tools (`analyse_bag_timing.py`).

### Measurement Integrity

**Why ROS Timestamps Matter:**
- Capture timestamp `t_capture` assigned immediately after `cv2.read()` returns
- All downstream nodes reference this timestamp (no clock drift between nodes)
- Container inference time `infer_ms` is informational only
- If container restarts, ROS timestamps remain valid (container state doesn't affect measurement)

**Frame Drop Detection:**
```python
if (t_current - t_previous) > 2.0 * expected_dt:
    # Gap detected (container restart, GStreamer stall, etc.)
    # This frame excluded from latency percentiles
```

---

## Data Serialization Strategy

When transmitting frames from ROS to the container via ZMQ, serialization method significantly impacts performance.

### Serialization Options

| Method | Frame Size (1920×1080 RGB) | Frame Size (640×640 RGB) | CPU Cost | Implementation |
|--------|----------------------------|--------------------------|----------|----------------|
| **Raw bytes** | 1.2 MB | 1.2 MB (at 640×640) | Low | `ndarray.tobytes()` |
| **Base64** | 1.6 MB | 1.6 MB | Moderate | `base64.b64encode()` |
| **Shared memory** | 0 bytes (pointer) | 0 bytes | Very low | POSIX shm (complex) |
| **Protobuf** | ~1.2 MB (compressed) | ~1.2 MB | High | `.proto` schema |

### Network Throughput Analysis

**At 30 FPS sustained:**
- Raw bytes: 1.2 MB × 30 = **36 MB/s** (288 Mbps)
- Base64: 1.6 MB × 30 = **48 MB/s** (384 Mbps)
- Localhost TCP: ~10-20 Gbps theoretical → **Well within capacity**

**Conclusion:** Even base64 is acceptable for localhost ZMQ, but raw bytes preferred for efficiency.

### Recommended Approach: Raw Bytes

**ROS Side (inference_client_node.py):**
```python
import numpy as np

def send_frame(self, img: np.ndarray):
    """Send frame to container via ZMQ (raw bytes)"""
    # Resize to inference resolution
    frame_resized = cv2.resize(img, (640, 640), interpolation=cv2.INTER_LINEAR)
    
    # Serialize as raw bytes (NO base64)
    frame_bytes = frame_resized.tobytes()
    
    # Construct message
    msg = {
        "timestamp_ns": self.get_clock().now().nanoseconds,
        "width": 640,
        "height": 640,
        "channels": 3,
        "dtype": "uint8",
        "data": frame_bytes  # Raw bytes, NOT base64-encoded string
    }
    
    # Send via ZMQ
    self.zmq_socket.send_json(msg, flags=zmq.SNDMORE)
    self.zmq_socket.send(frame_bytes, flags=0, copy=False, track=False)
```

**Container Side (detection_zmq.py):**
```python
def receive_frame(zmq_socket):
    """Receive frame from ROS via ZMQ (raw bytes)"""
    # Receive metadata
    metadata = zmq_socket.recv_json()
    
    # Receive frame bytes
    frame_bytes = zmq_socket.recv(copy=False, track=False)
    
    # Reconstruct numpy array
    frame = np.frombuffer(
        frame_bytes,
        dtype=np.uint8
    ).reshape((metadata["height"], metadata["width"], metadata["channels"]))
    
    return frame, metadata["timestamp_ns"]
```

### Why Not Base64?

**Base64 overhead:**
- Encodes 3 bytes as 4 ASCII characters → **33% size increase**
- Requires `base64.b64encode()` (CPU) on send, `base64.b64decode()` (CPU) on receive
- At 30 FPS: 48 MB/s vs 36 MB/s = **12 MB/s wasted bandwidth + CPU cycles**

**When base64 is needed:**
- Cross-network transmission via HTTP/REST APIs
- JSON-only transport (no binary support)
- Debugging (human-readable frame data in logs)

**Our case:** Localhost ZMQ supports binary frames natively → use raw bytes.

### Alternative: Shared Memory (Future Optimization)

If frame transmission becomes a bottleneck (e.g., 4K resolution, 60 FPS):
- Use POSIX shared memory (`/dev/shm`)
- ROS writes frame to shared memory region
- Container reads from same region (zero-copy)
- ZMQ sends only pointer + metadata (< 100 bytes)

**Implementation complexity:** High (requires synchronization, lifetime management, container volume mapping)  
**Performance gain:** ~10-15ms latency reduction at high resolutions  
**Recommendation:** Defer until raw bytes proven insufficient

---

## Resource Budget

Your thesis targets real-time onboard perception. This section quantifies compute resources.

### Compute Capacity

| Resource | Specification | Utilization | Headroom |
|----------|---------------|-------------|----------|
| CPU | Cortex-A76 4-core @ 2.4 GHz | ~60% (1 core for capture, 1 for ROS) | Moderate |
| Hailo NPU | 26 TOPS int8 | ~40% (YOLOv6n) | High |
| Memory | 8 GB LPDDR4 | ~2 GB (ROS + container) | High |
| Camera CSI | 1.5 Gbps | ~1.2 Gbps (1920×1080@30) | Comfortable |

### Frame Rate Analysis

**Camera Capability:** 58.4 FPS @ 1920×1080 (validated)

**Inference Throughput:**
- YOLOv6n on Hailo: ~35-40 FPS (640×640 input)
- Bottleneck: Hailo inference, not camera

**System Throughput:**
- Expected: 20-30 FPS end-to-end
- Thesis target: ≥15 FPS sustained → **Achievable with margin**

**Frame Drop Strategy:**
```
Camera: 58 FPS ──┐
                 ├─> Queue (max 5 frames)
                 │
Inference: 30 FPS ←┘
                 
Drops: 58 - 30 = 28 frames/sec (expected)
Drop policy: Oldest frame dropped when queue full
```

### Latency Contribution Breakdown

| Stage | Duration (avg) | Percentage | Optimization Potential |
|-------|----------------|------------|------------------------|
| Image preprocessing | 8ms | 20% | ✅ Moderate (GPU upload, optimized resize) |
| Inference (Hailo) | 28ms | 70% | ⚠️ Low (model choice) |
| Tracking (SORT) | 4ms | 10% | ✅ High (C++ rewrite, batch updates) |
| **Total** | **40ms** | **100%** | |

**Key Insight:** Hailo inference dominates latency. To achieve stretch goal (p95 < 100ms), focus on model efficiency or explore batch processing.

### Sustained Operation

**Long-Run Stability Requirements:**
- No memory leaks over 10-minute runs
- CPU temperature stable (throttling avoided)
- Hailo device temperature monitored via `hailortcli`
- Frame rate does not degrade over time

**Validation Test:**
```bash
# 10-minute bag recording
timeout 600s ros2 bag record /detections /tracks /timing
# Offline analysis should show:
# - FPS stable within 10% variance
# - p95 latency growth < 20% (accounts for warmup)
```

---

## Failure Modes and Recovery

Your system spans hardware, ROS, Docker, and networking. Documenting failure behavior is essential for robust operation.

### Failure Mode 1: Camera Not Detected

**Symptom:** `/dev/video0` or `/dev/media0` missing at boot

**Detection:**
- `camera_init_node` fails with error: "Camera device not found"
- `/camera/status` topic shows "fault"

**Recovery:**
1. Check physical connection (cable fully seated on CAM1 port)
2. Verify device tree overlay: `dtparam=tevs-rpi22` in `/boot/firmware/config.txt`
3. Reboot if overlay was missing
4. If device still missing, cable or camera hardware fault

**Fallback:** Launch with video file replay instead of live camera
```bash
ros2 launch thesis_bringup first_ros2_slice.launch.py  # Uses video files
```

### Failure Mode 2: Camera Initialization Failed

**Symptom:** Device present but `media-ctl` or `v4l2-ctl` commands fail

**Detection:**
- `camera_init_node` logs: "Camera init failed: CalledProcessError"
- Common causes: Wrong media device (`/dev/media1` vs `/dev/media0`), colorspace mismatch

**Recovery:**
1. Check which media device has `tevs` sensor:
   ```bash
   media-ctl -d /dev/media0 -p | grep tevs
   ```
2. Update `camera_init_node` parameter if needed
3. Manually run initialization commands (see Camera Hardware Overview section)
4. Restart `camera_init_node`

**Fallback:** None - camera unusable until fixed

### Failure Mode 3: Inference Container Crash

**Symptom:** Container exits or becomes unresponsive mid-run

**Detection:**
- `inference_client_node` receives ZMQ timeout (> 1 second)
- `/timing` topic pub rate drops to 0 Hz
- Container logs show segfault or GStreamer error

**Recovery:**
1. Container auto-restarts (if `restart: unless-stopped` in docker-compose)
2. `inference_client_node` reconnects automatically (ZMQ reconnect logic)
3. First frame after restart may have high latency (HEF reload)
4. ROS pipeline resumes normal operation within 2-3 seconds

**Impact:** Temporary detection gap, tracks may be lost (reacquisition needed)

### Failure Mode 4: ZMQ Connection Lost

**Symptom:** `inference_client_node` cannot connect to `tcp://127.0.0.1:5555`

**Detection:**
- Node logs: "recv timeout, no messages"
- `/detections` topic not publishing

**Recovery:**
1. Check container status: `docker ps` (should show `hailo-ubuntu-pi`)
2. Check port binding: `ss -ltnp | grep 5555`
3. Restart container if needed
4. `inference_client_node` reconnects automatically (built-in reconnect with backoff)

**Fallback:** Manual container restart
```bash
cd ~/pi-ai-kit-ubuntu
docker compose restart hailo-ubuntu-pi
```

### Failure Mode 5: Frame Rate Too High (Queue Overflow)

**Symptom:** Camera produces 58 FPS but inference only processes 30 FPS

**Detection:**
- `/timing` messages show increasing `pub_dt_ms` variance
- Latency spikes as stale frames processed

**Behavior:**
- `camera_capture_node` drops oldest frames from queue (max size: 5)
- Inference always processes most recent frame
- Frame drops logged: "Dropped N frames (queue full)"

**Recovery:** Not needed - this is expected behavior (frame dropping by design)

**Tuning:**
- Reduce queue size for lower latency (more aggressive dropping)
- Increase queue size for smoother FPS (tolerates occasional inference spikes)

### Failure Mode 6: Tracker Drift / Target Loss

**Symptom:** Target selector loses track despite person still visible

**Detection:**
- `/target` shows `target_visible=false` despite detections present
- High ID switch rate in tracker metrics

**Recovery:**
1. Verify detections still published: `ros2 topic echo /detections --once`
2. Check tracker configuration (IOU threshold, max age)
3. Reacquisition policy triggers after timeout
4. Target selector falls back to largest bbox (last known selection strategy)

**Fallback:** Manual target reselection (future: operator override via joystick)

### System Health Check Script

```bash
#!/bin/bash
# tools/health_check.sh - Run before recording important bags

echo "=== System Health Check ==="

# 1. Camera devices
[ -e /dev/video0 ] && echo "✓ Camera device" || echo "✗ Camera missing"

# 2. Container running
docker ps | grep -q hailo-ubuntu-pi && echo "✓ Container" || echo "✗ Container down"

# 3. ZMQ port bound
ss -ltnp | grep -q 5555 && echo "✓ ZMQ port" || echo "✗ ZMQ not bound"

# 4. ROS topics active (requires ROS sourced)
timeout 2s ros2 topic hz /detections 2>/dev/null | grep -q "average rate" && echo "✓ Detections" || echo "✗ No detections"

# 5. Temperature check
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
echo "CPU temp: $((TEMP / 1000))°C"

echo "=== Check Complete ==="
```

---

## Implementation Plan

### Phase 1: Camera Bring-Up
**Duration:** 2-3 hours  
**Risk:** Low (camera already validated)

**Deliverables:**
1. `camera_init_node.py` - ROS 2 lifecycle node for media pipeline setup
2. Validation: Camera accessible via V4L2, GStreamer can capture frames
3. Documentation: Camera initialization commands, troubleshooting steps

**Tasks:**
- Create `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_init_node.py`
- Implement lifecycle configure/activate hooks
- Run initialize commands from Python (subprocess.run)
- Validate device presence before configuration
- Publish `/camera/status` diagnostic topic
- Add entry point to `setup.py`
- Test standalone: `ros2 run thesis_bringup camera_init_node`

**Acceptance Criteria:**
- Node starts without errors
- `/dev/video0` accessible after node runs
- `v4l2-ctl --list-formats` shows UYVY
- GStreamer test pipeline works:
  ```bash
  gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=10 ! fakesink
  ```

---

### Phase 2: ROS Camera Capture Node
**Duration:** 3-4 hours  
**Risk:** Medium (new node, timing correctness critical)

**Deliverables:**
1. `camera_capture_node.py` - ROS 2 sensor driver for TEVS camera
2. Publishes `/camera/image_raw` (sensor_msgs/Image) with ROS timestamps
3. Blocking capture (CPU-efficient, no polling)
4. Frame rate diagnostics

**Tasks:**
- Create `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py`
- Use OpenCV `cv2.VideoCapture('/dev/video0')` with **blocking read** (not timer polling)
- Assign ROS timestamp immediately: `msg.header.stamp = self.get_clock().now().to_msg()`
- Publish to `/camera/image_raw` using `sensor_msgs/Image`
- Add `/camera/fps` diagnostic (std_msgs/Float32)
- Handle camera disconnect gracefully (retry logic)

**Implementation Pattern:**
```python
class CameraCaptureNode(Node):
    def __init__(self):
        super().__init__('camera_capture_node')
        self.cap = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)
        # Start capture thread (blocking reads)
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        
    def _capture_loop(self):
        """Blocking capture loop - camera driver handles timing"""
        while rclpy.ok():
            ret, frame = self.cap.read()  # Blocks until frame ready
            if not ret:
                self.get_logger().warn('Frame capture failed, retrying...')
                time.sleep(0.1)
                continue
            
            msg = self.bridge.cv2_to_imgmsg(frame, 'bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()  # CRITICAL
            msg.header.frame_id = 'camera'
            self.pub.publish(msg)
```

**Why Blocking Read:**
- Camera driver blocks until frame ready (hardware-timed)
- No CPU wasted on empty polls
- Natural rate limiting at camera framerate
- Simpler code, fewer edge cases

**Acceptance Criteria:**
- Node publishes at 30-58 Hz to `/camera/image_raw`
- Timestamps are ROS clock, monotonically increasing
- CPU usage < 5% (blocking wait, not polling)
- No memory leaks over 5-minute run

---

### Phase 3: Container Frame Ingestion from ROS
**Duration:** 1 day (6-8 hours)  
**Risk:** High (GStreamer appsrc integration, ZMQ serialization)

**Current State:** Container reads video files via `filesrc`  
**Target State:** Container receives frames from ROS via ZMQ

**Deliverables:**
1. Modify `inference_client_node.py` to send frames via ZMQ
2. Modify container `detection_zmq.py` to receive frames via ZMQ + `appsrc`
3. Efficient frame serialization (raw bytes, not base64)
4. Maintain backward compatibility with video file mode

**Tasks:**

*ROS Side (`inference_client_node.py`):*
- Subscribe to `/camera/image_raw`
- Resize frame to inference resolution (1920×1080 → 640×640)
- Serialize frame as **raw bytes** (not base64 - see Data Serialization below)
- Send via ZMQ REQ socket: `{"timestamp_ns": ..., "width": 640, "height": 640, "data": <bytes>}`
- Record `t_frame_sent` for network latency measurement
- Receive detections via ZMQ REP socket (or PUB/SUB for async)
- Record `t_frame_received` when detections arrive
- Match received timestamp to original frame
- Publish to `/detections` with latency breakdown

*Container Side (`detection_zmq.py`):*
- Add ZMQ REP server (port 5556) for frame ingestion
- Receive frame: `{"timestamp_ns", "width", "height", "data": bytes}`
- Reconstruct numpy array: `np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)`
- Feed to GStreamer via **`appsrc`** element (not `filesrc` or `v4l2src`)
- Run inference: `appsrc → videoconvert → hailonet → hailofilter`
- Send detections back via ZMQ with original timestamp
- **Remove all V4L2/camera code** from container

**GStreamer Pipeline Change:**
```python
# Old (file/camera source):
filesrc location=video.mp4 ! qtdemux ! h264parse ! avdec_h264 ! ...
# OR
v4l2src device=/dev/video0 ! video/x-raw,format=UYVY ! ...

# New (ROS-provided frames):
appsrc name=source ! video/x-raw,format=RGB,width=640,height=640,framerate=30/1 !
  videoconvert ! hailonet ! hailofilter ! ...
```

**Backward Compatibility:**
- Add env var: `HAILO_FRAME_SOURCE=ros|file`
- If `file`: use existing `filesrc` pipeline (for regression tests)
- If `ros`: use new `appsrc` pipeline (for live camera)

**Acceptance Criteria:**
- Container processes frames from ROS at 20-30 FPS
- Timestamps preserved through pipeline
- End-to-end latency ~40-80ms (measured ROS-side)
- Video file mode still works (backward compat validated)
- **Container never accesses `/dev/video0`** (validated with `lsof`)

---

### Phase 4: End-to-End ROS Integration + Dry-Run Mode
**Duration:** 1 day (6-8 hours)  
**Risk:** Medium (launch file orchestration, dry-run parameter propagation)

**Deliverables:**
1. `live_camera.launch.py` - Launch file for full live camera pipeline
2. **Dry-run mode:** `use_camera:=false` uses video file instead of live camera
3. Updated `first_ros2_slice.launch.py` to support camera mode
4. Integration with existing tracker and target selector nodes
5. Documentation in RUNBOOK.md for both live and dry-run modes

**Tasks:**
- Create `ros2_ws/src/thesis_bringup/launch/live_camera.launch.py` with dry-run support
- Launch sequence (live mode):
  1. `camera_init_node` (blocking until ready)
  2. `camera_capture_node`
  3. Container inference service (via ExecuteProcess or separate terminal)
  4. `inference_client_node`
  5. `tracker_node`
  6. `target_selector_node`
- Launch sequence (dry-run mode):
  1. `video_publisher_node` (publishes `/camera/image_raw` from video file)
  2. Skip camera_init and camera_capture
  3. Same pipeline: inference_client → tracker → target_selector
- Add launch argument: `use_camera:=true|false` to enable/disable live camera
- Add launch argument: `video_file:=<path>` for dry-run mode video source
- Document startup procedure in RUNBOOK.md (both modes)

**Launch File Structure with Dry-Run:**
```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node

def generate_launch_description():
    use_camera = LaunchConfiguration('use_camera')
    video_file = LaunchConfiguration('video_file')
    
    return LaunchDescription([
        # Arguments
        DeclareLaunchArgument('use_camera', default_value='true'),
        DeclareLaunchArgument('video_file', default_value='video.mp4'),
        
        # === LIVE CAMERA PATH (only if use_camera=true) ===
        Node(
            package='thesis_bringup',
            executable='camera_init_node',
            name='camera_init',
            condition=IfCondition(use_camera)
        ),
        Node(
            package='thesis_bringup',
            executable='camera_capture_node',
            name='camera_capture',
            condition=IfCondition(use_camera)
        ),
        
        # === DRY-RUN PATH (only if use_camera=false) ===
        Node(
            package='video_publisher',  # Or custom video replay node
            executable='video_publisher_node',
            name='video_publisher',
            parameters=[{'video_file': video_file, 'loop': True}],
            remappings=[('image', '/camera/image_raw')],
            condition=UnlessCondition(use_camera)
        ),
        
        # === COMMON PIPELINE (both paths) ===
        Node(package='thesis_inference_client', executable='inference_client_node', ...),
        Node(package='thesis_tracker', executable='tracker_node', ...),
        Node(package='thesis_target_selector', executable='target_selector_node', ...)
    ])
```

**Container-Side Dry-Run:**
- Modify `docker-compose.yaml`: add env var `HAILO_FRAME_SOURCE=ros|file`
- If `file`: container uses `filesrc` pipeline (skip ROS frame ingestion)
- If `ros`: container uses `appsrc` pipeline (receive frames from ROS)
- This allows testing inference service without ROS at all

**Acceptance Criteria:**
- **Live mode:** `ros2 launch thesis_bringup live_camera.launch.py` starts camera + full pipeline
- **Dry-run mode:** `ros2 launch ... use_camera:=false video_file:=test.mp4` runs without camera
- All nodes start successfully and remain active
- Topics publish at expected rates (check with `ros2 topic hz`)
- System stable for 2-minute run (no crashes, no memory growth)
- Dry-run mode useful for CI/CD, debugging, development on non-Pi machines

---

### Phase 5: End-to-End Validation
**Duration:** 1 day (6-8 hours)  
**Risk:** Medium (integration issues may surface, debugging ZMQ/GStreamer)

**Deliverables:**
1. Validated live camera pipeline with all nodes active
2. Recorded rosbag demonstrating successful operation
3. Initial latency measurements (p50, p95, p99)

**Test Sequence:**

**Test 1: Camera-Only Validation**
```bash
# Terminal 1: Init camera
ros2 run thesis_bringup camera_init_node

# Terminal 2: Capture frames
ros2 run thesis_bringup camera_capture_node

# Terminal 3: Check output
ros2 topic hz /camera/image_raw
ros2 topic echo /camera/fps
```
Expected: 30-58 Hz frame rate, clean images

**Test 2: Inference Integration**
```bash
# Terminal 1: Start container inference service
docker exec -it pi-ai-kit-ubuntu-hailo-ubuntu-pi-1 bash -lc '
  cd /root/thesis_service && ./run_detection_zmq.sh
'

# Terminal 2: Full ROS pipeline
ros2 launch thesis_bringup live_camera.launch.py

# Terminal 3: Verify detection rate
ros2 topic hz /detections /tracks
ros2 topic echo /timing --once
```
Expected: 15-30 Hz detections, latency ~40-80ms

**Test 3: Bag Recording**
```bash
cd ~/Desktop/Thesis-Code/bags/raw
timeout 60s ros2 bag record --storage mcap \
  /detections /timing /tracks /target /timing_tracker /camera/fps

mv rosbag2_* 2026-03-08__slice__camera_integration_test
ros2 bag info 2026-03-08__slice__camera_integration_test
```
Expected: All topics recorded, 60 seconds of data, ~900-1800 frames

**Test 4: Offline Latency Analysis**
```bash
cd ~/Desktop/Thesis-Code
python3 tools/analyse_bag_timing.py \
  bags/raw/2026-03-08__slice__camera_integration_test
```
Expected:
- FPS: 15-30 sustained
- Latency p50: 40-60ms
- Latency p95: 80-150ms (under 200ms target ✓)
- No unbounded growth

**Test 5: Stress Test (10 Minutes)**
```bash
timeout 600s ros2 bag record --storage mcap \
  /detections /timing /tracks /camera/fps

# Analyze for long-run stability
python3 tools/analyse_bag_timing.py bags/.../long_run_test
```
Expected:
- FPS variance < 10%
- No memory leaks (check `htop` during run)
- No CPU throttling (check temps)

**Acceptance Criteria:**
- All 5 tests pass
- Latency p95 < 200ms achieved
- System stable for ≥10 minutes
- Rosbag analysis tools work correctly with live camera data

---

### Phase 6: Performance Evaluation
**Duration:** 4-6 hours  
**Risk:** Low (data collection and analysis, but expect friction in rosbag tools)

**Deliverables:**
1. Performance report: FPS, latency distributions, resource utilization
2. Comparison: live camera vs. video file replay (verify no regression)
3. Identification of bottlenecks and optimization opportunities

**Measurement Protocol:**

**Metric 1: Frame Rate**
```bash
ros2 topic hz /camera/image_raw /detections /tracks --window 100
```
Record: Mean, std dev, min, max for each topic

**Metric 2: Latency Distribution**
```bash
# From recorded bag
python3 tools/analyse_bag_timing.py <bag_path>
```
Extract: p50, p95, p99, mean, max

**Metric 3: Component Breakdown**
From `/timing` messages, compute:
- Inference latency histogram
- Tracker latency histogram
- Inter-frame delay (jitter)

**Metric 4: Resource Utilization**
```bash
# During live recording
htop  # CPU usage per node
nvidia-smi # (if GPU used for preprocessing, future)
docker stats  # Container CPU/memory
cat /sys/class/thermal/thermal_zone0/temp  # CPU temp
```

**Comparison Test:**
Run same perception pipeline with:
1. Live camera (this integration)
2. Video file replay (existing baseline)

Verify: Latency distributions are similar (±10%), validates timing integrity

**Acceptance Criteria:**
- FPS sustained ≥15 Hz (target met ✓)
- Latency p95 < 200ms (target met ✓)
- Stretch: p95 < 100ms (bonus if achieved)
- No significant regression vs. video file baseline

---

## Performance Targets

Summary of thesis requirements and validated camera capability:

| Requirement | Thesis Target | Camera Capability | System Expected | Status |
|-------------|---------------|-------------------|-----------------|--------|
| Sustained FPS | ≥15 Hz (min: 10 Hz) | 58.4 Hz | 20-30 Hz | ✅ Exceeds |
| Latency p95 | ≤200 ms (stretch: ≤100 ms) | 17ms capture | 80-120ms | ✅ Achievable |
| Frame timing consistency | - | ±6.6ms std dev | Acceptable | ✅ Good |
| Long-run stability | No growth over 5 min | - | Validated in Phase 5 | ⏳ TBD |

**Key Insight:** Camera is not the bottleneck. Inference (Hailo) and tracking will determine system throughput.

---

## Rollback Plan

If live camera integration fails or introduces blocking issues:

**Immediate Actions:**
1. Keep `first_ros2_slice.launch.py` unchanged (video file mode)
2. Continue thesis work with video datasets (VisDrone, recorded bags)
3. Camera validation scripts remain in `tools/camera/` for hardware verification

**Decision Timeline:**
- **Day 1 (2026-03-08):** Camera validated independently ✅
- **Day 2-3 (2026-03-09/10):** Integration work (Phases 1-5)
- **Decision Point (2026-03-10 EOD):** Integration complete or rollback?
  - If working: Proceed to outdoor validation
  - If blocked: Defer camera integration, focus on tracker deliverables

**Fallback Path:**
1. Complete tracker evaluation (SORT vs ByteTrack vs OC-SORT) using video files
2. Complete embedding integration (Deliverable 1) using video files
3. Complete selective refine (Deliverable 2) using video files
4. Revisit camera integration post-Week 10 if time permits

**Risk Mitigation:**
- Video file pipeline is proven and stable
- All thesis deliverables achievable without live camera  
- Live camera is enhancement, not requirement for degree completion

---

## Appendix A: Node Implementation Skeleton

### camera_init_node.py
See Phase 1 implementation section for complete code.

### camera_capture_node.py (Skeleton)
```python
class CameraCaptureNode(Node):
    def __init__(self):
        self.cap = cv2.VideoCapture('/dev/video0')
        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)
        self.timer = self.create_timer(0.001, self.capture_callback)
    
    def capture_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, 'bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()  # CRITICAL
            self.pub.publish(msg)
```

---

## Appendix B: Quick Reference

### Start Live Pipeline
```bash
ros2 launch thesis_bringup live_camera.launch.py
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

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-08 | 1.0 | Initial plan (container-managed camera approach) |
| 2026-03-08 | 2.0 | **Major revision:** ROS-managed camera architecture |
| | | Added: Data Flow, Timing Model, Failure Modes, Resource Budget |
| | | Restructured: 6 implementation phases (clear separation of concerns) |
| | | Clarified: Camera = ROS sensor, container = inference only |

---

**Document Owner:** Francisco Tavares  
**Reviewer Feedback:** Incorporated (2026-03-08)  
**Status:** Architecture Finalized → Ready for Implementation  
**Next Action:** Begin Phase 1 (Camera Bring-Up)

