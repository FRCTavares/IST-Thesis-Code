#!/usr/bin/env python3
import os
from pathlib import Path
import time

import contextlib
import io
import sys

import hailo
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.detection_simple.detection_pipeline_simple import (
    GStreamerDetectionApp,
)

video_src = os.getenv("HAILO_VIDEO_SOURCE", "/root/thesis_service/example_640_x10.mp4")
video_sink = os.getenv("HAILO_VIDEO_SINK", "fakesink")
loop_video = os.getenv("HAILO_LOOP_VIDEO", "0")  # keep if you use it

from zmq_pub import ZmqPublisher

class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.zpub = ZmqPublisher(bind="tcp://0.0.0.0:5555", topic=b"dets")
        self.last_pts_ns = None
        self.seq = 0
        self._roi_ok_printed = False
        self._roi_fail_count = 0


def _bbox_to_xywh(bbox, user_data):
    try:
        if hasattr(bbox, "xmin") and hasattr(bbox, "width"):
            x = float(bbox.xmin())
            y = float(bbox.ymin())
            w = float(bbox.width())
            h = float(bbox.height())
            return x, y, w, h

        if hasattr(bbox, "get_xmin") and hasattr(bbox, "get_width"):
            x = float(bbox.get_xmin())
            y = float(bbox.get_ymin())
            w = float(bbox.get_width())
            h = float(bbox.get_height())
            return x, y, w, h

        if not user_data._roi_ok_printed:
            user_data._roi_ok_printed = True
            print(
                "BBOX API unknown, methods:",
                [m for m in dir(bbox) if any(k in m for k in ("x", "y", "w", "h"))][:50],
                flush=True,
            )
    except Exception as e:
        if not user_data._roi_ok_printed:
            user_data._roi_ok_printed = True
            print(f"[bbox] extraction failed: {e!r}", flush=True)

    return None, None, None, None


def app_callback(pad, info, user_data: user_app_callback_class):
    user_data.increment()
    frame_id = user_data.get_count()

    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    pts_ns = int(buffer.pts)

    # One message per unique PTS
    if user_data.last_pts_ns == pts_ns:
        return Gst.PadProbeReturn.OK
    user_data.last_pts_ns = pts_ns

    user_data.seq += 1

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
                x, y, w, h = _bbox_to_xywh(bbox, user_data)
            else:
                x = y = w = h = None

            dets.append({"label": label, "score": score, "x": x, "y": y, "w": w, "h": h})

        if (not user_data._roi_ok_printed) and (len(dets) > 0):
            user_data._roi_ok_printed = True
            print(f"[roi] extraction OK, first frame with dets: frame_id={frame_id}, n={len(dets)}", flush=True)

    except Exception as e:
        user_data._roi_fail_count += 1
        if (not user_data._roi_ok_printed) or (user_data._roi_fail_count % 60 == 0):
            print(f"[roi] extraction failed: {e!r}", flush=True)
        dets = []

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


def _set_env_file():
    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    os.environ["HAILO_ENV_FILE"] = str(env_file)


def main():
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

    # stop the pipeline created in __init__ so we can rebuild cleanly
    try:
        app.pipeline.set_state(Gst.State.NULL)
    except Exception:
        pass

    # apply overrides BEFORE create_pipelineclear
    
    app.video_sink = video_sink
    app.show_fps = False
    app.batch_size = 1

    post_so = os.getenv("HAILO_POST_SO", "/usr/lib/aarch64-linux-gnu/post_processes/libyolo_hailortpp_post.so")
    app.post_process_so = post_so

    # optional: only if needed later
    # app.post_function_name = os.getenv("HAILO_POST_FUNC", app.post_function_name)

    app.create_pipeline()
    print(app.get_pipeline_string(), flush=True)
    app.run()

if __name__ == "__main__":
    main()
