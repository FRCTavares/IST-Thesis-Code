#!/usr/bin/env python3
"""Data containers shared by the perception pipeline workers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sensor_msgs.msg import Image
from thesis_bringup.perception.preprocessing import ImageTransform


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
    transform: ImageTransform


@dataclass
class RawFrame:
    seq: int
    frame_id: int
    src_stamp_ns: int
    stamp_sec: int
    stamp_nanosec: int
    t_cam_msg_seen_ns: int
    image_msg: Image
