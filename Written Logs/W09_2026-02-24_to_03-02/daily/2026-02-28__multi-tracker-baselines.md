# Daily Log — 2026-02-28 — Implement OC-SORT + One More Tracker, Make Them Comparable (Week 9, Day 5)

## Goal
Implement OC-SORT + one more tracker (ByteTrack or practical transformer), and make them comparable. By end of day, you can swap tracker implementation with a launch arg and rerun evaluation.

**Target outcome:**
- OC-SORT node working with same interface as SORT
- Third tracker implemented (ByteTrack or practical alternative)
- All trackers configurable via parameter yaml files
- Comparison report showing runtime and tracking quality metrics across all 3 trackers

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS |
| Camera | **Hardware not available yet**, all tests use bag replay and synthetic occlusion. Camera integration scheduled once hardware arrives. |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Target environment | Outdoor tennis court |
| Perception target | 15 FPS |
| Control target | 30 Hz with prediction |
| Latency budget | 200 ms max |
| Tracker candidates | SORT (baseline), OC-SORT, ByteTrack / Transformer |

---

## Work Plan

### A) Implement OC-SORT node
- [ ] Create OC-SORT tracker node behind same wrapper interface as SORT
- [ ] Subscribe to `/detections`, publish `/tracks` (Track2DArray)
- [ ] Publish `/timing_tracker` with `track_ms` field
- [ ] Ensure no crash on Ctrl-C (executor-based shutdown)
- [ ] Test with existing evaluation bag from Day 27
- **Deliverable:** `thesis_bringup/nodes/tracker_ocs_node.py` (or similar)
- Notes: *(fill)*

**Implementation notes:**
- OC-SORT source: *(link to reference implementation)*
- Key differences from SORT: *(fill - observation-centric, virtual trajectory, etc.)*
- Dependencies: *(fill - scipy, numpy versions, etc.)*

### B) Implement tracker #3
- [ ] Chose tracker based on practicality:
  - **If attention/transformer:** Choose simple transformer-based association only if library exists and runs on Pi
  - **Otherwise:** ByteTrack is safe "strong baseline"
- [ ] Implement with same interface (subscribe `/detections`, publish `/tracks`, `/timing_tracker`)
- [ ] Test basic functionality
- **Decision:** *(fill - ByteTrack / Other)*
- **Deliverable:** Tracker node implementation
- Notes: *(fill)*

**Implementation notes:**
- Source: *(link)*
- Key features: *(fill - e.g., ByteTrack: two matching stages, low-score detection recovery)*
- Performance expectations: *(fill)*

### C) Add tracker parameter yaml files
- [ ] Create `config/tracker_sort.yaml`
  - Parameters: IoU threshold, min hits, max age, etc.
- [ ] Create `config/tracker_ocs.yaml`
  - Parameters: OC-SORT specific (delta_t, asso_func, inertia, use_byte, etc.)
- [ ] Create `config/tracker_bytetrack.yaml` (or chosen tracker #3)
  - Parameters: track_thresh, track_buffer, match_thresh, etc.
- [ ] Update launch file to accept `tracker:=<name>` argument and load corresponding config
- **Deliverable:** All trackers configured via params only
- Notes: *(fill)*

### D) Run the same bag through all trackers
- [ ] Use evaluation launch from Day 27 with `tracker:=sort`
- [ ] Run with `tracker:=ocs`
- [ ] Run with `tracker:=bytetrack` (or chosen tracker #3)
- [ ] Run `analyse_bag_tracking.py` on each output bag
- [ ] Produce 3 summary reports (same format)
- [ ] Create one comparison table (manual is fine today)
- **Deliverable:** `reports/compare/2026-02-28__tracker_compare.md`
- Notes: *(fill)*

---

## Results

### Deliverables checklist
- [ ] OC-SORT node implemented and tested
- [ ] Tracker #3 implemented and tested
- [ ] Parameter yaml files for all trackers
- [ ] `reports/compare/2026-02-28__tracker_compare.md` with comparison table

### Comparison table: Runtime and tracking quality

| Tracker | Runtime p95 (ms) | Target switches | Reacquire time p95 (s) | Notes |
|---------|------------------|-----------------|------------------------|-------|
| SORT | — | — | — | Baseline |
| OC-SORT | — | — | — | Observation-centric |
| ByteTrack / Other | — | — | — | *(fill)* |

### Decision: Which tracker is "baseline for outdoor"
*(Fill after analysis)*

**Rationale:**
- *(Consider: runtime stability on Pi, occlusion handling, ID switch rate, ease of tuning)*
- *(Outdoor tennis court environment: occlusion from net, multiple people, lighting changes)*

---

## Issues / Risks
- *(Fill as they arise)*

**Known challenges:**
- Pi 5 compute constraints for complex trackers
- Dependency conflicts between tracker implementations
- Parameter tuning for outdoor environment (untested without camera)

---

## Next steps (Day 01, March 1)
- [ ] Implement occlusion injection node for synthetic testing
- [ ] Design ambiguity test scenario (crossing persons)
- [ ] Extend tracking metrics: reacquisition time distribution, switches per minute, time locked percentage
- [ ] Run occlusion tests on at least 2 trackers

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
- Comparison report: `../../reports/compare/2026-02-28__tracker_compare.md`
