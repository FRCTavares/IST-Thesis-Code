"""Geometry scoring helpers for TIM-MARS.

This module is stateless and ROS-free. It computes bbox overlap, normalized
center distance, scale similarity, and the base geometric CandidateScore used by
the selected-target memory state machine.

Geometry remains the primary safety gate in TIM-MARS. Appearance evidence is
allowed only after geometry is plausible enough.
"""

from __future__ import annotations

from math import exp, log, sqrt
from typing import Optional, Tuple

from thesis_bringup.tim_mars.types import (
    BBox,
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def bbox_area(bbox: BBox) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0.0:
        return 0.0

    union = bbox_area(a) + bbox_area(b) - inter
    if union <= 0.0:
        return 0.0
    return clamp01(inter / union)


def bbox_centre(bbox: BBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return 0.5 * (x1 + x2), 0.5 * (y1 + y2)


def centre_distance_norm(a: BBox, b: BBox, image_width: float, image_height: float) -> float:
    ax, ay = bbox_centre(a)
    bx, by = bbox_centre(b)
    diag = sqrt(image_width * image_width + image_height * image_height)
    if diag <= 0:
        raise ValueError("image diagonal must be positive")
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2) / diag


def distance_similarity(distance_norm: float, sigma: float) -> float:
    if sigma <= 0:
        raise ValueError("distance sigma must be positive")
    return clamp01(exp(-0.5 * (distance_norm / sigma) ** 2))


def scale_similarity(a: BBox, b: BBox, sigma: float) -> float:
    """Return 1 for equal area, decaying with log-area ratio."""

    area_a = bbox_area(a)
    area_b = bbox_area(b)
    if area_a <= 1e-6 or area_b <= 1e-6:
        return 0.0
    if sigma <= 0:
        raise ValueError("scale sigma must be positive")
    ratio = area_b / area_a
    return clamp01(exp(-0.5 * (log(ratio) / sigma) ** 2))


def score_candidate(
    reference_bbox: BBox,
    candidate: CandidateTrack,
    current_track_id: Optional[int],
    cfg: TargetMemoryConfig,
) -> CandidateScore:
    """Score one candidate against the selected-target memory."""

    iou_score = bbox_iou(reference_bbox, candidate.bbox)
    dist = centre_distance_norm(reference_bbox, candidate.bbox, cfg.image_width, cfg.image_height)
    dist_score = distance_similarity(dist, cfg.distance_sigma)
    scale_score = scale_similarity(reference_bbox, candidate.bbox, cfg.scale_sigma)
    conf_score = clamp01(candidate.score)
    id_bonus = 1.0 if current_track_id is not None and candidate.track_id == current_track_id else 0.0

    total = (
        cfg.w_iou * iou_score
        + cfg.w_distance * dist_score
        + cfg.w_scale * scale_score
        + cfg.w_confidence * conf_score
        + cfg.w_id_bonus * id_bonus
    )

    return CandidateScore(
        track_id=candidate.track_id,
        total=clamp01(total),
        iou=iou_score,
        distance=dist_score,
        scale=scale_score,
        confidence=conf_score,
        id_bonus=id_bonus,
    )

__all__ = [
    "clamp01",
    "bbox_area",
    "bbox_iou",
    "bbox_centre",
    "centre_distance_norm",
    "distance_similarity",
    "scale_similarity",
    "score_candidate",
]
