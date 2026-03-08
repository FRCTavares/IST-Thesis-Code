#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from std_msgs.msg import String


class CameraInitNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("camera_init_node")

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("media_dev", "/dev/media0")
        self.declare_parameter("width", 1920)
        self.declare_parameter("height", 1080)
        self.declare_parameter("pixel_format", "UYVY")
        self.declare_parameter("sensor_entity", "tevs 10-0048")
        self.declare_parameter("csi_entity", "rp1-cfe-csi2_ch0")
        self.declare_parameter("trigger_mode", 0)
        self.declare_parameter("verify_stream", True)
        self.declare_parameter("stream_count", 5)
        self.declare_parameter("command_delay_s", 0.10)

        self._status_pub = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring TEVS camera")

        try:
            self._check_binaries()
            self._check_devices()
            self._init_media_pipeline()
            self._verify_format()
            if self.get_parameter("verify_stream").value:
                self._verify_streaming()

            self._status_pub = self.create_publisher(String, "/camera/status", 10)
            self.get_logger().info("TEVS camera configured successfully")
            return TransitionCallbackReturn.SUCCESS

        except Exception as exc:
            self.get_logger().error(f"Camera configuration failed: {exc}")
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activating camera_init_node")

        if self._status_pub is not None:
            self._status_pub.on_activate()
            msg = String()
            msg.data = "ready"
            self._status_pub.publish(msg)

        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Deactivating camera_init_node")

        if self._status_pub is not None:
            self._status_pub.on_deactivate()

        return TransitionCallbackReturn.SUCCESS

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

        if not device.exists():
            raise RuntimeError(f"Camera device not found: {device}")
        if not media_dev.exists():
            raise RuntimeError(f"Media device not found: {media_dev}")

    def _init_media_pipeline(self) -> None:
        media_dev = self.get_parameter("media_dev").value
        device = self.get_parameter("device").value
        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)
        pixel_format = self.get_parameter("pixel_format").value
        sensor_entity = self.get_parameter("sensor_entity").value
        csi_entity = self.get_parameter("csi_entity").value
        trigger_mode = int(self.get_parameter("trigger_mode").value)
        delay_s = float(self.get_parameter("command_delay_s").value)

        fmt_string = (
            f"fmt:UYVY8_1X16/{width}x{height} "
            "colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
        )

        commands = [
            f"media-ctl -d {media_dev} --reset",
            f"media-ctl -d {media_dev} -l '\"{sensor_entity}\":0 -> \"{csi_entity}\":0[1]'",
            f"media-ctl -d {media_dev} -V '\"{sensor_entity}\":0 [{fmt_string}]'",
            f"media-ctl -d {media_dev} -V '\"{csi_entity}\":0 [{fmt_string}]'",
            f"v4l2-ctl -d {device} --set-fmt-video=width={width},height={height},pixelformat={pixel_format}",
            f"v4l2-ctl -d {device} --set-ctrl=trigger_mode={trigger_mode}",
        ]

        for cmd in commands:
            self._run_shell(cmd)
            time.sleep(delay_s)

    def _verify_format(self) -> None:
        device = self.get_parameter("device").value
        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)
        pixel_format = self.get_parameter("pixel_format").value

        result = self._run_shell(
            f"v4l2-ctl -d {device} --get-fmt-video",
            capture_output=True,
        )

        stdout = result.stdout

        if pixel_format not in stdout:
            raise RuntimeError(
                f"Unexpected pixel format after init. Expected {pixel_format}. Output:\n{stdout}"
            )

        expected_size = f"Width/Height      : {width}/{height}"
        if expected_size not in stdout and f"{width}/{height}" not in stdout:
            raise RuntimeError(
                f"Unexpected resolution after init. Expected {width}x{height}. Output:\n{stdout}"
            )

        self.get_logger().info("Format verification passed")

    def _verify_streaming(self) -> None:
        device = self.get_parameter("device").value
        stream_count = int(self.get_parameter("stream_count").value)

        self._run_shell(
            f"v4l2-ctl -d {device} --stream-mmap=3 --stream-count={stream_count}",
            capture_output=True,
        )
        self.get_logger().info("Streaming verification passed")

    def _run_shell(
        self,
        cmd: str,
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        self.get_logger().info(f"Running: {cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            check=False,
            text=True,
            capture_output=capture_output,
        )

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
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()