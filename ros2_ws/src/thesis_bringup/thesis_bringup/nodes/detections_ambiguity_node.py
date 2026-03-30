#!/usr/bin/env python3

from __future__ import annotations

import copy
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from vision_msgs.msg import Detection2DArray


def _best_score(det) -> float:
    if not det.results:
        return 0.0
    return max(float(r.hypothesis.score) for r in det.results)


def _get_center_xy(det) -> tuple[float, float]:
    center = det.bbox.center
    if hasattr(center, "position"):
        return float(center.position.x), float(center.position.y)
    return float(center.x), float(center.y)


def _set_center_xy(det, x: float, y: float) -> None:
    center = det.bbox.center
    if hasattr(center, "position"):
        center.position.x = float(x)
        center.position.y = float(y)
    else:
        center.x = float(x)
        center.y = float(y)


class DetectionsAmbiguityNode(Node):
    def __init__(self) -> None:
        super().__init__("detections_ambiguity_node")

        self.declare_parameter("input_topic", "/detections")
        self.declare_parameter("output_topic", "/detections_ambiguous")
        self.declare_parameter("window_start_s", 5.0)
        self.declare_parameter("window_len_s", 10.0)
        self.declare_parameter("swap_y", False)
        self.declare_parameter("debug", False)

        self.input_topic = str(self.get_parameter("input_topic").value)
        self.output_topic = str(self.get_parameter("output_topic").value)
        self.window_start_s = float(self.get_parameter("window_start_s").value)
        self.window_len_s = float(self.get_parameter("window_len_s").value)
        self.swap_y = bool(self.get_parameter("swap_y").value)
        self.debug = bool(self.get_parameter("debug").value)

        self._t0_mono: float | None = None

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.sub = self.create_subscription(Detection2DArray, self.input_topic, self.on_detections, qos)
        self.pub = self.create_publisher(Detection2DArray, self.output_topic, qos)

        self.get_logger().info(
            f"detections_ambiguity_node ready input={self.input_topic} output={self.output_topic} "
            f"window_start_s={self.window_start_s} window_len_s={self.window_len_s} swap_y={self.swap_y}"
        )

    def _in_window(self) -> bool:
        if self._t0_mono is None:
            return False
        t = time.monotonic() - self._t0_mono
        return self.window_start_s <= t <= (self.window_start_s + self.window_len_s)

    def on_detections(self, msg: Detection2DArray) -> None:
        if self._t0_mono is None:
            self._t0_mono = time.monotonic()

        if not self._in_window() or len(msg.detections) < 2:
            self.pub.publish(msg)
            return

        out = copy.deepcopy(msg)
        ranked = sorted(
            range(len(out.detections)),
            key=lambda i: _best_score(out.detections[i]),
            reverse=True,
        )

        i0, i1 = ranked[0], ranked[1]
        d0 = out.detections[i0]
        d1 = out.detections[i1]

        x0, y0 = _get_center_xy(d0)
        x1, y1 = _get_center_xy(d1)

        if self.swap_y:
            _set_center_xy(d0, x1, y1)
            _set_center_xy(d1, x0, y0)
        else:
            _set_center_xy(d0, x1, y0)
            _set_center_xy(d1, x0, y1)

        if self.debug:
            self.get_logger().info(
                f"ambiguity_applied frame={msg.header.frame_id} swap_y={self.swap_y} i0={i0} i1={i1}"
            )

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
        if rclpy.ok():
            rclpy.shutdown()
