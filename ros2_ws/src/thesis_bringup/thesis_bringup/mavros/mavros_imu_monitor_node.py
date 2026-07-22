#!/usr/bin/env python3
"""MAVROS IMU monitor for flight-controller connectivity checks.

This node subscribes to MAVROS IMU data and reports basic liveness/status for
ground validation of Pixhawk/MAVROS integration.
"""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import (
    Imu,
    MagneticField,
)


def quat_to_rpy_rad(x: float, y: float, z: float, w: float) -> tuple[float, float, float]:
    """Convert quaternion to roll, pitch, yaw in radians."""
    # Roll
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


class MavrosImuMonitorNode(Node):
    def __init__(self) -> None:
        super().__init__("mavros_imu_monitor_node")

        self.declare_parameter("imu_topic", "/mavros/imu/data")
        self.declare_parameter("raw_imu_topic", "/mavros/imu/data_raw")
        self.declare_parameter("mag_topic", "/mavros/imu/mag")
        self.declare_parameter("print_hz", 2.0)
        self.declare_parameter("subscribe_raw", True)
        self.declare_parameter("subscribe_mag", True)

        self.imu_topic = str(self.get_parameter("imu_topic").value)
        self.raw_imu_topic = str(self.get_parameter("raw_imu_topic").value)
        self.mag_topic = str(self.get_parameter("mag_topic").value)
        self.print_hz = float(self.get_parameter("print_hz").value)
        self.subscribe_raw = bool(self.get_parameter("subscribe_raw").value)
        self.subscribe_mag = bool(self.get_parameter("subscribe_mag").value)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.latest_imu: Optional[Imu] = None
        self.latest_raw_imu: Optional[Imu] = None
        self.latest_mag: Optional[MagneticField] = None

        self.imu_count = 0
        self.raw_imu_count = 0
        self.mag_count = 0

        self.create_subscription(Imu, self.imu_topic, self._on_imu, qos)

        if self.subscribe_raw:
            self.create_subscription(Imu, self.raw_imu_topic, self._on_raw_imu, qos)

        if self.subscribe_mag:
            self.create_subscription(MagneticField, self.mag_topic, self._on_mag, qos)

        timer_period = 1.0 / max(self.print_hz, 0.1)
        self.create_timer(timer_period, self._print_status)

        self.get_logger().info(f"subscribing imu_topic={self.imu_topic}")
        if self.subscribe_raw:
            self.get_logger().info(f"subscribing raw_imu_topic={self.raw_imu_topic}")
        if self.subscribe_mag:
            self.get_logger().info(f"subscribing mag_topic={self.mag_topic}")

    def _on_imu(self, msg: Imu) -> None:
        self.latest_imu = msg
        self.imu_count += 1

    def _on_raw_imu(self, msg: Imu) -> None:
        self.latest_raw_imu = msg
        self.raw_imu_count += 1

    def _on_mag(self, msg: MagneticField) -> None:
        self.latest_mag = msg
        self.mag_count += 1

    def _print_status(self) -> None:
        if self.latest_imu is None:
            self.get_logger().warn(f"no IMU messages yet on {self.imu_topic}")
            return

        imu = self.latest_imu

        q = imu.orientation
        roll, pitch, yaw = quat_to_rpy_rad(q.x, q.y, q.z, q.w)

        av = imu.angular_velocity
        la = imu.linear_acceleration

        msg = (
            f"imu_count={self.imu_count} "
            f"rpy_deg=({math.degrees(roll):+.1f}, {math.degrees(pitch):+.1f}, {math.degrees(yaw):+.1f}) "
            f"gyro_rad_s=({av.x:+.3f}, {av.y:+.3f}, {av.z:+.3f}) "
            f"accel_m_s2=({la.x:+.3f}, {la.y:+.3f}, {la.z:+.3f})"
        )

        if self.latest_raw_imu is not None:
            raw = self.latest_raw_imu
            rav = raw.angular_velocity
            rla = raw.linear_acceleration
            msg += (
                f" | raw_count={self.raw_imu_count} "
                f"raw_gyro=({rav.x:+.3f}, {rav.y:+.3f}, {rav.z:+.3f}) "
                f"raw_accel=({rla.x:+.3f}, {rla.y:+.3f}, {rla.z:+.3f})"
            )

        if self.latest_mag is not None:
            mag = self.latest_mag.magnetic_field
            msg += (
                f" | mag_count={self.mag_count} "
                f"mag=({mag.x:+.6f}, {mag.y:+.6f}, {mag.z:+.6f})"
            )

        self.get_logger().info(msg)


def main() -> None:
    rclpy.init()
    node = MavrosImuMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
