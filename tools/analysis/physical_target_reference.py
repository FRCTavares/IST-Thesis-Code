#!/usr/bin/env python3
"""Schema, deterministic parsing, validation, and the Stage A identity
attribution rule for the physical-reference bbox annotation contract
``tim_physical_target_bbox_v1``.

Full semantics are frozen in
``docs/issues/p1-10-improve-bbox-evaluation.md`` (sections C-N). This
module owns the data shapes, deterministic load/validate/serialize
behaviour, and the pure Stage A identity-attribution function (section J)
that a later evaluator-refactor milestone will call while reading real
bags. It does not itself read bags, accumulate durations, or produce
reports.

Two things this schema and classifier exist to enforce, corrected after
review of the first version of this module:

1. The reference identity of the selected physical person is independent
   of any tracker ID -- ``classify_identity_stage_a`` below has no
   tracker-ID parameter at all.
2. Stage A physical-identity attribution (WHO does this output belong to)
   is answered *without* imposing any minimum localisation-quality
   threshold. ``classify_identity_stage_a`` has no IoU-threshold
   parameter: identity is either contextually certain (no plausible
   competing physical person, section G's ``target_only``) or resolved by
   *relative* comparison against explicitly recorded competing references
   (``distractors_complete``), never by asking whether the target overlap
   alone clears some bar. A controller-facing output that genuinely
   belongs to the selected person but is badly localised must remain
   ``identity_target`` and expose its poor IoU/centre-error to Stage B --
   it must never be miscounted as a wrong-person or unresolved outcome
   merely because the bbox is a bad fit.
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

# --- Reference-availability states (section G) ------------------------------
#
# Whether a trustworthy target_bbox_xyxy exists at all for this sample.
# This is a *reference* question, answered by the annotator once, before
# any Stage A attribution logic runs. present_ambiguous does not exist as
# a separate reference state in v1: a contested/crossing instant is
# represented by identity_context (below), not by withholding the
# reference itself.

STATE_PRESENT_SCORED = "present_scored"
STATE_PRESENT_REFERENCE_UNAVAILABLE = "present_reference_unavailable"
STATE_ABSENT = "absent"

ALL_STATES = frozenset(
    {
        STATE_PRESENT_SCORED,
        STATE_PRESENT_REFERENCE_UNAVAILABLE,
        STATE_ABSENT,
    }
)

STATES_REQUIRING_BBOX = frozenset({STATE_PRESENT_SCORED})
STATES_FORBIDDING_BBOX = frozenset(
    {STATE_PRESENT_REFERENCE_UNAVAILABLE, STATE_ABSENT}
)

# --- Competitive context (section G/J) --------------------------------------
#
# Only meaningful (required) on present_scored samples. This is an
# explicit *completeness assertion* by the annotator, not an inference
# from whatever happens to be in distractor_bboxes_xyxy: an empty
# distractor list can only ever mean "asserted target_only", never
# "distractors were simply not annotated".

CONTEXT_TARGET_ONLY = "target_only"
CONTEXT_DISTRACTORS_COMPLETE = "distractors_complete"

ALL_CONTEXTS = frozenset({CONTEXT_TARGET_ONLY, CONTEXT_DISTRACTORS_COMPLETE})

# Only these two states/contexts are interpolation endpoints (section I).
# A distractors_complete instant is never bridged by interpolation, even
# between two present_scored keyframes: distractor geometry cannot be
# safely interpolated, and the whole point of distractors_complete is
# that this instant needs explicit, not synthesised, evidence.
INTERPOLATION_ELIGIBLE_STATE = STATE_PRESENT_SCORED
INTERPOLATION_ELIGIBLE_CONTEXT = CONTEXT_TARGET_ONLY

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
    "identity_context",
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
    identity_context: str | None
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

    raw_context = data["identity_context"]
    raw_bbox = data["target_bbox_xyxy"]
    raw_distractors = data["distractor_bboxes_xyxy"] or []

    if identity_state in STATES_REQUIRING_BBOX:
        if raw_bbox is None:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] state {identity_state!r} requires target_bbox_xyxy"
            )
        if raw_context is None:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] state {identity_state!r} requires identity_context "
                f"(one of {sorted(ALL_CONTEXTS)}) -- an empty distractor list must "
                "never be ambiguous between 'no competing person' and "
                "'distractors not annotated'"
            )
        identity_context = str(raw_context)
        if identity_context not in ALL_CONTEXTS:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].identity_context {identity_context!r} is invalid; "
                f"expected one of {sorted(ALL_CONTEXTS)}"
            )
        if identity_context == CONTEXT_TARGET_ONLY and raw_distractors:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] context {CONTEXT_TARGET_ONLY!r} asserts no "
                "competing physical person exists and must not carry "
                "distractor_bboxes_xyxy"
            )
        if identity_context == CONTEXT_DISTRACTORS_COMPLETE and not raw_distractors:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] context {CONTEXT_DISTRACTORS_COMPLETE!r} "
                "requires at least one distractor_bboxes_xyxy entry -- use "
                f"{CONTEXT_TARGET_ONLY!r} if no competing physical person exists"
            )
    else:
        identity_context = None
        if raw_context is not None:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] state {identity_state!r} must not carry "
                "identity_context"
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
        for j, d in enumerate(raw_distractors)
    )

    interpolate_from_previous = bool(data["interpolate_from_previous"])

    return PhysicalReferenceSample(
        t_s=t_s,
        identity_state=identity_state,
        identity_context=identity_context,
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
    previous_context: str | None = None

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
            endpoints_eligible = (
                previous_state == INTERPOLATION_ELIGIBLE_STATE
                and previous_context == INTERPOLATION_ELIGIBLE_CONTEXT
                and sample.identity_state == INTERPOLATION_ELIGIBLE_STATE
                and sample.identity_context == INTERPOLATION_ELIGIBLE_CONTEXT
            )
            if not endpoints_eligible:
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] sets interpolate_from_previous=true but "
                    "both endpoints must be "
                    f"({INTERPOLATION_ELIGIBLE_STATE!r}, "
                    f"{INTERPOLATION_ELIGIBLE_CONTEXT!r}); got "
                    f"previous=({previous_state!r}, {previous_context!r}), "
                    f"current=({sample.identity_state!r}, {sample.identity_context!r})"
                )

        previous_t_s = sample.t_s
        previous_state = sample.identity_state
        previous_context = sample.identity_context


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
                "identity_context": sample.identity_context,
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


# --- Stage A identity attribution (section J) -------------------------------
#
# Deliberately the only scoring logic this milestone implements: a pure
# function with no bag I/O, no duration accounting, no tracker-ID
# parameter, and -- after correction -- no localisation-quality/IoU
# threshold parameter either. It assumes the caller already established
# that a target_bbox_xyxy and identity_context exist for this sample
# (identity_state == present_scored); the caller is responsible for
# routing present_reference_unavailable / absent samples, and samples
# with no controller-facing output at all, to their own outcomes without
# calling this function.
#
# WHO the output belongs to (this function) and HOW WELL that output is
# localised (Stage B, computed separately downstream using the same
# bbox_iou primitive) are answered independently. Stage A never discards
# a target-attributed sample for having a poor IoU -- it has no basis to,
# since it never computes a pass/fail threshold on the target overlap at
# all.

IDENTITY_TARGET = "identity_target"
IDENTITY_WRONG_PERSON = "wrong_person"
IDENTITY_UNRESOLVED = "identity_unresolved"

# Not a scientific margin: purely a floating-point-equality guard so two
# geometrically identical IoUs (most commonly 0.0 vs 0.0, "no overlap with
# anyone") are treated as the tie they are, rather than an arbitrary
# comparison-order artefact.
_TIE_EPSILON = 1e-9


def classify_identity_stage_a(
    *,
    identity_context: str,
    target_bbox_xyxy: BBoxXYXY,
    distractor_bboxes_xyxy: Sequence[BBoxXYXY],
    output_bbox_xyxy: BBoxXYXY,
) -> str:
    """Section J: WHO does this output belong to, independent of how well
    it is localised.

    - ``target_only``: no plausible competing physical person was
      recorded for this instant. Any controller-facing output is
      attributed to the target -- always ``IDENTITY_TARGET`` -- because
      there is no alternative physical identity it could defensibly be.
      Localisation quality (Stage B) is a completely separate question,
      answered elsewhere.
    - ``distractors_complete``: attribution is the *relative* winner of
      target-IoU versus the best distractor-IoU. A strict win for the
      target is ``IDENTITY_TARGET`` regardless of the absolute value (a
      target that wins 0.08 to 0.02 is still the target); a strict win
      for a distractor is ``IDENTITY_WRONG_PERSON``; a tie (including
      zero overlap with everyone) is ``IDENTITY_UNRESOLVED`` -- there is
      no geometric basis to prefer either explanation.
    """

    if identity_context == CONTEXT_TARGET_ONLY:
        return IDENTITY_TARGET

    if identity_context != CONTEXT_DISTRACTORS_COMPLETE:
        raise PhysicalReferenceValidationError(
            f"unknown identity_context {identity_context!r}"
        )
    if not distractor_bboxes_xyxy:
        raise PhysicalReferenceValidationError(
            f"{CONTEXT_DISTRACTORS_COMPLETE!r} requires at least one distractor bbox"
        )

    target_iou = bbox_iou(output_bbox_xyxy, target_bbox_xyxy)
    best_distractor_iou = max(
        bbox_iou(output_bbox_xyxy, distractor)
        for distractor in distractor_bboxes_xyxy
    )

    if target_iou > best_distractor_iou + _TIE_EPSILON:
        return IDENTITY_TARGET
    if best_distractor_iou > target_iou + _TIE_EPSILON:
        return IDENTITY_WRONG_PERSON
    return IDENTITY_UNRESOLVED
