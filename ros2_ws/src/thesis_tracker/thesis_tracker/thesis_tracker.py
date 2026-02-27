#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import Track2D, Track2DArray, Timing

from .sort_tracker import Sort, iou as sort_iou  # uses your exact iou()

BBox = Tuple[float, float, float, float]  # x1,y1,x2,y2


def xywh_center_to_xyxy(cx: float, cy: float, w: float, h: float) -> BBox:
    x1 = cx - 0.5 * w
    y1 = cy - 0.5 * h
    x2 = cx + 0.5 * w
    y2 = cy + 0.5 * h
    return x1, y1, x2, y2


def xyxy_to_cxcywh(b: BBox) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = b
    w = x2 - x1
    h = y2 - y1
    cx = x1 + 0.5 * w
    cy = y1 + 0.5 * h
    return cx, cy, w, h


def _parse_frame_id(frame_id_str: str) -> int:
    # inference_client_node uses "frame_<int>"
    try:
        if frame_id_str.startswith("frame_"):
            return int(frame_id_str.split("_", 1)[1])
    except Exception:
        pass
    return 0


class ThesisTrackerNode(Node):
    def __init__(self) -> None:
        super().__init__("thesis_tracker_node")

        # Frozen params, declared for visibility only
        self.declare_parameter("iou_threshold", 0.18)
        self.declare_parameter("max_age", 4)
        self.declare_parameter("min_hits", 3)
        self.declare_parameter("min_score", 0.35)

        self.iou_threshold = float(self.get_parameter("iou_threshold").value) # type: ignore
        self.max_age = int(self.get_parameter("max_age").value) # type: ignore
        self.min_hits = int(self.get_parameter("min_hits").value) # type: ignore
        self.min_score = float(self.get_parameter("min_score").value) # type: ignore

        # IMPORTANT: your Sort class uses iou_thresh, not iou_threshold
        self.tracker = Sort(iou_thresh=self.iou_threshold, max_age=self.max_age, min_hits=self.min_hits)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub = self.create_subscription(Detection2DArray, "/detections", self.on_detections, qos)
        self.pub = self.create_publisher(Track2DArray, "/tracks", qos)

        # New: publish tracker runtime timing
        self.pub_timing = self.create_publisher(Timing, "/timing_tracker", qos)

        self.get_logger().info(
            f"SORT wrapper ready: iou={self.iou_threshold}, max_age={self.max_age}, "
            f"min_hits={self.min_hits}, min_score={self.min_score}"
        )

    def on_detections(self, msg: Detection2DArray) -> None:
        det_boxes: List[BBox] = []
        det_scores: List[float] = []
        det_labels: List[str] = []

        # Build det list for SORT, keep scores/labels for annotation
        for det in msg.detections:
            if not det.results:
                continue
            best = max(det.results, key=lambda r: float(r.hypothesis.score))
            score = float(best.hypothesis.score)
            if score < self.min_score:
                continue

            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            w = float(det.bbox.size_x)
            h = float(det.bbox.size_y)

            box = xywh_center_to_xyxy(cx, cy, w, h)

            det_boxes.append(box)
            det_scores.append(score)
            det_labels.append("person")  # deterministic, person-only

        # Update SORT (your API) and time it
        t0 = time.perf_counter_ns()
        sort_tracks = self.tracker.update(det_boxes, frame_id=None)
        t1 = time.perf_counter_ns()
        track_ms = (t1 - t0) / 1e6

        out = Track2DArray()
        out.header = msg.header
        tracks_ros: List[Track2D] = []

        for tr in sort_tracks:
            # confirmed rule from your own header comment
            confirmed = (tr.hits >= self.tracker.min_hits) and (tr.time_since_update == 0)
            if not confirmed:
                continue

            tbox = tr.bbox()
            cx, cy, w, h = xyxy_to_cxcywh(tbox)

            # attach score via best IoU match this frame
            best_score = 0.0
            best_label = "person"
            if det_boxes:
                best_iou = 0.0
                best_i = -1
                for i, dbox in enumerate(det_boxes):
                    v = sort_iou(tbox, dbox)
                    if v > best_iou:
                        best_iou = v
                        best_i = i
                if best_i >= 0:
                    best_score = float(det_scores[best_i])
                    best_label = det_labels[best_i]

            m = Track2D()
            m.id = int(tr.track_id)
            m.cx = float(cx)
            m.cy = float(cy)
            m.w = float(w)
            m.h = float(h)
            m.score = float(best_score)
            m.label = str(best_label)
            tracks_ros.append(m)

        out.tracks = tracks_ros
        self.pub.publish(out)

        tmsg = Timing()
        tmsg.frame_id = _parse_frame_id(msg.header.frame_id)
        tmsg.track_ms = float(track_ms)
        self.pub_timing.publish(tmsg)


def main(args=None) -> None:
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init(args=args)
    node = None
    executor = SingleThreadedExecutor()

    try:
        node = ThesisTrackerNode()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if node is not None:
                executor.remove_node(node)
                node.destroy_node()
        except Exception:
            pass

        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass