#!/usr/bin/env python3
"""Refresh replayed image and track timestamps for a sustained P044 soak.

The relay is experiment-only. It prevents direct rosbag loop playback from
reintroducing duplicate or non-monotonic source timestamps into TIM-MARS.
Message content and tracker IDs are retained. CPU MARS remains authoritative.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image
from std_msgs.msg import String
from thesis_msgs.msg import Track2DArray


STATUS_SCHEMA = "p044_soak_input_relay_status_v1"
SUMMARY_SCHEMA = "p044_soak_input_relay_summary_v1"


def stamp_to_ns(stamp: Any) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def assign_stamp(stamp: Any, value_ns: int) -> None:
    value = max(0, int(value_ns))
    stamp.sec = value // 1_000_000_000
    stamp.nanosec = value % 1_000_000_000


class StrictStampAllocator:
    """Allocate strictly increasing timestamps from an imperfect clock."""

    def __init__(self) -> None:
        self.last_ns = 0

    def allocate(self, candidate_ns: int) -> int:
        resolved = max(int(candidate_ns), self.last_ns + 1)
        self.last_ns = resolved
        return resolved


class SourceRewindTracker:
    """Count positive source timestamps that move backwards or repeat."""

    def __init__(self) -> None:
        self.last_positive_ns: int | None = None
        self.rewinds = 0

    def observe(self, source_ns: int) -> None:
        value = int(source_ns)

        if value <= 0:
            return

        if (
            self.last_positive_ns is not None
            and value <= self.last_positive_ns
        ):
            self.rewinds += 1

        self.last_positive_ns = value


@dataclass
class RelayCounters:
    images_received: int = 0
    images_published: int = 0
    tracks_received: int = 0
    tracks_published: int = 0
    image_publication_errors: int = 0
    track_publication_errors: int = 0


def rewrite_image(message: Image, fresh_ns: int) -> Image:
    output = copy.deepcopy(message)
    assign_stamp(output.header.stamp, fresh_ns)
    return output


def rewrite_tracks(
    message: Track2DArray,
    fresh_ns: int,
    output_frame_id: int,
) -> Track2DArray:
    output = copy.deepcopy(message)

    assign_stamp(output.header.stamp, fresh_ns)

    if hasattr(output, "src_stamp_ns"):
        output.src_stamp_ns = int(fresh_ns)

    if hasattr(output, "t_cam_msg_seen_ns"):
        output.t_cam_msg_seen_ns = int(fresh_ns)

    if hasattr(output, "frame_id"):
        output.frame_id = int(output_frame_id)

    return output


class P044SoakInputRelay(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("p044_soak_input_relay")

        self.args = args
        self.started_monotonic_ns = time.monotonic_ns()
        self.counters = RelayCounters()
        self.allocator = StrictStampAllocator()
        self.image_source = SourceRewindTracker()
        self.track_source = SourceRewindTracker()
        self.closed = False

        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=max(1, int(args.qos_depth)),
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        status_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.image_pub = self.create_publisher(
            Image,
            args.output_image_topic,
            sensor_qos,
        )
        self.tracks_pub = self.create_publisher(
            Track2DArray,
            args.output_tracks_topic,
            sensor_qos,
        )
        self.status_pub = self.create_publisher(
            String,
            args.status_topic,
            status_qos,
        )

        self.image_sub = self.create_subscription(
            Image,
            args.input_image_topic,
            self.on_image,
            sensor_qos,
        )
        self.tracks_sub = self.create_subscription(
            Track2DArray,
            args.input_tracks_topic,
            self.on_tracks,
            sensor_qos,
        )

        self.status_timer = self.create_timer(
            max(0.1, float(args.status_period_s)),
            self.publish_status,
        )

        self.get_logger().info(
            "P044 sustained-input relay ready "
            f"(image={args.input_image_topic}->{args.output_image_topic}, "
            f"tracks={args.input_tracks_topic}->{args.output_tracks_topic})"
        )

    def fresh_stamp_ns(self) -> int:
        return self.allocator.allocate(
            self.get_clock().now().nanoseconds
        )

    def on_image(self, message: Image) -> None:
        self.counters.images_received += 1
        self.image_source.observe(
            stamp_to_ns(message.header.stamp)
        )

        try:
            output = rewrite_image(
                message,
                self.fresh_stamp_ns(),
            )
            self.image_pub.publish(output)
            self.counters.images_published += 1
        except Exception:
            self.counters.image_publication_errors += 1
            self.get_logger().exception(
                "Failed to republish refreshed image"
            )

    def on_tracks(self, message: Track2DArray) -> None:
        self.counters.tracks_received += 1

        source_ns = int(
            getattr(message, "src_stamp_ns", 0)
        )
        if source_ns <= 0:
            source_ns = stamp_to_ns(message.header.stamp)

        self.track_source.observe(source_ns)

        try:
            next_frame_id = (
                self.counters.tracks_published + 1
            )
            output = rewrite_tracks(
                message,
                self.fresh_stamp_ns(),
                next_frame_id,
            )
            self.tracks_pub.publish(output)
            self.counters.tracks_published += 1
        except Exception:
            self.counters.track_publication_errors += 1
            self.get_logger().exception(
                "Failed to republish refreshed tracks"
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": STATUS_SCHEMA,
            "timestamp_monotonic_ns": time.monotonic_ns(),
            "runtime_s": (
                time.monotonic_ns()
                - self.started_monotonic_ns
            )
            / 1e9,
            "input_image_topic": self.args.input_image_topic,
            "output_image_topic": self.args.output_image_topic,
            "input_tracks_topic": self.args.input_tracks_topic,
            "output_tracks_topic": self.args.output_tracks_topic,
            "counters": asdict(self.counters),
            "source_image_rewinds": (
                self.image_source.rewinds
            ),
            "source_track_rewinds": (
                self.track_source.rewinds
            ),
            "last_fresh_stamp_ns": self.allocator.last_ns,
            "claim_boundary": {
                "experiment_only_timestamp_refresh": True,
                "source_payload_content_retained": True,
                "tracker_ids_retained": True,
                "cpu_mars_authoritative": True,
                "repvgg_observational": True,
                "canonical_policy_changed": False,
                "production_nodes_modified": False,
            },
        }

    def publish_status(self) -> None:
        message = String()
        message.data = json.dumps(
            self.snapshot(),
            sort_keys=True,
        )
        self.status_pub.publish(message)

    def close(self) -> None:
        if self.closed:
            return

        self.closed = True
        payload = self.snapshot()
        payload["schema"] = SUMMARY_SCHEMA

        summary_path = Path(self.args.summary_path)
        summary_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        summary_path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh looping P044 replay timestamps before "
            "publishing them to perception and TIM-MARS."
        )
    )
    parser.add_argument(
        "--input-image-topic",
        default="/p044/soak/source/image",
    )
    parser.add_argument(
        "--output-image-topic",
        default="/camera/image_raw",
    )
    parser.add_argument(
        "--input-tracks-topic",
        default="/p044/soak/source/tracks",
    )
    parser.add_argument(
        "--output-tracks-topic",
        default="/tracks",
    )
    parser.add_argument(
        "--status-topic",
        default="/p044/soak/input_relay/status",
    )
    parser.add_argument(
        "--summary-path",
        required=True,
    )
    parser.add_argument(
        "--qos-depth",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--status-period-s",
        type=float,
        default=1.0,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = P044SoakInputRelay(args)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
