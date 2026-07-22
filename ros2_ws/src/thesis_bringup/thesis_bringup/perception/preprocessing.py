"""Image preprocessing helpers for thesis perception inference.

This module contains resizing, padding, coordinate mapping, and preprocessing
utilities shared by camera/perception runtime nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np


COORDINATE_TRANSFORM_CONTRACT = "tim_mars_source_pixels_resize_v1"


@dataclass(frozen=True)
class ImageTransform:
    """Describe the versioned direct-resize transform for one source image."""

    source_width: int
    source_height: int
    inference_width: int
    inference_height: int
    scale_x: float
    scale_y: float
    pad_x: float = 0.0
    pad_y: float = 0.0
    contract: str = COORDINATE_TRANSFORM_CONTRACT

    @classmethod
    def direct_resize(
        cls,
        source_width: int,
        source_height: int,
        inference_width: int,
        inference_height: int,
    ) -> "ImageTransform":
        """Build the canonical anisotropic direct-resize transform."""
        dimensions = (
            source_width,
            source_height,
            inference_width,
            inference_height,
        )
        if any(int(value) <= 0 for value in dimensions):
            raise ValueError(f"image dimensions must be positive: {dimensions}")

        return cls(
            source_width=int(source_width),
            source_height=int(source_height),
            inference_width=int(inference_width),
            inference_height=int(inference_height),
            scale_x=float(inference_width) / float(source_width),
            scale_y=float(inference_height) / float(source_height),
        )

    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        return min(max(float(value), lower), upper)

    def source_xyxy_to_inference(
        self,
        box: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        """Map and clip a source-pixel corner box into inference pixels."""
        x1, y1, x2, y2 = box
        return (
            self._clip(
                x1 * self.scale_x + self.pad_x,
                0.0,
                float(self.inference_width),
            ),
            self._clip(
                y1 * self.scale_y + self.pad_y,
                0.0,
                float(self.inference_height),
            ),
            self._clip(
                x2 * self.scale_x + self.pad_x,
                0.0,
                float(self.inference_width),
            ),
            self._clip(
                y2 * self.scale_y + self.pad_y,
                0.0,
                float(self.inference_height),
            ),
        )

    def inference_xyxy_to_source(
        self,
        box: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        """Map and clip an inference-pixel corner box into source pixels."""
        x1, y1, x2, y2 = box
        return (
            self._clip(
                (x1 - self.pad_x) / self.scale_x,
                0.0,
                float(self.source_width),
            ),
            self._clip(
                (y1 - self.pad_y) / self.scale_y,
                0.0,
                float(self.source_height),
            ),
            self._clip(
                (x2 - self.pad_x) / self.scale_x,
                0.0,
                float(self.source_width),
            ),
            self._clip(
                (y2 - self.pad_y) / self.scale_y,
                0.0,
                float(self.source_height),
            ),
        )

    def detection_frame_id(self, frame_id: int) -> str:
        """Encode contract metadata in the standard detection header frame."""
        return (
            f"{self.contract};frame={int(frame_id)};"
            f"source={self.source_width}x{self.source_height};"
            f"inference={self.inference_width}x{self.inference_height};"
            f"scale={self.scale_x:.9g},{self.scale_y:.9g};"
            f"pad={self.pad_x:.9g},{self.pad_y:.9g}"
        )


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
    transform: ImageTransform


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

    try:
        transform = ImageTransform.direct_resize(
            source_width=image_width,
            source_height=image_height,
            inference_width=infer_w,
            inference_height=infer_h,
        )
    except ValueError as exc:
        return None, "error", str(exc)

    if image_encoding not in ("rgb8", "bgr8"):
        return (
            None,
            "error",
            f"unsupported encoding '{image_msg.encoding}' in "
            f"{consumer_name}; expected rgb8 or bgr8",
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
            f"image size mismatch: got={len(image_msg.data)} "
            f"expected={expected_bytes}; dropping frame",
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
            transform=transform,
        ),
        None,
        None,
    )
