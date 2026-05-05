#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from std_msgs.msg import String
from thesis_msgs.msg import TargetState


def target_summary(msg: TargetState) -> str:
    return (
        f"id={int(msg.id):<3} "
        f"cx={float(msg.cx):7.2f} cy={float(msg.cy):7.2f} "
        f"w={float(msg.w):7.2f} h={float(msg.h):7.2f} "
        f"score={float(msg.score):.3f} q={float(msg.quality):.3f}"
    )


def centre_error(a: TargetState | None, b: TargetState | None) -> float | None:
    if a is None or b is None:
        return None
    if int(a.id) == 0 or int(b.id) == 0:
        return None
    dx = float(a.cx) - float(b.cx)
    dy = float(a.cy) - float(b.cy)
    return math.sqrt(dx * dx + dy * dy)


class TimVsTargetWatcher(Node):
    def __init__(self) -> None:
        super().__init__("tim_vs_target_watcher")

        self.raw: TargetState | None = None
        self.tim: TargetState | None = None
        self.status: dict = {}
        self.last_print = 0.0

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.create_subscription(TargetState, "/target", self.on_raw, qos)
        self.create_subscription(TargetState, "/target_memory", self.on_tim, qos)
        self.create_subscription(String, "/target_memory/status", self.on_status, qos)

        self.timer = self.create_timer(0.5, self.print_row)

    def on_raw(self, msg: TargetState) -> None:
        self.raw = msg

    def on_tim(self, msg: TargetState) -> None:
        self.tim = msg

    def on_status(self, msg: String) -> None:
        try:
            self.status = json.loads(msg.data)
        except json.JSONDecodeError:
            self.status = {}

    def print_row(self) -> None:
        state = self.status.get("state", "?")
        mode = self.status.get("control_mode", "?")
        reason = self.status.get("reason", "?")
        tim_lat = self.status.get("lat_ms", None)
        err = centre_error(self.raw, self.tim)

        print()
        print(f"TIM state={state} mode={mode} reason={reason} lat_ms={tim_lat}")
        print(f"RAW /target       : {target_summary(self.raw) if self.raw else 'none'}")
        print(f"TIM /target_memory: {target_summary(self.tim) if self.tim else 'none'}")
        print(f"centre_delta_px={err if err is not None else 'n/a'}")


def main() -> None:
    rclpy.init()
    node = TimVsTargetWatcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
