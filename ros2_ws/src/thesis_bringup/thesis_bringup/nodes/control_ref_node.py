from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from geometry_msgs.msg import TwistStamped
from thesis_msgs.msg import TargetState


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def apply_deadband(x: float, deadband: float) -> float:
    return 0.0 if abs(x) < deadband else x


class ControlRefNode(Node):
    def __init__(self) -> None:
        super().__init__('control_ref_node')

        self.declare_parameter('target_topic', '/target')
        self.declare_parameter('cmd_topic', '/control_ref/cmd_vel')
        self.declare_parameter('rate_hz', 30.0)
        self.declare_parameter('stale_timeout_s', 0.2)

        self.declare_parameter('img_w', 640.0)
        self.declare_parameter('img_h', 640.0)

        self.declare_parameter('min_score_valid', 0.10)
        self.declare_parameter('min_quality_valid', 0.05)

        self.declare_parameter('desired_h_norm', 0.25)

        self.declare_parameter('yaw_kp', 0.4)
        self.declare_parameter('forward_kp', 0.4)
        self.declare_parameter('lateral_kp', 0.0)

        self.declare_parameter('deadband_ex', 0.03)
        self.declare_parameter('deadband_h', 0.02)

        self.declare_parameter('max_yaw_z', 0.10)
        self.declare_parameter('max_vx', 0.10)
        self.declare_parameter('max_vy', 0.10)

        self.declare_parameter('max_delta_yaw_z', 0.03)
        self.declare_parameter('max_delta_vx', 0.03)
        self.declare_parameter('max_delta_vy', 0.03)

        self.declare_parameter('use_lateral', False)

        self.declare_parameter('invert_yaw', False)
        self.declare_parameter('invert_forward', False)
        self.declare_parameter('invert_lateral', False)

        self.declare_parameter('debug_log_every_n', 30)

        target_topic = str(self.get_parameter('target_topic').value)
        cmd_topic = str(self.get_parameter('cmd_topic').value)
        rate_hz = float(self.get_parameter('rate_hz').value)

        self.stale_timeout_s = float(self.get_parameter('stale_timeout_s').value)

        self.img_w = float(self.get_parameter('img_w').value)
        self.img_h = float(self.get_parameter('img_h').value)

        self.min_score_valid = float(self.get_parameter('min_score_valid').value)
        self.min_quality_valid = float(self.get_parameter('min_quality_valid').value)

        self.desired_h_norm = float(self.get_parameter('desired_h_norm').value)

        self.yaw_kp = float(self.get_parameter('yaw_kp').value)
        self.forward_kp = float(self.get_parameter('forward_kp').value)
        self.lateral_kp = float(self.get_parameter('lateral_kp').value)

        self.deadband_ex = float(self.get_parameter('deadband_ex').value)
        self.deadband_h = float(self.get_parameter('deadband_h').value)

        self.max_yaw_z = float(self.get_parameter('max_yaw_z').value)
        self.max_vx = float(self.get_parameter('max_vx').value)
        self.max_vy = float(self.get_parameter('max_vy').value)

        self.max_delta_yaw_z = float(self.get_parameter('max_delta_yaw_z').value)
        self.max_delta_vx = float(self.get_parameter('max_delta_vx').value)
        self.max_delta_vy = float(self.get_parameter('max_delta_vy').value)

        self.use_lateral = bool(self.get_parameter('use_lateral').value)

        self.invert_yaw = bool(self.get_parameter('invert_yaw').value)
        self.invert_forward = bool(self.get_parameter('invert_forward').value)
        self.invert_lateral = bool(self.get_parameter('invert_lateral').value)

        self.debug_log_every_n = int(self.get_parameter('debug_log_every_n').value)

        self.last_target: Optional[TargetState] = None
        self.last_target_rx_time = None

        self.prev_vx = 0.0
        self.prev_vy = 0.0
        self.prev_yaw_z = 0.0
        self.tick_count = 0

        target_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.sub_target = self.create_subscription(
            TargetState,
            target_topic,
            self.on_target,
            target_qos,
        )

        self.pub_cmd = self.create_publisher(TwistStamped, cmd_topic, 10)

        self.timer = self.create_timer(1.0 / rate_hz, self.on_timer)

        self.get_logger().info(f'Listening on {target_topic}')
        self.get_logger().info(f'Publishing commands to {cmd_topic}')

    def on_target(self, msg: TargetState) -> None:
        self.last_target = msg
        self.last_target_rx_time = self.get_clock().now()

    def is_fresh(self) -> bool:
        if self.last_target_rx_time is None:
            return False
        age_s = (self.get_clock().now() - self.last_target_rx_time).nanoseconds * 1e-9
        return age_s <= self.stale_timeout_s

    def target_valid(self, t: TargetState) -> bool:
        if not self.is_fresh():
            return False
        if not (0.0 <= t.cx <= self.img_w and 0.0 <= t.cy <= self.img_h):
            return False
        if not (0.0 < t.w <= self.img_w and 0.0 < t.h <= self.img_h):
            return False
        if t.score < self.min_score_valid:
            return False
        if t.quality < self.min_quality_valid:
            return False
        return True

    def slew(self, x: float, x_prev: float, max_delta: float) -> float:
        return clamp(x, x_prev - max_delta, x_prev + max_delta)

    def publish_cmd(self, vx: float, vy: float, yaw_z: float) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.twist.linear.x = vx
        msg.twist.linear.y = vy
        msg.twist.linear.z = 0.0
        msg.twist.angular.x = 0.0
        msg.twist.angular.y = 0.0
        msg.twist.angular.z = yaw_z
        self.pub_cmd.publish(msg)

    def publish_zero(self) -> None:
        self.prev_vx = self.slew(0.0, self.prev_vx, self.max_delta_vx)
        self.prev_vy = self.slew(0.0, self.prev_vy, self.max_delta_vy)
        self.prev_yaw_z = self.slew(0.0, self.prev_yaw_z, self.max_delta_yaw_z)
        self.publish_cmd(self.prev_vx, self.prev_vy, self.prev_yaw_z)

    def on_timer(self) -> None:
        self.tick_count += 1

        if self.last_target is None:
            self.publish_zero()
            return

        t = self.last_target

        if not self.target_valid(t):
            self.publish_zero()
            return

        cx_norm = float(t.cx) / self.img_w
        h_norm = float(t.h) / self.img_h

        ex = cx_norm - 0.5
        range_err = self.desired_h_norm - h_norm

        ex = apply_deadband(ex, self.deadband_ex)
        range_err = apply_deadband(range_err, self.deadband_h)

        yaw_sign = -1.0 if self.invert_yaw else 1.0
        forward_sign = -1.0 if self.invert_forward else 1.0
        lateral_sign = -1.0 if self.invert_lateral else 1.0

        yaw_z_cmd = clamp(yaw_sign * self.yaw_kp * ex, -self.max_yaw_z, self.max_yaw_z)
        vx_cmd = clamp(forward_sign * self.forward_kp * range_err, -self.max_vx, self.max_vx)

        if self.use_lateral:
            vy_cmd = clamp(lateral_sign * self.lateral_kp * ex, -self.max_vy, self.max_vy)
        else:
            vy_cmd = 0.0

        self.prev_vx = self.slew(vx_cmd, self.prev_vx, self.max_delta_vx)
        self.prev_vy = self.slew(vy_cmd, self.prev_vy, self.max_delta_vy)
        self.prev_yaw_z = self.slew(yaw_z_cmd, self.prev_yaw_z, self.max_delta_yaw_z)

        self.publish_cmd(self.prev_vx, self.prev_vy, self.prev_yaw_z)

        if self.debug_log_every_n > 0 and (self.tick_count % self.debug_log_every_n == 0):
            self.get_logger().info(
                f'id={t.id} cx_px={t.cx:.1f} h_px={t.h:.1f} '
                f'cx_norm={cx_norm:.3f} h_norm={h_norm:.3f} '
                f'score={t.score:.3f} quality={t.quality:.3f} '
                f'ex={ex:.3f} range_err={range_err:.3f} '
                f'vx={self.prev_vx:.3f} vy={self.prev_vy:.3f} yaw_z={self.prev_yaw_z:.3f}'
            )

def main(args=None) -> None:
    rclpy.init(args=args)
    node = ControlRefNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if rclpy.ok():
                node.publish_zero()
        except Exception:
            pass

        try:
            node.destroy_node()
        except Exception:
            pass

        try:
            rclpy.try_shutdown()
        except Exception:
            pass

if __name__ == '__main__':
    main()
