#!/usr/bin/env python3
from __future__ import annotations

from typing import List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from vision_msgs.msg import Detection2DArray


def _best_score(det) -> float:
    if not det.results:
        return 0.0
    return max(float(r.hypothesis.score) for r in det.results)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class DetectionsAmbiguityNode(Node):
    """
    Publish /detections_ambiguous from /detections by forcing a synthetic two-person crossing.

    In the window [window_start_s, window_start_s + window_len_s]:
      - choose top-2 detections by score
      - smoothly swap their bbox centre x coordinates (and optionally y)
    """

    def __init__(self) -> None:
        super().__init__("detections_ambiguity_node")

        self.declare_parameter("window_start_s", 5.0)
        self.declare_parameter("window_len_s", 10.0)
        self.declare_parameter("swap_y", False)
        self.declare_parameter("debug", False)

        self.window_start_s = float(self.get_parameter("window_start_s").value)
        self.window_len_s = float(self.get_parameter("window_len_s").value)
        self.swap_y = bool(self.get_parameter("swap_y").value)
        self.debug = bool(self.get_parameter("debug").value)

        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.sub = self.create_subscription(Detection2DArray, "/detections", self.on_msg, qos)
        self.pub = self.create_publisher(Detection2DArray, "/detections_ambiguous", qos)

        self.get_logger().info(
            f"Ambiguity ready: window_start_s={self.window_start_s} window_len_s={self.window_len_s} swap_y={self.swap_y}"
        )

    def _t_sec(self, msg: Detection2DArray) -> float:
        return float(msg.header.stamp.sec) + 1e-9 * float(msg.header.stamp.nanosec)

    def on_msg(self, msg: Detection2DArray) -> None:
        t = self._t_sec(msg)

        out = Detection2DArray()
        out.header = msg.header
        out.detections = list(msg.detections)

        if self.window_len_s <= 0.0 or len(out.detections) < 2:
            self.pub.publish(out)
            return

        t0 = self.window_start_s
        t1 = self.window_start_s + self.window_len_s
        if not (t0 <= t <= t1):
            self.pub.publish(out)
            return

        # pick top-2 by score
        idxs = sorted(range(len(out.detections)), key=lambda i: _best_score(out.detections[i]), reverse=True)[:2]
        i0, i1 = idxs[0], idxs[1]

        d0 = out.detections[i0]
        d1 = out.detections[i1]

        c0x = float(d0.bbox.center.position.x)
        c0y = float(d0.bbox.center.position.y)
        c1x = float(d1.bbox.center.position.x)
        c1y = float(d1.bbox.center.position.y)

        alpha = (t - t0) / max(1e-6, (t1 - t0))
        alpha = max(0.0, min(1.0, alpha))

        # smooth swap
        new0x = _lerp(c0x, c1x, alpha)
        new1x = _lerp(c1x, c0x, alpha)

        if self.swap_y:
            new0y = _lerp(c0y, c1y, alpha)
            new1y = _lerp(c1y, c0y, alpha)
        else:
            new0y, new1y = c0y, c1y

        d0.bbox.center.position.x = float(new0x)
        d1.bbox.center.position.x = float(new1x)
        d0.bbox.center.position.y = float(new0y)
        d1.bbox.center.position.y = float(new1y)

        out.detections[i0] = d0
        out.detections[i1] = d1

        if self.debug and (int(alpha * 10) in (0, 5, 10)):
            self.get_logger().info(f"alpha={alpha:.2f} x: ({c0x:.1f},{c1x:.1f}) -> ({new0x:.1f},{new1x:.1f})")

        self.pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DetectionsAmbiguityNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()