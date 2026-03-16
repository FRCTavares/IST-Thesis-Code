# Weekly Summary — W10 (2026-03-03 to 2026-03-09)

> Note (updated 2026-03-16): This file is a historical weekly record. Some commands and node names here reflect the integration state at that time (for example, explicit `camera_init_node` references). For current operations, use `RUNBOOK.md` and `tools/start_live_stack.sh` as the source of truth.

## Week 10 Ambition Targets (by end of Mar 9)

Move from "baseline working" to "demo-ready system with frozen configuration."

By end of Day 09 (March 9), you should have:

1. **One chosen baseline tracker** (decision locked) + 1 strong backup
   - Baseline tracker frozen with locked parameters
   - Backup tracker validated and documented

2. **Target selection logic upgraded** to handle multi-person scenes robustly
   - Not just "time alive only"
   - Explicit state machine: SEARCH → LOCKED → LOST → REACQUIRED
   - Score function using multiple features (time_alive, freshness, distance, motion, appearance)

3. **Outdoor test protocol ready** (even if no camera yet)
   - Scripted runs with checklists
   - Clear success criteria
   - Executable protocol like a flight test

4. **Embedding v1 running end-to-end** (even if simple)
   - Quantified benefit or clear failure reason
   - Appearance term in association cost

5. **Control interface demo**
   - 30 Hz control_ref stable
   - Loss handling and reacquisition events
   - Prediction with confidence clamping

**System requirements:**
- Outdoor tennis court target environment
- Full online processing
- 15 FPS perception, 30 Hz control
- Latency budget: 200 ms max
- Multi-person robustness

---

## Goals for the week
- [ ] Lock baseline tracker decision with justification
- [ ] Standardize evaluation suite (single command → full report)
- [ ] Upgrade target selector with state machine and multi-feature scoring
- [ ] Implement embedding v1 end-to-end with measurable impact
- [ ] Write outdoor test protocol (flight-test style)
- [ ] Tighten control interface with loss/reacquisition handling
- [ ] Integrate tracker timing into full latency breakdown
- [ ] Freeze Phase 1 baseline and define camera integration plan

---

## Daily Goals Summary

### Days 03-07: Planning and Preparation
**Outcome:** Week redirected to camera integration planning based on hardware availability.

**Key activities:**
- TEVS-AR0234 camera hardware testing and validation
- Media graph investigation and troubleshooting
- Architecture design for camera → ROS → container integration
- Camera Integration Plan document created

### Day 08 (03-08): Live Camera Integration - Complete System Bring-Up ✅
**Outcome:** Camera fully integrated into ROS pipeline, end-to-end live inference working at target performance.

**Key deliverables:**
- ✅ `camera_init_node.py` - Repeatable TEVS media graph configuration
- ✅ `camera_capture_node.py` - Live frame capture publishing to `/camera/image_raw`
- ✅ Modified `inference_client_node.py` - Live ROS frame ingestion and ZMQ transport
- ✅ Modified container `detection_zmq.py` - ROS frame reception via ZMQ
- ✅ Full live pipeline validated: camera → inference → tracker → selector
- ✅ Detection rate: **16.2 Hz** (above 15 Hz target)
- ✅ Latency: **~127.6 ms** (within 200 ms budget)
- ✅ Real person detection confirmed
- ✅ Full-pipeline smoke bag recorded

**Phase completion:**
- Phase 1 (Camera bring-up): ✅ Complete
- Phase 2 (Inference integration): ✅ Complete
- Phase 4 (Tracker + selector): ⏳ Connected, metadata propagation needs fixing

---

## What shipped (bulletproof facts)

**Week outcome:** Camera integration complete - thesis moved from file-based simulation to live camera perception.

**Major integration achieved on Day 08:**

1. **TEVS Camera Bring-Up (Phase 1 Complete)**
   - `camera_init_node.py` - Repeatable media graph configuration
   - `camera_capture_node.py` - Live frame capture at ~60 FPS local
   - Frozen working configuration:
     - Sensor entity: `tevs 11-0048`
     - CSI entity: `csi2`
     - Working link: `csi2:4 -> rp1-cfe-csi2_ch0:0`
     - Trigger mode: `/dev/v4l-subdev2`
   - Topics: `/camera/image_raw`, `/camera/status`, `/camera/fps`

2. **Live Inference Integration (Phase 2 Complete)**
   - `inference_client_node.py` - ROS image subscription → ZMQ frame transport
   - Container `detection_zmq.py` - ROS frame ingestion via ZMQ REQ/REP
   - End-to-end path working: camera → ROS → container → detections
   - Detection rate: **16.2 Hz** ✅ (above 15 Hz minimum)
   - Latency: **~127.6 ms** ✅ (within 200 ms budget)
   - Real person detection confirmed

3. **Full Pipeline Connected (Phase 4 Partial)**
   - Tracker and selector connected to live detections
   - Topics publishing: `/detections`, `/timing`, `/tracks`, `/target`
   - Full-pipeline bag recorded: `2026-03-08__camera_full_pipeline_smoke`
   - Known issue: metadata propagation (score, header) needs fixing

**Critical findings:**
- V4L2 standard checks unreliable on this driver path
- ROS topic Hz measurements not trustworthy for camera rate (use `/camera/fps`)
- Container environment setup critical (Hailo venv, postprocess function)
- CLI subscriber overhead affects throughput measurement

**Status:**
- Live camera perception stack: ✅ Working
- Performance targets: ✅ Met
- Metadata propagation: ⚠️ Needs cleanup
- Full-pipeline sustained rate: ⏳ Needs validation without observer overhead

---

## Numbers

**Live camera integration performance (Day 08):**

**Camera capture:**
- Local capture: ~60 FPS (from node logs)
- With CLI subscribers: 30-40 FPS (subscriber overhead)
- Truth source: `/camera/fps` (not `ros2 topic hz`)

**Live inference performance:**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Detection rate | 16.2 Hz | ≥15 Hz | ✅ |
| End-to-end latency (live) | ~127.6 ms | p95 ≤ 200 ms | ✅ |
| Real person detection | Confirmed | — | ✅ |

**Timing breakdown from smoke bag:**

From `/timing` (214 messages, 28.49s duration):

| Field | Mean | p50 | p95 | p99 | Max |
|-------|------|-----|-----|-----|-----|
| lat_ms | 67.11 | 63.92 | 98.36 | 124.24 | 140.85 |
| recv_ms | 16.00 | — | — | — | — |
| json_ms | 15.99 | — | — | — | — |
| loop_ms | 35.76 | — | 48.76 | 64.10 | — |
| pub_dt_ms | 135.62 | 146.49 | 208.50 | — | — |

**Note:** `recv_ms` and `json_ms` suspiciously similar, instrumentation needs review.

**Full-pipeline bag (`2026-03-08__camera_full_pipeline_smoke`):**

| Topic | Message count | Notes |
|-------|--------------|-------|
| /detections | 214 | Live camera detections |
| /timing | 214 | Inference timing |
| /tracks | 214 | Tracker output |
| /timing_tracker | 214 | Tracker timing |
| /target | 214 | Target selection |

**Full-pipeline achieved rate:** ~7.5 Hz (bag analysis)  
**Note:** Likely affected by CLI observation overhead during recording.

**Baseline tracker performance:**
- Not evaluated this week (camera integration priority)
- Deferred to Week 11

**Target selector upgrade:**
- Not implemented this week (camera integration priority)
- Deferred to Week 11

**Embedding v1 impact:**
- Not implemented this week (camera integration priority)
- Deferred to Week 11

---

## Frozen Baseline (Live Camera Integration)

**Camera Integration: Phase 1 & 2 Complete**

### Camera Bring-Up (Phase 1)
- **Init node:** `camera_init_node.py`
- **Capture node:** `camera_capture_node.py`
- **Media configuration:** Frozen recipe documented in Camera Integration Plan
- **Key entities:**
  - Sensor: `tevs 11-0048`
  - CSI: `csi2`
  - Link: `csi2:4 -> rp1-cfe-csi2_ch0:0`
  - Trigger: `/dev/v4l-subdev2`
- **Topics:** `/camera/image_raw`, `/camera/status`, `/camera/fps`
- **Performance:** ~60 FPS local capture

### Inference Integration (Phase 2)
- **Node:** `inference_client_node.py` (modified for live ROS frames)
- **Container:** `detection_zmq.py` (ROS frame ingestion mode)
- **Transport:** ZMQ REQ/REP on `127.0.0.1:5556`
- **Frame format:** 640×640, raw bytes (not base64)
- **Topics:** `/detections`, `/timing`
- **Performance:**
  - Detection rate: 16.2 Hz (above 15 Hz target)
  - Latency: ~127.6 ms (within 200 ms budget)

### Tracker & Selector (Phase 4 - Partial)
- **Status:** Connected to live detections, publishing topics
- **Known issues:**
  - Metadata propagation (score, header)
  - Full-pipeline sustained rate needs clean validation
- **Next:** Fix metadata, validate sustained performance

### Deferred to Week 11:
- Baseline tracker decision (OC-SORT vs ByteTrack)
- Target selector upgrade (multi-feature scoring, state machine)
- Embedding v1 integration
- Control interface tightening
- Outdoor test protocol

---

## Camera Integration Outcome

**What was achieved:**
- Live TEVS camera fully integrated as ROS sensor
- Container receives frames from ROS (not direct camera access)
- End-to-end perception pipeline working: camera → inference → tracker → selector
- Performance targets met on live system
- Reproducible bring-up procedure documented

**What changed from original Week 10 plan:**
- Camera became available ahead of schedule
- Week redirected to camera integration (originally planned for Week 11)
- Tracker evaluation and target selector upgrades deferred
- Camera integration completed 1 week ahead of schedule

**Risk mitigation:**
- TEVS driver path more fragile than expected (resolved)
- V4L2 standard checks unreliable (workaround documented)
- Container environment setup critical (frozen configuration)
- Measurement overhead affects observed performance (documented)

**Technical debt:**
- Timing instrumentation refinement (recv_ms, json_ms)
- Metadata propagation (score, header fields)
- Sustained full-pipeline rate validation

---

## Issues / risks

### Resolved this week:
1. **TEVS media graph fragility** - Exact entity configuration critical, now documented
2. **V4L2 command reliability** - Standard checks unreliable, workaround found
3. **Container environment setup** - Hailo venv and config requirements identified
4. **Camera ownership** - ROS now owns camera, container receives frames via ZMQ

### Active issues:
1. **Metadata propagation** - Track score and target header not propagating correctly
2. **Timing instrumentation** - `recv_ms` and `json_ms` suspiciously similar, needs review
3. **Full-pipeline rate** - Bag analysis shows 7.5 Hz, likely observer overhead
4. **CLI measurement reliability** - Subscriber overhead distorts naive Hz measurements

### Known limitations:
1. **Container launcher** - Not yet wrapped in single robust startup script
2. **Baseline not frozen** - Tracker, selector, embedding work deferred to Week 11
3. **Outdoor testing** - Protocol not yet written, deferred with other work

### Week 11 risks:
1. **Metadata fixes** - May reveal deeper architectural issues
2. **Sustained rate validation** - Needs clean measurement without observer overhead
3. **Outdoor conditions** - Exposure, lighting, motion blur unknown until tested
4. **Calibration** - Camera intrinsics and mounting geometry not yet measured

---

## Next week plan (Week 11)

**Week 11 focus:** Clean up live camera pipeline and prepare for outdoor testing

### Immediate priorities (Day 09-10):

**A) Fix pipeline metadata and validation**
- [ ] Fix tracker score propagation
- [ ] Fix target selector header propagation
- [ ] Re-run full pipeline without CLI observation overhead
- [ ] Record clean full-pipeline bag
- [ ] Validate sustained detection rate ≥15 Hz

**B) Refine timing instrumentation**
- [ ] Review `recv_ms` and `json_ms` measurement logic
- [ ] Ensure timing fields accurately represent what they claim
- [ ] Update timing analysis with corrected instrumentation
- [ ] Freeze timing baseline for outdoor comparison

### Mid-week (Day 11-13):

**C) Baseline tracker decision and freeze**
- [ ] Run evaluation suite on live camera data
- [ ] Lock baseline tracker (OC-SORT or ByteTrack)
- [ ] Document frozen configuration

**D) Camera calibration**
- [ ] Measure camera intrinsics
- [ ] Characterize distortion
- [ ] Document mounting geometry
- [ ] Test outdoor exposure and lighting

### Late week (Day 14-15):

**E) Outdoor test protocol**
- [ ] Write tennis court test scenarios
- [ ] Define success criteria with numbers
- [ ] Create pre-flight checklist
- [ ] Conduct first outdoor runs with frozen baseline

**F) Target selector upgrade (if time permits)**
- [ ] Implement multi-feature score function
- [ ] Add state machine (SEARCH → LOCKED → LOST → REACQUIRED)
- [ ] Measure improvement on live data

### Deferred to Week 12 (if not completed):
- Embedding v1 integration
- Control interface tightening (30 Hz, loss handling)
- Long-run stability testing (10+ minutes)
- Appearance-based association

---

## Links
- Week index: `index.md`
- Artefacts: `artefacts.md`
- Previous week: `../W09_2026-02-24_to_03-02/weekly.md`
