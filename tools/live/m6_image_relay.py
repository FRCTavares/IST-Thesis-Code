#!/usr/bin/env python3
"""Issue #55 M6 — minimal best-effort image relay.

Republishes a `sensor_msgs/Image` topic onto a second topic name without
touching pixel data. Used by the M6 integration gate to feed the replayed
`/camera/image_raw` frames to `web_video_server` on `/camera/dashboard`.

A dedicated helper is used here because `topic_tools` is not installed on the
runtime host and `image_transport republish` subscribes with RELIABLE QoS,
which is incompatible with the BEST_EFFORT QoS of the recorded camera bag.
This relay is deliberately not part of the perception pipeline.
"""

from __future__ import annotations

import argparse

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class ImageRelay(Node):
    def __init__(self, source: str, target: str, depth: int) -> None:
        super().__init__("m6_image_relay")
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=depth,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self._pub = self.create_publisher(Image, target, qos)
        self._sub = self.create_subscription(Image, source, self._forward, qos)
        self._count = 0
        self.get_logger().info(f"relaying {source} -> {target} (best_effort, depth={depth})")

    def _forward(self, msg: Image) -> None:
        self._pub.publish(msg)
        self._count += 1
        if self._count % 150 == 0:
            self.get_logger().info(f"relayed {self._count} frames")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/camera/image_raw")
    parser.add_argument("--target", default="/camera/dashboard")
    parser.add_argument("--depth", type=int, default=10)
    args, _ = parser.parse_known_args()

    rclpy.init()
    node = ImageRelay(args.source, args.target, args.depth)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
