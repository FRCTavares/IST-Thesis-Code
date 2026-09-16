#!/usr/bin/env python3
"""Measure finalized bag cadence and controller evidence per topic.

Timestamps are rosbag receive timestamps in stored read order. Rates use the
first/last observed sample; gap percentiles include all inter-message gaps.
No acquisition-quality threshold is inferred from these descriptive values.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
from typing import Any


def percentile(sorted_values: list[int], fraction: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return (sorted_values[lower] * (upper - position)
            + sorted_values[upper] * (position - lower)) if lower != upper else float(sorted_values[lower])


def topic_stats(stamps: list[int]) -> dict[str, Any]:
    count = len(stamps)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    ordered = sorted(gaps)
    duration_ns = stamps[-1] - stamps[0] if count else None
    return {
        "message_count": count,
        "first_timestamp_ns": stamps[0] if count else None,
        "last_timestamp_ns": stamps[-1] if count else None,
        "duration_s": duration_ns / 1e9 if duration_ns is not None else None,
        "average_rate_hz": ((count - 1) * 1e9 / duration_ns
                            if count > 1 and duration_ns > 0 else None),
        "gap_count": len(gaps),
        "gap_p50_s": percentile(ordered, 0.50) / 1e9 if ordered else None,
        "gap_p95_s": percentile(ordered, 0.95) / 1e9 if ordered else None,
        "gap_p99_s": percentile(ordered, 0.99) / 1e9 if ordered else None,
        "gap_max_s": max(gaps) / 1e9 if gaps else None,
        "timestamp_monotonic": all(gap > 0 for gap in gaps),
        "duplicate_timestamp_count": sum(gap == 0 for gap in gaps),
        "backward_timestamp_count": sum(gap < 0 for gap in gaps),
    }


def _stamp(msg: Any) -> int:
    return int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)


def _twist(msg: Any) -> tuple[float, ...]:
    return (float(msg.twist.linear.x), float(msg.twist.linear.y),
            float(msg.twist.linear.z), float(msg.twist.angular.x),
            float(msg.twist.angular.y), float(msg.twist.angular.z))


def pairing(left: list[tuple], right: list[tuple], *, numeric_tolerance: float = 0.0) -> dict[str, Any]:
    left_stamps = Counter(item[0] for item in left)
    right_stamps = Counter(item[0] for item in right)
    left_only = sum((left_stamps - right_stamps).values())
    right_only = sum((right_stamps - left_stamps).values())
    left_by_stamp: dict[int, list[tuple]] = defaultdict(list)
    right_by_stamp: dict[int, list[tuple]] = defaultdict(list)
    for item in left:
        left_by_stamp[item[0]].append(item[1:])
    for item in right:
        right_by_stamp[item[0]].append(item[1:])
    value_mismatch = 0
    for stamp in left_stamps.keys() & right_stamps.keys():
        for lhs, rhs in zip(left_by_stamp[stamp], right_by_stamp[stamp]):
            if len(lhs) != len(rhs) or any(
                not math.isclose(float(a), float(b), rel_tol=0.0,
                                 abs_tol=numeric_tolerance)
                if isinstance(a, (float, int)) and isinstance(b, (float, int))
                else a != b
                for a, b in zip(lhs, rhs)
            ):
                value_mismatch += 1
    return {
        "left_count": len(left), "right_count": len(right),
        "left_unpaired_count": left_only, "right_unpaired_count": right_only,
        "paired_value_mismatch_count": value_mismatch,
        "passed": left_only == right_only == value_mismatch == 0,
    }


def assess_bag(bag: Path, required: list[str], nonzero: list[str]) -> dict[str, Any]:
    from rclpy.serialization import deserialize_message
    from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
    from rosidl_runtime_py.utilities import get_message
    import yaml

    metadata = yaml.safe_load((bag / "metadata.yaml").read_text())
    info = metadata.get("rosbag2_bagfile_information", metadata)
    storage_id = str(info["storage_identifier"])
    reader = SequentialReader()
    reader.open(StorageOptions(uri=str(bag), storage_id=storage_id),
                ConverterOptions("cdr", "cdr"))
    types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    stamps: dict[str, list[int]] = {name: [] for name in types}
    pairs: dict[str, list[tuple]] = defaultdict(list)
    pair_topics = {
        "/control_ref/cmd_vel", "/control_ref/diagnostics",
        "/mavros/setpoint_velocity/cmd_vel",
    }
    classes = {name: get_message(types[name]) for name in pair_topics & types.keys()}
    while reader.has_next():
        name, raw, bag_ns = reader.read_next()
        stamps[name].append(int(bag_ns))
        if name in classes:
            msg = deserialize_message(raw, classes[name])
            if name == "/control_ref/diagnostics":
                pairs[name].append((_stamp(msg), float(msg.command_vx),
                                    float(msg.command_vy), 0.0, 0.0, 0.0,
                                    float(msg.command_yaw_z)))
            else:
                pairs[name].append((_stamp(msg), *_twist(msg)))

    topics = {name: topic_stats(samples) for name, samples in sorted(stamps.items())}
    missing = sorted(set(required) - types.keys())
    empty = sorted(name for name in set(nonzero) if not stamps.get(name))
    comparisons: dict[str, Any] = {}
    command = "/control_ref/cmd_vel"
    diagnostic = "/control_ref/diagnostics"
    mirror = "/mavros/setpoint_velocity/cmd_vel"
    if command in types or diagnostic in types:
        comparisons["command_diagnostic"] = pairing(
            pairs[command], pairs[diagnostic], numeric_tolerance=1e-6)
    if mirror in types:
        comparisons["command_mavros_mirror"] = pairing(pairs[command], pairs[mirror])
    return {
        "schema_version": 1,
        "bag_dir": str(bag),
        "timestamp_basis": "rosbag_receive_timestamp_ns_in_read_order",
        "topics": topics,
        "missing_required_topics": missing,
        "empty_required_topics": empty,
        "pairing": comparisons,
        "checks_passed": not missing and not empty
        and all(item["passed"] for item in comparisons.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--require-topic", action="append", default=[])
    parser.add_argument("--require-nonzero", action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = assess_bag(args.bag, args.require_topic, args.require_nonzero)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered)
    return 0 if report["checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
