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

    assert len(node.values) == 63
    assert node.values["tracks_topic"] == "/tracks"
    assert node.values["target_topic"] == "/target_memory_mars"
    assert node.values["appearance_enabled"] is True
    assert node.values["rank_aware_reacquisition_enabled"] is True
    assert node.values["absence_recovery_enabled"] is False


def test_tim_mars_ros_params_builds_config_from_ros_values():
    node = _FakeNode()
    declare_tim_mars_parameters(node)

    node.values["image_width"] = 1280.0
    node.values["image_height"] = 720.0
    node.values["appearance_enabled"] = True
    node.values["rank_aware_reacquisition_enabled"] = True
    node.values["rank_aware_confirm_frames"] = 4
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
    assert cfg.absence_recovery_enabled is True
    assert cfg.absence_confirm_frames == 5
