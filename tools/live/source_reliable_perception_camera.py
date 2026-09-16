#!/usr/bin/env python3
"""Source-capture camera entry point with reliable raw-image publication."""

from __future__ import annotations

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from thesis_bringup.perception.perception_camera_node import PerceptionCameraNode


class SourceReliablePerceptionCameraNode(PerceptionCameraNode):
    """Override only the source evidence raw-image publisher QoS."""

    def create_publisher(self, msg_type, topic, qos_profile, *args, **kwargs):
        if topic == "/camera/image_raw":
            qos_profile = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=5,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            )
        return super().create_publisher(
            msg_type, topic, qos_profile, *args, **kwargs
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SourceReliablePerceptionCameraNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
