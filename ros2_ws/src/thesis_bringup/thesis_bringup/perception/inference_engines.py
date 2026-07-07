#!/usr/bin/env python3
"""Inference backends used by the perception pipeline node."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from thesis_bringup.perception.pipeline_utils import (
    _bbox_to_xywh,
    _normalize_label,
    now_ns,
)


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


