#!/usr/bin/env python3
from __future__ import annotations

import math
from typing import Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import TargetState


class DetectionsOccluderNode(Node):
    """
    Publishes /detections_occluded from /detections with synthetic occlusion.

    Modes:
      - passthrough: publish input unchanged
      - periodic_blackout: publish empty detections for drop_s every period_s
      - target_centric: during blackout windows, drop detections within gate_px of last /target centre
      - fixed_roi: during blackout windows, drop detections whose centre falls inside roi_xyxy
    """

    def __init__(self) -> None:
        super().__init__("detections_occluder_node")

        # Core
        self.declare_parameter("mode", "periodic_blackout")
        self.declare_parameter("period_s", 3.0)
        self.declare_parameter("drop_s", 0.5)
        self.declare_parameter("debug", False)

        # Target-centric
        self.declare_parameter("gate_px", 60.0)
        self.declare_parameter("target_is_normalised", True)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)

        # Fixed ROI
        # Accept either a YAML list [x1,y1,x2,y2] or a string "x1,y1,x2,y2"
        self.declare_parameter("roi_xyxy", [0.0, 0.0, 0.0, 0.0])

        self.mode = str(self.get_parameter("mode").value)
        self.period_s = float(self.get_parameter("period_s").value)
        self.drop_s = float(self.get_parameter("drop_s").value)
        self.debug = bool(self.get_parameter("debug").value)

        self.gate_px = float(self.get_parameter("gate_px").value)
        self.target_is_normalised = bool(self.get_parameter("target_is_normalised").value)
        self.img_w = float(self.get_parameter("img_w").value)
        self.img_h = float(self.get_parameter("img_h").value)

        self.roi_xyxy = self._parse_roi(self.get_parameter("roi_xyxy").value)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub = self.create_subscription(Detection2DArray, "/detections", self.on_msg, qos)
        self.pub = self.create_publisher(Detection2DArray, "/detections_occluded", qos)

        # For target_centric mode
        self.last_target_cx: Optional[float] = None
        self.last_target_cy: Optional[float] = None
        self.sub_target = self.create_subscription(TargetState, "/target", self.on_target, qos)

        self.get_logger().info(
            "Occluder ready: "
            f"mode={self.mode}, period_s={self.period_s}, drop_s={self.drop_s}, "
            f"gate_px={self.gate_px}, target_is_normalised={self.target_is_normalised}, "
            f"img_w={self.img_w}, img_h={self.img_h}, roi_xyxy={self.roi_xyxy}"
        )

    @staticmethod
    def _parse_roi(v) -> Tuple[float, float, float, float]:
        # YAML list or tuple
        if isinstance(v, (list, tuple)) and len(v) == 4:
            return float(v[0]), float(v[1]), float(v[2]), float(v[3])
        # string "x1,y1,x2,y2"
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",")]
            if len(parts) == 4:
                return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
        # fallback
        return (0.0, 0.0, 0.0, 0.0)

    def on_target(self, msg: TargetState) -> None:
        """
        Stores last known target centre for target_centric filtering.

        Assumes TargetState has fields cx, cy (either normalised [0,1] or pixel).
        """
        # If your msg fields differ, change here (single place).
        self.last_target_cx = float(msg.cx)
        self.last_target_cy = float(msg.cy)

    def _t_sec(self, msg: Detection2DArray) -> float:
        return float(msg.header.stamp.sec) + 1e-9 * float(msg.header.stamp.nanosec)

    def _should_blackout(self, t: float) -> bool:
        if self.period_s <= 0.0 or self.drop_s <= 0.0:
            return False
        phase = math.fmod(t, self.period_s)
        if phase < 0:
            phase += self.period_s
        return phase < self.drop_s

    def _target_px(self) -> Optional[Tuple[float, float]]:
        if self.last_target_cx is None or self.last_target_cy is None:
            return None
        if self.target_is_normalised:
            return (self.last_target_cx * self.img_w, self.last_target_cy * self.img_h)
        return (self.last_target_cx, self.last_target_cy)

    def _filter_target_centric(self, msg: Detection2DArray) -> Detection2DArray:
        tp = self._target_px()
        if tp is None:
            return msg  # no target known, passthrough
        tx, ty = tp
        gate2 = self.gate_px * self.gate_px

        out = Detection2DArray()
        out.header = msg.header
        kept = []
        dropped = 0

        for det in msg.detections:
            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            dx = cx - tx
            dy = cy - ty
            if (dx * dx + dy * dy) > gate2:
                kept.append(det)
            else:
                dropped += 1

        out.detections = kept
        if self.debug and dropped > 0:
            self.get_logger().info(f"target_centric dropped={dropped} kept={len(kept)}")
        return out

    def _filter_fixed_roi(self, msg: Detection2DArray) -> Detection2DArray:
        x1, y1, x2, y2 = self.roi_xyxy
        if x2 <= x1 or y2 <= y1:
            return msg  # ROI not configured

        out = Detection2DArray()
        out.header = msg.header
        kept = []
        dropped = 0

        for det in msg.detections:
            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            inside = (x1 <= cx <= x2) and (y1 <= cy <= y2)
            if not inside:
                kept.append(det)
            else:
                dropped += 1

        out.detections = kept
        if self.debug and dropped > 0:
            self.get_logger().info(f"fixed_roi dropped={dropped} kept={len(kept)} roi={self.roi_xyxy}")
        return out

    def on_msg(self, msg: Detection2DArray) -> None:
        if self.mode == "passthrough":
            self.pub.publish(msg)
            return

        t = self._t_sec(msg)
        blackout = self._should_blackout(t)

        if self.mode == "periodic_blackout":
            if blackout:
                out = Detection2DArray()
                out.header = msg.header
                out.detections = []
                if self.debug:
                    self.get_logger().info(f"blackout t={t:.3f}")
                self.pub.publish(out)
            else:
                self.pub.publish(msg)
            return

        if self.mode == "target_centric":
            if blackout:
                self.pub.publish(self._filter_target_centric(msg))
            else:
                self.pub.publish(msg)
            return

        if self.mode == "fixed_roi":
            if blackout:
                self.pub.publish(self._filter_fixed_roi(msg))
            else:
                self.pub.publish(msg)
            return

        # Unknown mode -> passthrough
        self.pub.publish(msg)


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
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()