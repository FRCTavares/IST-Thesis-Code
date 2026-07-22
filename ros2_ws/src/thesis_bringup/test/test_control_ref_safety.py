from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from thesis_bringup.control.control_ref_node import (
    compute_control_command,
    ControlRefNode,
)


CONTROL_SOURCE = Path(
    "ros2_ws/src/thesis_bringup/"
    "thesis_bringup/control/control_ref_node.py"
)

BASE_COMMAND = {
    "img_w": 640.0,
    "img_h": 640.0,
    "desired_h_norm": 0.25,
    "yaw_kp": 0.4,
    "forward_kp": 0.4,
    "lateral_kp": 0.0,
    "deadband_ex": 0.03,
    "deadband_h": 0.02,
    "max_yaw_z": 0.10,
    "max_vx": 0.10,
    "max_vy": 0.10,
    "use_lateral": False,
    "invert_yaw": False,
    "invert_forward": False,
    "invert_lateral": False,
}


def _commands(*, cx: float, h: float):
    result = compute_control_command(
        cx=cx,
        h=h,
        **BASE_COMMAND,
    )
    return result[:3]


def _valid_target():
    return SimpleNamespace(
        id=1,
        cx=320.0,
        cy=320.0,
        w=80.0,
        h=160.0,
        score=1.0,
        quality=1.0,
    )


def _validation_context(age_s: float):
    context = SimpleNamespace(
        img_w=640.0,
        img_h=640.0,
        min_score_valid=0.10,
        min_quality_valid=0.05,
        stale_timeout_s=0.20,
    )
    context.target_age_s = lambda: age_s
    return context


def test_centred_target_has_zero_yaw_and_forward_command():
    vx, vy, yaw_z = _commands(cx=320.0, h=160.0)

    assert vx == pytest.approx(0.0)
    assert vy == pytest.approx(0.0)
    assert yaw_z == pytest.approx(0.0)


def test_target_left_produces_negative_yaw():
    _, _, yaw_z = _commands(cx=0.0, h=160.0)

    assert yaw_z == pytest.approx(-0.10)


def test_target_right_produces_positive_yaw():
    _, _, yaw_z = _commands(cx=640.0, h=160.0)

    assert yaw_z == pytest.approx(0.10)


def test_far_target_produces_positive_forward_command():
    vx, _, _ = _commands(cx=320.0, h=32.0)

    assert vx > 0.0


def test_near_target_produces_negative_forward_command():
    vx, _, _ = _commands(cx=320.0, h=320.0)

    assert vx < 0.0


def test_commands_are_saturated():
    vx, _, yaw_z = _commands(cx=640.0, h=640.0)

    assert vx == pytest.approx(-0.10)
    assert yaw_z == pytest.approx(0.10)


def test_slew_rate_limits_each_command_step():
    assert ControlRefNode.slew(None, 0.10, 0.00, 0.03) == pytest.approx(
        0.03
    )
    assert ControlRefNode.slew(None, -0.10, 0.00, 0.03) == pytest.approx(
        -0.03
    )


def test_stale_target_is_invalid():
    context = _validation_context(age_s=1.0)
    reason = ControlRefNode.target_invalid_reason(
        context,
        _valid_target(),
    )

    assert reason is not None
    assert reason.startswith("stale_target")


def test_zero_id_target_is_invalid():
    context = _validation_context(age_s=0.0)
    target = _valid_target()
    target.id = 0

    assert ControlRefNode.target_invalid_reason(
        context,
        target,
    ) == "id_zero"


def test_fresh_valid_target_has_no_invalid_reason():
    context = _validation_context(age_s=0.05)

    assert ControlRefNode.target_invalid_reason(
        context,
        _valid_target(),
    ) is None


def test_invalid_and_missing_target_paths_publish_zero():
    tree = ast.parse(CONTROL_SOURCE.read_text(encoding="utf-8"))

    on_timer = next(
        node
        for class_node in tree.body
        if isinstance(class_node, ast.ClassDef)
        and class_node.name == "ControlRefNode"
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "on_timer"
    )

    zero_calls = [
        node
        for node in ast.walk(on_timer)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "publish_zero"
    ]

    assert len(zero_calls) >= 3
