#!/usr/bin/env python3
"""Validate live timing invariants from /timing, /timing_tracker, /timing_target, /detections.

This utility runs for a short duration (or until one message per topic in --once mode),
checks ordering/sanity invariants, and prints a concise pass/fail report.
Exit code is non-zero if any invariant fails.
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from thesis_msgs.msg import Timing
from vision_msgs.msg import Detection2DArray

from timing_contract import (
    DET_OUT_FPS_WINDOW_SECONDS,
    FPS_INTERVAL_RELATIVE_DELTA_MAX,
    resolve_metric,
    topic_fields,
)


TOPIC_METRIC_FIELDS = {
    "/timing": list(topic_fields("/timing")),
    "/timing_tracker": list(topic_fields("/timing_tracker")),
    "/timing_target": list(topic_fields("/timing_target")),
}

NS_FIELDS = [
    "src_stamp_ns",
    "t_cam_msg_seen_ns",
    "t_pre_start_ns",
    "t_pre_end_ns",
    "t_zmq_send_start_ns",
    "t_zmq_send_end_ns",
    "t_zmq_recv_start_ns",
    "t_zmq_recv_end_ns",
    "t_decode_start_ns",
    "t_decode_end_ns",
    "t_det_pub_start_ns",
    "t_det_pub_end_ns",
    "t_req_recv_ns",
    "t_frame_unpack_start_ns",
    "t_frame_unpack_end_ns",
    "t_infer_start_ns",
    "t_infer_end_ns",
    "t_post_start_ns",
    "t_post_end_ns",
    "t_reply_send_ns",
    "t_track_cb_start_ns",
    "t_track_cb_end_ns",
    "t_target_cb_start_ns",
    "t_target_cb_end_ns",
    "pts_ns",
    "t_pub_ns",
]

@dataclass
class InvariantStat:
    passes: int = 0
    fails: int = 0
    first_fail: Optional[str] = None


class InvariantTracker:
    def __init__(self) -> None:
        self.stats: Dict[str, InvariantStat] = defaultdict(InvariantStat)

    def check(self, name: str, condition: bool, fail_msg: str) -> None:
        st = self.stats[name]
        if condition:
            st.passes += 1
        else:
            st.fails += 1
            if st.first_fail is None:
                st.first_fail = fail_msg

    def any_failures(self) -> bool:
        return any(st.fails > 0 for st in self.stats.values())


def _fmt_val(v) -> str:
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def _is_populated_number(v) -> bool:
    return bool(v is not None and float(v) != 0.0)


def _ordered_non_decreasing(values: Iterable[int]) -> bool:
    seq = list(values)
    return all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))


class TimingInvariantNode(Node):
    def __init__(self) -> None:
        super().__init__("timing_invariant_checker")

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.inv = InvariantTracker()
        self.counts = {"/timing": 0, "/timing_tracker": 0, "/timing_target": 0}

        self.frame_seen = {
            "/timing": set(),
            "/timing_tracker": set(),
            "/timing_target": set(),
        }
        self.e2e_det_by_frame: Dict[int, float] = {}
        self.detection_msg_count = 0
        self._det_arrival_ns: deque[int] = deque(maxlen=240)
        self._det_out_fps_latest: Optional[float] = None

        self.zero_counts: Dict[str, Dict[str, int]] = {
            "/timing": defaultdict(int),
            "/timing_tracker": defaultdict(int),
            "/timing_target": defaultdict(int),
        }

        self.create_subscription(Timing, "/timing", self._on_timing, qos)
        self.create_subscription(Timing, "/timing_tracker", self._on_timing_tracker, qos)
        self.create_subscription(Timing, "/timing_target", self._on_timing_target, qos)
        self.create_subscription(Detection2DArray, "/detections", self._on_detections, qos)

    def _on_detections(self, _msg: Detection2DArray) -> None:
        now_ns = time.monotonic_ns()
        self.detection_msg_count += 1
        self._det_arrival_ns.append(now_ns)

        cutoff_ns = now_ns - int(DET_OUT_FPS_WINDOW_SECONDS * 1e9)
        while self._det_arrival_ns and self._det_arrival_ns[0] < cutoff_ns:
            self._det_arrival_ns.popleft()

        if len(self._det_arrival_ns) >= 2:
            dt_ns = self._det_arrival_ns[-1] - self._det_arrival_ns[0]
            if dt_ns > 0:
                self._det_out_fps_latest = (len(self._det_arrival_ns) - 1) / (dt_ns / 1e9)

    def _check_basic_sanity(self, topic: str, msg: Timing) -> None:
        for field in NS_FIELDS:
            v = getattr(msg, field)
            name = f"A.ns_non_negative.{topic}.{field}"
            self.inv.check(
                name,
                isinstance(v, int) and v >= 0,
                f"{topic}: {field}={_fmt_val(v)}",
            )
            if int(v) == 0:
                self.zero_counts[topic][field] += 1

        for field in TOPIC_METRIC_FIELDS.get(topic, []):
            v, source_field = resolve_metric(msg, field)
            name = f"A.ms_finite.{topic}.{field}"
            self.inv.check(
                name,
                math.isfinite(v),
                f"{topic}: {field}({source_field})={_fmt_val(v)}",
            )
            if v == 0.0:
                self.zero_counts[topic][source_field] += 1

        for field in TOPIC_METRIC_FIELDS.get(topic, []):
            v, source_field = resolve_metric(msg, field)
            if _is_populated_number(v):
                name = f"A.derived_ms_non_negative.{topic}.{field}"
                self.inv.check(
                    name,
                    v >= 0.0,
                    f"{topic}: {field}({source_field})={_fmt_val(v)}",
                )

        self.inv.check(
            f"F.frame_id_non_zero.{topic}",
            int(msg.frame_id) > 0,
            f"{topic}: frame_id={int(msg.frame_id)}",
        )

    def _check_order_pair(self, topic: str, name: str, left: int, right: int, labels: str) -> None:
        if left > 0 and right > 0:
            self.inv.check(
                name,
                left <= right,
                f"{topic}: {labels} violated ({left} > {right})",
            )

    def _check_order_chain(self, topic: str, name: str, fields: list[str], msg: Timing) -> None:
        vals = [int(getattr(msg, f)) for f in fields]
        if all(v > 0 for v in vals):
            self.inv.check(
                name,
                _ordered_non_decreasing(vals),
                f"{topic}: " + ", ".join(f"{f}={v}" for f, v in zip(fields, vals)),
            )

    def _on_timing(self, msg: Timing) -> None:
        topic = "/timing"
        self.counts[topic] += 1
        self.frame_seen[topic].add(int(msg.frame_id))
        if float(msg.e2e_det_ms) > 0.0 and int(msg.frame_id) > 0:
            self.e2e_det_by_frame[int(msg.frame_id)] = float(msg.e2e_det_ms)

        self._check_basic_sanity(topic, msg)

        self._check_order_chain(
            topic,
            "B.host_chain.cam_pre",
            ["t_cam_msg_seen_ns", "t_pre_start_ns", "t_pre_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "B.host_chain.pre_send",
            ["t_pre_end_ns", "t_zmq_send_start_ns", "t_zmq_send_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "B.host_chain.send_recv",
            ["t_zmq_send_end_ns", "t_zmq_recv_start_ns", "t_zmq_recv_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "B.host_chain.recv_decode",
            ["t_zmq_recv_end_ns", "t_decode_start_ns", "t_decode_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "B.host_chain.decode_pub",
            ["t_decode_end_ns", "t_det_pub_start_ns", "t_det_pub_end_ns"],
            msg,
        )

        if _is_populated_number(float(msg.e2e_det_ms)) and _is_populated_number(float(msg.infer_ms)):
            self.inv.check(
                "B.e2e_det_ge_infer",
                float(msg.e2e_det_ms) >= float(msg.infer_ms),
                f"{topic}: e2e_det_ms={_fmt_val(float(msg.e2e_det_ms))}, infer_ms={_fmt_val(float(msg.infer_ms))}",
            )

        if _is_populated_number(float(msg.pub_dt_ms)) and self._det_out_fps_latest is not None and self._det_out_fps_latest > 0.0:
            pub_dt_ms = float(msg.pub_dt_ms)
            expected_ms = 1000.0 / float(self._det_out_fps_latest)
            rel_delta = abs(pub_dt_ms - expected_ms) / max(expected_ms, 1e-9)
            self.inv.check(
                "B.pub_dt_vs_det_out_fps_consistent",
                rel_delta <= FPS_INTERVAL_RELATIVE_DELTA_MAX,
                (
                    f"{topic}: pub_dt_ms={_fmt_val(pub_dt_ms)} expected_from_det_out_fps_ms={_fmt_val(expected_ms)} "
                    f"det_out_fps={_fmt_val(self._det_out_fps_latest)} rel_delta={_fmt_val(rel_delta)}"
                ),
            )

        self._check_order_chain(
            topic,
            "C.container_chain.req_unpack",
            ["t_req_recv_ns", "t_frame_unpack_start_ns", "t_frame_unpack_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "C.container_chain.unpack_infer",
            ["t_frame_unpack_end_ns", "t_infer_start_ns", "t_infer_end_ns"],
            msg,
        )
        self._check_order_chain(
            topic,
            "C.container_chain.infer_post",
            ["t_infer_end_ns", "t_post_start_ns", "t_post_end_ns"],
            msg,
        )
        self._check_order_pair(
            topic,
            "C.container_pair.post_reply",
            int(msg.t_post_end_ns),
            int(msg.t_reply_send_ns),
            "t_post_end_ns<=t_reply_send_ns",
        )

    def _on_timing_tracker(self, msg: Timing) -> None:
        topic = "/timing_tracker"
        self.counts[topic] += 1
        self.frame_seen[topic].add(int(msg.frame_id))

        self._check_basic_sanity(topic, msg)
        self._check_order_pair(
            topic,
            "D.tracker_order",
            int(msg.t_track_cb_start_ns),
            int(msg.t_track_cb_end_ns),
            "t_track_cb_start_ns<=t_track_cb_end_ns",
        )
        if _is_populated_number(float(msg.track_ms)):
            self.inv.check(
                "D.track_ms_non_negative",
                float(msg.track_ms) >= 0.0,
                f"{topic}: track_ms={_fmt_val(float(msg.track_ms))}",
            )

    def _on_timing_target(self, msg: Timing) -> None:
        topic = "/timing_target"
        self.counts[topic] += 1
        self.frame_seen[topic].add(int(msg.frame_id))

        self._check_basic_sanity(topic, msg)
        self._check_order_pair(
            topic,
            "E.target_order",
            int(msg.t_target_cb_start_ns),
            int(msg.t_target_cb_end_ns),
            "t_target_cb_start_ns<=t_target_cb_end_ns",
        )

        if _is_populated_number(float(msg.target_ms)):
            self.inv.check(
                "E.target_ms_non_negative",
                float(msg.target_ms) >= 0.0,
                f"{topic}: target_ms={_fmt_val(float(msg.target_ms))}",
            )

        if _is_populated_number(float(msg.e2e_target_ms)):
            self.inv.check(
                "E.e2e_target_ms_non_negative",
                float(msg.e2e_target_ms) >= 0.0,
                f"{topic}: e2e_target_ms={_fmt_val(float(msg.e2e_target_ms))}",
            )

        fid = int(msg.frame_id)
        if fid > 0 and _is_populated_number(float(msg.e2e_target_ms)) and fid in self.e2e_det_by_frame:
            det_ms = float(self.e2e_det_by_frame[fid])
            tgt_ms = float(msg.e2e_target_ms)
            self.inv.check(
                "E.e2e_target_ge_e2e_det",
                tgt_ms >= det_ms,
                f"frame_id={fid}: e2e_target_ms={_fmt_val(tgt_ms)}, e2e_det_ms={_fmt_val(det_ms)}",
            )

    def has_one_each(self) -> bool:
        return all(self.counts[t] > 0 for t in self.counts)


def print_report(node: TimingInvariantNode) -> None:
    print("=== Live Timing Invariant Report ===")
    print("samples:")
    for topic in ["/timing", "/timing_tracker", "/timing_target"]:
        print(f"  {topic}: {node.counts[topic]}")
    print(f"  /detections: {node.detection_msg_count}")
    if node._det_out_fps_latest is not None:
        print(f"  det_out_fps_latest_hz: {node._det_out_fps_latest:.3f}")

    common_all = (
        node.frame_seen["/timing"]
        & node.frame_seen["/timing_tracker"]
        & node.frame_seen["/timing_target"]
    )
    print("frame consistency:")
    print(f"  common frame_id count across all topics: {len(common_all)}")
    if common_all:
        sample = sorted(common_all)[:10]
        print(f"  example common frame_ids: {sample}")

    print("invariants:")
    for name in sorted(node.inv.stats.keys()):
        st = node.inv.stats[name]
        print(f"  {name}: pass={st.passes} fail={st.fails}")
        if st.first_fail is not None:
            print(f"    first_fail: {st.first_fail}")

    print("warnings:")
    warned_any = False
    for topic in ["/timing", "/timing_tracker", "/timing_target"]:
        total = node.counts[topic]
        if total <= 0:
            continue
        for field, zeros in sorted(node.zero_counts[topic].items()):
            ratio = zeros / total
            if ratio >= 0.95:
                print(f"  {topic} field {field} is zero in {zeros}/{total} samples ({ratio:.0%})")
                warned_any = True
    if not warned_any:
        print("  none")


class _StopFlag:
    def __init__(self) -> None:
        self.stop = False

    def handler(self, _sig, _frame) -> None:
        self.stop = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check live timing topic invariants")
    parser.add_argument("--duration", type=float, default=8.0, help="Sampling duration in seconds")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after at least one message is received from each topic",
    )
    parser.add_argument(
        "--topic-timeout",
        type=float,
        default=12.0,
        help="Timeout in seconds for waiting topic data in --once mode",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rclpy.init(args=None)
    node = TimingInvariantNode()

    stopper = _StopFlag()
    signal.signal(signal.SIGINT, stopper.handler)
    signal.signal(signal.SIGTERM, stopper.handler)

    start = time.monotonic()
    end_time = start + max(0.1, float(args.duration))
    once_deadline = start + max(0.1, float(args.topic_timeout))

    try:
        while rclpy.ok() and not stopper.stop:
            rclpy.spin_once(node, timeout_sec=0.1)
            now = time.monotonic()

            if args.once:
                if node.has_one_each():
                    break
                if now >= once_deadline:
                    break
            else:
                if now >= end_time:
                    break
    finally:
        print_report(node)
        failed = node.inv.any_failures()

        if args.once and not node.has_one_each():
            print("ERROR: --once mode did not receive all required topics before timeout")
            failed = True

        node.destroy_node()
        rclpy.shutdown()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
