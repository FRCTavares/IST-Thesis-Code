# Daily Log — 2026-03-02 — 30 Hz Control-Ready Loop with Prediction, and "Novelty Wedge" Hook (Week 9, Day 7)

## Goal
Implement control-ready 30 Hz loop with prediction, and add "novelty wedge" hook for learned embeddings. By end of day, you publish a 30 Hz control-setpoint topic driven by tracker prediction, and you have an embedding "slot" ready.

**Target outcome:**
- 30 Hz prediction node running (stable output even when detections slower)
- Control inputs clearly defined (ex, ey, ez in pixels with target_valid flag)
- Appearance embedding interface added to association logic with placeholder
- Evidence: `/control_ref` stable at 30 Hz in bag replay
- Diagram: detection rate vs tracker update vs controller tick

**This sets you up to replace placeholder with learned embedding later without refactor.**

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay and synthetic occlusion. Camera integration scheduled once hardware arrives. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court |
| Perception target | 15 FPS (detection rate) |
| Control target | **30 Hz** with prediction (this day's focus) |
| Latency budget | 200 ms max |
| Coordinate frame | Pixels (image space) |

---

## Work Plan

### A) 30 Hz prediction node
Create node that outputs control setpoints at fixed 30 Hz, using tracker state + prediction.

- [ ] Create `thesis_control_ref_node`:
  - Subscribes to `/tracks` and `/target`
  - Runs on 30 Hz timer (independent of detection/tracker rate)
  - Outputs `/control_ref` (custom msg or `geometry_msgs`)
  - Uses last known state + constant velocity prediction for 30 Hz interpolation
- [ ] Implement constant velocity prediction:
  - Track position history (last N states)
  - Compute velocity: `v = (pos_t - pos_t-1) / dt`
  - Predict: `pos_predicted = pos_last + v * dt_since_last`
- [ ] Handle stale data:
  - If no tracker update for > threshold (e.g., 200 ms), set `target_valid = False`
- [ ] Log timing: when predictions used vs fresh detections
- **Deliverable:** `thesis_control_ref_node` in `thesis_bringup/nodes/`
- Notes: *(fill)*

**Message definition (proposed):**
```python
# ControlReference.msg
std_msgs/Header header
float32 ex_px          # Error in x (pixels from center)
float32 ey_px          # Error in y (pixels from center)
float32 ez_px          # Error in z (area error, desired_area - current_area)
bool target_valid      # True if target locked, False if lost/stale
uint32 prediction_age_ms  # Time since last tracker update
```

### B) Define controller inputs clearly (pixels)
Formalize the control error signals in image space.

- [ ] Define coordinate system:
  - Image center: `(W/2, H/2)`
  - Error signals:
    - `ex = cx_px - W/2`  (horizontal error)
    - `ey = cy_px - H/2`  (vertical error)
    - `ez = desired_area - area_px`  (depth error, scale-based)
- [ ] Choose `desired_area`:
  - Option 1: Fixed value (e.g., 10,000 px²)
  - Option 2: Adaptive based on court distance
  - **Decision:** *(fill)*
- [ ] Add `target_valid` flag:
  - `False` when: no target, stale data, low confidence
  - `True` when: fresh tracker lock, confidence above threshold
- [ ] Document in README or control design doc
- Notes: *(fill)*

**Controller input summary:**
| Signal | Definition | Units | Notes |
|--------|------------|-------|-------|
| `ex_px` | `cx - W/2` | pixels | Horizontal error |
| `ey_px` | `cy - H/2` | pixels | Vertical error |
| `ez_px` | `A_desired - A_current` | pixels² | Depth/scale error |
| `target_valid` | Lock status | bool | False if stale/lost |

### C) Novelty wedge starter: embedding interface
Add appearance embedding hook to tracker association logic, even if embedding is dummy initially.

- [ ] Modify tracker code (SORT or chosen baseline) to include appearance term:
  - Current: `cost = IoU_distance(det, track)`
  - New: `cost = w_iou * IoU_distance + w_app * appearance_distance`
- [ ] Add `appearance_vec` field to track state:
  - Length: 8 to 16 floats
  - Initially: placeholder (colour histogram + downsampled gradient)
- [ ] Implement cheap placeholder appearance:
  - **Colour histogram:** HSV histogram (3x4x4 bins = 48 dim → reduce to 8 with PCA or simple binning)
  - **Gradient magnitude:** Sobel edge map, downsample to 2x2 or 4x4 grid
  - **Distance:** L2 or cosine distance
- [ ] Log appearance distance for matched pairs:
  - Add to `/timing_tracker` or separate `/appearance_debug` topic
- [ ] Make `w_app` configurable (start with 0.1 or 0.0 to verify no regression)
- **Deliverable:** Association code has plug-in for embeddings, logs include cost term
- Notes: *(fill)*

**Embedding design:**
```python
# Pseudocode
class TrackerWithAppearance:
    def extract_appearance(self, bbox, image):
        # Placeholder: colour histogram
        hsv = cv2.cvtColor(crop(image, bbox), cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0,1,2], None, [4,4,4])
        return hist.flatten()[:8]  # Reduce to 8-dim
    
    def appearance_distance(self, emb1, emb2):
        return np.linalg.norm(emb1 - emb2)  # L2 distance
    
    def associate(self, detections, tracks):
        cost_matrix = self.iou_cost(detections, tracks)
        app_cost = self.appearance_cost(detections, tracks)
        total_cost = w_iou * cost_matrix + w_app * app_cost
        return hungarian(total_cost)
```

**Next week:** Replace placeholder with learned embedding (ReID model or custom-trained).

### D) Evidence and diagrams
- [ ] Run full pipeline with 30 Hz control node
- [ ] Record bag including `/control_ref`
- [ ] Verify: `ros2 topic hz /control_ref` → ~30 Hz
- [ ] Create diagram showing rate hierarchy:
  - Detection: ~15 FPS
  - Tracker update: ~15 Hz (matches detections)
  - Control output: 30 Hz (prediction fills gaps)
- [ ] Plot timeline: detection timestamps vs control_ref timestamps
- **Deliverable:** Diagram + plot in artefacts/reports
- Notes: *(fill)*

**Diagram (detection → tracker → controller):**
```
Time axis:
|----det----det----det----det----det----|  15 Hz detections
|--trk--trk--trk--trk--trk--trk--trk----|  ~15 Hz tracker updates
|-ctrl-ctrl-ctrl-ctrl-ctrl-ctrl-ctrl----|  30 Hz control (prediction between)
    ↑                     ↑
    fresh update          prediction used
```

---

## Results

### Deliverables checklist
- [ ] `thesis_control_ref_node` implemented and tested
- [ ] Controller inputs (ex, ey, ez, target_valid) documented
- [ ] Appearance embedding hook added to tracker with placeholder
- [ ] Diagram: detection rate vs tracker update vs controller tick
- [ ] Evidence: `/control_ref` stable at 30 Hz in bag

### Numbers: Control loop performance

| Metric | Target | Achieved | Notes |
|--------|--------|----------|-------|
| `/control_ref` rate | 30 Hz | — | *(fill after test)* |
| Prediction ratio | — | — % | % of control outputs using prediction vs fresh data |
| Max prediction age | 200 ms | — ms | Threshold before `target_valid = False` |

### Appearance embedding placeholder

| Component | Implementation | Notes |
|-----------|----------------|-------|
| Feature extractor | Colour histogram + gradient | HSV 4x4x4 → 8-dim |
| Distance metric | L2 norm | *(or cosine)* |
| Weight in cost | `w_app = 0.1` | *(tune)* |
| Logged? | Yes, in `/timing_tracker` | *(or separate topic)* |

**Appearance distance statistics (from test bag):**
- *(Fill after implementation)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Prediction quality with constant velocity (outdoor: complex motion)
- Placeholder appearance may not be discriminative enough for real ambiguity
- Integration testing without camera (limited validation)

---

## Week 9 Summary
By end of Day 02, you should have:
- ✅ Tracker benchmarking harness (3 trackers: SORT, OC-SORT, ByteTrack/other)
- ✅ Occlusion + ambiguity test protocol with metrics
- ✅ Control interface stub running at 30 Hz
- ✅ Novelty wedge started (embedding hook with placeholder)

## Next week (Week 10) priorities
- [ ] Replace placeholder embedding with learned ReID model
- [ ] Camera bringup when hardware arrives (CSI, exposure, FPS lock)
- [ ] Outdoor validation with camera (if available)
- [ ] Control loop integration with ArduPilot MAVLink
- [ ] Comprehensive README and documentation

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Control diagram: *(fill after creation)*
- Control loop plots: *(fill after generation)*
