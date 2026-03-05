# W09 (2026-02-24 to 2026-03-02)

## Outcome (one paragraph)
The full ROS 2 perception slice is end-to-end and quantified.
`inference_client_node → tracker_node → target_selector_node` runs reliably at
sustained 30 Hz; a long-run bag (464 s, looping service) confirms no latency
growth across restarts. Timing is now measurable offline from MCAP bags, giving
a reproducible baseline for every future improvement (ByteTrack, embeddings,
camera bringup).

## Daily logs
- 2026-02-24: [ROS2 first slice](daily/2026-02-24__ros2-first-slice.md)
- 2026-02-25: [ROS2 full graph](daily/2026-02-25__ros2-full-graph.md)
- 2026-02-26: [Bag metrics polish](daily/2026-02-26__bag-metrics-polish.md)

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

## Next week focus
- [ ] Instrument `tracker_node` runtime (`track_ms`) and publish on `/timing_tracker`
- [ ] Camera bringup: CSI ribbon, image format, FPS lock, bagging protocol
- [ ] Decide ByteTrack vs OC-SORT as next tracker candidate; run offline comparison on primary bag
