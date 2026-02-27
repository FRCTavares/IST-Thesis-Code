import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import zmq

from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from thesis_msgs.msg import Timing


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


class InferenceClientNode(Node):
    def __init__(self):
        super().__init__("inference_client_node")

        # Params
        self.declare_parameter("addr", "tcp://127.0.0.1:5555")
        self.declare_parameter("topic", "dets")
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("label", "person")
        self.declare_parameter("min_score", 0.35)
        self.declare_parameter("conflate", True)
        self.declare_parameter("print_every", 60)

        # Logging-only throttle for idle/EOS periods
        self.declare_parameter("timeout_log_every", 10)

        self.addr = self.get_parameter("addr").value
        topic_str = self.get_parameter("topic").value
        self.topic_prefix = topic_str.encode("utf-8") + b" "  # IMPORTANT: space
        self.img_w = int(self.get_parameter("img_w").value)
        self.img_h = int(self.get_parameter("img_h").value)
        self.label = self.get_parameter("label").value
        self.min_score = float(self.get_parameter("min_score").value)
        self.conflate = bool(self.get_parameter("conflate").value)
        self.print_every = int(self.get_parameter("print_every").value)
        self.timeout_log_every = int(self.get_parameter("timeout_log_every").value)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.pub_dets = self.create_publisher(Detection2DArray, "/detections", qos)
        self.pub_timing = self.create_publisher(Timing, "/timing", qos)

        # ZMQ SUB (single-frame topic+space prefix messages)
        ctx = zmq.Context.instance()
        self.sub = ctx.socket(zmq.SUB)
        self.sub.setsockopt(zmq.SUBSCRIBE, self.topic_prefix)
        self.sub.setsockopt(zmq.RCVHWM, 5)
        self.sub.setsockopt(zmq.RCVTIMEO, 1000)
        if self.conflate:
            self.sub.setsockopt(zmq.CONFLATE, 1)
        self.sub.connect(self.addr)

        self.last_t_pub_ns = None
        self.n = 0

        # Timeout throttling state (logging-only)
        self.timeout_count = 0

        # Timer loop
        self.timer = self.create_timer(0.001, self.step)

        self.get_logger().info(
            f"SUB {self.addr} prefix={self.topic_prefix!r} W,H={self.img_w},{self.img_h} conflate={self.conflate}"
        )

    def step(self):
        t_loop0 = time.perf_counter_ns()

        # recv
        t_recv0 = time.perf_counter_ns()
        try:
            frame = self.sub.recv()  # bytes: b"dets " + b"{json}"
        except zmq.error.Again:
            self.timeout_count += 1

            # If stream has been dead for a while, drop pub_dt continuity so pub_dt_ms does not jump on restart.
            if self.timeout_count >= 3:
                self.last_t_pub_ns = None

            every = self.timeout_log_every if self.timeout_log_every > 0 else 10
            if (self.timeout_count % every) == 1:
                self.get_logger().warning(
                    f"recv timeout, no messages (count={self.timeout_count})"
                )
            return

        t_recv1 = time.perf_counter_ns()

        # Reset timeout counter on first successful recv after timeouts
        if self.timeout_count:
            self.timeout_count = 0

        t_rx_ns = time.time_ns()

        if not frame.startswith(self.topic_prefix):
            return

        payload = frame[len(self.topic_prefix):]

        # json
        t_json0 = time.perf_counter_ns()
        try:
            msg = json.loads(payload.decode("utf-8"))
        except Exception:
            return
        t_json1 = time.perf_counter_ns()

        # extract timing fields
        seq = int(msg.get("seq", 0) or 0)
        frame_id = int(msg.get("frame_id", 0) or 0)
        pts_ns = int(msg.get("pts_ns", 0) or 0)
        t_pub_ns = int(msg.get("t_pub", 0) or 0)

        pub_dt_ms = 0.0
        if t_pub_ns and self.last_t_pub_ns:
            pub_dt_ms = (t_pub_ns - self.last_t_pub_ns) / 1e6
        if t_pub_ns:
            self.last_t_pub_ns = t_pub_ns

        lat_ms = 0.0
        if t_pub_ns:
            lat_ms = (t_rx_ns - t_pub_ns) / 1e6

        recv_ms = (t_recv1 - t_recv0) / 1e6
        json_ms = (t_json1 - t_json0) / 1e6

        # build detections
        det_arr = Detection2DArray()
        det_arr.header.stamp = self.get_clock().now().to_msg()
        det_arr.header.frame_id = f"frame_{frame_id}"

        dets = msg.get("dets", [])
        for d in dets:
            if self.label and d.get("label") != self.label:
                continue
            score = float(d.get("score", 0.0))
            if score < self.min_score:
                continue

            # normalised top-left xywh
            x = clamp01(float(d.get("x", 0.0)))
            y = clamp01(float(d.get("y", 0.0)))
            w = clamp01(float(d.get("w", 0.0)))
            h = clamp01(float(d.get("h", 0.0)))

            # convert to vision_msgs bbox (centre + size in pixels)
            cx_px = (x + 0.5 * w) * self.img_w
            cy_px = (y + 0.5 * h) * self.img_h
            w_px = w * self.img_w
            h_px = h * self.img_h

            det = Detection2D()
            det.bbox.center.position.x = float(cx_px)
            det.bbox.center.position.y = float(cy_px)
            det.bbox.size_x = float(w_px)
            det.bbox.size_y = float(h_px)

            hyp = ObjectHypothesisWithPose()
            hyp.hypothesis.class_id = "person"
            hyp.hypothesis.score = float(score)
            det.results.append(hyp)

            det_arr.detections.append(det)

        # publish timing
        t_msg = Timing()
        t_msg.seq = seq
        t_msg.frame_id = frame_id
        t_msg.pts_ns = pts_ns
        t_msg.t_pub_ns = t_pub_ns
        t_msg.pub_dt_ms = float(pub_dt_ms)
        t_msg.lat_ms = float(lat_ms)
        t_msg.recv_ms = float(recv_ms)
        t_msg.json_ms = float(json_ms)
        t_msg.track_ms = 0.0
        # loop time filled after compute
        t_loop1 = time.perf_counter_ns()
        t_msg.loop_ms = float((t_loop1 - t_loop0) / 1e6)

        self.pub_dets.publish(det_arr)
        self.pub_timing.publish(t_msg)

        self.n += 1
        if self.print_every > 0 and (self.n % self.print_every == 0):
            self.get_logger().info(
                f"n={self.n} dets={len(det_arr.detections)} lat_ms={lat_ms:.2f} pub_dt_ms={pub_dt_ms:.2f} loop_ms={t_msg.loop_ms:.2f}"
            )


def main(args=None):
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init(args=args)
    node = None
    executor = SingleThreadedExecutor()

    try:
        node = InferenceClientNode()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if node is not None:
                executor.remove_node(node)
                node.destroy_node()
        except Exception:
            pass

        # Only shutdown if context still ok
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()