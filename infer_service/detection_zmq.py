#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import queue
import sys
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

        self.ctx = zmq.Context.instance()
        self.rep = self.ctx.socket(zmq.REP)
        self.rep.setsockopt(zmq.LINGER, 0)
        self.rep.setsockopt(zmq.RCVHWM, 1)
        self.rep.setsockopt(zmq.SNDHWM, 1)
        self.rep.bind(self.bind)

        self.pending_meta = deque()
        self.result_q: queue.Queue[dict] = queue.Queue(maxsize=1)

        self.pipeline = None
        self.appsrc = None
        self.identity = None

        self._build_pipeline()

    def _build_pipeline(self):
        pipeline_str = (
            f'appsrc name=source is-live=true block=true format=time do-timestamp=false '
            f'caps=video/x-raw,format=RGB,width={self.width},height={self.height},framerate={self.fps}/1 ! '
            f'queue max-size-buffers=2 leaky=downstream ! '
            f'videoconvert ! '
            f'hailonet hef-path={self.hef_path} batch-size=1 force-writable=true ! '
            f'queue max-size-buffers=2 leaky=downstream ! '
            f'hailofilter function-name={self.post_func} so-path={self.post_so} qos=false ! '
            f'identity name=post_identity silent=true ! '
            f'{self.video_sink} sync=false'
        )

        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name("source")
        self.identity = self.pipeline.get_by_name("post_identity")

        if self.appsrc is None:
            raise RuntimeError("Failed to get appsrc element from pipeline")
        if self.identity is None:
            raise RuntimeError("Failed to get identity element from pipeline")

        pad = self.identity.get_static_pad("src")
        if pad is None:
            raise RuntimeError("Failed to get src pad from post_identity")

        pad.add_probe(Gst.PadProbeType.BUFFER, self._probe_callback)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to set ROS inference pipeline to PLAYING")

        print("ROS pipeline:", pipeline_str, flush=True)

    def _probe_callback(self, pad, info):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        try:
            meta = self.pending_meta.popleft()
        except IndexError:
            return Gst.PadProbeReturn.OK

        dets = _extract_dets_from_buffer(buffer)

        reply = {
            "seq": meta["seq"],
            "frame_id": meta["frame_id"],
            "timestamp_ns": meta["timestamp_ns"],
            "infer_ms": (time.time_ns() - meta["t_infer0_ns"]) / 1e6,
            "detections": dets,
        }

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

        self.pending_meta.append(meta)

        ret = self.appsrc.emit("push-buffer", buf)
        if ret != Gst.FlowReturn.OK:
            try:
                self.pending_meta.pop()
            except Exception:
                pass
            raise RuntimeError(f"appsrc push-buffer failed: {ret}")

    def serve_forever(self):
        print(f"REQ/REP inference service listening on {self.bind}", flush=True)

        while True:
            try:
                parts = self.rep.recv_multipart()
            except KeyboardInterrupt:
                break

            if len(parts) != 2:
                self.rep.send_json(
                    {"ok": False, "error": f"expected 2 parts, got {len(parts)}"}
                )
                continue

            try:
                metadata = json.loads(parts[0].decode("utf-8"))
                frame_bytes = parts[1]

                expected_size = (
                    int(metadata["width"])
                    * int(metadata["height"])
                    * int(metadata["channels"])
                )
                if len(frame_bytes) != expected_size:
                    self.rep.send_json(
                        {
                            "ok": False,
                            "error": f"frame size mismatch: got={len(frame_bytes)} expected={expected_size}",
                        }
                    )
                    continue

                meta = {
                    "seq": int(metadata.get("seq", 0)),
                    "frame_id": int(metadata.get("frame_id", 0)),
                    "timestamp_ns": int(metadata["timestamp_ns"]),
                    "t_infer0_ns": time.time_ns(),
                }

                self._push_frame(frame_bytes, meta)

                try:
                    reply = self.result_q.get(timeout=2.0)
                except queue.Empty:
                    self.rep.send_json({"ok": False, "error": "inference timeout"})
                    continue

                self.rep.send_json(reply)

            except Exception as exc:
                self.rep.send_json({"ok": False, "error": str(exc)})

    def close(self):
        try:
            if self.pipeline is not None:
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass

        try:
            self.rep.close(0)
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