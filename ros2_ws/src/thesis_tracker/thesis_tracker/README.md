# thesis_tracker Python Layout

This package provides the ROS 2 tracker node and the tracker backend implementations.

- `nodes/`: ROS 2 executable nodes.
- `backends/`: selectable tracker backends: SORT, OC-SORT, ByteTrack, and DeepSORT-style tracking.
- `core/`: shared tracker primitives used by the backends, including SORT/Kalman/IoU utilities.

The public ROS executable is `tracker_node`.
The old compatibility executable `thesis_tracker_node` was removed.
