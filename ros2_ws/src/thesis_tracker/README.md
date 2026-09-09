# thesis_tracker

Last reviewed: 2026-09-09

## Purpose

The multi-object `tracker_node` and its selectable backends. Tracking-by-
detection in a detector-limited regime: one output message per input detection
frame, no backlog, tracker runs at the detector frame rate.

## ROS interface

Subscribes:

- `/detections` (`vision_msgs/Detection2DArray`)
- `/timing` (`thesis_msgs/Timing`) — for causal source timestamps
- `image_topic` (default `/camera/image_raw`) — consumed only when an
  appearance backend needs frames; ignored by the appearance-free backends

Publishes:

- `/tracks` ([thesis_msgs/Track2DArray](../thesis_msgs/msg/Track2DArray.msg)) —
  confirmed tracks only; IDs stable within a run and never reused
- `/timing_tracker` ([thesis_msgs/Timing](../thesis_msgs/msg/Timing.msg)) —
  `track_ms` (tracker `update()` compute); propagates `src_stamp_ns`

## Backends

| `tracker_type` | Behaviour |
| --- | --- |
| `sort` | Appearance-free SORT (Kalman + IoU). Node parameter default. |
| `ocsort` | Observation-Centric SORT; appearance-free, occlusion-oriented. |
| `bytetrack` | ByteTrack; appearance-free, low-confidence detection rescue. Canonical live tracker. |
| `deepsort` | DeepSORT core (8D Kalman, Mahalanobis gating, matching cascade, cosine gallery, IoU fallback). Appearance features come from the MARS-small128 ReID CNN (`models/reid/mars-small128.pb`); the backend requires that model and requires the image topic. Diagnostic architecture-comparison arm, not the canonical tracker. |

The `tracker_node` parameter default is `sort`; the per-backend YAML in
`../thesis_bringup/config/tracker_*.yaml` overrides it, and
`tools/start_live_stack.sh` selects ByteTrack.

## Rules

- Track IDs must be stable within a run — evaluation metrics depend on it.
- Source timestamps are propagated from `/timing` / detection headers onto
  `/tracks` and `/timing_tracker`.
- Per-backend parameters are owned by `../thesis_bringup/config/`.
- `Timing.msg` has no header — do not assign one.

## See also

- `thesis_tracker/README.md` — internal Python layout (`nodes/`, `backends/`, `core/`)
- `../thesis_bringup/config/` — per-backend parameters
- `docs/design/tim_tooling_index.md`
