"""Contracts for the Issue #55 dashboard backend boundary."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from thesis_bringup.dashboard.dashboard_bridge_node import (
    build_battery_telemetry,
    dashboard_request_origin_allowed,
    DashboardBridgeNode,
    DEFAULT_DASHBOARD_ALLOWED_ORIGINS,
    parse_dashboard_allowed_origins,
    sanitize_battery_measurements,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
BRIDGE = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/"
    "thesis_bringup/dashboard/dashboard_bridge_node.py"
)
FIELD_LAUNCHER = REPO_ROOT / "tools/start_field_ui.sh"
FIELD_FIREWALL = (
    REPO_ROOT
    / "tools/setup/setup_field_ui_firewall.sh"
)


class _UnavailableClient:
    def wait_for_service(self, *, timeout_sec: float) -> bool:
        del timeout_sec
        return False


def test_default_origin_policy_is_loopback_only_and_no_wildcard():
    origins = parse_dashboard_allowed_origins("")

    assert origins == set(DEFAULT_DASHBOARD_ALLOWED_ORIGINS)
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5173" in origins

    with pytest.raises(ValueError, match="wildcard"):
        parse_dashboard_allowed_origins("*")


def test_request_origin_policy_allows_cli_and_exact_browser_origin():
    origins = {"http://192.168.1.50:5173"}

    assert dashboard_request_origin_allowed("", origins)
    assert dashboard_request_origin_allowed(
        "http://192.168.1.50:5173",
        origins,
    )
    assert not dashboard_request_origin_allowed(
        "http://example.invalid:5173",
        origins,
    )


def test_battery_sanitization_preserves_truthful_mavros_values():
    values = sanitize_battery_measurements(
        0.64,
        15.7,
        -3.25,
    )

    assert values == {
        "percentage": 0.64,
        "voltage_v": 15.7,
        "current_a": -3.25,
    }

    invalid = sanitize_battery_measurements(
        float("nan"),
        -1.0,
        float("inf"),
    )

    assert invalid == {
        "percentage": None,
        "voltage_v": None,
        "current_a": None,
    }

    assert sanitize_battery_measurements(
        1.2,
        12.0,
        0.0,
    )["percentage"] is None


def test_battery_freshness_is_receive_time_based():
    values = {
        "percentage": 0.5,
        "voltage_v": 15.0,
        "current_a": -2.0,
    }

    fresh = build_battery_telemetry(
        values,
        last_rx_monotonic_ns=10_000_000_000,
        now_monotonic_ns=11_000_000_000,
        stale_timeout_s=3.0,
    )

    assert fresh["source"] == "mavros"
    assert fresh["stale"] is False
    assert fresh["age_ms"] == pytest.approx(1000.0)

    stale = build_battery_telemetry(
        values,
        last_rx_monotonic_ns=10_000_000_000,
        now_monotonic_ns=14_100_000_000,
        stale_timeout_s=3.0,
    )

    assert stale["source"] == "mavros"
    assert stale["stale"] is True
    assert stale["age_ms"] == pytest.approx(4100.0)


def test_battery_before_first_message_is_unavailable_not_zero():
    payload = build_battery_telemetry(
        {
            "percentage": None,
            "voltage_v": None,
            "current_a": None,
        },
        last_rx_monotonic_ns=None,
        now_monotonic_ns=123,
        stale_timeout_s=3.0,
    )

    assert payload == {
        "percentage": None,
        "voltage_v": None,
        "current_a": None,
        "age_ms": None,
        "stale": True,
        "source": None,
    }


def test_models_endpoint_payload_reports_model_availability(tmp_path):
    hef = tmp_path / "yolov8s.hef"
    hef.write_bytes(b"test")

    fake = SimpleNamespace(
        _supported_models=[
            SimpleNamespace(
                key="yolov8s",
                hef_file="yolov8s.hef",
            )
        ],
        _integrated_camera_hef_dir=str(tmp_path),
    )

    result = DashboardBridgeNode._handle_models_list(fake)

    assert result["ok"] is True
    assert result["models"] == [
        {
            "key": "yolov8s",
            "hef_file": "yolov8s.hef",
            "hef_path": str(hef),
            "available": True,
        }
    ]


def test_model_switch_contract_covers_validation_freeze_and_service_loss():
    authority_calls: list[tuple[int | None, str]] = []

    def apply_authority(
        target_id: int | None,
        *,
        reason: str,
    ) -> int:
        authority_calls.append((target_id, reason))
        return 7

    fake = SimpleNamespace(
        _model_to_hef={"yolov8s": "yolov8s.hef"},
        _runtime_reconfiguration_enabled=False,
        _apply_target_authority_request=apply_authority,
        _handle_integrated_camera_model_switch=lambda _model: None,
    )

    unsupported = DashboardBridgeNode._handle_model_switch(
        fake,
        "unknown",
    )
    assert unsupported["status_code"] == 400

    frozen = DashboardBridgeNode._handle_model_switch(
        fake,
        "yolov8s",
    )
    assert frozen["status_code"] == 409
    assert frozen["target_authority_generation"] == 7
    assert authority_calls[-1] == (
        None,
        "model_switch:yolov8s",
    )

    fake._runtime_reconfiguration_enabled = True

    unavailable = DashboardBridgeNode._handle_model_switch(
        fake,
        "yolov8s",
    )
    assert unavailable["status_code"] == 503


def test_tracker_switch_contract_covers_validation_freeze_and_service_loss():
    authority_calls: list[tuple[int | None, str]] = []

    def apply_authority(
        target_id: int | None,
        *,
        reason: str,
    ) -> int:
        authority_calls.append((target_id, reason))
        return 9

    fake = SimpleNamespace(
        _supported_trackers={"bytetrack"},
        _runtime_reconfiguration_enabled=False,
        _apply_target_authority_request=apply_authority,
        _tracker_set_params_client=_UnavailableClient(),
        _tracker_node_name="tracker_node",
    )

    unsupported = DashboardBridgeNode._handle_tracker_switch(
        fake,
        "unknown",
    )
    assert unsupported["status_code"] == 400

    frozen = DashboardBridgeNode._handle_tracker_switch(
        fake,
        "bytetrack",
    )
    assert frozen["status_code"] == 409
    assert frozen["target_authority_generation"] == 9
    assert authority_calls[-1] == (
        None,
        "tracker_switch:bytetrack",
    )

    fake._runtime_reconfiguration_enabled = True

    unavailable = DashboardBridgeNode._handle_tracker_switch(
        fake,
        "bytetrack",
    )
    assert unavailable["status_code"] == 503


def test_target_focus_contract_covers_validation_unavailable_and_success():
    parse_result: list[tuple[int | None, str | None]] = [
        (None, "invalid target")
    ]
    ready = [False]
    reset_count = [0]
    authority_calls: list[tuple[int | None, str]] = []

    def publish_reset() -> None:
        reset_count[0] += 1

    def apply_authority(
        target_id: int | None,
        *,
        reason: str,
    ) -> int:
        authority_calls.append((target_id, reason))
        return 11

    fake = SimpleNamespace(
        _parse_target_focus_id=lambda _value: parse_result[0],
        _target_select_topic="/target_memory_mars/select",
        _target_clear_topic="/target_memory_mars/clear",
        _target_command_subscriber_ready=lambda _topic: ready[0],
        _publish_immediate_target_reset=publish_reset,
        _apply_target_authority_request=apply_authority,
        _validated_target_topic="/target_memory_mars",
        get_logger=lambda: SimpleNamespace(
            info=lambda _message: None
        ),
    )

    invalid = DashboardBridgeNode._handle_target_focus(
        fake,
        "invalid",
    )
    assert invalid["status_code"] == 400

    parse_result[0] = (5, None)

    unavailable = DashboardBridgeNode._handle_target_focus(
        fake,
        5,
    )
    assert unavailable["status_code"] == 503
    assert reset_count[0] == 1
    assert authority_calls == []

    ready[0] = True

    selected = DashboardBridgeNode._handle_target_focus(
        fake,
        5,
    )
    assert selected["status_code"] == 200
    assert selected["requested_target"] == 5
    assert selected["action"] == "select"
    assert selected["target_authority_generation"] == 11
    assert authority_calls[-1] == (
        5,
        "operator_select",
    )


def test_websocket_snapshot_is_status_contract_and_carries_generation():
    state = {
        "tracks": [],
        "detections": [],
        "target": None,
        "target_requested": None,
        "target_active": None,
        "target_authority_source": "/target_memory_mars",
        "target_authority_generation": 4,
        "target_authority_reason": "operator_clear",
        "target_authority_session_id": "test-session",
        "target_authority_event_log_path": "",
        "target_memory": None,
        "camera_input_fps": 30.0,
        "det_out_fps": 15.0,
        "e2e_det_ms": 40.0,
        "pub_dt_ms": 66.0,
        "metrics_schema_version": 3,
        "metric_windows": {
            "det_out_fps_seconds": 3.0,
        },
        "metric_thresholds_ms": {
            "e2e_det_ms": 120.0,
            "pub_dt_ms": 120.0,
        },
        "replay_progress": None,
        "inference_resolution": {
            "width": 640,
            "height": 640,
        },
        "system": {
            "cpu_percent": 10.0,
            "mem_percent": 20.0,
            "mem_used_mb": 1000.0,
            "temp_c": 50.0,
        },
        "battery": {},
    }

    fake = SimpleNamespace(
        _state_lock=threading.Lock(),
        _state=state,
        _battery_measurements={
            "percentage": None,
            "voltage_v": None,
            "current_a": None,
        },
        _battery_last_rx_monotonic_ns=None,
        _battery_stale_timeout_s=3.0,
    )

    payload = json.loads(
        DashboardBridgeNode._snapshot_json(fake)
    )

    assert payload["target_authority_generation"] == 4
    assert payload["target_authority_session_id"] == "test-session"
    assert payload["battery"]["source"] is None
    assert payload["battery"]["stale"] is True


def test_source_network_and_route_contract_is_intentionally_scoped():
    bridge = BRIDGE.read_text(encoding="utf-8")
    launcher = FIELD_LAUNCHER.read_text(encoding="utf-8")
    firewall = FIELD_FIREWALL.read_text(encoding="utf-8")

    assert (
        'declare_parameter("ws_host", "127.0.0.1")'
        in bridge
    )
    assert (
        'declare_parameter("api_host", "127.0.0.1")'
        in bridge
    )
    assert (
        '",".join(DEFAULT_DASHBOARD_ALLOWED_ORIGINS)'
        in bridge
    )

    assert bridge.count(
        "if self._reject_disallowed_origin():"
    ) == 3

    for route in {
        '"/api/models"',
        '"/api/model"',
        '"/api/tracker"',
        '"/api/target"',
    }:
        assert route in bridge

    assert '"/api/status"' not in bridge

    assert (
        'export DASHBOARD_BRIDGE_BIND_HOST="$WLAN_IP"'
        in launcher
    )
    assert (
        'export DASHBOARD_BRIDGE_ALLOWED_ORIGINS='
        '"http://${WLAN_IP}:${UI_PORT}"'
        in launcher
    )

    assert "ufw allow in on wlan0 proto tcp" in firewall
    assert 'FIELD_OPERATOR_SSH_CIDR="${FIELD_OPERATOR_SSH_CIDR:-192.168.8.0/24}"' in firewall
    assert 'from "$FIELD_OPERATOR_SSH_CIDR"' in firewall
    assert 'proto tcp to any port 22' in firewall
    assert 'ufw allow 22' not in firewall
    assert 'ufw allow OpenSSH' not in firewall
