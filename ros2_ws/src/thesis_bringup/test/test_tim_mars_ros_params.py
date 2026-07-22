from pathlib import Path

from thesis_bringup.tim_mars.ros_params import (
    build_target_memory_config,
    declare_tim_mars_parameters,
    read_tim_mars_ros_params,
)
import yaml


class _Param:
    def __init__(self, value):
        self.value = value


class _FakeNode:
    def __init__(self):
        self.values = {}

    def declare_parameter(self, name, value):
        self.values[name] = value

    def get_parameter(self, name):
        return _Param(self.values[name])


def test_tim_mars_ros_params_declares_expected_interface():
    node = _FakeNode()

    declare_tim_mars_parameters(node)

    assert len(node.values) == 96
    assert node.values["tracks_topic"] == "/tracks"
    assert node.values["target_topic"] == "/target_memory_mars"
    assert node.values["appearance_enabled"] is True
    assert (
        node.values[
            "id_switch_min_appearance_similarity"
        ]
        == 0.0
    )
    assert (
        node.values["appearance_cache_max_centre_distance_norm"]
        == 0.25
    )
    assert node.values["appearance_cache_min_scale_ratio"] == 0.25
    assert node.values["appearance_crop_min_width_px"] == 12.0
    assert node.values["appearance_crop_min_height_px"] == 24.0
    assert (
        node.values["appearance_crop_max_clipping_fraction"]
        == 0.10
    )
    assert (
        node.values[
            "appearance_crop_max_overlap_iou_for_memory"
        ]
        == 0.10
    )
    assert (
        node.values[
            "appearance_crop_min_centre_distance_norm_for_memory"
        ]
        == 0.04
    )
    assert (
        node.values["appearance_protected_memory_enabled"]
        is False
    )
    assert (
        node.values["appearance_trusted_gallery_max_entries"]
        == 4
    )
    assert (
        node.values[
            "appearance_gallery_min_anchor_similarity"
        ]
        == 0.0
    )
    assert (
        node.values[
            "appearance_trusted_lock_frames_before_update"
        ]
        == 2
    )
    assert (
        node.values["hard_negative_confirm_observations"]
        == 2
    )
    assert (
        node.values["hard_negative_max_positive_similarity"]
        == 1.01
    )
    assert node.values["rank_aware_reacquisition_enabled"] is True
    assert node.values["candidate_belief_enabled"] is False
    assert node.values["candidate_belief_min_score"] == 0.45
    assert node.values["candidate_belief_confirm_frames"] == 2
    assert node.values["absence_recovery_enabled"] is False


def test_tim_mars_ros_params_builds_config_from_ros_values():
    node = _FakeNode()
    declare_tim_mars_parameters(node)

    node.values["image_width"] = 1280.0
    node.values["image_height"] = 720.0
    node.values["appearance_enabled"] = True
    node.values[
        "id_switch_min_appearance_similarity"
    ] = 0.78
    node.values["appearance_cache_max_centre_distance_norm"] = 0.40
    node.values["appearance_cache_min_scale_ratio"] = 0.30
    node.values["appearance_crop_min_width_px"] = 16.0
    node.values["appearance_crop_min_height_px"] = 32.0
    node.values["appearance_crop_max_clipping_fraction"] = 0.20
    node.values["appearance_crop_min_aspect_ratio"] = 0.25
    node.values["appearance_crop_max_aspect_ratio"] = 0.90
    node.values[
        "appearance_crop_max_overlap_iou_for_memory"
    ] = 0.15
    node.values[
        "appearance_crop_min_centre_distance_norm_for_memory"
    ] = 0.05
    node.values["appearance_protected_memory_enabled"] = True
    node.values["appearance_trusted_gallery_max_entries"] = 6
    node.values[
        "appearance_gallery_min_anchor_similarity"
    ] = 0.74
    node.values[
        "appearance_trusted_lock_frames_before_update"
    ] = 3
    node.values["hard_negative_confirm_observations"] = 4
    node.values[
        "hard_negative_max_positive_similarity"
    ] = 0.93
    node.values["rank_aware_reacquisition_enabled"] = True
    node.values["rank_aware_confirm_frames"] = 4
    node.values["candidate_belief_enabled"] = True
    node.values["candidate_belief_min_score"] = 0.33
    node.values["candidate_belief_confirm_frames"] = 5
    node.values["absence_recovery_enabled"] = True
    node.values["absence_confirm_frames"] = 5

    params = read_tim_mars_ros_params(node)
    cfg = build_target_memory_config(node, params)

    assert params.image_width == 1280.0
    assert params.image_height == 720.0
    assert params.appearance_enabled is True
    assert (
        params.appearance_cache_max_centre_distance_norm
        == 0.40
    )
    assert params.appearance_cache_min_scale_ratio == 0.30
    assert params.appearance_crop_min_width_px == 16.0
    assert params.appearance_crop_min_height_px == 32.0
    assert (
        params.appearance_crop_max_clipping_fraction
        == 0.20
    )
    assert params.appearance_crop_min_aspect_ratio == 0.25
    assert params.appearance_crop_max_aspect_ratio == 0.90
    assert (
        params.appearance_crop_max_overlap_iou_for_memory
        == 0.15
    )
    assert (
        params
        .appearance_crop_min_centre_distance_norm_for_memory
        == 0.05
    )

    assert cfg.image_width == 1280.0
    assert cfg.image_height == 720.0
    assert cfg.appearance_enabled is True
    assert (
        cfg.id_switch_min_appearance_similarity
        == 0.78
    )
    assert cfg.appearance_protected_memory_enabled is True
    assert cfg.appearance_trusted_gallery_max_entries == 6
    assert (
        cfg.appearance_gallery_min_anchor_similarity
        == 0.74
    )
    assert (
        cfg.appearance_trusted_lock_frames_before_update
        == 3
    )
    assert cfg.hard_negative_confirm_observations == 4
    assert (
        cfg.hard_negative_max_positive_similarity
        == 0.93
    )
    assert cfg.rank_aware_reacquisition_enabled is True
    assert cfg.rank_aware_confirm_frames == 4
    assert cfg.candidate_belief_enabled is True
    assert cfg.candidate_belief_min_score == 0.33
    assert cfg.candidate_belief_confirm_frames == 5
    assert cfg.absence_recovery_enabled is True
    assert cfg.absence_confirm_frames == 5


def test_canonical_yaml_defines_all_active_algorithm_parameters():
    node = _FakeNode()
    declare_tim_mars_parameters(node)

    config_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "tim_mars_canonical.yaml"
    )

    with config_path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)

    canonical = document["target_memory_mars_node"]["ros__parameters"]

    expected_active_keys = {
        "w_iou",
        "w_distance",
        "w_scale",
        "w_confidence",
        "w_id_bonus",
        "distance_sigma",
        "scale_sigma",
        "stale_quality_decay",
        "accept_score_locked",
        "accept_score_lost",
        "ambiguity_margin",
        "max_uncertain_frames",
        "min_confirm_frames_after_reacquire",
        "min_candidate_score",
        "allow_id_switch_recovery",
        "same_id_accept_relief",
        "id_switch_spatial_gate_enabled",
        "id_switch_min_iou",
        "id_switch_min_distance",
        "id_switch_min_scale",
        "id_switch_min_appearance_similarity",
        "short_gap_same_id_priority_enabled",
        "short_gap_same_id_grace_frames",
        "short_gap_same_id_min_total",
        "short_gap_new_id_suppression_enabled",
        "short_gap_new_id_allow_total",
        "short_gap_group_risk_allow_total",
        "appearance_protected_memory_enabled",
        "appearance_trusted_gallery_max_entries",
        "appearance_gallery_min_anchor_similarity",
        "appearance_trusted_lock_frames_before_update",
        "hard_negative_confirm_observations",
        "hard_negative_max_positive_similarity",
    }

    assert expected_active_keys <= canonical.keys()
    assert (
        canonical["appearance_protected_memory_enabled"]
        is True
    )
    assert (
        canonical[
            "appearance_gallery_min_anchor_similarity"
        ]
        == 0.75
    )

    for name, value in canonical.items():
        assert name in node.values
        node.values[name] = value

    params = read_tim_mars_ros_params(node)
    cfg = build_target_memory_config(node, params)

    assert (
        params.appearance_cache_max_centre_distance_norm
        == canonical[
            "appearance_cache_max_centre_distance_norm"
        ]
    )
    assert (
        params.appearance_cache_min_scale_ratio
        == canonical["appearance_cache_min_scale_ratio"]
    )
    assert (
        params.appearance_crop_min_width_px
        == canonical["appearance_crop_min_width_px"]
    )
    assert (
        params.appearance_crop_min_height_px
        == canonical["appearance_crop_min_height_px"]
    )
    assert (
        params.appearance_crop_max_clipping_fraction
        == canonical[
            "appearance_crop_max_clipping_fraction"
        ]
    )
    assert (
        params.appearance_crop_min_aspect_ratio
        == canonical[
            "appearance_crop_min_aspect_ratio"
        ]
    )
    assert (
        params.appearance_crop_max_aspect_ratio
        == canonical[
            "appearance_crop_max_aspect_ratio"
        ]
    )
    assert (
        params.appearance_crop_max_overlap_iou_for_memory
        == canonical[
            "appearance_crop_max_overlap_iou_for_memory"
        ]
    )
    assert (
        params
        .appearance_crop_min_centre_distance_norm_for_memory
        == canonical[
            "appearance_crop_min_centre_distance_norm_for_memory"
        ]
    )

    for name in expected_active_keys:
        assert getattr(cfg, name) == canonical[name]
