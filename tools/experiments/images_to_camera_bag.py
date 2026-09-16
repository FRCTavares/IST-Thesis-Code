#!/usr/bin/env python3
"""Write a sorted image sequence into a ROS 2 bag on /camera/image_raw.

Used to feed external (non-ROS) datasets such as DanceTrack and VisDrone-MOT
through the real detector/tracker pipeline the same way a recorded flight bag
is replayed. Each image is published as one sensor_msgs/msg/Image (bgr8) at
an evenly spaced timestamp derived from an explicit frame rate. No detection,
tracking or TIM-MARS computation happens here -- this only constructs the
source bag.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def discover_images(image_dir: Path) -> list[Path]:
    images = sorted(
        path
        for path in image_dir.iterdir()
        if path.suffix.lower() in IMAGE_SUFFIXES
    )

    if not images:
        raise ValueError(f"no images found under {image_dir}")

    return images


def frame_timestamps_ns(
    count: int,
    *,
    frame_rate_hz: float,
    start_time_ns: int,
) -> list[int]:
    if count <= 0:
        raise ValueError("count must be positive")
    if frame_rate_hz <= 0:
        raise ValueError("frame_rate_hz must be positive")

    period_ns = round(1_000_000_000 / frame_rate_hz)
    return [start_time_ns + index * period_ns for index in range(count)]


def validate_explicit_timestamps(
    timestamps_ns: Iterable[int],
    *,
    expected_count: int,
) -> list[int]:
    timestamps = list(timestamps_ns)

    if len(timestamps) != expected_count:
        raise ValueError(
            "timestamp count does not match image count: "
            f"{len(timestamps)} != {expected_count}"
        )

    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in timestamps
    ):
        raise ValueError("timestamps must be integer nanoseconds")

    if any(value <= 0 for value in timestamps):
        raise ValueError("timestamps must be positive")

    if any(
        later <= earlier
        for earlier, later in zip(timestamps, timestamps[1:])
    ):
        raise ValueError("timestamps must be strictly increasing")

    return timestamps


def load_timestamp_manifest(
    manifest_path: Path,
    image_paths: Iterable[Path],
) -> list[int]:
    image_paths = list(image_paths)

    payload = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if payload.get("schema") != "image_sequence_timestamps_v1":
        raise ValueError("unsupported timestamp manifest schema")

    frames = payload.get("frames")
    if not isinstance(frames, list):
        raise ValueError("timestamp manifest frames must be a list")

    expected_names = [path.name for path in image_paths]
    actual_names = []
    timestamps = []

    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError(
                "timestamp manifest frame entries must be objects"
            )
        actual_names.append(frame.get("file"))
        timestamps.append(frame.get("timestamp_ns"))

    if actual_names != expected_names:
        raise ValueError(
            "timestamp manifest filenames do not exactly match "
            "sorted image sequence"
        )

    return validate_explicit_timestamps(
        timestamps,
        expected_count=len(image_paths),
    )


def write_image_bag(
    image_paths: Iterable[Path],
    *,
    output_bag: Path,
    frame_rate_hz: float | None,
    start_time_ns: int,
    timestamps_ns: Iterable[int] | None = None,
    topic: str = "/camera/image_raw",
    frame_id: str = "camera",
) -> dict[str, object]:
    import cv2
    import rosbag2_py
    from cv_bridge import CvBridge
    from rclpy.serialization import serialize_message
    from rclpy.time import Time as RclpyTime

    image_paths = list(image_paths)

    if timestamps_ns is None:
        if frame_rate_hz is None:
            raise ValueError(
                "frame_rate_hz is required without explicit timestamps"
            )

        timestamps = frame_timestamps_ns(
            len(image_paths),
            frame_rate_hz=frame_rate_hz,
            start_time_ns=start_time_ns,
        )
        timestamp_mode = "fixed_frame_rate"
    else:
        timestamps = validate_explicit_timestamps(
            timestamps_ns,
            expected_count=len(image_paths),
        )
        timestamp_mode = "explicit_manifest"

    bridge = CvBridge()

    writer = rosbag2_py.SequentialWriter()
    storage_options = rosbag2_py.StorageOptions(
        uri=str(output_bag),
        storage_id="mcap",
    )
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    writer.open(storage_options, converter_options)
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=0,
            name=topic,
            type="sensor_msgs/msg/Image",
            serialization_format="cdr",
        )
    )

    written = 0
    skipped: list[str] = []

    for path, stamp_ns in zip(image_paths, timestamps):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)

        if image is None:
            skipped.append(path.name)
            continue

        message = bridge.cv2_to_imgmsg(image, encoding="bgr8")
        ros_time = RclpyTime(nanoseconds=stamp_ns)
        message.header.stamp = ros_time.to_msg()
        message.header.frame_id = frame_id

        writer.write(topic, serialize_message(message), stamp_ns)
        written += 1

    del writer

    return {
        "output_bag": str(output_bag),
        "topic": topic,
        "images_total": len(image_paths),
        "images_written": written,
        "images_skipped": skipped,
        "timestamp_mode": timestamp_mode,
        "frame_rate_hz": frame_rate_hz,
        "start_time_ns": timestamps[0] if timestamps else start_time_ns,
        "end_time_ns": timestamps[-1] if timestamps else start_time_ns,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_bag", type=Path)

    timing = parser.add_mutually_exclusive_group(required=True)
    timing.add_argument("--frame-rate", type=float)
    timing.add_argument("--timestamp-manifest", type=Path)

    parser.add_argument("--start-time-ns", type=int, default=0)
    parser.add_argument("--topic", default="/camera/image_raw")
    parser.add_argument("--frame-id", default="camera")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only write the first N images (for smoke tests).",
    )
    arguments = parser.parse_args()

    if arguments.output_bag.exists():
        if not arguments.overwrite:
            raise SystemExit(
                f"output bag exists: {arguments.output_bag} "
                "(pass --overwrite)"
            )
        import shutil

        shutil.rmtree(arguments.output_bag)

    images = discover_images(arguments.image_dir)

    if arguments.limit is not None:
        images = images[: arguments.limit]

    timestamps_ns = None
    if arguments.timestamp_manifest is not None:
        if arguments.start_time_ns != 0:
            raise SystemExit(
                "--start-time-ns cannot be combined with "
                "--timestamp-manifest"
            )

        timestamps_ns = load_timestamp_manifest(
            arguments.timestamp_manifest,
            images,
        )

    result = write_image_bag(
        images,
        output_bag=arguments.output_bag,
        frame_rate_hz=arguments.frame_rate,
        start_time_ns=arguments.start_time_ns,
        timestamps_ns=timestamps_ns,
        topic=arguments.topic,
        frame_id=arguments.frame_id,
    )

    if arguments.timestamp_manifest is not None:
        result["timestamp_manifest"] = str(
            arguments.timestamp_manifest
        )

    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
