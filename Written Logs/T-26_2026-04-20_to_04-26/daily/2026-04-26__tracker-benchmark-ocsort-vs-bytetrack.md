# Daily Log - 2026-04-26 (Day 26) - Tracker Benchmark (OC-SORT vs ByteTrack)

## Context

- Goal: benchmark upgraded OC-SORT and upgraded ByteTrack under identical 120s live timing windows.
- Runtime mode: live stack (`--profile daily`) with tracker profiling enabled.
- Baseline references:
  - SORT (`track_ms p50=2.40`, `p95=7.81`, `detections Hz=16.87`)
  - DeepSORT hist (`track_ms p95=42.49`)
  - DeepSORT MARS (`track_ms p95=71.28`)

## Commands Used

### OC-SORT run

```bash
cd ~/Desktop/Thesis-Code
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42

./tools/start_live_stack.sh \
  --profile daily \
  --tracker ocsort \
  --tracker-timing-on \
  --tracker-gc-probe-off \
  --tracker-profile-log-every 30
```

```bash
cd ~/Desktop/Thesis-Code

python3 tools/collect_live_timing_stats.py \
  --duration 120 \
  --run-label "ocsort_upgraded_$(date +%Y%m%d_%H%M%S)" \
  --json-out "reports/timing/ocsort_upgraded_$(date +%Y%m%d_%H%M%S).json"
```

### ByteTrack run

```bash
cd ~/Desktop/Thesis-Code
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"
export ROS_DOMAIN_ID=42

./tools/start_live_stack.sh \
  --profile daily \
  --tracker bytetrack \
  --tracker-timing-on \
  --tracker-gc-probe-off \
  --tracker-profile-log-every 30
```

```bash
cd ~/Desktop/Thesis-Code

python3 tools/collect_live_timing_stats.py \
  --duration 120 \
  --run-label "bytetrack_upgraded_$(date +%Y%m%d_%H%M%S)" \
  --json-out "reports/timing/bytetrack_upgraded_$(date +%Y%m%d_%H%M%S).json"
```

## Results

| Tracker | track_ms p50 | track_ms p95 | Detection Hz | Live status |
| --- | ---: | ---: | ---: | --- |
| SORT | 2.40 ms | 7.81 ms | 16.87 Hz | stable baseline |
| OC-SORT upgraded | 0.445 ms | 5.526 ms | 18.99 Hz | best live candidate |
| ByteTrack upgraded | 1.855 ms | 5.944 ms | 14.27 Hz | good, but threshold-starved |
| DeepSORT hist | 23.77 ms | 42.49 ms | 14.71 Hz | too expensive |
| DeepSORT MARS | 53.36 ms | 71.28 ms | 12.92 Hz | reference only |

## Decision

- Main live base: upgraded OC-SORT.
- ByteTrack remains computationally viable and should be kept as low-confidence rescue path.
- Current ByteTrack live comparison is not fully fair yet due to upstream score filtering.
- Live stack default tracker was switched from `sort` to `ocsort` after this benchmark decision.

## Critical Limitation (must be carried forward)

ByteTrack low-confidence rescue is currently limited by upstream detection thresholding.

Current live launcher behavior (`tools/start_live_stack.sh`):

- perception node starts with `-p min_score:=0.35`
- tracker node path also applies `min_score=0.35`

Impact:

- detections in `[0.10, 0.35)` are filtered before ByteTrack receives them
- ByteTrack second-stage low-score association is starved

Needed for paper-faithful ByteTrack evaluation:

- detector/perception min_score <= `0.10` (or `0.20`)
- tracker min_score <= `0.10` (or `0.20`)
- ByteTrack `track_thresh ~ 0.50`
- ByteTrack `det_thresh ~ 0.10` (or `0.20`)

## Code Fix Applied Today

- Fixed ByteTrack lost-track timeout semantics:
  - removed `self.frame_id += 1` from `ByteTrackTrack.predict()`
  - `frame_id` now remains "last update/activation frame" as required for timeout logic

File:

- `ros2_ws/src/thesis_tracker/thesis_tracker/backends/bytetrack_backend.py`

## Positioning Statement

- Label OC-SORT implementation as: **"OC-SORT-aligned embedded backend"**
- Do not label as exact upstream OC-SORT because runtime uses local KalmanBox/matcher integration.

## Artefacts

- `reports/timing/ocsort_upgraded_20260426_185737.json`
- `reports/timing/bytetrack_upgraded_20260426_213133.json`
- `reports/timing/live_benchmark_ocsort_vs_bytetrack_2026-04-26.md`

## Commit Message (suggested)

```text
tracker: promote OC-SORT as live baseline; fix ByteTrack timeout semantics

- benchmark upgraded OC-SORT and ByteTrack with matched 120s live runs
- record OC-SORT as best live candidate (track_ms p95=5.526, det_hz=18.99)
- keep ByteTrack as viable rescue backend; document threshold-starved evaluation caveat
- fix ByteTrack lost timeout logic by keeping frame_id as last update frame
- add written log and timing benchmark notes for reproducibility
```
