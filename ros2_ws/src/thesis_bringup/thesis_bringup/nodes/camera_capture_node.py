#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import threading
import time
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
        self.declare_parameter("width", 1920)
        self.declare_parameter("height", 1080)
        self.declare_parameter("fps", 60.0)
        self.declare_parameter("frame_id", "camera")
        self.declare_parameter("fourcc", "UYVY")
        self.declare_parameter("dashboard_topic", "/camera/dashboard")
        self.declare_parameter("dashboard_width", 640)
        self.declare_parameter("dashboard_height", 360)
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

        self._bridge = CvBridge()
        self._latest_frame = None
        self._dashboard_buffer = None
        self._frame_lock = threading.Lock()
        self._cap: cv2.VideoCapture | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        image_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._image_pub = self.create_publisher(Image, "/camera/image_raw", image_qos)

        self._dashboard_pub = None
        if self._publish_dashboard_topic:
            dashboard_qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
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

        self._configure_camera()

        self._open_camera()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self.create_timer(1.0 / 30.0, self._publish_frame)

        self.get_logger().info(
            f"camera_capture_node started, device={self._device}, "
            f"width={self._width}, height={self._height}, fps={self._fps}"
        )

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
            raise RuntimeError(f"Sensor subdevice not found: {sensor_subdev}")

    def _init_media_pipeline(self) -> None:
        fmt_string = (
            f"fmt:UYVY8_1X16/{self._width}x{self._height} "
            "colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
        )

        commands = [
            f"media-ctl -d {self._media_dev} -V '\"{self._sensor_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":{self._csi_source_pad} [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -l '\"{self._csi_entity}\":{self._csi_source_pad} -> \"{self._video_entity}\":0 [1]'",
            f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl=trigger_mode={self._trigger_mode}",
        ]

        for cmd in commands:
            self._run_shell(cmd)
            time.sleep(self._command_delay_s)

    def _run_shell(self, cmd: str) -> subprocess.CompletedProcess:
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
            raise RuntimeError(f"Command timed out after {exc.timeout}s\\nCMD: {cmd}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
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

            frame = cv2.flip(frame, -1)

            with self._frame_lock:
                self._latest_frame = frame

    def _publish_frame(self) -> None:
        with self._frame_lock:
            frame = self._latest_frame

        if frame is None:
            return

        stamp = self.get_clock().now().to_msg()

        if self._dashboard_pub is not None:
            if self._dashboard_buffer is None:
                self._dashboard_buffer = cv2.resize(
                    frame,
                    (self._dashboard_width, self._dashboard_height),
                    interpolation=cv2.INTER_LINEAR,
                )
            else:
                cv2.resize(
                    frame,
                    (self._dashboard_width, self._dashboard_height),
                    dst=self._dashboard_buffer,
                    interpolation=cv2.INTER_LINEAR,
                )

            dashboard_msg = self._bridge.cv2_to_imgmsg(self._dashboard_buffer, encoding="bgr8")
            dashboard_msg.header.stamp = stamp
            dashboard_msg.header.frame_id = self._frame_id
            self._dashboard_pub.publish(dashboard_msg)

        msg = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        msg.header.stamp = stamp
        msg.header.frame_id = self._frame_id
        self._image_pub.publish(msg)

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

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

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