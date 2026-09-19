"""Regression tests for the TIM-MARS controller-authority QoS contract."""

from __future__ import annotations

import json
import time

import pytest
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    qos_check_compatible,
    QoSCompatibility,
    ReliabilityPolicy,
)
from rclpy.time import Time
from std_msgs.msg import String

from thesis_bringup.authority_qos import (
    authority_status_qos,
    target_state_qos,
)
from thesis_bringup.control.control_ref_node import ControlRefNode
from thesis_msgs.msg import TargetState


@pytest.fixture(scope="module")
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def _spin_until(node, predicate, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.02)
        if predicate():
            return
    pytest.fail("ROS authority transport condition timed out")


def _spin_for(node, duration_s: float) -> None:
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.02)


def _status_payload(
    *,
    state: str,
    control_mode: str,
    frame_id: int,
    source_stamp_ns: int,
) -> String:
    return String(
        data=json.dumps(
            {
                "state": state,
                "control_mode": control_mode,
                "selection_generation": 1,
                "selection_session_id": "qos-contract-test",
                "frame_id": frame_id,
                "track_timestamp_ns": source_stamp_ns,
                "target_track_id": 7,
                "freshness_is_fresh": True,
                "reason": "qos_contract_test",
            }
        )
    )


def _target(*, frame_id: int, source_stamp_ns: int) -> TargetState:
    msg = TargetState()
    msg.frame_id = frame_id
    msg.src_stamp_ns = source_stamp_ns
    msg.id = 7
    msg.cx = 480.0
    msg.cy = 320.0
    msg.w = 80.0
    msg.h = 64.0
    msg.score = 1.0
    msg.quality = 1.0
    return msg


def test_authority_profiles_are_compatible_and_intentional():
    target_compatibility, target_reason = qos_check_compatible(
        target_state_qos(),
        target_state_qos(),
    )
    status_profile = authority_status_qos()
    status_compatibility, status_reason = qos_check_compatible(
        status_profile,
        authority_status_qos(),
    )

    assert target_compatibility != QoSCompatibility.ERROR, target_reason
    assert status_compatibility != QoSCompatibility.ERROR, status_reason
    assert target_state_qos().reliability == ReliabilityPolicy.BEST_EFFORT
    assert status_profile.reliability == ReliabilityPolicy.RELIABLE
    assert status_profile.durability == DurabilityPolicy.VOLATILE


def test_status_transport_reaches_fail_closed_controller_gate(ros):
    controller = ControlRefNode()
    # Drive policy ticks explicitly while the test spins status delivery.
    controller.timer.cancel()
    driver = Node("authority_qos_contract_driver")
    status_pub = driver.create_publisher(
        String,
        "/target_memory_mars/status",
        authority_status_qos(),
    )
    commands = []
    controller.pub_cmd.publish = commands.append
    controller.pub_mavros.publish = lambda _msg: None
    controller.pub_diag.publish = lambda _msg: None

    try:
        _spin_until(
            controller,
            lambda: status_pub.get_subscription_count() == 1,
        )

        status_endpoints = driver.get_subscriptions_info_by_topic(
            "/target_memory_mars/status"
        )
        assert len(status_endpoints) == 1
        assert (
            status_endpoints[0].qos_profile.reliability
            == ReliabilityPolicy.RELIABLE
        )

        _spin_for(controller, 0.20)
        source_stamp_ns = controller.get_clock().now().nanoseconds
        status_pub.publish(
            _status_payload(
                state="LOCKED",
                control_mode="NORMAL",
                frame_id=101,
                source_stamp_ns=source_stamp_ns,
            )
        )
        _spin_until(
            controller,
            lambda: controller.last_status is not None
            and controller.last_status.state == "LOCKED",
        )
        controller.on_target(
            _target(frame_id=101, source_stamp_ns=source_stamp_ns)
        )

        commands.clear()
        controller.on_timer()
        assert commands
        assert commands[-1].twist.linear.x > 0.0
        assert commands[-1].twist.angular.z > 0.0

        source_stamp_ns = controller.get_clock().now().nanoseconds
        status_pub.publish(
            _status_payload(
                state="LOST",
                control_mode="HOVER",
                frame_id=102,
                source_stamp_ns=source_stamp_ns,
            )
        )
        _spin_until(
            controller,
            lambda: controller.last_status is not None
            and controller.last_status.state == "LOST",
        )
        controller.on_target(
            _target(frame_id=102, source_stamp_ns=source_stamp_ns)
        )

        commands.clear()
        controller.on_timer()
        assert commands
        assert commands[-1].twist.linear.x == 0.0
        assert commands[-1].twist.linear.y == 0.0
        assert commands[-1].twist.angular.z == 0.0

        assert controller.last_status_rx_time is not None
        stale_now_ns = (
            controller.last_status_rx_time.nanoseconds
            + int((controller.stale_timeout_s + 0.01) * 1e9)
        )
        assert not controller.status_is_fresh(now_ns=stale_now_ns)
        controller.last_status_rx_time = Time(
            nanoseconds=(
                controller.get_clock().now().nanoseconds
                - int((controller.stale_timeout_s + 0.01) * 1e9)
            )
        )
        commands.clear()
        controller.on_timer()
        assert commands
        assert commands[-1].twist.linear.x == 0.0
        assert commands[-1].twist.linear.y == 0.0
        assert commands[-1].twist.angular.z == 0.0
    finally:
        driver.destroy_node()
        controller.destroy_node()
