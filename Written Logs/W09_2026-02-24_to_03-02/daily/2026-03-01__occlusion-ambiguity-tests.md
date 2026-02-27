# Daily Log — 2026-03-01 — Make Occlusion and Ambiguity a First-Class Test (Week 9, Day 6)

## Goal
Make occlusion and ambiguity a first-class test. By end of day, you have repeatable occlusion tests that stress identity consistency and you can quantify.

**Target outcome:**
- Synthetic occlusion injection working (drop target detections for controlled periods)
- Ambiguity test scenario defined (close persons, crossing paths)
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
    - **Fixed duration:** Drop all detections for target for exactly 1.0 s
    - **Overlap-based:** Mask detections when overlap > threshold (simulate person walking in front)
- [ ] Add parameter configuration:
  - `occlusion_mode`: 'fixed_duration' | 'overlap_threshold'
  - `occlusion_duration_s`: 1.0 (default)
  - `overlap_threshold`: 0.7 (default, for IoU-based masking)
- [ ] Test with evaluation launch: tracker runs on `/detections_occluded`
- **Deliverable:** `thesis_tools/detections_occluder_node.py`
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

- [ ] Define ambiguity scenario:
  - **Option 1:** Select a known MOT clip from VisDrone or similar dataset with crossing persons
  - **Option 2:** Create synthetic crossing using existing detections (translate bboxes to simulate)
  - **Option 3:** Use multi-person bag segment where persons come close (if available)
- [ ] Choose most practical option for today
- [ ] Run test scenario through at least 2 trackers
- [ ] Log ID switches and track consistency
- **Deliverable:** At least one repeatable run scenario documented
- Notes: *(fill)*

**Test scenario definition:**
- *(Fill after implementation)*
- Duration: *(fill)* s
- Number of persons: *(fill)*
- Minimum inter-person distance: *(fill)* pixels
- Expected challenge: *(describe what makes this hard)*

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
- [ ] Update `analyse_bag_tracking.py` or create separate occlusion analysis script
- **Deliverable:** Plots or tables in report
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] `thesis_tools/detections_occluder_node.py` — synthetic occlusion injection node
- [ ] Ambiguity test scenario defined and documented
- [ ] Extended metrics implemented and plotted
- [ ] Occlusion test results for at least 2 trackers

### Occlusion test parameters
| Parameter | Value | Notes |
|-----------|-------|-------|
| Occlusion duration | 1.0 s | Standard tennis court scenario |
| Occlusion mode | *(fill)* | fixed_duration / overlap |
| Test bag | *(fill)* | |
| Trackers tested | *(fill)* | e.g., SORT, OC-SORT |

### Results: Occlusion resilience

| Tracker | Reacquisition time p50 (s) | Reacquisition time p95 (s) | Switches per minute | Time locked (%) |
|---------|---------------------------|---------------------------|---------------------|-----------------|
| SORT | — | — | — | — |
| OC-SORT | — | — | — | — |
| Tracker #3 | — | — | — | — |

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
