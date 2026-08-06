#!/usr/bin/env python3
"""Dataset-neutral external pedestrian-tracking annotations.

This module normalizes MOTChallenge-compatible and VisDrone-MOT rows into one
auditable source-image coordinate model. It does not run a detector, tracker,
TIM-MARS, or selected-target evaluation.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


BBoxXYXY = tuple[float, float, float, float]

VISDRONE_CLASS_NAMES = {
    0: "ignored-region",
    1: "pedestrian",
    2: "people",
    3: "bicycle",
    4: "car",
    5: "van",
    6: "truck",
    7: "tricycle",
    8: "awning-tricycle",
    9: "bus",
    10: "motor",
    11: "others",
}

VISDRONE_PERSON_CLASS_IDS = frozenset({1, 2})


@dataclass(frozen=True)
class SequenceGeometry:
    """Image, frame, and time contract for one source sequence."""

    image_width: int
    image_height: int
    frame_rate: float
    source_index_base: int

    def __post_init__(self) -> None:
        if self.image_width <= 0:
            raise ValueError("image_width must be positive")
        if self.image_height <= 0:
            raise ValueError("image_height must be positive")
        if not math.isfinite(self.frame_rate) or self.frame_rate <= 0.0:
            raise ValueError("frame_rate must be finite and positive")
        if self.source_index_base not in (0, 1):
            raise ValueError("source_index_base must be 0 or 1")


@dataclass(frozen=True)
class ExternalObjectAnnotation:
    """One normalized source annotation with retained provenance."""

    dataset: str
    sequence_name: str
    split: str
    source_path: str
    source_line_number: int
    source_row: str
    source_frame_number: int
    normalized_frame_index: int
    timestamp_s: float
    image_width: int
    image_height: int
    frame_rate: float
    source_index_base: int
    identity: int
    bbox_xyxy: BBoxXYXY
    source_bbox_xywh: tuple[float, float, float, float]
    source_score: Optional[float]
    class_id: Optional[int]
    class_name: str
    visibility: Optional[float]
    truncation: Optional[int]
    occlusion: Optional[int]
    ignored_region: bool
    include_as_person_candidate: bool
    exclusion_reason: Optional[str]

    @property
    def width(self) -> float:
        return self.bbox_xyxy[2] - self.bbox_xyxy[0]

    @property
    def height(self) -> float:
        return self.bbox_xyxy[3] - self.bbox_xyxy[1]


def _finite_float(
    value: str,
    *,
    path: Path,
    line_number: int,
    field_name: str,
) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(
            f"{path}:{line_number}: invalid {field_name}: {value!r}"
        ) from exc

    if not math.isfinite(parsed):
        raise ValueError(
            f"{path}:{line_number}: non-finite {field_name}: {value!r}"
        )

    return parsed


def _integer_value(
    value: str,
    *,
    path: Path,
    line_number: int,
    field_name: str,
) -> int:
    parsed = _finite_float(
        value,
        path=path,
        line_number=line_number,
        field_name=field_name,
    )

    if not parsed.is_integer():
        raise ValueError(
            f"{path}:{line_number}: {field_name} must be integral: "
            f"{value!r}"
        )

    return int(parsed)


def normalize_frame_number(
    source_frame_number: int,
    source_index_base: int,
) -> int:
    """Convert source numbering to a zero-based frame index."""
    if source_index_base not in (0, 1):
        raise ValueError("source_index_base must be 0 or 1")

    normalized = source_frame_number - source_index_base

    if normalized < 0:
        raise ValueError(
            "source frame precedes the declared index base: "
            f"{source_frame_number} with base {source_index_base}"
        )

    return normalized


def timestamp_for_frame(
    normalized_frame_index: int,
    frame_rate: float,
) -> float:
    """Derive deterministic sequence-relative frame time."""
    if normalized_frame_index < 0:
        raise ValueError("normalized_frame_index must be non-negative")
    if not math.isfinite(frame_rate) or frame_rate <= 0.0:
        raise ValueError("frame_rate must be finite and positive")

    return normalized_frame_index / frame_rate


def clip_xyxy(
    bbox: BBoxXYXY,
    *,
    image_width: int,
    image_height: int,
) -> BBoxXYXY:
    """Clip geometric bbox edges to [0,width] and [0,height]."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")

    x1, y1, x2, y2 = bbox

    if not all(math.isfinite(value) for value in bbox):
        raise ValueError("bbox coordinates must be finite")

    return (
        min(float(image_width), max(0.0, x1)),
        min(float(image_height), max(0.0, y1)),
        min(float(image_width), max(0.0, x2)),
        min(float(image_height), max(0.0, y2)),
    )


def xywh_to_clipped_xyxy(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    image_width: int,
    image_height: int,
) -> BBoxXYXY:
    """Convert top-left xywh into clipped geometric-edge xyxy."""
    values = (x, y, width, height)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("bbox values must be finite")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("bbox width and height must be positive")

    clipped = clip_xyxy(
        (x, y, x + width, y + height),
        image_width=image_width,
        image_height=image_height,
    )

    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        raise ValueError("bbox is empty after source-image clipping")

    return clipped


def _nonempty_rows(path: Path) -> Iterable[tuple[int, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            row = raw_line.strip()
            if row:
                yield line_number, row


def _sort_and_validate_unique(
    rows: list[ExternalObjectAnnotation],
) -> list[ExternalObjectAnnotation]:
    ordered = sorted(
        rows,
        key=lambda item: (
            item.normalized_frame_index,
            item.identity,
            item.source_line_number,
        ),
    )

    seen: set[tuple[int, int]] = set()

    for row in ordered:
        key = (
            row.normalized_frame_index,
            row.identity,
        )
        if key in seen:
            raise ValueError(
                "duplicate normalized frame-identity annotation: "
                f"frame={row.normalized_frame_index} "
                f"identity={row.identity}"
            )
        seen.add(key)

    return ordered


def parse_motchallenge_annotations(
    path: Path,
    *,
    dataset: str,
    sequence_name: str,
    split: str,
    geometry: SequenceGeometry,
    person_class_ids: Optional[set[int]] = None,
) -> list[ExternalObjectAnnotation]:
    """Parse MOTChallenge-style rows without silently discarding metadata.

    Supported columns are:
    frame, id, left, top, width, height, confidence, class, visibility

    Additional columns are permitted and retained through source_row.
    """

    rows: list[ExternalObjectAnnotation] = []

    for line_number, source_row in _nonempty_rows(path):
        parts = next(csv.reader([source_row]))

        if len(parts) < 6:
            raise ValueError(
                f"{path}:{line_number}: expected at least 6 columns, "
                f"got {len(parts)}"
            )

        source_frame = _integer_value(
            parts[0],
            path=path,
            line_number=line_number,
            field_name="frame",
        )
        identity = _integer_value(
            parts[1],
            path=path,
            line_number=line_number,
            field_name="identity",
        )
        x = _finite_float(
            parts[2],
            path=path,
            line_number=line_number,
            field_name="bbox_left",
        )
        y = _finite_float(
            parts[3],
            path=path,
            line_number=line_number,
            field_name="bbox_top",
        )
        width = _finite_float(
            parts[4],
            path=path,
            line_number=line_number,
            field_name="bbox_width",
        )
        height = _finite_float(
            parts[5],
            path=path,
            line_number=line_number,
            field_name="bbox_height",
        )

        confidence = (
            _finite_float(
                parts[6],
                path=path,
                line_number=line_number,
                field_name="confidence",
            )
            if len(parts) >= 7 and parts[6].strip()
            else None
        )
        class_id = (
            _integer_value(
                parts[7],
                path=path,
                line_number=line_number,
                field_name="class_id",
            )
            if len(parts) >= 8 and parts[7].strip()
            else None
        )
        visibility = (
            _finite_float(
                parts[8],
                path=path,
                line_number=line_number,
                field_name="visibility",
            )
            if len(parts) >= 9 and parts[8].strip()
            else None
        )

        normalized_frame = normalize_frame_number(
            source_frame,
            geometry.source_index_base,
        )
        bbox = xywh_to_clipped_xyxy(
            x,
            y,
            width,
            height,
            image_width=geometry.image_width,
            image_height=geometry.image_height,
        )

        exclusion_reason: Optional[str] = None
        if identity <= 0:
            exclusion_reason = "non_positive_identity"
        elif confidence is not None and confidence <= 0.0:
            exclusion_reason = "non_positive_confidence"
        elif (
            person_class_ids is not None
            and class_id not in person_class_ids
        ):
            exclusion_reason = "non_person_class"

        rows.append(
            ExternalObjectAnnotation(
                dataset=dataset,
                sequence_name=sequence_name,
                split=split,
                source_path=path.as_posix(),
                source_line_number=line_number,
                source_row=source_row,
                source_frame_number=source_frame,
                normalized_frame_index=normalized_frame,
                timestamp_s=timestamp_for_frame(
                    normalized_frame,
                    geometry.frame_rate,
                ),
                image_width=geometry.image_width,
                image_height=geometry.image_height,
                frame_rate=geometry.frame_rate,
                source_index_base=geometry.source_index_base,
                identity=identity,
                bbox_xyxy=bbox,
                source_bbox_xywh=(x, y, width, height),
                source_score=confidence,
                class_id=class_id,
                class_name=(
                    "person"
                    if class_id is None
                    else f"class_{class_id}"
                ),
                visibility=visibility,
                truncation=None,
                occlusion=None,
                ignored_region=False,
                include_as_person_candidate=(
                    exclusion_reason is None
                ),
                exclusion_reason=exclusion_reason,
            )
        )

    return _sort_and_validate_unique(rows)


def parse_visdrone_annotations(
    path: Path,
    *,
    sequence_name: str,
    split: str,
    geometry: SequenceGeometry,
) -> list[ExternalObjectAnnotation]:
    """Parse VisDrone-MOT rows while preserving class and ignore semantics."""

    rows: list[ExternalObjectAnnotation] = []

    for line_number, source_row in _nonempty_rows(path):
        parts = next(csv.reader([source_row]))

        if len(parts) < 10:
            raise ValueError(
                f"{path}:{line_number}: expected at least 10 columns, "
                f"got {len(parts)}"
            )

        source_frame = _integer_value(
            parts[0],
            path=path,
            line_number=line_number,
            field_name="frame",
        )
        identity = _integer_value(
            parts[1],
            path=path,
            line_number=line_number,
            field_name="identity",
        )
        x = _finite_float(
            parts[2],
            path=path,
            line_number=line_number,
            field_name="bbox_left",
        )
        y = _finite_float(
            parts[3],
            path=path,
            line_number=line_number,
            field_name="bbox_top",
        )
        width = _finite_float(
            parts[4],
            path=path,
            line_number=line_number,
            field_name="bbox_width",
        )
        height = _finite_float(
            parts[5],
            path=path,
            line_number=line_number,
            field_name="bbox_height",
        )
        score = _finite_float(
            parts[6],
            path=path,
            line_number=line_number,
            field_name="score",
        )
        class_id = _integer_value(
            parts[7],
            path=path,
            line_number=line_number,
            field_name="class_id",
        )
        truncation = _integer_value(
            parts[8],
            path=path,
            line_number=line_number,
            field_name="truncation",
        )
        occlusion = _integer_value(
            parts[9],
            path=path,
            line_number=line_number,
            field_name="occlusion",
        )

        normalized_frame = normalize_frame_number(
            source_frame,
            geometry.source_index_base,
        )
        bbox = xywh_to_clipped_xyxy(
            x,
            y,
            width,
            height,
            image_width=geometry.image_width,
            image_height=geometry.image_height,
        )

        ignored_region = class_id == 0
        exclusion_reason: Optional[str] = None

        if ignored_region:
            exclusion_reason = "ignored_region"
        elif class_id not in VISDRONE_PERSON_CLASS_IDS:
            exclusion_reason = "non_person_class"
        elif identity <= 0:
            exclusion_reason = "non_positive_identity"
        elif score <= 0.0:
            exclusion_reason = "non_positive_score"

        rows.append(
            ExternalObjectAnnotation(
                dataset="visdrone_mot",
                sequence_name=sequence_name,
                split=split,
                source_path=path.as_posix(),
                source_line_number=line_number,
                source_row=source_row,
                source_frame_number=source_frame,
                normalized_frame_index=normalized_frame,
                timestamp_s=timestamp_for_frame(
                    normalized_frame,
                    geometry.frame_rate,
                ),
                image_width=geometry.image_width,
                image_height=geometry.image_height,
                frame_rate=geometry.frame_rate,
                source_index_base=geometry.source_index_base,
                identity=identity,
                bbox_xyxy=bbox,
                source_bbox_xywh=(x, y, width, height),
                source_score=score,
                class_id=class_id,
                class_name=VISDRONE_CLASS_NAMES.get(
                    class_id,
                    f"unknown_{class_id}",
                ),
                visibility=None,
                truncation=truncation,
                occlusion=occlusion,
                ignored_region=ignored_region,
                include_as_person_candidate=(
                    exclusion_reason is None
                ),
                exclusion_reason=exclusion_reason,
            )
        )

    return _sort_and_validate_unique(rows)
