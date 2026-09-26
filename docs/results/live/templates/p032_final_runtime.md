# #32 final mounted runtime — PENDING_PHYSICAL_EVIDENCE

Exact RUN_ID/TAG/bag: PENDING_PHYSICAL_EVIDENCE. Git SHA and clean-tree state:
PENDING_PHYSICAL_EVIDENCE. Retained #50 controller decision: PENDING_PHYSICAL_EVIDENCE.
Camera VGA 640x480; detector inference 640x640. Model/config hashes, FCU,
ROS/HailoRT/kernel versions and sampler provenance: PENDING_PHYSICAL_EVIDENCE.

The bounded window is 60 s warm-up + 1200 s active. Report both complete
bounded and post-warm-up populations; show gaps/stalls rather than selecting
only active bursts.

| Metric | Full bounded interval | Post-warm-up interval | Source / caveat |
| --- | --- | --- | --- |
| Detector cadence; p50/p95/p99/max gap | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | per_topic_quality + timing |
| Tracker cadence and latency p50/p95/p99/max | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | timing |
| Validated-target cadence and latency p50/p95/p99/max | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | timing_target |
| Camera-to-validated-target p50/p95/p99/max | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | source-time semantics |
| Controller command cadence and gaps | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | cmd + diagnostics |
| Missing/skipped/duplicate/drop evidence | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | report observability limits |
| Selective ReID calls/embeddings per second | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | status workload |
| Appearance cache hits/misses/expiry | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | status workload |
| Detector/tracker/TIM/controller CPU and RSS | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PID trees |
| Core summed CPU/RSS; system memory | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | resource analysis |
| Temperature, ARM clock, throttling | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | hardware sampler |
| Hailo contention/utilization | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | direct measurement or unavailable |
| Recorder/UI overhead and transport | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | outside core sum; field profile |
| Electrical power | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | reproducible measurement or unavailable |

## Integrity and decision

- Full-window PID-root and sampler coverage: PENDING_PHYSICAL_EVIDENCE.
- MCAP/visual/operator/provenance package integrity: PENDING_PHYSICAL_EVIDENCE.
- Retained MAVROS state: PENDING_PHYSICAL_EVIDENCE; require every
  `/mavros/state` sample inside the retained `trial_start` to `trial_end`
  interval to report `connected=true`, `armed=false`. Startup/shutdown samples
  outside that interval remain visible but are not part of the #32 measurement.
- Physical-v2 annotation: NOT_APPLICABLE only for the proven disarmed
  `p032_final_mounted_vga` characterization.
- Pixhawk DataFlash: NOT_APPLICABLE only for the same proven disarmed runtime
  characterization; do not attach an unrelated historical `.bin`.
- Validated-target rate >=10 Hz (>=15 Hz desired): PENDING_PHYSICAL_EVIDENCE.
- p95 camera-to-validated-target <=200 ms: PENDING_PHYSICAL_EVIDENCE.
- Nonzero thermal throttling investigated: PENDING_PHYSICAL_EVIDENCE.
- Final claim permitted/withheld and reason: PENDING_PHYSICAL_EVIDENCE.

Prior #54 raw-image DDS transport cost is a separate measured result; no raw
images are added to this final field MCAP. Hailo utilization and electrical
power must be marked unavailable when no direct measurement exists.
