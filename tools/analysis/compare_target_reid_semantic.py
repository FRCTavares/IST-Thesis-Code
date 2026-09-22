#!/usr/bin/env python3
"""Compare retained Target-ReID ROS messages and record timestamps."""

import argparse
import hashlib
import json
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.utilities import get_message


def records(path: Path):
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr", output_serialization_format="cdr"
        ),
    )
    types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    topic = "/target_reid"
    message_type = get_message(types[topic])
    while reader.has_next():
        name, raw, timestamp_ns = reader.read_next()
        if name == topic:
            yield int(timestamp_ns), message_to_ordereddict(
                deserialize_message(raw, message_type)
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bag_a", type=Path)
    parser.add_argument("bag_b", type=Path)
    args = parser.parse_args()
    a = list(records(args.bag_a))
    b = list(records(args.bag_b))
    a_bytes = json.dumps(a, separators=(",", ":"), ensure_ascii=True).encode()
    b_bytes = json.dumps(b, separators=(",", ":"), ensure_ascii=True).encode()
    result = {
        "bag_a": str(args.bag_a),
        "bag_b": str(args.bag_b),
        "count_a": len(a),
        "count_b": len(b),
        "first_timestamp_ns_a": a[0][0] if a else None,
        "first_timestamp_ns_b": b[0][0] if b else None,
        "last_timestamp_ns_a": a[-1][0] if a else None,
        "last_timestamp_ns_b": b[-1][0] if b else None,
        "record_times_and_all_deserialised_fields_equal": a == b,
        "semantic_sha256_a": hashlib.sha256(a_bytes).hexdigest(),
        "semantic_sha256_b": hashlib.sha256(b_bytes).hexdigest(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if a == b else 1


if __name__ == "__main__":
    raise SystemExit(main())
