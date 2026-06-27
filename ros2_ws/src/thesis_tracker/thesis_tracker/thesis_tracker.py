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
    # Legacy detector messages used "frame_<int>"
    try:
        if frame_id_str.startswith("frame_"):
            return int(frame_id_str.split("_", 1)[1])
    except Exception:
        pass
    return 0


def now_ns() -> int:
    return time.monotonic_ns()


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
        self.sub_timing = self.create_subscription(Timing, "/timing", self.on_timing, qos)
        self.pub = self.create_publisher(Track2DArray, "/tracks", qos)

        # New: publish tracker runtime timing
        self.pub_timing = self.create_publisher(Timing, "/timing_tracker", qos)

        self.frame_context: dict[int, tuple[int, int]] = {}
        self.max_context = 512

        self.get_logger().info(
            f"SORT wrapper ready: iou={self.iou_threshold}, max_age={self.max_age}, "
            f"min_hits={self.min_hits}, min_score={self.min_score}"
        )

    def on_timing(self, msg: Timing) -> None:
        frame_id = int(msg.frame_id)
        if frame_id <= 0:
            return

        self.frame_context[frame_id] = (int(msg.src_stamp_ns), int(msg.t_cam_msg_seen_ns))
        if len(self.frame_context) > self.max_context:
            oldest = next(iter(self.frame_context))
            self.frame_context.pop(oldest, None)

    def on_detections(self, msg: Detection2DArray) -> None:
        t_track_cb_start_ns = now_ns()
        frame_id = _parse_frame_id(msg.header.frame_id)

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

        # track_ms is defined as tracker backend compute only.
        t_track_update_start_ns = now_ns()
        sort_tracks = self.tracker.update(det_boxes, frame_id=None)
        t_track_update_end_ns = now_ns()

        out = Track2DArray()
        out.header = msg.header
        out.frame_id = int(frame_id)
        src_stamp_ns, t_cam_msg_seen_ns = self.frame_context.get(frame_id, (0, 0))
        out.src_stamp_ns = int(src_stamp_ns)
        out.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        out.t_track_cb_start_ns = int(t_track_cb_start_ns)
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
        t_track_cb_end_ns = now_ns()
        out.t_track_cb_end_ns = int(t_track_cb_end_ns)
        self.pub.publish(out)

        tmsg = Timing()
        tmsg.frame_id = int(frame_id)
        tmsg.src_stamp_ns = int(src_stamp_ns)
        tmsg.t_cam_msg_seen_ns = int(t_cam_msg_seen_ns)
        tmsg.t_track_cb_start_ns = int(t_track_cb_start_ns)
        tmsg.t_track_cb_end_ns = int(t_track_cb_end_ns)
        tmsg.track_ms = float((t_track_update_end_ns - t_track_update_start_ns) / 1e6)
        self.pub_timing.publish(tmsg)

def main(args=None) -> None:
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init(args=args)
    node = ThesisTrackerNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        # stop executor first, then destroy node
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