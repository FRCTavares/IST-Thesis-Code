"""ROS 2 runtime node for TIM-MARS selected-target memory.

This node wires ROS topics, parameters, optional raw target-selection mirroring,
optional image-based MARS appearance attachment, and status publication around
the pure TargetIdentityMemory algorithm.

Core accept/reject/reacquisition policy should stay out of this file. This file
should remain focused on ROS subscriptions, publications, image handling,
parameter wiring, and message conversion.
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from sensor_msgs.msg import Image
from std_msgs.msg import Empty, String, UInt32

from thesis_msgs.msg import TargetState, Track2DArray

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
    AppearanceAttachmentInput,
    AppearanceAttachmentState,
    attach_appearance_features,
)
from thesis_bringup.tim_mars.mars_reid_backend import MarsReIdBackend
from thesis_bringup.tim_mars.ros_messages import (
    status_json_from_output,
    status_only_json,
    target_msg_from_output,
)
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
        self._appearance_attachment_config = AppearanceAttachmentConfig(
            enabled=self._appearance_enabled,
            max_image_age_ms=self._appearance_max_image_age_ms,
            compute_min_interval_ms=self._appearance_compute_min_interval_ms,
            cache_ttl_ms=self._appearance_cache_ttl_ms,
        )
        self._appearance_attachment_state = AppearanceAttachmentState()

        initial_id = params.selected_track_id
        self._pending_select_id: Optional[int] = initial_id if initial_id > 0 else None
        self._last_mirrored_target_id: Optional[int] = None

        cfg = build_target_memory_config(self, params)
        self._tim = TargetIdentityMemory(cfg)

        self._log_memory_config(cfg)

        qos = self._best_effort_qos()
        self._create_ros_interfaces(qos)
        self._setup_appearance_backend(qos)

        self._log_node_ready()

    def _log_node_ready(self) -> None:
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

    def _log_memory_config(self, cfg) -> None:
        self.get_logger().info(
            "TIM-MARS config: "
            f"allow_id_switch_recovery={cfg.allow_id_switch_recovery} "
            f"id_switch_spatial_gate_enabled={cfg.id_switch_spatial_gate_enabled} "
            f"rank_aware_reacquisition_enabled={cfg.rank_aware_reacquisition_enabled} "
            f"rank_aware_lost_min_app={cfg.rank_aware_lost_min_app:.3f} "
            f"rank_aware_lost_app_margin={cfg.rank_aware_lost_app_margin:.3f} "
            f"absence_recovery_enabled={cfg.absence_recovery_enabled} "
            f"absence_after_missed_frames={cfg.absence_after_missed_frames} "
            f"absence_min_similarity={cfg.absence_min_similarity:.3f} "
            f"absence_appearance_margin={cfg.absence_appearance_margin:.3f} "
            f"absence_confirm_frames={cfg.absence_confirm_frames} "
            f"hard_negative_memory_enabled={cfg.hard_negative_memory_enabled} "
            f"hard_negative_max_entries={cfg.hard_negative_max_entries} "
            f"hard_negative_reject_similarity={cfg.hard_negative_reject_similarity:.3f} "
            f"hard_negative_reject_margin={cfg.hard_negative_reject_margin:.3f} "
        )

    @staticmethod
    def _best_effort_qos() -> QoSProfile:
        return QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

    def _create_ros_interfaces(self, qos: QoSProfile) -> None:
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

    def _setup_appearance_backend(self, qos: QoSProfile) -> None:
        if not self._appearance_enabled:
            return

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

        target_msg = self._target_msg_from_output(msg, out)
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
        result = attach_appearance_features(
            config=self._appearance_attachment_config,
            state=self._appearance_attachment_state,
            data=AppearanceAttachmentInput(
                candidates=candidates,
                now_ns=time.monotonic_ns(),
                latest_image_bgr=self._latest_image_bgr,
                latest_image_seen_ns=self._latest_image_seen_ns,
                latest_image_seq=self._latest_image_seq,
                mars_backend=self._mars_backend,
            ),
        )

        self._appearance_attachment_state = result.state
        self._last_appearance_candidates = result.diagnostics.candidates
        self._last_appearance_features_valid = result.diagnostics.features_valid
        self._last_appearance_image_age_ms = result.diagnostics.image_age_ms
        self._last_appearance_skip_reason = result.diagnostics.skip_reason

        if result.diagnostics.warning is not None:
            self.get_logger().warn(
                f"TIM-MARS embedding extraction failed: {result.diagnostics.warning}"
            )

        return result.candidates

    def _target_msg_from_output(self, tracks_msg: Track2DArray, out: TargetMemoryOutput) -> TargetState:
        target_msg = target_msg_from_output(
            out,
            image_width=self._image_width,
            image_height=self._image_height,
            tracks_are_normalized=self._tracks_are_normalized,
            zero_id_when_not_visible=self._zero_id_when_not_visible,
        )
        target_msg.header = tracks_msg.header
        return target_msg

    def _publish_status_only(self, out: TargetMemoryOutput) -> None:
        msg = String()
        msg.data = status_only_json(out)
        self._status_pub.publish(msg)

    def _publish_status(
        self,
        out: TargetMemoryOutput,
        tracks_msg: Track2DArray,
        t_start_ns: int,
        t_end_ns: int,
    ) -> None:
        msg = String()
        msg.data = status_json_from_output(
            out,
            frame_id=int(tracks_msg.frame_id),
            lat_ms=float(t_end_ns - t_start_ns) / 1e6,
            num_tracks=len(tracks_msg.tracks),
            appearance_enabled=self._appearance_enabled,
            appearance_candidates=self._last_appearance_candidates,
            appearance_features_valid=self._last_appearance_features_valid,
            appearance_image_age_ms=self._last_appearance_image_age_ms,
            appearance_skip_reason=self._last_appearance_skip_reason,
            appearance_compute_min_interval_ms=self._appearance_compute_min_interval_ms,
            appearance_cache_ttl_ms=self._appearance_cache_ttl_ms,
            appearance_cache_size=len(self._appearance_attachment_state.cache_by_track_id),
            appearance_update_cooldown_remaining=int(
                getattr(self._tim, "_appearance_update_cooldown_frames_remaining", 0)
            ),
        )
        self._status_pub.publish(msg)


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
