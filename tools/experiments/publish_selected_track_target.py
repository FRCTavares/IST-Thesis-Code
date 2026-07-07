#!/usr/bin/env python3
"""Publish a clean /target stream from one fixed tracker ID.

This helper is used for controlled TIM-MARS memory replays where the selected
target is represented by a known tracker ID. It subscribes to /tracks, copies
the matching track into a TargetState message, and publishes an invalid target
when the selected ID is absent.

It is a replay/evaluation helper, not an autonomous selector.
"""

import argparse

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from thesis_msgs.msg import Track2DArray, TargetState


class SelectedTrackTargetPublisher(Node):
    def __init__(self, target_id: int, tracks_topic: str, target_topic: str):
        super().__init__("selected_track_target_publisher")
        self.target_id = int(target_id)
        qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )
        self.pub = self.create_publisher(TargetState, target_topic, qos)
        self.sub = self.create_subscription(Track2DArray, tracks_topic, self.on_tracks, qos)
        self._seen = 0
        self._published_valid = 0
        self.get_logger().info(
            f"Publishing clean raw /target from {tracks_topic}: selected id={self.target_id} -> {target_topic}"
        )

    def on_tracks(self, msg: Track2DArray):
        out = TargetState()
        out.header = msg.header
        out.frame_id = int(getattr(msg, "frame_id", 0))

        selected = None
        for tr in msg.tracks:
            if int(getattr(tr, "id", 0)) == self.target_id:
                selected = tr
                break

        if selected is None:
            out.id = 0
            out.cx = 0.0
            out.cy = 0.0
            out.w = 0.0
            out.h = 0.0
            out.score = 0.0
            out.quality = 0.0
        else:
            out.id = int(selected.id)
            out.cx = float(selected.cx)
            out.cy = float(selected.cy)
            out.w = float(selected.w)
            out.h = float(selected.h)
            out.score = float(getattr(selected, "score", 1.0))
            out.quality = out.score

        self._seen += 1
        if out.id > 0:
            self._published_valid += 1
        if self._seen in (1, 10, 100) or self._seen % 500 == 0:
            self.get_logger().info(
                f"tracks_seen={self._seen} valid_targets={self._published_valid} last_id={out.id}"
            )

        self.pub.publish(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-id", type=int, required=True)
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--target-topic", default="/target")
    args = parser.parse_args()

    rclpy.init()
    node = SelectedTrackTargetPublisher(args.target_id, args.tracks_topic, args.target_topic)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except rclpy.executors.ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
