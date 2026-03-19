#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path

import gi
import hailo
import zmq

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.detection_simple.detection_pipeline_simple import (
    GStreamerDetectionApp,
)

from zmq_pub import ZmqPublisher


video_src = os.getenv("HAILO_VIDEO_SOURCE", "/root/thesis_service/example_640_x10.mp4")
video_sink = os.getenv("HAILO_VIDEO_SINK", "fakesink")
loop_video = os.getenv("HAILO_LOOP_VIDEO", "0")


def now_ns() -> int:
    """Monotonic nanoseconds for container stage timing."""
    return time.monotonic_ns()


def _set_env_file():
    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    os.environ["HAILO_ENV_FILE"] = str(env_file)


def _bbox_to_xywh(bbox):
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


def _extract_dets_from_buffer(buffer):
    dets = []
    try:
        roi = hailo.get_roi_from_buffer(buffer)
        for det in roi.get_objects_typed(hailo.HAILO_DETECTION):
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
        dets = []

    return dets


class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.zpub = ZmqPublisher(bind="tcp://0.0.0.0:5555", topic=b"dets")
        self.last_pts_ns = None
        self.seq = 0


def app_callback(pad, info, user_data: user_app_callback_class):
    user_data.increment()
    frame_id = user_data.get_count()

    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    pts_ns = int(buffer.pts)

    if user_data.last_pts_ns == pts_ns:
        return Gst.PadProbeReturn.OK
    user_data.last_pts_ns = pts_ns

    user_data.seq += 1
    dets = _extract_dets_from_buffer(buffer)

    user_data.zpub.send(
        dets,
        frame_id=frame_id,
        extra={
            "pts_ns": pts_ns,
            "seq": user_data.seq,
            "t_pub": time.time_ns(),
        },
    )

    return Gst.PadProbeReturn.OK


def main_file_mode():
    Gst.init(None)
    _set_env_file()

    arch = os.getenv("HAILO_ARCH", "hailo8")
    video_src = os.getenv("HAILO_VIDEO_SOURCE", "/root/thesis_service/example_640_x10.mp4")
    hef_path = os.getenv("HAILO_HEF_PATH", "/root/thesis_service/resources/hefs/yolov6n_hailo8.hef")

    if "--arch" not in sys.argv:
        sys.argv += ["--arch", arch]
    if "--input" not in sys.argv:
        sys.argv += ["--input", video_src]
    if "--hef-path" not in sys.argv:
        sys.argv += ["--hef-path", hef_path]

    user_data = user_app_callback_class()

    with contextlib.redirect_stdout(io.StringIO()):
        app = GStreamerDetectionApp(app_callback, user_data)

    try:
        app.pipeline.set_state(Gst.State.NULL)
    except Exception:
        pass

    app.video_sink = video_sink
    app.show_fps = False
    app.batch_size = 1

    post_so = os.getenv(
        "HAILO_POST_SO",
        "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so",
    )
    app.post_process_so = post_so
    app.post_function_name = os.getenv("HAILO_POST_FUNC", "filter")

    app.create_pipeline()
    print(app.get_pipeline_string(), flush=True)
    app.run()


class RosReqRepInferenceService:
    def __init__(self):
        Gst.init(None)
        _set_env_file()

        self.bind = os.getenv("HAILO_REQREP_BIND", "tcp://0.0.0.0:5556")
        self.hef_path = os.getenv(
            "HAILO_HEF_PATH",
            "/root/thesis_service/resources/hefs/yolov6n_hailo8.hef",
        )
        self.post_so = os.getenv(
            "HAILO_POST_SO",
            "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so",
        )
        self.post_func = os.getenv("HAILO_POST_FUNC", "filter")
        self.video_sink = os.getenv("HAILO_VIDEO_SINK", "fakesink")
        self.width = int(os.getenv("HAILO_INFER_WIDTH", "640"))
        self.height = int(os.getenv("HAILO_INFER_HEIGHT", "640"))
        self.fps = int(os.getenv("HAILO_INFER_FPS", "30"))
        self.log_every = max(0, int(os.getenv("HAILO_REQREP_LOG_EVERY", "0")))
        self.req_count = 0
        self.reply_count = 0
        self.last_req_recv_ns = 0

        self.ctx = zmq.Context.instance()
        self.router = self.ctx.socket(zmq.ROUTER)
        self.router.setsockopt(zmq.LINGER, 0)
        self.router.setsockopt(zmq.RCVHWM, 64)
        self.router.setsockopt(zmq.SNDHWM, 64)
        self.router.bind(self.bind)

        self.pending_meta = deque()
        self.pending_meta_by_pts: dict[int, dict] = {}
        self.meta_lock = threading.Lock()
        self.result_q: queue.Queue[dict] = queue.Queue(maxsize=8)

        self.pipeline = None
        self.appsrc = None
        self.pre_identity = None
        self.infer_identity = None
        self.identity = None

        self._build_pipeline()

    def _build_pipeline(self):
        pipeline_str = (
            f'appsrc name=source is-live=true block=false format=time do-timestamp=false '
            f'caps=video/x-raw,format=RGB,width={self.width},height={self.height},framerate={self.fps}/1 ! '
            f'queue max-size-buffers=6 leaky=downstream ! '
            f'videoconvert ! '
            f'identity name=pre_hailonet_identity silent=true ! '
            f'hailonet hef-path={self.hef_path} batch-size=1 force-writable=true ! '
            f'identity name=infer_identity silent=true ! '
            f'queue max-size-buffers=6 leaky=downstream ! '
            f'hailofilter function-name={self.post_func} so-path={self.post_so} qos=false ! '
            f'identity name=post_identity silent=true ! '
            f'{self.video_sink} sync=false'
        )

        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name("source")
        self.pre_identity = self.pipeline.get_by_name("pre_hailonet_identity")
        self.infer_identity = self.pipeline.get_by_name("infer_identity")
        self.identity = self.pipeline.get_by_name("post_identity")

        if self.appsrc is None:
            raise RuntimeError("Failed to get appsrc element from pipeline")
        if self.pre_identity is None:
            raise RuntimeError("Failed to get pre_hailonet_identity element from pipeline")
        if self.infer_identity is None:
            raise RuntimeError("Failed to get infer_identity element from pipeline")
        if self.identity is None:
            raise RuntimeError("Failed to get identity element from pipeline")

        pre_pad = self.pre_identity.get_static_pad("src")
        if pre_pad is None:
            raise RuntimeError("Failed to get src pad from pre_hailonet_identity")

        infer_pad = self.infer_identity.get_static_pad("src")
        if infer_pad is None:
            raise RuntimeError("Failed to get src pad from infer_identity")

        pad = self.identity.get_static_pad("src")
        if pad is None:
            raise RuntimeError("Failed to get src pad from post_identity")

        pre_pad.add_probe(Gst.PadProbeType.BUFFER, self._pre_infer_probe_callback)
        infer_pad.add_probe(Gst.PadProbeType.BUFFER, self._infer_probe_callback)
        pad.add_probe(Gst.PadProbeType.BUFFER, self._probe_callback)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to set ROS inference pipeline to PLAYING")

        print("ROS pipeline:", pipeline_str, flush=True)

    def _lookup_meta_by_buffer(self, buffer) -> dict | None:
        pts = int(buffer.pts)
        with self.meta_lock:
            return self.pending_meta_by_pts.get(pts)

    def _pre_infer_probe_callback(self, pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        meta = self._lookup_meta_by_buffer(buffer)
        if meta is not None and meta.get("t_infer_start_ns", 0) == 0:
            meta["t_infer_start_ns"] = now_ns()

        return Gst.PadProbeReturn.OK

    def _infer_probe_callback(self, pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        meta = self._lookup_meta_by_buffer(buffer)
        if meta is not None:
            t_here = now_ns()
            meta["t_infer_end_ns"] = t_here
            meta["t_post_start_ns"] = t_here

        return Gst.PadProbeReturn.OK

    def _probe_callback(self, pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        meta = self._lookup_meta_by_buffer(buffer)
        if meta is None:
            return Gst.PadProbeReturn.OK

        pts = int(buffer.pts)
        with self.meta_lock:
            for idx, item in enumerate(self.pending_meta):
                if int(item.get("pts", -1)) == pts:
                    del self.pending_meta[idx]
                    break

        t_post_end_ns = now_ns()
        meta["t_post_end_ns"] = t_post_end_ns

        dets = _extract_dets_from_buffer(buffer)

        timing = {
            "t_req_recv_ns": int(meta.get("t_req_recv_ns", 0)),
            "t_frame_unpack_start_ns": int(meta.get("t_frame_unpack_start_ns", 0)),
            "t_frame_unpack_end_ns": int(meta.get("t_frame_unpack_end_ns", 0)),
            "t_infer_start_ns": int(meta.get("t_infer_start_ns", 0)),
            "t_infer_end_ns": int(meta.get("t_infer_end_ns", 0)),
            "t_post_start_ns": int(meta.get("t_post_start_ns", 0)),
            "t_post_end_ns": int(meta.get("t_post_end_ns", 0)),
            "t_reply_send_ns": 0,
        }

        infer_ms = 0.0
        if timing["t_infer_end_ns"] > 0 and timing["t_infer_start_ns"] > 0 and timing["t_infer_end_ns"] >= timing["t_infer_start_ns"]:
            infer_ms = (timing["t_infer_end_ns"] - timing["t_infer_start_ns"]) / 1e6

        reply = {
            "seq": meta["seq"],
            "frame_id": meta["frame_id"],
            "src_stamp_ns": meta["src_stamp_ns"],
            "timestamp_ns": meta["src_stamp_ns"],
            "infer_ms": infer_ms,
            "detections": dets,
            "timing": timing,
            "_route": {
                "identity": meta.get("client_identity"),
                "has_empty": bool(meta.get("client_has_empty", False)),
            },
            "_req_dt_ms": float(meta.get("req_dt_ms", 0.0) or 0.0),
        }

        with self.meta_lock:
            self.pending_meta_by_pts.pop(pts, None)

        try:
            if self.result_q.full():
                try:
                    self.result_q.get_nowait()
                except queue.Empty:
                    pass
            self.result_q.put_nowait(reply)
        except Exception:
            pass

        return Gst.PadProbeReturn.OK

    def _push_frame(self, frame_bytes: bytes, meta: dict):
        buf = Gst.Buffer.new_allocate(None, len(frame_bytes), None)
        buf.fill(0, frame_bytes)

        frame_idx = meta["seq"]
        frame_duration_ns = int(1e9 / max(1, self.fps))
        buf.pts = frame_idx * frame_duration_ns
        buf.dts = Gst.CLOCK_TIME_NONE
        buf.duration = frame_duration_ns

        meta["pts"] = int(buf.pts)
        self.pending_meta.append(meta)
        with self.meta_lock:
            self.pending_meta_by_pts[int(buf.pts)] = meta

        ret = self.appsrc.emit("push-buffer", buf)
        if ret != Gst.FlowReturn.OK:
            try:
                self.pending_meta.pop()
            except Exception:
                pass
            with self.meta_lock:
                self.pending_meta_by_pts.pop(int(buf.pts), None)
            raise RuntimeError(f"appsrc push-buffer failed: {ret}")

    def serve_forever(self):
        print(f"ROUTER inference service listening on {self.bind}", flush=True)

        poller = zmq.Poller()
        poller.register(self.router, zmq.POLLIN)

        while True:
            try:
                events = dict(poller.poll(5))
            except KeyboardInterrupt:
                break

            if self.router in events and (events[self.router] & zmq.POLLIN):
                while True:
                    try:
                        parts = self.router.recv_multipart(flags=zmq.NOBLOCK)
                    except zmq.Again:
                        break
                    except KeyboardInterrupt:
                        return

                    if len(parts) < 2:
                        continue

                    client_identity = parts[0]
                    payload_idx = 1
                    has_empty = False
                    if len(parts) >= 2 and parts[1] == b"":
                        has_empty = True
                        payload_idx = 2

                    payload = parts[payload_idx:]

                    t_req_recv_ns = now_ns()
                    self.req_count += 1
                    req_dt_ms = 0.0
                    if self.last_req_recv_ns > 0:
                        req_dt_ms = (t_req_recv_ns - self.last_req_recv_ns) / 1e6
                    self.last_req_recv_ns = t_req_recv_ns

                    if len(payload) != 2:
                        self._send_error(
                            client_identity,
                            has_empty,
                            f"expected 2 payload parts, got {len(payload)}",
                        )
                        continue

                    try:
                        t_frame_unpack_start_ns = now_ns()
                        metadata = json.loads(payload[0].decode("utf-8"))
                        frame_bytes = payload[1]

                        expected_size = (
                            int(metadata["width"])
                            * int(metadata["height"])
                            * int(metadata["channels"])
                        )
                        if len(frame_bytes) != expected_size:
                            self._send_error(
                                client_identity,
                                has_empty,
                                f"frame size mismatch: got={len(frame_bytes)} expected={expected_size}",
                            )
                            continue

                        meta = {
                            "seq": int(metadata.get("seq", 0)),
                            "frame_id": int(metadata.get("frame_id", 0)),
                            "src_stamp_ns": int(metadata.get("src_stamp_ns", metadata.get("timestamp_ns", 0))),
                            "t_req_recv_ns": t_req_recv_ns,
                            "t_frame_unpack_start_ns": t_frame_unpack_start_ns,
                            "t_frame_unpack_end_ns": now_ns(),
                            "t_infer_start_ns": 0,
                            "t_infer_end_ns": 0,
                            "t_post_start_ns": 0,
                            "t_post_end_ns": 0,
                            "client_identity": client_identity,
                            "client_has_empty": has_empty,
                            "req_dt_ms": req_dt_ms,
                        }

                        self._push_frame(frame_bytes, meta)

                    except Exception as exc:
                        self._send_error(client_identity, has_empty, str(exc))

            while True:
                try:
                    reply = self.result_q.get_nowait()
                except queue.Empty:
                    break

                if not isinstance(reply, dict):
                    continue

                route = reply.pop("_route", None)
                req_dt_ms = float(reply.pop("_req_dt_ms", 0.0) or 0.0)
                if not isinstance(route, dict):
                    continue

                client_identity = route.get("identity")
                has_empty = bool(route.get("has_empty", False))
                if not isinstance(client_identity, (bytes, bytearray)):
                    continue

                timing = reply.get("timing", {})
                t_reply_send_ns = now_ns()
                if isinstance(timing, dict):
                    timing["t_reply_send_ns"] = t_reply_send_ns

                self._send_json(client_identity, has_empty, reply)

                self.reply_count += 1
                if self.log_every > 0 and (self.reply_count % self.log_every) == 0:
                    infer_ms = float(reply.get("infer_ms", 0.0) or 0.0)

                    wait_result_ms = 0.0
                    service_ms = 0.0
                    if isinstance(timing, dict):
                        t_frame_unpack_end_ns = int(timing.get("t_frame_unpack_end_ns", 0))
                        t_post_end_ns = int(timing.get("t_post_end_ns", 0))
                        t_req_recv_ns = int(timing.get("t_req_recv_ns", 0))
                        if t_post_end_ns > 0 and t_frame_unpack_end_ns > 0 and t_post_end_ns >= t_frame_unpack_end_ns:
                            wait_result_ms = (t_post_end_ns - t_frame_unpack_end_ns) / 1e6
                        if t_req_recv_ns > 0 and t_reply_send_ns >= t_req_recv_ns:
                            service_ms = (t_reply_send_ns - t_req_recv_ns) / 1e6

                    print(
                        "reqrep_prof "
                        f"count={self.reply_count} "
                        f"req_dt_ms={req_dt_ms:.3f} "
                        f"wait_result_ms={wait_result_ms:.3f} "
                        f"infer_ms={infer_ms:.3f} "
                        f"service_ms={service_ms:.3f}",
                        flush=True,
                    )

    def _send_json(self, identity: bytes, has_empty: bool, payload: dict):
        frames = [identity]
        if has_empty:
            frames.append(b"")
        frames.append(json.dumps(payload).encode("utf-8"))
        self.router.send_multipart(frames)

    def _send_error(self, identity: bytes, has_empty: bool, message: str):
        self._send_json(identity, has_empty, {"ok": False, "error": message})

    def close(self):
        try:
            if self.pipeline is not None:
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass

        try:
            self.router.close(0)
        except Exception:
            pass


def main_ros_mode():
    service = RosReqRepInferenceService()
    try:
        service.serve_forever()
    finally:
        service.close()


def main():
    frame_source = os.getenv("HAILO_FRAME_SOURCE", "file").strip().lower()

    if frame_source == "ros":
        main_ros_mode()
    else:
        main_file_mode()


if __name__ == "__main__":
    main()