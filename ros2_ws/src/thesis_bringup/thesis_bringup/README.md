# thesis_bringup Python Layout

This ROS 2 package keeps the thesis runtime nodes under one package name, but
the Python code is organised by responsibility.

- `camera/`: camera capture and video-file publishing nodes.
- `perception/`: image preprocessing and Hailo/perception pipeline nodes.
- `tim_mars/`: TIM-MARS selected-target memory, appearance memory, and MARS ReID backend.
- `control/`: target-to-control reference node.
- `dashboard/`: dashboard/WebSocket bridge node.
- `mavros/`: MAVROS monitoring helpers.

The ROS package name remains `thesis_bringup` to avoid breaking launch files,
scripts, and experiment commands. The internal modules are split for readability.
