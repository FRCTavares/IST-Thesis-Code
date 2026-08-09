# P1.21 raw-image transport onboard cost (Issue #54, required-work item 9)

Date: 9 August 2026

Issue: [#54](https://github.com/FRCTavares/IST-Thesis-Code/issues/54)

## Result

Measured, on the Pi, the CPU/RSS cost and DDS bandwidth of publishing
`/camera/image_raw` from `perception_camera_node`, comparing the new
default (`publish_image_raw=false`) against the flag forced on
(`--camera-publish-image-raw`). Both an analytical payload-only estimate
and genuinely measured DDS traffic (`ros2 topic bw`/`hz`) are reported,
kept explicitly distinct per this issue's engineering record.

| Metric | `publish_image_raw=false` (default) | `publish_image_raw=true` | Delta |
|---|---:|---:|---:|
| `/camera/image_raw` exists | no | yes | -- |
| `perception_camera_node` CPU (stable window mean) | 83.14% | 90.22% | **+7.08 pp** |
| `perception_camera_node` RSS (stable window mean) | 171,328 KiB | 171,654 KiB | +326 KiB (noise-level) |
| Achieved publish rate (`ros2 topic hz`, nominal 30 FPS) | n/a | 29.63 Hz | -- |
| Measured DDS bandwidth (`ros2 topic bw`, stable window) | n/a | 27.10 MB/s | -- |
| Analytical payload bandwidth (`640x480x3B @ 30fps`) | n/a | 27.65 MB/s (26.37 MiB/s) | -- |

The measured DDS bandwidth (27.10 MB/s) converges close to, and slightly
below, the analytical payload-only estimate (27.65 MB/s) -- consistent
with real publish-timing jitter around the nominal 30 FPS rather than any
additional serialization overhead the analytical figure would have
missed. At the default `640x480 bgr8 @ 30 FPS` capture geometry, enabling
raw-image publication costs roughly **7 percentage points of one CPU
core** and **~27 MB/s of sustained local DDS traffic**, for zero RSS
growth. This is why the default flight profile leaves it off: no
perception, tracking, TIM-MARS, or dashboard consumer needs the stream
(see the engineering record's image-graph audit), so paying this cost
unconditionally would have been pure waste.

## Provenance

- repository commit at capture: `2964fa90f6c954fc6e3c554768f07771f5613a92`
- measurement tool:
  [`tools/experiments/measure_p054_raw_image_transport_cost.sh`](../../../tools/experiments/measure_p054_raw_image_transport_cost.sh)
- command: `./tools/experiments/measure_p054_raw_image_transport_cost.sh`
- scenario: `perception_camera_node` integrated-camera path only
  (`--no-dashboard --no-control --no-web-video --no-tracker`), 15s warm-up,
  20s CPU/RSS sampling window per condition, 10s `ros2 topic hz`/`bw`
  windows for the "on" condition
- camera config: 640x480 capture/publish, `bgr8`, nominal 30 FPS,
  `inference_backend=hailo_direct`, model `yolov6n`
- a first measurement attempt on this date hit a pre-existing, previously
  documented platform condition (`docs/debug/LIVE_STACK_CAMERA_RECOVERY.md`)
  that wedged the camera's I2C path; recovered via that document's
  documented `sudo reboot` procedure, unrelated to this issue's code
  changes (see the engineering record's "Known platform issue" section)

## Recorded evidence

[`p054_raw_image_transport_cost_evidence/`](p054_raw_image_transport_cost_evidence/):
per-condition CPU/RSS CSV, topic lists, `ros2 topic hz`/`bw` raw output,
and `summary.json` (schema v1, contains both the analytical and measured
bandwidth figures with the same distinction documented above), with
`SHA256SUMS`.

## Issue #32 integration

This is the raw-image transport/bandwidth evidence #32's claim-boundary
section listed as out of scope for that issue ("a raw-image transport/
bandwidth claim (Issue #54 scope)"). It is keyed by topic
(`/camera/image_raw`) and camera config, not by #58's
`(architecture_id, sequence_id)` key, since it measures a transport-layer
property of the camera node itself rather than a tracker/TIM architecture
comparison -- #32 can join it directly as the resolution to that
previously-documented gap. This result does not itself close Issue #32.
