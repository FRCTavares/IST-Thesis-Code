# TEVS Camera Integration Plan

**Date:** 2026-03-08  
**Goal:** Integrate TEVS-AR0234 camera as ROS 2 sensor for real-time person perception  
**Status:** Phase 1 & 2 completed, Phase 4 next (tracker + selector integration)

---

## Executive Summary

**Current:**  
Live TEVS camera → ROS inference client → Container inference → Detections is now working end-to-end.

**Phase 1 (Camera bring-up):**
- ✅ `camera_init_node` configures the TEVS media pipeline successfully
- ✅ `camera_capture_node` opens `/dev/video0` and publishes `/camera/image_raw`
- ✅ `/camera/status` publishes ready
- ✅ `/camera/fps` confirms successful live streaming
- ✅ OpenCV/V4L2 capture path works reliably after explicit media graph configuration

**Phase 2 (Inference client integration):**
- ✅ Live inference path is working end-to-end
- ✅ `/detections` publishing at ~16.2 Hz (above 15 Hz minimum target)
- ✅ Real person detection confirmed
- ✅ `/timing` publishing
- ✅ Latency ~127.6 ms (within p95 ≤ 200 ms target envelope)
- ⚠️ Timing instrumentation (`recv_ms`, `json_ms`) needs refinement
- ⚠️ CLI measurement of `/camera/image_raw` not trustworthy for camera rate

**Revised architecture decision remains unchanged:**
- Camera is owned by ROS 2, not by the container
- ROS handles camera init, capture, timestamps and flow control
- Container handles inference only
- `inference_client_node` acts as bounded inference boundary

**Next step:**
- Integrate tracker and target selector on top of live camera detections

**Observed performance:**
- Detection rate: ~16.2 Hz ✅ (target: ≥15 Hz)
- End-to-end latency: ~127.6 ms ✅ (target: p95 ≤ 200 ms)
- Sensor/capture path: ~60 FPS local capability

---

## System Architecture

### Node Responsibilities

**camera_init_node**
- Configures TEVS media graph using `media-ctl`
- Enables the `csi2:4 -> rp1-cfe-csi2_ch0:0` link
- Sets `trigger_mode=0` on `/dev/v4l-subdev2`
- Publishes `/camera/status` = ready
- Runs once at startup, then remains alive

**camera_capture_node**
- Opens `/dev/video0` with OpenCV V4L2 backend
- Captures frames in a blocking dedicated thread
- Assigns ROS timestamps immediately on capture
- Publishes `/camera/image_raw`
- Publishes `/camera/fps`
- Handles reopen on transient capture failure

**inference_client_node**
- ✅ Subscribes to `/camera/image_raw`
- ✅ Resizes and serializes frames to container via ZMQ
- ✅ Receives detections with matched timestamps
- ✅ Publishes `/detections` and `/timing`
- ✅ Bounded queue with latest-frame behavior
- ⚠️ Timing instrumentation needs refinement

**Container inference service**
- ✅ Receives frames from ROS over ZMQ
- ✅ Runs Hailo inference and returns detections
- Container never accesses `/dev/video0`

---

## Phase 1 Outcome ✅ Completed

### What was implemented
- `camera_init_node.py`
- `camera_capture_node.py`

### What had to be fixed during bring-up
- Correct media device is `/dev/media0`
- Correct sensor entity is `tevs 11-0048`
- Correct CSI entity is `csi2`
- Correct capture link is `csi2:4 -> rp1-cfe-csi2_ch0:0`
- `trigger_mode` must be applied on `/dev/v4l-subdev2`, not `/dev/video0`

### Important practical finding
Some `v4l2-ctl` calls on `/dev/video0` were unreliable or blocking on this driver path, specifically:
- `--get-fmt-video`
- `--set-fmt-video`
- stream verification via `v4l2-ctl --stream-mmap`

These should not be used as the primary success criterion in the ROS init node.

### Actual success criterion used
Phase 1 was considered successful because:
- Media graph was configured correctly
- `/camera/status` published ready
- OpenCV capture from `/dev/video0` succeeded
- `camera_capture_node` published frames and FPS diagnostics successfully

---

## Verified Media Graph Configuration

The working configuration is:
- **Sensor entity:** `tevs 11-0048`
- **CSI entity:** `csi2`
- **Video node:** `rp1-cfe-csi2_ch0` as `/dev/video0`
- **Sensor subdevice:** `/dev/v4l-subdev2`

**Working sequence applied by camera_init_node:**
1. Set sensor pad format on `tevs 11-0048:0`
2. Set CSI sink pad format on `csi2:0`
3. Set CSI source pad format on `csi2:4`
4. Enable link `csi2:4 -> rp1-cfe-csi2_ch0:0`
5. Set `trigger_mode=0` on `/dev/v4l-subdev2`

This is now the frozen bring-up recipe.

---

## Observed Phase 1 Performance

### Local capture performance
From `camera_capture_node` logs:
- Initial local capture reached about 60 FPS
- Later values dropped when extra ROS subscribers and CLI tools were added
- This indicates subscriber overhead, not necessarily sensor failure

### ROS topic measurement
`ros2 topic hz /camera/image_raw` reported about 32 FPS

This should be treated carefully:
- It is not the true sensor rate
- It includes heavy ROS transport and subscriber overhead
- It should not replace `/camera/fps` as the main camera-rate indicator

### Practical interpretation
- Sensor path is healthy
- ROS image publication works
- Full-resolution image transport is expensive
- Phase 1 is good enough to proceed

---

## Revised Data Flow

1. ✅ `camera_init_node` configures the TEVS graph and publishes `/camera/status`
2. ✅ `camera_capture_node` reads `/dev/video0`, timestamps frames, publishes `/camera/image_raw`
3. ✅ `inference_client_node` subscribes to `/camera/image_raw`
4. ✅ `inference_client_node` keeps only the latest useful frames and drops stale ones
5. ✅ Frames are resized to inference resolution and sent to the container via ZMQ
6. ✅ Container runs Hailo inference and returns detections
7. ⏳ Detections will feed tracker and target selector **(next phase)**

---

## Revised Timing Interpretation

### Timestamp origin
Still correct:
- `t_capture` originates in ROS at frame acquisition time inside `camera_capture_node`

### Camera-rate truth source
**Use:**
- `/camera/fps`
- Internal node logs

**Do not use:**
- `ros2 topic hz /camera/image_raw` as the authoritative camera-rate metric

### End-to-end design target remains unchanged
- Camera may run faster than inference
- Inference boundary should aggressively prefer latest-frame behaviour
- Stale-frame processing must be avoided

---

## Revised Implementation Phases

### Phase 1 ✅ Completed

**Deliverables achieved:**
- `camera_init_node.py`
- `camera_capture_node.py`
- Verified `/camera/status`
- Verified `/camera/image_raw`
- Verified `/camera/fps`
- Verified real frame capture from `/dev/video0`

---

### Phase 2 ✅ Completed

**Deliverables achieved:**
- Modified `inference_client_node.py` to consume `/camera/image_raw`
- ZMQ frame ingestion working
- Frame serialization (resize + raw bytes)
- `/detections` publishing successfully
- `/timing` publishing successfully
- End-to-end live inference path confirmed

**Performance observed:**
- Detection rate: ~16.2 Hz (above 15 Hz minimum)
- End-to-end latency: ~127.6 ms (inside p95 ≤ 200 ms target)
- Real person detection confirmed working

**Known issues to refine later:**
- Timing fields `recv_ms` and `json_ms` are suspiciously similar (~26.6 ms each)
- Timing instrumentation needs review to ensure accurate measurement
- CLI `/camera/image_raw` Hz measurement not reliable (use `/camera/fps` instead)

**Phase 2 Success Condition met:**
- Live camera → inference client → container → detections working end-to-end
- Performance targets achieved

---

### Phase 3 ⏭️ Deferred

**Container `appsrc` integration** - Skipped for now
- Current container setup is working with frame ingestion
- Will revisit if needed after full pipeline validation

---

### Phase 4 ⏳ Next

**Integrate tracker and target selector on live camera detections:**
- Subscribe to `/camera/image_raw`
- Maintain bounded queue, size 1 or 2
- Oldest-drop policy when busy
- Resize to 640×640
- Serialize as raw bytes
- Send multipart ZMQ messages
- Receive detections with matching timestamp
- Publish `/detections` and `/timing`

---

### Phase 3

**Modify container detection_zmq.py:**
- Add ROS frame ingestion mode
- Use `appsrc`
- Keep file mode for regression testing
- No camera device access in container

---

### Phase 4 ⏳ Next

**Integrate tracker and target selector on live camera detections:**
- Connect `tracker_node` to `/detections`
- Connect `target_selector_node` to `/tracks`
- Verify `/tracks` and `/target` publishing
- Test full perception pipeline: camera → inference → tracking → target selection
- Record rosbag with all topics
- Validate target lock behavior on live person

**Success criteria:**
- `/tracks` publishes successfully
- `/target` publishes successfully
- Target lock maintained on moving person
- Full pipeline runs stable for 5+ minutes

---

### Phase 5

**End-to-end validation:**
- Live camera to detections
- Rosbag recording
- Latency analysis
- Long-run stability

---

### Phase 6

**Performance evaluation:**
- FPS
- Latency percentiles
- Bottleneck identification
- Live camera vs video replay comparison

---

## Revised Failure Modes

**Mode 1: Camera graph not enabled after boot**
- **Symptom:** No frames from `/dev/video0`
- **Recovery:** Rerun `camera_init_node`
- **Root cause:** Media graph and capture link must be explicitly configured

**Mode 2: Capture node opens but no frames arrive**
- **Symptom:** `cap.read()` fails
- **Recovery:** Verify media graph, verify trigger mode on `/dev/v4l-subdev2`, reopen camera
- **Note:** This was solved by enabling the correct CSI-to-video link

**Mode 3: ROS image topic appears slower than sensor**
- **Symptom:** `ros2 topic hz /camera/image_raw` lower than `/camera/fps`
- **Explanation:** Subscriber and transport overhead
- **Action:** Trust `/camera/fps` for sensor-side measurement

**Mode 4: Inference backlog**
- **Expected in next phase**
- **Recovery strategy:** Bounded latest-frame queue in `inference_client_node`

---

## Revised Quick Reference

### Start camera bring-up
```bash
ros2 run thesis_bringup camera_init_node
```

### Start camera capture
```bash
ros2 run thesis_bringup camera_capture_node
```

### Start inference client
```bash
ros2 run thesis_bringup inference_client_node
```

### Check camera status
```bash
ros2 topic echo /camera/status --once
```

### Check camera FPS
```bash
ros2 topic echo /camera/fps
```

### Check detections
```bash
ros2 topic echo /detections --once
ros2 topic hz /detections
```

### Check timing
```bash
ros2 topic echo /timing --once
```

### Check image topic (not reliable for true camera rate)
```bash
ros2 topic hz /camera/image_raw
```

### Real health checks
- `/camera/status`
- `/camera/fps`
- `/detections` Hz
- `/timing` values
- Successful OpenCV capture

### Avoid relying on
- `v4l2-ctl --get-fmt-video`
- `v4l2-ctl --set-fmt-video`
- `v4l2-ctl --stream-mmap` on `/dev/video0`
- `ros2 topic hz /camera/image_raw` as camera rate (subscriber overhead distorts measurement)

---

## Revised Risk Mitigation

**High risk now:**
- ZMQ frame ingestion redesign in `inference_client_node`
- Container `appsrc` integration
- Timestamp preservation across ROS → container → ROS
- End-to-end bounded latency under sustained load

**Medium risk now:**
- Full-resolution ROS image publication overhead
- Colour conversion assumptions between OpenCV and inference preprocessing
- Subscriber overhead distorting naive FPS measurements

**Low risk now:**
- TEVS bring-up itself, because this is now working

---

## Revised Success Criteria

### Already achieved ✅
- Camera initializes reliably via `camera_init_node`
- `/camera/status` publishes ready
- `/camera/image_raw` publishes successfully
- `/camera/fps` publishes successfully
- `/dev/video0` capture works through ROS node
- **Live inference path working end-to-end**
- **`/detections` publishing at 16.2 Hz (above 15 Hz target)**
- **`/timing` publishing successfully**
- **End-to-end latency ~127.6 ms (within 200 ms target)**
- **Real person detection confirmed**

### Still to achieve ⏳
- Tracker integration on `/detections`
- Target selector integration on `/tracks`
- Full pipeline: camera → inference → tracking → target selection
- Stable end-to-end live camera perception stack
- Timing instrumentation refinement

---

## Revised Timeline

**Day 1 (2026-03-08):**
- ✅ Camera validation done
- ✅ Plan finalized
- ✅ Phase 1 bring-up completed
- ✅ Phase 2 inference integration completed

**Day 2 (2026-03-09):**
- ⏳ Phase 4: Tracker + selector integration
- ⏳ Phase 5: End-to-end validation
- ⏳ Timing instrumentation refinement

**Day 3 (2026-03-10):**
- ⏳ Phase 6: Performance evaluation
- ⏳ Long-run stability testing

---

## Status Summary

**Phase 1:** ✅ Complete (Camera bring-up)  
**Phase 2:** ✅ Complete (Inference integration)  
**Phase 3:** ⏭️ Deferred (Container `appsrc`)  
**Phase 4:** ⏳ **Next** (Tracker + selector integration)  

**Next action:** Integrate `tracker_node` and `target_selector_node` on top of live camera detections

**Performance so far:**
- Detection rate: 16.2 Hz ✅
- End-to-end latency: ~127.6 ms ✅
- Above minimum targets, ready for full pipeline integration

---

**Document Owner:** Francisco Tavares  
**Last Updated:** 2026-03-08  
**Status:** Phase 1 & 2 Complete, Phase 4 Next
