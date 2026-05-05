from __future__ import annotations

import json
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from std_msgs.msg import Empty, String, UInt32

from thesis_msgs.msg import TargetState, Track2DArray

from thesis_bringup.target_memory import (
    BBox,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetMemoryOutput,
    TargetState as TimState,
)


class TargetMemoryNode(Node):
    """ROS wrapper for TIM-V0 selected-target memory.

    Input:
      /tracks

    Commands:
      /target_memory/select std_msgs/UInt32
      /target_memory/clear  std_msgs/Empty

    Outputs:
      /target_memory        thesis_msgs/TargetState
      /target_memory/status std_msgs/String JSON diagnostics

    This node does not replace /target yet. It is for live comparison first.
    """

    def __init__(self) -> None:
        super().__init__("target_memory_node")

        self.declare_parameter("tracks_topic", "/tracks")
        self.declare_parameter("target_topic", "/target_memory")
        self.declare_parameter("status_topic", "/target_memory/status")
        self.declare_parameter("select_topic", "/target_memory/select")
        self.declare_parameter("clear_topic", "/target_memory/clear")
        self.declare_parameter("mirror_target_topic", "/target")
        self.declare_parameter("mirror_raw_target_selection", True)

        self.declare_parameter("image_width", 640.0)
        self.declare_parameter("image_height", 640.0)
        self.declare_parameter("tracks_are_normalized", False)

        # Optional startup selection. 0 means wait for operator command.
        self.declare_parameter("selected_track_id", 0)

        # For bench/debug only. Keep false for thesis semantics.
        self.declare_parameter("auto_select_largest", False)

        # When true, id is forced to 0 unless TIM says target is currently visible.
        # Keep false while comparing /target_memory against /target.
        self.declare_parameter("zero_id_when_not_visible", True)

        # TIM gates.
        self.declare_parameter("accept_score_locked", 0.52)
        self.declare_parameter("accept_score_lost", 0.60)
        self.declare_parameter("ambiguity_margin", 0.07)
        self.declare_parameter("max_uncertain_frames", 6)
        self.declare_parameter("max_lost_frames", 30)
        self.declare_parameter("min_candidate_score", 0.10)

        self._tracks_topic = str(self.get_parameter("tracks_topic").value)
        self._target_topic = str(self.get_parameter("target_topic").value)
        self._status_topic = str(self.get_parameter("status_topic").value)
        self._select_topic = str(self.get_parameter("select_topic").value)
        self._clear_topic = str(self.get_parameter("clear_topic").value)
        self._mirror_target_topic = str(self.get_parameter("mirror_target_topic").value)
        self._mirror_raw_target_selection = bool(self.get_parameter("mirror_raw_target_selection").value)

        self._image_width = float(self.get_parameter("image_width").value)
        self._image_height = float(self.get_parameter("image_height").value)
        self._tracks_are_normalized = bool(self.get_parameter("tracks_are_normalized").value)
        self._auto_select_largest = bool(self.get_parameter("auto_select_largest").value)
        self._zero_id_when_not_visible = bool(self.get_parameter("zero_id_when_not_visible").value)

        initial_id = int(self.get_parameter("selected_track_id").value)
        self._pending_select_id: Optional[int] = initial_id if initial_id > 0 else None
        self._last_mirrored_target_id: Optional[int] = None

        cfg = TargetMemoryConfig(
            image_width=self._image_width,
            image_height=self._image_height,
            accept_score_locked=float(self.get_parameter("accept_score_locked").value),
            accept_score_lost=float(self.get_parameter("accept_score_lost").value),
            ambiguity_margin=float(self.get_parameter("ambiguity_margin").value),
            max_uncertain_frames=int(self.get_parameter("max_uncertain_frames").value),
            max_lost_frames=int(self.get_parameter("max_lost_frames").value),
            min_candidate_score=float(self.get_parameter("min_candidate_score").value),
        )
        self._tim = TargetIdentityMemory(cfg)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self._target_pub = self.create_publisher(TargetState, self._target_topic, qos)
        self._status_pub = self.create_publisher(String, self._status_topic, qos)

        self._tracks_sub = self.create_subscription(
            Track2DArray,
            self._tracks_topic,
            self._on_tracks,
            qos,
        )
        self._select_sub = self.create_subscription(
            UInt32,
            self._select_topic,
            self._on_select,
            qos,
        )
        self._clear_sub = self.create_subscription(
            Empty,
            self._clear_topic,
            self._on_clear,
            qos,
        )

        self._raw_target_sub = None
        if self._mirror_raw_target_selection:
            self._raw_target_sub = self.create_subscription(
                TargetState,
                self._mirror_target_topic,
                self._on_raw_target,
                qos,
            )

        self.get_logger().info(
            "TIM-V0 node ready: "
            f"tracks={self._tracks_topic}, target={self._target_topic}, "
            f"select={self._select_topic}, clear={self._clear_topic}, "
            f"normalised_tracks={self._tracks_are_normalized}, "
            f"mirror_raw_target_selection={self._mirror_raw_target_selection}"
        )

        if self._pending_select_id is not None:
            self.get_logger().info(
                f"Waiting to initialise TIM from track id {self._pending_select_id}"
            )

    def _on_raw_target(self, msg: TargetState) -> None:
        """Mirror positive dashboard /target selections into TIM.

        Important: /target id=0 is ambiguous because it can mean either
        operator clear or selected raw track temporarily invisible.
        Therefore this callback only mirrors positive ids. Use
        /target_memory/clear for explicit TIM clear.
        """
        target_id = int(msg.id)
        if target_id <= 0:
            return

        if self._last_mirrored_target_id == target_id and self._pending_select_id is None:
            return

        self._last_mirrored_target_id = target_id
        self._pending_select_id = target_id
        self.get_logger().info(
            f"TIM mirrored raw /target selection: track id {target_id}"
        )

    def _on_select(self, msg: UInt32) -> None:
        requested_id = int(msg.data)
        if requested_id <= 0:
            out = self._tim.clear()
            self.get_logger().info("TIM cleared by select id <= 0")
            self._publish_status_only(out)
            self._pending_select_id = None
            return

        self._pending_select_id = requested_id
        self.get_logger().info(f"TIM pending operator selection: track id {requested_id}")

    def _on_clear(self, _: Empty) -> None:
        out = self._tim.clear()
        self._pending_select_id = None
        self.get_logger().info("TIM cleared")
        self._publish_status_only(out)

    def _on_tracks(self, msg: Track2DArray) -> None:
        t_start_ns = time.monotonic_ns()

        candidates = [self._candidate_from_track(t) for t in msg.tracks]

        selected_candidate = None
        if self._pending_select_id is not None:
            selected_candidate = self._find_candidate(candidates, self._pending_select_id)

        if selected_candidate is not None:
            out = self._tim.select(selected_candidate)
            self.get_logger().info(
                f"TIM selected track {selected_candidate.track_id} on frame {int(msg.frame_id)}"
            )
            self._pending_select_id = None
        elif self._pending_select_id is not None and self._tim.state == TimState.NO_TARGET:
            out = self._tim.update([])
            out.reason = f"pending_selection_track_not_visible:{self._pending_select_id}"
        elif self._tim.state == TimState.NO_TARGET and self._auto_select_largest and candidates:
            largest = max(candidates, key=lambda c: self._bbox_area(c.bbox))
            out = self._tim.select(largest)
            self.get_logger().warn(
                f"TIM auto-selected largest track {largest.track_id}. "
                "Use only for debugging, not thesis runs."
            )
        else:
            out = self._tim.update(candidates)

        t_end_ns = time.monotonic_ns()

        target_msg = self._target_msg_from_output(msg, out, t_start_ns, t_end_ns)
        self._target_pub.publish(target_msg)
        self._publish_status(out, msg, t_start_ns, t_end_ns)

    def _candidate_from_track(self, track) -> CandidateTrack:
        cx = float(track.cx)
        cy = float(track.cy)
        w = float(track.w)
        h = float(track.h)

        if self._tracks_are_normalized:
            cx *= self._image_width
            w *= self._image_width
            cy *= self._image_height
            h *= self._image_height

        x1 = cx - 0.5 * w
        y1 = cy - 0.5 * h
        x2 = cx + 0.5 * w
        y2 = cy + 0.5 * h

        bbox = self._clip_bbox((x1, y1, x2, y2))

        return CandidateTrack(
            track_id=int(track.id),
            bbox=bbox,
            score=float(track.score),
        )

    def _target_msg_from_output(
        self,
        tracks_msg: Track2DArray,
        out: TargetMemoryOutput,
        t_start_ns: int,
        t_end_ns: int,
    ) -> TargetState:
        target_msg = TargetState()
        target_msg.header = tracks_msg.header
        target_msg.frame_id = int(tracks_msg.frame_id)
        target_msg.src_stamp_ns = int(tracks_msg.src_stamp_ns)
        target_msg.t_cam_msg_seen_ns = int(tracks_msg.t_cam_msg_seen_ns)
        target_msg.t_target_cb_start_ns = int(t_start_ns)
        target_msg.t_target_cb_end_ns = int(t_end_ns)

        if out.bbox is None or out.target_track_id is None:
            target_msg.id = 0
            target_msg.cx = 0.0
            target_msg.cy = 0.0
            target_msg.w = 0.0
            target_msg.h = 0.0
            target_msg.score = 0.0
            target_msg.quality = 0.0
            return target_msg

        if self._zero_id_when_not_visible and not out.visible:
            target_msg.id = 0
        else:
            target_msg.id = int(out.target_track_id)

        cx, cy, w, h = self._bbox_to_msg_geometry(out.bbox)
        target_msg.cx = float(cx)
        target_msg.cy = float(cy)
        target_msg.w = float(w)
        target_msg.h = float(h)

        # Existing TargetState has no explicit state/control field.
        # Use score for current visibility and quality for TIM confidence.
        target_msg.score = float(out.best_score.confidence) if out.visible and out.best_score else 0.0
        target_msg.quality = float(out.quality)
        return target_msg

    def _publish_status_only(self, out: TargetMemoryOutput) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": str(out.state.value),
                "control_mode": str(out.control_mode.value),
                "target_track_id": out.target_track_id,
                "visible": bool(out.visible),
                "reacquired": bool(out.reacquired),
                "quality": float(out.quality),
                "frames_since_seen": int(out.frames_since_seen),
                "reason": str(out.reason),
            },
            sort_keys=True,
        )
        self._status_pub.publish(msg)

    def _publish_status(
        self,
        out: TargetMemoryOutput,
        tracks_msg: Track2DArray,
        t_start_ns: int,
        t_end_ns: int,
    ) -> None:
        best = out.best_score
        msg = String()
        msg.data = json.dumps(
            {
                "frame_id": int(tracks_msg.frame_id),
                "state": str(out.state.value),
                "control_mode": str(out.control_mode.value),
                "target_track_id": out.target_track_id,
                "visible": bool(out.visible),
                "reacquired": bool(out.reacquired),
                "quality": float(out.quality),
                "frames_since_seen": int(out.frames_since_seen),
                "reason": str(out.reason),
                "lat_ms": float(t_end_ns - t_start_ns) / 1e6,
                "num_tracks": len(tracks_msg.tracks),
                "best": None
                if best is None
                else {
                    "track_id": int(best.track_id),
                    "total": float(best.total),
                    "iou": float(best.iou),
                    "distance": float(best.distance),
                    "scale": float(best.scale),
                    "confidence": float(best.confidence),
                    "id_bonus": float(best.id_bonus),
                    "ambiguous": bool(best.ambiguous),
                },
            },
            sort_keys=True,
        )
        self._status_pub.publish(msg)

    def _bbox_to_msg_geometry(self, bbox: BBox) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = bbox
        cx = 0.5 * (x1 + x2)
        cy = 0.5 * (y1 + y2)
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)

        if self._tracks_are_normalized:
            return (
                cx / self._image_width,
                cy / self._image_height,
                w / self._image_width,
                h / self._image_height,
            )

        return cx, cy, w, h

    def _clip_bbox(self, bbox: BBox) -> BBox:
        x1, y1, x2, y2 = bbox
        x1 = max(0.0, min(self._image_width, x1))
        y1 = max(0.0, min(self._image_height, y1))
        x2 = max(0.0, min(self._image_width, x2))
        y2 = max(0.0, min(self._image_height, y2))
        return (x1, y1, x2, y2)

    @staticmethod
    def _bbox_area(bbox: BBox) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @staticmethod
    def _find_candidate(candidates: list[CandidateTrack], track_id: int) -> Optional[CandidateTrack]:
        for candidate in candidates:
            if int(candidate.track_id) == int(track_id):
                return candidate
        return None


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TargetMemoryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
