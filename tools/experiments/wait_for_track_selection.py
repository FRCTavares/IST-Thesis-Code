#!/usr/bin/env python3
"""Resolve a usable target directly from the live /tracks ROS topic.

This avoids repeatedly spawning `ros2 topic echo`, whose DDS discovery time can
exceed a short per-attempt timeout even while /tracks is publishing normally.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from thesis_msgs.msg import Track2DArray


def select_largest_track_id(
    msg: Track2DArray,
    min_height: float = 40.0,
) -> Optional[int]:
    """Return the largest usable track, preserving the historical selection rule."""
    candidates: list[tuple[float, float, int, float, float]] = []

    for track in msg.tracks:
        track_id = int(track.id)
        width = float(track.w)
        height = float(track.h)
        score = float(track.score)

        if width <= 0.0 or height <= 0.0:
            continue

        if height < min_height:
            continue

        candidates.append(
            (
                width * height,
                score,
                track_id,
                width,
                height,
            )
        )

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return int(candidates[0][2])


def contains_target_id(msg: Track2DArray, target_id: int) -> bool:
    """Return whether the exact requested tracker ID is currently present."""
    return any(int(track.id) == int(target_id) for track in msg.tracks)


class TrackSelectionWaiter(Node):
    def __init__(
        self,
        *,
        topic: str,
        largest: bool,
        target_id: Optional[int],
        min_height: float,
    ) -> None:
        super().__init__("track_selection_waiter")

        self._largest = bool(largest)
        self._target_id = target_id
        self._min_height = float(min_height)
        self.result_id: Optional[int] = None
        self.messages_seen = 0
        self.nonempty_messages_seen = 0

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.create_subscription(
            Track2DArray,
            topic,
            self._on_tracks,
            qos,
        )

    def _on_tracks(self, msg: Track2DArray) -> None:
        self.messages_seen += 1

        if msg.tracks:
            self.nonempty_messages_seen += 1

        if self._largest:
            selected = select_largest_track_id(
                msg,
                min_height=self._min_height,
            )
            if selected is not None:
                self.result_id = selected
            return

        if self._target_id is not None and contains_target_id(
            msg,
            self._target_id,
        ):
            self.result_id = int(self._target_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve a target ID from the live thesis /tracks topic."
    )
    parser.add_argument("--topic", default="/tracks")
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Maximum wall-clock wait for a matching track message.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--largest",
        action="store_true",
        help="Select the largest usable track.",
    )
    mode.add_argument(
        "--target-id",
        type=int,
        help="Wait for this exact tracker ID.",
    )

    parser.add_argument(
        "--min-height",
        type=float,
        default=40.0,
        help="Minimum track height used only by --largest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.timeout <= 0.0:
        print("timeout must be > 0", file=sys.stderr)
        return 2

    rclpy.init()
    node = TrackSelectionWaiter(
        topic=str(args.topic),
        largest=bool(args.largest),
        target_id=args.target_id,
        min_height=float(args.min_height),
    )

    deadline = time.monotonic() + float(args.timeout)

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            rclpy.spin_once(
                node,
                timeout_sec=min(0.25, max(0.0, remaining)),
            )

            if node.result_id is not None:
                print(node.result_id)
                return 0

        print(
            "no matching target resolved "
            f"within {args.timeout:.3f}s "
            f"(messages_seen={node.messages_seen}, "
            f"nonempty_messages_seen={node.nonempty_messages_seen})",
            file=sys.stderr,
        )
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
