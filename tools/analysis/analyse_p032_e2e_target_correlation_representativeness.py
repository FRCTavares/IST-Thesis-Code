#!/usr/bin/env python3
"""Assess whether Issue #32's e2e_target_ms correlation misses are selective.

The same-frame timing-correlation fix raised e2e_target_ms coverage from
0% to a partial rate. Before treating the conditional percentiles (computed
only over correlated samples) as representative of the whole pipeline, this
script checks whether misses are associated with different operating
conditions than hits -- if misses cluster during high-latency or
high-cadence periods, the conditional distribution would be biased toward
"easy" frames and could not be promoted as an unqualified pipeline-wide
result.

All comparisons within a stage (hit-group vs miss-group covariate values)
use exact same-frame_id lookups across /timing, /timing_tracker, and
/timing_target as recorded in the same evidence bag -- the same clock
domain, no cross-process timestamp alignment involved. Temporal drift uses
the bag's own recording timestamps, binned into equal-duration windows
across the observed run.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


def read_topic_by_frame_id(
    bag_path: Path,
    topic: str,
    *,
    storage_id: str = "mcap",
) -> dict[int, dict[str, Any]]:
    """Return {frame_id: {field: value, ..., 'bag_time_ns': int}} for topic."""
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

    by_frame: dict[int, dict[str, Any]] = {}

    while reader.has_next():
        read_topic, data, timestamp_ns = reader.read_next()

        if read_topic != topic:
            continue

        msg = deserialize_message(data, Timing)
        frame_id = int(msg.frame_id)

        by_frame[frame_id] = {
            "bag_time_ns": int(timestamp_ns),
            "e2e_target_ms": float(msg.e2e_target_ms),
            "pub_dt_ms": float(msg.pub_dt_ms),
            "e2e_det_ms": float(msg.e2e_det_ms),
            "track_ms": float(msg.track_ms),
        }

    return by_frame


def mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def windowed_miss_rate(
    ordered_frame_ids: list[int],
    timing_target: dict[int, dict[str, Any]],
    *,
    window_count: int,
) -> list[dict[str, Any]]:
    if not ordered_frame_ids:
        return []

    start_ns = timing_target[ordered_frame_ids[0]]["bag_time_ns"]
    end_ns = timing_target[ordered_frame_ids[-1]]["bag_time_ns"]
    duration_ns = max(1, end_ns - start_ns)

    windows: list[dict[str, Any]] = [
        {"index": i, "total": 0, "hits": 0} for i in range(window_count)
    ]

    for frame_id in ordered_frame_ids:
        sample = timing_target[frame_id]
        offset = sample["bag_time_ns"] - start_ns
        fraction = min(0.999999, offset / duration_ns)
        window_index = int(fraction * window_count)
        windows[window_index]["total"] += 1
        if sample["e2e_target_ms"] > 0.0:
            windows[window_index]["hits"] += 1

    for window in windows:
        window["coverage_rate"] = (
            window["hits"] / window["total"] if window["total"] > 0 else None
        )
        window["start_offset_s"] = (
            (window["index"] / window_count) * duration_ns / 1e9
        )

    return windows


def covariate_comparison(
    ordered_frame_ids: list[int],
    timing_target: dict[int, dict[str, Any]],
    timing: dict[int, dict[str, Any]],
    timing_tracker: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Compare cadence/latency covariates between the hit and miss groups.

    All covariates are looked up by exact frame_id from the topic that
    actually computes them: pub_dt_ms/e2e_det_ms from /timing (the
    detector-side message; dashboard_bridge_node's own /timing_target
    message never copies these fields, so reading them off /timing_target
    itself would silently read zeros), and track_ms from /timing_tracker.
    """
    hit_pub_dt: list[float] = []
    miss_pub_dt: list[float] = []
    hit_e2e_det: list[float] = []
    miss_e2e_det: list[float] = []
    hit_track_ms: list[float] = []
    miss_track_ms: list[float] = []

    for frame_id in ordered_frame_ids:
        sample = timing_target[frame_id]
        is_hit = sample["e2e_target_ms"] > 0.0

        timing_sample = timing.get(frame_id)
        pub_dt = timing_sample["pub_dt_ms"] if timing_sample is not None else None
        e2e_det = timing_sample["e2e_det_ms"] if timing_sample is not None else None

        track_sample = timing_tracker.get(frame_id)
        track_ms = track_sample["track_ms"] if track_sample is not None else None

        if is_hit:
            if pub_dt is not None:
                hit_pub_dt.append(pub_dt)
            if e2e_det is not None:
                hit_e2e_det.append(e2e_det)
            if track_ms is not None:
                hit_track_ms.append(track_ms)
        else:
            if pub_dt is not None:
                miss_pub_dt.append(pub_dt)
            if e2e_det is not None:
                miss_e2e_det.append(e2e_det)
            if track_ms is not None:
                miss_track_ms.append(track_ms)

    return {
        "pub_dt_ms": {
            "hit_mean": mean_or_none(hit_pub_dt),
            "hit_median": median_or_none(hit_pub_dt),
            "miss_mean": mean_or_none(miss_pub_dt),
            "miss_median": median_or_none(miss_pub_dt),
            "hit_n": len(hit_pub_dt),
            "miss_n": len(miss_pub_dt),
        },
        "e2e_det_ms": {
            "hit_mean": mean_or_none(hit_e2e_det),
            "hit_median": median_or_none(hit_e2e_det),
            "miss_mean": mean_or_none(miss_e2e_det),
            "miss_median": median_or_none(miss_e2e_det),
            "hit_n": len(hit_e2e_det),
            "miss_n": len(miss_e2e_det),
        },
        "track_ms": {
            "hit_mean": mean_or_none(hit_track_ms),
            "hit_median": median_or_none(hit_track_ms),
            "miss_mean": mean_or_none(miss_track_ms),
            "miss_median": median_or_none(miss_track_ms),
            "hit_n": len(hit_track_ms),
            "miss_n": len(miss_track_ms),
        },
    }


def analyse(
    timing_target: dict[int, dict[str, Any]],
    timing_tracker: dict[int, dict[str, Any]],
    timing: dict[int, dict[str, Any]] | None = None,
    *,
    window_count: int = 10,
) -> dict[str, Any]:
    if not timing_target:
        raise ValueError("No /timing_target samples were supplied.")

    if timing is None:
        timing = {}

    ordered_frame_ids = sorted(
        timing_target.keys(), key=lambda fid: timing_target[fid]["bag_time_ns"]
    )

    total = len(ordered_frame_ids)
    hits = sum(
        1 for fid in ordered_frame_ids if timing_target[fid]["e2e_target_ms"] > 0.0
    )
    misses = total - hits

    windows = windowed_miss_rate(
        ordered_frame_ids, timing_target, window_count=window_count
    )
    coverage_rates = [
        w["coverage_rate"] for w in windows if w["coverage_rate"] is not None
    ]

    covariates = covariate_comparison(
        ordered_frame_ids, timing_target, timing, timing_tracker
    )

    # frame_id gaps in the ordered sequence indicate dropped /timing_target
    # messages (backlog/drop), not correlation misses -- a genuinely
    # different failure mode, reported separately.
    frame_id_gaps = 0
    for earlier, later in zip(ordered_frame_ids, ordered_frame_ids[1:]):
        if later - earlier > 1:
            frame_id_gaps += 1

    coverage_drift_ratio = None
    if len(coverage_rates) >= 2 and coverage_rates[0] not in (None, 0.0):
        coverage_drift_ratio = coverage_rates[-1] / coverage_rates[0]

    return {
        "schema": "p032_e2e_target_correlation_representativeness_v1",
        "total_timing_target_samples": total,
        "genuine_measurement_count": hits,
        "unavailable_sentinel_count": misses,
        "coverage_rate": hits / total if total > 0 else None,
        "frame_id_gap_count": frame_id_gaps,
        "windows": windows,
        "coverage_rate_drift": {
            "first_window": coverage_rates[0] if coverage_rates else None,
            "last_window": coverage_rates[-1] if coverage_rates else None,
            "ratio_last_over_first": coverage_drift_ratio,
            "min_window": min(coverage_rates) if coverage_rates else None,
            "max_window": max(coverage_rates) if coverage_rates else None,
        },
        "covariate_comparison_hit_vs_miss": covariates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--storage-id", default="mcap")
    parser.add_argument("--window-count", type=int, default=10)
    parser.add_argument("--json-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    timing_target = read_topic_by_frame_id(
        args.bag, "/timing_target", storage_id=args.storage_id
    )
    timing_tracker = read_topic_by_frame_id(
        args.bag, "/timing_tracker", storage_id=args.storage_id
    )
    timing = read_topic_by_frame_id(
        args.bag, "/timing", storage_id=args.storage_id
    )

    summary = analyse(
        timing_target, timing_tracker, timing, window_count=args.window_count
    )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
