#!/usr/bin/env python3

from __future__ import annotations

import threading
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32


class CameraCaptureNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_capture_node")

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("width", 1920)
        self.declare_parameter("height", 1080)
        self.declare_parameter("fps", 60.0)
        self.declare_parameter("frame_id", "camera")
        self.declare_parameter("fourcc", "UYVY")
        self.declare_parameter("reopen_delay_s", 1.0)
        self.declare_parameter("publish_fps_topic", True)

        self._device = self.get_parameter("device").value
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._fps = float(self.get_parameter("fps").value)
        self._frame_id = self.get_parameter("frame_id").value
        self._fourcc = self.get_parameter("fourcc").value
        self._reopen_delay_s = float(self.get_parameter("reopen_delay_s").value)
        self._publish_fps_topic = bool(self.get_parameter("publish_fps_topic").value)

        self._bridge = CvBridge()
        self._cap: cv2.VideoCapture | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._image_pub = self.create_publisher(Image, "/camera/image_raw", qos_profile_sensor_data)

        self._fps_pub = None
        if self._publish_fps_topic:
            fps_qos = QoSProfile(depth=1)
            fps_qos.reliability = ReliabilityPolicy.RELIABLE
            fps_qos.durability = DurabilityPolicy.VOLATILE
            self._fps_pub = self.create_publisher(Float32, "/camera/fps", fps_qos)

        self._frame_counter = 0
        self._fps_window_start = time.monotonic()
        self._last_log_time = 0.0

        self._open_camera()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        self.get_logger().info(
            f"camera_capture_node started, device={self._device}, "
            f"width={self._width}, height={self._height}, fps={self._fps}"
        )

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

            stamp = self.get_clock().now().to_msg()

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