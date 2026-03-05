# W09 (2026-02-23 to 2026-03-01)

## Outcome (one paragraph)
The full ROS 2 perception slice is end-to-end and quantified, and the evaluation
harness is in place. `inference_client_node → tracker_node → target_selector_node`
runs reliably at sustained 30 Hz. Three trackers (SORT, OC-SORT, ByteTrack) are
implemented and comparable via `eval_replay.launch.py`. Occlusion and ambiguity
tests are repeatable and produce extended metrics (`time_locked_pct`,
`switches_per_min`, reacq histogram). Decision: SORT for online/control runs,
OC-SORT for offline identity experiments.

## Daily logs
- 2026-02-23: [Stall, conflate, wall-hz, ROS 2 plan](daily/2026-02-23__stall-conflate-wallhz-ros2-plan.md)
- 2026-02-24: [ROS2 first slice](daily/2026-02-24__ros2-first-slice.md)
- 2026-02-25: [ROS2 full graph](daily/2026-02-25__ros2-full-graph.md)
- 2026-02-26: [Bag metrics polish](daily/2026-02-26__bag-metrics-polish.md)
- 2026-02-27: [Benchmark harness v0, repo cleanup](daily/2026-02-27__benchmark-harness.md)
- 2026-02-28: [Multi-tracker baselines (OC-SORT + ByteTrack)](daily/2026-02-28__multi-tracker-baselines.md)
- 2026-03-01: [Occlusion + ambiguity tests](daily/2026-03-01__occlusion-ambiguity-tests.md)

## Key artefacts
- Timing report (primary bag): `reports/timing/2026-02-26__timing_summary.md`
- Timing report (long-run): `reports/timing/2026-02-26__timing_summary_longrun.md`
- Figures (primary bag): `figures/timing/lat_ms_cdf_2026-02-25__slice__primary.png`, `figures/timing/loop_ms_cdf_2026-02-25__slice__primary.png`, `figures/timing/pub_dt_ms_timeseries_2026-02-25__slice__primary.png`
- Primary bag: `bags/raw/2026-02-25__slice__primary`
- Long-run bag: `bags/raw/2026-02-26__slice__longrun`

## Decisions locked this week
- Tracker: SORT (params: `iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35`)
- Target selection rule: time-alive (longest continuously seen track)
- Timing methodology: base window vs active-only (gap-filtered at `gap_ms=100`)
- Inference service isolation: Docker container, host networking, ZMQ PUB/SUB port 5555 with `CONFLATE=1`
- Storage format: MCAP, always stop recorder with SIGINT to write metadata
- Tracker for online/control runs: **SORT** (lowest compute tail under occlusion)
- Tracker for offline identity experiments: **OC-SORT** (fewer ID switches, re-evaluate after ReID)
- Eval harness auto-shutdown: `OnProcessExit → Shutdown()` (no timeout workaround)

## Next week focus (W10)
- [ ] 30 Hz control ref node (`thesis_control_ref_node`, `/control_ref` topic)
- [ ] Appearance embedding hook in tracker association (placeholder acceptable)
- [ ] Camera bringup: CSI ribbon, image format, FPS lock, bagging protocol
- [ ] Replace placeholder embedding with learned ReID model
