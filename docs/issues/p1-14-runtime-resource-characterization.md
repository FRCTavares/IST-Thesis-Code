# P1.14 End-to-End Runtime, Compute Budget, and Onboard Resource Characterisation

GitHub Issue: #32
Branch: `issue-32-runtime-resource-characterization`
Baseline: `6231fdc1370b78a55ffeee9a403adbbddf4fb424` (main after Issue #31's PR #72 merge)

## Objective

Establish the canonical embedded runtime/resource measurement methodology
for the thesis: per-stage latency decomposition, cadence/jitter/backlog,
CPU and memory cost, selective-appearance (TIM-MARS) budget, sustained
thermal/frequency behaviour, and (where a calibrated source exists) power.
This is the methodology and evidence Issue #58's cost axis is blocked on.

This issue does not retune the canonical TIM-MARS configuration, does not
change canonical tracker configs, and does not modify the parked
`issue-58-lightweight-vs-integrated-tracking` branch.

## Audit of existing instrumentation

Before adding anything, the repository was searched for existing
timing/resource primitives. Reusable and already-validated:

- `tools/timing_contract.py` -- canonical `/timing` field names, fallbacks,
  thresholds.
- `ros2_ws/src/thesis_msgs/msg/Timing.msg` -- already carries a full
  per-stage timestamp decomposition (camera callback through detector
  publish; container unpack/infer/post/reply; tracker callback; target
  callback).
- `tools/analysis/collect_live_timing_stats.py` -- live ROS collector for
  `/timing`, `/timing_tracker`, `/timing_target`: p50/p95/p99/mean per
  field, achieved Hz, frame-ID continuity (gaps/duplicates/missing
  estimate), cadence-consistency check. This is the live latency/cadence
  collector; reused unmodified as the `live_sustained` measurement source.
- `tools/analysis/check_live_timing_invariants.py` -- live timestamp
  monotonicity/ordering/non-negativity invariant checker. Reused as the
  pre-run smoke gate before any long sustained run.
- `tools/analysis/analyse_bag_timing.py` -- offline/replay percentile and
  active-window analysis for `/timing`.
- `tools/experiments/sample_process_groups.py` -- per-process-group (by
  PGID) CPU%/RSS sampler with percentile summaries. Reused unmodified for
  the CPU/memory dimension.
- `tools/experiments/sample_p044_hardware_health.py` -- `vcgencmd`-based
  temperature/throttled/ARM-frequency/core-voltage sampler plus
  `/proc/meminfo` and load average. Despite the P044 name this is a
  generic Raspberry Pi hardware-health sampler; reused unmodified for the
  thermal/frequency dimension.
- `tools/analysis/analyse_tim_reid_workload.py` -- appearance/ReID
  workload analyser reading `/target_memory_mars/status`
  (`read_status_records`, `analyse_records`). Reused (imported, not
  duplicated) as the basis for the new selective-appearance-budget
  analyser below.
- `tools/experiments/p044_soak_input_relay.py`,
  `tools/experiments/analyze_p044_sustained_soak.py` -- the established
  pattern (and, for the analyser, directly reusable generic percentile/
  windowing/drift-check functions) for running a bounded sustained soak by
  relaying a recorded bag onto live topics that real nodes consume, then
  validating early/middle/late drift.
- `tools/experiments/run_deterministic_tracker_replay.py`,
  `tools/experiments/run_deterministic_tim_replay.py` -- deterministic,
  non-real-time batch replay runners (confirmed by source inspection: "no
  ROS playback or executor scheduling"). Valid for algorithm compute-cost
  and architecture comparison under identical input; not valid for latency
  claims.

Genuine gaps filled by this issue:

- No manifest tied runtime measurements to Issue #58's architecture IDs.
- No orchestrator ran the identical protocol across all six #58
  architectures.
- No selective-appearance-budget analyser computed candidates/s,
  embeddings/s, fraction of frames invoking appearance, or a cache-hit-rate
  estimate (the raw counters already existed in the TIM-MARS status
  payload; nothing published a derived budget summary from them).
- No sustained live/onboard run script existed outside Issue #44's
  ReID-transport-specific soak (which is not directly reusable: its
  preflight hard-codes `EXPECTED_BRANCH=issue-44-selective-hailo-reid` and
  its stack wires Hailo ReID request/result transport that Issue #32's
  canonical CPU-MARS baseline does not use).

### A methodological finding from the audit itself

`tools/experiments/run_deterministic_tim_replay.py` hardcodes
`lat_ms=0.0` and `appearance_backend_wall_ms=0.0` (verified by source
inspection at the two call sites that construct the status message). The
deterministic replay path performs no real-time wall-clock measurement at
all. Before this was discovered, an early version of the new appearance-
budget analyser reported these as literal `0.000 ms` percentiles from
replay evidence -- an implausible, fabricated zero-latency claim. The
analyser was corrected to report `null` with an explicit
`latency_unavailable_reason` whenever it runs in `replay_algorithmic_cost`
mode, and only report real percentiles in `live_sustained` mode. This is
recorded here because it is exactly the kind of measurement-boundary error
Issue #32 exists to prevent, and because a prior repository result
(`docs/results/selected_target_tracking/hard_reentry_compute_throughput_summary.md`,
2026-05-27) used whole-replay `/usr/bin/time -v` elapsed time in a way this
issue's own text explicitly warns against ("not simply run `time` around a
replay script"). That prior result already carried a cautionary note; this
issue's `replay_algorithmic_cost` mode formalises the same caution as an
enforced null rather than a prose caveat.

## Methodology

### Live vs. replay (frozen)

- **`replay_algorithmic_cost`** -- deterministic, non-real-time batch
  replay of the tracker (and TIM, where enabled) backend against the
  frozen source bag's existing `/detections` stream. Executed via
  `tools/experiments/measure_p032_replay_cost.py`, which invokes the
  existing unmodified replay runners as subprocesses and records their
  whole-process resource usage (wall time, user/system CPU, peak RSS) via
  POSIX child `rusage` accounting (`os.wait4`/`resource.getrusage`
  semantics, one measured child per script invocation so
  `RUSAGE_CHILDREN` is unambiguous). Valid for: reproducibility, algorithm
  CPU-service-time, peak memory, fair architecture-to-architecture
  comparison under identical input. Not valid for: real-time latency,
  cadence, jitter, or backlog.
- **`live_sustained`** -- real ROS 2 nodes (perception detector, tracker,
  TIM-MARS) executing live on the Raspberry Pi 5 for a bounded sustained
  duration. Source imagery is supplied through the established Issue #44
  timestamp-refresh relay (`p044_soak_input_relay.py`), republishing
  recorded frames/tracks onto the live topics the real nodes consume at
  realistic cadence. This is not a physically live camera capture and is
  not offline batch replay: the nodes, hardware, and Hailo accelerator are
  real; the source is a replayed recording. Executed via
  `tools/experiments/run_p032_sustained_ground_run.sh`. Valid for: true
  end-to-end wall-clock latency distributions, real cadence/jitter,
  backlog, detector/Hailo contention, sustained thermal/frequency
  behaviour, sustained CPU/memory behaviour.

### Warm-up, duration, sampling cadence (frozen before any run)

- Warm-up: 60 s. The live timing collector starts only after the warm-up
  window elapses (implemented by delaying its launch, not by post-hoc
  filtering), so latency percentiles exclude warm-up by construction.
  Resource and hardware-health sampling span the full run including
  warm-up, so settling behaviour is visible in those series.
- Minimum sustained duration: 900 s (15 minutes).
- Sampling cadence: process-group CPU/RSS every 1.0 s; hardware health
  (temperature/frequency/voltage/memory/load) every 5.0 s.

### Architectures and join schema

Architecture IDs match Issue #58 exactly:
`bytetrack_raw`, `bytetrack_tim`, `sort_raw`, `sort_tim`, `deepsort_raw`,
`deepsort_tim`. The manifest
(`docs/data/runtime_characterization/p032_runtime_characterization_v1.yaml`)
freezes each architecture's tracker config path/hash, the canonical
TIM-MARS config/hash, and the MARS model/hash -- all independently
re-verified against #58's/#31's provenance and matched exactly (see
"Provenance verification" below).

The manifest is self-contained on `main`: it does not read or depend on
any file that lives only on the parked `issue-58-*` branch. The join is a
schema contract (`architecture_id`, `sequence_id`), not a file dependency.

### Fairness contract

Every replay measurement uses `--selection-mode fixed_id
--selected-track-id <manifest selected_target_id>`, matching the same
physical target Issue #58 selects for the same sequence, rather than each
tracker's own autonomous largest-track selection -- so architecture
comparisons are not confounded by different trackers locking onto
different people.

### Selective appearance budget

`tools/analysis/analyse_p032_appearance_budget.py` reuses
`analyse_tim_reid_workload.read_status_records` and adds the budget
metrics Issue #32 asks for that the existing analyser did not compute:
candidates encoded/s, embeddings/s, fraction of frames invoking
appearance, and a cache-hit-rate estimate. The cache-hit-rate is derived
from already-published counters
(`appearance_features_valid` in excess of fresh
`appearance_backend_valid`), not a new instrumentation point, since the
TIM-MARS status payload already tracks per-track embedding cache age and
cache size but does not publish a dedicated hit/miss counter.

### Provenance verification

Before any measurement, source bag, tracker config, TIM config, and MARS
model hashes are independently re-hashed and compared against the
manifest's frozen values. `measure_p032_replay_cost.py` fails closed
(`SystemExit`, no measurement attempted) on any mismatch. All four
canonical hashes were independently re-verified during this issue's audit
and matched the values already established by Issues #31/#58:

| Artifact | SHA-256 |
|---|---|
| `tim_mars_canonical.yaml` | `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931` |
| `mars-small128.pb` | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` |
| `tracker_bytetrack.yaml` | `e0e5c7c80a2f2b74cb6640e2ea90d9651c33f193c34365dc0d5a7ac9badaa906` |
| `tracker_sort.yaml` | `78051b9606cae6d2f6c8de25bffe38d26697e2edf153a9961bbf31934016319c` |
| `tracker_deepsort.yaml` | `d586e2e04c283313606cb366b64c0e7bad19692207f185d7dd9b89c89e33efb0` |
| May source bag (`..._raw_0.mcap`) | `becad555aa8150ea969448316f1478786743a76cde266b20b574d32af7602839` |

### Power

No calibrated power sensor (INA219/INA226-class) is installed on this
hardware. Per the issue's own instruction, power is recorded as
`unavailable_no_calibrated_sensor`, never estimated from software/clock
state.

## Workload

Scoped first to `dev_may_hard_reentry`: the only development sequence with
complete cross-architecture safety/availability evidence in Issue #58
(May-only finding). This keeps #32's first executed slice directly
joinable with #58's completed comparison rather than measuring cost on
sequences #58 cannot yet pair it with. Seq01/Seq03/Seq04 runtime
characterisation is explicitly future #32 work (see "Not yet done"), not
silently implied complete.

## Execution

### Replay algorithmic-cost matrix (all six architectures, May)

Executed via `tools/experiments/measure_p032_replay_cost.py` against
`dev_may_hard_reentry`. All six succeeded; results in
`docs/results/selected_target_tracking/p032_runtime_characterization_development/`.

| Architecture | Tracker total CPU (s) | TIM total CPU (s) | Combined CPU (s) | Peak RSS (KiB) |
|---|---:|---:|---:|---:|
| `bytetrack_raw` | 28.697 | n/a | 28.697 | 119,332 |
| `bytetrack_tim` | 28.890 | 44.609 | 73.499 | 815,460 |
| `sort_raw` | 28.215 | n/a | 28.215 | 119,216 |
| `sort_tim` | 28.764 | 45.573 | 74.336 | 762,160 |
| `deepsort_raw` | 345.645 | n/a | 345.645 | 786,084 |
| `deepsort_tim` | 344.592 | 44.025 | 388.617 | 792,024 |

Findings:

- DeepSORT's tracker stage costs roughly 12x ByteTrack/SORT's (~345 s vs
  ~28-29 s total CPU over the same 953-frame sequence) -- its internal
  appearance-based association is the dominant cost, not simple IoU
  matching.
- TIM-MARS adds a consistent ~42-46 s CPU regardless of which tracker
  feeds it, since it processes the same candidates for the same target on
  the same source frames (candidates encoded: 448-452 across all three;
  cache-hit-rate estimate ~0.75 across all three).
- TIM's marginal peak-RSS cost is architecture-dependent: +696 MB for
  ByteTrack, +643 MB for SORT, but only +5.9 MB for DeepSORT -- DeepSORT
  already keeps an appearance/ReID model resident, so TIM's own MARS
  model does not add a second large footprint on top of it the way it
  does for the lightweight trackers.
- These are `replay_algorithmic_cost` totals (deterministic, non-real-time
  batch processing): valid for architecture-to-architecture CPU/memory
  comparison under identical input, not a live-latency claim.

### Live sustained ground run (canonical `bytetrack_tim`, ~20 minutes)

Reaching a valid sustained run required five methodology-preserving fixes
to the launch script across six attempts (none produced retained partial
evidence -- every aborted attempt's output was inspected, confirmed
non-promotable, and removed before the next attempt):

1. Preflight correctly rejected a stray root `hailort.log` left by an
   earlier unrelated command in this session; removed, not a script bug.
2. The pre-run smoke check originally ran before bag playback started, so
   every topic had zero samples; reordered to run after playback begins.
3. No live `tracker_node` ran -- track output was replayed pre-recorded
   data, so `/timing_tracker` could never be published by construction.
   Added a live ByteTrack `tracker_node` between perception and TIM-MARS.
4. No live `dashboard_bridge_node` ran -- it is the sole publisher of
   `/timing_target`. Added it headless (`ws_port:=0`, `api_port:=0`),
   matching the existing `eval_replay.launch.py` precedent that already
   pairs `tracker_node` with `dashboard_bridge_node` this way.
5. `tracker_node` and `dashboard_bridge_node` each publish one placeholder
   Timing message with `frame_id=0` before their first real callback; the
   smoke check's first captured sample caught it. Added an 8s, then a 15s
   settle (to also let the 3-second cadence-consistency rolling window
   fill) before the checker subscribes.

Final run: exit 0, all gates passed (`sustained_analysis.json`
`"passed": true`, `"violations": []`). Evidence bag SHA-256
`6a67cb9324a9cfb785a638fbe9893f711f772406fd3f1e628f871cb1f61c7c49`.

| Metric | Value |
|---|---|
| Requested / observed duration | 1200.0 s / 1205.4 s |
| Warm-up (excluded from latency percentiles) | 60.0 s |
| Post-warm-up timing-collector window | 1140.1 s |
| Source loop repetitions | 17 (68 s clip) |
| `/timing` `e2e_det_ms` | p50 12.33 ms, p95 14.92 ms, p99 18.98 ms |
| `/timing_tracker` `track_ms` | p50 3.79 ms, p95 10.44 ms, p99 12.79 ms |
| TIM core latency (`lat_ms`, live) | p50 41.6 ms, p95 78.9 ms, p99 83.8 ms |
| MARS extraction (`appearance_backend_wall_ms`, live) | p50 46.5 ms, p95 79.9 ms, p99 83.6 ms |
| Cadence consistency | within tolerance (relative delta 0.212, max 0.35) |
| CPU (process-group, mean) | perception 7.2%, tracker 78.5%, TIM 14.0%, dashboard 5.2%, relay 4.8% |
| Peak RSS (mean) | perception 219 MB, tracker 137 MB, TIM 824 MB, dashboard 106 MB, relay 76.5 MB |
| Temperature | 55.4-60.9 degC, zero throttle samples (240/240) |
| ARM frequency | 1.50-2.40 GHz (dynamic) |
| Available memory | 5.95-6.59 GB, no drift violation |
| Appearance budget (live) | 60.8% of frames invoke fresh appearance; cache-hit-rate estimate 0.369; 2.47 candidates encoded/s |

`tracker_node`'s live CPU% (mean 78.5% of one core-equivalent, sustained)
is proportionally much higher than the replay pass's ~30 ms/frame implies
for ByteTrack at this cadence -- a genuine live-vs-replay divergence
(executor/spin overhead, not present in a tight deterministic batch loop)
rather than a discrepancy to reconcile; the two measurement modes are
reported separately and must not be blended into one number.

## Superseded evidence

The first sustained run (tag `p032_ground_run_331ccc24_2026_08_08_dev_may_hard_reentry`,
commit `be19b16c`, promoted at the same commit) is superseded **only for
`e2e_target_ms`/`sensor_to_target_ms`**, which that run recorded as always
exactly `0.0` due to the bug diagnosed and fixed below. Every other metric
from that run (`e2e_det_ms`, `track_ms`, TIM core/MARS extraction latency,
appearance budget, CPU, RSS, thermal, cadence) is unaffected by this bug
and remains valid; it is not re-promoted here only because the corrected
run (`dev_may_hard_reentry_corrected`, commit `7e51e79a`/`f9746979`)
reproduces it under the identical frozen protocol with the additional
correct `e2e_target_ms` evidence. The original run's promoted files and
this record's git history (commit `be19b16c`) remain available and are
not deleted or rewritten.

## e2e_target_ms: root cause, fix, and corrected sustained run (09-08-26)

### Diagnosis

The first sustained run (08-08-26) found `/timing_target`'s `e2e_target_ms`
(and `sensor_to_target_ms`) published as exactly `0.0` on every one of 3867
samples. Source inspection: `dashboard_bridge_node._publish_target_from_tracks`
only sets `e2e_target_ms` when the incoming `/tracks` message's
`t_cam_msg_seen_ns` is `> 0`; that field is populated in `tracker_node`
from a `frame_context` dictionary keyed by `frame_id` and filled by a
*separate* `/timing` subscription callback.

Inspecting the installed rclpy `SingleThreadedExecutor` source
(`/opt/ros/jazzy/lib/python3.12/site-packages/rclpy/executors.py`,
`Executor._wait_for_ready_callbacks`) showed it dispatches ready callbacks
in `node.subscriptions` *registration* order, not message-arrival order:
`for sub in node.subscriptions: if sub.handle.pointer in subs_ready: ...
yield`. `tracker_node` registered `/detections` before `/timing`, so
`on_detections` was *always* dispatched first whenever both were ready
together -- deterministic, not an occasional race. This ruled out
reordering `perception_pipeline_node`'s publish calls as a fix (the
consumer's dispatch order was the actual point of control, not the
producer's send order).

### Fix

- `tracker_node` now registers `/timing` before `/detections`
  (`f9746979`), so `on_timing` populates `frame_context` before
  `on_detections` needs it whenever both are ready in the same executor
  cycle. Dict lookup by exact integer `frame_id` already made
  mismatched-frame pairing structurally impossible; the defect was purely
  silent unavailability.
- Widened `/timing`'s subscription queue depth 1 -> 20 (`7e51e79a`) on the
  hypothesis that BEST_EFFORT depth=1 could silently evict an
  arrived-but-unprocessed `/timing` message under CPU contention; smoke
  testing showed this made no measurable difference (ruling out queue
  eviction as the dominant cause) but was kept as a strictly-safer
  defensive change.
- Extracted the correlation write path (`_store_frame_context`) and the
  `e2e_target_ms` computation (`dashboard_bridge_node._compute_e2e_target_ms`)
  into pure, directly-testable functions with 14 new focused tests,
  including a static check that `/timing` is registered before
  `/detections` and a static check that the tracking `backend.update()`
  call never references timing-context state (tracker/TIM decisions
  unchanged).

### Residual gap: not fully closed, and why

Live smoke testing after the fix showed genuine non-zero `e2e_target_ms`
values for the first time, but only on a partial fraction of frames
(smoke: ~20-25%). Investigation found this is a **producer-side temporal
gap**, not a dispatch-order or queue problem: `/timing`'s own fields
(`t_det_pub_start_ns`, `t_det_pub_end_ns`, `e2e_det_ms`) are only known
*after* `/detections` has already been published, so `/timing`
structurally cannot be published before `/detections` without
restructuring what fields it carries. When `tracker_node`'s executor
dispatches `on_detections` in an isolated wait-cycle before
`perception_pipeline_node` has even sent the matching `/timing` message
(not merely before it has been read), no consumer-side fix -- dispatch
order or queue depth -- can help, because the needed message does not
exist yet at dispatch time.

Confirmed `Detection2DArray.header.stamp` cannot substitute as a
correlation source: it carries the *source camera's wall-clock*
timestamp (`frame.stamp_sec`/`stamp_nanosec`, from the original Image
message's own header), not the host-monotonic arrival time
(`t_cam_msg_seen_ns`) the tracker/TIM measurement chain requires --
substituting it would silently change what is being measured.

A frame-keyed buffering/join mechanism was considered (deferring
`/tracks` publication in `on_detections` until the matching `/timing`
message arrives, rather than publishing immediately with whatever
context is available). This was **not implemented**: it would delay
`/tracks` publication -- the live control-path signal TIM-MARS and
ultimately the flight controller depend on -- which is a materially
larger, real-time-behaviour-affecting architectural change, not a
timing-only instrumentation fix, and was assessed as out of scope for
this issue rather than expanded into indefinitely.

### Corrected sustained run and representativeness (`dev_may_hard_reentry_corrected`, 09-08-26)

Same frozen protocol (`bytetrack_tim`, 1200 s requested / 1205.5 s
observed, 60 s warm-up, same workload/config/sampling cadence). All
acceptance gates passed (`passed: true`, zero violations). Evidence bag
SHA-256
`0c95ec33fa554ab4bb28ee2269aa6005761b5af94c5b9ad6956a42350a8644fb`;
report:
`reports/p032_ground_run_7e51e79a_2026_08_09_dev_may_hard_reentry_corrected`.

`tools/analysis/analyse_p032_e2e_target_latency.py` computes percentiles
only over genuinely-correlated samples (`e2e_target_ms > 0`), never mixed
with the unavailable-sentinel zeros -- `collect_live_timing_stats.py`'s
raw percentiles would otherwise report a misleading `p50 = 0.0 ms`
(median falling inside the ~75% zero block).

| Metric | Value |
|---|---:|
| Total `/timing_target` samples | 4109 |
| Genuine (correlated) measurements | 1038 |
| Unavailable-sentinel samples | 3071 |
| Coverage rate | 25.26% |
| `e2e_target_ms` p50 (conditional) | 19.66 ms |
| `e2e_target_ms` p90 (conditional) | 26.90 ms |
| `e2e_target_ms` p95 (conditional) | 30.60 ms |
| `e2e_target_ms` p99 (conditional) | 39.28 ms |
| `e2e_target_ms` max (conditional) | 52.39 ms |

**Representativeness** (`tools/analysis/analyse_p032_e2e_target_correlation_representativeness.py`,
same-`frame_id` exact lookups within the recorded bag, no cross-clock-domain
joining involved):

- *Temporal stability*: coverage rate across 10 equal-duration windows
  spanning the full run ranged 21.5%-28.1% (mean ~25%), with a
  last-window/first-window ratio of 0.90 -- within sampling noise for
  ~400 samples/window (expected binomial std dev ~2.2 points), no
  monotonic drift, no warm-up-specific effect (the first window, which
  includes the tail of warm-up, measured 27.6%, *above* the run mean).
  Zero `/timing_target` frame-ID gaps (no backlog/drops).
- *Covariate association*: misses show **no** association with
  detector-side latency or cadence -- `e2e_det_ms` hit-mean 12.68 ms vs
  miss-mean 12.68 ms; `pub_dt_ms` hit-mean 291.7 ms vs miss-mean 291.1 ms
  (both essentially identical). Misses show a **real** association with
  tracker compute latency -- `track_ms` hit-median 1.77 ms vs miss-median
  4.13 ms (~2.3x), hit-mean 3.24 ms vs miss-mean 4.85 ms (~1.5x).

**Classification** (Option C, qualified): coverage remains moderate
(25.26%) and the valid subset is **not fully representative** -- it is
demonstrably unbiased with respect to detector cadence/latency but
demonstrably skewed toward *lower*-tracker-latency frames. Since higher
`track_ms` frames are undersampled in the measured (hit) group and
plausibly correlate with genuinely higher end-to-end latency, the
reported conditional percentiles are treated as a **likely mild
underestimate** of the true unconditional tail latency, not a validated
unconditional measurement. `p95/p99 target latency` is therefore recorded
as **NOT YET MET** as an unqualified pipeline-wide criterion, while the
conditional evidence above is retained as genuine, useful, non-fabricated
measurement (a real improvement over the prior always-zero state).

**`end-to-end target p95 <= 200 ms`**: no such threshold is documented
anywhere in this repository (`grep`-verified against `docs/`). The closest
documented reference is `tools/timing_contract.py`'s
`METRIC_WARN_THRESHOLDS["e2e_target_ms"] = 150.0` -- a soft dashboard
*warn* indicator, not a formal acceptance gate. The measured conditional
p95 (30.60 ms) and p99 (39.28 ms) are comfortably under both the
suggested 200 ms and the documented 150 ms warn threshold, with enough
margin (4-6x) that the discovered track_ms-based bias is very unlikely to
change this qualitative picture -- but per the representativeness finding
above, this is reported as directionally reassuring evidence, not a
certified pass against an undocumented or informal threshold.

## Not yet done

- Live sustained characterisation is scoped to the canonical architecture
  (`bytetrack_tim`) for this execution slice; a full six-architecture live
  comparison remains future work.
- Seq01/Seq03/Seq04 runtime characterisation (blocked on nothing
  technical; simply not yet executed).
- Any cross-architecture live-latency claim (only replay CPU-cost is
  measured across all six architectures in this slice).
- Full (near-100%) `e2e_target_ms` correlation coverage: the residual gap
  is a producer-side temporal dependency; closing it fully would require
  restructuring `perception_pipeline_node`'s publish sequencing or a
  frame-keyed deferred-publish buffer in `tracker_node`, either of which
  is a live control-path behaviour change outside a timing-only
  instrumentation fix (see the residual-gap analysis above).
- An unqualified/unconditional `e2e_target_ms` p95/p99 acceptance claim
  (conditional evidence exists and is documented; representativeness is
  partially, not fully, established).
- Power (no calibrated sensor installed).
**Resolved external dependency — raw-image DDS/QoS transport.**
Issue #54 was completed and merged through PR #73
(`49744968a8c8189a83add20740c3f688a95fe21a`). Its independent onboard
camera-transport experiment measured `/camera/image_raw` at `29.63 Hz`
and `27.10 MB/s` DDS traffic for `640x480 bgr8`, nominal 30 FPS, with
`+7.08` percentage points of one CPU core and approximately `+326 KiB`
RSS when publication was enabled. The analytical raw-payload estimate
(`27.65 MB/s`, `26.37 MiB/s`) remains explicitly distinct from measured
DDS bandwidth. This transport-layer result is not retroactively treated
as part of Issue #32's sustained `bytetrack_tim` run; it is joined as
independent canonical evidence from
`docs/results/live/p054_raw_image_transport_cost.md`.
