"""Static contracts for the live TIM-MARS target-authority graph."""

from __future__ import annotations

import ast
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[4]
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
DASHBOARD = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/thesis_bringup/dashboard/dashboard_bridge_node.py"
)
TIM_NODE = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory_mars_node.py"
)
GROUND_RUNNER = REPO_ROOT / "tools/live/validate_target_authority_ground_run.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_methods(path: Path, class_name: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_read(path))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.name: node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


def _called_attributes(method: ast.FunctionDef) -> list[str]:
    return [
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]


def test_live_control_consumes_only_validated_tim_target():
    launcher = _read(LAUNCHER)
    block = re.search(
        r"(?ms)^    start_ros_bg control .*?^    sleep 1$",
        launcher,
    )

    assert block is not None
    assert "-p target_topic:=/target_memory_mars" in block.group(0)
    assert "-p target_topic:=/target " not in block.group(0)


def test_launcher_freezes_reconfiguration_and_commands_tim_topics():
    launcher = _read(LAUNCHER)

    assert 'DASHBOARD_RUNTIME_RECONFIGURATION_BOOL="false"' in launcher
    assert (
        "-p runtime_reconfiguration_enabled:="
        "$DASHBOARD_RUNTIME_RECONFIGURATION_BOOL"
    ) in launcher
    assert "-p target_select_topic:=/target_memory_mars/select" in launcher
    assert "-p target_clear_topic:=/target_memory_mars/clear" in launcher
    assert "target_authority_generation_initial=0" in launcher
    assert "target_authority_event_log=target_authority_events.jsonl" in launcher
    assert "-p target_authority_event_log_path:" in launcher
    assert "archive_target_authority_events" in launcher


def test_dashboard_target_focus_commands_authority_not_only_raw_target():
    methods = _class_methods(DASHBOARD, "DashboardBridgeNode")
    focus_calls = _called_attributes(methods["_handle_target_focus"])
    authority_calls = _called_attributes(
        methods["_apply_target_authority_request"]
    )

    assert "_apply_target_authority_request" in focus_calls
    assert "_target_command_subscriber_ready" in focus_calls
    assert "_publish_immediate_target_reset" in authority_calls
    assert "_publish_target_authority_command" in authority_calls

    readiness_calls = _called_attributes(
        methods["_target_command_subscriber_ready"]
    )
    assert "get_subscriptions_info_by_topic" in readiness_calls


def test_target_commands_use_reliable_qos_and_auto_fails_closed():
    dashboard = _read(DASHBOARD)
    tim_node = _read(TIM_NODE)

    assert "command_qos" in dashboard
    assert "command_qos" in tim_node
    assert "reliability=ReliabilityPolicy.RELIABLE" in dashboard
    assert "reliability=ReliabilityPolicy.RELIABLE" in tim_node
    assert '"auto"' in dashboard


def test_runtime_switches_fail_closed_around_target_authority():
    dashboard = _read(DASHBOARD)
    methods = _class_methods(DASHBOARD, "DashboardBridgeNode")

    assert 'declare_parameter("runtime_reconfiguration_enabled", False)' in dashboard
    for method_name in {"_handle_model_switch", "_handle_tracker_switch"}:
        method = methods[method_name]
        attributes = {
            node.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
        }
        calls = _called_attributes(method)
        authority_clear_line = min(
            node.lineno
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_apply_target_authority_request"
        )
        reconfiguration_guard_line = min(
            node.lineno
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
            and node.attr == "_runtime_reconfiguration_enabled"
        )

        assert "_runtime_reconfiguration_enabled" in attributes
        assert "_apply_target_authority_request" in calls
        assert authority_clear_line < reconfiguration_guard_line


def test_tim_select_and_clear_publish_immediate_zero_authority():
    methods = _class_methods(TIM_NODE, "TargetMemoryMarsNode")

    for method_name in {"_on_select", "_on_clear"}:
        calls = _called_attributes(methods[method_name])
        assert "clear" in calls
        assert "_publish_target_reset" in calls

    reset_calls = _called_attributes(methods["_publish_target_reset"])
    assert "publish" in reset_calls


def test_ground_runner_covers_required_authority_transitions():
    runner = _read(GROUND_RUNNER)

    for phase_name in {
        "raw_target_bypass",
        "explicit_select",
        "explicit_clear",
        "id_reuse_without_selection",
        "model_switch_rejected",
        "tracker_switch_rejected",
        "stale_validated_target",
        "tim_node_restart",
    }:
        assert phase_name in runner

    assert "/target_memory_mars" in runner
    assert "/control_ref/cmd_vel" in runner
    assert "enable_mavros:=false" in runner
