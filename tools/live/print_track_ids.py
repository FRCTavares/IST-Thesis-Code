#!/usr/bin/env python3
"""Print live tracker IDs from a ROS 2 Track2DArray topic.

This small runtime helper subscribes to a tracker output topic and prints
observed track IDs, scores, and compact bbox summaries. It is useful during
live setup and debugging when selecting or verifying a target ID.

It is an inspection helper only. It does not record data, publish targets, or
compute evaluation metrics.
"""

from __future__ import annotations

import argparse
import math
from typing import Any, Iterable, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

from thesis_msgs.msg import Track2DArray


def safe_get(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def get_track_id(track: Any) -> int:
    value = safe_get(track, ["id", "track_id", "target_id"], -1)
    return int(value) if is_number(value) else -1


def get_score(track: Any) -> Optional[float]:
    value = safe_get(track, ["score", "confidence", "quality"], None)
    return float(value) if is_number(value) else None


def get_bbox_summary(track: Any) -> str:
    # Direct x1/y1/x2/y2 style.
    x1 = safe_get(track, ["x1", "xmin", "left"], None)
    y1 = safe_get(track, ["y1", "ymin", "top"], None)
    x2 = safe_get(track, ["x2", "xmax", "right"], None)
    y2 = safe_get(track, ["y2", "ymax", "bottom"], None)
    if all(is_number(v) for v in (x1, y1, x2, y2)):
        return f"x1={float(x1):.1f} y1={float(y1):.1f} x2={float(x2):.1f} y2={float(y2):.1f}"

    # Common centre/size style.
    cx = safe_get(track, ["cx", "center_x", "bbox_cx"], None)
    cy = safe_get(track, ["cy", "center_y", "bbox_cy"], None)
    w = safe_get(track, ["w", "width", "bbox_w"], None)
    h = safe_get(track, ["h", "height", "bbox_h"], None)
    if all(is_number(v) for v in (cx, cy, w, h)):
        return f"cx={float(cx):.3f} cy={float(cy):.3f} w={float(w):.3f} h={float(h):.3f}"

    # Last-resort numeric field dump.
    fields = []
    if hasattr(track, "get_fields_and_field_types"):
        for name in track.get_fields_and_field_types().keys():
            value = getattr(track, name)
            if is_number(value):
                fields.append(f"{name}={float(value):.3f}")

    return " ".join(fields[:8]) if fields else "bbox=unknown"


class TrackIdPrinter(Node):
    def __init__(self, topic: str) -> None:
        super().__init__("track_id_printer")

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.latest: Optional[Track2DArray] = None
        self.create_subscription(Track2DArray, topic, self._on_tracks, qos)

    def _on_tracks(self, msg: Track2DArray) -> None:
        self.latest = msg


def main() -> None:
    parser = argparse.ArgumentParser(description="Print current track IDs from /tracks.")
    parser.add_argument("--topic", default="/tracks")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    rclpy.init()
    node = TrackIdPrinter(args.topic)

    deadline = node.get_clock().now().nanoseconds + int(args.timeout * 1e9)

    try:
        while rclpy.ok() and node.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.latest is not None:
                break

        if node.latest is None:
            print(f"[warn] no /tracks message received within {args.timeout:.1f}s")
            return

        tracks = list(getattr(node.latest, "tracks", []))
        if not tracks:
            print("[info] /tracks received, but no active tracks")
            return

        rows = []
        for track in tracks:
            tid = get_track_id(track)
            score = get_score(track)
            bbox = get_bbox_summary(track)
            rows.append((tid, score, bbox))

        rows.sort(key=lambda item: item[0])

        print("Available tracks:")
        print("  ID    score    bbox")
        for tid, score, bbox in rows:
            score_text = f"{score:.2f}" if score is not None else "NA"
            print(f"  {tid:<5} {score_text:<8} {bbox}")

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
