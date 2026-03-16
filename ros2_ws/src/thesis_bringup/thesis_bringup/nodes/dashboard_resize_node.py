#!/usr/bin/env python3

from __future__ import annotations

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image


class DashboardResizeNode(Node):
    def __init__(self) -> None:
        super().__init__("dashboard_resize_node")

        self.declare_parameter("input_topic", "/camera/image_raw")
        self.declare_parameter("output_topic", "/camera/dashboard")
        self.declare_parameter("out_width", 640)
        self.declare_parameter("out_height", 360)
        self.declare_parameter("frame_id", "camera")

        self._input_topic = str(self.get_parameter("input_topic").value)
        self._output_topic = str(self.get_parameter("output_topic").value)
        self._out_width = int(self.get_parameter("out_width").value)
        self._out_height = int(self.get_parameter("out_height").value)
        self._frame_id = str(self.get_parameter("frame_id").value)

        self._bridge = CvBridge()
        self._buffer = None

        out_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self._pub = self.create_publisher(Image, self._output_topic, out_qos)

        in_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._sub = self.create_subscription(Image, self._input_topic, self._on_image, in_qos)

        self.get_logger().info(
            "dashboard_resize_node started: "
            f"{self._input_topic} -> {self._output_topic} ({self._out_width}x{self._out_height})"
        )

    def _on_image(self, msg: Image) -> None:
        # Downscale for browser streaming to reduce CPU, network load, and MJPEG latency.
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        if self._buffer is None:
            self._buffer = cv2.resize(
                frame,
                (self._out_width, self._out_height),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            cv2.resize(
                frame,
                (self._out_width, self._out_height),
                dst=self._buffer,
                interpolation=cv2.INTER_LINEAR,
            )

        out = self._bridge.cv2_to_imgmsg(self._buffer, encoding="bgr8")
        out.header.stamp = msg.header.stamp
        out.header.frame_id = self._frame_id
        self._pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DashboardResizeNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
