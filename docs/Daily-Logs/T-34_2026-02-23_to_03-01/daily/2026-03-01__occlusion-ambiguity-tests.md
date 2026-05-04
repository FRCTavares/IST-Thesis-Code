# Daily Log — 2026-03-01 — Make Occlusion and Ambiguity a First-Class Test (T-34, Day 6)

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

- [x] Create ROS2 node `detections_occluder_node.py`:
  - Subscribes to `/detections`
  - Republishes to `/detections_occluded` with controlled drops
  - Configurable occlusion patterns:
    - **Periodic blackout:** drop all detections for `drop_s` every `period_s` (repeatable stress test)
    - **Target-centric occlusion:** subscribe to `/target` and drop detections whose centre lies within `gate_px` of last target centre for `occlusion_duration_s`
    - **(Stretch) ROI net occlusion:** fixed ROI rectangle that masks detections (simulate tennis net zone)
- [x] Add parameter configuration:
  - `mode`: 'periodic_blackout' | 'target_centric' | 'fixed_roi'
  - `period_s`: 3.0
  - `drop_s`: 0.5 (used as occlusion duration)
  - `gate_px`: 60
  - `roi_xyxy`: [x1,y1,x2,y2] (only for fixed_roi)
- [x] Test with evaluation launch: tracker runs on `/detections_occluded`
- [x] Tracker subscribes to `/detections_occluded` via ROS remap (no tracker code change)
- **Deliverable:** `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/detections_occluder_node.py` (and launch wires it into replay)
- Notes: See deliverables and results below

**Deliverables:**
- `thesis_bringup/nodes/detections_occluder_node.py` (modes: periodic_blackout, target_centric, fixed_roi)
- `launch/eval_replay_occluded.launch.py`

**Notes:**
- Raw bag: `2026-02-28__slice__smoke2`
- Eval runs created:
  - `...__sort__occl_pb_3_0.5`
  - `...__ocsort__occl_pb_3_0.5`
  - `...__sort__occl_tc_3_0.5_g60`
  - `...__ocsort__occl_tc_3_0.5_g60`
- Key finding: OC-SORT tail latency explodes under occlusion (p95 11.35 to 22.82 ms) vs SORT (p95 1.05 to 1.40 ms)

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

- [x] Implement synthetic crossing generator (no video needed):
  - Take two real detections tracks (or pick two bboxes per frame from the bag)
  - Apply deterministic offsets so they cross in image space over T seconds
  - Output `/detections_ambiguous`
- [x] Run `eval_replay` with tracker subscribed to `/detections_ambiguous`
- [x] Compare at least OC-SORT vs SORT (ByteTrack optional)
- [x] Log ID switches and track consistency
- **Deliverable:** See below
- Notes: See results section

**Deliverables:**
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/detections_ambiguity_node.py`
- `ros2_ws/src/thesis_bringup/launch/eval_replay_ambiguous.launch.py`

**Command:**
```bash
timeout -s SIGINT 75s ros2 launch thesis_bringup eval_replay_ambiguous.launch.py \
  bag:="$THESIS_ROOT/artifacts/bags/raw/2026-02-28__slice__smoke2" tracker:=sort window_start_s:=5.0 window_len_s:=10.0 swap_y:=false
```

**Test scenario definition:**
- start=5 s, len=10 s, swap_y=false, top-2 detections by score, smooth x-centre swap (forced crossing)
- Duration: 10.0 s window inside the bag (repeatable)
- Number of persons: 2
- Expected challenge: IoU ambiguity during crossing, identity swap risk

### C) Extended metrics
Extend tracking analysis beyond basic stats.

- [x] Reacquisition time distribution:
  - After each occlusion event, measure time until target reacquired
  - Plot histogram of reacquisition times
- [x] Switches per minute:
  - Count number of target switches (proxy for ID switches)
  - Normalize by active tracking time
- [x] "Time locked" percentage:
  - Percentage of time with valid target lock (no `target_lost` events)
  - Higher is better for control stability
- [x] Total lost time (s) and time locked % in summary
- [x] Switches per minute computed as switches / (duration_s/60)
- [x] Update `analyse_bag_tracking.py` or create separate occlusion analysis script
- **Deliverable:** `artifacts/reports/tracking/<eval>/summary.md` includes `time_locked_pct` + `switches_per_min` + reacq hist plot ✓
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [x] `.../detections_occluder_node.py` working (2 modes minimum)
- [x] `.../detections_ambiguity_node.py` working (synthetic crossing)
- [x] `analyse_bag_tracking.py` extended metrics implemented (`time_locked_pct`, `total_lost_time`, `switches_per_min`, reacq histogram) ✓
- [x] Results for 2 trackers on both tests (occlusion + ambiguity)

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

#### Periodic Blackout (period=3.0 s, drop=0.5 s)

| Tracker | Lock longest (s) | Reacq events | Reacq p95 (s) | Switches | track_ms p95 (ms) |
|---------|------------------|--------------|---------------|----------|-------------------|
| SORT    |           2.401  |           19 |         0.573 |       33 |             1.399 |
| OC-SORT |           2.407  |           20 |         0.578 |       31 |            11.353 |

#### Target-Centric Occlusion (gate=60 px, occlusion=0.5 s)

| Tracker | Lock longest (s) | Reacq events | Reacq p95 (s) | Switches | track_ms p95 (ms) |
|---------|------------------|--------------|---------------|----------|-------------------|
| SORT    |          55.633  |            0 |             — |       21 |             1.050 |
| OC-SORT |          58.210  |            1 |         0.050 |       21 |            22.819 |

### Results: Ambiguity test (synthetic crossing)

**Test parameters:** start=5 s, len=10 s, swap_y=false, top-2 detections by score, smooth x-centre swap (forced crossing)

| Tracker | Lock longest (s) | Switches | track_ms p95 (ms) |
|---------|------------------|----------|-------------------|
| SORT    |          56.359  |       21 |             5.899 |
| OC-SORT |          56.047  |       19 |             1.270 |

**Visualizations:**
- See occlusion and ambiguity compare reports for plots and summaries

### Clear conclusion: Which is better and why

**Occlusion tests:**
- **SORT wins on compute:** 8-22× better runtime tail under occlusion stress
- **OC-SORT ties on tracking:** Similar or slightly better switch behavior, but runtime cost is prohibitive

**Ambiguity test:**
- **OC-SORT wins on switches:** 19 vs 21 (10% improvement)
- **Runtime acceptable:** Both trackers show reasonable p95 (<6 ms) in crossing scenario

**Rationale:**
- For **flight-control coupling:** SORT is compute-safe baseline (p95 < 2 ms under target-centric occlusion)
- For **identity consistency experiments:** OC-SORT shows promise in ambiguity handling but needs runtime optimization
- **Recommendation:** Use SORT as baseline tracker until ReID embeddings are added; re-evaluate OC-SORT with appearance features. OC-SORT remains the default for offline identity experiments where compute tail is less critical.

---

## Issues / Risks
- Extended metrics (switches/min, time_locked_pct, reacq histogram) deferred to Day 02 — current reports show raw counts only
- Synthetic tests are deterministic and repeatable, but do not fully capture real appearance-driven ID ambiguity, ReID will be evaluated once embeddings are available.

**Known challenges:**
- Synthetic occlusion may not perfectly represent real-world scenarios
- Limited diversity in current bags (no real multi-person crossing yet)
- Need for VisDrone or similar dataset integration if synthetic insufficient

---

## Next steps (Day 02, March 2)
- [x] **Priority:** Implement extended metrics in `analyse_bag_tracking.py` ✓
  - [x] switches/min (normalized by duration)
  - [x] time_locked_pct (percentage of time with valid target)
  - [x] total_lost_time (sum of all lost intervals)
  - [x] reacq histogram plot (distribution of reacquisition times)
- [ ] Implement 30 Hz prediction node (control interface stub)
- [ ] Define controller inputs clearly (ex, ey, ez in pixels, target_valid flag)
- [ ] Add appearance embedding hook to association logic (placeholder: colour histogram + gradient)
- [ ] Demonstrate `/control_ref` stable at 30 Hz in bag

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Occlusion comparison: `../../artifacts/reports/compare/2026-03-01__occlusion_compare.md`
- Ambiguity comparison: `../../artifacts/reports/compare/2026-03-01__ambiguity_compare.md`
