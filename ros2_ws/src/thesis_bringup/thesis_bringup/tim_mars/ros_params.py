"""ROS parameter declaration and configuration bridge for TIM-MARS.

This module declares the ROS parameter surface of target_memory_mars_node.py,
reads parameter values from rclpy, and builds the pure TargetMemoryConfig used
by the selected-target memory state machine.

It is the boundary between ROS configuration and pure TIM-MARS algorithm logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    appearance_enabled: bool
    appearance_image_topic: str
    appearance_max_image_age_ms: float
    appearance_compute_min_interval_ms: float
    appearance_cache_ttl_ms: float

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
    node.declare_parameter("max_lost_frames", 30)
    node.declare_parameter("min_confirm_frames_after_reacquire", 1)
    node.declare_parameter("min_candidate_score", 0.10)

    # Controlled ID-switch recovery and short-gap protection.
    node.declare_parameter("allow_id_switch_recovery", True)
    node.declare_parameter("same_id_accept_relief", 0.08)
    node.declare_parameter("id_switch_spatial_gate_enabled", False)
    node.declare_parameter("id_switch_min_iou", 0.05)
    node.declare_parameter("id_switch_min_distance", 0.35)
    node.declare_parameter("id_switch_min_scale", 0.35)
    node.declare_parameter("short_gap_same_id_priority_enabled", True)
    node.declare_parameter("short_gap_same_id_grace_frames", 8)
    node.declare_parameter("short_gap_same_id_min_total", 0.30)
    node.declare_parameter("short_gap_new_id_suppression_enabled", True)
    node.declare_parameter("short_gap_new_id_allow_total", 0.70)
    node.declare_parameter("short_gap_group_risk_allow_total", 0.85)

    # Appearance extraction, scoring, and positive-memory update policy.
    node.declare_parameter("appearance_enabled", True)
    node.declare_parameter("appearance_image_topic", "/camera/dashboard")
    node.declare_parameter("appearance_max_image_age_ms", 250.0)
    node.declare_parameter("appearance_compute_min_interval_ms", 250.0)
    node.declare_parameter("appearance_cache_ttl_ms", 750.0)
    node.declare_parameter("appearance_weight", 0.12)
    node.declare_parameter("appearance_min_similarity", 0.35)
    node.declare_parameter("appearance_update_alpha", 0.10)
    node.declare_parameter("appearance_ambiguous_only", True)
    node.declare_parameter("appearance_update_cooldown_after_reacquire_frames", 0)
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
    node.declare_parameter("hard_negative_reject_similarity", 0.80)
    node.declare_parameter("hard_negative_reject_margin", 0.03)
    node.declare_parameter("hard_negative_min_geometry", 0.20)

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
    node.declare_parameter("rank_aware_missing_ttl_frames", 8)
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
        appearance_enabled=bool(node.get_parameter("appearance_enabled").value),
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
        max_lost_frames=int(node.get_parameter("max_lost_frames").value),
        min_confirm_frames_after_reacquire=int(
            node.get_parameter("min_confirm_frames_after_reacquire").value
        ),
        min_candidate_score=float(node.get_parameter("min_candidate_score").value),
        allow_id_switch_recovery=bool(node.get_parameter("allow_id_switch_recovery").value),
        same_id_accept_relief=float(node.get_parameter("same_id_accept_relief").value),
        id_switch_spatial_gate_enabled=bool(node.get_parameter("id_switch_spatial_gate_enabled").value),
        id_switch_min_iou=float(node.get_parameter("id_switch_min_iou").value),
        id_switch_min_distance=float(node.get_parameter("id_switch_min_distance").value),
        id_switch_min_scale=float(node.get_parameter("id_switch_min_scale").value),
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
            node.get_parameter("appearance_update_cooldown_after_reacquire_frames").value
        ),
        hard_negative_memory_enabled=bool(node.get_parameter("hard_negative_memory_enabled").value),
        hard_negative_max_entries=int(node.get_parameter("hard_negative_max_entries").value),
        hard_negative_update_alpha=float(node.get_parameter("hard_negative_update_alpha").value),
        hard_negative_min_candidate_similarity=float(node.get_parameter("hard_negative_min_candidate_similarity").value),
        hard_negative_reject_similarity=float(node.get_parameter("hard_negative_reject_similarity").value),
        hard_negative_reject_margin=float(node.get_parameter("hard_negative_reject_margin").value),
        hard_negative_min_geometry=float(node.get_parameter("hard_negative_min_geometry").value),
        appearance_conservative_enabled=bool(node.get_parameter("appearance_conservative_enabled").value),
        appearance_conservative_require_appearance=bool(
            node.get_parameter("appearance_conservative_require_appearance").value
        ),
        appearance_conservative_min_similarity=float(node.get_parameter("appearance_conservative_min_similarity").value),
        appearance_conservative_margin=float(node.get_parameter("appearance_conservative_margin").value),
        rank_aware_reacquisition_enabled=bool(node.get_parameter("rank_aware_reacquisition_enabled").value),
        rank_aware_lost_min_total=float(node.get_parameter("rank_aware_lost_min_total").value),
        rank_aware_lost_min_geom=float(node.get_parameter("rank_aware_lost_min_geom").value),
        rank_aware_lost_min_app=float(node.get_parameter("rank_aware_lost_min_app").value),
        rank_aware_lost_app_margin=float(node.get_parameter("rank_aware_lost_app_margin").value),
        rank_aware_confirm_frames=int(node.get_parameter("rank_aware_confirm_frames").value),
        rank_aware_missing_ttl_frames=int(node.get_parameter("rank_aware_missing_ttl_frames").value),
        candidate_belief_enabled=bool(node.get_parameter("candidate_belief_enabled").value),
        candidate_belief_min_score=float(node.get_parameter("candidate_belief_min_score").value),
        candidate_belief_confirm_frames=int(node.get_parameter("candidate_belief_confirm_frames").value),
        absence_recovery_enabled=bool(node.get_parameter("absence_recovery_enabled").value),
        absence_after_missed_frames=int(node.get_parameter("absence_after_missed_frames").value),
        absence_new_id_requires_appearance=bool(node.get_parameter("absence_new_id_requires_appearance").value),
        absence_min_total=float(node.get_parameter("absence_min_total").value),
        absence_min_distance=float(node.get_parameter("absence_min_distance").value),
        absence_min_scale=float(node.get_parameter("absence_min_scale").value),
        absence_min_similarity=float(node.get_parameter("absence_min_similarity").value),
        absence_appearance_margin=float(node.get_parameter("absence_appearance_margin").value),
        absence_confirm_frames=int(node.get_parameter("absence_confirm_frames").value),
    )
