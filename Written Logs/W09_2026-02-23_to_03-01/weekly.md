# Weekly Summary — W09 (2026-02-23 to 2026-03-01)

## Goals for the week
- [x] Get ROS 2 slice end-to-end (inference → tracker → target selector)
- [x] Record MCAP bags and generate quantitative timing reports
- [x] Establish reproducible baseline before camera bringup
- [x] Benchmarking harness (eval replay + tracking metrics script, 3 tracker candidates)
- [x] OC-SORT + ByteTrack implemented and compared against SORT
- [x] Occlusion + ambiguity test protocol with repeatable runs and extended metrics

## What shipped (bulletproof facts)
- ROS 2 slice stable: `/detections → /tracks → /target`, plus `/timing` diagnostic topic.
- `tools/analyse_bag_timing.py`: offline per-field stats (mean, p50, p95, p99, min, max) + figures + bag-tagged output.
- Long-run bag (~465 s) produced with looping inference service (`run_detection_zmq_forever.sh`), gap-filtered active-only analysis confirmed no latency growth across restarts.
- Added `/timing_tracker` stub; fixed `tracker_node` Ctrl-C crash (executor-based shutdown); made `inference_client_node` restart-safe.
- All timing figures saved with bag-ID tags (thesis-ready).
- `eval_replay.launch.py`: replayable harness, auto-shuts down on bag-play exit, collision-safe output naming.
- OC-SORT and ByteTrack backends implemented; per-tracker YAML configs; comparison report generated.
- `tools/analyse_bag_tracking.py`: target lock %, total lost time, switches/min, reacq histogram.
- `detections_occluder_node.py` (periodic + target-centric modes) and `detections_ambiguity_node.py` (synthetic crossing).
- Tracker candidates rationale locked in `artefacts.md`; tracker interface contract in `thesis_tracker/README.md`.

## Numbers (primary bag: 2026-02-25__slice__primary, n=3296)

| Metric | mean | p50 | p95 | p99 |
|--------|------|-----|-----|-----|
| `lat_ms` | 1.552 | 1.160 | 3.835 | 5.548 |
| `loop_ms` | 28.644 | 28.590 | 33.121 | 35.740 |
| `pub_dt_ms` | 33.327 | 33.331 | 36.734 | 37.905 |
| `track_ms` | — | — | — | — |

- Base window Hz (from bag counts/duration): ~30 Hz on all topics
- Active-only (long-run bag, gap_ms=100): 30.055 Hz; p95 `loop_ms` 33.355 ms, p99 36.064 ms; `lat_ms` mean 1.541 ms

## Issues / risks
- `track_ms` not yet instrumented in `tracker_node` — next action before any tracker comparison.
- Camera (CSI) not connected this week — all tests on pre-recorded video from inference service.
- `ros2 topic hz` does not accept multiple topics; use bag count÷duration instead.

## Week 9 Ambition Targets (by end of Mar 1)

Move from "pipeline works" to "outdoor, control-ready demo path" with real novelty hooks.

By end of Day 06 (March 1), you should have:

1. ✅ **Tracker benchmarking harness** (apples-to-apples) with at least 3 trackers:
   - SORT baseline
   - OC-SORT
   - ByteTrack

2. ✅ **Occlusion + ambiguity test protocol** implemented as repeatable runs:
   - Synthetic occlusion injection in replay
   - Multi-person crossing scenario
   - Metrics: reacquisition time, target-lock continuity, switches/min, time_locked_pct

3. ⏩ **Control interface stub** running at 30 Hz — **moved to W10 Day 1 (Mar 2)**

4. ⏩ **Novelty wedge / embedding hook** — **moved to W10 Day 1 (Mar 2)**

**Target specs:**
- Outdoor tennis court target environment
- Full online processing
- 15 FPS perception target
- 30 Hz control with prediction
- Latency budget: 200 ms max

## Remaining Daily Goals

### Day 27 (02-27): Build the benchmarking harness, not just measure one bag
**Outcome:** You can run `tracker=sort|ocsort|bytetrack` on the same recorded detections stream and get a single markdown summary + plots.

**Work blocks:**
- A) Create replayable evaluation mode (record detections-only bag, write replay runner launch)
- B) Define tracker interface contract (all trackers publish same `/tracks`, `/timing_tracker`)
- C) Implement metric extraction script v0 (`tools/analyse_bag_tracking.py`)
- D) Choose tracker candidates today (SORT, OC-SORT, ByteTrack/transformer)

**Deliverables:**
- `thesis_bringup/launch/eval_replay.launch.py`
- `tools/analyse_bag_tracking.py`
- Tracker decision in `artefacts.md`

### Day 28 (02-28): Implement OC-SORT + one more tracker, and make them comparable
**Outcome:** You can swap tracker implementation with a launch arg and rerun evaluation.

**Work blocks:**
- A) Implement OC-SORT node (same interface, publish `/timing_tracker`)
- B) Implement tracker #3 (ByteTrack or simple transformer-based if practical on Pi)
- C) Add tracker parameter yaml files for each tracker
- D) Run same bag through all trackers, produce comparison report

**Deliverables:**
- All trackers configured via params only
- `config/tracker_sort.yaml`, `config/tracker_ocs.yaml`, `config/tracker_bytetrack.yaml`
- `reports/compare/2026-02-28__tracker_compare.md`

### Day 01 (03-01): Make occlusion and ambiguity a first-class test
**Outcome:** You have repeatable occlusion tests that stress identity consistency and you can quantify.

**Work blocks:**
- A) Occlusion injection via synthetic drop node (drop detections for 1.0 s, simulate overlap)
- B) Ambiguity test (2 persons close, association ambiguous)
- C) Metrics: reacquisition time distribution, switches per minute, "time locked" percentage

**Deliverables:**
- `thesis_tools/detections_occluder_node.py`
- At least one repeatable run scenario for ambiguity
- Plots/tables showing test results for at least 2 trackers

### Day 02 (03-02) — moved to W10
This day's goals (30 Hz control ref node, embedding hook) fall on March 2 which is W10 Day 1.
See [W10 daily log](../../W10_2026-03-02_to_03-08/daily/2026-03-02__30hz-control-stub-and-embedding-hook.md).

## Next week plan (W10)
- [ ] 30 Hz control ref node (`thesis_control_ref_node`, `/control_ref` topic)
- [ ] Appearance embedding hook in tracker association (placeholder: colour histogram)
- [ ] Replace placeholder with learned embedding
- [ ] Camera bringup when hardware arrives (CSI ribbon, format, FPS lock)
- [ ] Finish comprehensive README

## Links
- Week index: `index.md`
- Artefacts: `artefacts.md`
