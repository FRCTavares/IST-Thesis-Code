"""Pure crop-quality measurement for TIM-MARS appearance evidence."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Tuple

BBox = Tuple[float, float, float, float]


@dataclass(frozen=True)
class CropQualityThresholds:
    """Thresholds applied in appearance-image pixel coordinates."""

    min_width_px: float = 12.0
    min_height_px: float = 24.0
    max_clipping_fraction: float = 0.10
    min_aspect_ratio: float = 0.20
    max_aspect_ratio: float = 1.00
    max_overlap_iou_for_memory: float = 0.10
    min_centre_distance_norm_for_memory: float = 0.04


@dataclass(frozen=True)
class AppearanceCropQuality:
    """Measured quality of one candidate appearance crop."""

    crop_width_px: float
    crop_height_px: float
    clipping_fraction: float
    aspect_ratio: float
    max_iou_with_other: float
    min_centre_distance_norm: float
    encoding_eligible: bool
    memory_update_eligible: bool
    rejection_reasons: tuple[str, ...] = ()


def _bbox_area(bbox: BBox) -> float:
    return (
        max(0.0, float(bbox[2]) - float(bbox[0]))
        * max(0.0, float(bbox[3]) - float(bbox[1]))
    )


def _clip_bbox(
    bbox: BBox,
    *,
    image_width: int,
    image_height: int,
) -> BBox:
    return (
        max(0.0, min(float(image_width), float(bbox[0]))),
        max(0.0, min(float(image_height), float(bbox[1]))),
        max(0.0, min(float(image_width), float(bbox[2]))),
        max(0.0, min(float(image_height), float(bbox[3]))),
    )


def _bbox_iou(first: BBox, second: BBox) -> float:
    intersection = _bbox_area(
        (
            max(first[0], second[0]),
            max(first[1], second[1]),
            min(first[2], second[2]),
            min(first[3], second[3]),
        )
    )
    union = (
        _bbox_area(first)
        + _bbox_area(second)
        - intersection
    )

    if union <= 0.0:
        return 0.0

    return intersection / union


def measure_crop_qualities(
    mapped_boxes: list[BBox],
    *,
    image_width: int,
    image_height: int,
    thresholds: CropQualityThresholds,
) -> list[AppearanceCropQuality]:
    """Measure every mapped bbox before appearance encoding."""

    if image_width <= 0 or image_height <= 0:
        raise ValueError("appearance image dimensions must be positive")

    clipped_boxes = [
        _clip_bbox(
            bbox,
            image_width=image_width,
            image_height=image_height,
        )
        for bbox in mapped_boxes
    ]
    diagonal = hypot(
        float(image_width),
        float(image_height),
    )

    qualities: list[AppearanceCropQuality] = []

    for index, (mapped, clipped) in enumerate(
        zip(mapped_boxes, clipped_boxes)
    ):
        mapped_area = _bbox_area(mapped)
        clipped_area = _bbox_area(clipped)

        crop_width = max(
            0.0,
            float(clipped[2]) - float(clipped[0]),
        )
        crop_height = max(
            0.0,
            float(clipped[3]) - float(clipped[1]),
        )

        clipping_fraction = (
            1.0
            if mapped_area <= 0.0
            else max(
                0.0,
                min(
                    1.0,
                    1.0 - clipped_area / mapped_area,
                ),
            )
        )

        aspect_ratio = (
            crop_width / crop_height
            if crop_height > 0.0
            else float("inf")
        )

        max_iou = 0.0
        min_centre_distance = 1.0

        centre_x = 0.5 * (
            float(clipped[0]) + float(clipped[2])
        )
        centre_y = 0.5 * (
            float(clipped[1]) + float(clipped[3])
        )

        for other_index, other in enumerate(
            clipped_boxes
        ):
            if other_index == index:
                continue

            max_iou = max(
                max_iou,
                _bbox_iou(clipped, other),
            )

            other_x = 0.5 * (
                float(other[0]) + float(other[2])
            )
            other_y = 0.5 * (
                float(other[1]) + float(other[3])
            )

            min_centre_distance = min(
                min_centre_distance,
                hypot(
                    centre_x - other_x,
                    centre_y - other_y,
                )
                / diagonal,
            )

        encoding_reasons: list[str] = []

        if crop_width < max(
            0.0,
            float(thresholds.min_width_px),
        ):
            encoding_reasons.append("crop_too_narrow")

        if crop_height < max(
            0.0,
            float(thresholds.min_height_px),
        ):
            encoding_reasons.append("crop_too_short")

        if clipping_fraction > max(
            0.0,
            float(thresholds.max_clipping_fraction),
        ):
            encoding_reasons.append("crop_too_clipped")

        if aspect_ratio < max(
            0.0,
            float(thresholds.min_aspect_ratio),
        ):
            encoding_reasons.append(
                "aspect_ratio_too_narrow"
            )

        if aspect_ratio > max(
            0.0,
            float(thresholds.max_aspect_ratio),
        ):
            encoding_reasons.append(
                "aspect_ratio_too_wide"
            )

        memory_reasons = list(encoding_reasons)

        if max_iou >= max(
            0.0,
            float(
                thresholds.max_overlap_iou_for_memory
            ),
        ):
            memory_reasons.append(
                "overlap_with_person"
            )

        if min_centre_distance <= max(
            0.0,
            float(
                thresholds
                .min_centre_distance_norm_for_memory
            ),
        ):
            memory_reasons.append(
                "group_centre_too_close"
            )

        qualities.append(
            AppearanceCropQuality(
                crop_width_px=crop_width,
                crop_height_px=crop_height,
                clipping_fraction=clipping_fraction,
                aspect_ratio=aspect_ratio,
                max_iou_with_other=max_iou,
                min_centre_distance_norm=(
                    min_centre_distance
                ),
                encoding_eligible=(
                    not encoding_reasons
                ),
                memory_update_eligible=(
                    not memory_reasons
                ),
                rejection_reasons=tuple(
                    memory_reasons
                ),
            )
        )

    return qualities


__all__ = [
    "AppearanceCropQuality",
    "CropQualityThresholds",
    "measure_crop_qualities",
]
