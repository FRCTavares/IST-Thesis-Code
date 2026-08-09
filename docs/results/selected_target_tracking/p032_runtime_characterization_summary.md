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
- [Corrected e2e_target_ms latency analyser](../../../tools/analysis/analyse_p032_e2e_target_latency.py)
- [e2e_target_ms correlation representativeness analyser](../../../tools/analysis/analyse_p032_e2e_target_correlation_representativeness.py)
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

### Live sustained run (canonical `bytetrack_tim`, ~20 minutes, corrected 09-08-26)

All acceptance gates passed (`passed: true`, zero violations). Observed
duration 1205.5 s against a 1200.0 s request, 60 s warm-up excluded from
latency percentiles. This run (tag `dev_may_hard_reentry_corrected`,
commit `7e51e79a`) supersedes the 08-08-26 run's `e2e_target_ms` field
only; every other metric from that run remains valid (see the engineering
record's "Superseded evidence" section).

| Metric | Value |
|---|---|
| `e2e_det_ms` | p50 12.20 ms, p95 14.90 ms, p99 20.00 ms |
| `track_ms` | p50 3.67 ms, p95 10.71 ms, p99 13.35 ms |
| TIM core latency (live) | p50 41.6 ms, p95 78.9 ms, p99 83.8 ms |
| MARS extraction (live) | p50 46.5 ms, p95 79.9 ms, p99 83.6 ms |
| Temperature | 55-61 degC, zero throttle samples |
| CPU (mean) | tracker ~78%, TIM ~14%, perception ~7%, dashboard ~5%, relay ~5% |

**`e2e_target_ms` -- fixed, but only conditionally representative.** The
previous run's always-`0.0` `e2e_target_ms` was a genuine bug: `tracker_node`
registered its `/timing` subscription *after* `/detections`, and rclpy's
`SingleThreadedExecutor` dispatches ready callbacks in registration order
-- proven by inspecting the installed executor source, not assumed.
Fixed (`f9746979`) by registering `/timing` first. This raised coverage
from 0% to a genuine, non-fabricated **25.26%** (1038/4109 samples), with
a residual gap traced to a producer-side temporal dependency
(`/timing`'s own fields require `/detections` to already be published, so
it cannot be sent first) that a consumer-side fix alone cannot fully
close without delaying live `/tracks` publication -- a real-time
control-path change judged out of scope for a timing-only fix.

Representativeness was tested explicitly, not assumed: coverage is
temporally stable (21.5-28.1% across 10 windows spanning the full run, no
drift, no warm-up effect) and shows **no** association with detector-side
cadence/latency, but **does** show a real association with tracker
compute latency (misses have ~2.3x higher median `track_ms` than hits).
The conditional percentiles below are therefore genuine measured evidence,
likely a **mild underestimate** of the true unconditional tail, not a
certified unconditional result:

| Percentile | `e2e_target_ms` (conditional, n=1038) |
|---|---:|
| p50 | 19.66 ms |
| p90 | 26.90 ms |
| p95 | 30.60 ms |
| p99 | 39.28 ms |
| max | 52.39 ms |

No `end-to-end target p95 <= 200 ms` threshold is documented anywhere in
this repository. The closest documented reference,
`tools/timing_contract.py`'s 150 ms dashboard *warn* threshold (not a
formal gate), is comfortably cleared by the measured p95/p99 with a 4-6x
margin -- directionally reassuring, but not presented as a certified pass
given the coverage caveat above. Full derivation, the representativeness
methodology, and the A/B/C classification are in the engineering record.

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
- an **unconditional** final controller-facing target-publication latency
  claim (`e2e_target_ms` is now genuinely measured, but only for 25.26%
  of frames, with a demonstrated mild bias toward lower-tracker-latency
  samples -- conditional evidence only, see above);
- a power claim (no calibrated sensor);
- Issue #32 completion.

The previously excluded raw-image transport/bandwidth claim is now backed
by independently merged Issue #54 evidence (PR #73): at `640x480 bgr8`,
nominal 30 FPS, `/camera/image_raw` achieved `29.63 Hz` and measured
`27.10 MB/s` DDS traffic when enabled. The distinct analytical payload
estimate is `27.65 MB/s` (`26.37 MiB/s`). Enabling raw publication added
`7.08` percentage points of one CPU core and approximately `326 KiB` RSS.
This is camera-transport evidence, not a six-architecture tracker/TIM
runtime comparison, and therefore does not by itself complete Issue #32.

## Provenance preservation

Compact evidence (replay-cost JSON per architecture, appearance-budget
JSON/Markdown, the aggregate JSON/CSV/Markdown, and the corrected live
sustained run's run metadata, sustained-run analysis, live timing summary,
appearance budget, resource/health summaries, relay summary, corrected
`e2e_target_ms` percentiles, and correlation-representativeness analysis)
with `SHA256SUMS` is in
[`p032_runtime_characterization_development/`](p032_runtime_characterization_development/).
Generated per-cell replay bags, the live evidence `.mcap` bags
(corrected run:
`bags/replay/p032_ground_run_7e51e79a_2026_08_09_dev_may_hard_reentry_corrected/evidence`,
SHA-256
`0c95ec33fa554ab4bb28ee2269aa6005761b5af94c5b9ad6956a42350a8644fb`;
superseded-for-`e2e_target_ms`-only run:
`bags/replay/p032_ground_run_331ccc24_2026_08_08_dev_may_hard_reentry/evidence`,
SHA-256
`6a67cb9324a9cfb785a638fbe9893f711f772406fd3f1e628f871cb1f61c7c49`), and
raw per-sample JSONL streams remain git-ignored and local, regenerable
from the tracked manifest and scripts against the frozen source/reference
bags.
