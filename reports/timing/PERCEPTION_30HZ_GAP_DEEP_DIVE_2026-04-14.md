# Perception 30 Hz Gap Deep Dive (2026-04-14)

## Purpose

This document explains why detections do not reach 30 Hz even when tracker, target selector, and control are disabled, and identifies the dominant latency component from measured evidence.

## Question

Why is detection throughput around 8-11 Hz instead of 30 Hz, despite camera publish cadence near 30 FPS and downstream nodes being removable?

## Short Answer

The dominant bottleneck is inside the perception engine path before Hailo inference starts for each frame.

The largest latency component is:

- `t_pre_end_ns -> t_infer_start_ns` (pre-infer queue/wait)

This hidden interval is much larger than `infer_ms`, `post_ms`, or publish cost.

## Evidence Sources

- Timing reports:
  - `reports/timing/tracker_base_active_20260414_140437.json`
  - `reports/timing/tracker_tuned_active_20260414_142832.json`
- Live perception logs:
  - `ros2_ws/log/live_stack/2026-04-14__14-04-18/perception_pipeline.log`
  - `ros2_ws/log/live_stack/2026-04-14__14-28-13/perception_pipeline.log`
- Live `/timing` probe sample set (best-effort QoS, n=120)

## Measured Breakdown

### 1. Report-level decomposition (active workload runs)

From the two active runs above:

- `e2e_det_ms` mean is ~111 ms
- `pre_ms` mean is ~5.9-6.0 ms
- `infer_ms` mean is ~7.5-7.6 ms

Residual not explained by `pre_ms + infer_ms` is ~97 ms (about 88% of `e2e_det_ms`).

### 2. Live direct timing decomposition (n=120)

Measured directly from `/timing` timestamps and fields:

- `q_wait_ms (t_pre_end_ns -> t_infer_start_ns)`:
  - mean 83.267 ms
  - p50 80.755 ms
  - p95 96.677 ms
  - p99 99.851 ms
- `infer_ms`:
  - mean 6.266 ms
  - p95 8.847 ms
- `post_ms`:
  - mean 0.448 ms
  - p95 1.146 ms
- `det_pub_ms`:
  - mean 0.721 ms
  - p95 1.983 ms
- `e2e_det_ms`:
  - mean 94.431 ms
  - p95 109.864 ms

Interpretation:

- Most of `e2e_det_ms` is waiting before `t_infer_start_ns`, not detector compute.

### 3. Perception log corroboration (same session family)

From perception pipeline logs:

- `rt_ms` is commonly around ~85-121 ms, with higher spikes.
- `pub_dt_ms` shows long tails and burstiness.

This aligns with a queueing/scheduling bottleneck and nontrivial frame waiting before infer start.

## Why Disabling Tracker/Target/Control Is Not Enough

Removing downstream nodes can reduce total load and tails, but it does not remove the dominant pre-infer wait in perception.

As long as the pre-infer wait remains around ~80-100 ms, detector throughput cannot approach 30 Hz.

## Throughput Math

30 Hz requires approximately 33.3 ms per frame end-to-end.

Current typical per-frame budget (mean):

- `pre_ms` ~3.5 ms
- `infer_ms` ~6.3 ms
- `post_ms` ~0.4 ms
- `det_pub_ms` ~0.7 ms
- pre-infer wait ~83.3 ms

Total is near ~94 ms, which corresponds to about 10.6 Hz in the best case.

To reach 30 Hz without changing other terms, pre-infer wait must drop from ~83 ms to around ~22 ms or lower.

## Code-Path Context

Relevant perception path:

- Preprocess and callback path in `perception_pipeline_node.on_image`
- Synchronous `engine.infer(...)` wait in `HailoGstInferenceEngine.infer`
- `t_infer_start_ns` set at pre-hailonet probe
- GStreamer path includes appsrc queue and `videoconvert` before hailonet

This is consistent with observed delay accumulating before infer start.

## What Is Still Unknown

The exact share of the pre-infer wait attributable to each of these sub-causes is not yet isolated:

- appsrc to pre-hailonet queue backlog behavior
- `videoconvert` and format-path scheduling cost under load
- thread scheduling contention between ROS callback and GStreamer processing threads
- bursty system-level contention causing p95/p99 inflation

## Key Conclusion

The current bottleneck is not primarily Hailo infer compute time and not primarily tracker/downstream time.

The major limiter is pre-infer queue/wait inside the single-process perception engine path.

Any plan to reach 30 Hz must attack this pre-infer wait first.

## Fix Strategy (Prioritized)

### Priority 1: Remove pre-hailonet queueing/format bottleneck

Objective:

- cut `q_wait_ms (t_pre_end_ns -> t_infer_start_ns)` from ~83 ms mean to near ~20 ms.

Actions:

1. Eliminate avoidable work between appsrc and hailonet:
  - remove or bypass `videoconvert` if caps can be matched directly to what `hailonet` consumes.
  - verify that appsrc caps and hailonet expected format are aligned, so conversion is not occurring implicitly.
2. Re-check appsrc timestamping behavior:
  - avoid synthetic pacing artifacts from fixed `pts = seq * frame_duration` if they introduce downstream buffering.
  - use live-source timestamping policy consistent with actual push cadence.
3. Keep queue depth minimal at pre-hailonet stage:
  - preserve freshness-first behavior and avoid accumulating frames before infer start.

Expected impact:

- largest single-step reduction in `e2e_det_ms` and throughput ceiling lift.

### Priority 2: Decouple ROS callback from infer wait

Objective:

- prevent callback-side blocking from amplifying burstiness and pub interval tails.

Actions:

1. Move inference submission/wait into a dedicated worker path.
2. Keep a latest-frame policy (overwrite stale frame) so the worker always processes freshest input.
3. Keep `on_image` lightweight and non-blocking.

Expected impact:

- lower `pub_dt_ms` tails and better cadence stability.

### Priority 3: Trim residual pre-processing cost

Objective:

- reduce non-dominant but still material `pre_ms` cost.

Actions:

1. Remove duplicate color/resize operations where possible.
2. Prefer camera output closer to inference shape/format for ablation runs.

Expected impact:

- modest gains (single-digit ms), useful after Priority 1.

### Priority 4: Strengthen observability to prevent blind spots

Objective:

- make the dominant hidden delay visible in normal reports.

Actions:

1. Add canonical reporting for derived wait metrics:
  - `q_wait_ms = t_infer_start_ns - t_pre_end_ns`
  - `post_to_pub_ms = t_det_pub_end_ns - t_post_end_ns`
2. Keep existing comparability gates (`detections_per_msg.mean`, `zero_ratio`) for all paired baseline-vs-candidate tests.

Expected impact:

- faster root-cause confirmation and safer iteration.

## Execution Sequence

1. Implement Priority 1 changes and run a 10-minute perception-focused test (same scene/model).
2. Accept only if:
  - `q_wait_ms` mean drops by at least 40 ms
  - `e2e_det_ms` mean drops materially
  - no increase in timeout incidence.
3. Then apply Priority 2 and repeat identical 10-minute test.
4. Reintroduce tracker/target/control and verify full-stack regression gates.

## Success Criteria Toward 30 Hz

Near-term milestone:

- `q_wait_ms` mean <= 25 ms
- `e2e_det_ms` mean <= 40 ms
- `/timing` mean >= 20 Hz under active workload

Final milestone:

- sustained `/timing` mean near 30 Hz
- stable tails (`pub_dt_ms` p95/p99) without workload collapse (`zero_ratio` stays low)

## Investigation Plan (No Code Changes)

1. Run controlled paired baseline-vs-candidate comparisons with identical scene and model while sampling direct hidden interval metrics:
   - compare `q_wait_ms` distributions, not only `e2e_det_ms`.
2. Run short tests with fixed conditions and one variable at a time:
   - camera FPS input level
   - queue buffer depth setting
   - host load level (with and without dashboard/web video consumers)
3. Correlate `q_wait_ms` spikes with perception log `rt_ms` and `pub_dt_ms` tails.
4. Add one profiling session using existing tracing tooling (CTF traces) focused on pre-hailonet stage occupancy and queue wait.
5. Keep detection workload comparability gates active (`detections_per_msg.mean`, `zero_ratio`) during all comparisons.

## Decision Impact

- Current tuned tracker variant remains dropped for rollout.
- Next optimization effort should prioritize reducing pre-infer wait, since this is the dominant contributor to missed 30 Hz.
