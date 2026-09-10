"""Static contracts for the live TIM-MARS target-authority graph."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess


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
    assert "-p status_topic:=/target_memory_mars/status" in block.group(0)
    # Yaw recovery is launched from the resolved CONTROL_YAW_RECOVERY_BOOL
    # (frozen #74 candidate; default OFF -- see live_defaults.sh).
    assert (
        "-p enable_yaw_recovery:=$CONTROL_ENABLE_YAW_RECOVERY"
        in block.group(0)
    )
    assert (
        'CONTROL_ENABLE_YAW_RECOVERY="${CONTROL_YAW_RECOVERY_BOOL:-false}"'
        in launcher
    )
    assert 'CONTROL_YAW_RECOVERY_BOOL="false"' in _read(
        LAUNCHER.parent / "lib" / "live_defaults.sh"
    )
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


def test_denied_runtime_switch_is_a_target_authority_no_op():
    """A denied model/tracker switch rejects before it touches target authority.

    The ``_runtime_reconfiguration_enabled`` guard and its 409 ``return`` both
    precede any ``_apply_target_authority_request`` call, and a ``return`` sits
    between the guard and that call.
    """
    dashboard = _read(DASHBOARD)
    methods = _class_methods(DASHBOARD, "DashboardBridgeNode")

    assert 'declare_parameter("runtime_reconfiguration_enabled", False)' in dashboard
    for method_name in {"_handle_model_switch", "_handle_tracker_switch"}:
        method = methods[method_name]
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
        return_lines = [
            node.lineno
            for node in ast.walk(method)
            if isinstance(node, ast.Return)
        ]

        assert "_apply_target_authority_request" in calls
        # Reconfiguration denial happens before any authority reset.
        assert reconfiguration_guard_line < authority_clear_line
        # A rejected no-op returns between the guard and the authority call.
        assert any(
            reconfiguration_guard_line <= line < authority_clear_line
            for line in return_lines
        )


def test_launcher_binds_dashboard_and_gates_non_loopback_on_a_token():
    launcher = _read(LAUNCHER)
    live_cli = (REPO_ROOT / "tools/lib/live_cli.sh").read_text(
        encoding="utf-8"
    )
    live_defaults = (REPO_ROOT / "tools/lib/live_defaults.sh").read_text(
        encoding="utf-8"
    )

    assert 'DASHBOARD_BIND="${DASHBOARD_BIND:-127.0.0.1}"' in live_defaults
    assert "dashboard_bind_is_loopback" in live_defaults
    assert "--dashboard-bind" in live_cli
    assert '-p api_host:="$DASHBOARD_BIND"' in launcher
    assert '-p ws_host:="$DASHBOARD_BIND"' in launcher
    assert "dashboard_cors_allowed_origins" in launcher

    # The control token must NOT be placed on the ROS command line; it is
    # delivered only through the inherited environment variable.
    assert "dashboard_control_api_token:=" not in launcher
    assert "export DASHBOARD_CONTROL_TOKEN" in launcher

    # Non-loopback bind without a token must refuse before the bridge starts.
    assert "dashboard_bind_is_loopback" in live_cli
    assert 'DASHBOARD_CONTROL_TOKEN' in live_cli
    assert "is not loopback" in live_cli


def _run_live_arg_gate(
    *,
    bind: str,
    token: str | None,
) -> subprocess.CompletedProcess:
    parts = [
        f'export THESIS_ROOT="{REPO_ROOT}"',
        f'cd "{REPO_ROOT}"',
        "source tools/lib/live_usage.sh",
        "source tools/lib/live_defaults.sh",
        "source tools/lib/live_storage.sh",
        "source tools/lib/live_cli.sh",
    ]
    if token is None:
        parts.append("unset DASHBOARD_CONTROL_TOKEN")
    else:
        parts.append(f"export DASHBOARD_CONTROL_TOKEN={token}")
    parts.append(
        "parse_and_validate_live_stack_args "
        f"--dashboard-bind {bind} && echo GATE_PASSED"
    )
    return subprocess.run(
        ["bash", "-c", "; ".join(parts)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_live_launcher_refuses_non_loopback_dashboard_bind_without_token():
    result = _run_live_arg_gate(bind="203.0.113.7", token=None)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "GATE_PASSED" not in result.stdout
    assert "not loopback" in output
    assert "DASHBOARD_CONTROL_TOKEN" in output


def test_live_launcher_accepts_non_loopback_dashboard_bind_with_token():
    result = _run_live_arg_gate(bind="203.0.113.7", token="synthetic-ground-secret")
    assert "GATE_PASSED" in result.stdout


def test_live_launcher_accepts_loopback_dashboard_bind_without_token():
    result = _run_live_arg_gate(bind="127.0.0.1", token=None)
    assert "GATE_PASSED" in result.stdout


def test_dashboard_has_no_container_model_switch_fallback():
    dashboard = _read(DASHBOARD)
    launcher = _read(LAUNCHER)
    methods = _class_methods(DASHBOARD, "DashboardBridgeNode")

    for retired_symbol in {
        "detector_container_name",
        "detector_bind",
        "enable_container_model_switch_api",
        "_handle_container_model_switch",
    }:
        assert retired_symbol not in dashboard

    assert '["docker", "exec"' not in dashboard
    assert "DASHBOARD_CONTAINER_MODEL_SWITCH_BOOL" not in launcher
    assert "-p enable_container_model_switch_api" not in launcher

    model_switch_calls = _called_attributes(methods["_handle_model_switch"])
    assert "_handle_integrated_camera_model_switch" in model_switch_calls


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
