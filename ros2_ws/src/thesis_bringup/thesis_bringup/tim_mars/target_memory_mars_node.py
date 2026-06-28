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

from thesis_bringup.tim_mars.mars_reid_backend import MarsReIdBackend
from thesis_bringup.tim_mars.ros_params import (
    build_target_memory_config,
    declare_tim_mars_parameters,
    read_tim_mars_ros_params,
)
from thesis_bringup.tim_mars.target_memory import (
    BBox,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryOutput,
    TargetState as TimState,
)


class TargetMemoryMarsNode(Node):
    """ROS wrapper for TIM-MARS selected-target memory.

    Input:
      /tracks

    Commands:
      /target_memory_mars/select std_msgs/UInt32
      /target_memory_mars/clear  std_msgs/Empty

    Outputs:
      /target_memory_mars        thesis_msgs/TargetState
      /target_memory_mars/status std_msgs/String JSON diagnostics

    This node does not replace /target yet. It is for live comparison first.
    """

    def __init__(self) -> None:
        super().__init__("target_memory_mars_node")

        declare_tim_mars_parameters(self)
        params = read_tim_mars_ros_params(self)

        self._tracks_topic = params.tracks_topic
        self._target_topic = params.target_topic
        self._status_topic = params.status_topic
        self._select_topic = params.select_topic
        self._clear_topic = params.clear_topic
        self._mirror_target_topic = params.mirror_target_topic
        self._mirror_raw_target_selection = params.mirror_raw_target_selection

        self._image_width = params.image_width
        self._image_height = params.image_height
        self._tracks_are_normalized = params.tracks_are_normalized
        self._auto_select_largest = params.auto_select_largest
        self._zero_id_when_not_visible = params.zero_id_when_not_visible

        self._appearance_enabled = params.appearance_enabled
        self._appearance_image_topic = params.appearance_image_topic
        self._appearance_max_image_age_ms = params.appearance_max_image_age_ms
        self._appearance_compute_min_interval_ms = params.appearance_compute_min_interval_ms
        self._appearance_cache_ttl_ms = params.appearance_cache_ttl_ms
        self._mars_model_path = params.mars_model_path
        self._mars_batch_size = params.mars_batch_size

        self._mars_backend = None
        self._latest_image_bgr = None
        self._latest_image_seen_ns: Optional[int] = None
        self._cv_bridge = None
        self._image_sub = None
        self._image_error_warned = False

        self._last_appearance_candidates = 0
        self._last_appearance_features_valid = 0
        self._last_appearance_image_age_ms: Optional[float] = None
        self._last_appearance_skip_reason = "disabled"

        self._latest_image_seq = 0
        self._last_mars_compute_ns = 0
        self._last_mars_image_seq = -1
        self._appearance_cache_by_track_id: dict[int, object] = {}
        self._appearance_cache_seen_ns: dict[int, int] = {}

        initial_id = params.selected_track_id
        self._pending_select_id: Optional[int] = initial_id if initial_id > 0 else None
        self._last_mirrored_target_id: Optional[int] = None

        cfg = build_target_memory_config(self, params)
        self._tim = TargetIdentityMemory(cfg)

        self.get_logger().info(
            "TIM-MARS config: "
            f"allow_id_switch_recovery={cfg.allow_id_switch_recovery} "
            f"id_switch_spatial_gate_enabled={cfg.id_switch_spatial_gate_enabled} "
            f"rank_aware_reacquisition_enabled={cfg.rank_aware_reacquisition_enabled} "
            f"rank_aware_lost_min_app={cfg.rank_aware_lost_min_app:.3f} "
            f"rank_aware_lost_app_margin={cfg.rank_aware_lost_app_margin:.3f} "
            f"active_reselection_enabled={cfg.active_reselection_enabled} "
            f"active_reselection_min_app={cfg.active_reselection_min_app:.3f} "
            f"active_reselection_app_margin={cfg.active_reselection_app_margin:.3f} "
            f"active_reselection_confirm_frames={cfg.active_reselection_confirm_frames} "
            f"absence_recovery_enabled={cfg.absence_recovery_enabled} "
            f"absence_after_missed_frames={cfg.absence_after_missed_frames} "
            f"absence_min_similarity={cfg.absence_min_similarity:.3f} "
            f"absence_appearance_margin={cfg.absence_appearance_margin:.3f} "
            f"absence_confirm_frames={cfg.absence_confirm_frames} "
            f"same_id_appearance_ambiguity_enabled={cfg.same_id_appearance_ambiguity_enabled} "
            f"same_id_appearance_ambiguity_margin={cfg.same_id_appearance_ambiguity_margin:.3f} "
            f"hard_negative_memory_enabled={cfg.hard_negative_memory_enabled} "
            f"hard_negative_max_entries={cfg.hard_negative_max_entries} "
            f"hard_negative_reject_similarity={cfg.hard_negative_reject_similarity:.3f} "
            f"hard_negative_reject_margin={cfg.hard_negative_reject_margin:.3f} "
            f"old_id_distrust_enabled={cfg.old_id_distrust_enabled} "
            f"old_id_distrust_min_challenger_app={cfg.old_id_distrust_min_challenger_app:.3f} "
            f"old_id_distrust_min_old_id_app_margin={cfg.old_id_distrust_min_old_id_app_margin:.3f}"
        )

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
            self._mars_backend = MarsReIdBackend(
                self._mars_model_path,
                batch_size=self._mars_batch_size,
            )
            self.get_logger().info(
                f"TIM-MARS loaded MARS ReID model: {self._mars_model_path}"
            )

        self.get_logger().info(
            "TIM-MARS node ready: "
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
            self._latest_image_seq += 1
        except Exception as exc:
            if not self._image_error_warned:
                self.get_logger().warn(f"TIM appearance image conversion failed: {exc}")
                self._image_error_warned = True

    def _on_raw_target(self, msg: TargetState) -> None:
        """Mirror positive dashboard /target selections into TIM.

        Important: /target id=0 is ambiguous because it can mean either
        operator clear or selected raw track temporarily invisible.
        Therefore this callback only mirrors positive ids. Use
        /target_memory_mars/clear for explicit TIM clear.
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

        if not candidates:
            self._last_appearance_skip_reason = "no_candidates"
            return candidates

        now_ns = time.monotonic_ns()

        if self._latest_image_bgr is None or self._latest_image_seen_ns is None:
            self._last_appearance_skip_reason = "no_image"
            return self._attach_cached_appearance_features(candidates, now_ns)

        age_ms = float(now_ns - self._latest_image_seen_ns) / 1e6
        self._last_appearance_image_age_ms = age_ms

        if age_ms > self._appearance_max_image_age_ms:
            self._last_appearance_skip_reason = "stale_image"
            return self._attach_cached_appearance_features(candidates, now_ns)

        if self._mars_backend is None:
            self._last_appearance_skip_reason = "no_mars_backend"
            return self._attach_cached_appearance_features(candidates, now_ns)

        elapsed_ms = float(now_ns - self._last_mars_compute_ns) / 1e6
        image_already_encoded = self._last_mars_image_seq == self._latest_image_seq
        interval_too_short = (
            self._last_mars_compute_ns > 0
            and elapsed_ms < self._appearance_compute_min_interval_ms
        )

        if image_already_encoded or interval_too_short:
            self._last_appearance_skip_reason = (
                "cached_same_image" if image_already_encoded else "cached_interval"
            )
            return self._attach_cached_appearance_features(candidates, now_ns)

        boxes = [candidate.bbox for candidate in candidates]
        try:
            appearances = self._mars_backend.encode(self._latest_image_bgr, boxes)
        except Exception as exc:
            self._last_appearance_skip_reason = f"mars_error:{type(exc).__name__}"
            self.get_logger().warn(f"TIM-MARS embedding extraction failed: {exc}")
            return self._attach_cached_appearance_features(candidates, now_ns)

        self._last_mars_compute_ns = now_ns
        self._last_mars_image_seq = self._latest_image_seq

        valid_features = 0
        for candidate, appearance in zip(candidates, appearances):
            if appearance is None:
                continue
            valid_features += 1
            track_id = int(candidate.track_id)
            self._appearance_cache_by_track_id[track_id] = appearance
            self._appearance_cache_seen_ns[track_id] = now_ns

        self._last_appearance_features_valid = valid_features
        self._last_appearance_skip_reason = "ok"

        return self._attach_cached_appearance_features(candidates, now_ns)

    def _attach_cached_appearance_features(
        self,
        candidates: list[CandidateTrack],
        now_ns: int,
    ) -> list[CandidateTrack]:
        enriched: list[CandidateTrack] = []
        valid_features = 0

        active_track_ids = {int(candidate.track_id) for candidate in candidates}

        for track_id in list(self._appearance_cache_by_track_id.keys()):
            if track_id not in active_track_ids:
                self._appearance_cache_by_track_id.pop(track_id, None)
                self._appearance_cache_seen_ns.pop(track_id, None)

        for candidate in candidates:
            track_id = int(candidate.track_id)
            appearance = self._appearance_cache_by_track_id.get(track_id)
            seen_ns = self._appearance_cache_seen_ns.get(track_id)

            if appearance is not None and seen_ns is not None:
                cache_age_ms = float(now_ns - seen_ns) / 1e6
                if cache_age_ms <= self._appearance_cache_ttl_ms:
                    valid_features += 1
                else:
                    appearance = None
                    self._appearance_cache_by_track_id.pop(track_id, None)
                    self._appearance_cache_seen_ns.pop(track_id, None)

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

        self._last_appearance_features_valid = max(
            int(self._last_appearance_features_valid),
            int(valid_features),
        )

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
        # /target_memory_mars is safe for controller-style consumers.
        # If TIM does not currently consider the target visible/control-valid,
        # publish an empty TargetState. Detailed memory state remains available
        # on /target_memory_mars/status.
        if (
            out.bbox is None
            or out.target_track_id is None
            or (self._zero_id_when_not_visible and not out.control_valid)
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
        target_msg.score = float(out.best_score.confidence) if out.control_valid and out.best_score else 0.0
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
                "memory_update_frozen": bool(out.memory_update_frozen),
                "memory_update_freeze_reason": str(out.memory_update_freeze_reason),
                "same_id_appearance_ambiguity": bool(out.same_id_appearance_ambiguity),
                "appearance_margin_best_vs_second": float(out.appearance_margin_best_vs_second),
                "geometry_strength": float(out.geometry_strength),
                "risk_hard_negative": bool(out.risk_hard_negative),
                "risk_absence": bool(out.risk_absence),
                "risk_scene_ambiguity": bool(out.risk_scene_ambiguity),
                "v4a_publish_allowed": bool(out.v4a_publish_allowed),
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
                "memory_update_frozen": bool(out.memory_update_frozen),
                "memory_update_freeze_reason": str(out.memory_update_freeze_reason),
                "same_id_appearance_ambiguity": bool(out.same_id_appearance_ambiguity),
                "appearance_margin_best_vs_second": float(out.appearance_margin_best_vs_second),
                "geometry_strength": float(out.geometry_strength),
                "risk_hard_negative": bool(out.risk_hard_negative),
                "risk_absence": bool(out.risk_absence),
                "risk_scene_ambiguity": bool(out.risk_scene_ambiguity),
                "v4a_publish_allowed": bool(out.v4a_publish_allowed),
                "lat_ms": float(t_end_ns - t_start_ns) / 1e6,
                "num_tracks": len(tracks_msg.tracks),
                "appearance_enabled": bool(self._appearance_enabled),
                "appearance_candidates": int(self._last_appearance_candidates),
                "appearance_features_valid": int(self._last_appearance_features_valid),
                "appearance_image_age_ms": self._last_appearance_image_age_ms,
                "appearance_skip_reason": str(self._last_appearance_skip_reason),
                "appearance_compute_min_interval_ms": float(self._appearance_compute_min_interval_ms),
                "appearance_cache_ttl_ms": float(self._appearance_cache_ttl_ms),
                "appearance_cache_size": int(len(self._appearance_cache_by_track_id)),
                "appearance_update_cooldown_remaining": int(getattr(self._tim, "_appearance_update_cooldown_frames_remaining", 0)),
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
                    "hard_negative_similarity": float(best.hard_negative_similarity),
                    "hard_negative_margin": float(best.hard_negative_margin),
                    "hard_negative_reject": bool(best.hard_negative_reject),
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
                        "hard_negative_similarity": float(score.hard_negative_similarity),
                        "hard_negative_margin": float(score.hard_negative_margin),
                        "hard_negative_reject": bool(score.hard_negative_reject),
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
    node = TargetMemoryMarsNode()
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
