#!/usr/bin/env python3
"""Schema, deterministic parsing, validation, and the Stage A identity rule
for the physical-reference bbox annotation contract
``tim_physical_target_bbox_v1``.

Full semantics are frozen in
``docs/issues/p1-10-improve-bbox-evaluation.md`` (sections C-N). This
module owns the data shapes, deterministic load/validate/serialize
behaviour, and the pure Stage A identity classifier (section J) that a
later evaluator-refactor milestone will call while reading real bags. It
does not itself read bags, accumulate durations, or produce reports.

The core scientific point this schema and classifier exist to enforce:
the reference identity of the selected physical person is independent of
any tracker ID (``classify_identity_stage_a`` below has no tracker-ID
parameter at all), and genuinely ambiguous instants (a nearby distractor,
a crossing) are represented explicitly (``present_ambiguous`` plus
optional distractor boxes) rather than left for a bare IoU threshold to
silently resolve. A high IoU against the target reference is correct only
when it also beats every recorded distractor; ties or a distractor match
are never "correct".
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from external_target_initialization import BBoxXYXY, bbox_iou  # noqa: E402,F401


SCHEMA_VERSION = 1
CONTRACT_VERSION = "tim_physical_target_bbox_v1"

STATE_PRESENT_SCORED = "present_scored"
STATE_PRESENT_AMBIGUOUS = "present_ambiguous"
STATE_PRESENT_REFERENCE_UNAVAILABLE = "present_reference_unavailable"
STATE_ABSENT = "absent"

ALL_STATES = frozenset(
    {
        STATE_PRESENT_SCORED,
        STATE_PRESENT_AMBIGUOUS,
        STATE_PRESENT_REFERENCE_UNAVAILABLE,
        STATE_ABSENT,
    }
)

# States where a target_bbox_xyxy is mandatory vs. forbidden.
STATES_REQUIRING_BBOX = frozenset({STATE_PRESENT_SCORED, STATE_PRESENT_AMBIGUOUS})
STATES_FORBIDDING_BBOX = frozenset(
    {STATE_PRESENT_REFERENCE_UNAVAILABLE, STATE_ABSENT}
)

# Only these two states are interpolation endpoints (section I).
INTERPOLATION_ELIGIBLE_STATE = STATE_PRESENT_SCORED

COORDINATE_CONVENTIONS = frozenset(
    {
        "source_pixels_p53_contract",
        "source_pixels_historical_pre_p53",
    }
)

REQUIRED_PROVENANCE_FIELDS = (
    "schema_version",
    "contract_version",
    "sequence_id",
    "source_bag_name",
    "source_bag_path",
    "source_image_topic",
    "source_width",
    "source_height",
    "coordinate_convention",
    "selected_physical_target_label",
    "annotator",
    "created_date",
)

REQUIRED_SAMPLE_FIELDS = (
    "t_s",
    "identity_state",
    "target_bbox_xyxy",
    "distractor_bboxes_xyxy",
    "interpolate_from_previous",
)


@dataclass(frozen=True)
class PhysicalReferenceProvenance:
    schema_version: int
    contract_version: str
    sequence_id: str
    source_bag_name: str
    source_bag_path: str
    source_image_topic: str
    source_width: int
    source_height: int
    coordinate_convention: str
    selected_physical_target_label: str
    annotator: str
    created_date: str
    coordinate_convention_evidence: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class PhysicalReferenceSample:
    t_s: float
    identity_state: str
    target_bbox_xyxy: BBoxXYXY | None
    distractor_bboxes_xyxy: tuple[BBoxXYXY, ...] = field(default_factory=tuple)
    interpolate_from_previous: bool = False
    notes: str = ""


@dataclass(frozen=True)
class PhysicalReferenceArtifact:
    provenance: PhysicalReferenceProvenance
    samples: tuple[PhysicalReferenceSample, ...]


class PhysicalReferenceValidationError(ValueError):
    """Raised for any structural or semantic violation of the v1 contract."""


def _require_finite(value: Any, label: str) -> float:
    try:
        as_float = float(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalReferenceValidationError(f"{label} must be numeric") from exc
    if not math.isfinite(as_float):
        raise PhysicalReferenceValidationError(f"{label} must be finite")
    return as_float


def _parse_bbox(raw: Any, label: str) -> BBoxXYXY:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise PhysicalReferenceValidationError(
            f"{label} must be a 4-element [x1, y1, x2, y2] array"
        )
    x1, y1, x2, y2 = (
        _require_finite(raw[0], f"{label}.x1"),
        _require_finite(raw[1], f"{label}.y1"),
        _require_finite(raw[2], f"{label}.x2"),
        _require_finite(raw[3], f"{label}.y2"),
    )
    return (x1, y1, x2, y2)


def _validate_bbox_bounds(
    box: BBoxXYXY, label: str, source_width: int, source_height: int
) -> None:
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        raise PhysicalReferenceValidationError(
            f"{label} has non-positive area: {box}"
        )
    if x1 < 0.0 or y1 < 0.0 or x2 > source_width or y2 > source_height:
        raise PhysicalReferenceValidationError(
            f"{label} is outside the declared source frame "
            f"({source_width}x{source_height}): {box}"
        )


def _looks_like_bare_tracker_id(label: str) -> bool:
    stripped = label.strip()
    if not stripped:
        return False
    return stripped.isdigit()


def parse_provenance(data: dict) -> PhysicalReferenceProvenance:
    missing = [f for f in REQUIRED_PROVENANCE_FIELDS if f not in data]
    if missing:
        raise PhysicalReferenceValidationError(
            f"provenance is missing required fields: {sorted(missing)}"
        )

    schema_version = data["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise PhysicalReferenceValidationError(
            f"unsupported schema_version {schema_version!r}; "
            f"expected {SCHEMA_VERSION}"
        )

    contract_version = str(data["contract_version"])
    if contract_version != CONTRACT_VERSION:
        raise PhysicalReferenceValidationError(
            f"unsupported contract_version {contract_version!r}; "
            f"expected {CONTRACT_VERSION!r}"
        )

    coordinate_convention = str(data["coordinate_convention"])
    if coordinate_convention not in COORDINATE_CONVENTIONS:
        raise PhysicalReferenceValidationError(
            f"invalid coordinate_convention {coordinate_convention!r}; "
            f"expected one of {sorted(COORDINATE_CONVENTIONS)}"
        )

    coordinate_convention_evidence = data.get("coordinate_convention_evidence")
    if coordinate_convention == "source_pixels_historical_pre_p53" and not (
        coordinate_convention_evidence and str(coordinate_convention_evidence).strip()
    ):
        raise PhysicalReferenceValidationError(
            "coordinate_convention_evidence is required and must be non-empty "
            "when coordinate_convention is source_pixels_historical_pre_p53"
        )

    source_width = int(data["source_width"])
    source_height = int(data["source_height"])
    if source_width <= 0 or source_height <= 0:
        raise PhysicalReferenceValidationError(
            "source_width and source_height must be positive integers"
        )

    selected_physical_target_label = str(data["selected_physical_target_label"])
    if not selected_physical_target_label.strip():
        raise PhysicalReferenceValidationError(
            "selected_physical_target_label must be non-empty"
        )
    if _looks_like_bare_tracker_id(selected_physical_target_label):
        raise PhysicalReferenceValidationError(
            "selected_physical_target_label "
            f"{selected_physical_target_label!r} looks like a bare tracker "
            "ID; the physical identity field must never be a tracker ID"
        )

    return PhysicalReferenceProvenance(
        schema_version=schema_version,
        contract_version=contract_version,
        sequence_id=str(data["sequence_id"]),
        source_bag_name=str(data["source_bag_name"]),
        source_bag_path=str(data["source_bag_path"]),
        source_image_topic=str(data["source_image_topic"]),
        source_width=source_width,
        source_height=source_height,
        coordinate_convention=coordinate_convention,
        coordinate_convention_evidence=(
            str(coordinate_convention_evidence)
            if coordinate_convention_evidence is not None
            else None
        ),
        selected_physical_target_label=selected_physical_target_label,
        annotator=str(data["annotator"]),
        created_date=str(data["created_date"]),
        notes=str(data.get("notes", "")),
    )


def parse_sample(data: dict, index: int) -> PhysicalReferenceSample:
    missing = [f for f in REQUIRED_SAMPLE_FIELDS if f not in data]
    if missing:
        raise PhysicalReferenceValidationError(
            f"sample[{index}] is missing required fields: {sorted(missing)}"
        )

    t_s = _require_finite(data["t_s"], f"sample[{index}].t_s")
    if t_s < 0.0:
        raise PhysicalReferenceValidationError(
            f"sample[{index}].t_s must be non-negative, got {t_s}"
        )

    identity_state = str(data["identity_state"])
    if identity_state not in ALL_STATES:
        raise PhysicalReferenceValidationError(
            f"sample[{index}].identity_state {identity_state!r} is invalid; "
            f"expected one of {sorted(ALL_STATES)}"
        )

    raw_bbox = data["target_bbox_xyxy"]
    raw_distractors = data["distractor_bboxes_xyxy"]

    if identity_state in STATES_REQUIRING_BBOX and raw_bbox is None:
        raise PhysicalReferenceValidationError(
            f"sample[{index}] state {identity_state!r} requires target_bbox_xyxy"
        )
    if identity_state in STATES_FORBIDDING_BBOX:
        if raw_bbox is not None:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] state {identity_state!r} must not carry "
                "target_bbox_xyxy"
            )
        if raw_distractors:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] state {identity_state!r} must not carry "
                "distractor_bboxes_xyxy"
            )

    target_bbox = (
        _parse_bbox(raw_bbox, f"sample[{index}].target_bbox_xyxy")
        if raw_bbox is not None
        else None
    )
    distractor_boxes = tuple(
        _parse_bbox(d, f"sample[{index}].distractor_bboxes_xyxy[{j}]")
        for j, d in enumerate(raw_distractors or [])
    )

    interpolate_from_previous = bool(data["interpolate_from_previous"])

    return PhysicalReferenceSample(
        t_s=t_s,
        identity_state=identity_state,
        target_bbox_xyxy=target_bbox,
        distractor_bboxes_xyxy=distractor_boxes,
        interpolate_from_previous=interpolate_from_previous,
        notes=str(data.get("notes", "")),
    )


def parse_physical_reference(data: dict) -> PhysicalReferenceArtifact:
    if "provenance" not in data or "samples" not in data:
        raise PhysicalReferenceValidationError(
            "artifact must contain top-level 'provenance' and 'samples' keys"
        )

    provenance = parse_provenance(data["provenance"])

    raw_samples = data["samples"]
    if not isinstance(raw_samples, list) or not raw_samples:
        raise PhysicalReferenceValidationError("samples must be a non-empty list")

    samples = tuple(
        parse_sample(raw, index) for index, raw in enumerate(raw_samples)
    )

    return PhysicalReferenceArtifact(provenance=provenance, samples=samples)


def validate_physical_reference(artifact: PhysicalReferenceArtifact) -> None:
    """Semantic validation beyond per-field parsing: bounds, monotonicity,
    and interpolation legality across the sample sequence."""

    provenance = artifact.provenance
    previous_t_s: float | None = None
    previous_state: str | None = None

    for index, sample in enumerate(artifact.samples):
        if previous_t_s is not None and sample.t_s <= previous_t_s:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].t_s={sample.t_s} is not strictly greater "
                f"than the previous sample's t_s={previous_t_s}"
            )

        if sample.target_bbox_xyxy is not None:
            _validate_bbox_bounds(
                sample.target_bbox_xyxy,
                f"sample[{index}].target_bbox_xyxy",
                provenance.source_width,
                provenance.source_height,
            )
        for j, distractor in enumerate(sample.distractor_bboxes_xyxy):
            _validate_bbox_bounds(
                distractor,
                f"sample[{index}].distractor_bboxes_xyxy[{j}]",
                provenance.source_width,
                provenance.source_height,
            )

        if sample.interpolate_from_previous:
            if index == 0:
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] cannot set interpolate_from_previous=true; "
                    "it has no predecessor"
                )
            if (
                previous_state != INTERPOLATION_ELIGIBLE_STATE
                or sample.identity_state != INTERPOLATION_ELIGIBLE_STATE
            ):
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] sets interpolate_from_previous=true but "
                    f"the endpoint states are "
                    f"({previous_state!r}, {sample.identity_state!r}); both "
                    f"must be {INTERPOLATION_ELIGIBLE_STATE!r}"
                )

        previous_t_s = sample.t_s
        previous_state = sample.identity_state


def load_physical_reference(path: Path) -> PhysicalReferenceArtifact:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    artifact = parse_physical_reference(data)
    validate_physical_reference(artifact)
    return artifact


def serialize_physical_reference(artifact: PhysicalReferenceArtifact) -> dict:
    """Deterministic dict form: stable key order via json.dumps(sort_keys=True)
    at write time; stable value shapes (tuples -> lists) here."""

    provenance = artifact.provenance
    return {
        "provenance": {
            "schema_version": provenance.schema_version,
            "contract_version": provenance.contract_version,
            "sequence_id": provenance.sequence_id,
            "source_bag_name": provenance.source_bag_name,
            "source_bag_path": provenance.source_bag_path,
            "source_image_topic": provenance.source_image_topic,
            "source_width": provenance.source_width,
            "source_height": provenance.source_height,
            "coordinate_convention": provenance.coordinate_convention,
            "coordinate_convention_evidence": provenance.coordinate_convention_evidence,
            "selected_physical_target_label": provenance.selected_physical_target_label,
            "annotator": provenance.annotator,
            "created_date": provenance.created_date,
            "notes": provenance.notes,
        },
        "samples": [
            {
                "t_s": sample.t_s,
                "identity_state": sample.identity_state,
                "target_bbox_xyxy": (
                    list(sample.target_bbox_xyxy)
                    if sample.target_bbox_xyxy is not None
                    else None
                ),
                "distractor_bboxes_xyxy": [
                    list(box) for box in sample.distractor_bboxes_xyxy
                ],
                "interpolate_from_previous": sample.interpolate_from_previous,
                "notes": sample.notes,
            }
            for sample in artifact.samples
        ],
    }


def write_physical_reference(path: Path, artifact: PhysicalReferenceArtifact) -> None:
    payload = serialize_physical_reference(artifact)
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# --- Stage A identity classification (section J) ---------------------------
#
# Deliberately the only scoring logic this milestone implements: a pure
# function with no bag I/O, no duration accounting, and critically no
# tracker-ID parameter. It assumes the caller already established that a
# target_bbox_xyxy exists for this sample (identity_state is
# present_scored, or present_ambiguous with at least one distractor
# recorded); the caller is responsible for routing present_ambiguous
# samples with zero distractors straight to IDENTITY_UNSCORED without
# calling this function at all, and for routing present_reference_unavailable
# / absent samples elsewhere entirely (section J steps 1-2).

IDENTITY_CORRECT = "identity_correct"
IDENTITY_WRONG = "identity_wrong"
IDENTITY_UNMATCHED = "identity_unmatched"
IDENTITY_UNSCORED = "identity_unscored"

DEFAULT_IDENTITY_IOU_THRESHOLD = 0.5


def classify_identity_stage_a(
    *,
    target_bbox_xyxy: BBoxXYXY,
    distractor_bboxes_xyxy: Sequence[BBoxXYXY],
    output_bbox_xyxy: BBoxXYXY,
    identity_iou_threshold: float = DEFAULT_IDENTITY_IOU_THRESHOLD,
) -> str:
    """Section J, steps 3-4: identity-correct iff the output matches the
    target reference AND (when distractors are recorded) beats every one
    of them -- never merely "IoU with the target is high"."""

    target_iou = bbox_iou(output_bbox_xyxy, target_bbox_xyxy)

    if not distractor_bboxes_xyxy:
        return (
            IDENTITY_CORRECT
            if target_iou >= identity_iou_threshold
            else IDENTITY_WRONG
        )

    best_distractor_iou = max(
        bbox_iou(output_bbox_xyxy, distractor)
        for distractor in distractor_bboxes_xyxy
    )
    target_passes = target_iou >= identity_iou_threshold
    target_beats_best_distractor = target_iou > best_distractor_iou

    if target_passes and target_beats_best_distractor:
        return IDENTITY_CORRECT
    if target_passes or best_distractor_iou >= identity_iou_threshold:
        # Either the target passed but a distractor matched at least as
        # well (tie goes to "cannot trust it"), or the target failed while
        # some distractor clearly matched the output instead.
        return IDENTITY_WRONG
    return IDENTITY_UNMATCHED
