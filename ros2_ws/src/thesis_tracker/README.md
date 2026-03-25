# thesis_tracker

Multi-object tracking node for thesis experiments.

## Documentation sync (2026-03-25)

Dashboard stream QoS and overlay fixes were applied outside this package.
Tracker ROS contracts documented below remain unchanged.

## ROS Interface Contract

### Subscribes
- `/detections` ([vision_msgs/Detection2DArray](http://docs.ros.org/en/api/vision_msgs/html/msg/Detection2DArray.html))

### Publishes
- `/tracks` ([thesis_msgs/Track2DArray](../../thesis_msgs/msg/Track2DArray.msg))
  - Confirmed tracks only (based on tracker-specific confirmation criteria)
  - Track IDs must be stable per tracker (no ID reassignment)
  
- `/timing_tracker` ([thesis_msgs/Timing](../../thesis_msgs/msg/Timing.msg))
  - Field: `track_ms` (float) - time spent in tracker update() call
  - **Note**: `Timing.msg` has no header, do not assign one

## Output Behavior

- **Per-frame, best-effort**: One output message per input detection frame
- **No backlog**: Drops old detections if processing falls behind
- **Detector-limited regime**: Tracking runs at detector frame rate, not faster

This design matches the PIC2 "tracking-by-detection, detector-limited regime" 
viewpoint and keeps the system aligned with the methodological foundation.

## Implementation

The tracker supports multiple backends selectable via ROS parameter `tracker_type`:
- `sort` - Simple Online and Realtime Tracking (baseline)
- `ocsort` - Observation-Centric SORT (occlusion handling)
- `bytetrack` - ByteTrack (low-confidence detection rescue)

See `config/` for per-tracker parameter files.

## Track ID Stability

Track IDs are stable within a single tracker run:
- Once assigned, a track ID persists until the track is pruned
- Track IDs are not reused within the same session
- Different tracker backends may produce different ID sequences for the same input

This is critical for evaluation metrics (MOTA, IDF1, HOTA).
