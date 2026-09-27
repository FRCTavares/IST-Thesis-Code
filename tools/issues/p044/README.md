# tools/issues/p044

Last reviewed: 2026-09-27

## P044 — Hailo appearance-offload evidence

Historical Issue #44 reproduction tooling retained after issue closure.

The files here reproduce the controlled Hailo ReID load, fault, transport and
sustained-soak experiments. They are intentionally separated from generic
experiment tooling because they implement the closed Issue #44 protocol.

The hardware-health sampler is not stored here: it became shared infrastructure
and lives at `tools/experiments/sample_hardware_health.py`.
