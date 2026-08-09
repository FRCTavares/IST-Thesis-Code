#!/usr/bin/env python3
"""Compute Issue #32's e2e_target_ms percentiles with correct availability semantics.

e2e_target_ms=0.0 on the wire is dashboard_bridge_node's schema-default
sentinel for "no valid same-frame timing context was available for this
sample" (see _compute_e2e_target_ms in dashboard_bridge_node.py), not a
genuine sub-millisecond measurement. tools/analysis/collect_live_timing_stats.py
computes percentiles over the raw field for every /timing/-family topic,
which is correct for every other stage (where 0 is never a real value in
practice) but would silently corrupt e2e_target_ms's percentiles by mixing
unavailable-sentinel zeros into the same population as genuine measurements
(e.g. a majority-zero population drags p50 down to 0.0, which reads as "the
median latency is near-instant" -- false).

This script reads the same /timing_target topic from a recorded evidence
bag, filters to samples with a genuine measurement (e2e_target_ms > 0),
and reports:
- the coverage rate (what fraction of frames got a genuine measurement);
- percentiles computed only over the genuine subset.

Reuses the same percentile implementation convention already used across
this issue's other analysers (linear-interpolated nearest-rank).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def read_timing_target_samples(
    bag_path: Path,
    *,
    topic: str = "/timing_target",
    storage_id: str = "mcap",
) -> list[tuple[int, float]]:
    """Return (bag_timestamp_ns, e2e_target_ms) for every message on topic."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from thesis_msgs.msg import Timing

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=storage_id),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )

    samples: list[tuple[int, float]] = []

    while reader.has_next():
        read_topic, data, timestamp_ns = reader.read_next()

        if read_topic != topic:
            continue

        msg = deserialize_message(data, Timing)
        samples.append((int(timestamp_ns), float(msg.e2e_target_ms)))

    return samples


def analyse(samples: list[tuple[int, float]]) -> dict[str, Any]:
    if not samples:
        raise ValueError("No /timing_target samples were supplied.")

    total = len(samples)
    genuine = [value for _timestamp_ns, value in samples if value > 0.0]
    unavailable_count = total - len(genuine)

    return {
        "schema": "p032_e2e_target_latency_v1",
        "total_samples": total,
        "genuine_measurement_count": len(genuine),
        "unavailable_sentinel_count": unavailable_count,
        "coverage_rate": len(genuine) / total if total > 0 else None,
        "coverage_rate_definition": (
            "Fraction of /timing_target samples with e2e_target_ms > 0. "
            "e2e_target_ms == 0.0 is dashboard_bridge_node's schema-default "
            "sentinel for missing same-frame timing correlation "
            "(t_cam_msg_seen_ns <= 0 on the incoming /tracks message), not "
            "a genuine near-zero latency. See docs/issues/"
            "p1-14-runtime-resource-characterization.md for the diagnosed "
            "root cause."
        ),
        "e2e_target_ms": {
            "count": len(genuine),
            "p50": percentile(genuine, 0.50),
            "p90": percentile(genuine, 0.90),
            "p95": percentile(genuine, 0.95),
            "p99": percentile(genuine, 0.99),
            "maximum": max(genuine) if genuine else None,
            "minimum": min(genuine) if genuine else None,
            "mean": (sum(genuine) / len(genuine)) if genuine else None,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--topic", default="/timing_target")
    parser.add_argument("--storage-id", default="mcap")
    parser.add_argument("--json-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    samples = read_timing_target_samples(
        args.bag, topic=args.topic, storage_id=args.storage_id
    )
    summary = analyse(samples)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
