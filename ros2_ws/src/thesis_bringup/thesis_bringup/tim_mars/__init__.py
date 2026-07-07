"""TIM-MARS selected-target memory package.

TIM-MARS is the conservative memory layer used above detector/tracker outputs.
It converts noisy multi-object tracker candidates into one selected,
controller-facing target state with explicit uncertainty and recovery logic.

The pure algorithm lives in target_memory.py and supporting policy modules.
ROS-specific parameter, message, and node glue live in ros_params.py,
ros_messages.py, and target_memory_mars_node.py.
"""
