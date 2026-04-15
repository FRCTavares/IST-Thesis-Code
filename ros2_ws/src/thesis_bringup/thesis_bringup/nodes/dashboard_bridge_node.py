#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import rclpy
import websockets
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParameters
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import Float32
from vision_msgs.msg import Detection2DArray
from thesis_msgs.msg import TargetState, Timing, Track2DArray


class DashboardBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("dashboard_bridge_node")

        self.declare_parameter("tracks_topic", "/tracks")
        self.declare_parameter("detections_topic", "/detections")
        self.declare_parameter("target_topic", "/target")
        self.declare_parameter("fps_topic", "/camera/fps")
        self.declare_parameter("replay_progress_topic", "/camera/replay_progress")
        self.declare_parameter("timing_topic", "/timing")

        self.declare_parameter("ws_host", "0.0.0.0")
        self.declare_parameter("ws_port", 8765)
        self.declare_parameter("api_host", "0.0.0.0")
        self.declare_parameter("api_port", 8090)
        self.declare_parameter("publish_hz", 30.0)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("detector_container_name", "pi-ai-kit-ubuntu-hailo-ubuntu-pi-1")
        self.declare_parameter("detector_bind", "tcp://0.0.0.0:5556")
        self.declare_parameter("detector_width", 640)
        self.declare_parameter("detector_height", 640)
        self.declare_parameter("detector_fps", 30)
        self.declare_parameter("detector_label", "person")
        # Legacy-only control path: restart container detector with a different HEF.
        self.declare_parameter("enable_container_model_switch_api", False)
        self.declare_parameter("perception_node_name", "perception_pipeline_node")
        thesis_root = os.getenv("THESIS_ROOT", "/home/francisco/Desktop/Thesis-Code")
        self.declare_parameter(
            "single_process_hef_dir",
            f"{thesis_root}/infer_service/resources/hefs",
        )
        self.declare_parameter("tracker_node_name", "tracker_node")

        self._tracks_topic = str(self.get_parameter("tracks_topic").value)
        self._detections_topic = str(self.get_parameter("detections_topic").value)
        self._target_topic = str(self.get_parameter("target_topic").value)
        self._fps_topic = str(self.get_parameter("fps_topic").value)
        self._replay_progress_topic = str(self.get_parameter("replay_progress_topic").value)
        self._timing_topic = str(self.get_parameter("timing_topic").value)

        self._ws_host = str(self.get_parameter("ws_host").value)
        self._ws_port = int(self.get_parameter("ws_port").value)
        self._api_host = str(self.get_parameter("api_host").value)
        self._api_port = int(self.get_parameter("api_port").value)
        self._publish_hz = float(self.get_parameter("publish_hz").value)
        self._img_w = max(1.0, float(self.get_parameter("img_w").value))
        self._img_h = max(1.0, float(self.get_parameter("img_h").value))
        self._detector_container_name = str(self.get_parameter("detector_container_name").value)
        self._detector_bind = str(self.get_parameter("detector_bind").value)
        self._detector_width = int(self.get_parameter("detector_width").value)
        self._detector_height = int(self.get_parameter("detector_height").value)
        self._detector_fps = int(self.get_parameter("detector_fps").value)
        self._detector_label = str(self.get_parameter("detector_label").value)
        self._enable_container_model_switch_api = bool(
            self.get_parameter("enable_container_model_switch_api").value
        )
        self._perception_node_name = str(self.get_parameter("perception_node_name").value).strip() or "perception_pipeline_node"
        self._single_process_hef_dir = str(self.get_parameter("single_process_hef_dir").value)
        self._tracker_node_name = str(self.get_parameter("tracker_node_name").value).strip() or "tracker_node"

        self._model_to_hef = {
            "yolov6n": "yolov6n_hailo8.hef",
            "yolov8s": "yolov8s.hef",
            "yolov8m": "yolov8m.hef",
        }
        self._supported_trackers = {"sort", "ocsort", "bytetrack"}

        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "tracks": [],
            "detections": [],
            "target": None,
            "fps": None,
            "video_fps": None,
            "replay_progress": None,
            "det_fps": None,
            "latency_ms": None,
            "system": {
                "cpu_percent": None,
                "mem_percent": None,
                "mem_used_mb": None,
                "temp_c": None,
            },
        }
        self._dirty = False

        self._last_cpu_total = None
        self._last_cpu_idle = None
        self._det_arrival_ns: deque[int] = deque(maxlen=240)

        self._stop_event = threading.Event()
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

        self._tracks_sub = self.create_subscription(Track2DArray, self._tracks_topic, self._on_tracks, qos)
        self._detections_sub = self.create_subscription(Detection2DArray, self._detections_topic, self._on_detections, qos)
        self._target_sub = self.create_subscription(TargetState, self._target_topic, self._on_target, qos)
        self._fps_sub = self.create_subscription(Float32, self._fps_topic, self._on_fps, qos)
        self._replay_progress_sub = self.create_subscription(Float32, self._replay_progress_topic, self._on_replay_progress, qos)
        self._timing_sub = self.create_subscription(Timing, self._timing_topic, self._on_timing, qos)
        self._publish_timer = self.create_timer(1.0 / max(self._publish_hz, 1.0), self._flush_state_to_clients)
        self._system_timer = self.create_timer(1.0, self._sample_system_metrics)

        self.get_logger().info(
            "dashboard_bridge_node started: "
            f"tracks={self._tracks_topic}, detections={self._detections_topic}, target={self._target_topic}, "
            f"fps={self._fps_topic}, replay_progress={self._replay_progress_topic}, timing={self._timing_topic}, "
            f"ws=ws://{self._ws_host}:{self._ws_port}, api=http://{self._api_host}:{self._api_port}, "
            f"container_model_switch_api={'enabled' if self._enable_container_model_switch_api else 'disabled'}, "
            f"single_process_hef_dir={self._single_process_hef_dir}"
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
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

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
                    self._send_json(int(result.get("status_code", 200 if result.get("ok") else 500)), result)
                    return

                if self.path == "/api/tracker":
                    tracker = str(payload.get("tracker", "")).strip().lower()
                    result = node_ref._handle_tracker_switch(tracker)
                    self._send_json(200 if result.get("ok") else 500, result)
                    return

                if self.path == "/api/replay":
                    self._send_json(200, {"ok": False, "error": "replay control not implemented in live mode"})
                    return

                self._send_json(404, {"ok": False, "error": "unknown endpoint"})

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        try:
            self._api_server = ThreadingHTTPServer((self._api_host, self._api_port), _ControlHandler)
            self._api_server.serve_forever()
        except Exception as exc:
            self.get_logger().error(f"Control API server failed: {exc}")

    def _handle_model_switch(self, model: str) -> dict[str, Any]:
        if model not in self._model_to_hef:
            return {"ok": False, "error": f"unsupported model: {model}", "status_code": 400}

        # Prefer single-process model switch when the perception node is available.
        single_process_result = self._handle_single_process_model_switch(model)
        if single_process_result is not None:
            return single_process_result

        if self._enable_container_model_switch_api:
            return self._handle_container_model_switch(model)

        return {
            "ok": False,
            "error": (
                "model switch unavailable: perception parameter service not reachable "
                "and container model switch API is disabled"
            ),
            "status_code": 503,
        }

    def _handle_single_process_model_switch(self, model: str) -> dict[str, Any] | None:
        if not self._perception_set_params_client.wait_for_service(timeout_sec=0.25):
            return None

        hef_name = self._model_to_hef[model]
        hef_path = os.path.join(self._single_process_hef_dir, hef_name)
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
            self.get_logger().error(f"Single-process model switch execution failed: {exc}")
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

        self.get_logger().info(f"Single-process model switch applied: {model} ({hef_name})")
        return {
            "ok": True,
            "requested_model": model,
            "hef_path": hef_path,
            "mode": "single-process",
            "status_code": 200,
        }

    def _handle_container_model_switch(self, model: str) -> dict[str, Any]:
        hef_name = self._model_to_hef[model]

        hef_path = f"/root/thesis_service/resources/hefs/{hef_name}"

        cmd = f"""
set -euo pipefail
for pid in $(pgrep -f '/root/thesis_service/detection_zmq.py$' || true); do
  if [ "$pid" != "$$" ]; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
done
VENV=/root/hailo-rpi5-examples/venv_hailo_rpi_examples
export PYTHONPATH=/root/hailo-rpi5-examples:${{PYTHONPATH:-}}
cd /root/thesis_service
export HAILO_FRAME_SOURCE=ros
export HAILO_REQREP_BIND={self._detector_bind}
export HAILO_INFER_WIDTH={self._detector_width}
export HAILO_INFER_HEIGHT={self._detector_height}
export HAILO_INFER_FPS={self._detector_fps}
export HAILO_VIDEO_SINK=fakesink
export HAILO_POST_FUNC=filter
export HAILO_DET_LABEL={self._detector_label}
export HAILO_HEF_PATH={hef_path}
nohup "$VENV/bin/python" /root/thesis_service/detection_zmq.py > /tmp/detection_zmq_live.log 2>&1 &
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
            "mode": "legacy-container",
            "status_code": 200,
        }

    def _handle_tracker_switch(self, tracker: str) -> dict[str, Any]:
        if tracker not in self._supported_trackers:
            return {
                "ok": False,
                "error": f"unsupported tracker: {tracker}",
            }

        if not self._tracker_set_params_client.wait_for_service(timeout_sec=1.0):
            return {
                "ok": False,
                "error": f"tracker parameter service unavailable on /{self._tracker_node_name}/set_parameters",
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
            return {"ok": False, "error": f"tracker switch failed: {exc}"}

        if not future.done():
            return {"ok": False, "error": "tracker switch timed out"}

        result = future.result()
        if result is None:
            return {"ok": False, "error": "tracker switch returned no response"}

        if not result.results:
            return {"ok": False, "error": "tracker switch returned empty result"}

        set_result = result.results[0]
        if not set_result.successful:
            reason = set_result.reason or "unknown tracker switch failure"
            return {"ok": False, "error": reason}

        self.get_logger().info(f"Tracker backend switch applied: {tracker}")
        return {"ok": True, "requested_tracker": tracker}

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
            snapshot = {
                "tracks": [dict(t) for t in self._state["tracks"]],
                "detections": [dict(d) for d in self._state["detections"]],
                "target": self._state["target"],
                "fps": self._state["fps"],
                "video_fps": self._state["video_fps"],
                "replay_progress": self._state["replay_progress"],
                "det_fps": self._state["det_fps"],
                "latency_ms": self._state["latency_ms"],
                "system": dict(self._state["system"]),
            }
        return json.dumps(snapshot, separators=(",", ":"))

    def _on_tracks(self, msg: Track2DArray) -> None:
        tracks = [
            {
                "id": int(track.id),
                "x": float(track.cx) / self._img_w,
                "y": float(track.cy) / self._img_h,
                "w": float(track.w) / self._img_w,
                "h": float(track.h) / self._img_h,
            }
            for track in msg.tracks
        ]
        with self._state_lock:
            self._state["tracks"] = tracks
            self._dirty = True

    def _on_detections(self, msg: Detection2DArray) -> None:
        now_ns = time.monotonic_ns()
        self._det_arrival_ns.append(now_ns)

        # Keep a short rolling window to smooth bursty callback timings.
        window_ns = 3_000_000_000
        cutoff_ns = now_ns - window_ns
        while self._det_arrival_ns and self._det_arrival_ns[0] < cutoff_ns:
            self._det_arrival_ns.popleft()

        det_fps = None
        if len(self._det_arrival_ns) >= 2:
            dt_ns = self._det_arrival_ns[-1] - self._det_arrival_ns[0]
            if dt_ns > 0:
                det_fps = (len(self._det_arrival_ns) - 1) / (dt_ns / 1e9)

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

            detections.append(
                {
                    "x": cx / self._img_w,
                    "y": cy / self._img_h,
                    "w": w / self._img_w,
                    "h": h / self._img_h,
                    "label": det_label,
                    "score": det_score,
                }
            )

        with self._state_lock:
            self._state["detections"] = detections
            if det_fps is not None:
                self._state["det_fps"] = det_fps
            self._dirty = True

    def _on_target(self, msg: TargetState) -> None:
        with self._state_lock:
            self._state["target"] = int(msg.id)
            self._dirty = True

    def _on_fps(self, msg: Float32) -> None:
        with self._state_lock:
            value = float(msg.data)
            self._state["fps"] = value
            self._state["video_fps"] = value
            self._dirty = True

    def _on_replay_progress(self, msg: Float32) -> None:
        with self._state_lock:
            value = float(msg.data)
            self._state["replay_progress"] = max(0.0, min(1.0, value))
            self._dirty = True

    def _on_timing(self, msg: Timing) -> None:
        with self._state_lock:
            self._state["latency_ms"] = float(msg.e2e_det_ms)
            self._dirty = True

    def _sample_system_metrics(self) -> None:
        cpu_percent = self._read_cpu_percent()
        mem_percent, mem_used_mb = self._read_memory_metrics()
        temp_c = self._read_cpu_temp_c()

        with self._state_lock:
            self._state["system"] = {
                "cpu_percent": cpu_percent,
                "mem_percent": mem_percent,
                "mem_used_mb": mem_used_mb,
                "temp_c": temp_c,
            }
            self._dirty = True

    def _read_cpu_percent(self) -> float | None:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline().strip()
        except Exception:
            return None

        parts = line.split()
        if len(parts) < 5 or parts[0] != "cpu":
            return None

        try:
            values = [int(v) for v in parts[1:]]
        except Exception:
            return None

        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)

        if self._last_cpu_total is None or self._last_cpu_idle is None:
            self._last_cpu_total = total
            self._last_cpu_idle = idle
            return None

        delta_total = total - self._last_cpu_total
        delta_idle = idle - self._last_cpu_idle

        self._last_cpu_total = total
        self._last_cpu_idle = idle

        if delta_total <= 0:
            return None

        usage = 100.0 * (1.0 - (float(delta_idle) / float(delta_total)))
        return max(0.0, min(100.0, usage))

    def _read_memory_metrics(self) -> tuple[float | None, float | None]:
        mem_total_kb = None
        mem_available_kb = None
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available_kb = int(line.split()[1])
                    if mem_total_kb is not None and mem_available_kb is not None:
                        break
        except Exception:
            return None, None

        if mem_total_kb is None or mem_available_kb is None or mem_total_kb <= 0:
            return None, None

        mem_used_kb = max(0, mem_total_kb - mem_available_kb)
        mem_percent = 100.0 * float(mem_used_kb) / float(mem_total_kb)
        mem_used_mb = float(mem_used_kb) / 1024.0
        return mem_percent, mem_used_mb

    def _read_cpu_temp_c(self) -> float | None:
        candidates = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]

        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                value = float(raw)
                if value > 1000.0:
                    value = value / 1000.0
                if value > 0.0:
                    return value
            except Exception:
                continue

        return None

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
        self._stop_event.set()

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
