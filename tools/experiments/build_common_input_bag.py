#!/usr/bin/env python3
"""Build a fail-closed canonical image+detection bag for offline replay.

The source image header timeline, rather than ROS record time, is the
scientific clock. This utility preserves CDR payloads unchanged, verifies a
one-to-one correspondence with detector messages, then writes image followed
by detection at every positive shared header stamp.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
DEFAULT_IMAGE_TOPIC = "/camera/image_raw"
DEFAULT_DETECTIONS_TOPIC = "/detections"
PROVENANCE_NAME = "common_input_provenance.json"
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Freeze a source-header-aligned image+detection bag.")
    parser.add_argument("source_bag", type=Path)
    parser.add_argument("detection_bag", type=Path)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument("--image-topic", default=DEFAULT_IMAGE_TOPIC)
    parser.add_argument("--detections-topic", default=DEFAULT_DETECTIONS_TOPIC)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()
def detect_storage_id(bag_path: Path) -> str:
    """Return the supported rosbag storage identifier."""
    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"
    raise RuntimeError(f"Could not determine rosbag storage for {bag_path}")
def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    """Open a CDR reader for one bag directory."""
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=detect_storage_id(bag_path)), rosbag2_py.ConverterOptions("cdr", "cdr"))
    return reader
def stamp_to_ns(message: Any) -> int:
    """Return a positive ROS header stamp or fail closed."""
    stamp = message.header.stamp
    value = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    if value <= 0:
        raise RuntimeError("Encountered a non-positive message header.stamp")
    return value
def read_topic_records(bag_path: Path, topic_name: str) -> tuple[Any, list[tuple[int, bytes]]]:
    """Read exactly one header-stamped topic, retaining raw CDR bytes."""
    reader = open_reader(bag_path)
    metadata = {item.name: item for item in reader.get_all_topics_and_types()}
    if topic_name not in metadata:
        raise RuntimeError(f"Missing required topic {topic_name!r} in {bag_path}")
    message_type = get_message(metadata[topic_name].type)
    records: list[tuple[int, bytes]] = []
    seen: set[int] = set()
    while reader.has_next():
        topic, serialized, _record_time_ns = reader.read_next()
        if topic != topic_name:
            continue
        stamp_ns = stamp_to_ns(deserialize_message(serialized, message_type))
        if stamp_ns in seen:
            raise RuntimeError(f"Duplicate source header timestamp on {topic_name}: {stamp_ns}")
        seen.add(stamp_ns)
        records.append((stamp_ns, serialized))
    if not records:
        raise RuntimeError(f"No messages found on required topic {topic_name!r}")
    return metadata[topic_name], records
def validate_common_input_records(images: list[tuple[int, bytes]], detections: list[tuple[int, bytes]]) -> list[tuple[int, bytes, bytes]]:
    """Fail closed unless both streams are exact, unique timestamp peers."""
    if len(images) != len(detections):
        raise RuntimeError("Source image and detection counts differ: " f"{len(images)} != {len(detections)}")
    image_by_stamp = dict(images)
    detection_by_stamp = dict(detections)
    if len(image_by_stamp) != len(images):
        raise RuntimeError("Duplicate source image header timestamp")
    if len(detection_by_stamp) != len(detections):
        raise RuntimeError("Duplicate detection header timestamp")
    if any(stamp <= 0 for stamp in image_by_stamp):
        raise RuntimeError("Source images contain a non-positive header timestamp")
    if any(stamp <= 0 for stamp in detection_by_stamp):
        raise RuntimeError("Detections contain a non-positive header timestamp")
    if set(image_by_stamp) != set(detection_by_stamp):
        missing_detections = sorted(set(image_by_stamp) - set(detection_by_stamp))
        missing_images = sorted(set(detection_by_stamp) - set(image_by_stamp))
        raise RuntimeError("Image/detection source-header timestamps do not match exactly; " f"missing detections={missing_detections[:3]}, missing images={missing_images[:3]}")
    return [(stamp, image_by_stamp[stamp], detection_by_stamp[stamp]) for stamp in sorted(image_by_stamp)]
def sha256_file(path: Path) -> str:
    """Hash one file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
def bag_file_hashes(path: Path) -> dict[str, str]:
    """Return deterministic hashes for bag data and metadata files."""
    return {item.name: sha256_file(item) for item in sorted(path.iterdir()) if item.is_file() and item.name != PROVENANCE_NAME}
def topic_metadata(item: Any) -> rosbag2_py.TopicMetadata:
    """Copy topic metadata needed by SequentialWriter."""
    return rosbag2_py.TopicMetadata(id=0, name=item.name, type=item.type, serialization_format="cdr", offered_qos_profiles=item.offered_qos_profiles, type_description_hash=item.type_description_hash)
def write_common_input(output_bag: Path, image_metadata: Any, detection_metadata: Any, pairs: list[tuple[int, bytes, bytes]]) -> None:
    """Write CDR payloads on canonical source-header time in stable order."""
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=str(output_bag), storage_id="mcap"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    writer.create_topic(topic_metadata(image_metadata))
    writer.create_topic(topic_metadata(detection_metadata))
    for stamp_ns, image, detection in pairs:
        writer.write(image_metadata.name, image, stamp_ns)
        writer.write(detection_metadata.name, detection, stamp_ns)
def main() -> int:
    """Construct the common input and its provenance sidecar."""
    args = parse_args()
    source_bag = args.source_bag.expanduser().resolve()
    detection_bag = args.detection_bag.expanduser().resolve()
    output_bag = args.output_bag.expanduser().resolve()
    for required in (source_bag, detection_bag):
        if not required.is_dir():
            raise RuntimeError(f"Input bag does not exist: {required}")
    if output_bag.exists():
        if not args.overwrite:
            raise RuntimeError(f"Output already exists: {output_bag}")
        shutil.rmtree(output_bag)
    image_metadata, images = read_topic_records(source_bag, args.image_topic)
    detection_metadata, detections = read_topic_records(detection_bag, args.detections_topic)
    pairs = validate_common_input_records(images, detections)
    write_common_input(output_bag, image_metadata, detection_metadata, pairs)
    provenance = {"schema_version": "common_input_source_header_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "inputs": {"source_bag": str(source_bag), "source_bag_files_sha256": bag_file_hashes(source_bag), "detection_bag": str(detection_bag), "detection_bag_files_sha256": bag_file_hashes(detection_bag)}, "topics": {"image": args.image_topic, "detections": args.detections_topic}, "counts": {"images": len(images), "detections": len(detections)}, "timestamp_contract": {"all_headers_positive": True, "one_to_one_exact_header_equality": True, "no_duplicate_or_missing_source_timestamps": True, "bag_write_timestamp": "canonical_positive_source_header_stamp", "output_order_at_each_timestamp": [args.image_topic, args.detections_topic], "message_contents": "original_serialized_cdr_payloads_preserved"}, "output_bag_files_sha256": bag_file_hashes(output_bag)}
    (output_bag / PROVENANCE_NAME).write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
