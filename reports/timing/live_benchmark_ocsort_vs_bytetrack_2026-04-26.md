# Live Benchmark: OC-SORT vs ByteTrack (2026-04-26)

## Setup

- Command profile: `--profile daily`
- Tracker profiling flags:
  - `--tracker-timing-on`
  - `--tracker-gc-probe-off`
  - `--tracker-profile-log-every 30`
- Duration per run: `120 s`

## Run Artifacts

- OC-SORT JSON: `reports/timing/ocsort_upgraded_20260426_185737.json`
- ByteTrack JSON: `reports/timing/bytetrack_upgraded_20260426_213133.json`

## Critical ByteTrack Note

ByteTrack low-confidence rescue is currently limited by upstream detection thresholds.

Observed current live launcher behavior:

- Perception side is started with `-p min_score:=0.35` in `tools/start_live_stack.sh`.
- Tracker side is also started with `-p min_score:=0.35` in `tools/start_live_stack.sh`.

Implication:

- Detections below `0.35` are filtered before ByteTrack can use them.
- This starves the low-score rescue stage and makes ByteTrack behavior closer to standard IoU tracking.

For paper-faithful ByteTrack evaluation, target:

- Perception/detector `min_score <= 0.1` (or `0.2`)
- Tracker `min_score <= 0.1` (or `0.2`)
- ByteTrack `track_thresh ~ 0.5`
- ByteTrack `det_thresh ~ 0.1` (or `0.2`)

## Results Summary

### OC-SORT (upgraded)

- `track_ms p50`: `0.445 ms`
- `track_ms p95`: `5.526 ms`
- `track_ms p99`: `7.406 ms`
- `/detections Hz`: `18.988 Hz`

### ByteTrack (upgraded)

- `track_ms p50`: `1.855 ms`
- `track_ms p95`: `5.944 ms`
- `track_ms p99`: `7.903 ms`
- `/detections Hz`: `14.266 Hz`

## Comparison Against Frozen Baselines

Frozen references:

- SORT: `track_ms p50=2.40`, `p95=7.81`, `/detections Hz=16.87`
- DeepSORT hist: `track_ms p95=42.49`
- DeepSORT MARS: `track_ms p95=71.28`

Current run interpretation:

- OC-SORT `track_ms p95=5.526`: below `~12 ms` target band (good live candidate).
- ByteTrack `track_ms p95=5.944`: below `~12 ms` target band (good live candidate).
- Both are far below DeepSORT latency tails.

Caveat for fairness:

- ByteTrack's rescue stage is constrained by the current `min_score=0.35` upstream filtering.
- A follow-up run with low score floors is required for a true ByteTrack paper-style comparison.
