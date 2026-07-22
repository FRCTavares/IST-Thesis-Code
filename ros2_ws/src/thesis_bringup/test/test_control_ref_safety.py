from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from thesis_bringup.control.control_ref_node import (
    compute_control_command,
    ControlRefNode,
)


CONTROL_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "control"
    / "control_ref_node.py"
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
        src_stamp_ns=9_950_000_000,
        id=1,
        cx=320.0,
        cy=320.0,
        w=80.0,
        h=160.0,
        score=1.0,
        quality=1.0,
    )


def _validation_context(
    receive_age_s: float,
    *,
    source_age_s: float = 0.05,
    order_status=None,
):
    now_ns = 10_000_000_000
    context = SimpleNamespace(
        img_w=640.0,
        img_h=640.0,
        min_score_valid=0.10,
        min_quality_valid=0.05,
        stale_timeout_s=0.20,
        future_tolerance_s=0.05,
        last_target_rx_time=SimpleNamespace(
            nanoseconds=now_ns - int(receive_age_s * 1e9)
        ),
        last_target_source_order_status=order_status,
    )
    context.get_clock = lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=now_ns)
    )
    context.target_age_s = lambda: receive_age_s
    context.target_freshness_result = lambda target: (
        ControlRefNode.target_freshness_result(context, target)
    )
    context.source_stamp_ns = now_ns - int(source_age_s * 1e9)
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
    context = _validation_context(receive_age_s=1.0)
    target = _valid_target()
    target.src_stamp_ns = context.source_stamp_ns
    reason = ControlRefNode.target_invalid_reason(
        context,
        target,
    )

    assert reason is not None
    assert reason.startswith("freshness_stale_receive")


def test_old_source_is_invalid_even_when_message_arrived_recently():
    context = _validation_context(
        receive_age_s=0.01,
        source_age_s=1.0,
    )
    target = _valid_target()
    target.src_stamp_ns = context.source_stamp_ns

    reason = ControlRefNode.target_invalid_reason(context, target)

    assert reason is not None
    assert reason.startswith("freshness_stale_source")


@pytest.mark.parametrize(
    "order_status",
    ["duplicate_source", "non_monotonic_source"],
)
def test_replayed_or_non_monotonic_source_is_invalid(order_status):
    context = _validation_context(
        receive_age_s=0.01,
        order_status=order_status,
    )
    target = _valid_target()
    target.src_stamp_ns = context.source_stamp_ns

    reason = ControlRefNode.target_invalid_reason(context, target)

    assert reason is not None
    assert reason.startswith(f"freshness_{order_status}")


def test_zero_id_target_is_invalid():
    context = _validation_context(receive_age_s=0.0)
    target = _valid_target()
    target.id = 0

    assert ControlRefNode.target_invalid_reason(
        context,
        target,
    ) == "id_zero"


def test_fresh_valid_target_has_no_invalid_reason():
    context = _validation_context(receive_age_s=0.05)
    target = _valid_target()
    target.src_stamp_ns = context.source_stamp_ns

    assert ControlRefNode.target_invalid_reason(
        context,
        target,
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
