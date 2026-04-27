#!/usr/bin/env python3

from __future__ import annotations

import gc
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from thesis_inference_client.preprocessing import preprocess_image_message
from thesis_msgs.msg import Timing
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def stamp_to_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def now_ns() -> int:
    return time.monotonic_ns()


def _ms(dt_ns: int) -> float:
    return float(dt_ns) / 1e6


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    out = str(value).strip().lower()
    if not out:
        return None
    if out in ("none", "all", "*"):
        return None
    return out


def _bbox_to_xywh(bbox) -> tuple[float | None, float | None, float | None, float | None]:
    if hasattr(bbox, "xmin") and hasattr(bbox, "width"):
        return (
            float(bbox.xmin()),
            float(bbox.ymin()),
            float(bbox.width()),
            float(bbox.height()),
        )

    if hasattr(bbox, "get_xmin") and hasattr(bbox, "get_width"):
        return (
            float(bbox.get_xmin()),
            float(bbox.get_ymin()),
            float(bbox.get_width()),
            float(bbox.get_height()),
        )

    return None, None, None, None


_COCO80_LABELS: tuple[str, ...] = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


@dataclass
class PreparedFrame:
    seq: int
    frame_id: int
    src_stamp_ns: int
    stamp_sec: int
    stamp_nanosec: int
    image_width: int
    image_height: int
    image_encoding: str
    t_loop0: int
    t_cam_msg_seen_ns: int
    t_pre_start_ns: int
    t_pre_end_ns: int
    t_ros_to_np_start_ns: int
    t_ros_to_np_end_ns: int
    t_resize_start_ns: int
    t_resize_end_ns: int
    t_color_start_ns: int
    t_color_end_ns: int
    infer_img: np.ndarray


@dataclass
class RawFrame:
    seq: int
    frame_id: int
    src_stamp_ns: int
    stamp_sec: int
    stamp_nanosec: int
    t_cam_msg_seen_ns: int
    image_msg: Image


class StubInferenceEngine:
    def infer(self, _frame_rgb: np.ndarray, _seq: int, _frame_id: int, _src_stamp_ns: int, _timeout_ms: int) -> dict[str, Any]:
        t0 = now_ns()
        return {
            "detections": [],
            "timing": {
                "t_infer_start_ns": t0,
                "t_infer_end_ns": t0,
                "t_post_start_ns": t0,
                "t_post_end_ns": t0,
            },
        }

    def close(self) -> None:
        return


class HailoGstInferenceEngine:
    def __init__(
        self,
        width: int,
        height: int,
        fps: int,
        hef_path: str,
        post_so: str,
        post_func: str,
        video_sink: str,
        queue_max_buffers: int,
        use_videoconvert: bool,
        label_filter: str | None,
    ) -> None:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        import hailo

        self.Gst = Gst
        self.hailo = hailo
        self.Gst.init(None)

        self.width = int(width)
        self.height = int(height)
        self.fps = max(1, int(fps))
        self.hef_path = str(hef_path)
        self.post_so = str(post_so)
        self.post_func = str(post_func)
        self.video_sink = str(video_sink)
        self.queue_max_buffers = max(1, int(queue_max_buffers))
        self.use_videoconvert = bool(use_videoconvert)
        self.label_filter = label_filter

        self.frame_duration_ns = int(1e9 / self.fps)
        self._closed = False
        self._cv = threading.Condition()
        self._pending_meta_by_pts: dict[int, dict[str, Any]] = {}
        self._results_by_pts: dict[int, dict[str, Any]] = {}

        self.pipeline = None
        self.appsrc = None
        self.pre_identity = None
        self.infer_identity = None
        self.post_identity = None

        self._build_pipeline()

    def _build_pipeline(self) -> None:
        queue_buffers = self.queue_max_buffers
        convert_stage = "videoconvert ! " if self.use_videoconvert else ""
        pipeline_str = (
            f"appsrc name=source is-live=true block=false format=time do-timestamp=false "
            f"max-buffers=1 leaky-type=downstream "
            f"caps=video/x-raw,format=RGB,width={self.width},height={self.height},framerate={self.fps}/1 ! "
            f"queue max-size-buffers={queue_buffers} leaky=downstream ! "
            f"{convert_stage}"
            f"identity name=pre_hailonet_identity silent=true ! "
            f"hailonet hef-path={self.hef_path} batch-size=1 force-writable=true ! "
            f"identity name=infer_identity silent=true ! "
            f"queue max-size-buffers={queue_buffers} leaky=downstream ! "
            f"hailofilter function-name={self.post_func} so-path={self.post_so} qos=false ! "
            f"identity name=post_identity silent=true ! "
            f"{self.video_sink} sync=false"
        )

        self.pipeline = self.Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name("source")
        self.pre_identity = self.pipeline.get_by_name("pre_hailonet_identity")
        self.infer_identity = self.pipeline.get_by_name("infer_identity")
        self.post_identity = self.pipeline.get_by_name("post_identity")

        if self.appsrc is None:
            raise RuntimeError("failed to initialize appsrc")
        if self.pre_identity is None or self.infer_identity is None or self.post_identity is None:
            raise RuntimeError("failed to initialize identity probes")

        pre_pad = self.pre_identity.get_static_pad("src")
        infer_pad = self.infer_identity.get_static_pad("src")
        post_pad = self.post_identity.get_static_pad("src")
        if pre_pad is None or infer_pad is None or post_pad is None:
            raise RuntimeError("failed to retrieve pipeline pads")

        pre_pad.add_probe(self.Gst.PadProbeType.BUFFER, self._on_pre_infer_probe)
        infer_pad.add_probe(self.Gst.PadProbeType.BUFFER, self._on_infer_probe)
        post_pad.add_probe(self.Gst.PadProbeType.BUFFER, self._on_post_probe)

        ret = self.pipeline.set_state(self.Gst.State.PLAYING)
        if ret == self.Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("failed to set Hailo pipeline to PLAYING")

    def _extract_dets_from_buffer(self, buffer) -> list[dict[str, Any]]:
        dets: list[dict[str, Any]] = []
        try:
            roi = self.hailo.get_roi_from_buffer(buffer)
            for det in roi.get_objects_typed(self.hailo.HAILO_DETECTION):
                label = det.get_label() if hasattr(det, "get_label") else None

                if hasattr(det, "get_confidence"):
                    score = float(det.get_confidence())
                elif hasattr(det, "get_score"):
                    score = float(det.get_score())
                else:
                    score = None

                bbox = det.get_bbox() if hasattr(det, "get_bbox") else None
                if bbox is not None:
                    x, y, w, h = _bbox_to_xywh(bbox)
                else:
                    x = y = w = h = None

                dets.append(
                    {
                        "label": label,
                        "score": score,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                    }
                )
        except Exception:
            return []

        if self.label_filter is None:
            return dets

        filtered: list[dict[str, Any]] = []
        for det in dets:
            det_label = _normalize_label(det.get("label"))
            if det_label == self.label_filter:
                filtered.append(det)
        return filtered

    def _lookup_pending_meta(self, pts: int) -> dict[str, Any] | None:
        with self._cv:
            return self._pending_meta_by_pts.get(pts)

    def _on_pre_infer_probe(self, _pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return self.Gst.PadProbeReturn.OK

        meta = self._lookup_pending_meta(int(buffer.pts))
        if meta is not None and _safe_int(meta.get("t_infer_start_ns"), 0) == 0:
            meta["t_infer_start_ns"] = now_ns()

        return self.Gst.PadProbeReturn.OK

    def _on_infer_probe(self, _pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return self.Gst.PadProbeReturn.OK

        meta = self._lookup_pending_meta(int(buffer.pts))
        if meta is not None:
            t_here = now_ns()
            meta["t_infer_end_ns"] = t_here
            meta["t_post_start_ns"] = t_here

        return self.Gst.PadProbeReturn.OK

    def _on_post_probe(self, _pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return self.Gst.PadProbeReturn.OK

        pts = int(buffer.pts)
        with self._cv:
            meta = self._pending_meta_by_pts.pop(pts, None)
        if meta is None:
            return self.Gst.PadProbeReturn.OK

        t_post_end_ns = now_ns()
        dets = self._extract_dets_from_buffer(buffer)

        timing = {
            "t_infer_start_ns": _safe_int(meta.get("t_infer_start_ns"), 0),
            "t_infer_end_ns": _safe_int(meta.get("t_infer_end_ns"), 0),
            "t_post_start_ns": _safe_int(meta.get("t_post_start_ns"), 0),
            "t_post_end_ns": t_post_end_ns,
        }

        result = {
            "detections": dets,
            "timing": timing,
        }

        with self._cv:
            self._results_by_pts[pts] = result
            self._cv.notify_all()

        return self.Gst.PadProbeReturn.OK

    def infer(self, frame_rgb: np.ndarray, seq: int, frame_id: int, src_stamp_ns: int, timeout_ms: int) -> dict[str, Any] | None:
        if self._closed:
            return None

        if frame_rgb.dtype != np.uint8:
            raise RuntimeError("inference frame must be uint8 RGB")

        frame_for_gst = frame_rgb if frame_rgb.flags["C_CONTIGUOUS"] else np.ascontiguousarray(frame_rgb)
        try:
            # Gst.Buffer.fill expects a flat byte buffer; 3D memoryviews can fail in PyGObject.
            frame_bytes = memoryview(frame_for_gst).cast("B")
        except TypeError:
            frame_bytes = frame_for_gst.tobytes(order="C")

        buf = self.Gst.Buffer.new_allocate(None, frame_for_gst.nbytes, None)
        buf.fill(0, frame_bytes)

        pts = int(seq * self.frame_duration_ns)

        buf.pts = pts
        buf.dts = self.Gst.CLOCK_TIME_NONE
        buf.duration = self.frame_duration_ns

        meta = {
            "seq": int(seq),
            "frame_id": int(frame_id),
            "src_stamp_ns": int(src_stamp_ns),
            "t_infer_start_ns": 0,
            "t_infer_end_ns": 0,
            "t_post_start_ns": 0,
            "t_post_end_ns": 0,
        }

        with self._cv:
            self._pending_meta_by_pts[pts] = meta

        ret = self.appsrc.emit("push-buffer", buf)
        if ret != self.Gst.FlowReturn.OK:
            with self._cv:
                self._pending_meta_by_pts.pop(pts, None)
            raise RuntimeError(f"appsrc push-buffer failed: {ret}")

        deadline = time.monotonic() + (max(1, int(timeout_ms)) / 1000.0)
        with self._cv:
            while not self._closed:
                result = self._results_by_pts.pop(pts, None)
                if result is not None:
                    return result

                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    self._pending_meta_by_pts.pop(pts, None)
                    return None
                self._cv.wait(timeout=remaining)

        return None

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._pending_meta_by_pts.clear()
            self._results_by_pts.clear()
            self._cv.notify_all()

        try:
            if self.pipeline is not None:
                self.pipeline.set_state(self.Gst.State.NULL)
        except Exception:
            pass

    def reload_hef(self, hef_path: str) -> None:
        if self._closed:
            raise RuntimeError("cannot reload HEF on a closed engine")

        new_hef_path = str(hef_path).strip()
        if not new_hef_path:
            raise RuntimeError("HEF path cannot be empty")

        with self._cv:
            self._pending_meta_by_pts.clear()
            self._results_by_pts.clear()
            self._cv.notify_all()

        try:
            if self.pipeline is not None:
                self.pipeline.set_state(self.Gst.State.NULL)
        except Exception:
            pass

        self.hef_path = new_hef_path
        self._build_pipeline()


class HailoDirectInferenceEngine:
    """In-process pyHailoRT backend with persistent configured network."""

    def __init__(
        self,
        hef_path: str,
        infer_timeout_ms: int,
        label_filter: str | None,
    ) -> None:
        from hailo_platform import HEF, InferVStreams, InputVStreamParams, OutputVStreamParams, VDevice

        self.HEF = HEF
        self.InferVStreams = InferVStreams
        self.InputVStreamParams = InputVStreamParams
        self.OutputVStreamParams = OutputVStreamParams
        self.VDevice = VDevice

        self.hef_path = str(hef_path)
        self.infer_timeout_ms = max(1, int(infer_timeout_ms))
        self.label_filter = label_filter

        self._lock = threading.RLock()
        self._closed = False

        self._vdevice = None
        self._network_group = None
        self._hef = None
        self._infer_ctx = None
        self._infer_pipeline = None
        self._activation_ctx = None

        self._input_name = ""
        self._input_shape: tuple[int, int, int] = (0, 0, 0)
        self._output_names: list[str] = []

        with self._lock:
            self._open_runtime_locked()

    def _open_runtime_locked(self) -> None:
        hef = self.HEF(self.hef_path)
        vdevice = self.VDevice()
        configured_networks = vdevice.configure(hef)
        if not configured_networks:
            vdevice.release()
            raise RuntimeError("no configured Hailo network groups available")

        network_group = configured_networks[0]
        input_infos = network_group.get_input_vstream_infos()
        if len(input_infos) != 1:
            vdevice.release()
            raise RuntimeError(
                f"direct backend requires exactly one input vstream (got={len(input_infos)})"
            )

        input_info = input_infos[0]
        input_shape = tuple(int(v) for v in tuple(input_info.shape))
        if len(input_shape) != 3:
            vdevice.release()
            raise RuntimeError(
                f"unexpected input shape for direct backend: {input_shape}"
            )

        output_infos = network_group.get_output_vstream_infos()
        output_names = [str(info.name) for info in output_infos]

        input_params = self.InputVStreamParams.make(
            network_group,
            timeout_ms=self.infer_timeout_ms,
            queue_size=1,
        )
        output_params = self.OutputVStreamParams.make(
            network_group,
            timeout_ms=self.infer_timeout_ms,
            queue_size=1,
        )

        infer_ctx = self.InferVStreams(network_group, input_params, output_params)
        infer_pipeline = None
        activation_ctx = None

        try:
            infer_pipeline = infer_ctx.__enter__()
            activation_ctx = network_group.activate(network_group.create_params())
            activation_ctx.__enter__()
        except Exception:
            try:
                infer_ctx.__exit__(None, None, None)
            except Exception:
                pass
            vdevice.release()
            raise

        self._hef = hef
        self._vdevice = vdevice
        self._network_group = network_group
        self._infer_ctx = infer_ctx
        self._infer_pipeline = infer_pipeline
        self._activation_ctx = activation_ctx
        self._input_name = str(input_info.name)
        self._input_shape = (input_shape[0], input_shape[1], input_shape[2])
        self._output_names = output_names

    def _close_runtime_locked(self) -> None:
        if self._activation_ctx is not None:
            try:
                self._activation_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._activation_ctx = None

        if self._infer_ctx is not None:
            try:
                self._infer_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._infer_ctx = None

        if self._vdevice is not None:
            try:
                self._vdevice.release()
            except Exception:
                pass

        self._vdevice = None
        self._network_group = None
        self._hef = None
        self._infer_pipeline = None
        self._input_name = ""
        self._input_shape = (0, 0, 0)
        self._output_names = []

    def _decode_class_rows(self, class_id: int, class_rows: Any) -> list[dict[str, Any]]:
        rows = np.asarray(class_rows)
        if rows.size == 0:
            return []

        if rows.ndim == 1:
            rows = rows.reshape(1, -1)
        elif rows.ndim > 2:
            rows = rows.reshape(-1, rows.shape[-1])

        mapped_label: str | None = None
        if 0 <= class_id < len(_COCO80_LABELS):
            mapped_label = _COCO80_LABELS[class_id]

        if self.label_filter is not None and mapped_label is not None:
            if _normalize_label(mapped_label) != self.label_filter:
                return []

        out: list[dict[str, Any]] = []
        for row in rows:
            if len(row) < 5:
                continue

            y_min = float(row[0])
            x_min = float(row[1])
            y_max = float(row[2])
            x_max = float(row[3])
            score = float(row[4])

            if not np.isfinite(score) or score <= 0.0:
                continue

            w = max(0.0, x_max - x_min)
            h = max(0.0, y_max - y_min)
            if w <= 0.0 or h <= 0.0:
                continue

            det: dict[str, Any] = {
                "class_id": int(class_id),
                "score": score,
                "x": float(x_min),
                "y": float(y_min),
                "w": float(w),
                "h": float(h),
            }
            if mapped_label is not None:
                det["label"] = mapped_label
            out.append(det)

        return out

    def _decode_output(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            if not value:
                return []
            # pyHailoRT NMS-by-class output shape for batch=1 is [batch][class][det,5].
            batch0 = value[0]
            if not isinstance(batch0, list):
                return []

            dets: list[dict[str, Any]] = []
            for class_id, class_rows in enumerate(batch0):
                dets.extend(self._decode_class_rows(class_id, class_rows))
            return dets

        if isinstance(value, np.ndarray):
            if value.ndim == 4 and value.shape[0] >= 1 and value.shape[2] >= 5:
                # TensorFlow-style NMS: [batch, class, bbox_params, dets].
                dets: list[dict[str, Any]] = []
                classes = value[0]
                for class_id in range(classes.shape[0]):
                    class_matrix = classes[class_id]
                    if class_matrix.ndim != 2 or class_matrix.shape[0] < 5:
                        continue
                    dets.extend(self._decode_class_rows(class_id, class_matrix.T))
                return dets

        return []

    def infer(
        self,
        frame_rgb: np.ndarray,
        _seq: int,
        _frame_id: int,
        _src_stamp_ns: int,
        _timeout_ms: int,
    ) -> dict[str, Any] | None:
        with self._lock:
            if self._closed:
                return None

            if frame_rgb.dtype != np.uint8:
                raise RuntimeError("inference frame must be uint8 RGB")
            if frame_rgb.ndim != 3:
                raise RuntimeError(f"inference frame must be HWC RGB, got ndim={frame_rgb.ndim}")
            if tuple(int(v) for v in frame_rgb.shape) != self._input_shape:
                raise RuntimeError(
                    f"inference frame shape mismatch (got={frame_rgb.shape}, expected={self._input_shape})"
                )

            frame_view = frame_rgb if frame_rgb.flags["C_CONTIGUOUS"] else np.ascontiguousarray(frame_rgb)
            batch = np.expand_dims(frame_view, axis=0)

            t_infer_start_ns = now_ns()
            try:
                outputs = self._infer_pipeline.infer({self._input_name: batch})
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    return None
                raise
            t_infer_end_ns = now_ns()

            t_post_start_ns = t_infer_end_ns
            dets: list[dict[str, Any]] = []
            for output_name in self._output_names:
                if output_name in outputs:
                    dets.extend(self._decode_output(outputs[output_name]))
            t_post_end_ns = now_ns()

            return {
                "detections": dets,
                "timing": {
                    "t_infer_start_ns": int(t_infer_start_ns),
                    "t_infer_end_ns": int(t_infer_end_ns),
                    "t_post_start_ns": int(t_post_start_ns),
                    "t_post_end_ns": int(t_post_end_ns),
                },
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._close_runtime_locked()

    def reload_hef(self, hef_path: str) -> None:
        new_hef_path = str(hef_path).strip()
        if not new_hef_path:
            raise RuntimeError("HEF path cannot be empty")

        with self._lock:
            if self._closed:
                raise RuntimeError("cannot reload HEF on a closed engine")

            self._close_runtime_locked()
            self.hef_path = new_hef_path
            self._open_runtime_locked()


class PerceptionPipelineNode(Node):
    """Single-process perception node with optional in-process Hailo backend."""

    def __init__(self) -> None:
        super().__init__("perception_pipeline_node")

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
