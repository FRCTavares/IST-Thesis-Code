# Runtime Metrics

This document defines the current runtime metrics used by the thesis live stack
and Issue #32.

The current contract is **Timing schema v4**. It describes only the current
direct/in-process Hailo architecture. Old container, Docker, and ZMQ timing
fields are not compatibility aliases and are not part of this schema.

## Timing topics

| Topic | Purpose |
| --- | --- |
| `/timing` | Detector input, preprocessing, direct-Hailo inference, detector publication, and detector cadence. |
| `/timing_tracker` | Tracker backend compute. |
| `/timing_target` | Validated TIM-MARS processing and end-to-end controller-authority latency. |

`/timing_target` is published by TIM-MARS because TIM-MARS is the selected
person identity authority. Raw `/target` timing is not a substitute for
validated target timing.

## Clock domains

Three timing concepts must remain separate.

1. **Source timestamp metadata** — `src_stamp_ns` comes from the source image
   header. Its clock may differ from the host clock.
2. **Host-monotonic stage timestamps** — the `t_*_ns` detector, tracker, and
   TIM-MARS timestamps are measured with the host monotonic clock and can be
   subtracted from one another when they belong to the same causal frame.
3. **Measured wall/service durations** — fields such as `infer_ms`,
   `track_ms`, `tim_mars_processing_ms`, and `appearance_backend_wall_ms`
   describe elapsed execution time around a specific operation.

Do not subtract `src_stamp_ns` from host-monotonic timestamps unless clock
comparability has been explicitly established for the run.

## Canonical Timing schema v4 metrics

| Metric | What it measures | Why it is used |
| --- | --- | --- |
| `ros_wait_ms` | Host-monotonic time from the perception image callback observing a frame until detector preprocessing starts. | Shows callback/scheduler delay before detector work begins. |
| `pre_ms` | Total detector preprocessing duration. | Measures host preprocessing cost before direct Hailo inference. |
| `ros_to_np_ms` | ROS image-to-NumPy conversion work within preprocessing. | Locates image-conversion overhead. |
| `resize_ms` | Detector resize work within preprocessing. | Locates resize overhead. |
| `color_ms` | Detector colour-conversion work within preprocessing. | Locates colour-format overhead. |
| `pre_infer_wait_ms` | Time from preprocessing completion until direct Hailo inference begins. | Detects in-process scheduling, queueing, or backpressure immediately before inference. |
| `infer_ms` | Direct Hailo detector inference execution. | Measures accelerator detector cost and stability. |
| `post_ms` | Detector post-processing duration. | Measures decode/filter/post-processing cost after inference. |
| `det_pub_ms` | Detection ROS publication-call duration. | Measures detector publication overhead. |
| `e2e_det_ms` | Camera callback observed to detection publication completion. | Main detector-path end-to-end responsiveness metric. |
| `pub_dt_ms` | Interval between consecutive detection publication completions. | Measures effective detector cadence and inter-publication jitter. |
| `track_ms` | Tracker backend `update()` compute only. | Compares tracker compute cost without conflating it with callback or publication overhead. |
| `tim_mars_processing_ms` | TIM-MARS target callback start to completion of the validated decision and controller-facing target message construction. | Measures selected-target authority processing cost, including identity reasoning, but excluding target publication return and later status publication work. |
| `e2e_validated_target_ms` | Camera callback observed to completion of the validated `/target_memory_mars` publication call. | Main camera-to-controller-authority latency metric used for architecture comparison and the control-readiness latency contract. |

The preprocessing submetrics are diagnostic components of `pre_ms`; small
unaccounted overhead can exist around the individually instrumented operations,
so they should not be assumed to sum exactly to `pre_ms`.

## Raw timestamps in Timing.msg

The message also carries host-monotonic timestamps for consistency checks:

- `t_cam_msg_seen_ns`
- `t_pre_start_ns`
- `t_pre_end_ns`
- `t_infer_start_ns`
- `t_infer_end_ns`
- `t_post_start_ns`
- `t_post_end_ns`
- `t_det_pub_start_ns`
- `t_det_pub_end_ns`
- `t_track_cb_start_ns`
- `t_track_cb_end_ns`
- `t_target_cb_start_ns`
- `t_target_process_end_ns`
- `t_target_pub_end_ns`

These make it possible to verify that derived millisecond metrics match their
underlying timestamp deltas.

## Statistical reporting

Canonical runtime reports should retain, where meaningful:

- sample count;
- mean;
- population standard deviation;
- p50;
- p90;
- p95;
- p99;
- maximum;
- effective frequency;
- interarrival/publication jitter;
- missing, skipped, duplicate, or dropped samples where the source provides
  enough information to calculate them;
- warm-up and steady-state populations separately when a warm-up effect exists.

The thesis acceptance criteria are statistical. For example, the
camera-to-validated-target latency requirement is evaluated using its
distribution, including p95; it is not converted into an undocumented
per-sample alarm threshold.

## Selective-ReID workload telemetry

TIM-MARS status messages provide frame-level appearance-workload evidence.

| Field | Meaning |
| --- | --- |
| `appearance_candidates` | Candidate tracks considered by the appearance path. |
| `appearance_request_candidates` | Candidates requested by the active ReID request policy. |
| `appearance_request_encoding_eligible` | Requested candidates whose crops pass encoding eligibility. |
| `appearance_features_valid` | Candidates that end the callback with a usable appearance feature. |
| `appearance_encoding_eligible` | Crops eligible for the appearance backend. |
| `appearance_backend_calls` | Number of appearance-backend invocations in the callback. |
| `appearance_backend_requested` | Embeddings requested from the backend. |
| `appearance_backend_returned` | Backend results returned. |
| `appearance_backend_valid` | Returned embeddings accepted as valid. |
| `appearance_backend_wall_ms` | Wall time spent in the measured appearance-backend invocation. |
| `appearance_cache_size` | Cache entries retained after the callback. |
| `appearance_cache_lookups` | Exact pre-existing-cache lookup attempts counted for telemetry. |
| `appearance_cache_hits` | Lookups with a valid reusable pre-existing embedding. |
| `appearance_cache_misses` | Lookups for which no pre-existing cache entry exists. |
| `appearance_cache_expired` | Existing entries rejected because their age exceeds the cache TTL. |
| `appearance_cache_invalidated` | Existing entries rejected for a non-TTL validity reason, such as generation or required-metadata mismatch. |

The exact cache accounting identity is:

    appearance_cache_lookups
      = appearance_cache_hits
      + appearance_cache_misses
      + appearance_cache_expired
      + appearance_cache_invalidated

Fresh embeddings generated during the current callback are explicitly excluded
from cache lookup telemetry. Therefore a just-computed embedding cannot be
mistaken for cache reuse.

The workload analyser also reports cache hit rate, backend invocation rate,
requested crops per second, valid embeddings per second, backend wall-time
statistics, TIM-MARS processing statistics, warm-up classification, and the
processing displacement associated with backend-call frames.

## Interpretation boundaries

Keep these quantities conceptually separate:

- `infer_ms` is detector Hailo execution, not whole perception latency.
- `track_ms` is tracker backend compute, not detector-to-track end-to-end
  latency.
- `tim_mars_processing_ms` is TIM-MARS processing, not camera-to-target
  end-to-end latency.
- `e2e_validated_target_ms` is the validated end-to-end controller-authority
  latency and must not be replaced by raw `/target` timing.
- `appearance_backend_wall_ms` measures appearance-backend service wall time;
  it is not automatically equal to CPU service time or whole TIM-MARS
  processing time.
- `pub_dt_ms` is cadence/jitter evidence, not processing latency.

## Historical evidence

Schema v4 intentionally performs no field fallback and contains no retired
container/ZMQ aliases. Historical bags and frozen reports produced under older
schemas remain valid historical evidence, but their old field names should not
be rewritten or silently interpreted as schema-v4 measurements.

Current analysis code should use only the schema-v4 contract defined in:

- `tools/timing_contract.py`
- `ros2_ws/src/thesis_msgs/msg/Timing.msg`
