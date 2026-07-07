"""Image preprocessing helpers for thesis perception inference.

This module contains resizing, padding, coordinate mapping, and preprocessing
utilities shared by camera/perception runtime nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np


@dataclass
class PreprocessFrameResult:
    image_width: int
    image_height: int
    image_encoding: str
    t_pre_start_ns: int
    t_pre_end_ns: int
    t_ros_to_np_start_ns: int
    t_ros_to_np_end_ns: int
    t_resize_start_ns: int
    t_resize_end_ns: int
    t_color_start_ns: int
    t_color_end_ns: int
    infer_img: np.ndarray
    numpy_owndata: bool


def preprocess_image_message(
    image_msg: Any,
    infer_w: int,
    infer_h: int,
    resize_buf: np.ndarray,
    rgb_buf: np.ndarray,
    now_ns: Callable[[], int],
    consumer_name: str,
    pre_start_ns: int | None = None,
) -> tuple[PreprocessFrameResult | None, str | None, str | None]:
    t_pre_start_ns = int(pre_start_ns) if pre_start_ns is not None else int(now_ns())
    t_ros_to_np_start_ns = t_pre_start_ns

    image_height = int(image_msg.height)
    image_width = int(image_msg.width)
    image_encoding = str(image_msg.encoding).lower()
    image_step = int(image_msg.step)

    if image_encoding not in ("rgb8", "bgr8"):
        return (
            None,
            "error",
            f"unsupported encoding '{image_msg.encoding}' in {consumer_name}; expected rgb8 or bgr8",
        )

    expected_step = image_width * 3
    if image_step != expected_step:
        return (
            None,
            "error",
            f"unsupported image step={image_step} (expected {expected_step} for packed 8UC3)",
        )

    expected_bytes = image_height * image_step
    if len(image_msg.data) != expected_bytes:
        return (
            None,
            "warning",
            f"image size mismatch: got={len(image_msg.data)} expected={expected_bytes}; dropping frame",
        )

    try:
        img = np.frombuffer(image_msg.data, dtype=np.uint8)
        img = img.reshape(image_height, image_width, 3)
    except Exception as exc:
        return None, "warning", f"ROS image to numpy conversion failed: {exc}"
    t_ros_to_np_end_ns = int(now_ns())

    t_resize_start_ns = int(now_ns())
    if image_width == infer_w and image_height == infer_h:
        infer_img = img
        t_resize_end_ns = t_resize_start_ns
    else:
        try:
            cv2.resize(
                img,
                (infer_w, infer_h),
                dst=resize_buf,
                interpolation=cv2.INTER_LINEAR,
            )
        except Exception as exc:
            return None, "warning", f"resize failed: {exc}"
        infer_img = resize_buf
        t_resize_end_ns = int(now_ns())

    t_color_start_ns = int(now_ns())
    if image_encoding == "bgr8":
        cv2.cvtColor(infer_img, cv2.COLOR_BGR2RGB, dst=rgb_buf)
        infer_img = rgb_buf
        t_color_end_ns = int(now_ns())
    else:
        t_color_end_ns = t_color_start_ns

    t_pre_end_ns = int(now_ns())

    return (
        PreprocessFrameResult(
            image_width=image_width,
            image_height=image_height,
            image_encoding=image_encoding,
            t_pre_start_ns=t_pre_start_ns,
            t_pre_end_ns=t_pre_end_ns,
            t_ros_to_np_start_ns=t_ros_to_np_start_ns,
            t_ros_to_np_end_ns=t_ros_to_np_end_ns,
            t_resize_start_ns=t_resize_start_ns,
            t_resize_end_ns=t_resize_end_ns,
            t_color_start_ns=t_color_start_ns,
            t_color_end_ns=t_color_end_ns,
            infer_img=infer_img,
            numpy_owndata=bool(img.flags["OWNDATA"]),
        ),
        None,
        None,
    )
