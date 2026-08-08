# Runtime and onboard resource characterization (Issue #32 / P1.14)

Status: canonical methodology frozen; first executed evidence slice
promoted. This is a **May-only, replay-plus-one-live-run finding**, not a
complete six-architecture x four-sequence characterization. It supplies the
schema and initial evidence Issue #58's cost axis is blocked on.

## Purpose

Establish the canonical embedded runtime/resource measurement methodology
for the thesis, per
[`docs/issues/p1-14-runtime-resource-characterization.md`](../../issues/p1-14-runtime-resource-characterization.md),
and measure the incremental cost of TIM-MARS for each Issue #58 architecture.

## Canonical links

- [Full engineering record](../../issues/p1-14-runtime-resource-characterization.md)
- [Runtime characterization manifest](../../data/runtime_characterization/p032_runtime_characterization_v1.yaml)
- [Replay-cost measurer](../../../tools/experiments/measure_p032_replay_cost.py)
- [Appearance-budget analyser](../../../tools/analysis/analyse_p032_appearance_budget.py)
- [Sustained ground-run launcher](../../../tools/experiments/run_p032_sustained_ground_run.sh)
- [Sustained-run acceptance analyser](../../../tools/analysis/analyze_p032_sustained_run.py)
- [Aggregate report builder](../../../tools/analysis/aggregate_p032_runtime_report.py)

## Live vs. replay (frozen distinction)

- **`replay_algorithmic_cost`**: deterministic, non-real-time batch replay
  of the tracker (and TIM, where enabled) against the frozen source bag's
  existing `/detections`. Valid for algorithm CPU-service-time, peak
  memory, and fair architecture comparison under identical input. Not a
  latency claim.
- **`live_sustained`**: real ROS 2 nodes (detector, tracker, TIM-MARS,
  dashboard bridge) executing live for a bounded duration, fed through the
  established Issue #44 timestamp-refresh replay relay at realistic
  cadence. Valid for true latency percentiles, cadence, backlog, thermal,
  and sustained CPU/memory. The source is a replayed recording, not a
  physically live camera.

## Results

### Replay algorithmic cost (all six architectures, May)

| Architecture | Tracker CPU (s) | TIM CPU (s) | Combined CPU (s) | Peak RSS (KiB) |
|---|---:|---:|---:|---:|
| `bytetrack_raw` | 28.697 | n/a | 28.697 | 119,332 |
| `bytetrack_tim` | 28.890 | 44.609 | 73.499 | 815,460 |
| `sort_raw` | 28.215 | n/a | 28.215 | 119,216 |
| `sort_tim` | 28.764 | 45.573 | 74.336 | 762,160 |
| `deepsort_raw` | 345.645 | n/a | 345.645 | 786,084 |
| `deepsort_tim` | 344.592 | 44.025 | 388.617 | 792,024 |

DeepSORT's internal appearance association costs ~12x ByteTrack/SORT's
tracker-stage CPU. TIM-MARS adds a consistent ~42-46 s regardless of
tracker. TIM's marginal memory cost is +696/+643 MB for ByteTrack/SORT but
only +5.9 MB for DeepSORT, which already keeps an appearance model
resident.

### Live sustained run (canonical `bytetrack_tim`, ~20 minutes)

All acceptance gates passed (`passed: true`, zero violations). Observed
duration 1205.4 s against a 1200.0 s request, 60 s warm-up excluded from
latency percentiles.

| Metric | Value |
|---|---|
| `e2e_det_ms` | p50 12.33 ms, p95 14.92 ms, p99 18.98 ms |
| `track_ms` | p50 3.79 ms, p95 10.44 ms, p99 12.79 ms |
| TIM core latency (live) | p50 41.6 ms, p95 78.9 ms, p99 83.8 ms |
| MARS extraction (live) | p50 46.5 ms, p95 79.9 ms, p99 83.6 ms |
| Temperature | 55.4-60.9 degC, zero throttle samples |
| CPU (mean) | tracker 78.5%, TIM 14.0%, perception 7.2%, dashboard 5.2%, relay 4.8% |

**Known limitation:** `e2e_target_ms` publishes as exactly `0.0` on every
sample. Diagnosed cause: `perception_pipeline_node` publishes
`/detections` before `/timing` for the same frame, so `tracker_node`'s
`frame_context` correlation almost always misses, and
`t_cam_msg_seen_ns` never reaches `dashboard_bridge_node`. This is a
genuine live-only finding (invisible to replay); recorded as unavailable,
not as a real near-zero latency. Full detail in the engineering record.

## Issue #58 integration

The output schema is keyed by `(architecture_id, sequence_id)` using
exactly Issue #58's six architecture identifiers and its
`dev_may_hard_reentry` / `dev_june_seq01` / `dev_june_seq03` /
`dev_june_seq04` sequence identifiers. #58 can join safety/availability
rows to #32's cost rows on that key without rerunning or re-interpreting
either issue's logs. This issue does not modify the parked
`issue-58-lightweight-vs-integrated-tracking` branch.

## Claim boundary

This is a May-only replay-cost matrix (all six architectures) plus one
canonical-architecture live sustained run. It supports:

- a fair, same-input CPU/memory comparison across all six Issue #58
  architectures on this sequence;
- genuine live latency, cadence, thermal, and resource evidence for the
  intended `bytetrack_tim` architecture specifically.

It does not support:

- any live-latency claim for `sort_*` or `deepsort_*` (replay CPU-cost
  only for those five architectures);
- any claim about Seq01/Seq03/Seq04 (not yet executed);
- a final controller-facing target-publication latency claim
  (`e2e_target_ms` diagnosed unavailable, see above);
- a power claim (no calibrated sensor);
- a raw-image transport/bandwidth claim (Issue #54 scope);
- Issue #32 completion.

## Provenance preservation

Compact evidence (replay-cost JSON per architecture, appearance-budget
JSON/Markdown, the aggregate JSON/CSV/Markdown, and the live sustained
run's run metadata, sustained-run analysis, live timing summary,
appearance budget, resource/health summaries, and relay summary) with
`SHA256SUMS` is in
[`p032_runtime_characterization_development/`](p032_runtime_characterization_development/).
Generated per-cell replay bags, the live evidence `.mcap` bag
(`bags/replay/p032_ground_run_331ccc24_2026_08_08_dev_may_hard_reentry/evidence`,
SHA-256
`6a67cb9324a9cfb785a638fbe9893f711f772406fd3f1e628f871cb1f61c7c49`), and
raw per-sample JSONL streams remain git-ignored and local, regenerable
from the tracked manifest and scripts against the frozen source/reference
bags.
