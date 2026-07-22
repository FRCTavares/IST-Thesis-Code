#!/usr/bin/env python3
"""Integrated perception pipeline node.

This node connects camera frames to preprocessing, Hailo inference backends,
detection publication, and timing telemetry for the live thesis perception
stack.
"""

from __future__ import annotations

from collections import deque
import gc
import os
import threading
import time
from typing import Any

import numpy as np
from rcl_interfaces.msg import SetParametersResult
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image
from thesis_bringup.perception.inference_engines import (
    HailoDirectInferenceEngine,
    HailoGstInferenceEngine,
    StubInferenceEngine,
)
from thesis_bringup.perception.pipeline_types import (
    PreparedFrame,
    RawFrame,
)
from thesis_bringup.perception.pipeline_utils import (
    _ms,
    _normalize_label,
    _safe_int,
    clamp01,
    now_ns,
    stamp_to_ns,
)
from thesis_bringup.perception.preprocessing import preprocess_image_message
from thesis_msgs.msg import Timing
from vision_msgs.msg import (
    Detection2D,
    Detection2DArray,
    ObjectHypothesisWithPose,
)


class PerceptionPipelineNode(Node):
    """Single-process perception node with optional in-process Hailo backend."""

    def __init__(
        self,
        *,
        node_name: str = "perception_pipeline_node",
        create_image_subscription: bool = True,
    ) -> None:
        super().__init__(node_name)

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("img_w", 640)
        self.declare_parameter("img_h", 640)
        self.declare_parameter("label", "person")
        self.declare_parameter("min_score", 0.35)
        self.declare_parameter("publish_timing", True)
        self.declare_parameter("image_reliability", "best_effort")
        self.declare_parameter("image_qos_depth", 2)
        self.declare_parameter("inference_backend", "hailo_direct")
        self.declare_parameter("allow_stub_fallback", False)
        self.declare_parameter("infer_timeout_ms", 300)
        self.declare_parameter("timeout_log_every", 20)
        self.declare_parameter("log_every", 240)
        self.declare_parameter("disable_python_gc", False)
        self.declare_parameter("async_latest_frame", True)
        self.declare_parameter("async_max_inflight", 1)
        self.declare_parameter("frame_queue_size", 1)
        self.declare_parameter("num_workers", 2)

        thesis_root = os.getenv("THESIS_ROOT", "/home/francisco/Desktop/Thesis-Code")
        default_hef = f"{thesis_root}/models/hef/yolov6n.hef"
        self.declare_parameter("hailo_fps", 30)
        self.declare_parameter("hailo_hef_path", default_hef)
        self.declare_parameter(
            "hailo_post_so",
            "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so",
        )
        self.declare_parameter("hailo_post_function", "filter")
        self.declare_parameter("hailo_video_sink", "fakesink")
        self.declare_parameter("hailo_queue_max_buffers", 6)
        self.declare_parameter("hailo_use_videoconvert", True)

        self.image_topic = str(self.get_parameter("image_topic").value)
        self.img_w = int(self.get_parameter("img_w").value)
        self.img_h = int(self.get_parameter("img_h").value)
        self.label = str(self.get_parameter("label").value)
        self.min_score = float(self.get_parameter("min_score").value)
        self.publish_timing = bool(self.get_parameter("publish_timing").value)
        self.image_reliability = str(self.get_parameter("image_reliability").value).strip().lower()
        self.image_qos_depth = max(1, int(self.get_parameter("image_qos_depth").value))
        self.inference_backend = str(self.get_parameter("inference_backend").value).strip().lower()
        self.allow_stub_fallback = bool(self.get_parameter("allow_stub_fallback").value)
        self.infer_timeout_ms = max(1, int(self.get_parameter("infer_timeout_ms").value))
        self.timeout_log_every = max(1, int(self.get_parameter("timeout_log_every").value))
        self.log_every = max(0, int(self.get_parameter("log_every").value))
        self.disable_python_gc = bool(self.get_parameter("disable_python_gc").value)
        self.async_latest_frame_requested = bool(self.get_parameter("async_latest_frame").value)
        self.async_max_inflight_requested = max(1, int(self.get_parameter("async_max_inflight").value))
        self.frame_queue_size = max(1, int(self.get_parameter("frame_queue_size").value))
        self.num_workers = max(1, int(self.get_parameter("num_workers").value))
        # Old callback-thread inference path has been removed; queue+worker is mandatory.
        self.async_latest_frame = True
        if not self.async_latest_frame_requested:
            self.get_logger().warning(
                "legacy async_latest_frame=false path has been removed; "
                "forcing queue+worker mode"
            )
        # Single-owner engine submission model: only one caller may submit to appsrc/engine.
        self.async_max_inflight = 1
        if self.async_max_inflight_requested != 1:
            self.get_logger().warning(
                "single-owner backend path enforces async_max_inflight=1; "
                f"requested={self.async_max_inflight_requested}"
            )

        self._gc_was_enabled = gc.isenabled()
        self._gc_disabled_by_node = False
        if self.disable_python_gc and self._gc_was_enabled:
            gc.disable()
            self._gc_disabled_by_node = True
            self.get_logger().info("perception_pipeline_node disabled Python cyclic GC")

        self.hailo_fps = max(1, int(self.get_parameter("hailo_fps").value))
        self.hailo_hef_path = str(self.get_parameter("hailo_hef_path").value)
        self.hailo_post_so = str(self.get_parameter("hailo_post_so").value)
        self.hailo_post_function = str(self.get_parameter("hailo_post_function").value)
        self.hailo_video_sink = str(self.get_parameter("hailo_video_sink").value)
        self.hailo_queue_max_buffers = max(1, int(self.get_parameter("hailo_queue_max_buffers").value))
        self.hailo_use_videoconvert = bool(self.get_parameter("hailo_use_videoconvert").value)

        self.label_filter = _normalize_label(self.label)

        self._engine_lock = threading.RLock()
        self._engine_cv = threading.Condition(self._engine_lock)
        self._engine_active_calls = 0
        self._param_cb_handle = self.add_on_set_parameters_callback(self._on_set_parameters)

        # Legacy-like flow for single-owner engine: preprocess and infer in the same worker.
        # This avoids a second staging queue where frames can accumulate before inference starts.
        self.prepared_queue_size = 0
        self._logged_encoding: str | None = None
        self._logged_own_data = False
        self._preprocess_log_lock = threading.Lock()

        qos_pub = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.pub_dets = self.create_publisher(Detection2DArray, "/detections", qos_pub)
        self.pub_timing = self.create_publisher(Timing, "/timing", qos_pub)

        self.sub_image = None
        if create_image_subscription:
            image_sub_qos = self._build_image_sub_qos()
            self.sub_image = self.create_subscription(
                Image,
                self.image_topic,
                self.on_image,
                image_sub_qos,
            )

        self.engine = self._build_engine()

        self.seq_counter = 0
        self.frame_counter = 0
        self.frames_received = 0
        self.frames_processed = 0
        self.frames_timeouts = 0
        self.frames_enqueued = 0
        self.frames_overwritten = 0
        self.frames_prepared_enqueued = 0
        self.frames_prepared_overwritten = 0
        self.last_roundtrip_ms = 0.0
        self.last_det_pub_ns: int | None = None
        self.pub_dt_hist_ms: deque[float] = deque(maxlen=600)

        self._worker_cv = threading.Condition()
        self._queued_frames: deque[RawFrame] = deque()
        # Retained for compatibility with helper methods from the old staged path.
        self._prepared_cv = threading.Condition()
        self._prepared_frames: deque[PreparedFrame] = deque()
        self._preprocess_workers: list[threading.Thread] = []
        self._worker_stop = False

        if self.num_workers != 1:
            self.get_logger().warning(
                "single-owner backend path executes one inline worker; "
                f"requested num_workers={self.num_workers}"
            )

        self._infer_worker_thread: threading.Thread | None = None
        self._infer_worker_thread = threading.Thread(
            target=self._infer_worker_loop,
            name="perception_engine_owner",
            daemon=True,
        )
        self._infer_worker_thread.start()

        self.get_logger().info(
            f"image_topic={self.image_topic} "
            f"infer_size={self.img_w}x{self.img_h} "
            f"publish_timing={self.publish_timing} "
            f"inference_backend={self.active_backend} "
            f"infer_timeout_ms={self.infer_timeout_ms} "
            f"label={self.label} min_score={self.min_score:.2f} "
            f"image_reliability={self.image_reliability} "
            f"image_qos_depth={self.image_qos_depth} "
            f"disable_python_gc={self.disable_python_gc} "
            "ingress_mode=inline_worker_owner "
            f"frame_queue_size={self.frame_queue_size} "
            f"prepared_queue_size={self.prepared_queue_size} "
            f"num_workers={self.num_workers} "
            f"async_max_inflight_requested={self.async_max_inflight_requested} "
            f"async_max_inflight_effective={self.async_max_inflight} "
            f"hailo_use_videoconvert={self.hailo_use_videoconvert}"
        )

    def _wait_for_engine_idle_locked(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while self._engine_active_calls > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            self._engine_cv.wait(timeout=remaining)
        return True

    @staticmethod
    def _is_hailo_backend_name(backend_name: str) -> bool:
        return backend_name in (
            "hailo",
            "hailo_direct",
            "direct",
            "hailort",
            "hailo_gst",
            "gst",
        )

    @staticmethod
    def _backend_wants_direct(backend_name: str) -> bool:
        return backend_name in ("hailo", "hailo_direct", "direct", "hailort")

    def _make_hailo_engine(self, hef_path: str) -> HailoGstInferenceEngine:
        return HailoGstInferenceEngine(
            width=self.img_w,
            height=self.img_h,
            fps=self.hailo_fps,
            hef_path=hef_path,
            post_so=self.hailo_post_so,
            post_func=self.hailo_post_function,
            video_sink=self.hailo_video_sink,
            queue_max_buffers=self.hailo_queue_max_buffers,
            use_videoconvert=self.hailo_use_videoconvert,
            label_filter=self.label_filter,
        )

    def _make_hailo_direct_engine(self, hef_path: str) -> HailoDirectInferenceEngine:
        return HailoDirectInferenceEngine(
            hef_path=hef_path,
            infer_timeout_ms=self.infer_timeout_ms,
            label_filter=self.label_filter,
        )

    def _switch_hailo_hef(self, new_hef_path: str) -> None:
        old_hef_path = self.hailo_hef_path

        with self._engine_lock:
            if not self._wait_for_engine_idle_locked(timeout_s=10.0):
                raise RuntimeError("engine busy while switching HEF")

            if isinstance(self.engine, (HailoGstInferenceEngine, HailoDirectInferenceEngine)):
                try:
                    self.engine.reload_hef(new_hef_path)
                except Exception as exc:
                    # Best effort rollback to keep inference alive on switch failure.
                    try:
                        self.engine.reload_hef(old_hef_path)
                    except Exception as rollback_exc:
                        self.get_logger().error(
                            "model switch rollback failed "
                            f"(old_hef={old_hef_path}): {rollback_exc}"
                        )
                    raise RuntimeError(f"failed to reload HEF: {exc}") from exc

                self.hailo_hef_path = new_hef_path
                if isinstance(self.engine, HailoDirectInferenceEngine):
                    self.active_backend = "hailo_direct"
                else:
                    self.active_backend = "hailo_gst"
                return

            old_engine = self.engine
            if self._backend_wants_direct(self.inference_backend):
                new_engine = self._make_hailo_direct_engine(new_hef_path)
                new_active_backend = "hailo_direct"
            else:
                new_engine = self._make_hailo_engine(new_hef_path)
                new_active_backend = "hailo_gst"

            self.engine = new_engine
            self.hailo_hef_path = new_hef_path
            self.active_backend = new_active_backend

            try:
                old_engine.close()
            except Exception:
                pass

    def _on_set_parameters(self, params) -> SetParametersResult:
        requested_hef_path: str | None = None
        for param in params:
            if param.name == "hailo_hef_path":
                requested_hef_path = str(param.value).strip()

        if requested_hef_path is None:
            return SetParametersResult(successful=True)

        if not self._is_hailo_backend_name(self.inference_backend):
            return SetParametersResult(
                successful=False,
                reason="model switch requires hailo backend",
            )

        if not requested_hef_path:
            return SetParametersResult(
                successful=False,
                reason="hailo_hef_path cannot be empty",
            )

        if not os.path.isfile(requested_hef_path):
            return SetParametersResult(
                successful=False,
                reason=f"HEF file not found: {requested_hef_path}",
            )

        if requested_hef_path == self.hailo_hef_path:
            return SetParametersResult(successful=True, reason="HEF unchanged")

        try:
            self._switch_hailo_hef(requested_hef_path)
        except Exception as exc:
            self.get_logger().error(f"model switch rejected: {exc}")
            return SetParametersResult(successful=False, reason=str(exc))

        self.get_logger().info(f"model switch applied (hef={requested_hef_path})")
        return SetParametersResult(successful=True, reason="model switch applied")

    def _build_engine(self):
        if self.inference_backend in ("stub", "none"):
            self.active_backend = "stub"
            self.get_logger().warning("perception backend set to stub (no real inference)")
            return StubInferenceEngine()

        if not self._is_hailo_backend_name(self.inference_backend):
            self.active_backend = "stub"
            self.get_logger().warning(
                f"unknown inference_backend='{self.inference_backend}', falling back to stub"
            )
            return StubInferenceEngine()

        try:
            if self._backend_wants_direct(self.inference_backend):
                engine = self._make_hailo_direct_engine(self.hailo_hef_path)
                self.active_backend = "hailo_direct"
                self.get_logger().info(
                    "initialized Hailo direct backend "
                    f"(hef={self.hailo_hef_path}, infer_timeout_ms={self.infer_timeout_ms})"
                )
                return engine

            engine = self._make_hailo_engine(self.hailo_hef_path)
            self.active_backend = "hailo_gst"
            self.get_logger().info(
                "initialized Hailo GStreamer backend "
                f"(hef={self.hailo_hef_path}, post_func={self.hailo_post_function}, "
                f"queue_max_buffers={self.hailo_queue_max_buffers})"
            )
            return engine
        except Exception as exc:
            if not self.allow_stub_fallback:
                raise
            self.active_backend = "stub-fallback"
            self.get_logger().error(
                f"failed to initialize Hailo backend ({exc}); using stub fallback"
            )
            return StubInferenceEngine()

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

    def _enqueue_raw_frame(self, frame: RawFrame) -> None:
        dropped_count = 0
        enqueued = False

        with self._worker_cv:
            # Keep freshest-frame behavior: if full, evict one oldest frame and retry once.
            for _ in range(2):
                if len(self._queued_frames) < self.frame_queue_size:
                    self._queued_frames.append(frame)
                    enqueued = True
                    break

                if self._queued_frames:
                    self._queued_frames.popleft()
                    dropped_count += 1

            if not enqueued:
                dropped_count += 1

            self.frames_overwritten += dropped_count
            if enqueued:
                self.frames_enqueued += 1
                self._worker_cv.notify()

    def _prepare_frame(
        self,
        raw: RawFrame,
        resize_buf: np.ndarray,
        rgb_buf: np.ndarray,
    ) -> PreparedFrame | None:
        t_loop0 = now_ns()
        preprocessed, prep_level, prep_msg = preprocess_image_message(
            image_msg=raw.image_msg,
            infer_w=self.img_w,
            infer_h=self.img_h,
            resize_buf=resize_buf,
            rgb_buf=rgb_buf,
            now_ns=now_ns,
            consumer_name="perception_pipeline_node",
            pre_start_ns=t_loop0,
        )
        if preprocessed is None:
            if prep_level == "warning":
                self.get_logger().warning(str(prep_msg))
            else:
                self.get_logger().error(str(prep_msg))
            return None

        with self._preprocess_log_lock:
            if preprocessed.image_encoding != self._logged_encoding:
                self._logged_encoding = preprocessed.image_encoding
                self.get_logger().info(
                    f"inference input encoding={preprocessed.image_encoding}"
                )

            if not self._logged_own_data:
                self._logged_own_data = True
                self.get_logger().info(
                    f"numpy_view_owndata={preprocessed.numpy_owndata}"
                )

        return PreparedFrame(
            seq=int(raw.seq),
            frame_id=int(raw.frame_id),
            src_stamp_ns=int(raw.src_stamp_ns),
            stamp_sec=int(raw.stamp_sec),
            stamp_nanosec=int(raw.stamp_nanosec),
            image_width=int(preprocessed.image_width),
            image_height=int(preprocessed.image_height),
            image_encoding=str(preprocessed.image_encoding),
            t_loop0=int(t_loop0),
            t_cam_msg_seen_ns=int(raw.t_cam_msg_seen_ns),
            t_pre_start_ns=int(preprocessed.t_pre_start_ns),
            t_pre_end_ns=int(preprocessed.t_pre_end_ns),
            t_ros_to_np_start_ns=int(preprocessed.t_ros_to_np_start_ns),
            t_ros_to_np_end_ns=int(preprocessed.t_ros_to_np_end_ns),
            t_resize_start_ns=int(preprocessed.t_resize_start_ns),
            t_resize_end_ns=int(preprocessed.t_resize_end_ns),
            t_color_start_ns=int(preprocessed.t_color_start_ns),
            t_color_end_ns=int(preprocessed.t_color_end_ns),
            infer_img=np.ascontiguousarray(preprocessed.infer_img).copy(),
        )

    def _enqueue_prepared_frame(self, frame: PreparedFrame) -> None:
        dropped_count = 0
        enqueued = False

        with self._prepared_cv:
            # Keep freshest-frame behavior on prepared queue as well.
            for _ in range(2):
                if len(self._prepared_frames) < self.prepared_queue_size:
                    self._prepared_frames.append(frame)
                    enqueued = True
                    break

                if self._prepared_frames:
                    self._prepared_frames.popleft()
                    dropped_count += 1

            if not enqueued:
                dropped_count += 1

            self.frames_prepared_overwritten += dropped_count
            if enqueued:
                self.frames_prepared_enqueued += 1
                self._prepared_cv.notify()

    def _preprocess_worker_loop(self, _worker_id: int) -> None:
        worker_resize_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)
        worker_rgb_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)

        while True:
            raw_frame: RawFrame | None = None
            with self._worker_cv:
                while not self._worker_stop and not self._queued_frames:
                    self._worker_cv.wait(timeout=0.2)

                if self._worker_stop:
                    return

                if self._queued_frames:
                    raw_frame = self._queued_frames.popleft()

            if raw_frame is None:
                continue

            frame = self._prepare_frame(
                raw_frame,
                resize_buf=worker_resize_buf,
                rgb_buf=worker_rgb_buf,
            )
            if frame is None:
                continue

            self._enqueue_prepared_frame(frame)

    def _infer_worker_loop(self) -> None:
        worker_resize_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)
        worker_rgb_buf = np.empty((self.img_h, self.img_w, 3), dtype=np.uint8)

        while True:
            raw_frame: RawFrame | None = None
            with self._worker_cv:
                while not self._worker_stop and not self._queued_frames:
                    self._worker_cv.wait(timeout=0.2)

                if self._worker_stop:
                    return

                if self._queued_frames:
                    raw_frame = self._queued_frames.popleft()

            if raw_frame is None:
                continue

            # Keep inference sequence tied to processed frames (legacy parity).
            # If sequence advances on received-but-dropped frames, appsrc PTS jumps
            # can introduce artificial wait before pre_hailonet probe timestamps.
            raw_frame.seq = int(self.seq_counter)
            raw_frame.frame_id = int(self.frame_counter)
            self.seq_counter += 1
            self.frame_counter += 1

            frame = self._prepare_frame(
                raw_frame,
                resize_buf=worker_resize_buf,
                rgb_buf=worker_rgb_buf,
            )
            if frame is None:
                continue

            try:
                self._process_prepared_frame(frame)
            except Exception as exc:
                self.get_logger().warning(
                    f"engine-owner inference worker error: {exc}"
                )

    def _build_detection_array(self, frame: PreparedFrame, result: dict[str, Any]) -> Detection2DArray:
        det_header_frame_id = f"frame_{frame.frame_id}"

        det_arr = Detection2DArray()
        det_arr.header.stamp.sec = int(frame.stamp_sec)
        det_arr.header.stamp.nanosec = int(frame.stamp_nanosec)
        det_arr.header.frame_id = det_header_frame_id

        dets = result.get("detections", result.get("dets", [])) if isinstance(result, dict) else []
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

        return det_arr

    def _process_prepared_frame(self, frame: PreparedFrame) -> None:
        t_engine_start_ns = now_ns()
        engine = None
        with self._engine_lock:
            engine = self.engine
            self._engine_active_calls += 1

        try:
            # Use positional args so engine backends remain compatible even if parameter
            # names differ (e.g., seq vs _seq in older implementations).
            result = engine.infer(
                frame.infer_img,
                frame.seq,
                frame.frame_id,
                frame.src_stamp_ns,
                self.infer_timeout_ms,
            )
        except Exception as exc:
            self.get_logger().warning(f"in-process inference failed: {exc}")
            result = None
        finally:
            with self._engine_lock:
                self._engine_active_calls = max(0, self._engine_active_calls - 1)
                if self._engine_active_calls == 0:
                    self._engine_cv.notify_all()

        t_engine_end_ns = now_ns()

        timeout_hit = result is None
        if timeout_hit:
            self.frames_timeouts += 1
            if (self.frames_timeouts % self.timeout_log_every) == 1:
                self.get_logger().warning(
                    f"in-process inference timeout (count={self.frames_timeouts})"
                )
            result = {
                "detections": [],
                "timing": {
                    "t_infer_start_ns": t_engine_start_ns,
                    "t_infer_end_ns": t_engine_end_ns,
                    "t_post_start_ns": t_engine_end_ns,
                    "t_post_end_ns": t_engine_end_ns,
                },
            }

        timing_reply = result.get("timing", {}) if isinstance(result, dict) else {}
        t_infer_start_ns = _safe_int(timing_reply.get("t_infer_start_ns"), 0)
        t_infer_end_ns = _safe_int(timing_reply.get("t_infer_end_ns"), 0)
        t_post_start_ns = _safe_int(timing_reply.get("t_post_start_ns"), 0)
        t_post_end_ns = _safe_int(timing_reply.get("t_post_end_ns"), 0)

        if t_infer_start_ns <= 0:
            t_infer_start_ns = t_engine_start_ns
        if t_infer_end_ns <= 0:
            t_infer_end_ns = t_engine_end_ns
        if t_post_start_ns <= 0:
            t_post_start_ns = t_infer_end_ns
        if t_post_end_ns <= 0:
            t_post_end_ns = t_infer_end_ns

        container_queue_ms = _ms(t_infer_start_ns - frame.t_pre_end_ns)
        if container_queue_ms < 0.0:
            container_queue_ms = 0.0

        roundtrip_ms = _ms(t_engine_end_ns - t_engine_start_ns)
        self.last_roundtrip_ms = roundtrip_ms

        t_det_pub_start_ns = now_ns()
        det_arr = self._build_detection_array(frame, result)

        try:
            self.pub_dets.publish(det_arr)
        except Exception as exc:
            if rclpy.ok():
                self.get_logger().warning(f"detections publish failed: {exc}")
            return

        t_det_pub_end_ns = now_ns()

        pub_dt_ms = 0.0
        if self.last_det_pub_ns is not None:
            pub_dt_ms = _ms(t_det_pub_end_ns - self.last_det_pub_ns)
            self.pub_dt_hist_ms.append(pub_dt_ms)
        self.last_det_pub_ns = t_det_pub_end_ns

        if self.publish_timing:
            tmsg = Timing()
            tmsg.seq = int(frame.seq)
            tmsg.frame_id = int(frame.frame_id)
            tmsg.src_stamp_ns = int(frame.src_stamp_ns)
            tmsg.t_cam_msg_seen_ns = int(frame.t_cam_msg_seen_ns)

            tmsg.image_width = int(frame.image_width)
            tmsg.image_height = int(frame.image_height)
            tmsg.image_encoding = str(frame.image_encoding)

            tmsg.t_pre_start_ns = int(frame.t_pre_start_ns)
            tmsg.t_pre_end_ns = int(frame.t_pre_end_ns)
            tmsg.t_det_pub_start_ns = int(t_det_pub_start_ns)
            tmsg.t_det_pub_end_ns = int(t_det_pub_end_ns)

            tmsg.t_infer_start_ns = int(t_infer_start_ns)
            tmsg.t_infer_end_ns = int(t_infer_end_ns)
            tmsg.t_post_start_ns = int(t_post_start_ns)
            tmsg.t_post_end_ns = int(t_post_end_ns)

            tmsg.ros_wait_ms = _ms(frame.t_pre_start_ns - frame.t_cam_msg_seen_ns)
            tmsg.pre_ms = _ms(frame.t_pre_end_ns - frame.t_pre_start_ns)
            tmsg.ros_to_np_ms = _ms(frame.t_ros_to_np_end_ns - frame.t_ros_to_np_start_ns)
            tmsg.resize_ms = _ms(frame.t_resize_end_ns - frame.t_resize_start_ns)
            tmsg.color_ms = _ms(frame.t_color_end_ns - frame.t_color_start_ns)
            tmsg.pack_ms = 0.0
            tmsg.container_queue_ms = float(container_queue_ms)
            tmsg.infer_ms = _ms(t_infer_end_ns - t_infer_start_ns)
            tmsg.post_ms = _ms(t_post_end_ns - t_post_start_ns)

            tmsg.det_pub_ms = _ms(t_det_pub_end_ns - t_det_pub_start_ns)
            tmsg.e2e_det_ms = _ms(t_det_pub_end_ns - frame.t_cam_msg_seen_ns)

            t_loop1 = now_ns()
            tmsg.loop_ms = _ms(t_loop1 - frame.t_loop0)
            tmsg.pub_dt_ms = float(pub_dt_ms)

            # Deprecated alias writes kept for schema <=2 consumers.
            tmsg.pts_ns = int(frame.src_stamp_ns)
            tmsg.t_pub_ns = int(t_engine_start_ns)
            tmsg.lat_ms = tmsg.e2e_det_ms

            try:
                self.pub_timing.publish(tmsg)
            except Exception as exc:
                if rclpy.ok():
                    self.get_logger().warning(f"timing publish failed: {exc}")

        self.frames_processed += 1
        if self.log_every > 0 and (self.frames_processed % self.log_every) == 0:
            if self.pub_dt_hist_ms:
                pub_dt_arr = np.array(self.pub_dt_hist_ms, dtype=np.float64)
                pub_dt_p50 = float(np.percentile(pub_dt_arr, 50))
                pub_dt_p95 = float(np.percentile(pub_dt_arr, 95))
            else:
                pub_dt_p50 = 0.0
                pub_dt_p95 = 0.0

            queue_note = (
                f" raw_enq={self.frames_enqueued} raw_overwritten={self.frames_overwritten}"
                f" prepared_enq={self.frames_prepared_enqueued} prepared_overwritten={self.frames_prepared_overwritten}"
            )

            self.get_logger().info(
                "perception_pipeline "
                f"frames={self.frames_processed} "
                f"recv={self.frames_received} "
                f"timeouts={self.frames_timeouts} "
                f"backend={self.active_backend} "
                f"dets={len(det_arr.detections)} "
                f"rt_ms={roundtrip_ms:.2f} "
                f"container_queue_ms={container_queue_ms:.2f} "
                f"pub_dt_ms={pub_dt_ms:.2f} "
                f"pub_dt_p50_ms={pub_dt_p50:.2f} "
                f"pub_dt_p95_ms={pub_dt_p95:.2f}"
                f"{queue_note}"
            )

    def on_image(self, msg: Image) -> None:
        t_cam_msg_seen_ns = now_ns()
        src_stamp_ns = stamp_to_ns(msg.header.stamp)

        self.frames_received += 1

        raw_frame = RawFrame(
            # Assigned on dequeue in _infer_worker_loop.
            seq=0,
            frame_id=0,
            src_stamp_ns=int(src_stamp_ns),
            stamp_sec=int(msg.header.stamp.sec),
            stamp_nanosec=int(msg.header.stamp.nanosec),
            t_cam_msg_seen_ns=int(t_cam_msg_seen_ns),
            image_msg=msg,
        )

        self._enqueue_raw_frame(raw_frame)

    def destroy_node(self):
        with self._worker_cv:
            self._worker_stop = True
            self._worker_cv.notify_all()

        if self._infer_worker_thread is not None and self._infer_worker_thread.is_alive():
            self._infer_worker_thread.join(timeout=2.0)

        if self._gc_disabled_by_node:
            try:
                gc.enable()
            except Exception:
                pass

        try:
            with self._engine_lock:
                if not self._wait_for_engine_idle_locked(timeout_s=5.0):
                    self.get_logger().warning(
                        "shutdown waiting for active inference calls timed out"
                    )
                self.engine.close()
        except Exception:
            pass

        return super().destroy_node()


def main(args=None) -> None:
    from rclpy.executors import SingleThreadedExecutor

    rclpy.init(args=args)
    node = None
    executor = SingleThreadedExecutor()

    try:
        node = PerceptionPipelineNode()
        executor.add_node(node)
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
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
