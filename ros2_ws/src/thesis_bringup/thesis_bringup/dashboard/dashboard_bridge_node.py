#!/usr/bin/env python3
"""Dashboard telemetry bridge for the live thesis stack.

This node aggregates runtime status, timing metrics, target/tracker state, and
camera/perception health into browser-facing telemetry for the dashboard UI.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
import json
import os
import subprocess
import threading
import time
from typing import Any
import uuid

from rcl_interfaces.msg import (
    Parameter,
    ParameterType,
    ParameterValue,
)
from rcl_interfaces.srv import SetParameters
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import (
    Empty,
    Float32,
    String,
    UInt32,
)
from thesis_bringup.dashboard.dashboard_models import SUPPORTED_MODELS
from thesis_bringup.dashboard.dashboard_system_metrics import SystemMetricsReader
from thesis_msgs.msg import (
    TargetState,
    Timing,
    Track2DArray,
)
from vision_msgs.msg import Detection2DArray
import websockets


METRICS_SCHEMA_VERSION = 3
DET_OUT_FPS_WINDOW_SECONDS = 3.0
METRIC_WARN_THRESHOLDS_MS = {
    "e2e_det_ms": 120.0,
    "pub_dt_ms": 120.0,
}


class DashboardBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("dashboard_bridge_node")

        self.declare_parameter("tracks_topic", "/tracks")
        self.declare_parameter("detections_topic", "/detections")
        self.declare_parameter("target_topic", "/target")
        self.declare_parameter("validated_target_topic", "/target_memory_mars")
        self.declare_parameter("target_select_topic", "/target_memory_mars/select")
        self.declare_parameter("target_clear_topic", "/target_memory_mars/clear")
        self.declare_parameter("target_memory_status_topic", "/target_memory_mars/status")
        self.declare_parameter("fps_topic", "/camera/fps")
        self.declare_parameter("replay_progress_topic", "/camera/replay_progress")
        self.declare_parameter("timing_topic", "/timing")
        self.declare_parameter("timing_target_topic", "/timing_target")

        self.declare_parameter("ws_host", "0.0.0.0")
        self.declare_parameter("ws_port", 8765)
        self.declare_parameter("api_host", "0.0.0.0")
        self.declare_parameter("api_port", 8090)
        self.declare_parameter("publish_hz", 30.0)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("camera_ref_w", 1280)
        self.declare_parameter("camera_ref_h", 720)
        self.declare_parameter("detector_container_name", "pi-ai-kit-ubuntu-hailo-ubuntu-pi-1")
        self.declare_parameter("detector_bind", "tcp://0.0.0.0:5556")
        self.declare_parameter("detector_width", 640)
        self.declare_parameter("detector_height", 640)
        self.declare_parameter("detector_fps", 30)
        self.declare_parameter("detector_label", "person")
        # Legacy-only control path: restart container detector with a different HEF.
        self.declare_parameter("enable_container_model_switch_api", False)
        self.declare_parameter("perception_node_name", "perception_camera_node")
        thesis_root = os.getenv("THESIS_ROOT", "/home/francisco/Desktop/Thesis-Code")
        self.declare_parameter(
            "integrated_camera_hef_dir",
            f"{thesis_root}/models/hef",
        )
        self.declare_parameter("tracker_node_name", "tracker_node")
        self.declare_parameter("target_memory_node_name", "target_memory_mars_node")
        self.declare_parameter("runtime_reconfiguration_enabled", False)
        self.declare_parameter("target_authority_event_log_path", "")

        self._tracks_topic = str(self.get_parameter("tracks_topic").value)
        self._detections_topic = str(self.get_parameter("detections_topic").value)
        self._target_topic = str(self.get_parameter("target_topic").value)
        self._validated_target_topic = str(
            self.get_parameter("validated_target_topic").value
        )
        self._target_select_topic = str(
            self.get_parameter("target_select_topic").value
        )
        self._target_clear_topic = str(
            self.get_parameter("target_clear_topic").value
        )
        self._target_memory_status_topic = str(
            self.get_parameter("target_memory_status_topic").value
        )
        self._fps_topic = str(self.get_parameter("fps_topic").value)
        self._replay_progress_topic = str(self.get_parameter("replay_progress_topic").value)
        self._timing_topic = str(self.get_parameter("timing_topic").value)
        self._timing_target_topic = str(self.get_parameter("timing_target_topic").value)

        self._ws_host = str(self.get_parameter("ws_host").value)
        self._ws_port = int(self.get_parameter("ws_port").value)
        self._api_host = str(self.get_parameter("api_host").value)
        self._api_port = int(self.get_parameter("api_port").value)
        self._publish_hz = float(self.get_parameter("publish_hz").value)
        self._img_w = max(1.0, float(self.get_parameter("img_w").value))
        self._img_h = max(1.0, float(self.get_parameter("img_h").value))
        self._camera_ref_w = max(1.0, float(self.get_parameter("camera_ref_w").value))
        self._camera_ref_h = max(1.0, float(self.get_parameter("camera_ref_h").value))
        self._detector_container_name = str(self.get_parameter("detector_container_name").value)
        self._detector_bind = str(self.get_parameter("detector_bind").value)
        self._detector_width = int(self.get_parameter("detector_width").value)
        self._detector_height = int(self.get_parameter("detector_height").value)
        self._detector_fps = int(self.get_parameter("detector_fps").value)
        self._detector_label = str(self.get_parameter("detector_label").value)
        self._enable_container_model_switch_api = bool(
            self.get_parameter("enable_container_model_switch_api").value
        )
        self._perception_node_name = (
            str(self.get_parameter("perception_node_name").value).strip()
            or "perception_camera_node"
        )
        self._integrated_camera_hef_dir = str(
            self.get_parameter("integrated_camera_hef_dir").value
        )
        self._tracker_node_name = (
            str(self.get_parameter("tracker_node_name").value).strip()
            or "tracker_node"
        )
        self._target_memory_node_name = (
            str(self.get_parameter("target_memory_node_name").value).strip()
            or "target_memory_mars_node"
        )
        self._runtime_reconfiguration_enabled = bool(
            self.get_parameter("runtime_reconfiguration_enabled").value
        )
        event_log_path = str(
            self.get_parameter("target_authority_event_log_path").value
        ).strip()
        self._target_authority_event_log_path = (
            os.path.abspath(os.path.expanduser(event_log_path))
            if event_log_path
            else ""
        )

        self._supported_models = SUPPORTED_MODELS
        self._model_to_hef = {model.key: model.hef_file for model in self._supported_models}
        self._supported_trackers = {"sort", "ocsort", "bytetrack", "deepsort"}
        self._target_focus_id: int | None = None
        self._target_authority_generation = 0
        self._target_authority_session_id = uuid.uuid4().hex
        self._target_authority_event_lock = threading.Lock()

        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "tracks": [],
            "detections": [],
            "target": None,
            "target_requested": None,
            "target_active": None,
            "target_authority_source": self._validated_target_topic,
            "target_authority_generation": self._target_authority_generation,
            "target_authority_reason": "startup",
            "target_authority_session_id": self._target_authority_session_id,
            "target_authority_event_log_path": self._target_authority_event_log_path,
            "target_memory": None,
            # Explicit telemetry keys (canonical)
            "camera_input_fps": None,
            "det_out_fps": None,
            "e2e_det_ms": None,
            "pub_dt_ms": None,
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "metric_windows": {
                "det_out_fps_seconds": DET_OUT_FPS_WINDOW_SECONDS,
            },
            "metric_thresholds_ms": {
                **METRIC_WARN_THRESHOLDS_MS,
            },
            "replay_progress": None,
            "inference_resolution": {
                "width": int(self._img_w),
                "height": int(self._img_h),
            },
            "system": {
                "cpu_percent": None,
                "mem_percent": None,
                "mem_used_mb": None,
                "temp_c": None,
            },
        }
        self._dirty = False

        self._system_metrics_reader = SystemMetricsReader()
        self._det_arrival_ns: deque[int] = deque(maxlen=240)

        self._tracker_set_params_client = self.create_client(
            SetParameters,
            f"/{self._tracker_node_name}/set_parameters",
        )
        self._perception_set_params_client = self.create_client(
            SetParameters,
            f"/{self._perception_node_name}/set_parameters",
        )

        self._loop = asyncio.new_event_loop()
        self._server = None
        self._ws_clients: set[Any] = set()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

        self._api_server: ThreadingHTTPServer | None = None
        self._api_thread = threading.Thread(target=self._run_api_server, daemon=True)
        self._api_thread.start()

        # Start websocket server asynchronously without blocking ROS thread startup.
        start_future = asyncio.run_coroutine_threadsafe(self._start_server(), self._loop)
        start_future.add_done_callback(self._on_server_start_done)

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        command_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self._target_pub = self.create_publisher(TargetState, self._target_topic, qos)
        self._target_select_pub = self.create_publisher(
            UInt32,
            self._target_select_topic,
            command_qos,
        )
        self._target_clear_pub = self.create_publisher(
            Empty,
            self._target_clear_topic,
            command_qos,
        )
        self._timing_target_pub = self.create_publisher(Timing, self._timing_target_topic, qos)

        self._tracks_sub = self.create_subscription(
            Track2DArray,
            self._tracks_topic,
            self._on_tracks,
            qos,
        )
        self._target_memory_status_sub = self.create_subscription(
            String,
            self._target_memory_status_topic,
            self._on_target_memory_status,
            qos,
        )
        self._detections_sub = self.create_subscription(
            Detection2DArray,
            self._detections_topic,
            self._on_detections,
            qos,
        )
        self._fps_sub = self.create_subscription(Float32, self._fps_topic, self._on_fps, qos)
        self._replay_progress_sub = self.create_subscription(
            Float32,
            self._replay_progress_topic,
            self._on_replay_progress,
            qos,
        )
        self._timing_sub = self.create_subscription(
            Timing,
            self._timing_topic,
            self._on_timing,
            qos,
        )
        self._publish_timer = self.create_timer(
            1.0 / max(self._publish_hz, 1.0),
            self._flush_state_to_clients,
        )
        self._system_timer = self.create_timer(1.0, self._sample_system_metrics)

        self._record_target_authority_event(
            generation=0,
            target_id=None,
            reason="startup",
        )

        self.get_logger().info(
            "dashboard_bridge_node started: "
            f"tracks={self._tracks_topic}, "
            f"detections={self._detections_topic}, "
            f"raw_target={self._target_topic}, "
            f"validated_target={self._validated_target_topic}, "
            f"target_select={self._target_select_topic}, "
            f"target_clear={self._target_clear_topic}, "
            f"fps={self._fps_topic}, "
            f"replay_progress={self._replay_progress_topic}, "
            f"timing={self._timing_topic}, "
            f"timing_target={self._timing_target_topic}, "
            f"ws=ws://{self._ws_host}:{self._ws_port}, "
            f"api=http://{self._api_host}:{self._api_port}, "
            "container_model_switch_api="
            f"{'enabled' if self._enable_container_model_switch_api else 'disabled'}, "
            "runtime_reconfiguration="
            f"{'enabled' if self._runtime_reconfiguration_enabled else 'disabled'}, "
            f"target_authority_session={self._target_authority_session_id}, "
            f"target_authority_event_log={self._target_authority_event_log_path or 'disabled'}, "
            f"integrated_camera_hef_dir={self._integrated_camera_hef_dir}"
        )

    def _run_api_server(self) -> None:
        node_ref = self

        class _ControlHandler(BaseHTTPRequestHandler):
            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self) -> None:
                if self.path == "/api/models":
                    self._send_json(200, node_ref._handle_models_list())
                    return

                self._send_json(404, {"ok": False, "error": "unknown endpoint"})

            def do_POST(self) -> None:
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except Exception:
                    content_length = 0

                raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8")) if raw else {}
                except Exception:
                    self._send_json(400, {"ok": False, "error": "invalid JSON body"})
                    return

                if self.path == "/api/model":
                    model = str(payload.get("model", "")).strip().lower()
                    result = node_ref._handle_model_switch(model)
                    self._send_json(
                        int(
                            result.get(
                                "status_code",
                                200 if result.get("ok") else 500,
                            )
                        ),
                        result,
                    )
                    return

                if self.path == "/api/tracker":
                    tracker = str(payload.get("tracker", "")).strip().lower()
                    result = node_ref._handle_tracker_switch(tracker)
                    self._send_json(
                        int(
                            result.get(
                                "status_code",
                                200 if result.get("ok") else 500,
                            )
                        ),
                        result,
                    )
                    return

                if self.path == "/api/target":
                    result = node_ref._handle_target_focus(payload.get("target"))
                    self._send_json(
                        int(
                            result.get(
                                "status_code",
                                200 if result.get("ok") else 500,
                            )
                        ),
                        result,
                    )
                    return

                self._send_json(404, {"ok": False, "error": "unknown endpoint"})

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        try:
            self._api_server = ThreadingHTTPServer(
                (self._api_host, self._api_port),
                _ControlHandler,
            )
            self._api_server.serve_forever()
        except Exception as exc:
            self.get_logger().error(f"Control API server failed: {exc}")

    def _handle_models_list(self) -> dict[str, Any]:
        models = []
        for model in self._supported_models:
            hef_path = os.path.join(self._integrated_camera_hef_dir, model.hef_file)
            models.append(
                {
                    "key": model.key,
                    "hef_file": model.hef_file,
                    "hef_path": hef_path,
                    "available": os.path.isfile(hef_path),
                }
            )

        return {
            "ok": True,
            "models": models,
        }

    def _handle_model_switch(self, model: str) -> dict[str, Any]:
        if model not in self._model_to_hef:
            return {"ok": False, "error": f"unsupported model: {model}", "status_code": 400}

        authority_generation = self._apply_target_authority_request(
            None,
            reason=f"model_switch:{model}",
        )

        if not self._runtime_reconfiguration_enabled:
            return {
                "ok": False,
                "error": (
                    "runtime model switching is disabled in the frozen live profile; "
                    "restart the stack with an explicitly validated model"
                ),
                "target_authority_generation": authority_generation,
                "status_code": 409,
            }

        # Prefer integrated-camera model switch when the perception node is available.
        integrated_camera_result = self._handle_integrated_camera_model_switch(model)
        if integrated_camera_result is not None:
            integrated_camera_result["target_authority_generation"] = (
                authority_generation
            )
            return integrated_camera_result

        if self._enable_container_model_switch_api:
            container_result = self._handle_container_model_switch(model)
            container_result["target_authority_generation"] = authority_generation
            return container_result

        return {
            "ok": False,
            "error": (
                "model switch unavailable: perception parameter service not reachable "
                "and container model switch API is disabled"
            ),
            "status_code": 503,
        }

    def _handle_integrated_camera_model_switch(self, model: str) -> dict[str, Any] | None:
        if not self._perception_set_params_client.wait_for_service(timeout_sec=0.25):
            return None

        hef_name = self._model_to_hef[model]
        hef_path = os.path.join(self._integrated_camera_hef_dir, hef_name)
        if not os.path.isfile(hef_path):
            return {
                "ok": False,
                "error": f"HEF file not found for model '{model}': {hef_path}",
                "status_code": 500,
            }

        request = SetParameters.Request()
        request.parameters = [
            Parameter(
                name="hailo_hef_path",
                value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=hef_path),
            )
        ]

        try:
            future = self._perception_set_params_client.call_async(request)
            deadline = time.monotonic() + 8.0
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.01)
        except Exception as exc:
            self.get_logger().error(f"Integrated-camera model switch execution failed: {exc}")
            return {"ok": False, "error": f"model switch failed: {exc}", "status_code": 500}

        if not future.done():
            return {"ok": False, "error": "model switch timed out", "status_code": 504}

        result = future.result()
        if result is None:
            return {"ok": False, "error": "model switch returned no response", "status_code": 500}

        if not result.results:
            return {"ok": False, "error": "model switch returned empty result", "status_code": 500}

        set_result = result.results[0]
        if not set_result.successful:
            reason = set_result.reason or "unknown model switch failure"
            return {"ok": False, "error": reason, "status_code": 500}

        self.get_logger().info(f"Integrated-camera model switch applied: {model} ({hef_name})")
        return {
            "ok": True,
            "requested_model": model,
            "hef_path": hef_path,
            "mode": "integrated-camera",
            "status_code": 200,
        }

    def _handle_container_model_switch(self, model: str) -> dict[str, Any]:
        hef_name = self._model_to_hef[model]

        cmd = """
echo "container model switching is not supported in the integrated-camera thesis repository" >&2
echo "use perception_camera_node launched by tools/start_live_stack.sh" >&2
exit 1
"""

        try:
            result = subprocess.run(
                ["docker", "exec", self._detector_container_name, "bash", "-lc", cmd],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
            )
        except Exception as exc:
            self.get_logger().error(f"Model switch execution failed: {exc}")
            return {"ok": False, "error": f"model switch failed: {exc}", "status_code": 500}

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            self.get_logger().error(f"Model switch command failed (model={model}): {stderr}")
            return {
                "ok": False,
                "error": f"model switch command failed: {stderr}",
                "status_code": 500,
            }

        self.get_logger().info(f"Model switch applied: {model} ({hef_name})")
        return {
            "ok": True,
            "requested_model": model,
            "mode": "container-switching-removed",
            "status_code": 200,
        }

    def _handle_tracker_switch(self, tracker: str) -> dict[str, Any]:
        if tracker not in self._supported_trackers:
            return {
                "ok": False,
                "error": f"unsupported tracker: {tracker}",
                "status_code": 400,
            }

        authority_generation = self._apply_target_authority_request(
            None,
            reason=f"tracker_switch:{tracker}",
        )

        if not self._runtime_reconfiguration_enabled:
            return {
                "ok": False,
                "error": (
                    "runtime tracker switching is disabled in the frozen live profile; "
                    "restart the stack with an explicitly validated tracker"
                ),
                "target_authority_generation": authority_generation,
                "status_code": 409,
            }

        if not self._tracker_set_params_client.wait_for_service(timeout_sec=1.0):
            return {
                "ok": False,
                "error": (
                    "tracker parameter service unavailable on "
                    f"/{self._tracker_node_name}/set_parameters"
                ),
                "status_code": 503,
            }

        request = SetParameters.Request()
        request.parameters = [
            Parameter(
                name="tracker_type",
                value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=tracker),
            )
        ]

        try:
            future = self._tracker_set_params_client.call_async(request)
            deadline = time.monotonic() + 3.0
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.01)
        except Exception as exc:
            self.get_logger().error(f"Tracker switch execution failed: {exc}")
            return {
                "ok": False,
                "error": f"tracker switch failed: {exc}",
                "status_code": 500,
            }

        if not future.done():
            return {
                "ok": False,
                "error": "tracker switch timed out",
                "status_code": 504,
            }

        result = future.result()
        if result is None:
            return {
                "ok": False,
                "error": "tracker switch returned no response",
                "status_code": 500,
            }

        if not result.results:
            return {
                "ok": False,
                "error": "tracker switch returned empty result",
                "status_code": 500,
            }

        set_result = result.results[0]
        if not set_result.successful:
            reason = set_result.reason or "unknown tracker switch failure"
            return {"ok": False, "error": reason, "status_code": 500}

        self.get_logger().info(f"Tracker backend switch applied: {tracker}")
        return {
            "ok": True,
            "requested_tracker": tracker,
            "target_authority_generation": authority_generation,
            "status_code": 200,
        }

    def _handle_target_focus(self, target_value: Any) -> dict[str, Any]:
        target_id, error = self._parse_target_focus_id(target_value)
        if error is not None:
            return {"ok": False, "error": error, "status_code": 400}

        command_topic = (
            self._target_select_topic
            if target_id is not None
            else self._target_clear_topic
        )
        if not self._target_command_subscriber_ready(command_topic):
            self._publish_immediate_target_reset()
            return {
                "ok": False,
                "error": "TIM-MARS command subscriber is unavailable",
                "target_authority_source": self._validated_target_topic,
                "status_code": 503,
            }

        authority_generation = self._apply_target_authority_request(
            target_id,
            reason="operator_select" if target_id is not None else "operator_clear",
        )

        requested_label = "CLEAR" if target_id is None else str(target_id)
        self.get_logger().info(f"Target focus updated: {requested_label}")
        return {
            "ok": True,
            "requested_target": target_id,
            "action": "select" if target_id is not None else "clear",
            "target_authority_source": self._validated_target_topic,
            "target_authority_generation": authority_generation,
            "status_code": 200,
        }

    def _target_command_subscriber_ready(self, topic_name: str) -> bool:
        """Return true only when the TIM node owns a command subscription."""
        return any(
            endpoint.node_name == self._target_memory_node_name
            for endpoint in self.get_subscriptions_info_by_topic(topic_name)
        )

    def _apply_target_authority_request(
        self,
        target_id: int | None,
        *,
        reason: str,
    ) -> int:
        """Reset raw output and command the authoritative TIM-MARS target."""
        with self._state_lock:
            self._target_focus_id = target_id
            self._target_authority_generation += 1
            authority_generation = self._target_authority_generation
            self._state["target"] = int(target_id) if target_id is not None else 0
            self._state["target_requested"] = (
                int(target_id) if target_id is not None else None
            )
            self._state["target_active"] = 0
            self._state["target_authority_generation"] = authority_generation
            self._state["target_authority_reason"] = str(reason)
            self._dirty = True

        self._publish_immediate_target_reset()
        self._publish_target_authority_command(target_id)
        self._record_target_authority_event(
            generation=authority_generation,
            target_id=target_id,
            reason=reason,
        )
        return authority_generation

    def _record_target_authority_event(
        self,
        *,
        generation: int,
        target_id: int | None,
        reason: str,
    ) -> None:
        """Append one durable authority transition to the live-run JSONL log."""
        if not self._target_authority_event_log_path:
            return

        payload = {
            "schema_version": 1,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            "authority_source": self._validated_target_topic,
            "session_id": self._target_authority_session_id,
            "generation": int(generation),
            "reason": str(reason),
            "requested_target_id": (
                int(target_id) if target_id is not None else None
            ),
            "authority_state": (
                "selection_requested" if target_id is not None else "cleared"
            ),
        }
        encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")

        try:
            parent = os.path.dirname(self._target_authority_event_log_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with self._target_authority_event_lock:
                descriptor = os.open(
                    self._target_authority_event_log_path,
                    os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                    0o640,
                )
                try:
                    os.write(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except OSError as exc:
            self.get_logger().error(
                "Could not persist target-authority event "
                f"to {self._target_authority_event_log_path}: {exc}"
            )

    def _publish_target_authority_command(self, target_id: int | None) -> None:
        """Publish one explicit TIM-MARS select or clear command."""
        if target_id is None:
            self._target_clear_pub.publish(Empty())
            return

        msg = UInt32()
        msg.data = int(target_id)
        self._target_select_pub.publish(msg)

    @staticmethod
    def _parse_target_focus_id(target_value: Any) -> tuple[int | None, str | None]:
        if target_value is None:
            return None, None

        if isinstance(target_value, bool):
            return None, "target must be an integer id or null"

        if isinstance(target_value, int):
            target_id = int(target_value)
        elif isinstance(target_value, float):
            if not target_value.is_integer():
                return None, "target must be an integer id or null"
            target_id = int(target_value)
        elif isinstance(target_value, str):
            text = target_value.strip().lower()
            if text in {"", "null", "none", "auto"}:
                return None, None
            try:
                target_id = int(text)
            except Exception:
                return None, "target must be an integer id or null"
        else:
            return None, "target must be an integer id or null"

        if target_id == 0:
            return None, None
        if target_id < 0:
            return None, "target must be >= 1 or null"
        return target_id, None

    @staticmethod
    def _sensor_to_target_ms_if_comparable(
        src_stamp_ns: int,
        t_target_cb_end_ns: int,
    ) -> float | None:
        if src_stamp_ns <= 0:
            return None

        delta_ns = int(t_target_cb_end_ns) - int(src_stamp_ns)
        if 0 <= delta_ns <= 60_000_000_000:
            return float(delta_ns) / 1e6
        return None

    def _publish_immediate_target_reset(self) -> None:
        now_ns = time.monotonic_ns()

        target_msg = TargetState()
        target_msg.frame_id = 0
        target_msg.src_stamp_ns = 0
        target_msg.t_cam_msg_seen_ns = 0
        target_msg.t_target_cb_start_ns = int(now_ns)
        target_msg.t_target_cb_end_ns = int(now_ns)
        target_msg.id = 0
        target_msg.cx = 0.0
        target_msg.cy = 0.0
        target_msg.w = 0.0
        target_msg.h = 0.0
        target_msg.score = 0.0
        target_msg.quality = 0.0
        self._target_pub.publish(target_msg)

        timing_msg = Timing()
        timing_msg.frame_id = 0
        timing_msg.t_target_cb_start_ns = int(now_ns)
        timing_msg.t_target_cb_end_ns = int(now_ns)
        timing_msg.target_ms = 0.0
        self._timing_target_pub.publish(timing_msg)

    def _publish_target_from_tracks(self, msg: Track2DArray) -> TargetState:
        with self._state_lock:
            focus_id = self._target_focus_id

        selected_track = None
        if focus_id is not None:
            for track in msg.tracks:
                if int(track.id) == int(focus_id):
                    selected_track = track
                    break

        t_target_cb_start_ns = time.monotonic_ns()

        target_msg = TargetState()
        target_msg.header = msg.header
        target_msg.frame_id = int(msg.frame_id)
        target_msg.src_stamp_ns = int(msg.src_stamp_ns)
        target_msg.t_cam_msg_seen_ns = int(msg.t_cam_msg_seen_ns)
        target_msg.t_target_cb_start_ns = int(t_target_cb_start_ns)

        if selected_track is None:
            target_msg.id = 0
            target_msg.cx = 0.0
            target_msg.cy = 0.0
            target_msg.w = 0.0
            target_msg.h = 0.0
            target_msg.score = 0.0
            target_msg.quality = 0.0
        else:
            target_msg.id = int(selected_track.id)
            target_msg.cx = float(selected_track.cx)
            target_msg.cy = float(selected_track.cy)
            target_msg.w = float(selected_track.w)
            target_msg.h = float(selected_track.h)
            target_msg.score = float(selected_track.score)
            target_msg.quality = 1.0

        t_target_cb_end_ns = time.monotonic_ns()
        target_msg.t_target_cb_end_ns = int(t_target_cb_end_ns)
        self._target_pub.publish(target_msg)

        timing_msg = Timing()
        timing_msg.frame_id = int(msg.frame_id)
        timing_msg.src_stamp_ns = int(msg.src_stamp_ns)
        timing_msg.t_cam_msg_seen_ns = int(msg.t_cam_msg_seen_ns)
        timing_msg.t_target_cb_start_ns = int(t_target_cb_start_ns)
        timing_msg.t_target_cb_end_ns = int(t_target_cb_end_ns)
        timing_msg.target_ms = float((t_target_cb_end_ns - t_target_cb_start_ns) / 1e6)
        if timing_msg.t_cam_msg_seen_ns > 0 and t_target_cb_end_ns >= timing_msg.t_cam_msg_seen_ns:
            timing_msg.e2e_target_ms = float(
                (t_target_cb_end_ns - timing_msg.t_cam_msg_seen_ns) / 1e6
            )
        sensor_ms = self._sensor_to_target_ms_if_comparable(
            int(msg.src_stamp_ns),
            t_target_cb_end_ns,
        )
        if sensor_ms is not None:
            timing_msg.sensor_to_target_ms = sensor_ms
        self._timing_target_pub.publish(timing_msg)

        return target_msg

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _start_server(self) -> None:
        self._server = await websockets.serve(
            self._handle_client,
            self._ws_host,
            self._ws_port,
            ping_interval=20,
            ping_timeout=20,
            max_queue=4,
        )

    def _on_server_start_done(self, future) -> None:
        try:
            future.result()
        except Exception as exc:
            self.get_logger().error(f"WebSocket server start failed: {exc}")

    async def _handle_client(self, websocket, _path=None) -> None:
        self._ws_clients.add(websocket)

        # Send current snapshot immediately when a dashboard connects.
        payload = self._snapshot_json()
        await websocket.send(payload)

        try:
            await websocket.wait_closed()
        finally:
            self._ws_clients.discard(websocket)

    def _flush_state_to_clients(self) -> None:
        with self._state_lock:
            if not self._dirty:
                return
            payload = json.dumps(self._state, separators=(",", ":"))
            self._dirty = False

        if not self._loop.is_running():
            return

        future = asyncio.run_coroutine_threadsafe(self._broadcast_payload(payload), self._loop)
        future.add_done_callback(self._on_broadcast_done)

    async def _broadcast_payload(self, payload: str) -> None:
        if not self._ws_clients:
            return

        clients_snapshot = list(self._ws_clients)
        send_tasks = [websocket.send(payload) for websocket in clients_snapshot]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        for websocket, result in zip(clients_snapshot, results):
            if isinstance(result, Exception):
                self._ws_clients.discard(websocket)

    def _on_broadcast_done(self, future) -> None:
        try:
            future.result()
        except Exception as exc:
            self.get_logger().error(f"WebSocket broadcast failed: {exc}")

    def _snapshot_json(self) -> str:
        with self._state_lock:
            camera_input_fps = self._state["camera_input_fps"]
            det_out_fps = self._state["det_out_fps"]
            e2e_det_ms = self._state["e2e_det_ms"]
            snapshot = {
                "tracks": [dict(t) for t in self._state["tracks"]],
                "detections": [dict(d) for d in self._state["detections"]],
                "target": self._state["target"],
                "target_requested": self._state["target_requested"],
                "target_active": self._state["target_active"],
                "target_authority_source": self._state[
                    "target_authority_source"
                ],
                "target_authority_generation": self._state[
                    "target_authority_generation"
                ],
                "target_authority_reason": self._state[
                    "target_authority_reason"
                ],
                "target_authority_session_id": self._state[
                    "target_authority_session_id"
                ],
                "target_authority_event_log_path": self._state[
                    "target_authority_event_log_path"
                ],
                "target_memory": self._state.get("target_memory"),
                "camera_input_fps": camera_input_fps,
                "det_out_fps": det_out_fps,
                "e2e_det_ms": e2e_det_ms,
                "pub_dt_ms": self._state["pub_dt_ms"],
                "metrics_schema_version": self._state["metrics_schema_version"],
                "metric_windows": dict(self._state["metric_windows"]),
                "metric_thresholds_ms": dict(self._state["metric_thresholds_ms"]),
                "replay_progress": self._state["replay_progress"],
                "inference_resolution": dict(self._state["inference_resolution"]),
                "system": dict(self._state["system"]),
            }
        return json.dumps(snapshot, separators=(",", ":"))

    @staticmethod
    def _clamp01(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _map_bbox_to_stream_norm(
        self,
        cx: float,
        cy: float,
        w: float,
        h: float,
    ) -> tuple[float, float, float, float]:
        ref_w = max(1.0, self._camera_ref_w)
        ref_h = max(1.0, self._camera_ref_h)

        return (
            self._clamp01(cx / ref_w),
            self._clamp01(cy / ref_h),
            self._clamp01(w / ref_w),
            self._clamp01(h / ref_h),
        )

    def _on_target_memory_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception:
            payload = {"raw": msg.data, "parse_error": True}

        with self._state_lock:
            self._state["target_memory"] = payload
            self._dirty = True

    def _on_tracks(self, msg: Track2DArray) -> None:
        tracks = []
        for track in msg.tracks:
            x, y, w, h = self._map_bbox_to_stream_norm(
                float(track.cx),
                float(track.cy),
                float(track.w),
                float(track.h),
            )
            tracks.append(
                {
                    "id": int(track.id),
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                }
            )

        target_msg = self._publish_target_from_tracks(msg)

        with self._state_lock:
            self._state["tracks"] = tracks
            self._state["target"] = int(target_msg.id)
            self._state["target_active"] = int(target_msg.id)
            self._dirty = True

    def _on_detections(self, msg: Detection2DArray) -> None:
        now_ns = time.monotonic_ns()
        self._det_arrival_ns.append(now_ns)

        # Keep a short rolling window to smooth bursty callback timings.
        window_ns = 3_000_000_000
        cutoff_ns = now_ns - window_ns
        while self._det_arrival_ns and self._det_arrival_ns[0] < cutoff_ns:
            self._det_arrival_ns.popleft()

        det_out_fps = None
        if len(self._det_arrival_ns) >= 2:
            dt_ns = self._det_arrival_ns[-1] - self._det_arrival_ns[0]
            if dt_ns > 0:
                # Derived from local callback cadence (host monotonic domain).
                det_out_fps = (len(self._det_arrival_ns) - 1) / (dt_ns / 1e9)

        detections = []
        for det in msg.detections:
            cx = float(det.bbox.center.position.x)
            cy = float(det.bbox.center.position.y)
            w = float(det.bbox.size_x)
            h = float(det.bbox.size_y)

            det_label = ""
            det_score = 0.0
            if det.results:
                det_label = str(det.results[0].hypothesis.class_id)
                det_score = float(det.results[0].hypothesis.score)

            x, y, w_norm, h_norm = self._map_bbox_to_stream_norm(cx, cy, w, h)

            detections.append(
                {
                    "x": x,
                    "y": y,
                    "w": w_norm,
                    "h": h_norm,
                    "label": det_label,
                    "score": det_score,
                }
            )

        with self._state_lock:
            self._state["detections"] = detections
            if det_out_fps is not None:
                self._state["det_out_fps"] = det_out_fps
            self._dirty = True

    def _on_fps(self, msg: Float32) -> None:
        with self._state_lock:
            value = float(msg.data)
            self._state["camera_input_fps"] = value
            self._dirty = True

    def _on_replay_progress(self, msg: Float32) -> None:
        with self._state_lock:
            value = float(msg.data)
            self._state["replay_progress"] = max(0.0, min(1.0, value))
            self._dirty = True

    def _on_timing(self, msg: Timing) -> None:
        with self._state_lock:
            if int(msg.image_width) > 0 and int(msg.image_height) > 0:
                self._camera_ref_w = float(msg.image_width)
                self._camera_ref_h = float(msg.image_height)
            e2e_det_ms = float(msg.e2e_det_ms)
            self._state["e2e_det_ms"] = e2e_det_ms
            pub_dt_ms = float(msg.pub_dt_ms)
            # pub_dt_ms is the canonical cadence interval from /timing in host monotonic domain.
            self._state["pub_dt_ms"] = pub_dt_ms
            self._dirty = True

    def _sample_system_metrics(self) -> None:
        cpu_percent = self._system_metrics_reader.read_cpu_percent()
        mem_percent, mem_used_mb = self._system_metrics_reader.read_memory_metrics()
        temp_c = self._system_metrics_reader.read_cpu_temp_c()

        with self._state_lock:
            self._state["system"] = {
                "cpu_percent": cpu_percent,
                "mem_percent": mem_percent,
                "mem_used_mb": mem_used_mb,
                "temp_c": temp_c,
            }
            self._dirty = True

    async def _shutdown_server(self) -> None:
        clients_snapshot = list(self._ws_clients)
        if clients_snapshot:
            close_tasks = [client.close() for client in clients_snapshot]
            await asyncio.gather(*close_tasks, return_exceptions=True)
        self._ws_clients.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def destroy_node(self):
        if self._api_server is not None:
            try:
                self._api_server.shutdown()
                self._api_server.server_close()
            except Exception:
                pass

        if self._api_thread.is_alive():
            self._api_thread.join(timeout=2.0)

        if self._loop.is_running():
            close_future = asyncio.run_coroutine_threadsafe(self._shutdown_server(), self._loop)
            try:
                close_future.result(timeout=2.0)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)

        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DashboardBridgeNode()

    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
