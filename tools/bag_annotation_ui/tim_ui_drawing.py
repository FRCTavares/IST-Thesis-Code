#!/usr/bin/env python3
"""Drawing and coordinate helpers for the TIM-MARS annotation UI.

This module is intentionally limited to pure image/box drawing utilities.
It should not import ROS, FastAPI, rosbag2, or access the UI cache.
"""

from __future__ import annotations

import math

import cv2


def xywh_to_xyxy(cx, cy, w, h):
    return (
        int(round(cx - w / 2)),
        int(round(cy - h / 2)),
        int(round(cx + w / 2)),
        int(round(cy + h / 2)),
    )


def model_box_to_image_box(box, img_shape, model_w=640.0, model_h=640.0):
    """Map 640x640 model-coordinate boxes into the displayed image frame.

    The UI displays decoded frames directly, so boxes are scaled independently
    in x/y from model coordinates to image coordinates.
    """
    img_h, img_w = img_shape[:2]
    if img_w <= 0 or img_h <= 0:
        return tuple(int(round(float(v))) for v in box)

    x1, y1, x2, y2 = [float(v) for v in box]

    sx = float(img_w) / float(model_w)
    sy = float(img_h) / float(model_h)

    ix1 = int(round(x1 * sx))
    iy1 = int(round(y1 * sy))
    ix2 = int(round(x2 * sx))
    iy2 = int(round(y2 * sy))

    ix1 = max(0, min(int(img_w) - 1, ix1))
    iy1 = max(0, min(int(img_h) - 1, iy1))
    ix2 = max(0, min(int(img_w) - 1, ix2))
    iy2 = max(0, min(int(img_h) - 1, iy2))

    return ix1, iy1, ix2, iy2


def draw_box(img, box, label, colour, thickness=2):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return

    # Draw a subtle dark outline first so coloured boxes remain visible
    # on bright court lines and shadows.
    cv2.rectangle(img, (x1, y1), (x2, y2), (10, 10, 10), thickness + 2)
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, thickness)

    if label:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.58
        label_th = 2
        (tw, th), base = cv2.getTextSize(label, font, scale, label_th)

        pad_x = 5
        pad_y = 4
        label_x1 = x1
        label_y2 = max(th + 2 * pad_y + 2, y1 - 4)
        label_y1 = max(0, label_y2 - th - 2 * pad_y)
        label_x2 = min(w - 1, label_x1 + tw + 2 * pad_x)

        # Filled dark label background.
        cv2.rectangle(img, (label_x1, label_y1), (label_x2, label_y2), (15, 15, 15), -1)
        cv2.rectangle(img, (label_x1, label_y1), (label_x2, label_y2), colour, 1)

        cv2.putText(
            img,
            label,
            (label_x1 + pad_x, label_y2 - pad_y),
            font,
            scale,
            colour,
            label_th,
            cv2.LINE_AA,
        )


def draw_model_box(img, box, label, colour, thickness=2):
    draw_box(
        img,
        model_box_to_image_box(box, img.shape),
        label,
        colour,
        thickness,
    )


def draw_dashed_box(img, box, colour, thickness=3, dash=14, gap=8):
    """Draw a dashed rectangle with no label."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return

    def dashed_line(p1, p2):
        x1_, y1_ = p1
        x2_, y2_ = p2
        length = int(math.hypot(x2_ - x1_, y2_ - y1_))
        if length <= 0:
            return
        dx = (x2_ - x1_) / length
        dy = (y2_ - y1_) / length
        step = dash + gap
        for start in range(0, length, step):
            end = min(start + dash, length)
            a = (int(round(x1_ + dx * start)), int(round(y1_ + dy * start)))
            b = (int(round(x1_ + dx * end)), int(round(y1_ + dy * end)))
            cv2.line(img, a, b, colour, thickness, cv2.LINE_AA)

    # Dark underlay for contrast.
    for tcol, tth in [((10, 10, 10), thickness + 2), (colour, thickness)]:
        old_colour = colour
        colour = tcol
        dashed_line((x1, y1), (x2, y1))
        dashed_line((x2, y1), (x2, y2))
        dashed_line((x2, y2), (x1, y2))
        dashed_line((x1, y2), (x1, y1))
        colour = old_colour


def draw_dashed_model_box(img, box, colour, thickness=3):
    draw_dashed_box(
        img,
        model_box_to_image_box(box, img.shape),
        colour,
        thickness=thickness,
    )



def draw_corner_box(
    img,
    box,
    colour,
    thickness=2,
    corner_ratio=0.28,
    shadow=True,
):
    """Draw a clean corner-bracket box.

    This is intended for the interactive/paper-style viewer overlay. It is less
    visually noisy than a full rectangle or dashed debug box.
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return

    bw = x2 - x1
    bh = y2 - y1
    corner = max(8, int(round(min(bw, bh) * corner_ratio)))
    corner = min(corner, max(8, bw // 2), max(8, bh // 2))

    def draw(col, th):
        # top-left
        cv2.line(img, (x1, y1), (x1 + corner, y1), col, th, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + corner), col, th, cv2.LINE_AA)

        # top-right
        cv2.line(img, (x2, y1), (x2 - corner, y1), col, th, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + corner), col, th, cv2.LINE_AA)

        # bottom-right
        cv2.line(img, (x2, y2), (x2 - corner, y2), col, th, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - corner), col, th, cv2.LINE_AA)

        # bottom-left
        cv2.line(img, (x1, y2), (x1 + corner, y2), col, th, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - corner), col, th, cv2.LINE_AA)

    if shadow:
        draw((10, 10, 10), thickness + 3)

    draw(colour, thickness)


def draw_model_corner_box(
    img,
    box,
    colour,
    thickness=2,
    corner_ratio=0.28,
    shadow=True,
):
    draw_corner_box(
        img,
        model_box_to_image_box(box, img.shape),
        colour,
        thickness=thickness,
        corner_ratio=corner_ratio,
        shadow=shadow,
    )
