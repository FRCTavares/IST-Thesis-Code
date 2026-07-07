"""Low-level appearance feature utilities for TIM-MARS.

This module is intentionally ROS-free. It provides bbox-to-crop conversion,
simple HSV appearance features, cosine similarity, and exponential feature
memory update helpers.

The helpers are generic building blocks. They do not own selected-target state,
tracker IDs, reacquisition rules, or controller-facing publication decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class AppearanceConfig:
    h_bins: int = 16
    s_bins: int = 8
    min_bbox_height: float = 30.0
    eps: float = 1e-8


def bbox_cxcywh_to_xyxy(
    cx: float,
    cy: float,
    w: float,
    h: float,
) -> tuple[float, float, float, float]:
    return (
        cx - 0.5 * w,
        cy - 0.5 * h,
        cx + 0.5 * w,
        cy + 0.5 * h,
    )


def clip_xyxy_bbox(
    bbox_xyxy: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox_xyxy

    x1_i = max(0, min(image_width - 1, int(round(x1))))
    y1_i = max(0, min(image_height - 1, int(round(y1))))
    x2_i = max(0, min(image_width, int(round(x2))))
    y2_i = max(0, min(image_height, int(round(y2))))

    if x2_i <= x1_i or y2_i <= y1_i:
        return None

    return x1_i, y1_i, x2_i, y2_i


def extract_crop(
    image_bgr: np.ndarray,
    bbox_xyxy: tuple[float, float, float, float],
    min_height: float = 30.0,
) -> np.ndarray | None:
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return None

    image_height, image_width = image_bgr.shape[:2]
    clipped = clip_xyxy_bbox(bbox_xyxy, image_width, image_height)

    if clipped is None:
        return None

    x1, y1, x2, y2 = clipped

    if (y2 - y1) < min_height:
        return None

    crop = image_bgr[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    return crop


def _normalise_vector(vec: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    vec = vec.astype(np.float32, copy=False)
    norm = float(np.linalg.norm(vec))

    if norm < eps:
        return np.zeros_like(vec, dtype=np.float32)

    return vec / norm


def _hsv_histogram(
    crop_bgr: np.ndarray,
    h_bins: int,
    s_bins: int,
    eps: float,
) -> np.ndarray:
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)

    hist = cv2.calcHist(
        [hsv],
        [0, 1],
        None,
        [h_bins, s_bins],
        [0, 180, 0, 256],
    )

    return _normalise_vector(hist.flatten(), eps=eps)


def extract_hsv_upper_lower_feature(
    image_bgr: np.ndarray,
    bbox_xyxy: tuple[float, float, float, float],
    config: AppearanceConfig | None = None,
) -> np.ndarray | None:
    cfg = config or AppearanceConfig()

    crop = extract_crop(
        image_bgr=image_bgr,
        bbox_xyxy=bbox_xyxy,
        min_height=cfg.min_bbox_height,
    )

    if crop is None:
        return None

    height = crop.shape[0]
    mid = max(1, height // 2)

    upper = crop[:mid, :]
    lower = crop[mid:, :]

    if upper.size == 0 or lower.size == 0:
        return None

    upper_hist = _hsv_histogram(upper, cfg.h_bins, cfg.s_bins, cfg.eps)
    lower_hist = _hsv_histogram(lower, cfg.h_bins, cfg.s_bins, cfg.eps)

    feature = np.concatenate([upper_hist, lower_hist]).astype(np.float32)

    return _normalise_vector(feature, eps=cfg.eps)


def cosine_similarity(
    a: np.ndarray | None,
    b: np.ndarray | None,
    eps: float = 1e-8,
) -> float:
    if a is None or b is None:
        return 0.0

    if a.shape != b.shape:
        return 0.0

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))

    if denom < eps:
        return 0.0

    return float(np.dot(a, b) / denom)


def update_feature_memory(
    memory: np.ndarray | None,
    candidate: np.ndarray | None,
    alpha: float = 0.10,
    eps: float = 1e-8,
) -> np.ndarray | None:
    if candidate is None:
        return memory

    alpha_clamped = max(0.0, min(1.0, float(alpha)))

    if memory is None:
        return _normalise_vector(candidate.copy(), eps=eps)

    if memory.shape != candidate.shape:
        return _normalise_vector(candidate.copy(), eps=eps)

    updated = (1.0 - alpha_clamped) * memory + alpha_clamped * candidate
    return _normalise_vector(updated.astype(np.float32), eps=eps)
