# Weekly Summary — W09 (2026-02-24 to 2026-03-02)

## Goals for the week
- [x] Get ROS 2 slice end-to-end (inference → tracker → target selector)
- [x] Record MCAP bags and generate quantitative timing reports
- [x] Establish reproducible baseline before camera bringup

## What shipped (bulletproof facts)
- ROS 2 slice stable: `/detections → /tracks → /target`, plus `/timing` diagnostic topic.
- `tools/analyse_bag_timing.py`: offline per-field stats (mean, p50, p95, p99, min, max) + figures + bag-tagged output.
- Long-run bag (~465 s) produced with looping inference service (`run_detection_zmq_forever.sh`), gap-filtered active-only analysis confirmed no latency growth across restarts.
- Added `/timing_tracker` stub; fixed `tracker_node` Ctrl-C crash (executor-based shutdown); made `inference_client_node` restart-safe.
- All timing figures saved with bag-ID tags (thesis-ready).

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

## Week 9 Ambition Targets (by end of Mar 2)

Move from "pipeline works" to "outdoor, control-ready demo path" with real novelty hooks.

By end of Day 02 (March 2), you should have:

1. **Tracker benchmarking harness** (apples-to-apples) with at least 3 trackers:
   - SORT baseline
   - OC-SORT (or ByteTrack)
   - "Attention/transformer style" tracker candidate (realistic, not research rabbit hole)

2. **Occlusion + ambiguity test protocol** implemented as repeatable runs:
   - Synthetic occlusion injection in replay
   - Multi-person crossing scenario
   - Metrics: reacquisition time, target-lock continuity, ID switches proxy

3. **Control interface stub** running at 30 Hz:
   - Prediction-based output at 30 Hz
   - Stable even when detections arrive at lower rate
   - Publishes control setpoints to a dummy topic

4. **Novelty wedge started**:
   - Tiny learned embedding hook defined
   - Working "placeholder embedding pipeline" with interface and logging
   - Even if embedding is dummy initially

**Target specs:**
- Outdoor tennis court target environment
- Full online processing
- 15 FPS perception target
- 30 Hz control with prediction
- Latency budget: 200 ms max

## Remaining Daily Goals

### Day 27 (02-27): Build the benchmarking harness, not just measure one bag
**Outcome:** You can run `tracker=A/B/C` on the same recorded detections stream and get a single markdown summary + plots.

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

### Day 02 (03-02): Control-ready 30 Hz loop with prediction, and "novelty wedge" hook
**Outcome:** You publish a 30 Hz control-setpoint topic driven by tracker prediction, and you have an embedding "slot" ready.

**Work blocks:**
- A) 30 Hz prediction node (subscribes `/tracks`, `/target`, outputs `/control_ref` at 30 Hz)
- B) Define controller inputs clearly (ex, ey, ez in pixels, target_valid flag)
- C) Novelty wedge starter: add appearance_vec field to association logic with placeholder (colour histogram + gradient)

**Deliverables:**
- `thesis_control_ref_node`
- Diagram: detection rate vs tracker update vs controller tick
- Evidence: `/control_ref` stable at 30 Hz in bag
- Association code has plug-in for embeddings with logged appearance distance

## Next week plan
- [ ] Replace placeholder with learned embedding
- [ ] Instrument all nodes with timing metrics
- [ ] Camera bringup when hardware arrives (CSI ribbon, format, FPS lock)
- [ ] Finish comprehensive README

## Links
- Week index: `index.md`
- Artefacts: `artefacts.md`
