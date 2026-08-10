#!/usr/bin/env python3
"""Schema, deterministic parsing, and validation for the physical-reference
bbox annotation contract ``tim_physical_target_bbox_v2``.

Full semantics are frozen in
``docs/issues/p1-10-physical-reference-v2-contract.md``. This module is a
sibling of, not a replacement for, ``physical_target_reference.py`` (the
frozen ``tim_physical_target_bbox_v1`` contract): v1 remains unmodified and
fully valid on its own terms, and this module never silently reinterprets a
v1 artifact or vice versa (both directions rejected by
``schema_version``/``contract_version`` checks below).

What v2 adds over v1, and why (see the frozen contract doc for the full
reasoning, corrected after a read-only audit of v1's actual evaluator
behaviour):

1. Distractor entries carry an explicit, annotation-local, namespaced
   ``person_ref`` identifying the physical person a box belongs to --
   never a tracker ID, detector index, or list position. This makes
   multi-person interpolation possible without ever risking that two
   different physical people's boxes get silently connected by
   coincidence of list order.
2. An explicit, validated ``evaluation_window`` on every artifact, so the
   intended evaluation horizon is never implicitly just
   ``samples[0].t_s -> samples[-1].t_s``.
3. This module intentionally implements schema and validation ONLY. It
   contains no interpolation math, no duration accounting, and --
   deliberately -- no freshness/support-window/tolerance constant of any
   kind: an isolated present_scored keyframe grants zero duration of
   scored reference on its own under the frozen v2 contract, and
   inventing a tolerance here would silently reintroduce exactly the kind
   of stale-geometry problem v2 exists to eliminate. The evaluator that
   resolves interpolation and duration is a later milestone (M2-v2).

Stable, version-independent primitives (bbox validation, the identity
state/context vocabulary, the bare-tracker-ID guard, and the Stage A
classifier itself) are imported from v1 rather than duplicated -- none of
those concepts change meaning between schema versions.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from physical_target_reference import (  # noqa: E402
    ALL_CONTEXTS,
    ALL_STATES,
    COORDINATE_CONVENTIONS,
    CONTEXT_DISTRACTORS_COMPLETE,
    CONTEXT_TARGET_ONLY,
    STATE_ABSENT,
    STATE_PRESENT_REFERENCE_UNAVAILABLE,
    STATE_PRESENT_SCORED,
    STATES_FORBIDDING_BBOX,
    STATES_REQUIRING_BBOX,
    BBoxXYXY,
    PhysicalReferenceValidationError,
    _looks_like_bare_tracker_id,
    _parse_bbox,
    _require_finite,
    _validate_bbox_bounds,
    bbox_iou,
    classify_identity_stage_a,
)

__all__ = [
    "SCHEMA_VERSION",
    "CONTRACT_VERSION",
    "PERSON_REF_PATTERN",
    "ALL_CONTEXTS",
    "ALL_STATES",
    "COORDINATE_CONVENTIONS",
    "CONTEXT_DISTRACTORS_COMPLETE",
    "CONTEXT_TARGET_ONLY",
    "STATE_ABSENT",
    "STATE_PRESENT_REFERENCE_UNAVAILABLE",
    "STATE_PRESENT_SCORED",
    "BBoxXYXY",
    "PhysicalReferenceValidationError",
    "bbox_iou",
    "classify_identity_stage_a",
    "EvaluationWindow",
    "DistractorEntry",
    "PhysicalReferenceProvenance",
    "PhysicalReferenceSample",
    "PhysicalReferenceArtifact",
    "parse_provenance",
    "parse_sample",
    "parse_physical_reference",
    "validate_physical_reference",
    "serialize_physical_reference",
    "write_physical_reference",
    "load_physical_reference",
]


SCHEMA_VERSION = 2
CONTRACT_VERSION = "tim_physical_target_bbox_v2"

# --- Annotation-local physical-person correspondence (contract section D) ---
#
# Frozen, deterministic namespace: visibly belongs to the physical-reference
# contract, structurally cannot collide with a tracker ID, detector index, a
# bare digit string, or an unprefixed ordinal. `phys_d001`, `phys_d002`, ...
PERSON_REF_PATTERN = re.compile(r"^phys_d[0-9]{3,}$")

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
    "evaluation_window",
)

REQUIRED_SAMPLE_FIELDS = (
    "t_s",
    "identity_state",
    "identity_context",
    "target_bbox_xyxy",
    "distractors",
    "interpolate_from_previous",
)


@dataclass(frozen=True)
class EvaluationWindow:
    """Contract section I: the declared bag-relative evaluation horizon,
    independent of which timestamps happen to carry keyframes."""

    start_s: float
    end_s: float


@dataclass(frozen=True)
class DistractorEntry:
    """One physical distractor at one sample. ``person_ref`` is an
    annotation-local physical-person identifier (contract section D) --
    never a tracker ID, detector index, or a stand-in for list position."""

    person_ref: str
    bbox_xyxy: BBoxXYXY


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
    evaluation_window: EvaluationWindow
    coordinate_convention_evidence: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class PhysicalReferenceSample:
    t_s: float
    identity_state: str
    identity_context: str | None
    target_bbox_xyxy: BBoxXYXY | None
    distractors: tuple[DistractorEntry, ...] = field(default_factory=tuple)
    interpolate_from_previous: bool = False
    notes: str = ""


@dataclass(frozen=True)
class PhysicalReferenceArtifact:
    provenance: PhysicalReferenceProvenance
    samples: tuple[PhysicalReferenceSample, ...]


def _validate_person_ref(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PhysicalReferenceValidationError(f"{label} must be a string")
    if not PERSON_REF_PATTERN.match(value):
        raise PhysicalReferenceValidationError(
            f"{label} {value!r} does not match the required annotation-local "
            f"physical-person namespace {PERSON_REF_PATTERN.pattern!r} "
            "(e.g. 'phys_d001') -- person_ref must never be a tracker ID, "
            "a detector index, a bare digit string, or derived from list "
            "position"
        )
    return value


def _parse_evaluation_window(data: Any) -> EvaluationWindow:
    if not isinstance(data, dict):
        raise PhysicalReferenceValidationError(
            "provenance.evaluation_window must be an object with 'start_s' "
            "and 'end_s'"
        )
    if "start_s" not in data or "end_s" not in data:
        raise PhysicalReferenceValidationError(
            "provenance.evaluation_window requires both 'start_s' and 'end_s'"
        )
    start_s = _require_finite(
        data["start_s"], "provenance.evaluation_window.start_s"
    )
    end_s = _require_finite(data["end_s"], "provenance.evaluation_window.end_s")
    if start_s < 0.0:
        raise PhysicalReferenceValidationError(
            "provenance.evaluation_window.start_s must be non-negative, got "
            f"{start_s}"
        )
    if end_s <= start_s:
        raise PhysicalReferenceValidationError(
            "provenance.evaluation_window.end_s must be strictly greater "
            f"than start_s ({start_s}), got {end_s}"
        )
    return EvaluationWindow(start_s=start_s, end_s=end_s)


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

    sequence_id = str(data["sequence_id"])
    if not sequence_id.strip():
        raise PhysicalReferenceValidationError(
            "sequence_id must be non-empty -- a physical-reference artifact "
            "must carry a deliberate sequence identity, not a placeholder"
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

    evaluation_window = _parse_evaluation_window(data["evaluation_window"])

    return PhysicalReferenceProvenance(
        schema_version=schema_version,
        contract_version=contract_version,
        sequence_id=sequence_id,
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
        evaluation_window=evaluation_window,
        notes=str(data.get("notes", "")),
    )


def _parse_distractors(raw_distractors: Any, index: int) -> tuple[DistractorEntry, ...]:
    if not isinstance(raw_distractors, list):
        raise PhysicalReferenceValidationError(
            f"sample[{index}].distractors must be a list"
        )

    entries: list[DistractorEntry] = []
    seen_refs: set[str] = set()
    for j, entry in enumerate(raw_distractors):
        if not isinstance(entry, dict):
            raise PhysicalReferenceValidationError(
                f"sample[{index}].distractors[{j}] must be an object with "
                "'person_ref' and 'bbox_xyxy'"
            )
        if "person_ref" not in entry:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].distractors[{j}] is missing 'person_ref'"
            )
        if "bbox_xyxy" not in entry:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].distractors[{j}] is missing 'bbox_xyxy'"
            )
        person_ref = _validate_person_ref(
            entry["person_ref"], f"sample[{index}].distractors[{j}].person_ref"
        )
        if person_ref in seen_refs:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] has duplicate person_ref {person_ref!r} "
                "across its distractors -- each physical person must appear "
                "at most once per sample"
            )
        seen_refs.add(person_ref)
        bbox = _parse_bbox(
            entry["bbox_xyxy"], f"sample[{index}].distractors[{j}].bbox_xyxy"
        )
        entries.append(DistractorEntry(person_ref=person_ref, bbox_xyxy=bbox))

    # Deterministic canonical ordering, independent of drawing/input order
    # (contract section D / "deterministic serialization"): downstream code,
    # including any future interpolation resolution, must never rely on the
    # order distractors happened to be drawn or written in.
    entries.sort(key=lambda d: d.person_ref)
    return tuple(entries)


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
    raw_distractors = data["distractors"] or []

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
                "distractors"
            )
        if identity_context == CONTEXT_DISTRACTORS_COMPLETE and not raw_distractors:
            raise PhysicalReferenceValidationError(
                f"sample[{index}] context {CONTEXT_DISTRACTORS_COMPLETE!r} "
                "requires at least one distractor entry -- use "
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
                "distractors"
            )

    target_bbox = (
        _parse_bbox(raw_bbox, f"sample[{index}].target_bbox_xyxy")
        if raw_bbox is not None
        else None
    )
    distractors = _parse_distractors(raw_distractors, index)

    interpolate_from_previous = bool(data["interpolate_from_previous"])

    return PhysicalReferenceSample(
        t_s=t_s,
        identity_state=identity_state,
        identity_context=identity_context,
        target_bbox_xyxy=target_bbox,
        distractors=distractors,
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
    """Semantic validation beyond per-field parsing: evaluation-window
    membership, bounds, monotonicity, and interpolation legality --
    including exact physical-person correspondence for distractors_complete
    (contract section F). Interpolation math itself is out of scope for
    this module; only the legality of a claimed interpolation is checked
    here."""

    provenance = artifact.provenance
    window = provenance.evaluation_window
    previous_sample: PhysicalReferenceSample | None = None

    for index, sample in enumerate(artifact.samples):
        if previous_sample is not None and sample.t_s <= previous_sample.t_s:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].t_s={sample.t_s} is not strictly greater "
                f"than the previous sample's t_s={previous_sample.t_s}"
            )

        if sample.t_s < window.start_s or sample.t_s >= window.end_s:
            raise PhysicalReferenceValidationError(
                f"sample[{index}].t_s={sample.t_s} lies outside the declared "
                f"evaluation_window [{window.start_s}, {window.end_s})"
            )

        if sample.target_bbox_xyxy is not None:
            _validate_bbox_bounds(
                sample.target_bbox_xyxy,
                f"sample[{index}].target_bbox_xyxy",
                provenance.source_width,
                provenance.source_height,
            )
        for d in sample.distractors:
            _validate_bbox_bounds(
                d.bbox_xyxy,
                f"sample[{index}].distractors[{d.person_ref}].bbox_xyxy",
                provenance.source_width,
                provenance.source_height,
            )

        if sample.interpolate_from_previous:
            if index == 0:
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] cannot set interpolate_from_previous=true; "
                    "it has no predecessor"
                )
            assert previous_sample is not None
            if (
                previous_sample.identity_state != STATE_PRESENT_SCORED
                or sample.identity_state != STATE_PRESENT_SCORED
            ):
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] sets interpolate_from_previous=true but "
                    f"both endpoints must be {STATE_PRESENT_SCORED!r}; got "
                    f"previous={previous_sample.identity_state!r}, "
                    f"current={sample.identity_state!r}"
                )
            if previous_sample.identity_context != sample.identity_context:
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] sets interpolate_from_previous=true but "
                    "identity_context differs between endpoints: "
                    f"previous={previous_sample.identity_context!r}, "
                    f"current={sample.identity_context!r}"
                )
            if sample.identity_context == CONTEXT_DISTRACTORS_COMPLETE:
                previous_refs = {d.person_ref for d in previous_sample.distractors}
                current_refs = {d.person_ref for d in sample.distractors}
                if previous_refs != current_refs:
                    raise PhysicalReferenceValidationError(
                        f"sample[{index}] sets interpolate_from_previous=true "
                        "under distractors_complete but the physical-person "
                        "correspondence set differs between endpoints: "
                        f"previous={sorted(previous_refs)}, "
                        f"current={sorted(current_refs)} -- interpolation "
                        "requires an exact person_ref set match"
                    )
            elif sample.identity_context != CONTEXT_TARGET_ONLY:
                raise PhysicalReferenceValidationError(
                    f"sample[{index}] sets interpolate_from_previous=true but "
                    f"identity_context {sample.identity_context!r} is not "
                    "interpolation-eligible"
                )

        previous_sample = sample


def load_physical_reference(path: Path) -> PhysicalReferenceArtifact:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    artifact = parse_physical_reference(data)
    validate_physical_reference(artifact)
    return artifact


def serialize_physical_reference(artifact: PhysicalReferenceArtifact) -> dict:
    """Deterministic dict form. Distractors are always written sorted by
    person_ref -- semantically identical artifacts never receive different
    hashes merely because distractors were drawn, input, or stored in a
    different order (contract section D)."""

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
            "evaluation_window": {
                "start_s": provenance.evaluation_window.start_s,
                "end_s": provenance.evaluation_window.end_s,
            },
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
                "distractors": [
                    {"person_ref": d.person_ref, "bbox_xyxy": list(d.bbox_xyxy)}
                    for d in sorted(sample.distractors, key=lambda d: d.person_ref)
                ],
                "interpolate_from_previous": sample.interpolate_from_previous,
                "notes": sample.notes,
            }
            for sample in artifact.samples
        ],
    }


def write_physical_reference(path: Path, artifact: PhysicalReferenceArtifact) -> None:
    payload = serialize_physical_reference(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
