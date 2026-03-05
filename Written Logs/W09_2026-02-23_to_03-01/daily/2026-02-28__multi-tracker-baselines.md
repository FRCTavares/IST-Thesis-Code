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
- [x] Create OC-SORT tracker node behind same wrapper interface as SORT
- [x] Subscribe to `/detections`, publish `/tracks` (Track2DArray)
- [x] Publish `/timing_tracker` with `track_ms` field
- [x] Ensure no crash on Ctrl-C (executor-based shutdown)
- [x] Test with existing evaluation bag from Day 27
- **Deliverable:** `ros2_ws/src/thesis_tracker/backends/ocsort_backend.py` + integrated via `tracker_node.py` (`tracker_type:=ocsort`)
- Notes: See implementation notes below

**Implementation notes:**
- OC-SORT source: implemented as a lightweight embedded-style variant (no external repo dependency, same Kalman + Hungarian core as SORT, with second-stage association)
- Key differences from SORT: lower-threshold second-stage association for occlusion recovery; observation-centric velocity history scaffold
- Dependencies: numpy only (no new deps)

### B) Implement tracker #3
- [x] Chose tracker based on practicality:
  - **If attention/transformer:** Choose simple transformer-based association only if library exists and runs on Pi
  - **Otherwise:** ByteTrack is safe "strong baseline"
- [x] Implement with same interface (subscribe `/detections`, publish `/tracks`, `/timing_tracker`)
- [x] Test basic functionality
- **Decision:** ByteTrack
- **Deliverable:** `ros2_ws/src/thesis_tracker/backends/bytetrack_backend.py` + integrated via `tracker_node.py` (`tracker_type:=bytetrack`)
- Notes: See implementation notes below

**Implementation notes:**
- Source: lightweight in-repo implementation (two-stage matching, no ReID)
- Key features: high/low confidence split, low-score rescue stage
- Performance expectations: SORT-class runtime, improved robustness when detector confidence drops

### C) Add tracker parameter yaml files
- [x] Create `ros2_ws/src/thesis_bringup/config/tracker_sort.yaml`
  - Parameters: IoU threshold, min hits, max age, etc.
- [x] Create `ros2_ws/src/thesis_bringup/config/tracker_ocs.yaml`
  - Parameters: OC-SORT specific (delta_t, asso_func, inertia, use_byte, etc.)
- [x] Create `ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml` (or chosen tracker #3)
  - Parameters: track_thresh, track_buffer, match_thresh, etc.
- [x] Update launch file to accept `tracker:=<name>` argument and load corresponding config
- **Deliverable:** All trackers configured via params only
- Notes: Normalised `min_score=0.35` across all trackers for fair comparison.

### D) Run the same bag through all trackers
- [x] Use evaluation launch from Day 27 with `tracker:=sort`
- [x] Run with `tracker:=ocs`
- [x] Run with `tracker:=bytetrack` (or chosen tracker #3)
- [x] Run `analyse_bag_tracking.py` on each output bag
- [x] Produce 3 summary reports (same format)
- [x] Create one comparison table (manual is fine today)
- **Deliverable:** `reports/compare/2026-02-28__tracker_compare.md`
- Notes: Raw bag: `bags/raw/2026-02-28__slice__smoke2` (59.06 s). Eval runs (timeout-capped, comparable): `bags/eval/2026-02-28__eval__2026-02-28__slice__smoke2__sort__r3` (67.58 s), `bags/eval/2026-02-28__eval__2026-02-28__slice__smoke2__ocsort__r2` (66.96 s), `bags/eval/2026-02-28__eval__2026-02-28__slice__smoke2__bytetrack__r2` (67.05 s). `eval_replay.launch.py` still requires SIGINT to stop recorder, used `timeout -s SIGINT 70s` to standardise duration.

---

## Results

### Deliverables checklist
- [x] OC-SORT backend implemented and tested
- [x] Tracker #3 implemented and tested (ByteTrack)
- [x] Parameter yaml files for all trackers (min_score aligned)
- [x] `reports/compare/2026-02-28__tracker_compare.md` generated from per-run summaries

### Comparison table: Runtime and tracking quality

| Tracker | track_ms p50 (ms) | track_ms p95 (ms) | track_ms mean (ms) | Target switches | Reacq events | Notes |
|---------|-------------------|-------------------|--------------------|-----------------|--------------|---------|
| SORT | 0.8611 | 5.8584 | 1.8820 | 37 | 0 | baseline |
| OC-SORT | 0.8904 | 2.7111 | 1.4038 | 28 | 1 | best runtime tail + fewer switches |
| ByteTrack | 0.9662 | 4.6358 | 1.7800 | 50 | 0 | worst switches in this clip |

### Decision: Which tracker is "baseline for outdoor"
**Decision: baseline for outdoor: OC-SORT**

**Rationale:**
- Lowest target switches on this run (28 vs 37 vs 50).
- Best runtime stability (track_ms p95 2.71 ms).
- SORT-class complexity, no extra dependencies, good default before adding ReID.

**Caveat:**
Motion-only comparison, no ground-truth ID metrics yet; next step is occlusion injection and ambiguity tests.

---

## Issues / Risks
- `eval_replay.launch.py` does not auto-stop recorder after `ros2 bag play` exits, required timeout/SIGINT to avoid overlong eval bags.
- Kernel update to 6.8.0-1048-raspi broke Hailo driver until DKMS rebuilt for the new kernel (fixed by installing headers and DKMS autoinstall).
- ByteTrack config initially used `min_score=0.2`, fixed to 0.35 for fair comparison.

---

## Next steps (Day 01, March 1)
- [x] Fix `eval_replay.launch.py` to auto-shutdown when bag play exits ✓ (`OnProcessExit → Shutdown`).
- [ ] Add "switches per minute" and "fraction locked" to tracking summary (if not already present).
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
