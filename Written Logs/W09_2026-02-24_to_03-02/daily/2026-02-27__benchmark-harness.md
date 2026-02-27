# Daily Log — 2026-02-27 — Tracker Benchmark Harness v0 Working (Week 9, Day 4)

## Goal
Build a replayable benchmarking harness so the same detections stream can be replayed through different trackers and analysed into a single markdown summary with plots.

**Target outcome:**
- Replayable eval mode (bag play + tracker + selector + record outputs)
- Standard tracker output contract
- Tracking metrics script v0
- Decide tracker candidates for A, B, C

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 + F9P GNSS |
| Camera | Not available, tests use bag replay |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy |
| Storage | MCAP |
| Target env | Outdoor tennis court |
| Targets | Perception 15 FPS, control 30 Hz with prediction, latency budget 200 ms |

---

## Work Plan

### A) Create replayable evaluation mode (core)
- [x] Created replay runner launch file.
- Launch plays an input bag and records tracked outputs into a new MCAP bag directory.
- Outputs recorded: `/tracks`, `/target`, `/timing_tracker`.
- **Deliverable:** `thesis_bringup/launch/eval_replay.launch.py` ✓
- Notes:
  - `ros2 bag record` prints "Press SPACE", ignore — it always prints this.
  - Stop with Ctrl-C once; recorder flushes and finalises MCAP cleanly.

### B) Define the tracker interface contract
- [~] Contract drafted (in this log for now), needs to be moved into `thesis_tracker/README.md` tomorrow.
- Contract v0:
  - Input: `/detections` (Detection2DArray)
  - Output: `/tracks` (Track2DArray)
  - Output: `/timing_tracker` (Timing) with `track_ms` populated
  - Required fields in Timing for v0: `frame_id`, `track_ms`
- Notes:
  - `Timing` has no header; do not write `tmsg.header`.

### C) Implement metric extraction script v0
- [x] Created `~/Desktop/Thesis/tools/analyse_bag_tracking.py`
- Script reads `/target` and `/timing_tracker`, generates:
  - Target lock continuity (quality-gated)
  - Reacquisition events and timings
  - Target switches (currently naive, needs debounce fix)
  - `track_ms` stats and plots
- Produces `summary.md` + plots:
  - `target_lock_timeseries.png`
  - `track_ms_cdf.png`
  - `reacq_hist.png`
- **Deliverable:** `tools/analyse_bag_tracking.py` ✓
- Notes:
  - Target gating rule used: `has_target := (TargetState.quality > 0)`.

### D) Choose tracker candidates today
- [x] Tracker 1: SORT — already implemented and integrated.
- [x] Tracker 2: OC-SORT — chosen for stronger occlusion handling with minimal extra compute.
- [x] Tracker 3: ByteTrack — chosen over transformer trackers for shippable integration and predictable compute.
- **Deliverable:** Decision rationale to write in `artefacts.md` tomorrow.

---

## Results

### Deliverables checklist
- [x] `thesis_bringup/launch/eval_replay.launch.py`
- [x] `~/Desktop/Thesis/tools/analyse_bag_tracking.py`
- [ ] Tracker contract moved into `thesis_tracker/README.md` (do tomorrow)
- [ ] Tracker candidates rationale written into `artefacts.md` (do tomorrow)

### Harness commands (verified)

```bash
# Replay evaluation and record tracked outputs
cd ~/Desktop/Thesis/ros2_ws
colcon build --packages-select thesis_bringup
source install/setup.bash

ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=/home/francisco/Desktop/Thesis/bags/raw/2026-02-25__slice__primary \
  tracker:=sort

# Analyse
cd ~/Desktop/Thesis
python3 tools/analyse_bag_tracking.py \
  /home/francisco/Desktop/Thesis/bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort \
  --tag sort
```

### Bag used (tracked outputs)
- Bag: `.../bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort`
- Duration: 109.206 s
- Msg counts:
  - `/target`: 9389
  - `/timing_tracker`: 3248
  - `/tracks`: 6513

### Numbers (SORT baseline, v0)

| Metric | Value | Notes |
|--------|-------|-------|
| Target lock continuity (longest) | 108.498 s | quality gate `quality > 0` |
| Reacquisition events | 3 | likely brief quality blips |
| Reacq mean / p95 | 0.025 s / 0.041 s | not true occlusion yet |
| track_ms mean / p50 | 1.946 ms / 0.693 ms | median is good |
| track_ms p95 / p99 | 9.256 ms / 29.339 ms | heavy tail |
| track_ms max | 79.806 ms | outlier tail, investigate later |
| Target switches | 6116 | **invalid metric v0** — needs debounce + semantic meaning for `TargetState.id` |

### Tracker comparison table

| Tracker | Status | Notes |
|---------|--------|-------|
| SORT | ✓ Working | Baseline, already implemented |
| OC-SORT | Pending | Implement Day 28 |
| ByteTrack | Pending | Implement Day 28 |

### Interpretation (what we learned)
- Harness is functional end-to-end.
- SORT update runtime is usually sub-millisecond but has a heavy tail, which matters for latency budgets and control stability.
- "Target switches" cannot be treated as ID switches yet; the metric needs debounce and `TargetState.id` must be confirmed as a stable identity, not a churning track id.

---

## Issues / Risks
- `Timing` message has no header — ensure tracker node does not assign one.
- Current "switch count" is not meaningful without debounce and clarified semantics of `TargetState.id`.
- Runtime tails (p99, max) could impact control loop even if mean is small.

---

## Next steps (Day 28)

**Must do**
- [ ] Move tracker interface contract into `thesis_tracker/README.md` (short and strict).
- [ ] Fix analysis metric: implement debounced target switches (k=8 frames).
- [ ] Add a second metric: fraction of time locked (`sum(has_target)/N`) and total lost time.

**Tracker implementation**
- [ ] Implement OC-SORT in `thesis_tracker` under same contract (`tracker:=ocsort`).
- [ ] Implement ByteTrack (or integrate a minimal Python implementation) under same contract (`tracker:=bytetrack`).
- [ ] Create per-tracker YAML config files and load them via `cfg:=...`.

**Comparative run**
- [ ] Run the same detections bag through: `sort`, `ocsort`, `bytetrack`.
- [ ] Produce a single comparison markdown with one table.

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
