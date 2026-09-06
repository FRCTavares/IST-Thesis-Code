# Issue #32 — Final runtime characterization

## Purpose

This file freezes the execution and reporting protocol for the final promoted
onboard runtime characterization. Preparing this protocol does not create final
evidence and does not close Issue #32.

## Dependency gate

Retained final characterization begins only after:

1. Issue #27 prospective held-out H01--H03 execution is complete without
   post-held-out tuning.
2. Issue #58 has its final architecture conclusion under the frozen comparison
   contract.
3. Issue #50 has resolved the physical controller policy, including whether the
   bounded #74 yaw-recovery behavior is promoted or remains disabled.
4. Issue #64 is resolved before final characterization if its remaining
   drone-POV evidence changes the promoted image-resolution choice.
5. The final detector, tracker, TIM-MARS, controller, model hashes and runtime
   configuration are frozen.

Runtime characterization must not alter the held-out split or membership,
tracker thresholds, TIM-MARS decision policy, frozen models, or historical
provenance.

## Measured controller path

The core process-group CPU/RSS total contains:

- detector/perception;
- tracker;
- TIM-MARS when active;
- controller when active.

Dashboard, replay, bag recording, resource sampling and offline analysis are
not included in this core controller-path total. Their enabled state is still
recorded in provenance when relevant.

For replay characterization, MAVROS is forced off. `/control_ref/cmd_vel` is
recorded so controller computation and output cadence can be characterized
without claiming physical closed-loop flight behavior.

## Measurement window

Resource and hardware samplers start before playback so sampler startup can be
validated. Their entire lifetime is not the Issue #32 statistical population.

The runner records a monotonic timestamp immediately before starting playback
and another immediately after playback completes. The Issue #32 analyzer
retains only samples within those explicit bounds.

The default warm-up exclusion is 60 seconds. Every retained report contains:

- the complete active-playback population;
- the post-warm-up steady-state population.

The planned baseline sustained measurement is 20 minutes of active replay after
tooling preflight. Extend the run if the final system has not reached a stable
thermal/memory regime. Architecture-overhead claims requiring run-to-run
variation should use matched repetitions rather than treating samples from one
run as independent repetitions.

## Required provenance

Each retained run must identify at least:

- execution commit and clean/dirty state;
- hardware, OS, kernel, ROS 2 and HailoRT versions;
- detector model path and SHA-256;
- appearance model path and SHA-256;
- tracker configuration;
- TIM-MARS configuration;
- controller target, status and command topics;
- controller MAVROS state;
- controller yaw-recovery state;
- source bag or live-source identity;
- replay rate when applicable;
- resource/hardware sampling intervals;
- warm-up duration;
- exact analysis monotonic start/end bounds;
- active core architecture process groups;
- relevant publishers, subscribers and recorders.

## Required final outputs

The final report set must contain, where observable:

- detector latency decomposition;
- tracker backend latency;
- TIM-MARS processing latency;
- camera-to-validated-target end-to-end latency;
- effective frequency and publication/interarrival jitter;
- missing, skipped, duplicate and dropped evidence when the source exposes
  enough information;
- selective appearance invocations, requested candidates, embeddings, cache
  behavior and embeddings/s;
- detector/tracker/TIM/controller CPU and RSS;
- core summed CPU and RSS;
- temperature, ARM clock, throttling and memory;
- controller command cadence;
- the existing Issue #54 measured raw-image DDS transport result;
- Hailo utilization/contention only if directly measurable;
- electrical power only if reproducibly measured.

## Statistical contract

For continuous numeric metrics, retain where meaningful:

- sample count;
- mean;
- population standard deviation;
- p50;
- p90;
- p95;
- p99;
- maximum.

The Issue #32 resource analyzer additionally retains minimum because it is
useful for memory, clock and thermal interpretation.

## Final decision table

| Quantity | Interpretation |
| --- | --- |
| Validated-target effective rate | Desired at least 15 Hz; below 10 Hz fails the minimum system requirement |
| Camera-to-validated-target latency | p95 must be at most 200 ms; 100 ms remains the design target |
| Controller command cadence | Report effective frequency and jitter against the configured approximately 30 Hz control loop |
| Wrong-person behavior | Use the frozen identity/safety evaluation contract; Issue #32 does not redefine identity acceptance |
| CPU and RSS | Descriptive resource evidence plus matched architecture overhead; do not invent a pass threshold |
| Thermal throttling | Any non-zero throttle state must be reported and investigated before accepting the run |
| Temperature and ARM clock | Report steady-state behavior without inventing an unsupported temperature threshold |
| Hailo utilization | Measured value if directly observable; otherwise `unavailable` |
| Electrical power | Reproducible measurement if available; otherwise `unavailable` |

## Claim boundaries

Replay resource characterization measures computation under a controlled
source. It is not a substitute for physical closed-loop validation.

Core-voltage telemetry is not power.

A calculated image payload is not a substitute for measured DDS bandwidth.

Development runs may validate tooling but must never be relabeled as final,
held-out or physical evidence.
