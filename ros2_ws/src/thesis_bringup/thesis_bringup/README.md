# thesis_bringup — Python layout

Last reviewed: 2026-09-09

This ROS 2 package keeps the thesis runtime nodes under one package name, with
the Python code organised by responsibility.

- `camera/`: camera capture and video-file publishing nodes.
- `perception/`: preprocessing, Hailo runtime, and the perception nodes.
- `tim_mars/`: TIM-MARS selected-target memory, appearance memory, and the MARS ReID backend.
- `control/`: target-to-control reference node and the state-aware control policy.
- `dashboard/`: dashboard / WebSocket bridge node.
- `mavros/`: MAVROS monitoring helper.

The ROS package name stays `thesis_bringup` to avoid breaking launch files,
scripts, and experiment commands. Package ROS contract: `../README.md`.
