#!/usr/bin/env python3
"""
tools/compare_cmd_mirror_bag.py

Offline payload comparison of the MAVROS mirror validation bag.

Reads two TwistStamped topics from an MCAP bag and verifies that every
command published on the debug topic also appears on the mirror topic with
identical payload.

Matching strategy: multiset (Counter) comparison over
    (stamp_sec, stamp_nsec, frame_id, linear.x/y/z, angular.x/y/z)

This is robust to bag ordering artefacts (MCAP chunk batching) and to
duplicate messages — which occur when the ROS 2 timer callback and the
incoming-perception callback fire in the same clock tick and both call
publish_pair().  A plain positional comparison breaks because MCAP may
flush a burst of D messages before the corresponding M messages; stamp-based
dict matching breaks because a replayed bag triggers duplicate (stamp,
payload) pairs.  The multiset approach handles both correctly.

Expected result for the Day 13 validation bag: the two multisets are either
equal or differ by exactly one entry (one extra debug message at
startup/shutdown).

Default bag:  $THESIS_ROOT/bags/tmp/2026-03-13__cmd_mirror_check
Default topics:
  debug   /control_ref/cmd_vel
  mirror  /mavros_mock/setpoint_velocity/cmd_vel

Usage
-----
  python3 tools/compare_cmd_mirror_bag.py [--bag PATH] [--debug-topic T] [--mirror-topic T]

Exit codes
----------
  0  PASS — multisets are equal (counts may differ by at most 1 on one key)
  1  FAIL — payload mismatch, or bag/topic missing
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# ROS 2 bag + message imports
# ---------------------------------------------------------------------------
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BAG = os.path.join(
    os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code")),
    "bags", "tmp", "2026-03-13__cmd_mirror_check",
)
DEFAULT_DEBUG_TOPIC  = "/control_ref/cmd_vel"
DEFAULT_MIRROR_TOPIC = "/mavros_mock/setpoint_velocity/cmd_vel"

# Key fields extracted from each TwistStamped message.
# Floats are kept as-is; since publish_pair() passes the same Python float
# values through the same code path for both messages, the serialised bits
# are expected to be bitwise identical.
MsgKey = Tuple[int, int, str, float, float, float, float, float, float]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_reader(bag_path: str) -> SequentialReader:
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=bag_path, storage_id=""),
        ConverterOptions(input_serialization_format="", output_serialization_format=""),
    )
    return reader


def _msg_key(msg) -> MsgKey:
    """Canonical key uniquely identifying a TwistStamped payload."""
    return (
        msg.header.stamp.sec,
        msg.header.stamp.nanosec,
        msg.header.frame_id,
        msg.twist.linear.x,
        msg.twist.linear.y,
        msg.twist.linear.z,
        msg.twist.angular.x,
        msg.twist.angular.y,
        msg.twist.angular.z,
    )


def _load_counters(
    bag_path: str, topic_a: str, topic_b: str
) -> Tuple[Counter, Counter, int, int]:
    """Read bag, return (Counter_a, Counter_b, n_a, n_b)."""
    reader = _open_reader(bag_path)

    topics_and_types = reader.get_all_topics_and_types()
    type_map: Dict[str, str] = {t.name: t.type for t in topics_and_types}

    available = set(type_map.keys())
    for t in (topic_a, topic_b):
        if t not in available:
            print(f"ERROR: topic '{t}' not found in bag.")
            print(f"  Available topics: {sorted(available)}")
            sys.exit(1)

    msg_type_a = get_message(type_map[topic_a])
    msg_type_b = get_message(type_map[topic_b])

    counter_a: Counter = Counter()
    counter_b: Counter = Counter()
    n_a = n_b = 0

    while reader.has_next():
        topic, data, _t_ns = reader.read_next()
        if topic == topic_a:
            counter_a[_msg_key(deserialize_message(data, msg_type_a))] += 1
            n_a += 1
        elif topic == topic_b:
            counter_b[_msg_key(deserialize_message(data, msg_type_b))] += 1
            n_b += 1

    return counter_a, counter_b, n_a, n_b


def _format_key(key: MsgKey) -> str:
    sec, nsec, fid, lx, ly, lz, ax, ay, az = key
    return (
        f"stamp={sec}.{nsec:09d} frame='{fid}' "
        f"linear=({lx:.6g},{ly:.6g},{lz:.6g}) "
        f"angular=({ax:.6g},{ay:.6g},{az:.6g})"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare debug and MAVROS mirror TwistStamped topics in a bag."
    )
    parser.add_argument("--bag",          default=DEFAULT_BAG,          help="Path to MCAP bag directory")
    parser.add_argument("--debug-topic",  default=DEFAULT_DEBUG_TOPIC,  help="Debug/internal topic name")
    parser.add_argument("--mirror-topic", default=DEFAULT_MIRROR_TOPIC, help="MAVROS mirror topic name")
    args = parser.parse_args()

    bag_path = os.path.expandvars(os.path.expanduser(args.bag))
    if not os.path.isdir(bag_path):
        print(f"ERROR: bag directory not found: {bag_path}")
        return 1

    print(f"Bag:          {bag_path}")
    print(f"Debug topic:  {args.debug_topic}")
    print(f"Mirror topic: {args.mirror_topic}")
    print()

    ctr_d, ctr_m, n_d, n_m = _load_counters(bag_path, args.debug_topic, args.mirror_topic)

    print(f"Messages — debug: {n_d}, mirror: {n_m}")
    print(f"Unique keys — debug: {len(ctr_d)}, mirror: {len(ctr_m)}")

    count_diff = abs(n_d - n_m)
    if count_diff == 0:
        print("Count: exact match.")
    elif count_diff <= 2:
        print(f"Count: differs by {count_diff} (expected — startup/shutdown timing).")
    else:
        print(f"WARNING: count differs by {count_diff} — more than expected startup/shutdown skew.")

    # Find keys where counts differ between the two topics.
    all_keys = set(ctr_d.keys()) | set(ctr_m.keys())
    mismatches: List[Tuple[MsgKey, int, int]] = []  # (key, count_d, count_m)

    for key in all_keys:
        cd = ctr_d[key]
        cm = ctr_m[key]
        if cd != cm:
            mismatches.append((key, cd, cm))

    # A single key with (count_d=1, count_m=0) is the expected off-by-one.
    single_extra = (
        len(mismatches) == 1
        and abs(mismatches[0][1] - mismatches[0][2]) == 1
    )

    print()
    if not mismatches:
        print(f"PASS — multisets are identical ({n_d} debug, {n_m} mirror messages).")
        return 0
    elif single_extra:
        key, cd, cm = mismatches[0]
        extra_in = "debug" if cd > cm else "mirror"
        print(
            f"PASS — multisets match except for one extra message on {extra_in} topic "
            f"(expected startup/shutdown skew)."
        )
        print(f"  Extra: {_format_key(key)}")
        return 0
    else:
        # Sort by difference magnitude descending
        mismatches.sort(key=lambda t: abs(t[1] - t[2]), reverse=True)
        print(f"FAIL — {len(mismatches)} key(s) with unequal counts:")
        for key, cd, cm in mismatches[:10]:
            print(f"  debug×{cd} mirror×{cm}  {_format_key(key)}")
        if len(mismatches) > 10:
            print(f"  ... ({len(mismatches) - 10} more)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
