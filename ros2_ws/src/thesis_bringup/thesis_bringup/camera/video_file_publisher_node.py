#!/usr/bin/env python3

from __future__ import annotations

from collections import deque
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32


class VideoFilePublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("video_file_publisher_node")

        self.declare_parameter("video_path", "")
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("fps_topic", "/camera/fps")
        self.declare_parameter("frame_id", "camera")
        self.declare_parameter("loop", True)
        self.declare_parameter("target_fps", 30.0)
        self.declare_parameter("output_width", 0)
        self.declare_parameter("output_height", 0)
        self.declare_parameter("output_encoding", "rgb8")
        self.declare_parameter("image_reliability", "best_effort")
        self.declare_parameter("image_qos_depth", 1)
        self.declare_parameter("publish_dashboard_topic", False)
        self.declare_parameter("dashboard_topic", "/camera/dashboard")
        self.declare_parameter("dashboard_width", 640)
        self.declare_parameter("dashboard_height", 360)
        self.declare_parameter("dashboard_fps", 10.0)
        self.declare_parameter("replay_progress_topic", "/camera/replay_progress")

        self._video_path = str(self.get_parameter("video_path").value).strip()
        self._image_topic = str(self.get_parameter("image_topic").value)
        self._fps_topic = str(self.get_parameter("fps_topic").value)
        self._frame_id = str(self.get_parameter("frame_id").value)
        self._loop = bool(self.get_parameter("loop").value)
        self._target_fps = float(self.get_parameter("target_fps").value)
        self._output_width = int(self.get_parameter("output_width").value)
        self._output_height = int(self.get_parameter("output_height").value)
        self._output_encoding = str(self.get_parameter("output_encoding").value).strip().lower()
        self._image_reliability = str(self.get_parameter("image_reliability").value).strip().lower()
        self._image_qos_depth = max(1, int(self.get_parameter("image_qos_depth").value))
        self._publish_dashboard_topic = bool(self.get_parameter("publish_dashboard_topic").value)
        self._dashboard_topic = str(self.get_parameter("dashboard_topic").value)
        self._dashboard_width = int(self.get_parameter("dashboard_width").value)
        self._dashboard_height = int(self.get_parameter("dashboard_height").value)
        self._dashboard_fps = float(self.get_parameter("dashboard_fps").value)
        self._replay_progress_topic = str(self.get_parameter("replay_progress_topic").value)

        if self._output_encoding not in ("rgb8", "bgr8"):
            raise RuntimeError(
                f"Unsupported output_encoding '{self._output_encoding}'. Expected rgb8 or bgr8"
            )

        if not self._video_path:
            raise RuntimeError("Parameter video_path is required")

        path = Path(self._video_path)
        if not path.exists():
            raise RuntimeError(f"Video file not found: {path}")

        self._cap = cv2.VideoCapture(self._video_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open video file: {self._video_path}")

        src_fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if self._target_fps <= 0.0:
            self._target_fps = src_fps if src_fps > 0.0 else 30.0

        image_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=self._image_qos_depth,
        )
        if self._image_reliability == "reliable":
            image_qos.reliability = ReliabilityPolicy.RELIABLE
        elif self._image_reliability not in ("best_effort", "besteffort"):
            self.get_logger().warning(
                f"invalid image_reliability='{self._image_reliability}', using best_effort"
            )
        self._image_pub = self.create_publisher(Image, self._image_topic, image_qos)
        self._fps_pub = self.create_publisher(Float32, self._fps_topic, image_qos)
        replay_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._replay_progress_pub = self.create_publisher(Float32, self._replay_progress_topic, replay_qos)

        self._dashboard_pub = None
        if self._publish_dashboard_topic:
            dashboard_qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
            )
            self._dashboard_pub = self.create_publisher(Image, self._dashboard_topic, dashboard_qos)

        self._bridge = CvBridge()
        self._rgb_buffer: np.ndarray | None = None
        self._dashboard_buffer: np.ndarray | None = None
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._frame_count = 0
        self._fps_window_ns: deque[int] = deque(maxlen=240)
        self._last_fps_pub_ns = 0
        self._last_dashboard_pub_ns = 0
        self._dashboard_period_ns = 0
        if self._dashboard_pub is not None and self._dashboard_fps > 0.0:
            self._dashboard_period_ns = int(1e9 / self._dashboard_fps)

        self.create_timer(1.0 / self._target_fps, self._publish_tick)

        self.get_logger().info(
            f"video_file_publisher_node started video={self._video_path} "
            f"image_topic={self._image_topic} fps_topic={self._fps_topic} target_fps={self._target_fps:.2f} "
            f"dashboard_fps={self._dashboard_fps:.2f} output_encoding={self._output_encoding} "
            f"image_reliability={self._image_reliability} image_qos_depth={self._image_qos_depth} "
            f"loop={self._loop}"
        )

        if self._total_frames <= 1:
            self.get_logger().warning(
                "Unable to infer reliable replay progress from CAP_PROP_FRAME_COUNT; "
                "auto-log stop near loop may be unavailable."
            )

    def _read_frame(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        if ok:
            return frame

        if not self._loop:
            return None

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = self._cap.read()
        if ok:
            return frame
        return None

    def _publish_tick(self) -> None:
        if not rclpy.ok():
            return

        frame = self._read_frame()
        if frame is None:
            if not self._loop:
                self.get_logger().info("Video ended; shutting down node because loop=false")
                rclpy.shutdown()
            else:
                self.get_logger().warning("Unable to read frame from video file")
            return

        if self._output_width > 0 and self._output_height > 0:
            frame = cv2.resize(
                frame,
                (self._output_width, self._output_height),
                interpolation=cv2.INTER_LINEAR,
            )

        stamp = self.get_clock().now().to_msg()

        if self._dashboard_pub is not None:
            now_ns = self.get_clock().now().nanoseconds
            should_pub_dashboard = self._dashboard_period_ns <= 0
            if not should_pub_dashboard:
                should_pub_dashboard = (now_ns - self._last_dashboard_pub_ns) >= self._dashboard_period_ns

            if should_pub_dashboard:
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
                try:
                    self._dashboard_pub.publish(dashboard_msg)
                except Exception:
                    return
                self._last_dashboard_pub_ns = now_ns

        if self._output_encoding == "rgb8":
            if self._rgb_buffer is None or self._rgb_buffer.shape != frame.shape:
                self._rgb_buffer = np.empty_like(frame)
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=self._rgb_buffer)
            msg = self._bridge.cv2_to_imgmsg(self._rgb_buffer, encoding="rgb8")
        else:
            msg = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")

        msg.header.stamp = stamp
        msg.header.frame_id = self._frame_id
        try:
            self._image_pub.publish(msg)
        except Exception:
            return

        now_ns = self.get_clock().now().nanoseconds
        self._fps_window_ns.append(now_ns)

        if self._total_frames > 1:
            pos_frames = float(self._cap.get(cv2.CAP_PROP_POS_FRAMES) or 1.0)
            progress = (pos_frames - 1.0) / max(1.0, float(self._total_frames - 1))
            progress = max(0.0, min(1.0, progress))
            progress_msg = Float32()
            progress_msg.data = float(progress)
            try:
                self._replay_progress_pub.publish(progress_msg)
            except Exception:
                return

        window_ns = 3_000_000_000
        cutoff_ns = now_ns - window_ns
        while self._fps_window_ns and self._fps_window_ns[0] < cutoff_ns:
            self._fps_window_ns.popleft()

        if (now_ns - self._last_fps_pub_ns) >= 200_000_000 and len(self._fps_window_ns) >= 2:
            dt_ns = self._fps_window_ns[-1] - self._fps_window_ns[0]
            if dt_ns > 0:
                fps_msg = Float32()
                fps_msg.data = float(len(self._fps_window_ns) - 1) / (dt_ns / 1e9)
                try:
                    self._fps_pub.publish(fps_msg)
                except Exception:
                    return
                self._last_fps_pub_ns = now_ns

        self._frame_count += 1
        if self._frame_count % 300 == 0:
            self.get_logger().info(f"published_frames={self._frame_count}")

    def destroy_node(self):
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VideoFilePublisherNode()

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
