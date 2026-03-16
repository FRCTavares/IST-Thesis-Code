#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import rclpy
import websockets
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import Float32
from thesis_msgs.msg import TargetState, Timing, Track2DArray


class DashboardBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("dashboard_bridge_node")

        self.declare_parameter("tracks_topic", "/tracks")
        self.declare_parameter("target_topic", "/target")
        self.declare_parameter("fps_topic", "/camera/fps")
        self.declare_parameter("timing_topic", "/timing")

        self.declare_parameter("ws_host", "0.0.0.0")
        self.declare_parameter("ws_port", 8765)
        self.declare_parameter("publish_hz", 30.0)
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)

        self._tracks_topic = str(self.get_parameter("tracks_topic").value)
        self._target_topic = str(self.get_parameter("target_topic").value)
        self._fps_topic = str(self.get_parameter("fps_topic").value)
        self._timing_topic = str(self.get_parameter("timing_topic").value)

        self._ws_host = str(self.get_parameter("ws_host").value)
        self._ws_port = int(self.get_parameter("ws_port").value)
        self._publish_hz = float(self.get_parameter("publish_hz").value)
        self._img_w = max(1.0, float(self.get_parameter("img_w").value))
        self._img_h = max(1.0, float(self.get_parameter("img_h").value))

        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "tracks": [],
            "target": None,
            "fps": None,
            "latency_ms": None,
        }
        self._dirty = False

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
        self._target_sub = self.create_subscription(TargetState, self._target_topic, self._on_target, qos)
        self._fps_sub = self.create_subscription(Float32, self._fps_topic, self._on_fps, qos)
        self._timing_sub = self.create_subscription(Timing, self._timing_topic, self._on_timing, qos)
        self._publish_timer = self.create_timer(1.0 / max(self._publish_hz, 1.0), self._flush_state_to_clients)

        self.get_logger().info(
            "dashboard_bridge_node started: "
            f"tracks={self._tracks_topic}, target={self._target_topic}, "
            f"fps={self._fps_topic}, timing={self._timing_topic}, "
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
                "target": self._state["target"],
                "fps": self._state["fps"],
                "latency_ms": self._state["latency_ms"],
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

    def _on_target(self, msg: TargetState) -> None:
        with self._state_lock:
            self._state["target"] = int(msg.id)
            self._dirty = True

    def _on_fps(self, msg: Float32) -> None:
        with self._state_lock:
            self._state["fps"] = float(msg.data)
            self._dirty = True

    def _on_timing(self, msg: Timing) -> None:
        with self._state_lock:
            self._state["latency_ms"] = float(msg.lat_ms)
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
