"""HTTP contract tests for the dashboard control API.

Drives the real ``DashboardControlHandler`` over an ephemeral localhost port
against a minimal fake node. No ROS graph, no physical hardware. Synthetic
secrets only.
"""

from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import types
import urllib.error
import urllib.request

import pytest

from thesis_bringup.dashboard import dashboard_bridge_node as bridge_module
from thesis_bringup.dashboard.dashboard_bridge_node import (
    _parse_csv_origins,
    _resolve_control_api_token,
    DashboardBridgeNode,
    DashboardControlHandler,
)
from thesis_bringup.dashboard.dashboard_models import SupportedModel


ALLOWED_ORIGIN = "http://localhost:5173"
SYNTHETIC_TOKEN = "test-only-shared-secret-1234"


class _FakeLogger:
    def info(self, *_a, **_k) -> None:
        return

    def error(self, *_a, **_k) -> None:
        return

    def warning(self, *_a, **_k) -> None:
        return


def _make_node(
    *,
    runtime_reconfiguration_enabled: bool = False,
    control_api_token: str = "",
    cors_origins: str = f"{ALLOWED_ORIGIN},http://127.0.0.1:5173",
    subscriber_ready: bool = True,
) -> DashboardBridgeNode:
    node = object.__new__(DashboardBridgeNode)

    node._cors_allowed_origins = _parse_csv_origins(cors_origins)
    node._control_api_token = control_api_token
    node._runtime_reconfiguration_enabled = runtime_reconfiguration_enabled
    node._target_authority_generation = 7

    node._supported_models = (
        SupportedModel("yolov8s", "yolov8s.hef"),
        SupportedModel("yolov8n", "yolov8n.hef"),
    )
    node._model_to_hef = {
        model.key: model.hef_file for model in node._supported_models
    }
    node._integrated_camera_hef_dir = "/nonexistent/hef"
    node._supported_trackers = {"sort", "ocsort", "bytetrack", "deepsort"}

    node._validated_target_topic = "/target_memory_mars"
    node._target_select_topic = "/target_memory_mars/select"
    node._target_clear_topic = "/target_memory_mars/clear"

    # Record authority side effects so tests can assert a denied switch is a
    # true no-op.
    node.authority_calls = []

    def _apply(self, target_id, *, reason):
        self.authority_calls.append((target_id, reason))
        self._target_authority_generation += 1
        return self._target_authority_generation

    def _ready(self, _topic):
        return subscriber_ready

    node._apply_target_authority_request = types.MethodType(_apply, node)
    node._target_command_subscriber_ready = types.MethodType(_ready, node)
    node._publish_immediate_target_reset = types.MethodType(
        lambda self: None, node
    )
    node.get_logger = types.MethodType(lambda self: _FakeLogger(), node)
    return node


@contextmanager
def _server(node):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardControlHandler)
    httpd.dashboard_node = node
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _request(port, method, path, *, body=None, headers=None):
    url = f"http://127.0.0.1:{port}{path}"
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()


def _json(raw):
    return json.loads(raw.decode("utf-8"))


# --- Safe defaults ---------------------------------------------------------

def test_dashboard_bind_and_cors_defaults_are_safe():
    assert bridge_module.DEFAULT_DASHBOARD_BIND_HOST == "127.0.0.1"
    default_origins = _parse_csv_origins(
        bridge_module.DEFAULT_DASHBOARD_CORS_ALLOWED_ORIGINS
    )
    assert "*" not in bridge_module.DEFAULT_DASHBOARD_CORS_ALLOWED_ORIGINS
    assert all(
        origin.startswith(("http://localhost", "http://127.0.0.1"))
        for origin in default_origins
    )
    source = Path(bridge_module.__file__).read_text(encoding="utf-8")
    assert (
        'declare_parameter("api_host", DEFAULT_DASHBOARD_BIND_HOST)' in source
    )
    assert (
        'declare_parameter("ws_host", DEFAULT_DASHBOARD_BIND_HOST)' in source
    )
    assert 'declare_parameter("dashboard_control_api_token", "")' in source
    assert (
        'send_header("Access-Control-Allow-Origin", "*")' not in source
    )


# --- Control token is never on the process command line --------------------

def test_control_token_resolution_prefers_param_then_environment():
    assert _resolve_control_api_token("param-secret", {}) == "param-secret"
    assert (
        _resolve_control_api_token("", {"DASHBOARD_CONTROL_TOKEN": "env-secret"})
        == "env-secret"
    )
    assert (
        _resolve_control_api_token(
            "  param-secret  ", {"DASHBOARD_CONTROL_TOKEN": "env-secret"}
        )
        == "param-secret"
    )
    assert _resolve_control_api_token("", {}) == ""
    assert _resolve_control_api_token(None, {}) == ""


def test_node_reads_control_token_from_environment_not_argv():
    source = Path(bridge_module.__file__).read_text(encoding="utf-8")
    assert "_resolve_control_api_token(" in source
    assert 'environ.get("DASHBOARD_CONTROL_TOKEN", "")' in source
    assert "os.environ," in source
    # The startup log line records only a marker, never the raw value.
    assert (
        "'configured' if self._control_api_token else 'open'" in source
    )
    for line in source.splitlines():
        if "get_logger()" in line and "self._control_api_token" in line:
            raise AssertionError(f"token value in a log call: {line}")


# --- Read-only ---------------------------------------------------------------

def test_get_models_returns_expected_structure():
    with _server(_make_node()) as port:
        status, _headers, raw = _request(port, "GET", "/api/models")
    payload = _json(raw)
    assert status == 200
    assert payload["ok"] is True
    assert isinstance(payload["models"], list) and payload["models"]
    assert {m["key"] for m in payload["models"]} == {"yolov8s", "yolov8n"}


def test_unknown_endpoint_is_404():
    with _server(_make_node()) as port:
        get_status, _h, _r = _request(port, "GET", "/api/nope")
        post_status, _h2, _r2 = _request(
            port, "POST", "/api/nope", body={}
        )
    assert get_status == 404
    assert post_status == 404


# --- Frozen reconfiguration is a true no-op --------------------------------

@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/model", {"model": "yolov8s"}),
        ("/api/tracker", {"tracker": "bytetrack"}),
    ],
)
def test_denied_switch_is_409_and_touches_no_authority(path, body):
    node = _make_node(runtime_reconfiguration_enabled=False)
    with _server(node) as port:
        status, _headers, raw = _request(port, "POST", path, body=body)
    payload = _json(raw)
    assert status == 409
    assert payload["ok"] is False
    assert node.authority_calls == []
    assert node._target_authority_generation == 7
    assert payload["target_authority_generation"] == 7


# --- Target selection ------------------------------------------------------

def test_target_select_and_clear_ok():
    node = _make_node(subscriber_ready=True)
    with _server(node) as port:
        sel_status, _h, sel_raw = _request(
            port, "POST", "/api/target", body={"target": 5}
        )
        clr_status, _h2, clr_raw = _request(
            port, "POST", "/api/target", body={"target": None}
        )
    assert sel_status == 200 and _json(sel_raw)["ok"] is True
    assert clr_status == 200 and _json(clr_raw)["ok"] is True
    assert node.authority_calls == [(5, "operator_select"), (None, "operator_clear")]


@pytest.mark.parametrize("bad", ["abc", 1.5, True, -3])
def test_target_invalid_value_is_400(bad):
    with _server(_make_node()) as port:
        status, _h, raw = _request(
            port, "POST", "/api/target", body={"target": bad}
        )
    assert status == 400
    assert _json(raw)["ok"] is False


def test_target_unavailable_subscriber_is_503():
    node = _make_node(subscriber_ready=False)
    with _server(node) as port:
        status, _h, raw = _request(
            port, "POST", "/api/target", body={"target": 5}
        )
    assert status == 503
    assert _json(raw)["ok"] is False
    assert node.authority_calls == []


def test_invalid_json_body_is_400():
    with _server(_make_node()) as port:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/target",
            data=b"{not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
    assert status == 400


# --- Authentication ------------------------------------------------------

def test_control_post_requires_token_when_configured():
    node = _make_node(control_api_token=SYNTHETIC_TOKEN, subscriber_ready=True)
    with _server(node) as port:
        missing, _h, _r = _request(
            port, "POST", "/api/target", body={"target": 5}
        )
        wrong, _h2, _r2 = _request(
            port,
            "POST",
            "/api/target",
            body={"target": 5},
            headers={"Authorization": "Bearer wrong"},
        )
        correct, _h3, correct_raw = _request(
            port,
            "POST",
            "/api/target",
            body={"target": 5},
            headers={"Authorization": f"Bearer {SYNTHETIC_TOKEN}"},
        )
    assert missing == 401
    assert wrong == 401
    assert correct == 200 and _json(correct_raw)["ok"] is True
    assert node.authority_calls == [(5, "operator_select")]


def test_get_models_is_open_even_with_token_configured():
    with _server(_make_node(control_api_token=SYNTHETIC_TOKEN)) as port:
        status, _h, _r = _request(port, "GET", "/api/models")
    assert status == 200


def test_no_token_on_loopback_preserves_open_control():
    node = _make_node(control_api_token="", subscriber_ready=True)
    with _server(node) as port:
        status, _h, raw = _request(
            port, "POST", "/api/target", body={"target": 5}
        )
    assert status == 200 and _json(raw)["ok"] is True


# --- CORS ---------------------------------------------------------------

def _acao(headers):
    return {k.lower(): v for k, v in headers.items()}.get(
        "access-control-allow-origin"
    )


def test_allowlisted_origin_gets_matching_acao_never_wildcard():
    with _server(_make_node()) as port:
        status, headers, _r = _request(
            port, "GET", "/api/models", headers={"Origin": ALLOWED_ORIGIN}
        )
    assert status == 200
    assert _acao(headers) == ALLOWED_ORIGIN
    assert "*" not in " ".join(headers.values())
    lower = {k.lower() for k in headers}
    assert "vary" in lower


def test_non_allowlisted_origin_gets_no_acao():
    with _server(_make_node()) as port:
        _status, headers, _r = _request(
            port,
            "GET",
            "/api/models",
            headers={"Origin": "http://evil.example"},
        )
    assert _acao(headers) is None


def test_options_preflight_allows_authorization_header_for_allowlisted_origin():
    with _server(_make_node()) as port:
        status, headers, _r = _request(
            port,
            "OPTIONS",
            "/api/target",
            headers={"Origin": ALLOWED_ORIGIN},
        )
    lower = {k.lower(): v for k, v in headers.items()}
    assert status == 204
    assert lower.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert "Authorization" in lower.get("access-control-allow-headers", "")
    assert "*" not in " ".join(headers.values())


def test_empty_allowlist_grants_no_cross_origin():
    with _server(_make_node(cors_origins="")) as port:
        _status, headers, _r = _request(
            port, "GET", "/api/models", headers={"Origin": ALLOWED_ORIGIN}
        )
    assert _acao(headers) is None
