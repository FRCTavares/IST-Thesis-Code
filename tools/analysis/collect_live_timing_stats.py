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
from pathlib import Path
import signal
import sys
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from thesis_msgs.msg import Timing
from vision_msgs.msg import Detection2DArray

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.timing_contract import (  # noqa: E402
    FPS_INTERVAL_RELATIVE_DELTA_MAX,
    METRICS_SCHEMA_VERSION,
    METRIC_WARN_THRESHOLDS,
    METRIC_WINDOWS,
    resolve_metric,
    topic_fields,
)


TIMING_FIELDS = list(topic_fields("/timing"))
TRACKER_FIELDS = list(topic_fields("/timing_tracker"))
TARGET_FIELDS = list(topic_fields("/timing_target"))


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


def _clamp01(v: float) -> float:
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return v


def _score_lower_is_better(value: float, good: float, bad: float) -> float:
    if not math.isfinite(value):
        return float("nan")
    if bad <= good:
        return 0.0
    return _clamp01((bad - value) / (bad - good))


def _compute_cadence_consistency(summary: Dict[str, object]) -> Dict[str, float | bool]:
    metrics = summary.get("metrics", {})
    dstream = summary.get("detection_stream", {})

    timing_metrics = metrics.get("/timing", {}) if isinstance(metrics, dict) else {}
    pub_dt_stats = timing_metrics.get("pub_dt_ms", {}) if isinstance(timing_metrics, dict) else {}

    det_out_fps_hz = float(dstream.get("hz", float("nan"))) if isinstance(dstream, dict) else float("nan")
    pub_dt_p50_ms = float(pub_dt_stats.get("p50", float("nan"))) if isinstance(pub_dt_stats, dict) else float("nan")

    fps_from_pub_dt = float("nan")
    if math.isfinite(pub_dt_p50_ms) and pub_dt_p50_ms > 0.0:
        fps_from_pub_dt = 1000.0 / pub_dt_p50_ms

    relative_delta = float("nan")
    if math.isfinite(det_out_fps_hz) and det_out_fps_hz > 0.0 and math.isfinite(fps_from_pub_dt) and fps_from_pub_dt > 0.0:
        relative_delta = abs(det_out_fps_hz - fps_from_pub_dt) / max(fps_from_pub_dt, 1e-9)

    within_tolerance = bool(
        math.isfinite(relative_delta) and relative_delta <= FPS_INTERVAL_RELATIVE_DELTA_MAX
    )

    return {
        "det_out_fps_hz": det_out_fps_hz,
        "pub_dt_p50_ms": pub_dt_p50_ms,
        "fps_from_pub_dt_p50": fps_from_pub_dt,
        "relative_delta": relative_delta,
        "within_tolerance": within_tolerance,
        "relative_delta_max": FPS_INTERVAL_RELATIVE_DELTA_MAX,
    }


def _compute_health(summary: Dict[str, object]) -> Dict[str, float]:
    metrics = summary.get("metrics", {})
    topics = summary.get("topics", {})
    dstream = summary.get("detection_stream", {})

    timing_metrics = metrics.get("/timing", {}) if isinstance(metrics, dict) else {}
    timing_topic = topics.get("/timing", {}) if isinstance(topics, dict) else {}

    e2e_p95 = float(
        timing_metrics.get("e2e_det_ms", {}).get("p95", float("nan"))
    ) if isinstance(timing_metrics, dict) else float("nan")
    pub_dt_p95 = float(
        timing_metrics.get("pub_dt_ms", {}).get("p95", float("nan"))
    ) if isinstance(timing_metrics, dict) else float("nan")

    timing_hz = float(timing_topic.get("hz", float("nan"))) if isinstance(timing_topic, dict) else float("nan")
    det_hz = float(dstream.get("hz", float("nan"))) if isinstance(dstream, dict) else float("nan")

    throughput_ratio = float("nan")
    if math.isfinite(timing_hz) and timing_hz > 0.0 and math.isfinite(det_hz):
        throughput_ratio = det_hz / timing_hz

    latency_score = _score_lower_is_better(e2e_p95, good=70.0, bad=220.0)
    cadence_score = _score_lower_is_better(pub_dt_p95, good=80.0, bad=220.0)
    throughput_score = float("nan")
    if math.isfinite(throughput_ratio):
        throughput_score = _clamp01(throughput_ratio / 0.9)

    weighted = [
        (0.45, latency_score),
        (0.20, cadence_score),
        (0.35, throughput_score),
    ]

    acc = 0.0
    wsum = 0.0
    for w, v in weighted:
        if math.isfinite(v):
            acc += w * v
            wsum += w

    health_score = float("nan")
    if wsum > 0.0:
        health_score = (acc / wsum) * 100.0

    return {
        "score": health_score,
        "latency_component": latency_score * 100.0 if math.isfinite(latency_score) else float("nan"),
        "cadence_component": cadence_score * 100.0 if math.isfinite(cadence_score) else float("nan"),
        "throughput_component": throughput_score * 100.0 if math.isfinite(throughput_score) else float("nan"),
        "throughput_ratio": throughput_ratio,
        "e2e_det_p95_ms": e2e_p95,
        "pub_dt_p95_ms": pub_dt_p95,
    }


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

        self.detection_msg_count = 0
        self.detection_counts: List[float] = []

        self.create_subscription(Timing, "/timing", self._on_timing, qos)
        self.create_subscription(Timing, "/timing_tracker", self._on_tracker, qos)
        self.create_subscription(Timing, "/timing_target", self._on_target, qos)
        self.create_subscription(Detection2DArray, "/detections", self._on_detections, qos)

    def _ingest(self, topic: str, msg: Timing, fields: List[str]) -> None:
        self.counts[topic] += 1
        fid = int(msg.frame_id)
        if fid > 0:
            self.frame_ids[topic].append(fid)

        for f in fields:
            v, _source = resolve_metric(msg, f)
            if finite_non_negative(v):
                self.samples[topic][f].append(v)

    def _on_timing(self, msg: Timing) -> None:
        self._ingest("/timing", msg, TIMING_FIELDS)

    def _on_tracker(self, msg: Timing) -> None:
        self._ingest("/timing_tracker", msg, TRACKER_FIELDS)

    def _on_target(self, msg: Timing) -> None:
        self._ingest("/timing_target", msg, TARGET_FIELDS)

    def _on_detections(self, msg: Detection2DArray) -> None:
        self.detection_msg_count += 1
        self.detection_counts.append(float(len(msg.detections)))


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
        "contract": {
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "metric_windows": dict(METRIC_WINDOWS),
            "metric_thresholds_ms": {
                "e2e_det_ms": float(METRIC_WARN_THRESHOLDS["e2e_det_ms"]),
                "pub_dt_ms": float(METRIC_WARN_THRESHOLDS["pub_dt_ms"]),
                "infer_ms": float(METRIC_WARN_THRESHOLDS["infer_ms"]),
                "container_queue_ms": float(METRIC_WARN_THRESHOLDS["container_queue_ms"]),
                "track_ms": float(METRIC_WARN_THRESHOLDS["track_ms"]),
                "e2e_target_ms": float(METRIC_WARN_THRESHOLDS["e2e_target_ms"]),
            },
        },
        "topics": {k: asdict(v) for k, v in topic_stats.items()},
        "metrics": {
            "/timing": summarize_fields(node.samples["/timing"]),
            "/timing_tracker": summarize_fields(node.samples["/timing_tracker"]),
            "/timing_target": summarize_fields(node.samples["/timing_target"]),
        },
        "detection_stream": {
            "count": int(node.detection_msg_count),
            "hz": (float(node.detection_msg_count) / duration_s) if duration_s > 0 else 0.0,
            "detections_per_msg": {
                "n": float(len(node.detection_counts)),
                "p50": percentile(node.detection_counts, 50.0),
                "p95": percentile(node.detection_counts, 95.0),
                "p99": percentile(node.detection_counts, 99.0),
                "mean": (sum(node.detection_counts) / len(node.detection_counts)) if node.detection_counts else float("nan"),
                "min": min(node.detection_counts) if node.detection_counts else float("nan"),
                "max": max(node.detection_counts) if node.detection_counts else float("nan"),
                "zero_ratio": (
                    sum(1 for x in node.detection_counts if x <= 0.0) / len(node.detection_counts)
                ) if node.detection_counts else float("nan"),
            },
        },
    }
    summary["cadence_consistency"] = _compute_cadence_consistency(summary)
    summary["health"] = _compute_health(summary)

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

    print_section("/detections Load")
    dstream = summary["detection_stream"]
    dstats = dstream["detections_per_msg"]
    print(
        f"/detections: count={dstream['count']} hz={dstream['hz']:.3f} "
        f"det/msg p50={dstats['p50']:.3f} p95={dstats['p95']:.3f} p99={dstats['p99']:.3f} "
        f"mean={dstats['mean']:.3f} zero_ratio={dstats['zero_ratio']:.3f}"
    )

    print_section("Combined Health Score")
    health = summary["health"]
    print(
        f"score={health['score']:.1f} "
        f"latency={health['latency_component']:.1f} "
        f"cadence={health['cadence_component']:.1f} "
        f"throughput={health['throughput_component']:.1f} "
        f"throughput_ratio={health['throughput_ratio']:.3f} "
        f"(e2e_p95={health['e2e_det_p95_ms']:.3f} ms, pub_dt_p95={health['pub_dt_p95_ms']:.3f} ms)"
    )

    print_section("Cadence Consistency")
    cadence = summary["cadence_consistency"]
    print(
        f"det_out_fps_hz={cadence['det_out_fps_hz']:.3f} "
        f"fps_from_pub_dt_p50={cadence['fps_from_pub_dt_p50']:.3f} "
        f"relative_delta={cadence['relative_delta']:.3f} "
        f"max={cadence['relative_delta_max']:.3f} "
        f"within_tolerance={cadence['within_tolerance']}"
    )

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
