#!/usr/bin/env python3

from __future__ import annotations

import copy
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import TargetState


def _get_center_xy(det) -> tuple[float, float]:
    center = det.bbox.center
    if hasattr(center, "position"):
        return float(center.position.x), float(center.position.y)
    return float(center.x), float(center.y)


class DetectionsOccluderNode(Node):
    def __init__(self) -> None:
        super().__init__("detections_occluder_node")

        self.declare_parameter("input_topic", "/detections")
        self.declare_parameter("output_topic", "/detections_occluded")
        self.declare_parameter("target_topic", "/target")
        self.declare_parameter("mode", "periodic_blackout")
        self.declare_parameter("period_s", 3.0)
        self.declare_parameter("drop_s", 0.5)
        self.declare_parameter("gate_px", 60.0)
        self.declare_parameter("target_is_normalised", True)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("roi_xyxy", [0.0, 0.0, 0.0, 0.0])
        self.declare_parameter("debug", False)

        self.input_topic = str(self.get_parameter("input_topic").value)
        self.output_topic = str(self.get_parameter("output_topic").value)
        self.target_topic = str(self.get_parameter("target_topic").value)
        self.mode = str(self.get_parameter("mode").value)
        self.period_s = float(self.get_parameter("period_s").value)
        self.drop_s = float(self.get_parameter("drop_s").value)
        self.gate_px = float(self.get_parameter("gate_px").value)
        self.target_is_normalised = bool(self.get_parameter("target_is_normalised").value)
        self.img_w = int(self.get_parameter("img_w").value)
        self.img_h = int(self.get_parameter("img_h").value)
        self.roi_xyxy = [float(v) for v in self.get_parameter("roi_xyxy").value]
        self.debug = bool(self.get_parameter("debug").value)

        self._t0_mono: float | None = None
        self._last_target: TargetState | None = None

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub = self.create_subscription(Detection2DArray, self.input_topic, self.on_detections, qos)
        self.sub_target = self.create_subscription(TargetState, self.target_topic, self.on_target, qos)
        self.pub = self.create_publisher(Detection2DArray, self.output_topic, qos)

        self.get_logger().info(
            f"detections_occluder_node ready input={self.input_topic} output={self.output_topic} "
            f"mode={self.mode} period_s={self.period_s} drop_s={self.drop_s}"
        )

    def on_target(self, msg: TargetState) -> None:
        self._last_target = msg

    def _drop_phase_active(self) -> bool:
        if self._t0_mono is None:
            return False
        if self.period_s <= 0.0:
            return False
        t = time.monotonic() - self._t0_mono
        return (t % self.period_s) < self.drop_s

    def _target_xy_px(self) -> tuple[float, float] | None:
        if self._last_target is None or self._last_target.id == 0:
            return None
        tx = float(self._last_target.cx)
        ty = float(self._last_target.cy)
        if self.target_is_normalised:
            tx *= float(self.img_w)
            ty *= float(self.img_h)
        return tx, ty

    def on_detections(self, msg: Detection2DArray) -> None:
        if self._t0_mono is None:
            self._t0_mono = time.monotonic()

        if not self._drop_phase_active():
            self.pub.publish(msg)
            return

        out = copy.deepcopy(msg)

        if self.mode == "periodic_blackout":
            out.detections = []
        elif self.mode == "fixed_roi":
            x1, y1, x2, y2 = self.roi_xyxy if len(self.roi_xyxy) == 4 else (0.0, 0.0, 0.0, 0.0)
            kept = []
            for det in out.detections:
                cx, cy = _get_center_xy(det)
                inside = (x1 <= cx <= x2) and (y1 <= cy <= y2)
                if not inside:
                    kept.append(det)
            out.detections = kept
        elif self.mode == "target_centric":
            txy = self._target_xy_px()
            if txy is not None:
                tx, ty = txy
                kept = []
                for det in out.detections:
                    cx, cy = _get_center_xy(det)
                    dx = cx - tx
                    dy = cy - ty
                    if (dx * dx + dy * dy) > (self.gate_px * self.gate_px):
                        kept.append(det)
                out.detections = kept
            else:
                out.detections = []

        if self.debug:
            self.get_logger().info(
                f"occlusion_applied mode={self.mode} in={len(msg.detections)} out={len(out.detections)}"
            )

        self.pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DetectionsOccluderNode()
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
