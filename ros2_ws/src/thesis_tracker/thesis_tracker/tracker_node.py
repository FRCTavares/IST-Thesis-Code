#!/usr/bin/env python3
"""Unified tracker node supporting multiple tracking backends."""
from __future__ import annotations

import time
from typing import List, Tuple, Union

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

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
        self.pub = self.create_publisher(Track2DArray, "/tracks", qos)
        self.pub_timing = self.create_publisher(Timing, "/timing_tracker", qos)
        
        # Declare min_score parameter (common filtering)
        self.declare_parameter("min_score", 0.35)
        self.min_score = float(self.get_parameter("min_score").value)
        
        self.get_logger().info(
            f"Tracker node ready: type={tracker_type}, min_score={self.min_score}"
        )
    
    def _create_backend(self, tracker_type: str) -> TrackerBackendType:
        """Create tracker backend based on type."""
        if tracker_type == "sort":
            self.declare_parameter("iou_threshold", 0.18)
            self.declare_parameter("max_age", 4)
            self.declare_parameter("min_hits", 3)
            self.declare_parameter("centre_gate", 200.0)
            
            return SortBackend(
                iou_threshold=float(self.get_parameter("iou_threshold").value),
                max_age=int(self.get_parameter("max_age").value),
                min_hits=int(self.get_parameter("min_hits").value),
                centre_gate=float(self.get_parameter("centre_gate").value)
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
    
    def on_detections(self, msg: Detection2DArray) -> None:
        """Process detection message and publish tracks."""
        det_boxes: List[BBox] = []
        det_scores: List[float] = []
        det_labels: List[str] = []
        
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
            det_labels.append("person")  # Person-only for now
        
        # Get frame timestamp
        frame_time_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)
        
        # Update tracker and measure timing
        t0 = time.perf_counter_ns()
        tracks = self.backend.update(det_boxes, det_scores, frame_time_ns)
        t1 = time.perf_counter_ns()
        track_ms = (t1 - t0) / 1e6
        
        # Convert tracks to ROS message
        out = Track2DArray()
        out.header = msg.header
        tracks_ros: List[Track2D] = []
        
        for track in tracks:
            cx, cy, w, h = xyxy_to_cxcywh(track.bbox_xyxy)
            
            m = Track2D()
            m.id = int(track.track_id)
            m.cx = float(cx)
            m.cy = float(cy)
            m.w = float(w)
            m.h = float(h)
            m.score = float(track.score)
            m.label = "person"
            tracks_ros.append(m)
        
        out.tracks = tracks_ros
        self.pub.publish(out)
        
        # Publish timing
        tmsg = Timing()
        tmsg.frame_id = _parse_frame_id(msg.header.frame_id)
        tmsg.track_ms = float(track_ms)
        self.pub_timing.publish(tmsg)


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
