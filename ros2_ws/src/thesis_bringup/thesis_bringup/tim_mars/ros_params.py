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

    node.declare_parameter("tracks_topic", "/tracks")
    node.declare_parameter("target_topic", "/target_memory_mars")
    node.declare_parameter("status_topic", "/target_memory_mars/status")
    node.declare_parameter("select_topic", "/target_memory_mars/select")
    node.declare_parameter("clear_topic", "/target_memory_mars/clear")
    node.declare_parameter("mirror_target_topic", "/target")
    node.declare_parameter("mirror_raw_target_selection", True)

    node.declare_parameter("image_width", 640.0)
    node.declare_parameter("image_height", 640.0)
    node.declare_parameter("tracks_are_normalized", False)
    node.declare_parameter("selected_track_id", 0)
    node.declare_parameter("auto_select_largest", False)
    node.declare_parameter("zero_id_when_not_visible", True)

    node.declare_parameter("accept_score_locked", 0.52)
    node.declare_parameter("accept_score_lost", 0.60)
    node.declare_parameter("ambiguity_margin", 0.07)
    node.declare_parameter("max_uncertain_frames", 6)
    node.declare_parameter("max_lost_frames", 30)
    node.declare_parameter("min_candidate_score", 0.10)
    node.declare_parameter("allow_id_switch_recovery", True)
    node.declare_parameter("id_switch_spatial_gate_enabled", False)
    node.declare_parameter("id_switch_min_iou", 0.05)
    node.declare_parameter("id_switch_min_distance", 0.35)
    node.declare_parameter("id_switch_min_scale", 0.35)
    node.declare_parameter("hold_last_on_reject_enabled", False)
    node.declare_parameter("hold_last_on_reject_frames", 0)

    # Appearance extraction / ReID.
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
    node.declare_parameter("appearance_challenge_enabled", False)
    node.declare_parameter("appearance_challenge_min_similarity", 0.50)
    node.declare_parameter("appearance_challenge_margin", 0.20)
    node.declare_parameter("appearance_challenge_min_total", 0.45)
    node.declare_parameter("same_id_appearance_ambiguity_enabled", False)
    node.declare_parameter("same_id_appearance_ambiguity_min_similarity", 0.70)
    node.declare_parameter("same_id_appearance_ambiguity_margin", 0.05)
    node.declare_parameter("same_id_appearance_ambiguity_min_challenger_total", 0.35)
    node.declare_parameter("same_id_appearance_ambiguity_min_challenger_distance", 0.20)
    node.declare_parameter("same_id_appearance_ambiguity_min_challenger_scale", 0.30)
    node.declare_parameter("hard_negative_memory_enabled", False)
    node.declare_parameter("hard_negative_max_entries", 8)
    node.declare_parameter("hard_negative_update_alpha", 0.20)
    node.declare_parameter("hard_negative_min_candidate_similarity", 0.70)
    node.declare_parameter("hard_negative_reject_similarity", 0.80)
    node.declare_parameter("hard_negative_reject_margin", 0.08)
    node.declare_parameter("hard_negative_min_geometry", 0.20)
    node.declare_parameter("appearance_conservative_enabled", False)
    node.declare_parameter("appearance_conservative_require_appearance", False)
    node.declare_parameter("appearance_conservative_min_similarity", 0.65)
    node.declare_parameter("appearance_conservative_margin", 0.25)

    node.declare_parameter(
        "mars_model_path",
        "/home/francisco/Desktop/Thesis-Code/models/reid/mars-small128.pb",
    )
    node.declare_parameter("mars_batch_size", 32)

    node.declare_parameter("rank_aware_reacquisition_enabled", True)
    node.declare_parameter("rank_aware_lost_min_total", 0.40)
    node.declare_parameter("rank_aware_lost_min_geom", 0.10)
    node.declare_parameter("rank_aware_lost_min_app", 0.05)
    node.declare_parameter("rank_aware_lost_app_margin", 0.03)
    node.declare_parameter("rank_aware_confirm_frames", 1)
    node.declare_parameter("rank_aware_missing_ttl_frames", 8)

    node.declare_parameter("active_reselection_enabled", False)
    node.declare_parameter("active_reselection_min_total", 0.20)
    node.declare_parameter("active_reselection_min_geometry", 0.05)
    node.declare_parameter("active_reselection_min_app", 0.82)
    node.declare_parameter("active_reselection_app_margin", 0.10)
    node.declare_parameter("active_reselection_confirm_frames", 2)
    node.declare_parameter("active_reselection_reject_hard_negative", True)

    node.declare_parameter("absence_recovery_enabled", False)
    node.declare_parameter("absence_after_missed_frames", 6)
    node.declare_parameter("absence_new_id_requires_appearance", True)
    node.declare_parameter("absence_min_total", 0.45)
    node.declare_parameter("absence_min_distance", 0.25)
    node.declare_parameter("absence_min_scale", 0.35)
    node.declare_parameter("absence_min_similarity", 0.65)
    node.declare_parameter("absence_appearance_margin", 0.20)
    node.declare_parameter("absence_confirm_frames", 3)

    node.declare_parameter("tim_policy", "legacy")
    node.declare_parameter("v4a_same_id_ambiguity_freezes_memory", True)
    node.declare_parameter("v4a_same_id_min_geometry_to_publish", 0.45)

    node.declare_parameter("old_id_distrust_enabled", False)
    node.declare_parameter("old_id_distrust_min_challenger_app", 0.55)
    node.declare_parameter("old_id_distrust_min_challenger_geometry", 0.05)
    node.declare_parameter("old_id_distrust_min_old_id_app_margin", 0.15)
    node.declare_parameter("old_id_distrust_min_candidates", 2)
    node.declare_parameter("old_id_distrust_after_missed_frames", 3)
    node.declare_parameter("old_id_distrust_max_total_gap", 0.12)
    node.declare_parameter("old_id_handoff_enabled", False)
    node.declare_parameter("old_id_handoff_min_app", 0.84)
    node.declare_parameter("old_id_handoff_min_geometry", 0.90)
    node.declare_parameter("old_id_handoff_min_total", 0.55)
    node.declare_parameter("old_id_handoff_max_total_gap", 0.12)
    node.declare_parameter("old_id_handoff_confirm_frames", 3)
    node.declare_parameter("old_id_handoff_reject_hard_negative", False)
    node.declare_parameter("old_id_reacquire_block_enabled", False)
    node.declare_parameter("old_id_reacquire_block_frames", 60)
    node.declare_parameter("old_id_reacquire_block_after_missed_frames", 3)


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
        accept_score_locked=float(node.get_parameter("accept_score_locked").value),
        accept_score_lost=float(node.get_parameter("accept_score_lost").value),
        ambiguity_margin=float(node.get_parameter("ambiguity_margin").value),
        max_uncertain_frames=int(node.get_parameter("max_uncertain_frames").value),
        max_lost_frames=int(node.get_parameter("max_lost_frames").value),
        min_candidate_score=float(node.get_parameter("min_candidate_score").value),
        allow_id_switch_recovery=bool(node.get_parameter("allow_id_switch_recovery").value),
        id_switch_spatial_gate_enabled=bool(node.get_parameter("id_switch_spatial_gate_enabled").value),
        id_switch_min_iou=float(node.get_parameter("id_switch_min_iou").value),
        id_switch_min_distance=float(node.get_parameter("id_switch_min_distance").value),
        id_switch_min_scale=float(node.get_parameter("id_switch_min_scale").value),
        hold_last_on_reject_enabled=bool(node.get_parameter("hold_last_on_reject_enabled").value),
        hold_last_on_reject_frames=int(node.get_parameter("hold_last_on_reject_frames").value),
        appearance_enabled=params.appearance_enabled,
        appearance_weight=float(node.get_parameter("appearance_weight").value),
        appearance_min_similarity=float(node.get_parameter("appearance_min_similarity").value),
        appearance_update_alpha=float(node.get_parameter("appearance_update_alpha").value),
        appearance_ambiguous_only=bool(node.get_parameter("appearance_ambiguous_only").value),
        appearance_update_cooldown_after_reacquire_frames=int(
            node.get_parameter("appearance_update_cooldown_after_reacquire_frames").value
        ),
        appearance_challenge_enabled=bool(node.get_parameter("appearance_challenge_enabled").value),
        appearance_challenge_min_similarity=float(node.get_parameter("appearance_challenge_min_similarity").value),
        appearance_challenge_margin=float(node.get_parameter("appearance_challenge_margin").value),
        appearance_challenge_min_total=float(node.get_parameter("appearance_challenge_min_total").value),
        same_id_appearance_ambiguity_enabled=bool(node.get_parameter("same_id_appearance_ambiguity_enabled").value),
        same_id_appearance_ambiguity_min_similarity=float(
            node.get_parameter("same_id_appearance_ambiguity_min_similarity").value
        ),
        same_id_appearance_ambiguity_margin=float(node.get_parameter("same_id_appearance_ambiguity_margin").value),
        same_id_appearance_ambiguity_min_challenger_total=float(
            node.get_parameter("same_id_appearance_ambiguity_min_challenger_total").value
        ),
        same_id_appearance_ambiguity_min_challenger_distance=float(
            node.get_parameter("same_id_appearance_ambiguity_min_challenger_distance").value
        ),
        same_id_appearance_ambiguity_min_challenger_scale=float(
            node.get_parameter("same_id_appearance_ambiguity_min_challenger_scale").value
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
        active_reselection_enabled=bool(node.get_parameter("active_reselection_enabled").value),
        active_reselection_min_total=float(node.get_parameter("active_reselection_min_total").value),
        active_reselection_min_geometry=float(node.get_parameter("active_reselection_min_geometry").value),
        active_reselection_min_app=float(node.get_parameter("active_reselection_min_app").value),
        active_reselection_app_margin=float(node.get_parameter("active_reselection_app_margin").value),
        active_reselection_confirm_frames=int(node.get_parameter("active_reselection_confirm_frames").value),
        active_reselection_reject_hard_negative=bool(node.get_parameter("active_reselection_reject_hard_negative").value),
        absence_recovery_enabled=bool(node.get_parameter("absence_recovery_enabled").value),
        absence_after_missed_frames=int(node.get_parameter("absence_after_missed_frames").value),
        absence_new_id_requires_appearance=bool(node.get_parameter("absence_new_id_requires_appearance").value),
        absence_min_total=float(node.get_parameter("absence_min_total").value),
        absence_min_distance=float(node.get_parameter("absence_min_distance").value),
        absence_min_scale=float(node.get_parameter("absence_min_scale").value),
        absence_min_similarity=float(node.get_parameter("absence_min_similarity").value),
        absence_appearance_margin=float(node.get_parameter("absence_appearance_margin").value),
        absence_confirm_frames=int(node.get_parameter("absence_confirm_frames").value),
        tim_policy=str(node.get_parameter("tim_policy").value),
        v4a_same_id_ambiguity_freezes_memory=bool(node.get_parameter("v4a_same_id_ambiguity_freezes_memory").value),
        v4a_same_id_min_geometry_to_publish=float(node.get_parameter("v4a_same_id_min_geometry_to_publish").value),
        old_id_distrust_enabled=bool(node.get_parameter("old_id_distrust_enabled").value),
        old_id_distrust_min_challenger_app=float(node.get_parameter("old_id_distrust_min_challenger_app").value),
        old_id_distrust_min_challenger_geometry=float(node.get_parameter("old_id_distrust_min_challenger_geometry").value),
        old_id_distrust_min_old_id_app_margin=float(node.get_parameter("old_id_distrust_min_old_id_app_margin").value),
        old_id_distrust_min_candidates=int(node.get_parameter("old_id_distrust_min_candidates").value),
        old_id_distrust_after_missed_frames=int(node.get_parameter("old_id_distrust_after_missed_frames").value),
        old_id_distrust_max_total_gap=float(node.get_parameter("old_id_distrust_max_total_gap").value),
        old_id_handoff_enabled=bool(node.get_parameter("old_id_handoff_enabled").value),
        old_id_handoff_min_app=float(node.get_parameter("old_id_handoff_min_app").value),
        old_id_handoff_min_geometry=float(node.get_parameter("old_id_handoff_min_geometry").value),
        old_id_handoff_min_total=float(node.get_parameter("old_id_handoff_min_total").value),
        old_id_handoff_max_total_gap=float(node.get_parameter("old_id_handoff_max_total_gap").value),
        old_id_handoff_confirm_frames=int(node.get_parameter("old_id_handoff_confirm_frames").value),
        old_id_handoff_reject_hard_negative=bool(node.get_parameter("old_id_handoff_reject_hard_negative").value),
        old_id_reacquire_block_enabled=bool(node.get_parameter("old_id_reacquire_block_enabled").value),
        old_id_reacquire_block_frames=int(node.get_parameter("old_id_reacquire_block_frames").value),
        old_id_reacquire_block_after_missed_frames=int(
            node.get_parameter("old_id_reacquire_block_after_missed_frames").value
        ),
    )
