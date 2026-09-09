# thesis_msgs

Last reviewed: 2026-09-09

## Purpose

The custom ROS 2 message contracts shared by `thesis_tracker`,
`thesis_bringup`, and the repository tooling. ament_cmake interface package;
messages are generated from `msg/*.msg` by `rosidl` (`CMakeLists.txt`).

## Messages

| Message | Role |
| --- | --- |
| `Track2D` | One tracked bounding box: `id, cx, cy, w, h, score, label`. |
| `Track2DArray` | Header plus frame/timestamp metadata plus `Track2D[] tracks`; the `/tracks` contract, with causal source-timestamp fields. |
| `TargetState` | Selected-target box plus score/quality plus callback timestamps; carried by both raw `/target` and the controller-authoritative `/target_memory_mars`. |
| `Timing` | Timing schema v4 — per-stage host-monotonic timestamps and derived latency/cadence metrics for the current direct/in-process Hailo runtime. |
| `AppearanceEmbeddingRequest` | Cross-process appearance-embedding request: causal request id, backend/embedding-space contract, host-monotonic submit/deadline, source-observation and identity provenance, source bbox (xyxy), owned BGR8 crop. |
| `AppearanceEmbeddingResult` | Echoed contract, start/complete timestamps, `succeeded` flag, `embedding[]`, `error`. |

`AppearanceEmbeddingRequest` / `AppearanceEmbeddingResult` are current
supported infrastructure. Their asynchronous transport is default-disabled and
was primarily exercised by the Issue #44 embedded-ReID comparison; they are not
removed or historical-only.

## Rules

- `Timing.msg` has no `std_msgs/Header` — do not add one.
- The machine-readable Timing contract is `tools/timing_contract.py`; the metric
  vocabulary is `docs/RUNTIME_METRICS.md`. This README does not restate the
  schema.
- Changing the field semantics of `Timing`, `TargetState`, or `Track2DArray`
  requires a deliberate contract and provenance review — evaluation tooling
  depends on them.

## See also

- `docs/RUNTIME_METRICS.md`
- `../thesis_tracker/README.md`, `../thesis_bringup/README.md`
