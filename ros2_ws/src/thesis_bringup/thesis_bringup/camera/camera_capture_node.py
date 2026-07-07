#!/usr/bin/env python3
"""Live camera capture node for the thesis ROS 2 stack.

This node owns host-side camera acquisition, frame timing, optional resizing,
camera health reporting, and image publication for downstream perception nodes.

It is hardware-sensitive code. Keep behavior changes small and validate on the
target camera platform.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import re
import os
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32


class CameraCaptureNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_capture_node")

        self._declare_parameters()
        self._load_parameters()
        self._validate_runtime_parameters()

        self._media_dev = self._resolve_media_device(self._media_dev)
        self._sensor_entity = self._resolve_sensor_entity(self._media_dev, self._sensor_entity)
        self._device = self._resolve_video_device(self._device)

        self._bridge = CvBridge()
        self._latest_frame = None
        self._latest_frame_id = 0
        self._last_published_frame_id = 0
        self._last_dashboard_published_frame_id = 0
        self._latest_capture_stamp_sec = 0
        self._latest_capture_stamp_nanosec = 0
        self._frame_lock = threading.Lock()
        self._new_frame_event = threading.Event()
        self._dashboard_event = threading.Event()
        self._cap: cv2.VideoCapture | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._publisher_thread: threading.Thread | None = None
        self._dashboard_thread: threading.Thread | None = None
        self._publish_resize_buf: np.ndarray | None = None
        self._publish_rgb_buf: np.ndarray | None = None
        self._dashboard_resize_buf: np.ndarray | None = None

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

        self._capture_fps_pub = None
        if self._publish_capture_fps_topic:
            self._capture_fps_pub = self.create_publisher(Float32, self._capture_fps_topic, 10)

        self._capture_frame_counter = 0
        self._capture_fps_window_start = time.monotonic()
        self._publish_frame_counter = 0
        self._publish_fps_window_start = time.monotonic()
        self._latest_capture_fps = 0.0
        self._latest_publish_fps = 0.0
        self._last_log_time = 0.0
        self._start_monotonic = time.monotonic()
        self._last_frame_monotonic = 0.0
        self._watchdog_exit_started = False
        self._image_publish_period = (1.0 / self._fps) if self._fps > 0.0 else 0.0
        self.add_on_set_parameters_callback(self._on_set_parameters)

        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

        self._configure_camera()
        if self._publish_width_auto:
            self._publish_width = self._width
        if self._publish_height_auto:
            self._publish_height = self._height

        self._open_camera()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self._publisher_thread = threading.Thread(target=self._publisher_loop, daemon=True)
        self._publisher_thread.start()
        if self._dashboard_pub is not None:
            self._dashboard_thread = threading.Thread(target=self._dashboard_loop, daemon=True)
            self._dashboard_thread.start()

        self.get_logger().info(
            f"camera_capture_node started, device={self._device}, "
            f"capture={self._width}x{self._height}, "
            f"publish={self._publish_width}x{self._publish_height} "
            f"({self._publish_resize_mode}, {self._publish_encoding}), fps={self._fps}"
        )


    def _declare_parameters(self) -> None:
        """Declare ROS parameters used by the camera capture node."""
        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("media_dev", "/dev/media0")
        self.declare_parameter("sensor_subdev", "/dev/v4l-subdev2")
        self.declare_parameter("width", 1280)
        self.declare_parameter("height", 720)
        self.declare_parameter("publish_width", 0)
        self.declare_parameter("publish_height", 0)
        self.declare_parameter("publish_resize_mode", "letterbox")
        self.declare_parameter("publish_encoding", "bgr8")
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
        self.declare_parameter("apply_sensor_trigger_control", False)
        self.declare_parameter("apply_sensor_rate_controls", True)
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
        self.declare_parameter("publish_fps_topic", True)
        self.declare_parameter("flip_image", True)
        self.declare_parameter("fail_on_media_init_error", False)
        self.declare_parameter("adopt_detected_sensor_resolution", True)
        self.declare_parameter("dashboard_publish_requires_subscribers", True)
        self.declare_parameter("capture_fps_topic", "/camera/capture_fps")
        self.declare_parameter("publish_capture_fps_topic", True)

    def _load_parameters(self) -> None:
        """Load ROS parameter values into node attributes."""
        self._device = self.get_parameter("device").value
        self._media_dev = self.get_parameter("media_dev").value
        self._sensor_subdev = self.get_parameter("sensor_subdev").value
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._publish_width = int(self.get_parameter("publish_width").value)
        self._publish_height = int(self.get_parameter("publish_height").value)
        self._publish_resize_mode = str(self.get_parameter("publish_resize_mode").value).strip().lower()
        self._publish_encoding = str(self.get_parameter("publish_encoding").value).strip().lower()
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
        self._apply_sensor_trigger_control = bool(
            self.get_parameter("apply_sensor_trigger_control").value
        )
        self._apply_sensor_rate_controls = bool(self.get_parameter("apply_sensor_rate_controls").value)
        self._sensor_max_fps = int(self.get_parameter("sensor_max_fps").value)
        self._sensor_ae_exposure_upper = int(self.get_parameter("sensor_ae_exposure_upper").value)
        self._sensor_ae_exposure_max = int(self.get_parameter("sensor_ae_exposure_max").value)
        self._sensor_exposure_mode = int(self.get_parameter("sensor_exposure_mode").value)
        self._sensor_manual_exposure = int(self.get_parameter("sensor_manual_exposure").value)
        self._command_delay_s = float(self.get_parameter("command_delay_s").value)
        self._command_timeout_s = float(self.get_parameter("command_timeout_s").value)
        self._reopen_delay_s = float(self.get_parameter("reopen_delay_s").value)
        self._startup_frame_timeout_s = max(
            1.0, float(self.get_parameter("startup_frame_timeout_s").value)
        )
        self._stall_timeout_s = max(1.0, float(self.get_parameter("stall_timeout_s").value))
        self._publish_fps_topic = bool(self.get_parameter("publish_fps_topic").value)
        # Kept for backward compatibility with existing launch args, but ignored.
        self._flip_image = bool(self.get_parameter("flip_image").value)
        self._fail_on_media_init_error = bool(self.get_parameter("fail_on_media_init_error").value)
        self._adopt_detected_sensor_resolution = bool(
            self.get_parameter("adopt_detected_sensor_resolution").value
        )
        self._dashboard_publish_requires_subscribers = bool(
            self.get_parameter("dashboard_publish_requires_subscribers").value
        )
        self._capture_fps_topic = str(self.get_parameter("capture_fps_topic").value)
        self._publish_capture_fps_topic = bool(self.get_parameter("publish_capture_fps_topic").value)

    def _validate_runtime_parameters(self) -> None:
        """Normalize runtime parameters and warn about ignored legacy settings."""
        if self._flip_image:
            self.get_logger().warn(
                "flip_image parameter is deprecated and ignored; camera frames are published unrotated"
            )

        self._publish_width_auto = self._publish_width <= 0
        self._publish_height_auto = self._publish_height <= 0

        if self._publish_width_auto:
            self._publish_width = self._width
        if self._publish_height_auto:
            self._publish_height = self._height
        if self._publish_resize_mode not in ("resize", "letterbox"):
            self.get_logger().warn(
                f"invalid publish_resize_mode='{self._publish_resize_mode}', using letterbox"
            )
            self._publish_resize_mode = "letterbox"
        if self._publish_encoding not in ("bgr8", "rgb8"):
            self.get_logger().warn(
                f"invalid publish_encoding='{self._publish_encoding}', using bgr8"
            )
            self._publish_encoding = "bgr8"

    def _on_set_parameters(self, params) -> SetParametersResult:
        next_publish_width = self._publish_width
        next_publish_height = self._publish_height
        next_dashboard_width = self._dashboard_width
        next_dashboard_height = self._dashboard_height

        publish_changed = False
        dashboard_changed = False

        for param in params:
            if param.name not in {
                "publish_width",
                "publish_height",
                "dashboard_width",
                "dashboard_height",
            }:
                continue

            try:
                value = int(param.value)
            except Exception:
                return SetParametersResult(
                    successful=False,
                    reason=f"{param.name} must be an integer",
                )

            if value <= 0:
                return SetParametersResult(
                    successful=False,
                    reason=f"{param.name} must be > 0",
                )

            if param.name == "publish_width":
                next_publish_width = value
                publish_changed = True
            elif param.name == "publish_height":
                next_publish_height = value
                publish_changed = True
            elif param.name == "dashboard_width":
                next_dashboard_width = value
                dashboard_changed = True
            elif param.name == "dashboard_height":
                next_dashboard_height = value
                dashboard_changed = True

        if not publish_changed and not dashboard_changed:
            return SetParametersResult(successful=True)

        with self._frame_lock:
            if publish_changed:
                self._publish_width = next_publish_width
                self._publish_height = next_publish_height
                self._publish_width_auto = False
                self._publish_height_auto = False
                self._publish_resize_buf = None
                self._publish_rgb_buf = None
                self._last_published_frame_id = 0

            if dashboard_changed:
                self._dashboard_width = next_dashboard_width
                self._dashboard_height = next_dashboard_height
                self._dashboard_resize_buf = None
                self._last_dashboard_published_frame_id = 0

        self._new_frame_event.set()
        self._dashboard_event.set()

        self.get_logger().info(
            "runtime camera resolution update: "
            f"publish={self._publish_width}x{self._publish_height}, "
            f"dashboard={self._dashboard_width}x{self._dashboard_height}"
        )
        return SetParametersResult(successful=True)

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

    def _can_probe_video_device(self, device_path: str) -> bool:
        try:
            result = subprocess.run(
                ["v4l2-ctl", "-d", device_path, "--all"],
                check=False,
                text=True,
                capture_output=True,
                timeout=self._command_timeout_s,
            )
        except Exception:
            return False

        return result.returncode == 0

    def _resolve_video_device(self, configured_device: str) -> str:
        configured_path = Path(configured_device)
        if configured_path.exists():
            if self._can_probe_video_device(configured_device):
                return configured_device
            self.get_logger().warn(
                f"Configured camera device {configured_device} exists but failed V4L2 probe; "
                "searching fallback video nodes"
            )

        candidates = [Path(p) for p in self._extract_video_nodes_from_media(self._media_dev)]
        for path in sorted(Path("/dev").glob("video*")):
            if path not in candidates:
                candidates.append(path)

        if not candidates:
            raise RuntimeError(
                f"Configured camera device {configured_device} not found and media device "
                f"{self._media_dev} exposes no video nodes. "
                "Camera sensor/CSI graph is likely not initialized; reboot host to recover."
            )

        for candidate in candidates:
            if self._can_probe_video_device(str(candidate)):
                self.get_logger().warn(
                    f"Configured camera device {configured_device} not usable; using {candidate} instead"
                )
                return str(candidate)

        raise RuntimeError(
            f"Configured camera device {configured_device} is not usable and no fallback /dev/video* "
            "candidate could be opened"
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
                mismatch_msg = (
                    "Requested sensor format "
                    f"{active_width}x{active_height} was {reason}; "
                    f"sensor reports {detected_width}x{detected_height}"
                )

                # If the sensor rejects the requested format, keeping the requested
                # size for CSI/video often leads to a running node with no frames.
                # In that case, prefer a safe fallback to the detected sensor mode.
                must_adopt_for_stability = sensor_result.returncode != 0
                if self._adopt_detected_sensor_resolution or must_adopt_for_stability:
                    if must_adopt_for_stability and not self._adopt_detected_sensor_resolution:
                        self.get_logger().warn(
                            mismatch_msg
                            + "; overriding adopt_detected_sensor_resolution=false to keep stream alive"
                        )
                    self.get_logger().warn(
                        mismatch_msg + "; adopting detected resolution for capture"
                    )
                    active_width, active_height = detected_width, detected_height
                    self._width, self._height = active_width, active_height
                    fmt_string = (
                        f"fmt:UYVY8_1X16/{active_width}x{active_height} "
                        "field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
                    )
                else:
                    if self._fail_on_media_init_error:
                        raise RuntimeError(
                            mismatch_msg
                            + "; set adopt_detected_sensor_resolution=true or fix requested width/height"
                        )
                    self.get_logger().error(
                        mismatch_msg + "; keeping requested resolution for capture configuration"
                    )

        commands = [
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -V '\"{self._csi_entity}\":{self._csi_source_pad} [{fmt_string}]'",
            f"media-ctl -d {self._media_dev} -l '\"{self._csi_entity}\":{self._csi_source_pad} -> \"{self._video_entity}\":0 [1]'",
        ]

        trigger_cmd = None
        rate_controls_cmd = None
        if Path(self._sensor_subdev).exists():
            trigger_cmd = (
                f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl=trigger_mode={self._trigger_mode}"
            )

            if self._apply_sensor_rate_controls:
                rate_controls = [
                    f"max_fps={self._sensor_max_fps}",
                    f"ae_exposure_upper={self._sensor_ae_exposure_upper}",
                    f"ae_exposure_max={self._sensor_ae_exposure_max}",
                    f"exposure_mode={self._sensor_exposure_mode}",
                ]
                if self._sensor_exposure_mode == 0:
                    rate_controls.append(f"exposure={self._sensor_manual_exposure}")
                rate_controls_cmd = (
                    f"v4l2-ctl -d {self._sensor_subdev} --set-ctrl={','.join(rate_controls)}"
                )

        for cmd in commands:
            self._run_shell(cmd, allow_failure=not self._fail_on_media_init_error)
            time.sleep(self._command_delay_s)

        if trigger_cmd is not None and self._apply_sensor_trigger_control:
            self.get_logger().info(f"Applying sensor trigger control: trigger_mode={self._trigger_mode}")
            self._run_shell(trigger_cmd, allow_failure=not self._fail_on_media_init_error)
            time.sleep(self._command_delay_s)
        elif trigger_cmd is not None:
            self.get_logger().info("Skipping sensor trigger control write")

        if rate_controls_cmd is not None:
            self.get_logger().info(
                "Applying sensor rate controls: "
                f"max_fps={self._sensor_max_fps}, "
                f"ae_exposure_upper={self._sensor_ae_exposure_upper}, "
                f"ae_exposure_max={self._sensor_ae_exposure_max}, "
                f"exposure_mode={self._sensor_exposure_mode}, "
                f"manual_exposure={self._sensor_manual_exposure}"
            )
            rate_result = self._run_shell(rate_controls_cmd, allow_failure=True)
            if rate_result.returncode != 0:
                combined_output = (
                    f"{rate_result.stdout or ''}\n{rate_result.stderr or ''}"
                ).lower()
                if "connection timed out" in combined_output:
                    raise RuntimeError(
                        "Sensor rate control timed out while configuring camera; "
                        "aborting startup to avoid wedged capture path"
                    )

                self.get_logger().warn(
                    "Sensor rate control apply failed; continuing with current sensor defaults"
                )
                if trigger_cmd is not None and self._apply_sensor_trigger_control:
                    # Re-apply trigger control to recover a known-good baseline after timeout.
                    self._run_shell(trigger_cmd, allow_failure=True)
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

        self.get_logger().info(f"Opening camera: {self._device}")
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
            "Opened camera actual mode: "
            f"{actual_width}x{actual_height} @ {actual_fps:.2f} FPS, FOURCC={actual_fourcc}"
        )

        if actual_width != self._width or actual_height != self._height:
            self.get_logger().warn(
                "Requested capture size "
                f"{self._width}x{self._height} differs from actual {actual_width}x{actual_height}"
            )

        if self._fps > 0.0 and abs(actual_fps - self._fps) > 1.0:
            self.get_logger().warn(
                f"Requested FPS {self._fps:.2f} differs from actual {actual_fps:.2f}"
            )

        if len(self._fourcc) == 4 and actual_fourcc.upper() != self._fourcc.upper():
            self.get_logger().warn(
                f"Requested FOURCC {self._fourcc} differs from actual {actual_fourcc}"
            )

        self._cap = cap

    def _watchdog_loop(self) -> None:
        while not self._stop_event.wait(timeout=0.5):
            now = time.monotonic()

            with self._frame_lock:
                last_frame_time = self._last_frame_monotonic

            if last_frame_time <= 0.0:
                if now - self._start_monotonic > self._startup_frame_timeout_s:
                    self._exit_for_camera_watchdog(
                        "camera startup timed out before first frame "
                        f"({self._startup_frame_timeout_s:.1f}s)"
                    )
                    return
                continue

            if now - last_frame_time > self._stall_timeout_s:
                self._exit_for_camera_watchdog(
                    "camera frame stream stalled "
                    f"({now - last_frame_time:.1f}s without frames)"
                )
                return

    def _exit_for_camera_watchdog(self, reason: str) -> None:
        if self._watchdog_exit_started:
            return
        self._watchdog_exit_started = True
        try:
            self.get_logger().error(
                reason
                + "; exiting camera node so live stack can fail fast instead of hanging"
            )
        except Exception:
            pass
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        os._exit(12)

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

            capture_stamp = self.get_clock().now().to_msg()

            with self._frame_lock:
                self._latest_frame = frame
                self._latest_frame_id += 1
                self._last_frame_monotonic = time.monotonic()
                self._latest_capture_stamp_sec = int(capture_stamp.sec)
                self._latest_capture_stamp_nanosec = int(capture_stamp.nanosec)

            self._capture_frame_counter += 1
            self._publish_capture_fps_if_due()
            self._new_frame_event.set()
            if self._dashboard_pub is not None:
                self._dashboard_event.set()

    def _publisher_loop(self) -> None:
        next_publish_time = time.monotonic()

        while rclpy.ok() and not self._stop_event.is_set():
            if self._image_publish_period <= 0.0:
                has_new_frame = self._new_frame_event.wait(timeout=0.25)
                if not has_new_frame:
                    continue
                self._new_frame_event.clear()
                self._publish_latest_frame()
                continue

            now = time.monotonic()
            wait_timeout = max(0.0, next_publish_time - now)
            self._new_frame_event.wait(timeout=wait_timeout)
            self._new_frame_event.clear()

            now = time.monotonic()
            if now < next_publish_time:
                continue

            self._publish_latest_frame()

            next_publish_time += self._image_publish_period
            if (now - next_publish_time) > (self._image_publish_period * 4.0):
                next_publish_time = now + self._image_publish_period

    def _dashboard_loop(self) -> None:
        if self._dashboard_pub is None or self._dashboard_fps <= 0.0:
            return

        period = 1.0 / self._dashboard_fps
        next_publish_time = time.monotonic()

        while rclpy.ok() and not self._stop_event.is_set():
            now = time.monotonic()
            wait_timeout = max(0.0, next_publish_time - now)
            self._dashboard_event.wait(timeout=wait_timeout)
            self._dashboard_event.clear()

            now = time.monotonic()
            if now < next_publish_time:
                continue

            self._publish_dashboard_latest_frame()

            next_publish_time += period
            if (now - next_publish_time) > (period * 4.0):
                next_publish_time = now + period

    def _has_dashboard_subscribers(self) -> bool:
        if self._dashboard_pub is None:
            return False

        if not self._dashboard_publish_requires_subscribers:
            return True

        if self._stop_event.is_set() or not rclpy.ok():
            return False

        try:
            sub_count = self._dashboard_pub.get_subscription_count()
            intra_count = 0
            if hasattr(self._dashboard_pub, "get_intra_process_subscription_count"):
                intra_count = self._dashboard_pub.get_intra_process_subscription_count()
        except Exception as exc:
            if self._stop_event.is_set() or not rclpy.ok():
                return False
            raise exc

        return (sub_count + intra_count) > 0

    def _publish_dashboard_latest_frame(self) -> None:
        if self._dashboard_pub is None:
            return

        if not self._has_dashboard_subscribers():
            return

        with self._frame_lock:
            frame = self._latest_frame
            frame_id = self._latest_frame_id
            stamp_sec = self._latest_capture_stamp_sec
            stamp_nanosec = self._latest_capture_stamp_nanosec

        if frame is None:
            return

        if frame_id == self._last_dashboard_published_frame_id:
            return

        dashboard_frame = frame
        if frame.shape[1] != self._dashboard_width or frame.shape[0] != self._dashboard_height:
            if (
                self._dashboard_resize_buf is None
                or self._dashboard_resize_buf.shape[0] != self._dashboard_height
                or self._dashboard_resize_buf.shape[1] != self._dashboard_width
            ):
                self._dashboard_resize_buf = np.empty(
                    (self._dashboard_height, self._dashboard_width, 3), dtype=np.uint8
                )
            cv2.resize(
                frame,
                (self._dashboard_width, self._dashboard_height),
                dst=self._dashboard_resize_buf,
                interpolation=cv2.INTER_AREA,
            )
            dashboard_frame = self._dashboard_resize_buf

        dashboard_msg = self._bridge.cv2_to_imgmsg(dashboard_frame, encoding="bgr8")
        dashboard_msg.header.stamp.sec = int(stamp_sec)
        dashboard_msg.header.stamp.nanosec = int(stamp_nanosec)
        dashboard_msg.header.frame_id = self._frame_id
        if not self._try_publish(self._dashboard_pub, dashboard_msg):
            return
        self._last_dashboard_published_frame_id = frame_id

    def _prepare_publish_frame(self, frame: np.ndarray) -> np.ndarray:
        target_w = self._publish_width
        target_h = self._publish_height

        if frame.shape[1] == target_w and frame.shape[0] == target_h:
            return frame

        if (
            self._publish_resize_buf is None
            or self._publish_resize_buf.shape[0] != target_h
            or self._publish_resize_buf.shape[1] != target_w
        ):
            self._publish_resize_buf = np.empty((target_h, target_w, 3), dtype=np.uint8)

        src_h, src_w = frame.shape[:2]
        if self._publish_resize_mode == "resize":
            interpolation = cv2.INTER_AREA if (target_w <= src_w and target_h <= src_h) else cv2.INTER_LINEAR
            cv2.resize(
                frame,
                (target_w, target_h),
                dst=self._publish_resize_buf,
                interpolation=interpolation,
            )
            return self._publish_resize_buf

        self._publish_resize_buf.fill(0)
        scale = min(target_w / float(src_w), target_h / float(src_h))
        out_w = max(1, int(round(src_w * scale)))
        out_h = max(1, int(round(src_h * scale)))
        off_x = (target_w - out_w) // 2
        off_y = (target_h - out_h) // 2
        roi = self._publish_resize_buf[off_y:off_y + out_h, off_x:off_x + out_w]
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        cv2.resize(frame, (out_w, out_h), dst=roi, interpolation=interpolation)
        return self._publish_resize_buf

    def _publish_latest_frame(self) -> None:
        with self._frame_lock:
            frame = self._latest_frame
            frame_id = self._latest_frame_id
            stamp_sec = self._latest_capture_stamp_sec
            stamp_nanosec = self._latest_capture_stamp_nanosec

        if frame is None:
            return

        # Publish only new frames to avoid re-encoding and republishing duplicates.
        if frame_id == self._last_published_frame_id:
            return

        publish_frame = self._prepare_publish_frame(frame)
        if self._publish_encoding == "rgb8":
            if self._publish_rgb_buf is None or self._publish_rgb_buf.shape != publish_frame.shape:
                self._publish_rgb_buf = np.empty_like(publish_frame)
            cv2.cvtColor(publish_frame, cv2.COLOR_BGR2RGB, dst=self._publish_rgb_buf)
            msg = self._bridge.cv2_to_imgmsg(self._publish_rgb_buf, encoding="rgb8")
        else:
            msg = self._bridge.cv2_to_imgmsg(publish_frame, encoding="bgr8")

        msg.header.stamp.sec = int(stamp_sec)
        msg.header.stamp.nanosec = int(stamp_nanosec)
        msg.header.frame_id = self._frame_id
        if not self._try_publish(self._image_pub, msg):
            return
        self._last_published_frame_id = frame_id

        self._publish_frame_counter += 1
        self._publish_fps_if_due()

    def _publish_capture_fps_if_due(self) -> None:
        now = time.monotonic()
        dt = now - self._capture_fps_window_start

        if dt < 1.0:
            return

        capture_fps = self._capture_frame_counter / dt if dt > 0.0 else 0.0
        self._latest_capture_fps = capture_fps

        if self._capture_fps_pub is not None:
            capture_fps_msg = Float32()
            capture_fps_msg.data = float(capture_fps)
            self._try_publish(self._capture_fps_pub, capture_fps_msg)

        self._capture_frame_counter = 0
        self._capture_fps_window_start = now

    def _publish_fps_if_due(self) -> None:
        if self._fps_pub is None:
            return

        now = time.monotonic()
        dt = now - self._publish_fps_window_start

        if dt >= 1.0:
            fps = self._publish_frame_counter / dt if dt > 0.0 else 0.0
            self._latest_publish_fps = fps

            fps_msg = Float32()
            fps_msg.data = float(fps)
            if not self._try_publish(self._fps_pub, fps_msg):
                return

            self.get_logger().info(
                f"Camera FPS capture={self._latest_capture_fps:.2f} publish={fps:.2f}"
            )

            self._publish_frame_counter = 0
            self._publish_fps_window_start = now

    def _try_publish(self, publisher, msg) -> bool:
        if self._stop_event.is_set() or not rclpy.ok():
            return False

        try:
            publisher.publish(msg)
            return True
        except Exception as exc:
            if self._stop_event.is_set() or not rclpy.ok():
                return False
            raise exc

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
        self._dashboard_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._publisher_thread is not None and self._publisher_thread.is_alive():
            self._publisher_thread.join(timeout=2.0)

        if self._dashboard_thread is not None and self._dashboard_thread.is_alive():
            self._dashboard_thread.join(timeout=2.0)

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
    except (KeyboardInterrupt, ExternalShutdownException):
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
