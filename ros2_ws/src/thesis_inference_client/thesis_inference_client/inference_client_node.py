#!/usr/bin/env python3

from __future__ import annotations

import json
import threading
import time
from collections import deque

import cv2
import rclpy
import zmq
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from thesis_msgs.msg import Timing


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def stamp_to_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


class InferenceClientNode(Node):
    def __init__(self):
        super().__init__("inference_client_node")

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("addr", "tcp://127.0.0.1:5556")
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("label", "person")
        self.declare_parameter("min_score", 0.35)
        self.declare_parameter("queue_size", 1)
        self.declare_parameter("request_timeout_ms", 500)
        self.declare_parameter("send_hwm", 1)
        self.declare_parameter("recv_hwm", 1)
        self.declare_parameter("print_every", 60)
        self.declare_parameter("timeout_log_every", 10)

        self.image_topic = self.get_parameter("image_topic").value
        self.addr = self.get_parameter("addr").value
        self.img_w = int(self.get_parameter("img_w").value)
        self.img_h = int(self.get_parameter("img_h").value)
        self.label = self.get_parameter("label").value
        self.min_score = float(self.get_parameter("min_score").value)
        self.queue_size = max(1, int(self.get_parameter("queue_size").value))
        self.request_timeout_ms = int(self.get_parameter("request_timeout_ms").value)
        self.send_hwm = int(self.get_parameter("send_hwm").value)
        self.recv_hwm = int(self.get_parameter("recv_hwm").value)
        self.print_every = int(self.get_parameter("print_every").value)
        self.timeout_log_every = int(self.get_parameter("timeout_log_every").value)

        qos_pub = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.pub_dets = self.create_publisher(Detection2DArray, "/detections", qos_pub)
        self.pub_timing = self.create_publisher(Timing, "/timing", qos_pub)

        self.sub_image = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            qos_profile_sensor_data,
        )

        self.bridge = CvBridge()

        self.ctx = zmq.Context.instance()
        self.req = None
        self._make_req_socket()

        self.queue = deque(maxlen=self.queue_size)
        self.queue_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self.worker_loop, daemon=True)

        self.last_t_frame_sent_ns = None
        self.seq_counter = 0
        self.frame_counter = 0

        self.frames_received = 0
        self.frames_sent = 0
        self.frames_dropped = 0
        self.zmq_timeouts = 0
        self.last_roundtrip_ms = 0.0

        self.worker.start()

        self.get_logger().info(
            f"image_topic={self.image_topic} addr={self.addr} "
            f"infer_size={self.img_w}x{self.img_h} queue_size={self.queue_size}"
        )

    def _make_req_socket(self) -> None:
        if self.req is not None:
            try:
                self.req.close(0)
            except Exception:
                pass

        self.req = self.ctx.socket(zmq.REQ)
        self.req.setsockopt(zmq.LINGER, 0)
        self.req.setsockopt(zmq.SNDHWM, self.send_hwm)
        self.req.setsockopt(zmq.RCVHWM, self.recv_hwm)
        self.req.setsockopt(zmq.SNDTIMEO, self.request_timeout_ms)
        self.req.setsockopt(zmq.RCVTIMEO, self.request_timeout_ms)
        self.req.connect(self.addr)

    def image_callback(self, msg: Image) -> None:
        with self.queue_lock:
            if len(self.queue) == self.queue.maxlen:
                self.queue.popleft()
                self.frames_dropped += 1
            self.queue.append(msg)
            self.frames_received += 1

    def pop_latest_frame(self) -> Image | None:
        with self.queue_lock:
            if not self.queue:
                return None
            latest = self.queue.pop()
            dropped_here = len(self.queue)
            if dropped_here > 0:
                self.frames_dropped += dropped_here
            self.queue.clear()
            return latest

    def worker_loop(self) -> None:
        while rclpy.ok() and not self.stop_event.is_set():
            image_msg = self.pop_latest_frame()
            if image_msg is None:
                time.sleep(0.001)
                continue

            t_loop0 = time.perf_counter_ns()

            seq = self.seq_counter
            self.seq_counter += 1

            frame_id = self.frame_counter
            self.frame_counter += 1

            t_capture_ns = stamp_to_ns(image_msg.header.stamp)

            try:
                cv_bgr = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
            except Exception as exc:
                self.get_logger().warning(f"cv_bridge conversion failed: {exc}")
                continue

            try:
                resized_bgr = cv2.resize(
                    cv_bgr,
                    (self.img_w, self.img_h),
                    interpolation=cv2.INTER_LINEAR,
                )
                resized_rgb = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
            except Exception as exc:
                self.get_logger().warning(f"frame preprocessing failed: {exc}")
                continue

            frame_bytes = resized_rgb.tobytes()

            metadata = {
                "seq": seq,
                "frame_id": frame_id,
                "timestamp_ns": t_capture_ns,
                "width": self.img_w,
                "height": self.img_h,
                "channels": 3,
                "dtype": "uint8",
                "encoding": "rgb8",
            }

            t_frame_sent_ns = time.time_ns()

            pub_dt_ms = 0.0
            if self.last_t_frame_sent_ns is not None:
                pub_dt_ms = (t_frame_sent_ns - self.last_t_frame_sent_ns) / 1e6
            self.last_t_frame_sent_ns = t_frame_sent_ns

            t_json0 = time.perf_counter_ns()
            response = None
            try:
                self.req.send_json(metadata, flags=zmq.SNDMORE)
                self.req.send(frame_bytes, flags=0, copy=False)
                raw_reply = self.req.recv()

                if isinstance(raw_reply, bytes):
                    response = json.loads(raw_reply.decode("utf-8"))
                else:
                    response = raw_reply

            except zmq.error.Again:
                self.zmq_timeouts += 1
                every = self.timeout_log_every if self.timeout_log_every > 0 else 10
                if (self.zmq_timeouts % every) == 1:
                    self.get_logger().warning(
                        f"REQ timeout waiting for inference response "
                        f"(count={self.zmq_timeouts})"
                    )
                self._make_req_socket()
                continue
            except Exception as exc:
                self.get_logger().warning(f"ZMQ request failed: {exc}")
                self._make_req_socket()
                continue
            t_json1 = time.perf_counter_ns()

            t_infer_end_ns = time.time_ns()
            roundtrip_ms = (t_infer_end_ns - t_frame_sent_ns) / 1e6
            self.last_roundtrip_ms = roundtrip_ms

            det_arr = Detection2DArray()
            det_arr.header.stamp = image_msg.header.stamp
            det_arr.header.frame_id = (
                image_msg.header.frame_id if image_msg.header.frame_id else f"frame_{frame_id}"
            )

            dets = response.get("detections", response.get("dets", []))
            for d in dets:
                score = float(d.get("score", 0.0))
                if score < self.min_score:
                    continue

                label_ok = True
                if self.label:
                    if "label" in d:
                        label_ok = d.get("label") == self.label
                    elif "class_id" in d:
                        label_ok = int(d.get("class_id", -1)) == 0
                if not label_ok:
                    continue

                if all(k in d for k in ("x", "y", "w", "h")):
                    x = clamp01(float(d.get("x", 0.0)))
                    y = clamp01(float(d.get("y", 0.0)))
                    w = clamp01(float(d.get("w", 0.0)))
                    h = clamp01(float(d.get("h", 0.0)))

                    cx_px = (x + 0.5 * w) * self.img_w
                    cy_px = (y + 0.5 * h) * self.img_h
                    w_px = w * self.img_w
                    h_px = h * self.img_h

                elif all(k in d for k in ("x1", "y1", "x2", "y2")):
                    x1 = float(d.get("x1", 0.0))
                    y1 = float(d.get("y1", 0.0))
                    x2 = float(d.get("x2", 0.0))
                    y2 = float(d.get("y2", 0.0))

                    w_px = max(0.0, x2 - x1)
                    h_px = max(0.0, y2 - y1)
                    cx_px = x1 + 0.5 * w_px
                    cy_px = y1 + 0.5 * h_px
                else:
                    continue

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

            t_msg = Timing()
            t_msg.seq = seq
            t_msg.frame_id = frame_id
            t_msg.pts_ns = t_capture_ns
            t_msg.t_pub_ns = t_frame_sent_ns
            t_msg.pub_dt_ms = float(pub_dt_ms)
            t_msg.lat_ms = float((t_infer_end_ns - t_capture_ns) / 1e6)
            t_msg.recv_ms = float(roundtrip_ms)
            t_msg.json_ms = float((t_json1 - t_json0) / 1e6)
            t_msg.track_ms = 0.0

            t_loop1 = time.perf_counter_ns()
            t_msg.loop_ms = float((t_loop1 - t_loop0) / 1e6)

            self.pub_dets.publish(det_arr)
            self.pub_timing.publish(t_msg)

            self.frames_sent += 1

            if self.print_every > 0 and (self.frames_sent % self.print_every == 0):
                self.get_logger().info(
                    f"sent={self.frames_sent} recv={self.frames_received} "
                    f"drop={self.frames_dropped} dets={len(det_arr.detections)} "
                    f"lat_ms={t_msg.lat_ms:.2f} rt_ms={roundtrip_ms:.2f} "
                    f"loop_ms={t_msg.loop_ms:.2f}"
                )

    def destroy_node(self):
        self.stop_event.set()

        if self.worker is not None and self.worker.is_alive():
            self.worker.join(timeout=2.0)

        if self.req is not None:
            try:
                self.req.close(0)
            except Exception:
                pass
            self.req = None

        return super().destroy_node()


def main(args=None):
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

        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()