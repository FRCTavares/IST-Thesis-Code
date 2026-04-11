#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import re
from pathlib import Path

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32


class CameraCaptureNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_capture_node")

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("media_dev", "/dev/media0")
        self.declare_parameter("sensor_subdev", "/dev/v4l-subdev2")
        self.declare_parameter("width", 1280)
        self.declare_parameter("height", 720)
        self.declare_parameter("fps", 30.0)
        self.declare_parameter("frame_id", "camera")
        self.declare_parameter("fourcc", "UYVY")
        self.declare_parameter("dashboard_topic", "/camera/dashboard")
        self.declare_parameter("dashboard_width", 640)
        self.declare_parameter("dashboard_height", 360)
        self.declare_parameter("dashboard_fps", 30.0)
        self.declare_parameter("publish_dashboard_topic", True)
        self.declare_parameter("sensor_entity", "tevs 11-0048")
        self.declare_parameter("csi_entity", "csi2")
        self.declare_parameter("csi_source_pad", 4)
        self.declare_parameter("video_entity", "rp1-cfe-csi2_ch0")
        self.declare_parameter("trigger_mode", 0)
        self.declare_parameter("command_delay_s", 0.10)
        self.declare_parameter("command_timeout_s", 5.0)
        self.declare_parameter("reopen_delay_s", 1.0)
        self.declare_parameter("publish_fps_topic", True)
        self.declare_parameter("flip_image", True)
        self.declare_parameter("fail_on_media_init_error", False)

        self._device = self.get_parameter("device").value
        self._media_dev = self.get_parameter("media_dev").value
        self._sensor_subdev = self.get_parameter("sensor_subdev").value
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._fps = float(self.get_parameter("fps").value)
        self._frame_id = self.get_parameter("frame_id").value
        self._fourcc = self.get_parameter("fourcc").value
        self._dashboard_topic = str(self.get_parameter("dashboard_topic").value)
        self._dashboard_width = int(self.get_parameter("dashboard_width").value)
        self._dashboard_height = int(self.get_parameter("dashboard_height").value)
        self._dashboard_fps = max(0.0, float(self.get_parameter("dashboard_fps").value))
        self._publish_dashboard_topic = bool(self.get_parameter("publish_dashboard_topic").value)
        self._sensor_entity = self.get_parameter("sensor_entity").value
        self._csi_entity = self.get_parameter("csi_entity").value
        self._csi_source_pad = int(self.get_parameter("csi_source_pad").value)
        self._video_entity = self.get_parameter("video_entity").value
        self._trigger_mode = int(self.get_parameter("trigger_mode").value)
        self._command_delay_s = float(self.get_parameter("command_delay_s").value)
        self._command_timeout_s = float(self.get_parameter("command_timeout_s").value)
        self._reopen_delay_s = float(self.get_parameter("reopen_delay_s").value)
        self._publish_fps_topic = bool(self.get_parameter("publish_fps_topic").value)
        self._flip_image = bool(self.get_parameter("flip_image").value)
        self._fail_on_media_init_error = bool(self.get_parameter("fail_on_media_init_error").value)

        self._media_dev = self._resolve_media_device(self._media_dev)
        self._sensor_entity = self._resolve_sensor_entity(self._media_dev, self._sensor_entity)
        self._device = self._resolve_video_device(self._device)

        self._bridge = CvBridge()
        self._latest_frame = None
        self._latest_frame_id = 0
        self._last_published_frame_id = 0
        self._frame_lock = threading.Lock()
        self._new_frame_event = threading.Event()
        self._cap: cv2.VideoCapture | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._publisher_thread: threading.Thread | None = None

        image_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._image_pub = self.create_publisher(Image, "/camera/image_raw", image_qos)

        self._dashboard_pub = None
        if self._publish_dashboard_topic:
            dashboard_qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.VOLATILE,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
            )
            self._dashboard_pub = self.create_publisher(Image, self._dashboard_topic, dashboard_qos)

        self._fps_pub = None
        if self._publish_fps_topic:
            self._fps_pub = self.create_publisher(Float32, "/camera/fps", 10)

        self._frame_counter = 0
        self._fps_window_start = time.monotonic()
        self._last_log_time = 0.0
        self._last_dashboard_pub_time = 0.0

        self._configure_camera()

        self._open_camera()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self._publisher_thread = threading.Thread(target=self._publisher_loop, daemon=True)
        self._publisher_thread.start()

        self.get_logger().info(
            f"camera_capture_node started, device={self._device}, "
            f"width={self._width}, height={self._height}, fps={self._fps}"
        )

    def _probe_media_topology(self, media_dev: str) -> str | None:
        try:
            result = subprocess.run(
                ["media-ctl", "-d", media_dev, "-p"],
                check=False,
                text=True,
                capture_output=True,
                timeout=self._command_timeout_s,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        return result.stdout or ""

    def _resolve_media_device(self, configured_media_dev: str) -> str:
        candidates = [configured_media_dev]
        for path in sorted(Path("/dev").glob("media*")):
            path_str = str(path)
            if path_str not in candidates:
                candidates.append(path_str)

        required_markers = (self._sensor_entity, self._csi_entity, self._video_entity)

        for media_dev in candidates:
            topology = self._probe_media_topology(media_dev)
            if topology and all(marker in topology for marker in required_markers):
                if media_dev != configured_media_dev:
                    self.get_logger().warn(
                        f"Configured media_dev={configured_media_dev} does not match camera topology; "
                        f"using {media_dev} instead"
                    )
                return media_dev

        # Fallback heuristic after crash/re-enumeration: prefer the CSI graph over PISP backends.
        # This prevents selecting /dev/media0 pispbe when the actual camera graph moved.
        for media_dev in candidates:
            topology = self._probe_media_topology(media_dev)
            if not topology:
                continue
            if self._csi_entity in topology and "driver          pispbe" not in topology:
                if media_dev != configured_media_dev:
                    self.get_logger().warn(
                        f"Configured media_dev={configured_media_dev} does not expose CSI topology; "
                        f"using {media_dev} instead"
                    )
                return media_dev

        self.get_logger().warn(
            f"Could not auto-detect camera media device; using configured value {configured_media_dev}"
        )
        return configured_media_dev

    def _extract_video_nodes_from_media(self, media_dev: str) -> list[str]:
        topology = self._probe_media_topology(media_dev)
        if not topology:
            return []

        nodes = re.findall(r"device node name\s+(/dev/video\d+)", topology)
        unique_nodes = []
        for node in nodes:
            if node not in unique_nodes:
                unique_nodes.append(node)
        return unique_nodes

    def _resolve_sensor_entity(self, media_dev: str, configured_sensor_entity: str) -> str:
        topology = self._probe_media_topology(media_dev)
        if not topology:
            return configured_sensor_entity

        if configured_sensor_entity in topology:
            return configured_sensor_entity

        entity_names = re.findall(r"- entity\s+\d+:\s+([^\n(]+)\s*\(", topology)
        tevs_entities = [name.strip() for name in entity_names if name.strip().startswith("tevs ")]
        if tevs_entities:
            detected = tevs_entities[0]
            self.get_logger().warn(
                f"Configured sensor_entity='{configured_sensor_entity}' not present on {media_dev}; "
                f"using '{detected}' instead"
            )
            return detected

        self.get_logger().warn(
            f"No TEVS sensor entity auto-detected on {media_dev}; using configured value "
            f"'{configured_sensor_entity}'"
        )
        return configured_sensor_entity

    def _detect_sensor_resolution(self) -> tuple[int, int] | None:
        topology = self._probe_media_topology(self._media_dev)
        if not topology:
            return None

        sensor_header = re.search(
            rf"- entity\s+\d+:\s+{re.escape(self._sensor_entity)}\s*\([\s\S]*?\n\n",
            topology,
        )
        if not sensor_header:
            return None

        sensor_block = sensor_header.group(0)
        match = re.search(r"fmt:[^/]+/(\d+)x(\d+)", sensor_block)
        if not match:
            return None

        width = int(match.group(1))
        height = int(match.group(2))
        if width <= 0 or height <= 0:
            return None
        return width, height

    def _resolve_video_device(self, configured_device: str) -> str:
        configured_path = Path(configured_device)
        if configured_path.exists():
            return configured_device

        candidates = [Path(p) for p in self._extract_video_nodes_from_media(self._media_dev)]
        if not candidates:
            raise RuntimeError(
                f"Configured camera device {configured_device} not found and media device "
                f"{self._media_dev} exposes no video nodes. "
                "Camera sensor/CSI graph is likely not initialized; reboot host to recover."
            )

        for candidate in candidates:
            cap = cv2.VideoCapture(str(candidate), cv2.CAP_V4L2)
            try:
                if cap.isOpened():
                    self.get_logger().warn(
                        f"Configured camera device {configured_device} not found; using {candidate} instead"
                    )
                    return str(candidate)
            finally:
                cap.release()

        self.get_logger().warn(
            f"Configured camera device {configured_device} not found and no usable /dev/video* candidate opened"
        )
        return configured_device

    def _configure_camera(self) -> None:
        self.get_logger().info("Configuring TEVS camera before capture start")
        self._check_binaries()
        self._check_devices()
        self._init_media_pipeline()
        self.get_logger().info("TEVS camera configured successfully")

    def _check_binaries(self) -> None:
        for tool in ("media-ctl", "v4l2-ctl"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"Required binary not found in PATH: {tool}")

    def _check_devices(self) -> None:
        device = Path(self._device)
        media_dev = Path(self._media_dev)
        sensor_subdev = Path(self._sensor_subdev)

        if not device.exists():
            raise RuntimeError(f"Camera device not found: {device}")
        if not media_dev.exists():
            raise RuntimeError(f"Media device not found: {media_dev}")
        if not sensor_subdev.exists():
            self.get_logger().warn(
                f"Sensor subdevice not found: {sensor_subdev}; "
                "continuing without trigger_mode configuration"
            )

    def _init_media_pipeline(self) -> None:
        active_width = self._width
        active_height = self._height

        fmt_string = (
            f"fmt:UYVY8_1X16/{active_width}x{active_height} "
            "field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
        )

        sensor_cmd = f"media-ctl -d {self._media_dev} -V '\"{self._sensor_entity}\":0 [{fmt_string}]'"
        sensor_result = self._run_shell(sensor_cmd, allow_failure=not self._fail_on_media_init_error)
        time.sleep(self._command_delay_s)

        detected_resolution = self._detect_sensor_resolution()
        if detected_resolution is not None:
            detected_width, detected_height = detected_resolution
            if (detected_width, detected_height) != (active_width, active_height):
                reason = "not accepted" if sensor_result.returncode != 0 else "applied differently"
                self.get_logger().warn(
                    "Requested sensor format "
                    f"{active_width}x{active_height} was {reason}; "
                    f"using detected sensor format {detected_width}x{detected_height}"
                )
                active_width, active_height = detected_width, detected_height
                self._width, self._height = active_width, active_height
                fmt_string = (
                    f"fmt:UYVY8_1X16/{active_width}x{active_height} "
                    "field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
                )

        commands = [
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":{self._csi_source_pad} [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -l '\"{self._csi_entity}\":{self._csi_source_pad} -> \"{self._video_entity}\":0 [1]'",
        ]

        if Path(self._sensor_subdev).exists():
            commands.append(
                f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl=trigger_mode={self._trigger_mode}"
            )

        for cmd in commands:
            self._run_shell(cmd, allow_failure=not self._fail_on_media_init_error)
            time.sleep(self._command_delay_s)

    def _run_shell(self, cmd: str, allow_failure: bool = False) -> subprocess.CompletedProcess:
        self.get_logger().info(f"Running: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=False,
                text=True,
                capture_output=True,
                timeout=self._command_timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            if allow_failure:
                self.get_logger().warn(
                    "Camera init command timed out (continuing): "
                    f"timeout={exc.timeout}s, cmd={cmd}"
                )
                return subprocess.CompletedProcess(cmd, 124, "", f"timeout after {exc.timeout}s")
            raise RuntimeError(f"Command timed out after {exc.timeout}s\\nCMD: {cmd}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            if allow_failure:
                self.get_logger().warn(
                    "Camera init command failed (continuing): "
                    f"rc={result.returncode}, cmd={cmd}, stdout={stdout}, stderr={stderr}"
                )
                return result
            raise RuntimeError(
                f"Command failed with code {result.returncode}\\n"
                f"CMD: {cmd}\\n"
                f"STDOUT:\\n{stdout}\\n"
                f"STDERR:\\n{stderr}"
            )

        return result

    def _open_camera(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass

        self.get_logger().info(f"Opening camera: {self._device}")
        cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)

        if not cap.isOpened():
            raise RuntimeError(f"Failed to open camera device: {self._device}")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if len(self._fourcc) == 4:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc))

        self._cap = cap

    def _capture_loop(self) -> None:
        while rclpy.ok() and not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                self._retry_reopen()
                continue

            ok, frame = self._cap.read()

            if not ok:
                now = time.monotonic()
                if now - self._last_log_time > 1.0:
                    self.get_logger().warn("Frame capture failed, reopening camera")
                    self._last_log_time = now
                self._retry_reopen()
                continue

            if self._flip_image:
                frame = cv2.flip(frame, -1)

            with self._frame_lock:
                self._latest_frame = frame
                self._latest_frame_id += 1
            self._new_frame_event.set()

    def _publisher_loop(self) -> None:
        while rclpy.ok() and not self._stop_event.is_set():
            has_new_frame = self._new_frame_event.wait(timeout=0.25)
            if not has_new_frame:
                continue
            self._new_frame_event.clear()
            self._publish_latest_frame()

    def _publish_latest_frame(self) -> None:
        with self._frame_lock:
            frame = self._latest_frame
            frame_id = self._latest_frame_id

        if frame is None:
            return

        # Publish only new frames to avoid re-encoding and republishing duplicates.
        if frame_id == self._last_published_frame_id:
            return

        stamp = self.get_clock().now().to_msg()

        if self._dashboard_pub is not None:
            now = time.monotonic()
            publish_dashboard = True
            if self._dashboard_fps > 0.0:
                period = 1.0 / self._dashboard_fps
                publish_dashboard = (now - self._last_dashboard_pub_time) >= period

            if publish_dashboard:
                dashboard_frame = frame
                if frame.shape[1] != self._dashboard_width or frame.shape[0] != self._dashboard_height:
                    dashboard_frame = cv2.resize(
                        frame,
                        (self._dashboard_width, self._dashboard_height),
                        interpolation=cv2.INTER_AREA,
                    )
                dashboard_msg = self._bridge.cv2_to_imgmsg(dashboard_frame, encoding="bgr8")
                dashboard_msg.header.stamp = stamp
                dashboard_msg.header.frame_id = self._frame_id
                self._dashboard_pub.publish(dashboard_msg)
                self._last_dashboard_pub_time = now

        msg = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        msg.header.stamp = stamp
        msg.header.frame_id = self._frame_id
        self._image_pub.publish(msg)
        self._last_published_frame_id = frame_id

        self._frame_counter += 1
        self._publish_fps_if_due()

    def _publish_fps_if_due(self) -> None:
        if self._fps_pub is None:
            return

        now = time.monotonic()
        dt = now - self._fps_window_start

        if dt >= 1.0:
            fps = self._frame_counter / dt if dt > 0.0 else 0.0
            fps_msg = Float32()
            fps_msg.data = float(fps)
            self._fps_pub.publish(fps_msg)

            self.get_logger().info(f"Camera FPS: {fps:.2f}")

            self._frame_counter = 0
            self._fps_window_start = now

    def _retry_reopen(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        time.sleep(self._reopen_delay_s)

        try:
            self._open_camera()
            self.get_logger().info("Camera reopened successfully")
        except Exception as exc:
            now = time.monotonic()
            if now - self._last_log_time > 1.0:
                self.get_logger().warn(f"Camera reopen failed: {exc}")
                self._last_log_time = now

    def destroy_node(self):
        self._stop_event.set()
        self._new_frame_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._publisher_thread is not None and self._publisher_thread.is_alive():
            self._publisher_thread.join(timeout=2.0)

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CameraCaptureNode()

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