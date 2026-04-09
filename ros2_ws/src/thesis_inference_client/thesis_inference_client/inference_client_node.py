#!/usr/bin/env python3

from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from typing import Tuple

import cv2
import numpy as np
import rclpy
import zmq
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from thesis_msgs.msg import Timing


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def stamp_to_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def now_ns() -> int:
    """Monotonic nanoseconds for stage timing."""
    return time.monotonic_ns()


def _ms(dt_ns: int) -> float:
    return float(dt_ns) / 1e6


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


class InferenceClientNode(Node):
    def __init__(self):
        super().__init__("inference_client_node")

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("addr", "tcp://127.0.0.1:5556")
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("label", "person")
        self.declare_parameter("min_score", 0.35)
        self.declare_parameter("queue_size", 2)
        self.declare_parameter("request_timeout_ms", 200)
        self.declare_parameter("request_retries", 2)
        self.declare_parameter("send_hwm", 1)
        self.declare_parameter("recv_hwm", 1)
        self.declare_parameter("print_every", 240)
        self.declare_parameter("timeout_log_every", 20)
        self.declare_parameter("publish_timing", True)
        self.declare_parameter("num_workers", 2)
        self.declare_parameter("image_reliability", "best_effort")
        self.declare_parameter("image_qos_depth", 2)

        self.image_topic = self.get_parameter("image_topic").value
        self.addr = self.get_parameter("addr").value
        self.img_w = int(self.get_parameter("img_w").value)
        self.img_h = int(self.get_parameter("img_h").value)
        self.label = self.get_parameter("label").value
        self.min_score = float(self.get_parameter("min_score").value)
        self.queue_size = max(1, int(self.get_parameter("queue_size").value))
        self.request_timeout_ms = int(self.get_parameter("request_timeout_ms").value)
        self.request_retries = max(0, int(self.get_parameter("request_retries").value))
        self.send_hwm = int(self.get_parameter("send_hwm").value)
        self.recv_hwm = int(self.get_parameter("recv_hwm").value)
        self.print_every = int(self.get_parameter("print_every").value)
        self.timeout_log_every = int(self.get_parameter("timeout_log_every").value)
        self.publish_timing = bool(self.get_parameter("publish_timing").value)
        self.num_workers = max(1, int(self.get_parameter("num_workers").value))
        self.image_reliability = str(self.get_parameter("image_reliability").value).strip().lower()
        self.image_qos_depth = max(1, int(self.get_parameter("image_qos_depth").value))

        self.resize_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)
        self._logged_encoding: str | None = None
        self._logged_own_data = False
        self._meta_base = {
            "width": self.img_w,
            "height": self.img_h,
            "channels": 3,
        }

        qos_pub = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.pub_dets = self.create_publisher(Detection2DArray, "/detections", qos_pub)
        self.pub_timing = self.create_publisher(Timing, "/timing", qos_pub)

        image_sub_qos = self._build_image_sub_qos()
        self.sub_image = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            image_sub_qos,
        )

        self.ctx = zmq.Context.instance()

        self.queue: queue.Queue[Tuple[Image, int, int]] = queue.Queue(maxsize=self.queue_size)
        self.state_lock = threading.Lock()
        self.publish_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.workers: list[threading.Thread] = []

        self.last_t_frame_sent_ns = None
        self.seq_counter = 0
        self.frame_counter = 0

        self.frames_received = 0
        self.frames_sent = 0
        self.frames_dropped = 0
        self.zmq_timeouts = 0
        self.last_roundtrip_ms = 0.0
        self.empty_polls = 0
        self.pub_dt_hist_ms = deque(maxlen=600)

        for worker_id in range(self.num_workers):
            t = threading.Thread(target=self.worker_loop, args=(worker_id,), daemon=True)
            self.workers.append(t)
            t.start()

        self.get_logger().info(
            f"image_topic={self.image_topic} addr={self.addr} "
            f"infer_size={self.img_w}x{self.img_h} queue_size={self.queue_size} "
            f"publish_timing={self.publish_timing} num_workers={self.num_workers} "
            f"image_reliability={self.image_reliability} image_qos_depth={self.image_qos_depth}"
        )

    def _build_image_sub_qos(self) -> QoSProfile:
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=self.image_qos_depth,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        if self.image_reliability == "reliable":
            qos.reliability = ReliabilityPolicy.RELIABLE
        elif self.image_reliability not in ("best_effort", "besteffort"):
            self.get_logger().warning(
                f"invalid image_reliability='{self.image_reliability}', using best_effort"
            )
        return qos

    def _make_worker_socket(self) -> zmq.Socket:
        sock = self.ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.LINGER, 0)
        sock.setsockopt(zmq.SNDHWM, self.send_hwm)
        sock.setsockopt(zmq.RCVHWM, self.recv_hwm)
        sock.setsockopt(zmq.SNDTIMEO, self.request_timeout_ms)
        sock.setsockopt(zmq.RCVTIMEO, self.request_timeout_ms)
        sock.connect(self.addr)
        return sock

    def image_callback(self, msg: Image) -> None:
        t_cam_msg_seen_ns = now_ns()
        src_stamp_ns = stamp_to_ns(msg.header.stamp)
        frame_ctx = (msg, t_cam_msg_seen_ns, src_stamp_ns)

        dropped_count = 0
        enqueued = False

        # Keep freshest-frame behavior: if full, evict one oldest frame and retry once.
        for _ in range(2):
            try:
                self.queue.put_nowait(frame_ctx)
                enqueued = True
                break
            except queue.Full:
                try:
                    self.queue.get_nowait()
                    dropped_count += 1
                except queue.Empty:
                    pass

        if not enqueued:
            # If contention still keeps the queue full, drop this incoming frame.
            dropped_count += 1

        with self.state_lock:
            self.frames_received += 1
            self.frames_dropped += dropped_count

    def worker_loop(self, worker_id: int) -> None:
        req = self._make_worker_socket()
        # Each worker needs its own resize buffer to avoid cross-thread races.
        worker_resize_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)
        worker_rgb_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)

        while rclpy.ok() and not self.stop_event.is_set():
            try:
                frame_ctx = self.queue.get(timeout=0.02)
            except queue.Empty:
                with self.state_lock:
                    self.empty_polls += 1
                continue

            image_msg, t_cam_msg_seen_ns, src_stamp_ns = frame_ctx

            t_loop0 = now_ns()
            with self.state_lock:
                seq = self.seq_counter
                self.seq_counter += 1
                frame_id = self.frame_counter
                self.frame_counter += 1

            t_pre_start_ns = now_ns()
            t_ros_to_np_start_ns = t_pre_start_ns

            image_height = int(image_msg.height)
            image_width = int(image_msg.width)
            image_encoding = str(image_msg.encoding).lower()
            image_step = int(image_msg.step)

            if image_encoding not in ("rgb8", "bgr8"):
                self.get_logger().error(
                    f"unsupported encoding '{image_msg.encoding}' in inference_client; "
                    f"expected rgb8 or bgr8. Fix camera node encoding and restart."
                )
                continue

            expected_step = image_width * 3
            if image_step != expected_step:
                self.get_logger().error(
                    f"unsupported image step={image_step} (expected {expected_step} for packed 8UC3). "
                    f"Fix camera node to publish tightly packed RGB/BGR images."
                )
                continue

            expected_bytes = image_height * image_step
            if len(image_msg.data) != expected_bytes:
                self.get_logger().warning(
                    f"image size mismatch: got={len(image_msg.data)} expected={expected_bytes}; dropping frame"
                )
                continue

            try:
                img = np.frombuffer(image_msg.data, dtype=np.uint8)
                img = img.reshape(image_height, image_width, 3)
            except Exception as exc:
                self.get_logger().warning(f"ROS image to numpy conversion failed: {exc}")
                continue
            t_ros_to_np_end_ns = now_ns()

            if image_encoding != self._logged_encoding:
                self._logged_encoding = image_encoding
                self.get_logger().info(f"inference input encoding={image_encoding}")

            if not self._logged_own_data:
                self._logged_own_data = True
                self.get_logger().info(f"numpy_view_owndata={img.flags['OWNDATA']}")

            t_resize_start_ns = now_ns()
            if image_width == self.img_w and image_height == self.img_h:
                infer_img = img
                t_resize_end_ns = t_resize_start_ns
            else:
                try:
                    cv2.resize(
                        img,
                        (self.img_w, self.img_h),
                        dst=worker_resize_buf,
                        interpolation=cv2.INTER_LINEAR,
                    )
                except Exception as exc:
                    self.get_logger().warning(f"resize failed: {exc}")
                    continue
                infer_img = worker_resize_buf
                t_resize_end_ns = now_ns()

            t_color_start_ns = now_ns()
            if image_encoding == "bgr8":
                cv2.cvtColor(infer_img, cv2.COLOR_BGR2RGB, dst=worker_rgb_buf)
                infer_img = worker_rgb_buf
                t_color_end_ns = now_ns()
            else:
                t_color_end_ns = t_color_start_ns

            t_pack_start_ns = now_ns()
            frame_payload = memoryview(infer_img)
            t_pack_end_ns = now_ns()
            t_pre_end_ns = now_ns()

            metadata = self._meta_base.copy()
            metadata["seq"] = seq
            metadata["frame_id"] = frame_id
            metadata["src_stamp_ns"] = src_stamp_ns

            t_frame_sent_ns = now_ns()
            with self.state_lock:
                pub_dt_ms = 0.0
                if self.last_t_frame_sent_ns is not None:
                    pub_dt_ms = (t_frame_sent_ns - self.last_t_frame_sent_ns) / 1e6
                    self.pub_dt_hist_ms.append(pub_dt_ms)
                self.last_t_frame_sent_ns = t_frame_sent_ns

            response = None
            attempt = 0
            while attempt <= self.request_retries:
                try:
                    t_zmq_send_start_ns = now_ns()
                    req.send_json(metadata, flags=zmq.SNDMORE)
                    req.send(frame_payload, flags=0, copy=False)
                    t_zmq_send_end_ns = now_ns()

                    t_zmq_recv_start_ns = now_ns()
                    raw_reply = req.recv()
                    t_zmq_recv_end_ns = now_ns()

                    t_decode_start_ns = now_ns()
                    if isinstance(raw_reply, bytes):
                        response = json.loads(raw_reply.decode("utf-8"))
                    else:
                        response = raw_reply
                    t_decode_end_ns = now_ns()
                    break

                except zmq.error.Again:
                    with self.state_lock:
                        self.zmq_timeouts += 1
                        timeout_count = self.zmq_timeouts
                    every = self.timeout_log_every if self.timeout_log_every > 0 else 10
                    if (timeout_count % every) == 1:
                        self.get_logger().warning(
                            f"REQ timeout waiting for inference response "
                            f"(count={timeout_count}, worker={worker_id}, attempt={attempt + 1}/{self.request_retries + 1})"
                        )
                    try:
                        req.close(0)
                    except Exception:
                        pass
                    req = self._make_worker_socket()
                    attempt += 1

                except Exception as exc:
                    self.get_logger().warning(
                        f"ZMQ request failed (worker={worker_id}, attempt={attempt + 1}/{self.request_retries + 1}): {exc}"
                    )
                    try:
                        req.close(0)
                    except Exception:
                        pass
                    req = self._make_worker_socket()
                    attempt += 1

            if response is None:
                continue

            roundtrip_ms = _ms(t_zmq_recv_end_ns - t_zmq_send_start_ns)
            with self.state_lock:
                self.last_roundtrip_ms = roundtrip_ms

            det_arr = Detection2DArray()
            det_arr.header.stamp = image_msg.header.stamp
            det_arr.header.frame_id = f"frame_{frame_id}"

            dets = response.get("detections", response.get("dets", []))
            for d in dets:
                score = float(d.get("score", 0.0))
                if score < self.min_score:
                    continue

                det_label = str(d.get("label", "")).strip()

                label_ok = True
                if self.label:
                    if "label" in d:
                        label_ok = det_label.lower() == str(self.label).strip().lower()
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
                if det_label:
                    hyp.hypothesis.class_id = det_label
                elif self.label:
                    hyp.hypothesis.class_id = str(self.label)
                else:
                    hyp.hypothesis.class_id = "person"
                hyp.hypothesis.score = float(score)
                det.results.append(hyp)

                det_arr.detections.append(det)

            timing_reply = response.get("timing", {}) if isinstance(response, dict) else {}

            t_req_recv_ns = _safe_int(timing_reply.get("t_req_recv_ns"), 0)
            t_frame_unpack_start_ns = _safe_int(timing_reply.get("t_frame_unpack_start_ns"), 0)
            t_frame_unpack_end_ns = _safe_int(timing_reply.get("t_frame_unpack_end_ns"), 0)
            t_infer_start_ns = _safe_int(timing_reply.get("t_infer_start_ns"), 0)
            t_infer_end_reply_ns = _safe_int(timing_reply.get("t_infer_end_ns"), 0)
            t_post_start_ns = _safe_int(timing_reply.get("t_post_start_ns"), 0)
            t_post_end_ns = _safe_int(timing_reply.get("t_post_end_ns"), 0)
            t_reply_send_ns = _safe_int(timing_reply.get("t_reply_send_ns"), 0)

            t_det_pub_start_ns = now_ns()

            t_msg = Timing()
            t_msg.seq = seq
            t_msg.frame_id = frame_id
            t_msg.src_stamp_ns = src_stamp_ns
            t_msg.t_cam_msg_seen_ns = t_cam_msg_seen_ns
            t_msg.image_width = int(image_msg.width)
            t_msg.image_height = int(image_msg.height)
            t_msg.image_encoding = str(image_msg.encoding)

            t_msg.t_pre_start_ns = t_pre_start_ns
            t_msg.t_pre_end_ns = t_pre_end_ns
            t_msg.t_zmq_send_start_ns = t_zmq_send_start_ns
            t_msg.t_zmq_send_end_ns = t_zmq_send_end_ns
            t_msg.t_zmq_recv_start_ns = t_zmq_recv_start_ns
            t_msg.t_zmq_recv_end_ns = t_zmq_recv_end_ns
            t_msg.t_decode_start_ns = t_decode_start_ns
            t_msg.t_decode_end_ns = t_decode_end_ns
            t_msg.t_det_pub_start_ns = t_det_pub_start_ns

            t_msg.t_req_recv_ns = t_req_recv_ns
            t_msg.t_frame_unpack_start_ns = t_frame_unpack_start_ns
            t_msg.t_frame_unpack_end_ns = t_frame_unpack_end_ns
            t_msg.t_infer_start_ns = t_infer_start_ns
            t_msg.t_infer_end_ns = t_infer_end_reply_ns
            t_msg.t_post_start_ns = t_post_start_ns
            t_msg.t_post_end_ns = t_post_end_ns
            t_msg.t_reply_send_ns = t_reply_send_ns

            t_msg.ros_wait_ms = _ms(t_pre_start_ns - t_cam_msg_seen_ns)
            t_msg.pre_ms = _ms(t_pre_end_ns - t_pre_start_ns)
            t_msg.ros_to_np_ms = _ms(t_ros_to_np_end_ns - t_ros_to_np_start_ns)
            t_msg.resize_ms = _ms(t_resize_end_ns - t_resize_start_ns)
            t_msg.color_ms = _ms(t_color_end_ns - t_color_start_ns)
            t_msg.pack_ms = _ms(t_pack_end_ns - t_pack_start_ns)
            t_msg.zmq_req_send_ms = _ms(t_zmq_send_end_ns - t_zmq_send_start_ns)
            t_msg.zmq_wait_reply_ms = _ms(t_zmq_recv_end_ns - t_zmq_recv_start_ns)
            t_msg.zmq_roundtrip_ms = _ms(t_zmq_recv_end_ns - t_zmq_send_start_ns)
            t_msg.decode_ms = _ms(t_decode_end_ns - t_decode_start_ns)

            if t_frame_unpack_start_ns > 0 and t_frame_unpack_end_ns >= t_frame_unpack_start_ns:
                t_msg.container_unpack_ms = _ms(t_frame_unpack_end_ns - t_frame_unpack_start_ns)
            if t_infer_start_ns > 0 and t_req_recv_ns > 0 and t_infer_start_ns >= t_req_recv_ns:
                t_msg.container_queue_ms = _ms(t_infer_start_ns - t_req_recv_ns)
            if t_infer_end_reply_ns > 0 and t_infer_start_ns > 0 and t_infer_end_reply_ns >= t_infer_start_ns:
                t_msg.infer_ms = _ms(t_infer_end_reply_ns - t_infer_start_ns)
            if t_post_end_ns > 0 and t_post_start_ns > 0 and t_post_end_ns >= t_post_start_ns:
                t_msg.post_ms = _ms(t_post_end_ns - t_post_start_ns)

            t_msg.pts_ns = src_stamp_ns
            t_msg.t_pub_ns = t_frame_sent_ns
            t_msg.pub_dt_ms = float(pub_dt_ms)
            t_msg.track_ms = 0.0

            with self.publish_lock:
                self.pub_dets.publish(det_arr)
                t_det_pub_end_ns = now_ns()
                t_msg.t_det_pub_end_ns = t_det_pub_end_ns
                t_msg.det_pub_ms = _ms(t_det_pub_end_ns - t_det_pub_start_ns)
                t_msg.e2e_det_ms = _ms(t_det_pub_end_ns - t_cam_msg_seen_ns)

                t_loop1 = now_ns()
                loop_ms = _ms(t_loop1 - t_loop0)

                if self.publish_timing:
                    self.pub_timing.publish(t_msg)

            with self.state_lock:
                self.frames_sent += 1
                sent_now = self.frames_sent
                recv_now = self.frames_received
                dropped_now = self.frames_dropped
                empty_polls_now = self.empty_polls
                pub_dt_hist = list(self.pub_dt_hist_ms)

            if pub_dt_hist:
                pub_dt_p50 = float(np.percentile(pub_dt_hist, 50))
                pub_dt_p95 = float(np.percentile(pub_dt_hist, 95))
                pub_dt_min = float(min(pub_dt_hist))
                pub_dt_max = float(max(pub_dt_hist))
            else:
                pub_dt_p50 = 0.0
                pub_dt_p95 = 0.0
                pub_dt_min = 0.0
                pub_dt_max = 0.0

            if self.print_every > 0 and (sent_now % self.print_every == 0):
                self.get_logger().info(
                    f"sent={sent_now} recv={recv_now} "
                    f"drop={dropped_now} dets={len(det_arr.detections)} "
                    f"e2e_det_ms={t_msg.e2e_det_ms:.2f} pre_ms={t_msg.pre_ms:.2f} "
                    f"ros_to_np_ms={t_msg.ros_to_np_ms:.2f} "
                    f"resize_ms={t_msg.resize_ms:.2f} "
                    f"color_ms={t_msg.color_ms:.2f} pack_ms={t_msg.pack_ms:.2f} "
                    f"rt_ms={roundtrip_ms:.2f} "
                    f"loop_ms={loop_ms:.2f} "
                    f"pub_dt_ms={pub_dt_ms:.2f} "
                    f"pub_dt_p50_ms={pub_dt_p50:.2f} "
                    f"pub_dt_p95_ms={pub_dt_p95:.2f} "
                    f"pub_dt_min_ms={pub_dt_min:.2f} "
                    f"pub_dt_max_ms={pub_dt_max:.2f} "
                    f"empty_polls={empty_polls_now}"
                )

        try:
            req.close(0)
        except Exception:
            pass

    def destroy_node(self):
        self.stop_event.set()

        for t in self.workers:
            if t.is_alive():
                t.join(timeout=2.0)

        return super().destroy_node()


def main(args=None):
    from rclpy.executors import MultiThreadedExecutor

    rclpy.init(args=args)
    node = None
    executor = MultiThreadedExecutor(num_threads=4)

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