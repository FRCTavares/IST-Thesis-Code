# Daily Log — 2026-03-01 — Make Occlusion and Ambiguity a First-Class Test (Week 9, Day 6)

## Goal
Make occlusion and ambiguity a first-class test. By end of day, you have repeatable occlusion tests that stress identity consistency and you can quantify.

**Target outcome:**
- Occlusion injection working with two modes: (1) periodic blackout, (2) target-centric occlusion (drop detections near last known target bbox)
- Ambiguity test implemented (not just defined): synthetic "two-person crossing" generated from detections and replayed through at least 2 trackers
- Extended metrics: reacquisition time distribution, switches per minute, time locked percentage
- Results for at least 2 trackers showing which handles occlusion/ambiguity better

**This is where you stop "it works in clean scenes" and make it credible.**

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay and synthetic occlusion. Camera integration scheduled once hardware arrives. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court (occlusion from net, multiple people) |
| Perception target | 15 FPS |
| Control target | 30 Hz with prediction |
| Latency budget | 200 ms max |
| Test focus | Occlusion resilience, identity consistency |

---

## Work Plan

### A) Occlusion injection (no camera needed)
During replay, inject synthetic occlusion by dropping or masking detections.

- [ ] Create ROS2 node `detections_occluder_node.py`:
  - Subscribes to `/detections`
  - Republishes to `/detections_occluded` with controlled drops
  - Configurable occlusion patterns:
    - **Periodic blackout:** drop all detections for `drop_s` every `period_s` (repeatable stress test)
    - **Target-centric occlusion:** subscribe to `/target` and drop detections whose centre lies within `gate_px` of last target centre for `occlusion_duration_s`
    - **(Stretch) ROI net occlusion:** fixed ROI rectangle that masks detections (simulate tennis net zone)
- [ ] Add parameter configuration:
  - `mode`: 'periodic_blackout' | 'target_centric' | 'fixed_roi'
  - `period_s`: 3.0
  - `drop_s`: 0.5
  - `occlusion_duration_s`: 1.0
  - `gate_px`: 60
  - `roi_xyxy`: [x1,y1,x2,y2] (only for fixed_roi)
- [ ] Test with evaluation launch: tracker runs on `/detections_occluded`
- [ ] Tracker subscribes to `/detections_occluded` via ROS remap (no tracker code change)
- **Deliverable:** `ros2_ws/src/thesis_bringup/nodes/detections_occluder_node.py` (and launch wires it into replay)
- Notes: *(fill)*

**Implementation approach:**
```python
# Pseudocode
class OccluderNode:
    def __init__(self):
        self.sub = self.create_subscription('/detections', self.callback)
        self.pub = self.create_publisher('/detections_occluded')
        self.occlusion_active = False
        self.occlusion_start_time = None
    
    def callback(self, msg):
        if self.should_occlude(msg):
            # Drop or mask target detection
            filtered_msg = self.filter_detections(msg)
            self.pub.publish(filtered_msg)
        else:
            self.pub.publish(msg)
```

### B) Ambiguity test
When 2 persons close, association becomes ambiguous.

- [ ] Implement synthetic crossing generator (no video needed):
  - Take two real detections tracks (or pick two bboxes per frame from the bag)
  - Apply deterministic offsets so they cross in image space over T seconds
  - Output `/detections_ambiguous`
- [ ] Run `eval_replay` with tracker subscribed to `/detections_ambiguous`
- [ ] Compare at least OC-SORT vs SORT (ByteTrack optional)
- [ ] Log ID switches and track consistency
- **Deliverable:** `ros2_ws/src/thesis_bringup/nodes/detections_ambiguity_node.py` + one documented run command
- Notes: *(fill)*

**Test scenario definition:**
- *(Fill after implementation)*
- Duration: 10.0 s window inside the bag (repeatable)
- Number of persons: 2
- Minimum inter-person distance: ≤ 20 px at closest approach
- Expected challenge: IoU ambiguity during crossing, identity swap risk

### C) Extended metrics
Extend tracking analysis beyond basic stats.

- [ ] Reacquisition time distribution:
  - After each occlusion event, measure time until target reacquired
  - Plot histogram of reacquisition times
- [ ] Switches per minute:
  - Count number of target switches (proxy for ID switches)
  - Normalize by active tracking time
- [ ] "Time locked" percentage:
  - Percentage of time with valid target lock (no `target_lost` events)
  - Higher is better for control stability
- [ ] Total lost time (s) and time locked % in summary
- [ ] Switches per minute computed as switches / (duration_s/60)
- [ ] Update `analyse_bag_tracking.py` or create separate occlusion analysis script
- **Deliverable:** `reports/tracking/<eval>/summary.md` includes `time_locked_pct` + `switches_per_min` + reacq hist plot
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] `.../detections_occluder_node.py` working (2 modes minimum)
- [ ] `.../detections_ambiguity_node.py` working (synthetic crossing)
- [ ] `analyse_bag_tracking.py` extended metrics implemented
- [ ] Results for 2 trackers on both tests (occlusion + ambiguity)

### Occlusion test parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| Blackout period | 3.0 s | periodic_blackout |
| Blackout drop | 0.5 s | periodic_blackout |
| Target-centric gate | 60 px | target_centric |
| Occlusion duration | 1.0 s | target_centric |
| Test bag | 2026-02-28__slice__smoke2 | baseline |
| Trackers tested | SORT, OC-SORT | minimum |

### Results: Occlusion resilience

| Tracker | track_ms p95 (ms) | switches/min | time locked (%) | reacq p50 (s) | reacq p95 (s) |
|---------|-------------------|--------------|-----------------|---------------|---------------|
| SORT | — | — | — | — | — |
| OC-SORT | — | — | — | — | — |

**Visualizations:**
- *(Reference to plots generated)*

### Clear conclusion: Which is better and why
*(Fill after analysis)*

**Rationale:**
- *(Consider: reacquisition speed, ID consistency, computational cost)*
- *(Match to outdoor tennis court requirements: net occlusion, player crossing)*
- *(Recommendation for baseline tracker moving forward)*

---

## Issues / Risks
- *(Fill as they arise)*
- Synthetic tests are deterministic and repeatable, but do not fully capture real appearance-driven ID ambiguity, ReID will be evaluated once embeddings are available.

**Known challenges:**
- Synthetic occlusion may not perfectly represent real-world scenarios
- Limited diversity in current bags (no real multi-person crossing yet)
- Need for VisDrone or similar dataset integration if synthetic insufficient

---

## Next steps (Day 02, March 2)
- [ ] Implement 30 Hz prediction node (control interface stub)
- [ ] Define controller inputs clearly (ex, ey, ez in pixels, target_valid flag)
- [ ] Add appearance embedding hook to association logic (placeholder: colour histogram + gradient)
- [ ] Demonstrate `/control_ref` stable at 30 Hz in bag

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Occlusion plots: *(fill after generation)*
