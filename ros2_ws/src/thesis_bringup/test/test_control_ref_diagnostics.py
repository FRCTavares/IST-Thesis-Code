"""Issue #74 controller-diagnostics instrumentation tests.

Proves the recorded ``/control_ref/diagnostics`` topic reconstructs the
controller decision / recovery state for every command, that its command
fields equal the paired ``/control_ref/cmd_vel`` Twist, and that the
instrumentation does not change what the controller commands. No Pixhawk,
no MAVROS, no aircraft -- rclpy + synthetic messages only.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace

from builtin_interfaces.msg import Time
import pytest
import rclpy
from std_msgs.msg import String

from thesis_bringup.control.control_ref_node import ControlRefNode
from thesis_bringup.control.state_aware_policy import StateAwarePolicyConfig
from thesis_msgs.msg import ControlDiagnostics, TargetState


CONTROL_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "control"
    / "control_ref_node.py"
)


# --------------------------------------------------------------------------- #
# rclpy integration harness
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


class _Driver:
    """A constructed ControlRefNode with its publishers captured."""

    def __init__(self) -> None:
        self.node = ControlRefNode()
        self.cmd: list = []
        self.diag: list = []
        self.node.pub_cmd.publish = self.cmd.append
        self.node.pub_diag.publish = self.diag.append
        self.node.pub_mavros.publish = lambda _m: None

    def close(self) -> None:
        self.node.destroy_node()

    def now_ns(self) -> int:
        return self.node.get_clock().now().nanoseconds

    def enable_recovery(self) -> None:
        """Represent the frozen #74 candidate: same bounds, recovery armed."""
        n = self.node
        n.enable_yaw_recovery = True
        n.state_aware_policy_config = StateAwarePolicyConfig(
            recovery_enabled=True,
            recovery_yaw_rate=n.recovery_yaw_rate,
            recovery_max_duration_s=n.recovery_max_duration_s,
            recovery_max_integrated_yaw_rad=n.recovery_max_integrated_yaw_rad,
            last_trusted_max_age_s=n.recovery_last_trusted_max_age_s,
        )

    def status(self, *, state: str, control_mode: str, generation: int = 3,
               frame_id: int | None = 91, track_ns: int | None = None,
               target_track_id: int | None = 7, fresh: bool = True) -> None:
        payload = {
            "state": state,
            "control_mode": control_mode,
            "selection_generation": generation,
            "selection_session_id": "session-current",
            "target_track_id": target_track_id,
            "freshness_is_fresh": fresh,
            "reason": "test",
        }
        if frame_id is not None:
            payload["frame_id"] = frame_id
        if track_ns is not None:
            payload["track_timestamp_ns"] = track_ns
        self.node.on_status(String(data=json.dumps(payload)))

    def target(self, *, cx: float = 320.0, src_ns: int | None = None,
               track_id: int = 7, frame_id: int = 91) -> None:
        msg = TargetState()
        msg.frame_id = frame_id
        msg.src_stamp_ns = src_ns if src_ns is not None else self.now_ns()
        msg.id = track_id
        msg.cx = cx
        msg.cy = 320.0
        msg.w = 80.0
        msg.h = 160.0
        msg.score = 1.0
        msg.quality = 1.0
        self.node.on_target(msg)

    def last_diag(self) -> ControlDiagnostics:
        assert self.diag, "no diagnostics were published"
        return self.diag[-1]

    def last_cmd(self):
        assert self.cmd, "no command was published"
        return self.cmd[-1]


@pytest.fixture()
def driver(ros):
    d = _Driver()
    yield d
    d.close()


# --------------------------------------------------------------------------- #
# A. normal publication
# --------------------------------------------------------------------------- #
def test_normal_follow_publishes_matching_diagnostics(driver):
    src = driver.now_ns() - 10_000_000
    driver.status(state="LOCKED", control_mode="NORMAL", frame_id=91,
                  track_ns=src, target_track_id=7)
    driver.target(cx=400.0, src_ns=src, track_id=7, frame_id=91)
    driver.node.on_timer()

    diag = driver.last_diag()
    cmd = driver.last_cmd()

    assert diag.mode == "NORMAL_FOLLOW"
    assert diag.reason == "trusted_locked_normal"
    assert diag.tim_state == "LOCKED"
    assert diag.tim_control_mode == "NORMAL"
    assert diag.selection_generation == 3
    assert diag.status_fresh is True
    assert diag.target_fresh is True
    assert diag.target_valid is True
    assert diag.target_id == 7
    assert diag.recovery_enabled is False
    assert diag.recovery_active is False
    # F: command parity with the paired Twist
    assert diag.command_vx == pytest.approx(cmd.twist.linear.x)
    assert diag.command_vy == pytest.approx(cmd.twist.linear.y)
    assert diag.command_yaw_z == pytest.approx(cmd.twist.angular.z)
    assert diag.header.stamp == cmd.header.stamp
    # exactly one diagnostic per command emission
    assert len(driver.diag) == len(driver.cmd)


# --------------------------------------------------------------------------- #
# B. LOST with recovery disabled (current baseline)
# --------------------------------------------------------------------------- #
def test_lost_recovery_disabled_is_distinguishable_and_zero(driver):
    src = driver.now_ns() - 10_000_000
    driver.status(state="LOST", control_mode="NO_CONTROL", frame_id=95,
                  track_ns=src, target_track_id=7)
    driver.target(src_ns=src, track_id=7, frame_id=95)
    driver.node.on_timer()

    diag = driver.last_diag()
    cmd = driver.last_cmd()

    assert diag.mode == "HOVER"
    assert diag.reason == "recovery_disabled"
    assert diag.tim_state == "LOST"
    assert diag.recovery_enabled is False
    assert diag.recovery_active is False
    assert diag.command_vx == 0.0
    assert diag.command_vy == 0.0
    assert diag.command_yaw_z == 0.0
    assert cmd.twist.linear.x == 0.0
    assert cmd.twist.angular.z == 0.0


# --------------------------------------------------------------------------- #
# C. recovery-capable representation (candidate behaviour, launcher unchanged)
# --------------------------------------------------------------------------- #
def test_recovery_yaw_only_representation_keeps_translation_zero(driver):
    driver.enable_recovery()
    src = driver.now_ns() - 10_000_000
    # 1) establish a trusted off-centre observation
    driver.status(state="LOCKED", control_mode="NORMAL", generation=3,
                  frame_id=91, track_ns=src, target_track_id=7)
    driver.target(cx=520.0, src_ns=src, track_id=7, frame_id=91)
    driver.node.on_timer()
    assert driver.last_diag().mode == "NORMAL_FOLLOW"

    # 2) LOST, same generation -> recovery becomes eligible
    src2 = driver.now_ns() - 5_000_000
    driver.status(state="LOST", control_mode="NO_CONTROL", generation=3,
                  frame_id=96, track_ns=src2, target_track_id=7)
    driver.target(cx=520.0, src_ns=src2, track_id=7, frame_id=96)
    driver.node.on_timer()   # first recovery tick: hard zero
    first = driver.last_diag()
    assert first.mode == "RECOVERY_YAW_ONLY"
    assert first.recovery_enabled is True
    assert first.recovery_active is True
    assert first.command_vx == 0.0 and first.command_vy == 0.0
    assert first.command_yaw_z == 0.0
    assert first.recovery_direction in ("left", "right")

    driver.node.on_timer()   # second recovery tick: bounded yaw
    second = driver.last_diag()
    cmd = driver.last_cmd()
    assert second.mode == "RECOVERY_YAW_ONLY"
    assert second.recovery_active is True
    assert second.command_vx == 0.0
    assert second.command_vy == 0.0
    assert cmd.twist.linear.x == 0.0
    assert cmd.twist.linear.y == 0.0
    assert second.command_yaw_z == pytest.approx(cmd.twist.angular.z)
    assert abs(second.command_yaw_z) <= driver.node.max_yaw_z + 1e-9
    assert second.recovery_elapsed_s >= 0.0
    assert second.recovery_max_duration_s == pytest.approx(1.0)
    assert second.recovery_max_integrated_yaw_rad == pytest.approx(0.10)


# --------------------------------------------------------------------------- #
# builder-level unit tests (D, E) -- crafted state, exact helper reuse
# --------------------------------------------------------------------------- #
NOW_NS = 1_000_000_000_000


def _ctx(**overrides):
    ctx = SimpleNamespace(
        _diag_mode="RECOVERY_YAW_ONLY",
        _diag_reason="recent_lost_trusted_direction",
        _diag_target_valid=False,
        _diag_invalid_reason="",
        cmd_frame_id="base_link",
        last_status=None,
        last_status_rx_time=None,
        stale_timeout_s=0.9,
        future_tolerance_s=0.05,
        last_target=None,
        last_target_rx_time=None,
        last_target_source_order_status=None,
        enable_yaw_recovery=True,
        recovery_yaw_rate=0.10,
        recovery_max_duration_s=1.0,
        recovery_max_integrated_yaw_rad=0.10,
        recovery_last_trusted_max_age_s=1.0,
        recovery_active=True,
        recovery_start_ns=NOW_NS - 500_000_000,
        recovery_last_update_ns=NOW_NS - 30_000_000,
        recovery_integrated_yaw_rad=0.098,
        recovery_consumed_trusted_stamp_ns=None,
        last_trusted_stamp_ns=NOW_NS - 300_000_000,
        last_trusted_horizontal_error=0.25,
        last_trusted_generation=3,
        max_yaw_z=0.10,
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    ctx.get_clock = lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=NOW_NS)
    )
    ctx.status_is_fresh = lambda now_ns=None: ControlRefNode.status_is_fresh(
        ctx, now_ns
    )
    ctx.is_fresh = lambda: ControlRefNode.is_fresh(ctx)
    ctx.recovery_direction_label = (
        lambda: ControlRefNode.recovery_direction_label(ctx)
    )
    ctx.recovery_elapsed_s = lambda now_ns: ControlRefNode.recovery_elapsed_s(
        ctx, now_ns
    )
    ctx.last_trusted_age_s = lambda now_ns: ControlRefNode.last_trusted_age_s(
        ctx, now_ns
    )
    ctx.recovery_history_consumed = (
        lambda: ControlRefNode.recovery_history_consumed(ctx)
    )
    return ctx


def _build(ctx, *, vx=0.0, vy=0.0, yaw_z=0.05):
    return ControlRefNode._build_diagnostics(
        ctx,
        now_ns=NOW_NS,
        stamp=Time(sec=1000, nanosec=0),
        vx=vx,
        vy=vy,
        yaw_z=yaw_z,
    )


def test_diagnostic_exposes_recovery_budget_elapsed_and_bounds():
    msg = _build(_ctx(), yaw_z=0.05)
    assert msg.recovery_active is True
    assert msg.recovery_elapsed_s == pytest.approx(0.5)
    assert msg.recovery_integrated_yaw_rad == pytest.approx(0.098)
    assert msg.recovery_budget_remaining_rad == pytest.approx(0.002)
    assert msg.recovery_max_integrated_yaw_rad == pytest.approx(0.10)
    assert msg.recovery_max_duration_s == pytest.approx(1.0)
    assert msg.recovery_yaw_rate == pytest.approx(0.10)
    assert msg.recovery_direction == "right"


def test_diagnostic_carries_termination_reason_verbatim():
    ctx = _ctx(
        _diag_mode="HOVER",
        _diag_reason="recovery_yaw_budget_exhausted",
        recovery_active=False,
    )
    msg = _build(ctx, yaw_z=0.0)
    assert msg.mode == "HOVER"
    assert msg.reason == "recovery_yaw_budget_exhausted"
    assert msg.recovery_active is False


def test_last_trusted_age_reaches_topic_without_recompute_drift():
    ctx = _ctx()
    msg = _build(ctx)
    assert msg.last_trusted_valid is True
    assert msg.last_trusted_age_s == pytest.approx(0.3)
    assert msg.last_trusted_age_s == pytest.approx(
        ControlRefNode.last_trusted_age_s(ctx, NOW_NS)
    )
    assert msg.last_trusted_generation == 3

    missing = _ctx(last_trusted_stamp_ns=None, last_trusted_horizontal_error=None,
                   last_trusted_generation=None)
    msg2 = _build(missing)
    assert msg2.last_trusted_valid is False
    assert math.isnan(msg2.last_trusted_age_s)
    assert math.isnan(msg2.last_trusted_horizontal_error)
    assert msg2.last_trusted_generation == -1


def test_diagnostic_command_fields_match_the_twist_for_same_args():
    ctx = _ctx()
    stamp = Time(sec=1000, nanosec=123)
    twist = ControlRefNode._make_twist_msg(
        ctx, stamp, 0.0, 0.0, 0.037, "base_link"
    )
    diag = ControlRefNode._build_diagnostics(
        ctx, now_ns=NOW_NS, stamp=stamp, vx=0.0, vy=0.0, yaw_z=0.037
    )
    assert diag.command_vx == twist.twist.linear.x
    assert diag.command_vy == twist.twist.linear.y
    assert diag.command_yaw_z == twist.twist.angular.z


# --------------------------------------------------------------------------- #
# source contract: instrumentation is wired, recovery still OFF
# --------------------------------------------------------------------------- #
def test_publish_pair_emits_diagnostics_and_recovery_stays_off():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "ControlRefNode"
    )
    methods = {
        n.name for n in cls.body if isinstance(n, ast.FunctionDef)
    }
    assert {"_set_decision", "_build_diagnostics", "_emit_diagnostics"} <= methods

    publish_pair = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name == "publish_pair"
    )
    emit_calls = [
        n for n in ast.walk(publish_pair)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_emit_diagnostics"
    ]
    assert len(emit_calls) == 1

    # recovery remains feature-gated OFF; no activation path introduced here
    assert "declare_parameter('enable_yaw_recovery', False)" in source
    assert "enable_yaw_recovery:=true" not in source
    assert "control-yaw-recovery" not in source
    # control.log path is not removed
    assert "def maybe_log_recovery_diagnostics(" in source
