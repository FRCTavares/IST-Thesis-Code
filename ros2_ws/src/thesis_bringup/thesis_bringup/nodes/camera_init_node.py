#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import String


class CameraInitNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("camera_init_node")

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("media_dev", "/dev/media0")
        self.declare_parameter("sensor_subdev", "/dev/v4l-subdev2")

        self.declare_parameter("width", 1920)
        self.declare_parameter("height", 1080)

        self.declare_parameter("sensor_entity", "tevs 11-0048")
        self.declare_parameter("csi_entity", "csi2")
        self.declare_parameter("csi_source_pad", 4)
        self.declare_parameter("video_entity", "rp1-cfe-csi2_ch0")

        self.declare_parameter("trigger_mode", 0)
        self.declare_parameter("command_delay_s", 0.10)
        self.declare_parameter("command_timeout_s", 5.0)

        self._status_pub = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring TEVS camera")

        try:
            self._check_binaries()
            self._check_devices()
            self._init_media_pipeline()

            qos = QoSProfile(depth=1)
            qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
            qos.reliability = ReliabilityPolicy.RELIABLE
            self._status_pub = self.create_publisher(String, "/camera/status", qos)

            msg = String()
            msg.data = "ready"
            self._status_pub.publish(msg)

            self.get_logger().info("TEVS camera configured successfully")
            return TransitionCallbackReturn.SUCCESS

        except Exception as exc:
            self.get_logger().error(f"Camera configuration failed: {exc}")
            return TransitionCallbackReturn.FAILURE

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Cleaning up camera_init_node")
        self._status_pub = None
        return TransitionCallbackReturn.SUCCESS

    def _check_binaries(self) -> None:
        for tool in ("media-ctl", "v4l2-ctl"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"Required binary not found in PATH: {tool}")

    def _check_devices(self) -> None:
        device = Path(self.get_parameter("device").value)
        media_dev = Path(self.get_parameter("media_dev").value)
        sensor_subdev = Path(self.get_parameter("sensor_subdev").value)

        if not device.exists():
            raise RuntimeError(f"Camera device not found: {device}")
        if not media_dev.exists():
            raise RuntimeError(f"Media device not found: {media_dev}")
        if not sensor_subdev.exists():
            raise RuntimeError(f"Sensor subdevice not found: {sensor_subdev}")

    def _init_media_pipeline(self) -> None:
        media_dev = self.get_parameter("media_dev").value
        sensor_subdev = self.get_parameter("sensor_subdev").value

        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)

        sensor_entity = self.get_parameter("sensor_entity").value
        csi_entity = self.get_parameter("csi_entity").value
        csi_source_pad = int(self.get_parameter("csi_source_pad").value)
        video_entity = self.get_parameter("video_entity").value

        trigger_mode = int(self.get_parameter("trigger_mode").value)
        delay_s = float(self.get_parameter("command_delay_s").value)

        fmt_string = (
            f"fmt:UYVY8_1X16/{width}x{height} "
            "colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
        )

        commands = [
            f"media-ctl -d {media_dev} -V '\"{sensor_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {media_dev} -V '\"{csi_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {media_dev} -V '\"{csi_entity}\":{csi_source_pad} [{fmt_string}]'",
            f"media-ctl -d {media_dev} -l '\"{csi_entity}\":{csi_source_pad} -> \"{video_entity}\":0 [1]'",
            f"v4l2-ctl -d {sensor_subdev} --set-ctrl=trigger_mode={trigger_mode}",
        ]

        for cmd in commands:
            self._run_shell(cmd)
            time.sleep(delay_s)

    def _run_shell(
        self,
        cmd: str,
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        self.get_logger().info(f"Running: {cmd}")

        timeout_s = float(self.get_parameter("command_timeout_s").value)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=False,
                text=True,
                capture_output=capture_output,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Command timed out after {exc.timeout}s\nCMD: {cmd}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            raise RuntimeError(
                f"Command failed with code {result.returncode}\n"
                f"CMD: {cmd}\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        return result


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CameraInitNode()

    try:
        result = node.trigger_configure()
        if result != TransitionCallbackReturn.SUCCESS:
            raise RuntimeError("camera_init_node failed to configure")
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