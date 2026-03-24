#!/usr/bin/env python3
"""Unified tracker node supporting multiple tracking backends."""
from __future__ import annotations

import gc
import time
from contextlib import contextmanager
from typing import List, Tuple, Union

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.serialization import serialize_message

from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import Track2D, Track2DArray, Timing

from .backends import BBox, TrackOutput
from .backends.sort_backend import SortBackend
from .backends.ocsort_backend import OCSortBackend
from .backends.bytetrack_backend import ByteTrackBackend

# Type alias for tracker backends
TrackerBackendType = Union[SortBackend, OCSortBackend, ByteTrackBackend]


def xywh_center_to_xyxy(cx: float, cy: float, w: float, h: float) -> BBox:
    """Convert center format to corner format."""
    x1 = cx - 0.5 * w
    y1 = cy - 0.5 * h
    x2 = cx + 0.5 * w
    y2 = cy + 0.5 * h
    return x1, y1, x2, y2


def xyxy_to_cxcywh(b: BBox) -> Tuple[float, float, float, float]:
    """Convert corner format to center format."""
    x1, y1, x2, y2 = b
    w = x2 - x1
    h = y2 - y1
    cx = x1 + 0.5 * w
    cy = y1 + 0.5 * h
    return cx, cy, w, h


def _parse_frame_id(frame_id_str: str) -> int:
    """Parse frame ID from 'frame_<int>' format."""
    try:
        if frame_id_str.startswith("frame_"):
            return int(frame_id_str.split("_", 1)[1])
    except Exception:
        pass
    return 0


def now_ns() -> int:
    return time.monotonic_ns()


class SectionProfiler:
    """Minimal per-callback section profiler using perf_counter_ns."""

    __slots__ = ("starts", "durations")

    def __init__(self) -> None:
        self.starts: dict[str, int] = {}
        self.durations: dict[str, int] = {}

    @contextmanager
    def section(self, name: str):
        t0 = now_ns()
        self.starts[name] = t0
        try:
            yield
        finally:
            self.durations[name] = now_ns() - t0

    def ms(self, name: str) -> float:
        return float(self.durations.get(name, 0)) / 1e6


def _estimate_track_msg_payload_bytes(tracks: List[Track2D]) -> int:
    """Cheap estimate used only for correlation, not exact DDS wire size."""
    fixed_per_track = 4 + 5 * 4  # id + (cx, cy, w, h, score)
    total = 0
    for t in tracks:
        total += fixed_per_track + len(t.label)
    return total


class TrackerNode(Node):
    """Unified tracker node with selectable backend."""
    
    def __init__(self) -> None:
        super().__init__("tracker_node")
        
        # Declare tracker type parameter
        self.declare_parameter("tracker_type", "sort")
        tracker_type = str(self.get_parameter("tracker_type").value)
        
        # Create the appropriate backend
        self.backend = self._create_backend(tracker_type)
        
        # Setup ROS communication
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        
        self.sub = self.create_subscription(
            Detection2DArray, "/detections", self.on_detections, qos
        )
        self.sub_timing = self.create_subscription(
            Timing, "/timing", self.on_timing, qos
        )
        self.pub = self.create_publisher(Track2DArray, "/tracks", qos)
        self.pub_timing = self.create_publisher(Timing, "/timing_tracker", qos)

        self.frame_context: dict[int, tuple[int, int]] = {}
        self.max_context = 512
        
        # Declare min_score parameter (common filtering)
        self.declare_parameter("min_score", 0.35)
        self.min_score = float(self.get_parameter("min_score").value)
        self.declare_parameter("publish_tracks", True)
        self.publish_tracks = bool(self.get_parameter("publish_tracks").value)

        # Instrumentation controls
        self.declare_parameter("profiling_enabled", True)
        self.declare_parameter("profiling_log_every_n", 30)
        self.declare_parameter("profiling_publish_details", True)
        self.declare_parameter("profiling_serialize_sample_every_n", 0)
        self.declare_parameter("profiling_gc_probe", True)
        self.profiling_enabled = bool(self.get_parameter("profiling_enabled").value)
        self.profiling_log_every_n = int(self.get_parameter("profiling_log_every_n").value)
        self.profiling_publish_details = bool(
            self.get_parameter("profiling_publish_details").value
        )
        self.profiling_serialize_sample_every_n = int(
            self.get_parameter("profiling_serialize_sample_every_n").value
        )
        self.profiling_gc_probe = bool(self.get_parameter("profiling_gc_probe").value)
        self._frame_counter = 0
        self._gc_collections_seen = 0

        if self.profiling_gc_probe:
            gc.callbacks.append(self._on_gc_event)
        
        self.get_logger().info(
            "Tracker node ready: "
            f"type={tracker_type}, min_score={self.min_score}, "
            f"publish_tracks={self.publish_tracks}, "
            f"profiling_enabled={self.profiling_enabled}, "
            f"log_every_n={self.profiling_log_every_n}, "
            f"publish_details={self.profiling_publish_details}, "
            f"serialize_sample_every_n={self.profiling_serialize_sample_every_n}, "
            f"gc_probe={self.profiling_gc_probe}"
        )

    def _on_gc_event(self, phase: str, _info: dict) -> None:
        if phase == "stop":
            self._gc_collections_seen += 1
    
    def _create_backend(self, tracker_type: str) -> TrackerBackendType:
        """Create tracker backend based on type."""
        if tracker_type == "sort":
            self.declare_parameter("iou_threshold", 0.18)
            self.declare_parameter("max_age", 4)
            self.declare_parameter("min_hits", 3)
            self.declare_parameter("centre_gate", 200.0)
            self.declare_parameter("gate_x", -1.0)
            self.declare_parameter("gate_y", -1.0)

            gate_x = float(self.get_parameter("gate_x").value)
            gate_y = float(self.get_parameter("gate_y").value)
            gate_x = None if gate_x <= 0.0 else gate_x
            gate_y = None if gate_y <= 0.0 else gate_y
            
            return SortBackend(
                iou_threshold=float(self.get_parameter("iou_threshold").value),
                max_age=int(self.get_parameter("max_age").value),
                min_hits=int(self.get_parameter("min_hits").value),
                centre_gate=float(self.get_parameter("centre_gate").value),
                gate_x=gate_x,
                gate_y=gate_y,
            )
        
        elif tracker_type == "ocsort":
            self.declare_parameter("iou_threshold", 0.18)
            self.declare_parameter("max_age", 4)
            self.declare_parameter("min_hits", 3)
            self.declare_parameter("centre_gate", 200.0)
            self.declare_parameter("delta_t", 3)
            self.declare_parameter("asso_threshold", 0.1)
            
            return OCSortBackend(
                iou_threshold=float(self.get_parameter("iou_threshold").value),
                max_age=int(self.get_parameter("max_age").value),
                min_hits=int(self.get_parameter("min_hits").value),
                centre_gate=float(self.get_parameter("centre_gate").value),
                delta_t=int(self.get_parameter("delta_t").value),
                asso_threshold=float(self.get_parameter("asso_threshold").value)
            )
        
        elif tracker_type == "bytetrack":
            self.declare_parameter("track_thresh", 0.5)
            self.declare_parameter("match_thresh", 0.8)
            self.declare_parameter("track_buffer", 30)
            self.declare_parameter("det_thresh", 0.2)
            self.declare_parameter("second_match_thresh", 0.5)
            
            return ByteTrackBackend(
                track_thresh=float(self.get_parameter("track_thresh").value),
                match_thresh=float(self.get_parameter("match_thresh").value),
                track_buffer=int(self.get_parameter("track_buffer").value),
                det_thresh=float(self.get_parameter("det_thresh").value),
                second_match_thresh=float(self.get_parameter("second_match_thresh").value)
            )
        
        else:
            self.get_logger().error(f"Unknown tracker_type: {tracker_type}, defaulting to SORT")
            return SortBackend()

    def on_timing(self, msg: Timing) -> None:
        frame_id = int(msg.frame_id)
        if frame_id <= 0:
            return

        self.frame_context[frame_id] = (int(msg.src_stamp_ns), int(msg.t_cam_msg_seen_ns))
        if len(self.frame_context) > self.max_context:
            oldest = next(iter(self.frame_context))
            self.frame_context.pop(oldest, None)
    
    def on_detections(self, msg: Detection2DArray) -> None:
        """Process detection message and publish tracks."""
        self._frame_counter += 1
        profiler = SectionProfiler()

        gc_before = self._gc_collections_seen
        gc_count_before = gc.get_count() if self.profiling_gc_probe else (0, 0, 0)
        t_track_cb_start_ns = now_ns()
        frame_id = _parse_frame_id(msg.header.frame_id)

        det_boxes: List[BBox] = []
        det_scores: List[float] = []
        
        # Parse detections from vision_msgs format
        for det in msg.detections:
            if not det.results:
                continue
            
            # Get best hypothesis
            best = max(det.results, key=lambda r: float(r.hypothesis.score))
            score = float(best.hypothesis.score)
            
            # Apply min_score filter
            if score < self.min_score:
                continue
            
            # Convert to xyxy format
            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            w = float(det.bbox.size_x)
            h = float(det.bbox.size_y)
            box = xywh_center_to_xyxy(cx, cy, w, h)
            
            det_boxes.append(box)
            det_scores.append(score)
        
        # Get frame timestamp
        frame_time_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)
        
        # track_ms is defined as tracker backend compute only.
        with profiler.section("tracker_update"):
            tracks = self.backend.update(det_boxes, det_scores, frame_time_ns)
        
        # Convert tracks to ROS message
        src_stamp_ns, t_cam_msg_seen_ns = self.frame_context.get(frame_id, (0, 0))
        queue_delay_ms = 0.0
        if t_cam_msg_seen_ns > 0:
            queue_delay_ms = float(t_track_cb_start_ns - int(t_cam_msg_seen_ns)) / 1e6

        with profiler.section("build_msg"):
            out = Track2DArray()
            out.header = msg.header
            out.frame_id = int(frame_id)
            out.src_stamp_ns = int(src_stamp_ns)
            out.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
            out.t_track_cb_start_ns = int(t_track_cb_start_ns)
            tracks_ros: List[Track2D] = []

            with profiler.section("per_track_loop"):
                for track in tracks:
                    tbox = track.bbox_xyxy
                    cx, cy, w, h = xyxy_to_cxcywh(tbox)

                    # Fast path for performance isolation:
                    # skip per-track best-IoU score recovery in Python.
                    best_score = float(track.score) if float(track.score) > 0.0 else 1.0

                    m = Track2D()
                    m.id = int(track.track_id)
                    m.cx = float(cx)
                    m.cy = float(cy)
                    m.w = float(w)
                    m.h = float(h)
                    m.score = float(best_score)
                    m.label = "person"
                    tracks_ros.append(m)

            out.tracks = tracks_ros

        serialize_ms = -1.0
        serialized_size_bytes = -1
        should_sample_serialize = (
            self.profiling_serialize_sample_every_n > 0
            and (self._frame_counter % self.profiling_serialize_sample_every_n == 0)
        )
        if should_sample_serialize:
            with profiler.section("serialize_tracks"):
                wire = serialize_message(out)
            serialize_ms = profiler.ms("serialize_tracks")
            serialized_size_bytes = len(wire)

        t_track_cb_end_ns_pre_publish = now_ns()
        out.t_track_cb_end_ns = int(t_track_cb_end_ns_pre_publish)
        with profiler.section("publish_tracks"):
            if self.publish_tracks:
                self.pub.publish(out)
        t_track_cb_end_ns = now_ns()

        tmsg = Timing()
        tmsg.frame_id = int(frame_id)
        tmsg.src_stamp_ns = int(src_stamp_ns)
        tmsg.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        tmsg.t_track_cb_start_ns = int(t_track_cb_start_ns)
        tmsg.t_track_cb_end_ns = int(t_track_cb_end_ns)
        tmsg.track_ms = profiler.ms("tracker_update")

        # Structured detailed breakdown reuses explicit stage fields so downstream
        # tooling can consume one timing stream without extra message types.
        if self.profiling_publish_details:
            tmsg.ros_wait_ms = float(queue_delay_ms)
            tmsg.target_ms = profiler.ms("per_track_loop")
            tmsg.recv_ms = profiler.ms("build_msg")
            tmsg.json_ms = profiler.ms("publish_tracks")
            tmsg.loop_ms = float(t_track_cb_end_ns - t_track_cb_start_ns) / 1e6

        self.pub_timing.publish(tmsg)

        gc_after = self._gc_collections_seen
        gc_count_after = gc.get_count() if self.profiling_gc_probe else (0, 0, 0)

        if self.profiling_enabled and self.profiling_log_every_n > 0:
            if self._frame_counter % self.profiling_log_every_n == 0:
                payload_est_bytes = _estimate_track_msg_payload_bytes(tracks_ros)
                self.get_logger().info(
                    "tracker_profile "
                    f"frame={frame_id} "
                    f"det_count={len(det_boxes)} "
                    f"track_count={len(tracks_ros)} "
                    f"queue_delay_ms={queue_delay_ms:.3f} "
                    f"tracker_update_ms={profiler.ms('tracker_update'):.3f} "
                    f"per_track_loop_ms={profiler.ms('per_track_loop'):.3f} "
                    f"build_msg_ms={profiler.ms('build_msg'):.3f} "
                    f"publish_ms={profiler.ms('publish_tracks'):.3f} "
                    f"serialize_ms={serialize_ms:.3f} "
                    f"total_ms={(t_track_cb_end_ns - t_track_cb_start_ns) / 1e6:.3f} "
                    f"msg_est_bytes={payload_est_bytes} "
                    f"msg_serialized_bytes={serialized_size_bytes} "
                    f"gc_collections_delta={gc_after - gc_before} "
                    f"gc_count_before={gc_count_before} "
                    f"gc_count_after={gc_count_after}"
                )

    def destroy_node(self) -> bool:
        if self.profiling_gc_probe:
            try:
                gc.callbacks.remove(self._on_gc_event)
            except ValueError:
                pass
        return super().destroy_node()


def main(args=None) -> None:
    """Main entry point."""
    from rclpy.executors import SingleThreadedExecutor
    
    rclpy.init(args=args)
    node = TrackerNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            executor.shutdown()
        except Exception:
            pass
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
