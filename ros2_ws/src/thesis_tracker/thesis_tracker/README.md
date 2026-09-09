# thesis_tracker — Python layout

Last reviewed: 2026-09-09

This package provides the ROS 2 tracker node and the tracker backend
implementations.

- `nodes/`: ROS 2 executable nodes.
- `backends/`: selectable tracker backends: SORT, OC-SORT, ByteTrack, and DeepSORT.
- `core/`: shared tracker primitives used by the backends, including SORT/Kalman/IoU utilities.

The public ROS executable is `tracker_node`. The old compatibility executable
`thesis_tracker_node` was removed. Package ROS contract: `../README.md`.
