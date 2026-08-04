"""ROS parameter declaration and configuration bridge for TIM-MARS.

This module declares the ROS parameter surface of target_memory_mars_node.py,
reads parameter values from rclpy, and builds the pure TargetMemoryConfig used
by the selected-target memory state machine.

It is the boundary between ROS configuration and pure TIM-MARS algorithm logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thesis_bringup.freshness import (
    DEFAULT_FUTURE_TOLERANCE_S,
    DEFAULT_MAX_OUTPUT_AGE_S,
)
from thesis_bringup.tim_mars.appearance_request_policy import (
    AppearanceRequestPolicy,
)
from thesis_bringup.tim_mars.target_memory import TargetMemoryConfig


@dataclass(frozen=True)
class TimMarsRosParams:
    """ROS-facing TIM-MARS parameters that are not part of the pure algorithm."""

    tracks_topic: str
    target_topic: str
    status_topic: str
    select_topic: str
    clear_topic: str
    mirror_target_topic: str
    mirror_raw_target_selection: bool

    image_width: float
    image_height: float
    tracks_are_normalized: bool
    selected_track_id: int
    auto_select_largest: bool
    zero_id_when_not_visible: bool
    freshness_max_output_age_s: float
    freshness_future_tolerance_s: float

    appearance_enabled: bool
    appearance_request_policy: str
    appearance_image_topic: str
    appearance_max_image_age_ms: float
    appearance_compute_min_interval_ms: float
    appearance_cache_ttl_ms: float
    appearance_cache_max_centre_distance_norm: float
    appearance_cache_min_scale_ratio: float

    appearance_async_reid_enabled: bool
    appearance_async_reid_request_topic: str
    appearance_async_reid_result_topic: str
    appearance_async_reid_queue_capacity: int
    appearance_async_reid_deadline_ms: float
    appearance_async_reid_qos_depth: int

    appearance_crop_min_width_px: float
    appearance_crop_min_height_px: float
    appearance_crop_max_clipping_fraction: float
    appearance_crop_min_aspect_ratio: float
    appearance_crop_max_aspect_ratio: float
    appearance_crop_max_overlap_iou_for_memory: float
    appearance_crop_min_centre_distance_norm_for_memory: float

    mars_model_path: str
    mars_batch_size: int


def declare_tim_mars_parameters(node: Any) -> None:
    """Declare all ROS parameters consumed by the TIM-MARS node."""
    # ROS topic wiring.
    node.declare_parameter("tracks_topic", "/tracks")
    node.declare_parameter("target_topic", "/target_memory_mars")
    node.declare_parameter("status_topic", "/target_memory_mars/status")
    node.declare_parameter("select_topic", "/target_memory_mars/select")
    node.declare_parameter("clear_topic", "/target_memory_mars/clear")
    node.declare_parameter("mirror_target_topic", "/target")
    node.declare_parameter("mirror_raw_target_selection", False)

    # Image geometry and selected-target initialization.
    node.declare_parameter("image_width", 640.0)
    node.declare_parameter("image_height", 640.0)
    node.declare_parameter("tracks_are_normalized", False)
    node.declare_parameter("selected_track_id", 0)
    node.declare_parameter("auto_select_largest", False)
    node.declare_parameter("zero_id_when_not_visible", True)
    node.declare_parameter(
        "freshness_max_output_age_s",
        DEFAULT_MAX_OUTPUT_AGE_S,
    )
    node.declare_parameter(
        "freshness_future_tolerance_s",
        DEFAULT_FUTURE_TOLERANCE_S,
    )

    # Candidate scoring and geometry normalization.
    node.declare_parameter("w_iou", 0.34)
    node.declare_parameter("w_distance", 0.26)
    node.declare_parameter("w_scale", 0.18)
    node.declare_parameter("w_confidence", 0.14)
    node.declare_parameter("w_id_bonus", 0.08)
    node.declare_parameter("distance_sigma", 0.18)
    node.declare_parameter("scale_sigma", 0.55)
    node.declare_parameter("stale_quality_decay", 0.85)

    # Acceptance, ambiguity, and state hysteresis.
    node.declare_parameter("accept_score_locked", 0.52)
    node.declare_parameter("accept_score_lost", 0.60)
    node.declare_parameter("ambiguity_margin", 0.07)
    node.declare_parameter("max_uncertain_frames", 6)
    node.declare_parameter("min_confirm_frames_after_reacquire", 1)
    node.declare_parameter("min_candidate_score", 0.10)

    # Controlled ID-switch recovery and short-gap protection.
    node.declare_parameter("allow_id_switch_recovery", True)
    node.declare_parameter("same_id_accept_relief", 0.08)
    node.declare_parameter("id_switch_spatial_gate_enabled", False)
    node.declare_parameter("id_switch_min_iou", 0.05)
    node.declare_parameter("id_switch_min_distance", 0.35)
    node.declare_parameter("id_switch_min_scale", 0.35)
    node.declare_parameter(
        "id_switch_min_appearance_similarity",
        0.0,
    )
    node.declare_parameter("short_gap_same_id_priority_enabled", True)
    node.declare_parameter("short_gap_same_id_grace_frames", 8)
    node.declare_parameter("short_gap_same_id_min_total", 0.30)
    node.declare_parameter("short_gap_new_id_suppression_enabled", True)
    node.declare_parameter("short_gap_new_id_allow_total", 0.70)
    node.declare_parameter("short_gap_group_risk_allow_total", 0.85)

    # Appearance extraction, scoring, and positive-memory update policy.
    node.declare_parameter("appearance_enabled", True)
    node.declare_parameter(
        "appearance_request_policy",
        AppearanceRequestPolicy.ALL_CANDIDATES.value,
    )
    node.declare_parameter("appearance_image_topic", "/camera/dashboard")
    node.declare_parameter("appearance_max_image_age_ms", 250.0)
    node.declare_parameter("appearance_compute_min_interval_ms", 250.0)
    node.declare_parameter("appearance_cache_ttl_ms", 750.0)
    node.declare_parameter(
        "appearance_cache_max_centre_distance_norm",
        0.25,
    )
    node.declare_parameter(
        "appearance_cache_min_scale_ratio",
        0.25,
    )

    # Appearance crop-quality controls, measured in appearance-image pixels.
    # Optional cross-process RepVGG transport.
    node.declare_parameter(
        "appearance_async_reid_enabled",
        False,
    )
    node.declare_parameter(
        "appearance_async_reid_request_topic",
        "/appearance/reid/request",
    )
    node.declare_parameter(
        "appearance_async_reid_result_topic",
        "/appearance/reid/result",
    )
    node.declare_parameter(
        "appearance_async_reid_queue_capacity",
        8,
    )
    node.declare_parameter(
        "appearance_async_reid_deadline_ms",
        500.0,
    )
    node.declare_parameter(
        "appearance_async_reid_qos_depth",
        1,
    )

    node.declare_parameter("appearance_crop_min_width_px", 12.0)
    node.declare_parameter("appearance_crop_min_height_px", 24.0)
    node.declare_parameter(
        "appearance_crop_max_clipping_fraction",
        0.10,
    )
    node.declare_parameter(
        "appearance_crop_min_aspect_ratio",
        0.20,
    )
    node.declare_parameter(
        "appearance_crop_max_aspect_ratio",
        1.00,
    )
    node.declare_parameter(
        "appearance_crop_max_overlap_iou_for_memory",
        0.10,
    )
    node.declare_parameter(
        "appearance_crop_min_centre_distance_norm_for_memory",
        0.04,
    )

    node.declare_parameter("appearance_weight", 0.12)
    node.declare_parameter("appearance_min_similarity", 0.35)
    node.declare_parameter("appearance_update_alpha", 0.10)
    node.declare_parameter("appearance_ambiguous_only", True)
    node.declare_parameter("appearance_update_cooldown_after_reacquire_frames", 0)

    # P1.4 protected/adaptive positive-memory separation.
    node.declare_parameter(
        "appearance_protected_memory_enabled",
        False,
    )
    node.declare_parameter(
        "appearance_trusted_gallery_max_entries",
        4,
    )
    node.declare_parameter(
        "appearance_gallery_min_anchor_similarity",
        0.0,
    )
    node.declare_parameter(
        "appearance_trusted_lock_frames_before_update",
        2,
    )

    node.declare_parameter(
        "mars_model_path",
        "/home/francisco/Desktop/Thesis-Code/models/reid/mars-small128.pb",
    )
    node.declare_parameter("mars_batch_size", 32)

    # Hard-negative distractor memory.
    node.declare_parameter("hard_negative_memory_enabled", True)
    node.declare_parameter("hard_negative_max_entries", 8)
    node.declare_parameter("hard_negative_update_alpha", 0.20)
    node.declare_parameter("hard_negative_min_candidate_similarity", 0.70)
    node.declare_parameter("hard_negative_confirm_observations", 2)
    node.declare_parameter(
        "hard_negative_max_positive_similarity",
        1.01,
    )
    node.declare_parameter("hard_negative_reject_similarity", 0.80)
    node.declare_parameter("hard_negative_reject_margin", 0.03)
    node.declare_parameter("hard_negative_min_geometry", 0.20)
    node.declare_parameter("hard_negative_max_age_frames", 0)
    node.declare_parameter(
        "hard_negative_decay_policy",
        "none_until_expiry",
    )
    node.declare_parameter(
        "same_id_hijack_protection_enabled",
        False,
    )

    # Conservative appearance publication filter.
    node.declare_parameter("appearance_conservative_enabled", True)
    node.declare_parameter("appearance_conservative_require_appearance", False)
    node.declare_parameter("appearance_conservative_min_similarity", 0.65)
    node.declare_parameter("appearance_conservative_margin", 0.05)

    # Rank-aware reacquisition and candidate-belief confirmation.
    node.declare_parameter("rank_aware_reacquisition_enabled", True)
    node.declare_parameter("rank_aware_lost_min_total", 0.40)
    node.declare_parameter("rank_aware_lost_min_geom", 0.10)
    node.declare_parameter("rank_aware_lost_min_app", 0.05)
    node.declare_parameter("rank_aware_lost_app_margin", 0.03)
    node.declare_parameter("rank_aware_confirm_frames", 1)
    node.declare_parameter("candidate_belief_enabled", False)
    node.declare_parameter("candidate_belief_min_score", 0.45)
    node.declare_parameter("candidate_belief_confirm_frames", 2)

    # Absence-aware new-ID recovery.
    node.declare_parameter("absence_recovery_enabled", False)
    node.declare_parameter("absence_after_missed_frames", 6)
    node.declare_parameter("absence_new_id_requires_appearance", True)
    node.declare_parameter("absence_min_total", 0.45)
    node.declare_parameter("absence_min_distance", 0.25)
    node.declare_parameter("absence_min_scale", 0.35)
    node.declare_parameter("absence_min_similarity", 0.65)
    node.declare_parameter("absence_appearance_margin", 0.20)
    node.declare_parameter("absence_confirm_frames", 3)


def _read_appearance_request_policy(node: Any) -> str:
    """Read and validate the configured candidate-request policy."""
    raw_value = str(
        node.get_parameter(
            "appearance_request_policy"
        ).value
    )

    try:
        return AppearanceRequestPolicy(raw_value).value
    except ValueError as exc:
        supported = ", ".join(
            policy.value
            for policy in AppearanceRequestPolicy
        )
        raise ValueError(
            "Unsupported appearance_request_policy "
            f"{raw_value!r}; expected one of: {supported}"
        ) from exc


def read_tim_mars_ros_params(node: Any) -> TimMarsRosParams:
    """Read ROS-facing TIM-MARS parameters after declaration/overrides."""
    return TimMarsRosParams(
        tracks_topic=str(node.get_parameter("tracks_topic").value),
        target_topic=str(node.get_parameter("target_topic").value),
        status_topic=str(node.get_parameter("status_topic").value),
        select_topic=str(node.get_parameter("select_topic").value),
        clear_topic=str(node.get_parameter("clear_topic").value),
        mirror_target_topic=str(node.get_parameter("mirror_target_topic").value),
        mirror_raw_target_selection=bool(node.get_parameter("mirror_raw_target_selection").value),
        image_width=float(node.get_parameter("image_width").value),
        image_height=float(node.get_parameter("image_height").value),
        tracks_are_normalized=bool(node.get_parameter("tracks_are_normalized").value),
        selected_track_id=int(node.get_parameter("selected_track_id").value),
        auto_select_largest=bool(node.get_parameter("auto_select_largest").value),
        zero_id_when_not_visible=bool(node.get_parameter("zero_id_when_not_visible").value),
        freshness_max_output_age_s=float(
            node.get_parameter("freshness_max_output_age_s").value
        ),
        freshness_future_tolerance_s=float(
            node.get_parameter("freshness_future_tolerance_s").value
        ),
        appearance_enabled=bool(node.get_parameter("appearance_enabled").value),
        appearance_request_policy=(
            _read_appearance_request_policy(node)
        ),
        appearance_image_topic=str(node.get_parameter("appearance_image_topic").value),
        appearance_max_image_age_ms=float(node.get_parameter("appearance_max_image_age_ms").value),
        appearance_compute_min_interval_ms=max(
            0.0,
            float(node.get_parameter("appearance_compute_min_interval_ms").value),
        ),
        appearance_cache_ttl_ms=max(
            0.0,
            float(node.get_parameter("appearance_cache_ttl_ms").value),
        ),
        appearance_cache_max_centre_distance_norm=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_cache_max_centre_distance_norm"
                ).value
            ),
        ),
        appearance_cache_min_scale_ratio=max(
            0.0,
            min(
                1.0,
                float(
                    node.get_parameter(
                        "appearance_cache_min_scale_ratio"
                    ).value
                ),
            ),
        ),
        appearance_async_reid_enabled=bool(
            node.get_parameter(
                "appearance_async_reid_enabled"
            ).value
        ),
        appearance_async_reid_request_topic=str(
            node.get_parameter(
                "appearance_async_reid_request_topic"
            ).value
        ),
        appearance_async_reid_result_topic=str(
            node.get_parameter(
                "appearance_async_reid_result_topic"
            ).value
        ),
        appearance_async_reid_queue_capacity=max(
            1,
            int(
                node.get_parameter(
                    "appearance_async_reid_queue_capacity"
                ).value
            ),
        ),
        appearance_async_reid_deadline_ms=max(
            1.0,
            float(
                node.get_parameter(
                    "appearance_async_reid_deadline_ms"
                ).value
            ),
        ),
        appearance_async_reid_qos_depth=max(
            1,
            int(
                node.get_parameter(
                    "appearance_async_reid_qos_depth"
                ).value
            ),
        ),
        appearance_crop_min_width_px=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_crop_min_width_px"
                ).value
            ),
        ),
        appearance_crop_min_height_px=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_crop_min_height_px"
                ).value
            ),
        ),
        appearance_crop_max_clipping_fraction=max(
            0.0,
            min(
                1.0,
                float(
                    node.get_parameter(
                        "appearance_crop_max_clipping_fraction"
                    ).value
                ),
            ),
        ),
        appearance_crop_min_aspect_ratio=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_crop_min_aspect_ratio"
                ).value
            ),
        ),
        appearance_crop_max_aspect_ratio=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_crop_max_aspect_ratio"
                ).value
            ),
        ),
        appearance_crop_max_overlap_iou_for_memory=max(
            0.0,
            min(
                1.0,
                float(
                    node.get_parameter(
                        "appearance_crop_max_overlap_iou_for_memory"
                    ).value
                ),
            ),
        ),
        appearance_crop_min_centre_distance_norm_for_memory=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_crop_min_centre_distance_norm_for_memory"
                ).value
            ),
        ),
        mars_model_path=str(node.get_parameter("mars_model_path").value),
        mars_batch_size=int(node.get_parameter("mars_batch_size").value),
    )


def build_target_memory_config(node: Any, params: TimMarsRosParams) -> TargetMemoryConfig:
    """Build the pure TIM algorithm config from ROS parameters."""
    return TargetMemoryConfig(
        image_width=params.image_width,
        image_height=params.image_height,
        w_iou=float(node.get_parameter("w_iou").value),
        w_distance=float(node.get_parameter("w_distance").value),
        w_scale=float(node.get_parameter("w_scale").value),
        w_confidence=float(node.get_parameter("w_confidence").value),
        w_id_bonus=float(node.get_parameter("w_id_bonus").value),
        distance_sigma=float(node.get_parameter("distance_sigma").value),
        scale_sigma=float(node.get_parameter("scale_sigma").value),
        stale_quality_decay=float(node.get_parameter("stale_quality_decay").value),
        accept_score_locked=float(node.get_parameter("accept_score_locked").value),
        accept_score_lost=float(node.get_parameter("accept_score_lost").value),
        ambiguity_margin=float(node.get_parameter("ambiguity_margin").value),
        max_uncertain_frames=int(node.get_parameter("max_uncertain_frames").value),
        min_confirm_frames_after_reacquire=int(
            node.get_parameter("min_confirm_frames_after_reacquire").value
        ),
        min_candidate_score=float(node.get_parameter("min_candidate_score").value),
        allow_id_switch_recovery=bool(node.get_parameter("allow_id_switch_recovery").value),
        same_id_accept_relief=float(node.get_parameter("same_id_accept_relief").value),
        id_switch_spatial_gate_enabled=bool(
            node.get_parameter("id_switch_spatial_gate_enabled").value
        ),
        id_switch_min_iou=float(node.get_parameter("id_switch_min_iou").value),
        id_switch_min_distance=float(node.get_parameter("id_switch_min_distance").value),
        id_switch_min_scale=float(node.get_parameter("id_switch_min_scale").value),
        id_switch_min_appearance_similarity=float(
            node.get_parameter(
                "id_switch_min_appearance_similarity"
            ).value
        ),
        short_gap_same_id_priority_enabled=bool(
            node.get_parameter("short_gap_same_id_priority_enabled").value
        ),
        short_gap_same_id_grace_frames=int(
            node.get_parameter("short_gap_same_id_grace_frames").value
        ),
        short_gap_same_id_min_total=float(
            node.get_parameter("short_gap_same_id_min_total").value
        ),
        short_gap_new_id_suppression_enabled=bool(
            node.get_parameter("short_gap_new_id_suppression_enabled").value
        ),
        short_gap_new_id_allow_total=float(
            node.get_parameter("short_gap_new_id_allow_total").value
        ),
        short_gap_group_risk_allow_total=float(
            node.get_parameter("short_gap_group_risk_allow_total").value
        ),
        appearance_enabled=params.appearance_enabled,
        appearance_weight=float(node.get_parameter("appearance_weight").value),
        appearance_min_similarity=float(node.get_parameter("appearance_min_similarity").value),
        appearance_update_alpha=float(node.get_parameter("appearance_update_alpha").value),
        appearance_ambiguous_only=bool(node.get_parameter("appearance_ambiguous_only").value),
        appearance_update_cooldown_after_reacquire_frames=int(
            node.get_parameter(
                "appearance_update_cooldown_after_reacquire_frames"
            ).value
        ),
        appearance_protected_memory_enabled=bool(
            node.get_parameter(
                "appearance_protected_memory_enabled"
            ).value
        ),
        appearance_trusted_gallery_max_entries=max(
            0,
            int(
                node.get_parameter(
                    "appearance_trusted_gallery_max_entries"
                ).value
            ),
        ),
        appearance_gallery_min_anchor_similarity=max(
            0.0,
            float(
                node.get_parameter(
                    "appearance_gallery_min_anchor_similarity"
                ).value
            ),
        ),
        appearance_trusted_lock_frames_before_update=max(
            1,
            int(
                node.get_parameter(
                    "appearance_trusted_lock_frames_before_update"
                ).value
            ),
        ),
        hard_negative_memory_enabled=bool(
            node.get_parameter("hard_negative_memory_enabled").value
        ),
        hard_negative_max_entries=int(node.get_parameter("hard_negative_max_entries").value),
        hard_negative_update_alpha=float(
            node.get_parameter(
                "hard_negative_update_alpha"
            ).value
        ),
        hard_negative_min_candidate_similarity=float(
            node.get_parameter(
                "hard_negative_min_candidate_similarity"
            ).value
        ),
        hard_negative_confirm_observations=max(
            1,
            int(
                node.get_parameter(
                    "hard_negative_confirm_observations"
                ).value
            ),
        ),
        hard_negative_max_positive_similarity=float(
            node.get_parameter(
                "hard_negative_max_positive_similarity"
            ).value
        ),
        hard_negative_reject_similarity=float(
            node.get_parameter("hard_negative_reject_similarity").value
        ),
        hard_negative_reject_margin=float(
            node.get_parameter(
                "hard_negative_reject_margin"
            ).value
        ),
        hard_negative_min_geometry=float(
            node.get_parameter(
                "hard_negative_min_geometry"
            ).value
        ),
        hard_negative_max_age_frames=max(
            0,
            int(
                node.get_parameter(
                    "hard_negative_max_age_frames"
                ).value
            ),
        ),
        hard_negative_decay_policy=str(
            node.get_parameter(
                "hard_negative_decay_policy"
            ).value
        ),
        same_id_hijack_protection_enabled=bool(
            node.get_parameter(
                "same_id_hijack_protection_enabled"
            ).value
        ),
        appearance_conservative_enabled=bool(
            node.get_parameter("appearance_conservative_enabled").value
        ),
        appearance_conservative_require_appearance=bool(
            node.get_parameter("appearance_conservative_require_appearance").value
        ),
        appearance_conservative_min_similarity=float(
            node.get_parameter(
                "appearance_conservative_min_similarity"
            ).value
        ),
        appearance_conservative_margin=float(
            node.get_parameter("appearance_conservative_margin").value
        ),
        rank_aware_reacquisition_enabled=bool(
            node.get_parameter("rank_aware_reacquisition_enabled").value
        ),
        rank_aware_lost_min_total=float(node.get_parameter("rank_aware_lost_min_total").value),
        rank_aware_lost_min_geom=float(node.get_parameter("rank_aware_lost_min_geom").value),
        rank_aware_lost_min_app=float(node.get_parameter("rank_aware_lost_min_app").value),
        rank_aware_lost_app_margin=float(node.get_parameter("rank_aware_lost_app_margin").value),
        rank_aware_confirm_frames=int(node.get_parameter("rank_aware_confirm_frames").value),
        candidate_belief_enabled=bool(node.get_parameter("candidate_belief_enabled").value),
        candidate_belief_min_score=float(node.get_parameter("candidate_belief_min_score").value),
        candidate_belief_confirm_frames=int(
            node.get_parameter("candidate_belief_confirm_frames").value
        ),
        absence_recovery_enabled=bool(node.get_parameter("absence_recovery_enabled").value),
        absence_after_missed_frames=int(node.get_parameter("absence_after_missed_frames").value),
        absence_new_id_requires_appearance=bool(
            node.get_parameter("absence_new_id_requires_appearance").value
        ),
        absence_min_total=float(node.get_parameter("absence_min_total").value),
        absence_min_distance=float(node.get_parameter("absence_min_distance").value),
        absence_min_scale=float(node.get_parameter("absence_min_scale").value),
        absence_min_similarity=float(node.get_parameter("absence_min_similarity").value),
        absence_appearance_margin=float(node.get_parameter("absence_appearance_margin").value),
        absence_confirm_frames=int(node.get_parameter("absence_confirm_frames").value),
    )
