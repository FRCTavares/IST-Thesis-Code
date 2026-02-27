#!/usr/bin/env python3

from __future__ import annotations

from typing import Optional, Tuple, List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from thesis_msgs.msg import Track2DArray, TargetState


def _track_score(t) -> float:
    # Prefer explicit score if your Track2D has it
    if hasattr(t, "score"):
        return float(t.score)
    return 1.0


def _track_confirmed(t) -> bool:
    if hasattr(t, "confirmed"):
        return bool(t.confirmed)
    # If Track2D has no confirmed flag, treat all as confirmed
    return True


def _track_area(t) -> float:
    if hasattr(t, "area"):
        return float(t.area)
    # else compute from w,h if present
    if hasattr(t, "w") and hasattr(t, "h"):
        return float(max(0.0, t.w) * max(0.0, t.h))
    return 0.0


class ThesisTargetSelectorNode(Node):
    def __init__(self) -> None:
        super().__init__("thesis_target_selector_node")

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub = self.create_subscription(
            Track2DArray,
            "/tracks",
            self.on_tracks,
            qos,
        )

        self.pub = self.create_publisher(
            TargetState,
            "/target",
            qos,
        )

        self.prev_id: Optional[int] = None

    def on_tracks(self, msg: Track2DArray) -> None:
        tracks = list(msg.tracks)

        # No confirmed flag in Track2D, so treat all as eligible
        selected = None

        # 1) sticky previous id if still present
        if self.prev_id is not None:
            for t in tracks:
                if int(t.id) == int(self.prev_id):
                    selected = t
                    break

        # 2) else best by (score desc, area desc)
        if selected is None and tracks:
            tracks.sort(key=lambda t: (float(t.score), float(max(0.0, t.w) * max(0.0, t.h))), reverse=True)
            selected = tracks[0]

        out = TargetState()

        if selected is None:
            out.id = 0
            out.cx = 0.0
            out.cy = 0.0
            out.w = 0.0
            out.h = 0.0
            out.score = 0.0
            out.quality = 0.0
            self.prev_id = None
            self.pub.publish(out)
            return

        self.prev_id = int(selected.id)

        out.id = int(selected.id)
        out.cx = float(selected.cx)
        out.cy = float(selected.cy)
        out.w = float(selected.w)
        out.h = float(selected.h)
        out.score = float(selected.score)
        out.quality = 1.0  # deterministic "selected"
        self.pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ThesisTargetSelectorNode()
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