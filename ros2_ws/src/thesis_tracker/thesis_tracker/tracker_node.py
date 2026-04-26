#!/usr/bin/env python3
"""Unified tracker node supporting multiple tracking backends."""
from __future__ import annotations

from collections import deque
import gc
import time
from contextlib import contextmanager
from typing import List, Tuple, Union

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.parameter import Parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.serialization import serialize_message

from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import Track2D, Track2DArray, Timing

from .backends import BBox, TrackOutput
from .backends.sort_backend import SortBackend
from .backends.ocsort_backend import OCSortBackend
from .backends.bytetrack_backend import ByteTrackBackend
from .backends.deepsort_core_backend import DeepSortBackend

# Type alias for tracker backends
TrackerBackendType = Union[SortBackend, OCSortBackend, ByteTrackBackend, DeepSortBackend]


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

        self._supported_tracker_types = {"sort", "ocsort", "bytetrack", "deepsort"}
        
        # Declare tracker type parameter
        self.declare_parameter("tracker_type", "sort")
        tracker_type = str(self.get_parameter("tracker_type").value).strip().lower()
        if tracker_type not in self._supported_tracker_types:
            self.get_logger().warn(
                f"Unsupported tracker_type '{tracker_type}', defaulting to 'sort'"
            )
            tracker_type = "sort"
        
        # Create the appropriate backend
        self.backend = self._create_backend(tracker_type)
        self._tracker_type_current = tracker_type
        self._param_callback_handle = self.add_on_set_parameters_callback(self._on_set_parameters)
        
        # Setup ROS communication
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        
        self.sub = self.create_subscription(
            Detection2DArray, "/detections", self.on_detections, qos
        )
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.image_topic = str(self.get_parameter("image_topic").value)
        self.sub_image = self.create_subscription(
            Image, self.image_topic, self.on_image, qos
        )
        self.sub_timing = self.create_subscription(
            Timing, "/timing", self.on_timing, qos
        )
        self.pub = self.create_publisher(Track2DArray, "/tracks", qos)
        self.pub_timing = self.create_publisher(Timing, "/timing_tracker", qos)

        self.frame_context: dict[int, tuple[int, int]] = {}
        self.max_context = 512
        self._frame_context_order: deque[int] = deque()
        
        # Declare min_score parameter (common filtering)
        self.declare_parameter("min_score", 0.35)
        self.min_score = float(self.get_parameter("min_score").value)
        self.declare_parameter("publish_tracks", True)
        self.publish_tracks = bool(self.get_parameter("publish_tracks").value)
        self.declare_parameter("publish_tracks_requires_subscribers", False)
        self.publish_tracks_requires_subscribers = bool(
            self.get_parameter("publish_tracks_requires_subscribers").value
        )
        self.declare_parameter("publish_timing_topic", False)
        self.publish_timing_topic = bool(self.get_parameter("publish_timing_topic").value)

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

        if self.profiling_serialize_sample_every_n > 0:
            self.get_logger().warn(
                "Tracker serialization profiling is enabled; this can increase latency jitter"
            )

        if self.profiling_gc_probe:
            gc.callbacks.append(self._on_gc_event)
        
        self.get_logger().info(
            "Tracker node ready: "
            f"type={self._tracker_type_current}, min_score={self.min_score}, "
            f"image_topic={self.image_topic}, "
            f"publish_tracks={self.publish_tracks}, "
            f"publish_tracks_requires_subscribers={self.publish_tracks_requires_subscribers}, "
            f"publish_timing_topic={self.publish_timing_topic}, "
            f"profiling_enabled={self.profiling_enabled}, "
            f"log_every_n={self.profiling_log_every_n}, "
            f"publish_details={self.profiling_publish_details}, "
            f"serialize_sample_every_n={self.profiling_serialize_sample_every_n}, "
            f"gc_probe={self.profiling_gc_probe}"
        )

    def _declare_param_if_missing(self, name: str, default_value):
        if self.has_parameter(name):
            return self.get_parameter(name).value
        return self.declare_parameter(name, default_value).value

    def _on_set_parameters(self, parameters: List[Parameter]) -> SetParametersResult:
        requested_tracker: str | None = None

        for parameter in parameters:
            if parameter.name == "tracker_type":
                requested_tracker = str(parameter.value).strip().lower()

        if requested_tracker is None:
            return SetParametersResult(successful=True)

        if requested_tracker not in self._supported_tracker_types:
            return SetParametersResult(
                successful=False,
                reason=(
                    f"unsupported tracker_type '{requested_tracker}', "
                    "supported: sort, ocsort, bytetrack, deepsort"
                ),
            )

        if requested_tracker == self._tracker_type_current:
            return SetParametersResult(successful=True)

        try:
            self.backend = self._create_backend(requested_tracker)
            self.frame_context.clear()
            self._frame_context_order.clear()
            self._tracker_type_current = requested_tracker
            self.get_logger().info(f"Tracker backend switched at runtime: {requested_tracker}")
            return SetParametersResult(successful=True)
        except Exception as exc:
            self.get_logger().error(f"Failed to switch tracker backend to '{requested_tracker}': {exc}")
            return SetParametersResult(successful=False, reason=str(exc))

    def _has_track_subscribers(self) -> bool:
        if not self.publish_tracks_requires_subscribers:
            return True

        sub_count = self.pub.get_subscription_count()
        intra_count = 0
        if hasattr(self.pub, "get_intra_process_subscription_count"):
            intra_count = self.pub.get_intra_process_subscription_count()
        return (sub_count + intra_count) > 0

    def _on_gc_event(self, phase: str, _info: dict) -> None:
        if phase == "stop":
            self._gc_collections_seen += 1
    
    def _create_backend(self, tracker_type: str) -> TrackerBackendType:
        """Create tracker backend based on type."""
        if tracker_type == "sort":
            iou_threshold = float(self._declare_param_if_missing("iou_threshold", 0.18))
            max_age = int(self._declare_param_if_missing("max_age", 4))
            min_hits = int(self._declare_param_if_missing("min_hits", 3))
            centre_gate = float(self._declare_param_if_missing("centre_gate", 200.0))
            gate_x = float(self._declare_param_if_missing("gate_x", -1.0))
            gate_y = float(self._declare_param_if_missing("gate_y", -1.0))
            gate_x = None if gate_x <= 0.0 else gate_x
            gate_y = None if gate_y <= 0.0 else gate_y
            
            return SortBackend(
                iou_threshold=iou_threshold,
                max_age=max_age,
                min_hits=min_hits,
                centre_gate=centre_gate,
                gate_x=gate_x,
                gate_y=gate_y,
            )
        
        elif tracker_type == "ocsort":
            iou_threshold = float(self._declare_param_if_missing("iou_threshold", 0.18))
            max_age = int(self._declare_param_if_missing("max_age", 4))
            min_hits = int(self._declare_param_if_missing("min_hits", 3))
            centre_gate = float(self._declare_param_if_missing("centre_gate", 200.0))
            delta_t = int(self._declare_param_if_missing("delta_t", 3))
            asso_threshold = float(self._declare_param_if_missing("asso_threshold", 0.1))
            
            return OCSortBackend(
                iou_threshold=iou_threshold,
                max_age=max_age,
                min_hits=min_hits,
                centre_gate=centre_gate,
                delta_t=delta_t,
                asso_threshold=asso_threshold,
            )
        
        elif tracker_type == "bytetrack":
            track_thresh = float(self._declare_param_if_missing("track_thresh", 0.5))
            match_thresh = float(self._declare_param_if_missing("match_thresh", 0.8))
            track_buffer = int(self._declare_param_if_missing("track_buffer", 30))
            det_thresh = float(self._declare_param_if_missing("det_thresh", 0.2))
            second_match_thresh = float(self._declare_param_if_missing("second_match_thresh", 0.5))
            
            return ByteTrackBackend(
                track_thresh=track_thresh,
                match_thresh=match_thresh,
                track_buffer=track_buffer,
                det_thresh=det_thresh,
                second_match_thresh=second_match_thresh,
            )

        elif tracker_type == "deepsort":
            max_age = int(self._declare_param_if_missing("max_age", 30))
            n_init = int(self._declare_param_if_missing("n_init", 3))
            match_thresh = float(self._declare_param_if_missing("match_thresh", 0.25))
            max_iou_distance = float(
                self._declare_param_if_missing("max_iou_distance", 1.0 - match_thresh)
            )
            centre_gate = float(self._declare_param_if_missing("centre_gate", 200.0))
            appearance_enabled = bool(self._declare_param_if_missing("appearance_enabled", True))
            appearance_max_frame_age_ms = float(
                self._declare_param_if_missing("appearance_max_frame_age_ms", 120.0)
            )
            appearance_hist_bins = int(self._declare_param_if_missing("appearance_hist_bins", 8))
            appearance_weight = float(self._declare_param_if_missing("appearance_weight", 0.0))
            max_cosine_distance = float(
                self._declare_param_if_missing("max_cosine_distance", 0.2)
            )
            # Backward-compatible alias from the earlier histogram prototype.
            appearance_max_distance = float(
                self._declare_param_if_missing("appearance_max_distance", max_cosine_distance)
            )
            appearance_min_crop_size = int(
                self._declare_param_if_missing("appearance_min_crop_size", 12)
            )
            appearance_update_alpha = float(
                self._declare_param_if_missing("appearance_update_alpha", 0.2)
            )
            nn_budget = int(self._declare_param_if_missing("nn_budget", 100))
            only_position_gating = bool(
                self._declare_param_if_missing("only_position_gating", False)
            )

            return DeepSortBackend(
                max_age=max_age,
                n_init=n_init,
                match_thresh=match_thresh,
                max_iou_distance=max_iou_distance,
                centre_gate=centre_gate,
                appearance_enabled=appearance_enabled,
                appearance_max_frame_age_ms=appearance_max_frame_age_ms,
                appearance_hist_bins=appearance_hist_bins,
                appearance_weight=appearance_weight,
                appearance_max_distance=appearance_max_distance,
                appearance_min_crop_size=appearance_min_crop_size,
                appearance_update_alpha=appearance_update_alpha,
                nn_budget=nn_budget,
                only_position_gating=only_position_gating,
            )

        else:
            self.get_logger().error(f"Unknown tracker_type: {tracker_type}, defaulting to SORT")
            return SortBackend()

    def on_image(self, msg: Image) -> None:
        """Forward the latest camera image only to the DeepSORT backend."""
        if isinstance(self.backend, DeepSortBackend):
            self.backend.update_latest_image(msg)

    def on_timing(self, msg: Timing) -> None:
        frame_id = int(msg.frame_id)
        if frame_id <= 0:
            return

        if frame_id not in self.frame_context:
            self._frame_context_order.append(frame_id)
            if len(self._frame_context_order) > self.max_context:
                oldest = self._frame_context_order.popleft()
                self.frame_context.pop(oldest, None)

        self.frame_context[frame_id] = (int(msg.src_stamp_ns), int(msg.t_cam_msg_seen_ns))
    
    def on_detections(self, msg: Detection2DArray) -> None:
        """Process detection message and publish tracks."""
        self._frame_counter += 1
        t_track_cb_start_ns = now_ns()
        frame_id = _parse_frame_id(msg.header.frame_id)
        should_log_profile = (
            self.profiling_enabled
            and self.profiling_log_every_n > 0
            and (self._frame_counter % self.profiling_log_every_n == 0)
        )
        should_sample_serialize = (
            self.profiling_serialize_sample_every_n > 0
            and (self._frame_counter % self.profiling_serialize_sample_every_n == 0)
        )
        profiler = SectionProfiler() if self.profiling_enabled else None

        gc_before = self._gc_collections_seen if (self.profiling_gc_probe and should_log_profile) else 0
        gc_count_before = gc.get_count() if (self.profiling_gc_probe and should_log_profile) else (0, 0, 0)

        det_boxes: List[BBox] = []
        det_scores: List[float] = []
        det_boxes_append = det_boxes.append
        det_scores_append = det_scores.append
        min_score = self.min_score
        
        # Parse detections from vision_msgs format
        for det in msg.detections:
            if not det.results:
                continue

            score = -1.0
            for result in det.results:
                result_score = float(result.hypothesis.score)
                if result_score > score:
                    score = result_score
            
            # Apply min_score filter
            if score < min_score:
                continue
            
            # Convert to xyxy format
            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            w = float(det.bbox.size_x)
            h = float(det.bbox.size_y)
            box = xywh_center_to_xyxy(cx, cy, w, h)
            
            det_boxes_append(box)
            det_scores_append(score)
        
        # Get frame timestamp
        frame_time_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)

        # track_ms is defined as tracker backend compute only.
        if profiler is not None:
            with profiler.section("tracker_update"):
                tracks = self.backend.update(det_boxes, det_scores, frame_time_ns)
            tracker_update_ms = profiler.ms("tracker_update")
        else:
            t_tracker_update_start_ns = now_ns()
            tracks = self.backend.update(det_boxes, det_scores, frame_time_ns)
            tracker_update_ms = float(now_ns() - t_tracker_update_start_ns) / 1e6

        should_publish_tracks = self.publish_tracks and self._has_track_subscribers()
        should_build_track_msg = should_publish_tracks or should_sample_serialize
        
        # Convert tracks to ROS message
        src_stamp_ns, t_cam_msg_seen_ns = self.frame_context.pop(frame_id, (0, 0))
        queue_delay_ms = 0.0
        if t_cam_msg_seen_ns > 0:
            queue_delay_ms = float(t_track_cb_start_ns - int(t_cam_msg_seen_ns)) / 1e6

        out: Track2DArray | None = None
        tracks_ros: List[Track2D] = []
        if should_build_track_msg:
            if profiler is not None:
                with profiler.section("build_msg"):
                    out = Track2DArray()
                    out.header = msg.header
                    out.frame_id = int(frame_id)
                    out.src_stamp_ns = int(src_stamp_ns)
                    out.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
                    out.t_track_cb_start_ns = int(t_track_cb_start_ns)

                    with profiler.section("per_track_loop"):
                        tracks_ros_append = tracks_ros.append
                        for track in tracks:
                            x1, y1, x2, y2 = track.bbox_xyxy
                            w = x2 - x1
                            h = y2 - y1
                            cx = x1 + 0.5 * w
                            cy = y1 + 0.5 * h

                            # Fast path for performance isolation:
                            # skip per-track best-IoU score recovery in Python.
                            score = float(track.score)
                            best_score = score if score > 0.0 else 1.0

                            m = Track2D()
                            m.id = int(track.track_id)
                            m.cx = float(cx)
                            m.cy = float(cy)
                            m.w = float(w)
                            m.h = float(h)
                            m.score = float(best_score)
                            m.label = "person"
                            tracks_ros_append(m)

                    out.tracks = tracks_ros
            else:
                out = Track2DArray()
                out.header = msg.header
                out.frame_id = int(frame_id)
                out.src_stamp_ns = int(src_stamp_ns)
                out.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
                out.t_track_cb_start_ns = int(t_track_cb_start_ns)

                tracks_ros_append = tracks_ros.append
                for track in tracks:
                    x1, y1, x2, y2 = track.bbox_xyxy
                    w = x2 - x1
                    h = y2 - y1
                    cx = x1 + 0.5 * w
                    cy = y1 + 0.5 * h

                    score = float(track.score)
                    best_score = score if score > 0.0 else 1.0

                    m = Track2D()
                    m.id = int(track.track_id)
                    m.cx = float(cx)
                    m.cy = float(cy)
                    m.w = float(w)
                    m.h = float(h)
                    m.score = float(best_score)
                    m.label = "person"
                    tracks_ros_append(m)

                out.tracks = tracks_ros

        serialize_ms = -1.0
        serialized_size_bytes = -1
        if should_sample_serialize and out is not None:
            if profiler is not None:
                with profiler.section("serialize_tracks"):
                    wire = serialize_message(out)
                serialize_ms = profiler.ms("serialize_tracks")
            else:
                t_serialize_start_ns = now_ns()
                wire = serialize_message(out)
                serialize_ms = float(now_ns() - t_serialize_start_ns) / 1e6
            serialized_size_bytes = len(wire)

        t_track_cb_end_ns_pre_publish = now_ns()
        if profiler is not None:
            with profiler.section("publish_tracks"):
                if should_publish_tracks and out is not None:
                    out.t_track_cb_end_ns = int(t_track_cb_end_ns_pre_publish)
                    self.pub.publish(out)
        else:
            if should_publish_tracks and out is not None:
                out.t_track_cb_end_ns = int(t_track_cb_end_ns_pre_publish)
                self.pub.publish(out)
        t_track_cb_end_ns = now_ns()

        tmsg = Timing()
        tmsg.frame_id = int(frame_id)
        tmsg.src_stamp_ns = int(src_stamp_ns)
        tmsg.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        tmsg.t_track_cb_start_ns = int(t_track_cb_start_ns)
        tmsg.t_track_cb_end_ns = int(t_track_cb_end_ns)
        tmsg.track_ms = float(tracker_update_ms)

        # Structured detailed breakdown reuses explicit stage fields so downstream
        # tooling can consume one timing stream without extra message types.
        if self.profiling_publish_details:
            tmsg.ros_wait_ms = float(queue_delay_ms)
            # Keep detailed non-canonical profiling local to logs only.

        if self.publish_timing_topic:
            self.pub_timing.publish(tmsg)

        gc_after = self._gc_collections_seen if (self.profiling_gc_probe and should_log_profile) else 0
        gc_count_after = gc.get_count() if (self.profiling_gc_probe and should_log_profile) else (0, 0, 0)

        if should_log_profile:
            payload_est_bytes = _estimate_track_msg_payload_bytes(tracks_ros) if tracks_ros else -1
            self.get_logger().info(
                "tracker_profile "
                f"frame={frame_id} "
                f"det_count={len(det_boxes)} "
                f"track_count={len(tracks)} "
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
