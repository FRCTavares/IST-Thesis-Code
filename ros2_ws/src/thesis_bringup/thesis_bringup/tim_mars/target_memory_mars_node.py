"""ROS 2 runtime node for TIM-MARS selected-target memory.

This node wires ROS topics, parameters, optional raw target-selection mirroring,
optional image-based MARS appearance attachment, and status publication around
the pure TargetIdentityMemory algorithm.

Core accept/reject/reacquisition policy should stay out of this file. This file
should remain focused on ROS subscriptions, publications, image handling,
parameter wiring, and message conversion.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image
from std_msgs.msg import (
    Empty,
    String,
    UInt32,
)
from thesis_bringup.freshness import (
    classify_freshness,
    FRESHNESS_CONTRACT_VERSION,
)
from thesis_bringup.tim_mars.appearance_attachment import AppearanceAttachmentConfig
from thesis_bringup.tim_mars.appearance_request_transport import (
    TimAppearanceRequestTransport,
)
from thesis_bringup.tim_mars.appearance_ros_transport import (
    request_to_ros_message,
    result_from_ros_message,
)
from thesis_bringup.tim_mars.crop_quality import CropQualityThresholds
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
from thesis_bringup.tim_mars.runtime import (
    TimMarsRuntime,
    TimMarsRuntimeConfig,
    TimMarsRuntimeResult,
)
from thesis_bringup.tim_mars.target_memory import TargetMemoryOutput
from thesis_msgs.msg import (
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
    TargetState,
    Timing,
    Track2DArray,
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

    The raw /target topic remains available for diagnostics, while this node's
    validated output is the only target authority used by live control.
    """

    def __init__(self) -> None:
        super().__init__("target_memory_mars_node")

        declare_tim_mars_parameters(self)
        params = read_tim_mars_ros_params(self)

        self._freshness_max_output_age_s = (
            params.freshness_max_output_age_s
        )
        self._freshness_future_tolerance_s = (
            params.freshness_future_tolerance_s
        )
        self._last_tracks_source_stamp_ns: int | None = None

        self._tracks_topic = params.tracks_topic
        self._target_topic = params.target_topic
        self._timing_target_topic = params.timing_target_topic
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
        self._appearance_request_policy = (
            params.appearance_request_policy
        )
        self._appearance_image_topic = params.appearance_image_topic
        self._appearance_max_image_age_ms = params.appearance_max_image_age_ms
        self._appearance_compute_min_interval_ms = params.appearance_compute_min_interval_ms
        self._appearance_cache_ttl_ms = params.appearance_cache_ttl_ms
        self._appearance_cache_max_centre_distance_norm = (
            params.appearance_cache_max_centre_distance_norm
        )
        self._appearance_cache_min_scale_ratio = (
            params.appearance_cache_min_scale_ratio
        )
        self._mars_model_path = params.mars_model_path
        self._mars_batch_size = params.mars_batch_size

        self._appearance_async_reid_enabled = (
            params.appearance_async_reid_enabled
        )
        self._appearance_async_reid_request_topic = (
            params.appearance_async_reid_request_topic
        )
        self._appearance_async_reid_result_topic = (
            params.appearance_async_reid_result_topic
        )
        self._appearance_async_reid_queue_capacity = (
            params.appearance_async_reid_queue_capacity
        )
        self._appearance_async_reid_deadline_ms = (
            params.appearance_async_reid_deadline_ms
        )
        self._appearance_async_reid_qos_depth = (
            params.appearance_async_reid_qos_depth
        )

        self._mars_backend = None
        self._cv_bridge = None
        self._image_sub = None
        self._image_error_warned = False
        self._image_stamp_warned = False

        self._appearance_async_transport = None
        self._appearance_async_request_pub = None
        self._appearance_async_result_sub = None
        self._appearance_async_reconcile_timer = None
        self._appearance_async_last_status_json = None
        self._appearance_async_publish_errors = 0

        self._last_mirrored_target_id: Optional[int] = None

        cfg = build_target_memory_config(self, params)
        appearance_cfg = AppearanceAttachmentConfig(
            enabled=self._appearance_enabled,
            max_image_age_ms=self._appearance_max_image_age_ms,
            compute_min_interval_ms=self._appearance_compute_min_interval_ms,
            cache_ttl_ms=self._appearance_cache_ttl_ms,
            cache_max_centre_distance_norm=(
                self._appearance_cache_max_centre_distance_norm
            ),
            cache_min_scale_ratio=(
                self._appearance_cache_min_scale_ratio
            ),
            crop_quality=CropQualityThresholds(
                min_width_px=(
                    params.appearance_crop_min_width_px
                ),
                min_height_px=(
                    params.appearance_crop_min_height_px
                ),
                max_clipping_fraction=(
                    params
                    .appearance_crop_max_clipping_fraction
                ),
                min_aspect_ratio=(
                    params.appearance_crop_min_aspect_ratio
                ),
                max_aspect_ratio=(
                    params.appearance_crop_max_aspect_ratio
                ),
                max_overlap_iou_for_memory=(
                    params
                    .appearance_crop_max_overlap_iou_for_memory
                ),
                min_centre_distance_norm_for_memory=(
                    params
                    .appearance_crop_min_centre_distance_norm_for_memory
                ),
            ),
        )
        self._runtime = TimMarsRuntime(
            TimMarsRuntimeConfig(
                memory=cfg,
                appearance=appearance_cfg,
                image_width=self._image_width,
                image_height=self._image_height,
                appearance_request_policy=(
                    self._appearance_request_policy
                ),
                tracks_are_normalized=self._tracks_are_normalized,
                selected_track_id=params.selected_track_id,
                auto_select_largest=self._auto_select_largest,
                image_buffer_size=64,
                appearance_async_request_crops_enabled=(
                    self._appearance_async_reid_enabled
                ),
            )
        )

        self._log_memory_config(cfg)

        qos = self._best_effort_qos()
        self._create_ros_interfaces(qos)
        self._setup_async_reid_transport()
        self._setup_appearance_backend(qos)

        self._log_node_ready()

    def _log_node_ready(self) -> None:
        self.get_logger().info(
            "TIM-MARS node ready: "
            f"tracks={self._tracks_topic}, target={self._target_topic}, "
            f"timing_target={self._timing_target_topic}, "
            f"select={self._select_topic}, clear={self._clear_topic}, "
            f"normalised_tracks={self._tracks_are_normalized}, "
            f"mirror_raw_target_selection={self._mirror_raw_target_selection}, "
            f"appearance_enabled={self._appearance_enabled}, "
            f"appearance_request_policy="
            f"{self._appearance_request_policy}, "
            f"appearance_image_topic={self._appearance_image_topic}, "
            f"appearance_async_reid_enabled="
            f"{self._appearance_async_reid_enabled}"
        )

        if self._runtime.pending_select_id is not None:
            self.get_logger().info(
                "Waiting to initialise TIM from track id "
                f"{self._runtime.pending_select_id}"
            )

    def _log_memory_config(self, cfg) -> None:
        self.get_logger().info(
            "TIM-MARS config: "
            f"allow_id_switch_recovery={cfg.allow_id_switch_recovery} "
            f"id_switch_spatial_gate_enabled={cfg.id_switch_spatial_gate_enabled} "
            f"id_switch_min_appearance_similarity="
            f"{cfg.id_switch_min_appearance_similarity:.3f} "
            f"appearance_protected_memory_enabled="
            f"{cfg.appearance_protected_memory_enabled} "
            f"appearance_trusted_gallery_max_entries="
            f"{cfg.appearance_trusted_gallery_max_entries} "
            f"appearance_gallery_min_anchor_similarity="
            f"{cfg.appearance_gallery_min_anchor_similarity:.3f} "
            f"appearance_trusted_lock_frames_before_update="
            f"{cfg.appearance_trusted_lock_frames_before_update} "
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
            f"hard_negative_confirm_observations="
            f"{cfg.hard_negative_confirm_observations} "
            f"hard_negative_max_positive_similarity="
            f"{cfg.hard_negative_max_positive_similarity:.3f} "
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
        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._target_pub = self.create_publisher(TargetState, self._target_topic, qos)
        self._timing_target_pub = self.create_publisher(
            Timing,
            self._timing_target_topic,
            qos,
        )
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
            command_qos,
        )
        self._clear_sub = self.create_subscription(
            Empty,
            self._clear_topic,
            self._on_clear,
            command_qos,
        )

        self._raw_target_sub = None
        if self._mirror_raw_target_selection:
            self._raw_target_sub = self.create_subscription(
                TargetState,
                self._mirror_target_topic,
                self._on_raw_target,
                qos,
            )

    def _setup_async_reid_transport(self) -> None:
        """Create optional TIM-side request and result ROS interfaces."""
        if not self._appearance_async_reid_enabled:
            return

        if not self._appearance_enabled:
            raise RuntimeError(
                "asynchronous ReID transport requires "
                "appearance_enabled"
            )

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=self._appearance_async_reid_qos_depth,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self._appearance_async_transport = (
            TimAppearanceRequestTransport(
                capacity=(
                    self
                    ._appearance_async_reid_queue_capacity
                ),
                deadline_ms=(
                    self
                    ._appearance_async_reid_deadline_ms
                ),
            )
        )

        self._appearance_async_request_pub = (
            self.create_publisher(
                AppearanceEmbeddingRequest,
                self
                ._appearance_async_reid_request_topic,
                qos,
            )
        )
        self._appearance_async_result_sub = (
            self.create_subscription(
                AppearanceEmbeddingResult,
                self
                ._appearance_async_reid_result_topic,
                self._on_async_reid_result,
                qos,
            )
        )

        reconcile_period_s = min(
            0.25,
            max(
                0.05,
                self._appearance_async_reid_deadline_ms
                / 2000.0,
            ),
        )
        self._appearance_async_reconcile_timer = (
            self.create_timer(
                reconcile_period_s,
                self._reconcile_async_reid,
            )
        )

        self.get_logger().info(
            "Enabled TIM causal RepVGG transport "
            f"(request_topic="
            f"{self._appearance_async_reid_request_topic}, "
            f"result_topic="
            f"{self._appearance_async_reid_result_topic}, "
            f"capacity="
            f"{self._appearance_async_reid_queue_capacity}, "
            f"deadline_ms="
            f"{self._appearance_async_reid_deadline_ms:.1f}, "
            f"qos_depth="
            f"{self._appearance_async_reid_qos_depth})"
        )

    def _cancel_async_reid(
        self,
        reason: str,
    ) -> tuple[int, ...]:
        transport = self._appearance_async_transport

        if transport is None:
            return ()

        cancelled = transport.cancel_all(
            reason=str(reason)
        )

        if cancelled:
            self.get_logger().info(
                "Cancelled TIM causal ReID work "
                f"(reason={reason}, "
                f"request_ids={cancelled})"
            )

        return cancelled

    def _reconcile_async_reid(self) -> None:
        """Expire overdue causal work and republish current status."""
        transport = self._appearance_async_transport

        if transport is None:
            return

        expired = transport.expire_in_flight(
            now_ns=time.monotonic_ns()
        )

        if expired:
            self.get_logger().warning(
                "Expired TIM causal ReID requests "
                "without a result "
                f"(count={len(expired)}, "
                f"first={expired[0]}, "
                f"last={expired[-1]})"
            )

        base_status_json = (
            self._appearance_async_last_status_json
        )

        if base_status_json is None:
            return

        message = String()
        message.data = (
            self._augment_status_with_async_reid(
                base_status_json
            )
        )
        self._status_pub.publish(message)

    def _publish_async_reid_requests(
        self,
        result: TimMarsRuntimeResult,
    ) -> None:
        transport = self._appearance_async_transport
        publisher = self._appearance_async_request_pub

        if transport is None or publisher is None:
            return

        if not result.appearance_request_crops:
            return

        batch = transport.stage(
            result.appearance_request_crops,
            now_ns=time.monotonic_ns(),
        )

        if batch.dropped_request_ids:
            self.get_logger().warning(
                "TIM causal ReID ledger dropped requests "
                f"{batch.dropped_request_ids}"
            )

        if batch.expired_request_ids:
            self.get_logger().warning(
                "TIM causal ReID requests expired "
                f"before publication: "
                f"{batch.expired_request_ids}"
            )

        for request in batch.requests:
            try:
                publisher.publish(
                    request_to_ros_message(request)
                )
            except Exception as exc:
                self._appearance_async_publish_errors += 1
                self.get_logger().error(
                    "TIM causal ReID publication failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                self._cancel_async_reid(
                    "request_publish_failure"
                )
                break

    def _on_async_reid_result(
        self,
        message: AppearanceEmbeddingResult,
    ) -> None:
        transport = self._appearance_async_transport

        if transport is None:
            return

        now_ns = time.monotonic_ns()
        frame_generation = int(
            self._runtime
            .appearance_state
            .frame_generation
        )
        track_generations = dict(
            self._runtime
            .appearance_state
            .track_generation_by_id
        )

        try:
            result = result_from_ros_message(
                message
            )
        except Exception as exc:
            decision = (
                transport.reject_malformed_result(
                    request_id=int(
                        message.request_id
                    ),
                    now_ns=now_ns,
                    reason=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    current_frame_generation=(
                        frame_generation
                    ),
                    current_track_generations=(
                        track_generations
                    ),
                )
            )

            self.get_logger().warning(
                "Rejected malformed RepVGG result "
                f"id={int(message.request_id)}: "
                f"{type(exc).__name__}: {exc}"
            )

            if decision is not None:
                self.get_logger().warning(
                    "Resolved malformed RepVGG result "
                    f"as {decision.reason}"
                )
            return

        decision = transport.complete(
            result,
            now_ns=now_ns,
            current_frame_generation=(
                frame_generation
            ),
            current_track_generations=(
                track_generations
            ),
        )

        if not decision.accepted:
            self.get_logger().warning(
                "Rejected causal RepVGG result "
                f"id={decision.request_id}, "
                f"track={decision.track_id}, "
                f"reason={decision.reason}"
            )

    def _augment_status_with_async_reid(
        self,
        status_json: str,
    ) -> str:
        transport = self._appearance_async_transport

        if transport is None:
            return status_json

        diagnostics = transport.diagnostics()
        queue = diagnostics.queue

        payload = json.loads(status_json)
        payload["appearance_async_reid"] = {
            "enabled": True,
            "constructed": diagnostics.constructed,
            "published": diagnostics.published,
            "cancelled": diagnostics.cancelled,
            "expired_in_flight": (
                diagnostics.expired_in_flight
            ),
            "malformed_results": (
                diagnostics.malformed_results
            ),
            "publish_errors": (
                self._appearance_async_publish_errors
            ),
            "queued": queue.queued,
            "in_flight": queue.in_flight,
            "maximum_queued": queue.maximum_queued,
            "submitted": queue.submitted,
            "dequeued": queue.dequeued,
            "accepted_results": (
                queue.accepted_results
            ),
            "rejected_submissions": (
                queue.rejected_submissions
            ),
            "rejected_results": (
                queue.rejected_results
            ),
            "drop_reasons": queue.drop_reasons,
            "result_reasons": queue.result_reasons,
            "last_result_reason": (
                diagnostics.last_result_reason
            ),
            "last_accepted_request_id": (
                diagnostics
                .last_accepted_request_id
            ),
            "last_accepted_track_id": (
                diagnostics
                .last_accepted_track_id
            ),
        }

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
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
        self._runtime.mars_backend = self._mars_backend
        self.get_logger().info(
            f"TIM-MARS loaded MARS ReID model: {self._mars_model_path}"
        )

    def _on_image(self, msg: Image) -> None:
        if not self._appearance_enabled or self._cv_bridge is None:
            return

        try:
            image_bgr = self._cv_bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8",
            )
            image_stamp_ns = self._runtime.stamp_to_ns(msg.header.stamp)

            if not self._runtime.add_image(image_stamp_ns, image_bgr):
                if not self._image_stamp_warned:
                    self.get_logger().warn(
                        "TIM appearance image has no valid header timestamp; "
                        "discarding it to avoid mixing clock domains"
                    )
                    self._image_stamp_warned = True
        except Exception as exc:
            if not self._image_error_warned:
                self.get_logger().warn(
                    f"TIM appearance image conversion failed: {exc}"
                )
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

        if (
            self._last_mirrored_target_id == target_id
            and self._runtime.pending_select_id is None
        ):
            return

        self._cancel_async_reid(
            "mirrored_target_selection"
        )
        self._last_mirrored_target_id = target_id
        self._runtime.request_selection(target_id)
        self.get_logger().info(
            f"TIM mirrored raw /target selection: track id {target_id}"
        )

    def _on_select(self, msg: UInt32) -> None:
        requested_id = int(msg.data)
        if requested_id <= 0:
            self._cancel_async_reid(
                "operator_select_clear"
            )
            out = self._runtime.clear()
            self._publish_target_reset()
            self.get_logger().info("TIM cleared by select id <= 0")
            self._publish_status_only(out)
            return

        self._cancel_async_reid(
            "operator_selection"
        )
        out = self._runtime.clear()
        self._publish_target_reset()
        self._publish_status_only(out)
        self._runtime.request_selection(requested_id)
        self.get_logger().info(
            f"TIM pending operator selection: track id {requested_id}"
        )

    def _on_clear(self, _: Empty) -> None:
        self._cancel_async_reid(
            "operator_clear"
        )
        out = self._runtime.clear()
        self._publish_target_reset()
        self.get_logger().info("TIM cleared")
        self._publish_status_only(out)

    def _publish_target_reset(self) -> None:
        """Immediately revoke controller authority while TIM has no target."""
        now = self.get_clock().now()
        monotonic_ns = time.monotonic_ns()

        target_msg = TargetState()
        target_msg.header.stamp = now.to_msg()
        target_msg.frame_id = 0
        target_msg.src_stamp_ns = 0
        target_msg.t_cam_msg_seen_ns = 0
        target_msg.t_target_cb_start_ns = int(monotonic_ns)
        target_msg.t_target_cb_end_ns = int(monotonic_ns)
        target_msg.id = 0
        target_msg.cx = 0.0
        target_msg.cy = 0.0
        target_msg.w = 0.0
        target_msg.h = 0.0
        target_msg.score = 0.0
        target_msg.quality = 0.0
        self._target_pub.publish(target_msg)

    def _on_tracks(self, msg: Track2DArray) -> None:
        t_start_ns = time.monotonic_ns()

        pending_before = self._runtime.pending_select_id
        state_before = self._runtime.memory.state
        frame_generation_before = int(
            self._runtime
            .appearance_state
            .frame_generation
        )

        result = self._runtime.process_tracks(msg)
        out = result.output

        frame_generation_after = int(
            self._runtime
            .appearance_state
            .frame_generation
        )

        if (
            self._appearance_async_transport
            is not None
            and frame_generation_before > 0
            and frame_generation_after
            != frame_generation_before
        ):
            self._cancel_async_reid(
                "source_frame_generation_change"
            )

        self._publish_async_reid_requests(
            result
        )

        if (
            pending_before is not None
            and self._runtime.pending_select_id is None
            and out.reason == "operator_select"
        ):
            self.get_logger().info(
                f"TIM selected track {out.target_track_id} "
                f"on frame {int(msg.frame_id)}"
            )
        elif (
            pending_before is None
            and self._auto_select_largest
            and state_before.value == "NO_TARGET"
            and out.reason == "operator_select"
        ):
            self.get_logger().warn(
                f"TIM auto-selected largest track {out.target_track_id}. "
                "Use only for manual inspection, not final thesis evaluation."
            )

        if result.diagnostics.appearance_warning is not None:
            self.get_logger().warn(
                "TIM-MARS embedding extraction failed: "
                f"{result.diagnostics.appearance_warning}"
            )

        target_msg = self._target_msg_from_output(msg, out)
        target_msg.t_target_cb_start_ns = int(t_start_ns)
        t_process_end_ns = time.monotonic_ns()
        target_msg.t_target_cb_end_ns = int(t_process_end_ns)
        self._target_pub.publish(target_msg)
        t_target_pub_end_ns = time.monotonic_ns()

        timing_msg = Timing()
        timing_msg.frame_id = int(msg.frame_id)
        timing_msg.src_stamp_ns = int(target_msg.src_stamp_ns)
        timing_msg.t_cam_msg_seen_ns = int(msg.t_cam_msg_seen_ns)
        timing_msg.t_target_cb_start_ns = int(t_start_ns)
        timing_msg.t_target_process_end_ns = int(t_process_end_ns)
        timing_msg.t_target_pub_end_ns = int(t_target_pub_end_ns)
        timing_msg.tim_mars_processing_ms = float(
            (t_process_end_ns - t_start_ns) / 1e6
        )
        if (
            timing_msg.t_cam_msg_seen_ns > 0
            and t_target_pub_end_ns >= timing_msg.t_cam_msg_seen_ns
        ):
            timing_msg.e2e_validated_target_ms = float(
                (t_target_pub_end_ns - timing_msg.t_cam_msg_seen_ns) / 1e6
            )
        self._timing_target_pub.publish(timing_msg)

        self._publish_status(
            result,
            msg,
            t_start_ns,
            t_process_end_ns,
        )

    def _target_msg_from_output(
        self,
        tracks_msg: Track2DArray,
        out: TargetMemoryOutput,
    ) -> TargetState:
        target_msg = target_msg_from_output(
            out,
            image_width=self._image_width,
            image_height=self._image_height,
            tracks_are_normalized=self._tracks_are_normalized,
            zero_id_when_not_visible=self._zero_id_when_not_visible,
        )
        target_msg.header = tracks_msg.header
        target_msg.frame_id = int(tracks_msg.frame_id)
        target_msg.src_stamp_ns = int(tracks_msg.src_stamp_ns)
        if target_msg.src_stamp_ns <= 0:
            target_msg.src_stamp_ns = self._runtime.track_time_ns(tracks_msg) or 0
        target_msg.t_cam_msg_seen_ns = int(tracks_msg.t_cam_msg_seen_ns)
        return target_msg

    def _publish_status_only(self, out: TargetMemoryOutput) -> None:
        base_status_json = status_only_json(out)
        self._appearance_async_last_status_json = (
            base_status_json
        )

        msg = String()
        msg.data = self._augment_status_with_async_reid(
            base_status_json
        )
        self._status_pub.publish(msg)

    def _publish_status(
        self,
        result: TimMarsRuntimeResult,
        tracks_msg: Track2DArray,
        t_start_ns: int,
        t_end_ns: int,
    ) -> None:
        diagnostics = result.diagnostics
        source_stamp_ns = int(tracks_msg.src_stamp_ns)
        if source_stamp_ns <= 0:
            source_stamp_ns = self._runtime.track_time_ns(tracks_msg) or 0
        freshness = classify_freshness(
            now_ns=self.get_clock().now().nanoseconds,
            source_stamp_ns=source_stamp_ns,
            max_age_s=self._freshness_max_output_age_s,
            future_tolerance_s=self._freshness_future_tolerance_s,
            previous_source_stamp_ns=self._last_tracks_source_stamp_ns,
            reject_duplicate=True,
        )
        if (
            source_stamp_ns > 0
            and (
                self._last_tracks_source_stamp_ns is None
                or source_stamp_ns > self._last_tracks_source_stamp_ns
            )
        ):
            self._last_tracks_source_stamp_ns = source_stamp_ns

        msg = String()
        base_status_json = status_json_from_output(
            result.output,
            frame_id=int(tracks_msg.frame_id),
            tim_mars_processing_ms=float(
                t_end_ns - t_start_ns
            ) / 1e6,
            num_tracks=len(tracks_msg.tracks),
            appearance_enabled=self._appearance_enabled,
            appearance_candidates=diagnostics.appearance_candidates,
            appearance_request_policy=(
                diagnostics.appearance_request_policy
            ),
            appearance_request_reason=(
                diagnostics.appearance_request_reason
            ),
            appearance_request_candidates=(
                diagnostics.appearance_request_candidates
            ),
            appearance_request_track_ids=(
                diagnostics.appearance_request_track_ids
            ),
            appearance_request_encoding_eligible=(
                diagnostics
                .appearance_request_encoding_eligible
            ),
            appearance_features_valid=diagnostics.appearance_features_valid,
            appearance_image_age_ms=diagnostics.image_track_offset_ms,
            appearance_skip_reason=diagnostics.appearance_skip_reason,
            track_timestamp_ns=diagnostics.track_timestamp_ns,
            selected_image_timestamp_ns=(
                diagnostics.selected_image_timestamp_ns
            ),
            image_track_offset_ms=diagnostics.image_track_offset_ms,
            appearance_warning=diagnostics.appearance_warning,
            candidate_track_ids=diagnostics.candidate_track_ids,
            appearance_compute_min_interval_ms=self._appearance_compute_min_interval_ms,
            appearance_cache_ttl_ms=self._appearance_cache_ttl_ms,
            appearance_cache_size=diagnostics.appearance_cache_size,
            appearance_cache_lookups=(
                diagnostics.appearance_cache_lookups
            ),
            appearance_cache_hits=(
                diagnostics.appearance_cache_hits
            ),
            appearance_cache_misses=(
                diagnostics.appearance_cache_misses
            ),
            appearance_cache_expired=(
                diagnostics.appearance_cache_expired
            ),
            appearance_cache_invalidated=(
                diagnostics.appearance_cache_invalidated
            ),
            appearance_embedding_age_ms_by_track_id=(
                diagnostics.appearance_embedding_age_ms_by_track_id
            ),
            appearance_crop_quality_by_track_id=(
                diagnostics.appearance_crop_quality_by_track_id
            ),
            appearance_encoding_rejected=(
                diagnostics.appearance_encoding_rejected
            ),
            appearance_memory_update_ineligible=(
                diagnostics.appearance_memory_update_ineligible
            ),
            appearance_encoding_eligible=(
                diagnostics.appearance_encoding_eligible
            ),
            appearance_backend_calls=(
                diagnostics.appearance_backend_calls
            ),
            appearance_backend_requested=(
                diagnostics.appearance_backend_requested
            ),
            appearance_backend_returned=(
                diagnostics.appearance_backend_returned
            ),
            appearance_backend_valid=(
                diagnostics.appearance_backend_valid
            ),
            appearance_backend_wall_ms=(
                diagnostics.appearance_backend_wall_ms
            ),
            appearance_update_cooldown_remaining=(
                diagnostics.appearance_update_cooldown_remaining
            ),
            freshness_contract=FRESHNESS_CONTRACT_VERSION,
            freshness_status=freshness.status,
            freshness_is_fresh=freshness.fresh,
            freshness_source_age_ms=(
                None
                if freshness.source_age_s is None
                else freshness.source_age_s * 1000.0
            ),
            freshness_max_output_age_ms=(
                self._freshness_max_output_age_s * 1000.0
            ),
        )
        self._appearance_async_last_status_json = (
            base_status_json
        )
        msg.data = self._augment_status_with_async_reid(
            base_status_json
        )
        self._status_pub.publish(msg)

    def destroy_node(self):
        """Cancel causal transport before destroying ROS interfaces."""
        timer = self._appearance_async_reconcile_timer

        if timer is not None:
            timer.cancel()

        self._cancel_async_reid(
            "node_shutdown"
        )
        return super().destroy_node()


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
