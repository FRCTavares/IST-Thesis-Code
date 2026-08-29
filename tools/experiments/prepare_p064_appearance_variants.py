#!/usr/bin/env python3
"""Prepare exact-timestamp appearance-image variants for Issue #64."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import rosbag2_py
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.utilities import get_message

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from p064_appearance_contract import (  # noqa: E402
    VARIANT_SCHEMA,
    aspect_ratio,
    image_record,
    image_stream_digest,
    parse_resolution,
    timestamp_digest,
    validate_image_records,
    validate_resize_evidence,
)


RESAMPLING = {
    "area": cv2.INTER_AREA,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "lanczos4": cv2.INTER_LANCZOS4,
}


def detect_storage_id(bag_path: Path) -> str:
    text = (bag_path / "metadata.yaml").read_text(
        encoding="utf-8", errors="ignore"
    )
    if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
        return "mcap"
    if "storage_identifier: sqlite3" in text or "storage_id: sqlite3" in text:
        return "sqlite3"
    raise RuntimeError(f"unsupported bag storage: {bag_path}")


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag_path), storage_id=detect_storage_id(bag_path)
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    return reader


def choose_image_topic(available: dict[str, str], requested: str) -> str:
    if requested != "auto":
        if requested not in available:
            raise RuntimeError(f"image topic not found: {requested}")
        return requested
    for topic in ("/camera/image_raw", "/camera/dashboard"):
        if topic in available:
            return topic
    raise RuntimeError("bag has no supported image topic")


def stamp_ns(message: Any) -> int:
    stamp = message.header.stamp
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def resize_complete_fov(
    image: Any,
    *,
    output_width: int,
    output_height: int,
    resampling: str,
) -> Any:
    """Direct-resize the complete frame without crop, pad, or letterbox."""
    if output_width <= 0 or output_height <= 0:
        raise ValueError("output dimensions must be positive")
    return cv2.resize(
        image,
        (output_width, output_height),
        interpolation=RESAMPLING[resampling],
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_manifest(path: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": item.name,
            "size_bytes": item.stat().st_size,
            "sha256": sha256_file(item),
        }
        for item in sorted(path.iterdir())
        if item.is_file() and item.name != "p064_appearance_variant.json"
    ]


def inspect_master(
    master_bag: Path, image_topic: str
) -> tuple[str, Any, list[Any], int]:
    reader = open_reader(master_bag)
    available = {
        item.name: item.type for item in reader.get_all_topics_and_types()
    }
    topic = choose_image_topic(available, image_topic)
    message_type = get_message(available[topic])
    reader.set_filter(rosbag2_py.StorageFilter(topics=[topic]))
    records = []
    nonpositive_skipped = 0
    while reader.has_next():
        _topic, serialized, _bag_time_ns = reader.read_next()
        message = deserialize_message(serialized, message_type)
        timestamp_ns = stamp_ns(message)
        if timestamp_ns <= 0:
            nonpositive_skipped += 1
            continue
        records.append(image_record(message, timestamp_ns))
    return (
        topic,
        message_type,
        validate_image_records(records),
        nonpositive_skipped,
    )


def write_variant(
    *,
    master_bag: Path,
    image_topic: str,
    message_type: Any,
    master_records: list[Any],
    output_bag: Path,
    output_width: int,
    output_height: int,
    resampling: str,
    allow_upsample_control: bool,
    nonpositive_skipped: int,
) -> dict[str, Any]:
    master_width = master_records[0].width
    master_height = master_records[0].height
    try:
        resize_class = validate_resize_evidence(
            master_width,
            master_height,
            output_width,
            output_height,
            allow_upsample_control=allow_upsample_control,
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(uri=str(output_bag), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=0,
            name=image_topic,
            type="sensor_msgs/msg/Image",
            serialization_format="cdr",
        )
    )

    bridge = CvBridge()
    reader = open_reader(master_bag)
    reader.set_filter(rosbag2_py.StorageFilter(topics=[image_topic]))
    output_records = []
    previous_stamp = None
    while reader.has_next():
        _topic, serialized, bag_time_ns = reader.read_next()
        message = deserialize_message(serialized, message_type)
        timestamp_ns = stamp_ns(message)
        if timestamp_ns <= 0:
            continue
        if previous_stamp is not None and timestamp_ns <= previous_stamp:
            raise RuntimeError(
                "master image storage is not strictly timestamp ordered; "
                "refuse streaming conversion"
            )
        previous_stamp = timestamp_ns
        image = bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        resized = resize_complete_fov(
            image,
            output_width=output_width,
            output_height=output_height,
            resampling=resampling,
        )
        output = bridge.cv2_to_imgmsg(resized, encoding="bgr8")
        output.header = message.header
        writer.write(image_topic, serialize_message(output), int(bag_time_ns))
        output_records.append(image_record(output, timestamp_ns))

    del writer
    output_records = validate_image_records(output_records)
    validate_timestamps = [item.timestamp_ns for item in master_records]
    if [item.timestamp_ns for item in output_records] != validate_timestamps:
        raise RuntimeError("generated timestamp timeline differs from master")

    provenance = {
        "schema": VARIANT_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_status": (
            "upsampled_control_not_high_resolution_evidence"
            if resize_class == "upsample_control"
            else "genuine_source_derived_condition"
        ),
        "master": {
            "bag": str(master_bag),
            "image_topic": image_topic,
            "width": master_width,
            "height": master_height,
            "aspect_ratio": aspect_ratio(master_width, master_height),
            "frame_count": len(master_records),
            "nonpositive_header_images_skipped": int(
                nonpositive_skipped
            ),
            "image_stream_sha256": image_stream_digest(master_records),
            "timestamp_sha256": timestamp_digest(master_records),
        },
        "output": {
            "bag": str(output_bag),
            "image_topic": image_topic,
            "width": output_width,
            "height": output_height,
            "aspect_ratio": aspect_ratio(output_width, output_height),
            "frame_count": len(output_records),
            "image_stream_sha256": image_stream_digest(output_records),
            "timestamp_sha256": timestamp_digest(output_records),
            "resize_class": resize_class,
            "resampling": resampling,
            "complete_fov": True,
            "crop": False,
            "letterbox": False,
            "padding": False,
            "coordinate_mapping": "independent_x_y_direct_resize",
            "timestamp_contract": "exact_positive_source_header_stamp",
            "artifact_files": artifact_manifest(output_bag),
        },
    }
    provenance_path = output_bag / "p064_appearance_variant.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    provenance["provenance_file"] = {
        "path": str(provenance_path),
        "sha256": sha256_file(provenance_path),
    }
    return provenance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("master_bag", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--resolution",
        action="append",
        required=True,
        help="Repeatable WIDTHxHEIGHT appearance condition.",
    )
    parser.add_argument("--image-topic", default="auto")
    parser.add_argument(
        "--resampling",
        choices=tuple(RESAMPLING),
        default="area",
    )
    parser.add_argument("--allow-upsample-control", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    master_bag = args.master_bag.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    if not (master_bag / "metadata.yaml").is_file():
        raise RuntimeError(f"invalid master bag: {master_bag}")
    conditions = [parse_resolution(value) for value in args.resolution]
    if len(conditions) != len(set(conditions)):
        raise RuntimeError("duplicate output resolution requested")
    (
        image_topic,
        message_type,
        master_records,
        nonpositive_skipped,
    ) = inspect_master(
        master_bag, args.image_topic
    )
    output_root.mkdir(parents=True, exist_ok=True)
    results = []
    for width, height in conditions:
        output_bag = output_root / f"{width}x{height}"
        if output_bag.exists():
            if not args.overwrite:
                raise RuntimeError(f"output exists: {output_bag}")
            shutil.rmtree(output_bag)
        results.append(
            write_variant(
                master_bag=master_bag,
                image_topic=image_topic,
                message_type=message_type,
                master_records=master_records,
                output_bag=output_bag,
                output_width=width,
                output_height=height,
                resampling=args.resampling,
                allow_upsample_control=args.allow_upsample_control,
                nonpositive_skipped=nonpositive_skipped,
            )
        )
    summary = {
        "schema": "p064_appearance_variant_batch_v1",
        "master_bag": str(master_bag),
        "master_image_stream_sha256": image_stream_digest(master_records),
        "master_timestamp_sha256": timestamp_digest(master_records),
        "master_nonpositive_header_images_skipped": (
            nonpositive_skipped
        ),
        "conditions": results,
    }
    summary_path = output_root / "p064_appearance_variants.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
