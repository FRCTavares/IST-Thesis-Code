#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import time
import threading
from collections import deque
from typing import Any

import rclpy
import websockets
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
        self.declare_parameter("publish_hz", 30.0)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)

        self._tracks_topic = str(self.get_parameter("tracks_topic").value)
        self._detections_topic = str(self.get_parameter("detections_topic").value)
        self._target_topic = str(self.get_parameter("target_topic").value)
        self._fps_topic = str(self.get_parameter("fps_topic").value)
        self._replay_progress_topic = str(self.get_parameter("replay_progress_topic").value)
        self._timing_topic = str(self.get_parameter("timing_topic").value)

        self._ws_host = str(self.get_parameter("ws_host").value)
        self._ws_port = int(self.get_parameter("ws_port").value)
        self._publish_hz = float(self.get_parameter("publish_hz").value)
        self._img_w = max(1.0, float(self.get_parameter("img_w").value))
        self._img_h = max(1.0, float(self.get_parameter("img_h").value))

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

        self._loop = asyncio.new_event_loop()
        self._server = None
        self._ws_clients: set[Any] = set()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

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
            f"ws=ws://{self._ws_host}:{self._ws_port}"
        )

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
