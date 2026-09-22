# Issue #32 — Final runtime characterization

## Purpose

This file freezes the execution and reporting protocol for the final promoted
onboard runtime characterization. Preparing this protocol does not create final
evidence and does not close Issue #32.

**FINAL PHYSICAL RUN PENDING #50.** Issue #64 closed on 22 September 2026
with VGA 640x480 retained. Run the final mounted measurement only after #50
records the retained controller policy; use `docs/flight/README.md` for the
field sequence. Remote runner validation is not final integrated evidence.

The exact two-branch post-#50 run and analysis commands are in
`docs/issues/p032-final-mounted-runbook.md`; final table fields are in
`docs/results/live/templates/p032_final_runtime.md`.

## Dependency gate

Retained final characterization begins only after:

1. Issue #27 prospective held-out H01--H03 execution is complete without
   post-held-out tuning.
2. Issue #58 has its final architecture conclusion under the frozen comparison
   contract.
3. Issue #50 has resolved the physical controller policy, including whether the
   bounded #74 yaw-recovery behavior is promoted or remains disabled.
4. Issue #64 is resolved: VGA 640x480 is retained; HD is not promoted.
5. The final detector, tracker, TIM-MARS, controller, model hashes and runtime
   configuration are frozen.

Runtime characterization must not alter the held-out split or membership,
tracker thresholds, TIM-MARS decision policy, frozen models, or historical
provenance.

## Measured controller path

The core CPU/RSS total contains:

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

For the final mounted Pi/camera/Hailo/controller system, start the production
live stack with VGA 640x480 and retained #50/#74
controller configuration. Attach
`tools/experiments/measure_p032_live_resources.py` to that run's `pids.txt`
without changing launcher ownership. The helper starts the PID-tree and
hardware samplers, waits for first samples, records monotonic start/end bounds,
then finalizes and analyses both streams. Its default group list is detector,
tracker, TIM-MARS and controller; every requested live root must be present.
Retain the live run's configuration/recording provenance alongside the resource
measurement provenance. Do not use the historical process-group sampler against
these PIDs as though PID and process-group ID were interchangeable.

Use a nominal 20-minute active measurement after a 60-second warm-up, for a
nominal 21-minute bounded run. After the retained live stack is healthy, attach
from a second shell with:

    python3 tools/experiments/measure_p032_live_resources.py \
      --run-dir ros2_ws/log/live_stack/<run-id> \
      --duration-s 1260 --warm-up-s 60

Resolve `<run-id>` from the exact production run; do not attach to a stale
`latest` link. Keep the normal stack running until the attachment finishes,
then stop it with its normal operator command. The report includes both the complete bounded
population and the post-warm-up population. Inspect full intervals, cadence
and stalls; active-only averages cannot hide pauses. Extend or repeat if the
system has not reached a stable thermal/memory regime. Architecture-overhead
claims requiring run-to-run variation need matched repetitions rather than
pretending that samples from one run are independent repetitions.

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
- active core architecture groups and raw resource sampling mode;
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
source. The final mounted-system characterization uses the production live
stack, but passive or bench operation still does not establish physical
closed-loop performance.

Core-voltage telemetry is not power.

A calculated image payload is not a substitute for measured DDS bandwidth.

Development runs may validate tooling but must never be relabeled as final,
held-out or physical evidence.
