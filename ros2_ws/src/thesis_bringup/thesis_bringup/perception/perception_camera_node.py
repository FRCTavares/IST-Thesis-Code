#!/usr/bin/env python3
"""Camera-source node for modular perception experiments.

This node provides a camera image source path used by perception pipeline
development and validation workflows.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

import cv2
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image
from thesis_bringup.perception.perception_pipeline_node import PerceptionPipelineNode


class PerceptionCameraNode(PerceptionPipelineNode):
    """Integrated camera plus Hailo perception node.

    This node keeps the colour frame inside the perception process and publishes
    compact semantic outputs only. It bypasses the full-rate /camera/image_raw
    DDS transport path used by the modular camera/perception pipeline.
    """

    def __init__(self) -> None:
        super().__init__(
            node_name="perception_camera_node",
            create_image_subscription=False,
        )

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("media_dev", "/dev/media0")
        self.declare_parameter("sensor_subdev", "/dev/v4l-subdev2")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", 30.0)
        self.declare_parameter("frame_id", "camera")
        self.declare_parameter("fourcc", "UYVY")

        self.declare_parameter("sensor_entity", "tevs 11-0048")
        self.declare_parameter("csi_entity", "csi2")
        self.declare_parameter("csi_source_pad", 4)
        self.declare_parameter("video_entity", "rp1-cfe-csi2_ch0")

        self.declare_parameter("trigger_mode", 0)
        self.declare_parameter("apply_sensor_trigger_control", False)
        self.declare_parameter("apply_sensor_rate_controls", False)
        self.declare_parameter("sensor_max_fps", 30)
        self.declare_parameter("sensor_ae_exposure_upper", 8333)
        self.declare_parameter("sensor_ae_exposure_max", 33333)
        self.declare_parameter("sensor_exposure_mode", 1)
        self.declare_parameter("sensor_manual_exposure", 8333)

        self.declare_parameter("command_delay_s", 0.10)
        self.declare_parameter("command_timeout_s", 5.0)
        self.declare_parameter("reopen_delay_s", 1.0)
        self.declare_parameter("startup_frame_timeout_s", 20.0)
        self.declare_parameter("stall_timeout_s", 4.0)

        # Optional low-rate image publisher for dashboard and TIM-MARS appearance crops.
        # This is not the main inference path; inference still stays inside this process.
        self.declare_parameter("publish_dashboard_topic", False)
        self.declare_parameter("dashboard_topic", "/camera/dashboard")
        self.declare_parameter("dashboard_fps", 10.0)

        self._device = str(self.get_parameter("device").value)
        self._media_dev = str(self.get_parameter("media_dev").value)
        self._sensor_subdev = str(self.get_parameter("sensor_subdev").value)
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._fps = float(self.get_parameter("fps").value)
        self._frame_id = str(self.get_parameter("frame_id").value)
        self._fourcc = str(self.get_parameter("fourcc").value)

        self._sensor_entity = str(self.get_parameter("sensor_entity").value)
        self._csi_entity = str(self.get_parameter("csi_entity").value)
        self._csi_source_pad = int(self.get_parameter("csi_source_pad").value)
        self._video_entity = str(self.get_parameter("video_entity").value)

        self._trigger_mode = int(self.get_parameter("trigger_mode").value)
        self._apply_sensor_trigger_control = bool(
            self.get_parameter("apply_sensor_trigger_control").value
        )
        self._apply_sensor_rate_controls = bool(
            self.get_parameter("apply_sensor_rate_controls").value
        )
        self._sensor_max_fps = int(self.get_parameter("sensor_max_fps").value)
        self._sensor_ae_exposure_upper = int(
            self.get_parameter("sensor_ae_exposure_upper").value
        )
        self._sensor_ae_exposure_max = int(
            self.get_parameter("sensor_ae_exposure_max").value
        )
        self._sensor_exposure_mode = int(self.get_parameter("sensor_exposure_mode").value)
        self._sensor_manual_exposure = int(
            self.get_parameter("sensor_manual_exposure").value
        )

        self._command_delay_s = float(self.get_parameter("command_delay_s").value)
        self._command_timeout_s = float(self.get_parameter("command_timeout_s").value)
        self._reopen_delay_s = float(self.get_parameter("reopen_delay_s").value)
        self._startup_frame_timeout_s = max(
            1.0, float(self.get_parameter("startup_frame_timeout_s").value)
        )
        self._stall_timeout_s = max(1.0, float(self.get_parameter("stall_timeout_s").value))

        self._publish_dashboard_topic = bool(
            self.get_parameter("publish_dashboard_topic").value
        )
        self._dashboard_topic = str(self.get_parameter("dashboard_topic").value)
        self._dashboard_fps = max(0.0, float(self.get_parameter("dashboard_fps").value))
        self._dashboard_period_s = (
            1.0 / self._dashboard_fps if self._dashboard_fps > 0.0 else 0.0
        )
        self._last_dashboard_pub_monotonic = 0.0

        dashboard_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._dashboard_pub = (
            self.create_publisher(Image, self._dashboard_topic, dashboard_qos)
            if self._publish_dashboard_topic
            else None
        )

        # Publish the live camera frame stream for recording and replay.
        # The integrated perception path normally only publishes semantic outputs
        # plus /camera/dashboard; /camera/image_raw is required for field bags.
        self._image_raw_pub = self.create_publisher(Image, "/camera/image_raw", dashboard_qos)

        self._cap = None
        self._camera_stop = threading.Event()
        self._camera_thread: threading.Thread | None = None
        self._last_frame_monotonic = 0.0
        self._camera_frame_id = 0

        self._configure_camera()
        self._open_camera()

        self._camera_thread = threading.Thread(
            target=self._camera_loop,
            name="perception_camera_capture",
            daemon=True,
        )
        self._camera_thread.start()

        self.get_logger().info(
            "perception_camera_node started, "
            f"capture={self._width}x{self._height}, "
            f"fps={self._fps:.2f}, "
            f"infer={self.img_w}x{self.img_h}, "
            f"dashboard={'on' if self._publish_dashboard_topic else 'off'} "
            f"topic={self._dashboard_topic} fps={self._dashboard_fps:.2f}"
        )

    def _check_binaries(self) -> None:
        for tool in ("media-ctl", "v4l2-ctl"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"Required binary not found in PATH: {tool}")

    def _check_devices(self) -> None:
        for path in (self._device, self._media_dev):
            if not Path(path).exists():
                raise RuntimeError(f"Required camera device not found: {path}")

        if not Path(self._sensor_subdev).exists():
            self.get_logger().warn(
                f"Sensor subdevice not found: {self._sensor_subdev}; "
                "continuing without sensor control writes"
            )

    def _run_shell(self, cmd: str, *, allow_failure: bool = False) -> subprocess.CompletedProcess:
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
                    f"Camera command timed out, continuing: timeout={exc.timeout}s, cmd={cmd}"
                )
                return subprocess.CompletedProcess(
                    cmd,
                    124,
                    "",
                    f"timeout after {exc.timeout}s",
                )
            raise RuntimeError(f"Command timed out after {exc.timeout}s\nCMD: {cmd}") from exc

        if result.returncode != 0 and not allow_failure:
            raise RuntimeError(
                f"Command failed with code {result.returncode}\n"
                f"CMD: {cmd}\n"
                f"STDOUT:\n{result.stdout.strip()}\n"
                f"STDERR:\n{result.stderr.strip()}"
            )

        if result.returncode != 0 and allow_failure:
            self.get_logger().warn(
                "Camera command failed, continuing: "
                f"rc={result.returncode}, cmd={cmd}, "
                f"stdout={result.stdout.strip()}, stderr={result.stderr.strip()}"
            )

        return result

    def _resolve_sensor_entity(self) -> None:
        result = self._run_shell(
            f"media-ctl -d {self._media_dev} -p",
            allow_failure=True,
        )
        graph = f"{result.stdout}\n{result.stderr}"

        if self._sensor_entity in graph:
            return

        for line in graph.splitlines():
            line = line.strip()
            if line.startswith("- entity") and "tevs " in line:
                parts = line.split("'")
                if len(parts) >= 2:
                    detected = parts[1]
                    self.get_logger().warn(
                        f"Configured sensor_entity='{self._sensor_entity}' not present on "
                        f"{self._media_dev}; using '{detected}' instead"
                    )
                    self._sensor_entity = detected
                    return

    def _configure_camera(self) -> None:
        self.get_logger().info("Configuring TEVS camera before integrated capture start")
        self._check_binaries()
        self._check_devices()
        self._resolve_sensor_entity()

        fmt_string = (
            f"fmt:UYVY8_1X16/{self._width}x{self._height} "
            "field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
        )

        commands = [
            f"media-ctl -d {self._media_dev} -V '\"{self._sensor_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":{self._csi_source_pad} [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -l '\"{self._csi_entity}\":{self._csi_source_pad} -> \"{self._video_entity}\":0 [1]'",
        ]

        for cmd in commands:
            self._run_shell(cmd, allow_failure=True)
            time.sleep(self._command_delay_s)

        if Path(self._sensor_subdev).exists() and self._apply_sensor_trigger_control:
            self._run_shell(
                f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl=trigger_mode={self._trigger_mode}",
                allow_failure=True,
            )
            time.sleep(self._command_delay_s)

        if Path(self._sensor_subdev).exists() and self._apply_sensor_rate_controls:
            controls = [
                f"max_fps={self._sensor_max_fps}",
                f"ae_exposure_upper={self._sensor_ae_exposure_upper}",
                f"ae_exposure_max={self._sensor_ae_exposure_max}",
                f"exposure_mode={self._sensor_exposure_mode}",
            ]
            if self._sensor_exposure_mode == 0:
                controls.append(f"exposure={self._sensor_manual_exposure}")

            self._run_shell(
                f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl={','.join(controls)}",
                allow_failure=True,
            )
            time.sleep(self._command_delay_s)

        self.get_logger().info("TEVS camera configured successfully for integrated capture")

    @staticmethod
    def _decode_fourcc(raw_fourcc: float) -> str:
        try:
            code = int(raw_fourcc)
        except Exception:
            return "????"

        chars = [chr((code >> (8 * i)) & 0xFF) for i in range(4)]
        return "".join(char if 32 <= ord(char) <= 126 else "?" for char in chars)

    def _open_camera(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass

        self.get_logger().info(f"Opening integrated camera: {self._device}")

        cap = cv2.VideoCapture()
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self._command_timeout_s * 1000.0))
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self._stall_timeout_s * 1000.0))

        cap.open(self._device, cv2.CAP_V4L2)

        if not cap.isOpened():
            raise RuntimeError(f"Failed to open camera device: {self._device}")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if len(self._fourcc) == 4:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc))

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = float(cap.get(cv2.CAP_PROP_FPS))
        actual_fourcc = self._decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))

        self.get_logger().info(
            "Opened integrated camera actual mode: "
            f"{actual_width}x{actual_height} @ {actual_fps:.2f} FPS, FOURCC={actual_fourcc}"
        )

        self._cap = cap

    def _retry_reopen(self) -> None:
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass

        time.sleep(self._reopen_delay_s)
        self._open_camera()

    def _maybe_publish_dashboard_frame(self, msg: Image, *, now_monotonic: float) -> None:
        if self._dashboard_pub is None:
            return

        if self._dashboard_period_s > 0.0:
            elapsed_s = now_monotonic - self._last_dashboard_pub_monotonic
            if elapsed_s < self._dashboard_period_s:
                return

        self._dashboard_pub.publish(msg)
        self._last_dashboard_pub_monotonic = now_monotonic

    def _frame_to_msg(self, frame) -> Image:
        stamp = self.get_clock().now().to_msg()

        msg = Image()
        msg.header.stamp = stamp
        msg.header.frame_id = self._frame_id
        msg.height = int(frame.shape[0])
        msg.width = int(frame.shape[1])
        msg.encoding = "bgr8"
        msg.is_bigendian = 0
        msg.step = int(frame.shape[1] * 3)
        msg.data = frame.tobytes()
        return msg

    def _camera_loop(self) -> None:
        next_frame_time = time.monotonic()
        startup_t0 = time.monotonic()

        while rclpy.ok() and not self._camera_stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                self._retry_reopen()
                continue

            ok, frame = self._cap.read()
            now = time.monotonic()

            if not ok:
                if now - startup_t0 > self._startup_frame_timeout_s:
                    self.get_logger().error("Integrated camera startup/read timeout")
                    os._exit(12)
                self.get_logger().warn("Integrated camera read failed, reopening")
                self._retry_reopen()
                continue

            self._last_frame_monotonic = now
            self._camera_frame_id += 1

            msg = self._frame_to_msg(frame)
            self._image_raw_pub.publish(msg)
            self._maybe_publish_dashboard_frame(msg, now_monotonic=time.monotonic())
            self.on_image(msg)

            if self._fps > 0.0:
                next_frame_time += 1.0 / self._fps
                delay = next_frame_time - time.monotonic()
                if delay > 0.0:
                    self._camera_stop.wait(timeout=delay)
                elif delay < -0.5:
                    next_frame_time = time.monotonic()

    def destroy_node(self) -> None:
        self._camera_stop.set()

        if self._camera_thread is not None:
            self._camera_thread.join(timeout=2.0)

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None

    try:
        node = PerceptionCameraNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
