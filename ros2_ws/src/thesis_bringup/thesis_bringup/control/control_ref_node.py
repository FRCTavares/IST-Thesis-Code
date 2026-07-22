"""Selected-target to velocity-reference controller node.

This node converts the current selected target state into body-frame velocity
references for ground validation and optional MAVROS publication. It includes
target freshness checks, saturation, slew limiting, and fail-safe zero output.
"""

from typing import Optional

from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from thesis_msgs.msg import TargetState


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def apply_deadband(x: float, deadband: float) -> float:
    return 0.0 if abs(x) < deadband else x


def compute_control_command(
    *,
    cx: float,
    h: float,
    img_w: float,
    img_h: float,
    desired_h_norm: float,
    yaw_kp: float,
    forward_kp: float,
    lateral_kp: float,
    deadband_ex: float,
    deadband_h: float,
    max_yaw_z: float,
    max_vx: float,
    max_vy: float,
    use_lateral: bool,
    invert_yaw: bool,
    invert_forward: bool,
    invert_lateral: bool,
) -> tuple[float, float, float, float, float, float, float]:
    """Compute unslewed body-frame commands and diagnostic errors."""
    if img_w <= 0.0 or img_h <= 0.0:
        raise ValueError("image dimensions must be positive")

    cx_norm = float(cx) / img_w
    h_norm = float(h) / img_h

    ex = apply_deadband(cx_norm - 0.5, deadband_ex)
    range_err = apply_deadband(
        desired_h_norm - h_norm,
        deadband_h,
    )

    yaw_sign = -1.0 if invert_yaw else 1.0
    forward_sign = -1.0 if invert_forward else 1.0
    lateral_sign = -1.0 if invert_lateral else 1.0

    yaw_z_cmd = clamp(
        yaw_sign * yaw_kp * ex,
        -max_yaw_z,
        max_yaw_z,
    )
    vx_cmd = clamp(
        forward_sign * forward_kp * range_err,
        -max_vx,
        max_vx,
    )

    if use_lateral:
        vy_cmd = clamp(
            lateral_sign * lateral_kp * ex,
            -max_vy,
            max_vy,
        )
    else:
        vy_cmd = 0.0

    return (
        vx_cmd,
        vy_cmd,
        yaw_z_cmd,
        cx_norm,
        h_norm,
        ex,
        range_err,
    )


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
        self.declare_parameter('enable_mavros', False)
        self.declare_parameter('mavros_topic', '/mavros/setpoint_velocity/cmd_vel')
        self.declare_parameter('cmd_frame_id', 'base_link')
        self.declare_parameter('mavros_frame_id', 'base_link')
        self.declare_parameter('invalid_warn_every_n', 30)
        self.declare_parameter('timer_slip_warn_factor', 2.0)
        self.declare_parameter('enable_ambiguity_hold', False)
        self.declare_parameter('ambiguity_quality_threshold', 0.5)
        self.declare_parameter('ambiguity_warn_every_n', 30)
        self.declare_parameter('saturation_warn_every_n', 90)

        target_topic = str(self.get_parameter('target_topic').value)
        cmd_topic = str(self.get_parameter('cmd_topic').value)
        rate_hz = float(self.get_parameter('rate_hz').value)
        self.enable_mavros = bool(self.get_parameter('enable_mavros').value)
        self.mavros_topic = str(self.get_parameter('mavros_topic').value)
        self.cmd_frame_id = str(self.get_parameter('cmd_frame_id').value)
        self.mavros_frame_id = str(self.get_parameter('mavros_frame_id').value)
        self.invalid_warn_every_n = int(self.get_parameter('invalid_warn_every_n').value)
        self.timer_slip_warn_factor = float(self.get_parameter('timer_slip_warn_factor').value)
        self.enable_ambiguity_hold = bool(self.get_parameter('enable_ambiguity_hold').value)
        self.ambiguity_quality_threshold = float(
            self.get_parameter('ambiguity_quality_threshold').value
        )
        self.ambiguity_warn_every_n = int(self.get_parameter('ambiguity_warn_every_n').value)
        self.saturation_warn_every_n = int(self.get_parameter('saturation_warn_every_n').value)

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
        self.expected_period_s = 1.0 / rate_hz if rate_hz > 0.0 else 0.0
        self.last_timer_time = None
        self.last_invalid_reason: Optional[str] = None
        self.invalid_count = 0
        self.valid_prev_tick = False
        self.last_mode: Optional[str] = None
        self.saturation_count = 0
        self._ambiguity_prev = False
        self._ambiguity_count = 0

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
        self.pub_mavros = self.create_publisher(TwistStamped, self.mavros_topic, 10)

        self.timer = self.create_timer(1.0 / rate_hz, self.on_timer)

        self.get_logger().info(f'Listening on {target_topic}')
        self.get_logger().info(f'Publishing commands to {cmd_topic}')
        self.get_logger().info(
            f'Command frame_id={self.cmd_frame_id} | MAVROS frame_id={self.mavros_frame_id}'
        )
        self.get_logger().info(
            f'MAVROS mirroring '
            f'{"enabled" if self.enable_mavros else "disabled"} '
            f'on {self.mavros_topic}'
        )

    def on_target(self, msg: TargetState) -> None:
        self.last_target = msg
        self.last_target_rx_time = self.get_clock().now()

    def is_fresh(self) -> bool:
        if self.last_target_rx_time is None:
            return False
        age_s = (self.get_clock().now() - self.last_target_rx_time).nanoseconds * 1e-9
        return age_s <= self.stale_timeout_s

    def target_age_s(self) -> Optional[float]:
        if self.last_target_rx_time is None:
            return None
        return (self.get_clock().now() - self.last_target_rx_time).nanoseconds * 1e-9

    def target_invalid_reason(self, t: TargetState) -> Optional[str]:
        if t.id == 0:
            return 'id_zero'

        age_s = self.target_age_s()
        if age_s is None:
            return 'no_target_rx_time'
        if age_s > self.stale_timeout_s:
            return f'stale_target(age={age_s:.3f}s>{self.stale_timeout_s:.3f}s)'

        if not (0.0 <= t.cx <= self.img_w and 0.0 <= t.cy <= self.img_h):
            return 'target_out_of_bounds'
        if not (0.0 < t.w <= self.img_w and 0.0 < t.h <= self.img_h):
            return 'target_invalid_size'
        if t.score < self.min_score_valid:
            return f'low_score({t.score:.3f}<{self.min_score_valid:.3f})'
        if t.quality < self.min_quality_valid:
            return f'low_quality({t.quality:.3f}<{self.min_quality_valid:.3f})'
        return None

    def target_valid(self, t: TargetState) -> bool:
        return self.target_invalid_reason(t) is None

    def slew(self, x: float, x_prev: float, max_delta: float) -> float:
        return clamp(x, x_prev - max_delta, x_prev + max_delta)

    def _make_twist_msg(
        self,
        stamp,
        vx: float,
        vy: float,
        yaw_z: float,
        frame_id: str,
    ) -> TwistStamped:
        msg = TwistStamped()
        msg.header.stamp = stamp
        msg.header.frame_id = frame_id
        msg.twist.linear.x = float(vx)
        msg.twist.linear.y = float(vy)
        msg.twist.linear.z = 0.0
        msg.twist.angular.x = 0.0
        msg.twist.angular.y = 0.0
        msg.twist.angular.z = float(yaw_z)
        return msg

    def publish_pair(self, stamp, vx: float, vy: float, yaw_z: float) -> None:
        """Publish matching commands to debug and optional MAVROS topics.

        Both messages share the same header stamp for reliable topic checks.
        """
        msg = self._make_twist_msg(stamp, vx, vy, yaw_z, self.cmd_frame_id)
        self.pub_cmd.publish(msg)
        if self.enable_mavros:
            self.pub_mavros.publish(
                self._make_twist_msg(
                    stamp,
                    vx,
                    vy,
                    yaw_z,
                    self.mavros_frame_id,
                )
            )

    def maybe_warn_invalid_target(self, reason: str, t: Optional[TargetState]) -> None:
        self.invalid_count += 1
        should_log = (
            reason != self.last_invalid_reason
            or (
                self.invalid_warn_every_n > 0
                and (self.invalid_count % self.invalid_warn_every_n == 0)
            )
        )
        if should_log:
            age_s = self.target_age_s()
            age_str = f'{age_s:.3f}s' if age_s is not None else 'n/a'
            if t is None:
                self.get_logger().warn(f'target invalid: {reason} age={age_str}')
            else:
                self.get_logger().warn(
                    f'target invalid: {reason} age={age_str} '
                    f'id={t.id} cx={t.cx:.1f} cy={t.cy:.1f} w={t.w:.1f} h={t.h:.1f} '
                    f'score={t.score:.3f} quality={t.quality:.3f}'
                )
        self.last_invalid_reason = reason

    def publish_zero(self) -> None:
        self.prev_vx = 0.0
        self.prev_vy = 0.0
        self.prev_yaw_z = 0.0
        self.publish_pair(self.get_clock().now().to_msg(), 0.0, 0.0, 0.0)

    def update_mode(self, mode: str) -> None:
        if mode != self.last_mode:
            self.get_logger().info(
                f'control_mode_transition: '
                f'{self.last_mode or "INIT"} -> {mode}'
            )
            self.last_mode = mode

    def is_ambiguous(self, t: TargetState) -> bool:
        return t.id > 0 and t.quality < self.ambiguity_quality_threshold

    def maybe_warn_saturation(self, vx_cmd: float, vy_cmd: float, yaw_z_cmd: float) -> None:
        saturated_axes = []
        if self.max_vx > 0.0 and abs(vx_cmd) >= (0.99 * self.max_vx):
            saturated_axes.append(f'vx={vx_cmd:.3f}/{self.max_vx:.3f}')
        if self.max_vy > 0.0 and abs(vy_cmd) >= (0.99 * self.max_vy):
            saturated_axes.append(f'vy={vy_cmd:.3f}/{self.max_vy:.3f}')
        if self.max_yaw_z > 0.0 and abs(yaw_z_cmd) >= (0.99 * self.max_yaw_z):
            saturated_axes.append(f'yaw_z={yaw_z_cmd:.3f}/{self.max_yaw_z:.3f}')

        if not saturated_axes:
            return

        self.saturation_count += 1
        should_log = (
            self.saturation_warn_every_n > 0
            and (self.saturation_count % self.saturation_warn_every_n == 0)
        )
        if should_log:
            self.get_logger().warn('command_saturation: ' + ' '.join(saturated_axes))

    def on_timer(self) -> None:
        self.tick_count += 1

        now = self.get_clock().now()
        if (
            self.last_timer_time is not None
            and self.expected_period_s > 0.0
            and self.timer_slip_warn_factor > 1.0
        ):
            dt_s = (now - self.last_timer_time).nanoseconds * 1e-9
            if dt_s > (self.expected_period_s * self.timer_slip_warn_factor):
                self.get_logger().warn(
                    f'control timer slip detected dt={dt_s:.3f}s '
                    f'expected={self.expected_period_s:.3f}s'
                )
        self.last_timer_time = now

        if self.last_target is None:
            self.valid_prev_tick = False
            self.update_mode('NO_TARGET')
            self.maybe_warn_invalid_target('no_target_msg', None)
            self.publish_zero()
            return

        t = self.last_target

        invalid_reason = self.target_invalid_reason(t)
        if invalid_reason is not None:
            self.valid_prev_tick = False
            self.update_mode('TARGET_INVALID')
            self.maybe_warn_invalid_target(invalid_reason, t)
            self.publish_zero()
            return

        ambiguous = self.is_ambiguous(t)
        if ambiguous:
            self._ambiguity_count += 1
            should_log = (
                not self._ambiguity_prev
                or (
                    self.ambiguity_warn_every_n > 0
                    and (self._ambiguity_count % self.ambiguity_warn_every_n == 0)
                )
            )
            if should_log:
                self.get_logger().warn(
                    f'ambiguity_flag=true quality={t.quality:.3f} '
                    f'threshold={self.ambiguity_quality_threshold:.3f}'
                )
            self._ambiguity_prev = True
            if self.enable_ambiguity_hold:
                self.update_mode('AMBIGUITY_HOLD')
                self.publish_zero()
                return
        elif self._ambiguity_prev:
            self.get_logger().info('ambiguity_flag=false')
            self._ambiguity_prev = False

        if not self.valid_prev_tick and self.last_invalid_reason is not None:
            self.get_logger().info('target_reacquired=true')
            self.get_logger().info(f'target valid again after: {self.last_invalid_reason}')
        self.last_invalid_reason = None
        self.invalid_count = 0
        self.valid_prev_tick = True
        self.update_mode('TRACKING')

        (
            vx_cmd,
            vy_cmd,
            yaw_z_cmd,
            cx_norm,
            h_norm,
            ex,
            range_err,
        ) = compute_control_command(
            cx=float(t.cx),
            h=float(t.h),
            img_w=self.img_w,
            img_h=self.img_h,
            desired_h_norm=self.desired_h_norm,
            yaw_kp=self.yaw_kp,
            forward_kp=self.forward_kp,
            lateral_kp=self.lateral_kp,
            deadband_ex=self.deadband_ex,
            deadband_h=self.deadband_h,
            max_yaw_z=self.max_yaw_z,
            max_vx=self.max_vx,
            max_vy=self.max_vy,
            use_lateral=self.use_lateral,
            invert_yaw=self.invert_yaw,
            invert_forward=self.invert_forward,
            invert_lateral=self.invert_lateral,
        )

        self.prev_vx = self.slew(vx_cmd, self.prev_vx, self.max_delta_vx)
        self.prev_vy = self.slew(vy_cmd, self.prev_vy, self.max_delta_vy)
        self.prev_yaw_z = self.slew(yaw_z_cmd, self.prev_yaw_z, self.max_delta_yaw_z)
        self.maybe_warn_saturation(vx_cmd, vy_cmd, yaw_z_cmd)

        self.publish_pair(
            self.get_clock().now().to_msg(),
            self.prev_vx,
            self.prev_vy,
            self.prev_yaw_z,
        )

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
    except (KeyboardInterrupt, ExternalShutdownException):
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
