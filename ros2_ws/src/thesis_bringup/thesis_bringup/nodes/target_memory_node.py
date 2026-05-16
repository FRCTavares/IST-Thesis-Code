from __future__ import annotations

import json
import time
from typing import Optional

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from sensor_msgs.msg import Image
from std_msgs.msg import Empty, String, UInt32

from thesis_msgs.msg import TargetState, Track2DArray

from thesis_bringup.appearance_memory import (
    AppearanceConfig,
    extract_hsv_upper_lower_feature,
)
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

        # TIM-V1B appearance extraction.
        # Disabled by default to preserve TIM-V0 live behaviour.
        self.declare_parameter("appearance_enabled", False)
        self.declare_parameter("appearance_image_topic", "/camera/dashboard")
        self.declare_parameter("appearance_h_bins", 16)
        self.declare_parameter("appearance_s_bins", 8)
        self.declare_parameter("appearance_min_bbox_height", 30.0)
        self.declare_parameter("appearance_max_image_age_ms", 250.0)
        self.declare_parameter("appearance_weight", 0.12)
        self.declare_parameter("appearance_min_similarity", 0.35)
        self.declare_parameter("appearance_update_alpha", 0.10)
        self.declare_parameter("appearance_ambiguous_only", True)

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

        self._appearance_enabled = bool(self.get_parameter("appearance_enabled").value)
        self._appearance_image_topic = str(self.get_parameter("appearance_image_topic").value)
        self._appearance_max_image_age_ms = float(self.get_parameter("appearance_max_image_age_ms").value)
        self._appearance_cfg = AppearanceConfig(
            h_bins=int(self.get_parameter("appearance_h_bins").value),
            s_bins=int(self.get_parameter("appearance_s_bins").value),
            min_bbox_height=float(self.get_parameter("appearance_min_bbox_height").value),
        )
        self._latest_image_bgr = None
        self._latest_image_seen_ns: Optional[int] = None
        self._cv_bridge = None
        self._image_sub = None
        self._image_error_warned = False

        self._last_appearance_candidates = 0
        self._last_appearance_features_valid = 0
        self._last_appearance_image_age_ms: Optional[float] = None
        self._last_appearance_skip_reason = "disabled"

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
            appearance_enabled=self._appearance_enabled,
            appearance_weight=float(self.get_parameter("appearance_weight").value),
            appearance_min_similarity=float(self.get_parameter("appearance_min_similarity").value),
            appearance_update_alpha=float(self.get_parameter("appearance_update_alpha").value),
            appearance_ambiguous_only=bool(self.get_parameter("appearance_ambiguous_only").value),
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

        if self._appearance_enabled:
            from cv_bridge import CvBridge

            self._cv_bridge = CvBridge()
            self._image_sub = self.create_subscription(
                Image,
                self._appearance_image_topic,
                self._on_image,
                qos,
            )

        self.get_logger().info(
            "TIM node ready: "
            f"tracks={self._tracks_topic}, target={self._target_topic}, "
            f"select={self._select_topic}, clear={self._clear_topic}, "
            f"normalised_tracks={self._tracks_are_normalized}, "
            f"mirror_raw_target_selection={self._mirror_raw_target_selection}, "
            f"appearance_enabled={self._appearance_enabled}, "
            f"appearance_image_topic={self._appearance_image_topic}"
        )

        if self._pending_select_id is not None:
            self.get_logger().info(
                f"Waiting to initialise TIM from track id {self._pending_select_id}"
            )

    def _on_image(self, msg: Image) -> None:
        if not self._appearance_enabled or self._cv_bridge is None:
            return

        try:
            self._latest_image_bgr = self._cv_bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8",
            )
            self._latest_image_seen_ns = time.monotonic_ns()
        except Exception as exc:
            if not self._image_error_warned:
                self.get_logger().warn(f"TIM appearance image conversion failed: {exc}")
                self._image_error_warned = True

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
        candidates = self._attach_appearance_features(candidates)

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

    def _attach_appearance_features(self, candidates: list[CandidateTrack]) -> list[CandidateTrack]:
        self._last_appearance_candidates = len(candidates)
        self._last_appearance_features_valid = 0
        self._last_appearance_image_age_ms = None

        if not self._appearance_enabled:
            self._last_appearance_skip_reason = "disabled"
            return candidates

        if self._latest_image_bgr is None or self._latest_image_seen_ns is None:
            self._last_appearance_skip_reason = "no_image"
            return candidates

        age_ms = float(time.monotonic_ns() - self._latest_image_seen_ns) / 1e6
        self._last_appearance_image_age_ms = age_ms

        if age_ms > self._appearance_max_image_age_ms:
            self._last_appearance_skip_reason = "stale_image"
            return candidates

        enriched: list[CandidateTrack] = []
        valid_features = 0

        for candidate in candidates:
            appearance = extract_hsv_upper_lower_feature(
                self._latest_image_bgr,
                candidate.bbox,
                self._appearance_cfg,
            )
            if appearance is not None:
                valid_features += 1

            enriched.append(
                CandidateTrack(
                    track_id=candidate.track_id,
                    bbox=candidate.bbox,
                    score=candidate.score,
                    age=candidate.age,
                    last_seen=candidate.last_seen,
                    appearance=appearance,
                )
            )

        self._last_appearance_features_valid = valid_features
        self._last_appearance_skip_reason = "ok"

        return enriched

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

        # Conservative TargetState contract:
        # /target_memory is safe for controller-style consumers.
        # If TIM does not currently consider the target visible/control-valid,
        # publish an empty TargetState. Detailed memory state remains available
        # on /target_memory/status.
        if (
            out.bbox is None
            or out.target_track_id is None
            or (self._zero_id_when_not_visible and not out.visible)
        ):
            target_msg.id = 0
            target_msg.cx = 0.0
            target_msg.cy = 0.0
            target_msg.w = 0.0
            target_msg.h = 0.0
            target_msg.score = 0.0
            target_msg.quality = 0.0
            return target_msg

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
                "appearance_enabled": bool(self._appearance_enabled),
                "appearance_candidates": int(self._last_appearance_candidates),
                "appearance_features_valid": int(self._last_appearance_features_valid),
                "appearance_image_age_ms": self._last_appearance_image_age_ms,
                "appearance_skip_reason": str(self._last_appearance_skip_reason),
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
                    "appearance": float(best.appearance),
                    "appearance_used": bool(best.appearance_used),
                    "appearance_raw": float(best.appearance_raw),
                    "appearance_gate_passed": bool(best.appearance_gate_passed),
                    "geometry_allows_appearance": bool(best.geometry_allows_appearance),
                    "ambiguous": bool(best.ambiguous),
                },
                "all_scores": [
                    {
                        "track_id": int(score.track_id),
                        "total": float(score.total),
                        "iou": float(score.iou),
                        "distance": float(score.distance),
                        "scale": float(score.scale),
                        "confidence": float(score.confidence),
                        "id_bonus": float(score.id_bonus),
                        "appearance": float(score.appearance),
                        "appearance_used": bool(score.appearance_used),
                        "appearance_raw": float(score.appearance_raw),
                        "appearance_gate_passed": bool(score.appearance_gate_passed),
                        "geometry_allows_appearance": bool(score.geometry_allows_appearance),
                        "ambiguous": bool(score.ambiguous),
                    }
                    for score in out.all_scores
                ],
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
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
