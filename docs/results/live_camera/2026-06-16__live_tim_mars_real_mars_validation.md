# Live TIM-MARS with real MARS appearance validation

Date: 2026-06-16

## Purpose

Validate that TIM-MARS can run live on the Raspberry Pi 5 with real MARS appearance features while preserving the 30 Hz perception and tracking pipeline.

## Final live architecture

perception_camera_node:
- integrated camera capture
- Hailo direct inference
- publishes /detections at 30 Hz
- publishes /camera/dashboard at low rate for TIM-MARS appearance crops

tracker_node:
- ByteTrack
- publishes /tracks at 30 Hz

dashboard_bridge_node:
- manual selected raw target
- publishes /target at 30 Hz

target_memory_mars_node:
- consumes /tracks, /target, and /camera/dashboard
- publishes /target_memory_mars and /target_memory_mars/status

## Important correction

TIM-MARS expects the appearance image topic through:

appearance_image_topic=/camera/dashboard

The incorrect parameter image_topic=/camera/image_raw does not configure TIM-MARS appearance input.

The integrated perception node was patched to optionally publish /camera/dashboard without reintroducing the full-rate /camera/image_raw transport path.

## Baseline problem

With real images enabled, TIM-MARS originally recomputed MARS embeddings on every /tracks callback, approximately 30 Hz.

Observed result before throttling:

- target_memory_mars_node CPU: 141% to 151%
- /target_memory_mars: roughly 28 to 30 Hz
- large occasional stalls: up to about 0.328 s
- temperature: about 65.9 C
- throttled: 0x0

This confirmed that MARS appearance was real, but too expensive when evaluated every frame.

## Implemented optimisation

TIM-MARS was patched to throttle and cache appearance features:

- appearance_compute_min_interval_ms=500.0
- appearance_cache_ttl_ms=1000.0
- appearance_max_image_age_ms=350.0

The node now computes MARS features at a bounded rate and reuses cached embeddings between updates.

## Final measured result

Measured live stack:

- /tracks: about 30 Hz
- /target_memory_mars: about 30 Hz
- /target_memory_mars/status: about 30 Hz

Representative output:

- /target id: 1
- /target_memory_mars id: 1
- TIM-MARS quality: about 0.923
- appearance_raw: about 0.9999

CPU and thermal:

- perception_camera_node: about 79.2% CPU
- tracker_node: about 10.6% CPU
- dashboard_bridge_node: about 18.3% CPU
- target_memory_mars_node: about 13.1% CPU
- temperature: about 59.8 C
- throttled: 0x0

## Interpretation

The live experiment confirms that real TIM-MARS with MARS appearance is feasible on the Raspberry Pi 5 when appearance extraction is treated as a bounded identity cue instead of a 30 Hz per-frame computation.

The correct real-time design is:

- run detection and tracking at 30 Hz
- publish controller-facing TIM-MARS output at 30 Hz
- compute MARS appearance at a lower bounded rate
- cache appearance features between updates

This preserves real-time behaviour while keeping the identity memory layer appearance-aware.

## Caveats

This is a live runtime validation, not yet a full multi-person correctness validation.

The next validation step is to record bags with more people and re-entry or occlusion cases using this real live TIM-MARS path.
