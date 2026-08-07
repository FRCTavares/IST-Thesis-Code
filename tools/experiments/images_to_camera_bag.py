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


def write_image_bag(
    image_paths: Iterable[Path],
    *,
    output_bag: Path,
    frame_rate_hz: float,
    start_time_ns: int,
    topic: str = "/camera/image_raw",
    frame_id: str = "camera",
) -> dict[str, object]:
    import cv2
    import rosbag2_py
    from cv_bridge import CvBridge
    from rclpy.serialization import serialize_message
    from rclpy.time import Time as RclpyTime

    image_paths = list(image_paths)
    timestamps_ns = frame_timestamps_ns(
        len(image_paths),
        frame_rate_hz=frame_rate_hz,
        start_time_ns=start_time_ns,
    )

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

    for path, stamp_ns in zip(image_paths, timestamps_ns):
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
        "frame_rate_hz": frame_rate_hz,
        "start_time_ns": start_time_ns,
        "end_time_ns": timestamps_ns[-1] if timestamps_ns else start_time_ns,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument("--frame-rate", type=float, required=True)
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

    result = write_image_bag(
        images,
        output_bag=arguments.output_bag,
        frame_rate_hz=arguments.frame_rate,
        start_time_ns=arguments.start_time_ns,
        topic=arguments.topic,
        frame_id=arguments.frame_id,
    )

    import json

    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
