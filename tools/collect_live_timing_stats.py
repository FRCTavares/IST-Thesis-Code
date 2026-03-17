#!/usr/bin/env python3
"""Collect live timing stats from /timing, /timing_tracker, /timing_target.

Outputs:
- per-field p50/p95/p99 for requested metrics
- achieved Hz per topic
- frame_id continuity stats (gaps/duplicates/missing estimate)
- optional JSON report for later delta comparison across ablation runs
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from thesis_msgs.msg import Timing


TIMING_FIELDS = [
    "pre_ms",
    "zmq_req_send_ms",
    "zmq_wait_reply_ms",
    "zmq_roundtrip_ms",
    "decode_ms",
    "container_unpack_ms",
    "container_queue_ms",
    "infer_ms",
    "post_ms",
    "e2e_det_ms",
]

TRACKER_FIELDS = ["track_ms"]
TARGET_FIELDS = ["target_ms", "e2e_target_ms", "sensor_to_target_ms"]


@dataclass
class TopicStats:
    count: int
    hz: float
    frame_id_min: Optional[int]
    frame_id_max: Optional[int]
    frame_id_unique: int
    frame_id_duplicates: int
    frame_id_gaps: int
    frame_id_missing_estimate: int


def percentile(vals: List[float], q: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    if q <= 0:
        return s[0]
    if q >= 100:
        return s[-1]
    pos = (q / 100.0) * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    w = pos - lo
    return s[lo] * (1.0 - w) + s[hi] * w


def finite_non_negative(v: float) -> bool:
    return math.isfinite(v) and v >= 0.0


class Collector(Node):
    def __init__(self) -> None:
        super().__init__("live_timing_stats_collector")

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=200,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.samples: Dict[str, Dict[str, List[float]]] = {
            "/timing": {k: [] for k in TIMING_FIELDS},
            "/timing_tracker": {k: [] for k in TRACKER_FIELDS},
            "/timing_target": {k: [] for k in TARGET_FIELDS},
        }
        self.frame_ids: Dict[str, List[int]] = {
            "/timing": [],
            "/timing_tracker": [],
            "/timing_target": [],
        }
        self.counts = {"/timing": 0, "/timing_tracker": 0, "/timing_target": 0}

        self.create_subscription(Timing, "/timing", self._on_timing, qos)
        self.create_subscription(Timing, "/timing_tracker", self._on_tracker, qos)
        self.create_subscription(Timing, "/timing_target", self._on_target, qos)

    def _ingest(self, topic: str, msg: Timing, fields: List[str]) -> None:
        self.counts[topic] += 1
        fid = int(msg.frame_id)
        if fid > 0:
            self.frame_ids[topic].append(fid)

        for f in fields:
            v = float(getattr(msg, f))
            if finite_non_negative(v):
                self.samples[topic][f].append(v)

    def _on_timing(self, msg: Timing) -> None:
        self._ingest("/timing", msg, TIMING_FIELDS)

    def _on_tracker(self, msg: Timing) -> None:
        self._ingest("/timing_tracker", msg, TRACKER_FIELDS)

    def _on_target(self, msg: Timing) -> None:
        self._ingest("/timing_target", msg, TARGET_FIELDS)


class StopFlag:
    def __init__(self) -> None:
        self.stop = False

    def handler(self, _sig, _frame) -> None:
        self.stop = True


def calc_topic_stats(frame_ids: List[int], count: int, duration_s: float) -> TopicStats:
    hz = (count / duration_s) if duration_s > 0 else 0.0
    if not frame_ids:
        return TopicStats(
            count=count,
            hz=hz,
            frame_id_min=None,
            frame_id_max=None,
            frame_id_unique=0,
            frame_id_duplicates=0,
            frame_id_gaps=0,
            frame_id_missing_estimate=0,
        )

    s = sorted(frame_ids)
    unique = sorted(set(s))
    duplicates = len(s) - len(unique)

    gaps = 0
    missing = 0
    for i in range(len(unique) - 1):
        d = unique[i + 1] - unique[i]
        if d > 1:
            gaps += 1
            missing += d - 1

    return TopicStats(
        count=count,
        hz=hz,
        frame_id_min=unique[0],
        frame_id_max=unique[-1],
        frame_id_unique=len(unique),
        frame_id_duplicates=duplicates,
        frame_id_gaps=gaps,
        frame_id_missing_estimate=missing,
    )


def summarize_fields(samples: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for field, vals in samples.items():
        out[field] = {
            "n": float(len(vals)),
            "p50": percentile(vals, 50.0),
            "p95": percentile(vals, 95.0),
            "p99": percentile(vals, 99.0),
            "mean": (sum(vals) / len(vals)) if vals else float("nan"),
            "min": min(vals) if vals else float("nan"),
            "max": max(vals) if vals else float("nan"),
        }
    return out


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def print_field_table(fields: Dict[str, Dict[str, float]]) -> None:
    print("field                         n      p50      p95      p99      mean")
    for f in sorted(fields.keys()):
        s = fields[f]
        print(
            f"{f:28s} {int(s['n']):6d} "
            f"{s['p50']:8.3f} {s['p95']:8.3f} {s['p99']:8.3f} {s['mean']:8.3f}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect live timing stats for ablation runs")
    p.add_argument("--duration", type=float, default=120.0, help="Collection duration in seconds")
    p.add_argument("--run-label", type=str, default="run", help="Label for this run in output")
    p.add_argument("--json-out", type=str, default="", help="Optional path to write JSON summary")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    rclpy.init(args=None)
    node = Collector()

    stop = StopFlag()
    signal.signal(signal.SIGINT, stop.handler)
    signal.signal(signal.SIGTERM, stop.handler)

    start = time.monotonic()
    end = start + max(0.1, float(args.duration))

    while rclpy.ok() and not stop.stop and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)

    duration_s = max(1e-9, time.monotonic() - start)

    topic_stats = {
        t: calc_topic_stats(node.frame_ids[t], node.counts[t], duration_s)
        for t in ["/timing", "/timing_tracker", "/timing_target"]
    }

    summary = {
        "run_label": args.run_label,
        "duration_s": duration_s,
        "topics": {k: asdict(v) for k, v in topic_stats.items()},
        "metrics": {
            "/timing": summarize_fields(node.samples["/timing"]),
            "/timing_tracker": summarize_fields(node.samples["/timing_tracker"]),
            "/timing_target": summarize_fields(node.samples["/timing_target"]),
        },
    }

    print_section(f"Run: {args.run_label}")
    print(f"duration_s: {duration_s:.3f}")

    print_section("Topic Rates and Frame Continuity")
    for t in ["/timing", "/timing_tracker", "/timing_target"]:
        s = topic_stats[t]
        print(
            f"{t}: count={s.count} hz={s.hz:.3f} "
            f"fid_min={s.frame_id_min} fid_max={s.frame_id_max} unique={s.frame_id_unique} "
            f"dup={s.frame_id_duplicates} gaps={s.frame_id_gaps} missing_est={s.frame_id_missing_estimate}"
        )

    print_section("/timing Stage Metrics (ms)")
    print_field_table(summary["metrics"]["/timing"])

    print_section("/timing_tracker Metrics (ms)")
    print_field_table(summary["metrics"]["/timing_tracker"])

    print_section("/timing_target Metrics (ms)")
    print_field_table(summary["metrics"]["/timing_target"])

    if args.json_out:
        out_dir = os.path.dirname(args.json_out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"\njson_out: {args.json_out}")

    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
