#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Optional, Tuple, List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.executors import ExternalShutdownException

from thesis_msgs.msg import Track2DArray, TargetState, Timing


def now_ns() -> int:
    return time.monotonic_ns()


def sensor_to_target_ms_if_comparable(src_stamp_ns: int, t_target_cb_end_ns: int) -> float | None:
    """Return sensor->target latency only when the two stamps look comparable.

    src_stamp_ns may come from ROS header time (often wall/system clock), while
    t_target_cb_end_ns is monotonic. Mixing clock domains is invalid.
    Accept only small, non-negative deltas that match expected end-to-end latency.
    """
    if src_stamp_ns <= 0:
        return None

    delta_ns = int(t_target_cb_end_ns) - int(src_stamp_ns)
    if 0 <= delta_ns <= 60_000_000_000:  # accept up to 60 seconds
        return float(delta_ns) / 1e6

    return None


def _track_score(t) -> float:
    # Prefer explicit score if your Track2D has it
    if hasattr(t, "score"):
        return float(t.score)
    return 1.0


def _track_confirmed(t) -> bool:
    if hasattr(t, "confirmed"):
        return bool(t.confirmed)
    # If Track2D has no confirmed flag, treat all as confirmed
    return True


def _track_area(t) -> float:
    if hasattr(t, "area"):
        return float(t.area)
    # else compute from w,h if present
    if hasattr(t, "w") and hasattr(t, "h"):
        return float(max(0.0, t.w) * max(0.0, t.h))
    return 0.0


class ThesisTargetSelectorNode(Node):
    def __init__(self) -> None:
        super().__init__("thesis_target_selector_node")

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub = self.create_subscription(
            Track2DArray,
            "/tracks",
            self.on_tracks,
            qos,
        )
        self.sub_timing = self.create_subscription(
            Timing,
            "/timing",
            self.on_timing,
            qos,
        )

        self.pub = self.create_publisher(
            TargetState,
            "/target",
            qos,
        )
        self.pub_timing = self.create_publisher(
            Timing,
            "/timing_target",
            qos,
        )

        self.declare_parameter("ambiguity_score_gap_ratio", 0.05)
        self.declare_parameter("ambiguity_log_every_n", 30)
        self.declare_parameter("enable_ambiguity_quality_override", False)
        self.declare_parameter("ambiguity_quality_value", 0.0)

        self.ambiguity_score_gap_ratio = float(self.get_parameter("ambiguity_score_gap_ratio").value)
        self.ambiguity_log_every_n = int(self.get_parameter("ambiguity_log_every_n").value)
        self.enable_ambiguity_quality_override = bool(
            self.get_parameter("enable_ambiguity_quality_override").value
        )
        self.ambiguity_quality_value = float(self.get_parameter("ambiguity_quality_value").value)

        self.prev_id: Optional[int] = None
        self._prev_ambiguity = False
        self._ambiguity_count = 0
        self._warned_sensor_clock_mismatch = False
        self.frame_context: dict[int, tuple[int, int]] = {}
        self.max_context = 1024

    def on_timing(self, msg: Timing) -> None:
        frame_id = int(msg.frame_id)
        if frame_id <= 0:
            return

        self.frame_context[frame_id] = (int(msg.src_stamp_ns), int(msg.t_cam_msg_seen_ns))
        if len(self.frame_context) > self.max_context:
            oldest = next(iter(self.frame_context))
            self.frame_context.pop(oldest, None)

    def on_tracks(self, msg: Track2DArray) -> None:
        t_target_cb_start_ns = now_ns()
        tracks = list(msg.tracks)
        prev_id_before = self.prev_id

        ambiguous = False
        if len(tracks) >= 2:
            ranked_for_ambiguity = sorted(
                tracks,
                key=lambda t: (float(t.score), float(max(0.0, t.w) * max(0.0, t.h))),
                reverse=True,
            )
            top_score = float(ranked_for_ambiguity[0].score)
            second_score = float(ranked_for_ambiguity[1].score)
            if top_score > 0.0:
                gap_ratio = (top_score - second_score) / top_score
                ambiguous = gap_ratio < self.ambiguity_score_gap_ratio

        if ambiguous:
            self._ambiguity_count += 1
            should_log = (
                not self._prev_ambiguity
                or (
                    self.ambiguity_log_every_n > 0
                    and (self._ambiguity_count % self.ambiguity_log_every_n == 0)
                )
            )
            if should_log:
                self.get_logger().warning(
                    f"ambiguity_flag=true frame_id={msg.frame_id} track_count={len(tracks)}"
                )
        elif self._prev_ambiguity:
            self.get_logger().info(f"ambiguity_flag=false frame_id={msg.frame_id}")
        self._prev_ambiguity = ambiguous

        # No confirmed flag in Track2D, so treat all as eligible
        selected = None

        # 1) sticky previous id if still present
        if self.prev_id is not None:
            for t in tracks:
                if int(t.id) == int(self.prev_id):
                    selected = t
                    break

        # 2) else best by (score desc, area desc)
        if selected is None and tracks:
            tracks.sort(key=lambda t: (float(t.score), float(max(0.0, t.w) * max(0.0, t.h))), reverse=True)
            selected = tracks[0]

        out = TargetState()
        out.header = msg.header
        out.frame_id = int(msg.frame_id)

        # Prefer context carried in tracks, but fall back to /timing cache when needed.
        src_stamp_ns = int(msg.src_stamp_ns)
        t_cam_msg_seen_ns = int(msg.t_cam_msg_seen_ns)
        if (src_stamp_ns <= 0 or t_cam_msg_seen_ns <= 0) and int(msg.frame_id) > 0:
            cached_src, cached_cam = self.frame_context.get(int(msg.frame_id), (0, 0))
            if src_stamp_ns <= 0:
                src_stamp_ns = int(cached_src)
            if t_cam_msg_seen_ns <= 0:
                t_cam_msg_seen_ns = int(cached_cam)

        out.src_stamp_ns = int(src_stamp_ns)
        out.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        out.t_target_cb_start_ns = int(t_target_cb_start_ns)

        if selected is None:
            t_target_cb_end_ns = now_ns()
            target_ms = (t_target_cb_end_ns - t_target_cb_start_ns) / 1e6
            out.id = 0
            out.cx = 0.0
            out.cy = 0.0
            out.w = 0.0
            out.h = 0.0
            out.score = 0.0
            out.quality = 0.0
            out.t_target_cb_end_ns = int(t_target_cb_end_ns)
            self.prev_id = None
            self.pub.publish(out)

            tmsg = Timing()
            tmsg.frame_id = int(msg.frame_id)
            tmsg.src_stamp_ns = int(src_stamp_ns)
            tmsg.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
            tmsg.t_target_cb_start_ns = int(t_target_cb_start_ns)
            tmsg.t_target_cb_end_ns = int(t_target_cb_end_ns)
            tmsg.target_ms = float(target_ms)
            if t_cam_msg_seen_ns > 0 and t_target_cb_end_ns >= int(t_cam_msg_seen_ns):
                tmsg.e2e_target_ms = float((t_target_cb_end_ns - int(t_cam_msg_seen_ns)) / 1e6)
            sensor_ms = sensor_to_target_ms_if_comparable(int(src_stamp_ns), t_target_cb_end_ns)
            if sensor_ms is not None:
                tmsg.sensor_to_target_ms = sensor_ms
            elif int(src_stamp_ns) > 0 and not self._warned_sensor_clock_mismatch:
                self.get_logger().warning(
                    "Skipping sensor_to_target_ms: src_stamp_ns clock domain is not comparable to host monotonic time"
                )
                self._warned_sensor_clock_mismatch = True
            self.pub_timing.publish(tmsg)
            return

        new_id = int(selected.id)
        if prev_id_before is None and new_id > 0:
            self.get_logger().info(f"target_reacquired=true id={new_id} frame_id={msg.frame_id}")
        elif prev_id_before is not None and prev_id_before != new_id:
            self.get_logger().info(
                f"target_switch prev_id={prev_id_before} new_id={new_id} frame_id={msg.frame_id}"
            )
        self.prev_id = new_id

        out.id = int(selected.id)
        out.cx = float(selected.cx)
        out.cy = float(selected.cy)
        out.w = float(selected.w)
        out.h = float(selected.h)
        out.score = float(selected.score)
        if ambiguous and self.enable_ambiguity_quality_override:
            out.quality = float(self.ambiguity_quality_value)
        else:
            out.quality = 1.0  # deterministic "selected"
        t_target_cb_end_ns = now_ns()
        out.t_target_cb_end_ns = int(t_target_cb_end_ns)
        self.pub.publish(out)

        tmsg = Timing()
        tmsg.frame_id = int(msg.frame_id)
        tmsg.src_stamp_ns = int(src_stamp_ns)
        tmsg.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        tmsg.t_target_cb_start_ns = int(t_target_cb_start_ns)
        tmsg.t_target_cb_end_ns = int(t_target_cb_end_ns)
        tmsg.target_ms = float((t_target_cb_end_ns - t_target_cb_start_ns) / 1e6)
        if t_cam_msg_seen_ns > 0 and t_target_cb_end_ns >= int(t_cam_msg_seen_ns):
            tmsg.e2e_target_ms = float((t_target_cb_end_ns - int(t_cam_msg_seen_ns)) / 1e6)
        sensor_ms = sensor_to_target_ms_if_comparable(int(src_stamp_ns), t_target_cb_end_ns)
        if sensor_ms is not None:
            tmsg.sensor_to_target_ms = sensor_ms
        elif int(src_stamp_ns) > 0 and not self._warned_sensor_clock_mismatch:
            self.get_logger().warning(
                "Skipping sensor_to_target_ms: src_stamp_ns clock domain is not comparable to host monotonic time"
            )
            self._warned_sensor_clock_mismatch = True
        self.pub_timing.publish(tmsg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ThesisTargetSelectorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()