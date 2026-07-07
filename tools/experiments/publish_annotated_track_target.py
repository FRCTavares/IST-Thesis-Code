#!/usr/bin/env python3
"""Publish /target from annotation CSV + /tracks.

This is a controlled evaluation publisher.

It follows the annotated physical target over tracker-ID fragmentation:
  annotation interval says ID 5 -> publish track 5
  later annotation says ID 1 -> publish track 1
  target_visible=false -> publish invalid target

This is NOT a real raw selector baseline. It is an oracle-style controlled
target stream used to test whether TIM preserves or damages a correct
physical-target selection stream.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from thesis_msgs.msg import TargetState, Track2DArray


@dataclass(frozen=True)
class AnnotationInterval:
    start_s: float
    end_s: float
    target_visible: bool
    track_id: Optional[int]
    event_type: str


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_track_id(value: object) -> Optional[int]:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def load_annotations(path: Path) -> list[AnnotationInterval]:
    rows: list[AnnotationInterval] = []

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"start_s", "end_s", "target_visible", "correct_target_track_id", "event_type"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"annotation CSV missing columns: {sorted(missing)}")

        for raw in reader:
            start_s = float(raw["start_s"])
            end_s = float(raw["end_s"])
            if end_s <= start_s:
                raise ValueError(f"invalid interval {start_s} -> {end_s}")

            visible = _parse_bool(raw["target_visible"])
            track_id = _parse_track_id(raw["correct_target_track_id"])

            rows.append(
                AnnotationInterval(
                    start_s=start_s,
                    end_s=end_s,
                    target_visible=visible,
                    track_id=track_id,
                    event_type=str(raw.get("event_type", "")).strip(),
                )
            )

    rows.sort(key=lambda r: r.start_s)

    for prev, cur in zip(rows, rows[1:]):
        if cur.start_s < prev.end_s:
            raise ValueError(
                f"overlapping annotation intervals: "
                f"{prev.start_s}-{prev.end_s} and {cur.start_s}-{cur.end_s}"
            )

    return rows


def stamp_to_ns(msg: Track2DArray) -> int:
    stamp = msg.header.stamp
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def get_track_id(track: object) -> Optional[int]:
    for name in ("id", "track_id"):
        if hasattr(track, name):
            return int(getattr(track, name))
    return None


def find_track_by_id(tracks: Iterable[object], target_id: int) -> Optional[object]:
    for track in tracks:
        if get_track_id(track) == target_id:
            return track
    return None


def copy_float_field(dst: object, src: object, name: str, default: float = 0.0) -> None:
    if hasattr(dst, name):
        setattr(dst, name, float(getattr(src, name, default)))


class AnnotatedTrackTargetPublisher(Node):
    def __init__(self) -> None:
        super().__init__("annotated_track_target_publisher")

        self.declare_parameter("annotation_csv", "")
        self.declare_parameter("tracks_topic", "/tracks")
        self.declare_parameter("target_topic", "/target")
        self.declare_parameter("publish_missing_as_invalid", True)

        annotation_csv = str(self.get_parameter("annotation_csv").value)
        if not annotation_csv:
            raise ValueError("annotation_csv parameter is required")

        self.annotation_path = Path(annotation_csv)
        self.intervals = load_annotations(self.annotation_path)

        self.tracks_topic = str(self.get_parameter("tracks_topic").value)
        self.target_topic = str(self.get_parameter("target_topic").value)
        self.publish_missing_as_invalid = bool(
            self.get_parameter("publish_missing_as_invalid").value
        )

        self.first_stamp_ns: Optional[int] = None
        self.last_interval: Optional[AnnotationInterval] = None
        self.published_count = 0
        self.invalid_count = 0
        self.missing_track_count = 0

        self.pub = self.create_publisher(TargetState, self.target_topic, 10)

        tracks_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.sub = self.create_subscription(
            Track2DArray,
            self.tracks_topic,
            self.on_tracks,
            tracks_qos,
        )

        self.get_logger().info(
            f"annotation target publisher ready: "
            f"csv={self.annotation_path} intervals={len(self.intervals)} "
            f"tracks_topic={self.tracks_topic} target_topic={self.target_topic}"
        )

    def interval_at(self, t_s: float) -> Optional[AnnotationInterval]:
        # Small CSVs, linear scan is fine and easier to audit.
        for interval in self.intervals:
            if interval.start_s <= t_s < interval.end_s:
                return interval
        return None

    def make_invalid(self, tracks_msg: Track2DArray) -> TargetState:
        out = TargetState()
        out.header = tracks_msg.header
        out.id = 0
        out.cx = 0.0
        out.cy = 0.0
        out.w = 0.0
        out.h = 0.0
        out.score = 0.0
        out.quality = 0.0

        if hasattr(out, "src_stamp_ns"):
            out.src_stamp_ns = stamp_to_ns(tracks_msg)
        if hasattr(out, "t_cam_msg_seen_ns"):
            out.t_cam_msg_seen_ns = 0
        if hasattr(out, "t_target_cb_start_ns"):
            out.t_target_cb_start_ns = 0
        if hasattr(out, "t_target_cb_end_ns"):
            out.t_target_cb_end_ns = 0
        if hasattr(out, "frame_id"):
            # TargetState.frame_id is uint32, not header.frame_id.
            out.frame_id = int(getattr(tracks_msg, "frame_id", 0))

        return out

    def make_target(self, tracks_msg: Track2DArray, track: object, target_id: int) -> TargetState:
        out = TargetState()
        out.header = tracks_msg.header
        out.id = int(target_id)

        copy_float_field(out, track, "cx")
        copy_float_field(out, track, "cy")
        copy_float_field(out, track, "w")
        copy_float_field(out, track, "h")
        copy_float_field(out, track, "score")
        out.quality = float(getattr(track, "quality", getattr(track, "score", 1.0)))

        if hasattr(out, "src_stamp_ns"):
            out.src_stamp_ns = stamp_to_ns(tracks_msg)
        if hasattr(out, "t_cam_msg_seen_ns"):
            out.t_cam_msg_seen_ns = 0
        if hasattr(out, "t_target_cb_start_ns"):
            out.t_target_cb_start_ns = 0
        if hasattr(out, "t_target_cb_end_ns"):
            out.t_target_cb_end_ns = 0
        if hasattr(out, "frame_id"):
            out.frame_id = int(getattr(tracks_msg, "frame_id", 0))

        return out

    def on_tracks(self, msg: Track2DArray) -> None:
        stamp_ns = stamp_to_ns(msg)
        if self.first_stamp_ns is None:
            self.first_stamp_ns = stamp_ns

        t_s = (stamp_ns - self.first_stamp_ns) / 1e9
        interval = self.interval_at(t_s)

        if interval is None or not interval.target_visible or interval.track_id is None:
            self.pub.publish(self.make_invalid(msg))
            self.invalid_count += 1
            return

        track = find_track_by_id(msg.tracks, interval.track_id)
        if track is None:
            self.missing_track_count += 1
            if self.publish_missing_as_invalid:
                self.pub.publish(self.make_invalid(msg))
                self.invalid_count += 1
            return

        self.pub.publish(self.make_target(msg, track, interval.track_id))
        self.published_count += 1

        if self.last_interval != interval:
            self.last_interval = interval
            self.get_logger().info(
                f"annotation interval: t={t_s:.3f}s "
                f"id={interval.track_id} event={interval.event_type}"
            )


def main() -> None:
    rclpy.init()
    node: Optional[AnnotatedTrackTargetPublisher] = None

    try:
        node = AnnotatedTrackTargetPublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except rclpy.executors.ExternalShutdownException:
        pass
    finally:
        if node is not None:
            try:
                node.get_logger().info(
                    f"stopping annotation target publisher: "
                    f"published={node.published_count} "
                    f"invalid={node.invalid_count} "
                    f"missing_track={node.missing_track_count}"
                )
            except Exception:
                pass
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
