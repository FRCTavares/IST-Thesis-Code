from pathlib import Path

import yaml

from thesis_bringup.tim_mars.ros_params import (
    build_target_memory_config,
    declare_tim_mars_parameters,
    read_tim_mars_ros_params,
)


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

    assert len(node.values) == 80
    assert node.values["tracks_topic"] == "/tracks"
    assert node.values["target_topic"] == "/target_memory_mars"
    assert node.values["appearance_enabled"] is True
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

    assert cfg.image_width == 1280.0
    assert cfg.image_height == 720.0
    assert cfg.appearance_enabled is True
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
        "short_gap_same_id_priority_enabled",
        "short_gap_same_id_grace_frames",
        "short_gap_same_id_min_total",
        "short_gap_new_id_suppression_enabled",
        "short_gap_new_id_allow_total",
        "short_gap_group_risk_allow_total",
    }

    assert expected_active_keys <= canonical.keys()

    for name, value in canonical.items():
        assert name in node.values
        node.values[name] = value

    params = read_tim_mars_ros_params(node)
    cfg = build_target_memory_config(node, params)

    for name in expected_active_keys:
        assert getattr(cfg, name) == canonical[name]
