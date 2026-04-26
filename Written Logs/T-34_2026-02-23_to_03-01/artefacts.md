# Artefacts — T-34 (2026-02-24 to 2026-03-02)

## Bags
- `bags/raw/2026-02-25__slice__secondary` (110 s, secondary — `/detections /tracks /target /timing`)
- `bags/raw/2026-02-25__slice__primary` (110 s, **primary** — `/detections /tracks /target /timing`)
- `bags/raw/2026-02-26__slice__longrun` (464.7 s, long-run looping service — same topics)

## Reports
- `reports/timing/2026-02-26__timing_summary.md` (primary bag, n=3296)
- `reports/timing/2026-02-26__timing_summary_secondary.md` (secondary bag)
- `reports/timing/2026-02-26__timing_summary_longrun.md` (long-run bag, active-only)

## Figures (thesis-ready)

### Bag: 2026-02-25__slice__primary
- `figures/timing/lat_ms_hist_2026-02-25__slice__primary.png`
- `figures/timing/lat_ms_cdf_2026-02-25__slice__primary.png`
- `figures/timing/loop_ms_hist_2026-02-25__slice__primary.png`
- `figures/timing/loop_ms_cdf_2026-02-25__slice__primary.png`
- `figures/timing/pub_dt_ms_timeseries_2026-02-25__slice__primary.png`

### Bag: 2026-02-25__slice__secondary
- `figures/timing/lat_ms_hist_2026-02-25__slice__secondary.png`
- `figures/timing/lat_ms_cdf_2026-02-25__slice__secondary.png`
- `figures/timing/loop_ms_hist_2026-02-25__slice__secondary.png`
- `figures/timing/loop_ms_cdf_2026-02-25__slice__secondary.png`
- `figures/timing/pub_dt_ms_timeseries_2026-02-25__slice__secondary.png`

## Tracker Candidates — Rationale and Decision

| Tracker | Chosen role | Rationale |
|---------|------------|----------|
| **SORT** | Online baseline (flight-safe) | Lowest compute tail: p95 < 2 ms under target-centric occlusion. Simplest, no extra deps. Default for all live/control runs. Params: `iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35`. |
| **OC-SORT** | Offline identity experiments | Fewest target switches (28 vs 37 SORT vs 50 ByteTrack) and best p95 runtime (2.71 ms) in clean scenes. Runtime tail explodes under occlusion (p95 11–23 ms). Re-evaluate once ReID embeddings are added. |
| **ByteTrack** | Reserve / comparison | Two-stage high/low-confidence matching. Most target switches in current test clip (50). No extra deps. Kept for completeness. |

**Decision:** Use **SORT** as baseline tracker for all online and control-coupled runs. Use **OC-SORT** for offline identity-consistency experiments. Re-run comparison after appearance embeddings are integrated.

---

## Code (paths only)
- `tools/analyse_bag_timing.py`
- `infer_service/run_detection_zmq_forever.sh`
- `ros2_ws/src/thesis_msgs/`
- `ros2_ws/src/thesis_inference_client/`
- `ros2_ws/src/thesis_tracker/`
- `ros2_ws/src/thesis_target_selector/`
- `ros2_ws/src/thesis_bringup/`

## Repro commands (copy-paste)
```bash
# Analyse primary bag
python3 tools/analyse_bag_timing.py bags/raw/2026-02-25__slice__primary \
  --out reports/timing/2026-02-26__timing_summary.md \
  --figdir figures --plot-timeseries --gap-ms 100

# Analyse long-run bag (active-only)
python3 tools/analyse_bag_timing.py bags/raw/2026-02-26__slice__longrun \
  --out reports/timing/2026-02-26__timing_summary_longrun.md \
  --figdir figures --plot-timeseries --gap-ms 100

# Record a new bag (always MCAP + SIGINT)
ros2 bag record --storage mcap --topics /detections /tracks /target /timing &
kill -SIGINT $!
ros2 bag info <bag_dir>
```
