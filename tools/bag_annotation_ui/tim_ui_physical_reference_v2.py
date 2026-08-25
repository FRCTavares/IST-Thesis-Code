#!/usr/bin/env python3
"""Backend helpers for the Issue #25 v2 physical-reference bbox annotation
UI mode (``tim_physical_target_bbox_v2``).

Sibling of ``tim_ui_physical_reference.py`` (v1), not a replacement -- v1's
adapter and routes remain valid and untouched (no real v1 artifacts exist
to migrate). This module is the v2-specific analogue: a thin adapter
between the UI and ``tools/analysis/physical_target_reference_v2.py``,
which is the schema authority. It never duplicates that module's
parsing/validation/serialization rules -- the two new pieces of pure logic
below (``next_person_ref``, ``known_person_refs``) are UI-convenience
concerns the schema module has no reason to own: the backend validator
does not care what generated a ``person_ref``, only that it matches the
frozen namespace, and "which person_refs exist in this artifact" is
always re-derived from the artifact's own samples, never stored
separately.

``normalize_rect`` and ``safe_physical_reference_relpath`` are reused
directly from ``tim_ui_physical_reference`` (v1) -- reverse-drag/zero-area
box normalisation and repository-relative path safety have no
schema-version dependency at all.
"""

from __future__ import annotations

import json
import math
import sys

import cv2
import numpy as np
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).resolve().parent
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_reference_v2 as ptr2  # noqa: E402
from physical_target_bbox_evaluation_v2 import (  # noqa: E402
    REF_COVERED,
    REF_GAP,
    REF_TARGET_ABSENT,
    REF_UNAVAILABLE,
    resolve_reference_interval,
)

from tim_ui_physical_reference import (  # noqa: E402
    PhysicalReferenceUIError,
    normalize_rect,  # noqa: F401  (re-exported for the v2 routes/tests)
    safe_physical_reference_relpath,
)

PERSON_REF_PREFIX = "phys_d"
PERSON_REF_DIGIT_WIDTH = 3


def next_person_ref(known_refs: list[str]) -> str:
    """Deterministic new-person-ref generator: the lowest unused positive
    ordinal in the frozen ``phys_dNNN`` namespace
    (``physical_target_reference_v2.PERSON_REF_PATTERN``).

    Never derived from a tracker ID, detector index, drawing order, or
    bbox geometry -- the only input is which ordinals are already used.
    Given ``{phys_d001, phys_d002, phys_d004}`` this returns ``phys_d003``
    (the lowest unused ordinal), not ``phys_d005`` (the next monotonic
    one)."""

    used: set[int] = set()
    for ref in known_refs:
        match = ptr2.PERSON_REF_PATTERN.match(str(ref))
        if not match:
            continue
        digits = str(ref)[len(PERSON_REF_PREFIX) :]
        try:
            used.add(int(digits))
        except ValueError:
            continue

    n = 1
    while n in used:
        n += 1
    return f"{PERSON_REF_PREFIX}{n:0{PERSON_REF_DIGIT_WIDTH}d}"


def known_person_refs(samples: list[dict]) -> list[str]:
    """Every ``person_ref`` appearing anywhere in the artifact's saved
    samples, sorted. The artifact's own samples are the single source of
    truth for which physical people it knows about -- nothing is stored
    separately, so removing a distractor from one sample's draft can never
    make another sample's own person_ref disappear from this list."""

    refs: set[str] = set()
    for sample in samples or []:
        for entry in sample.get("distractors") or []:
            ref = entry.get("person_ref")
            if ref:
                refs.add(str(ref))
    return sorted(refs)


PREVIEW_EXPLICIT = "explicit_keyframe"
PREVIEW_INTERPOLATED = "interpolated"
PREVIEW_GAP = "reference_gap"
PREVIEW_ABSENT = "absent"
PREVIEW_UNAVAILABLE = "present_reference_unavailable"
PREVIEW_EXACT_TOLERANCE_S = 1e-6

OPTICAL_FLOW_METHOD = "sparse_lk_median_translation"
MAX_OPTICAL_FLOW_FRAME_DISTANCE = 150


def _sample_preview(sample: ptr2.PhysicalReferenceSample) -> dict[str, Any]:
    """Serialize one exact human keyframe for read-only display."""

    return {
        "classification": PREVIEW_EXPLICIT,
        "identity_state": sample.identity_state,
        "identity_context": sample.identity_context,
        "target_bbox_xyxy": (
            list(sample.target_bbox_xyxy)
            if sample.target_bbox_xyxy is not None
            else None
        ),
        "distractors": [
            {"person_ref": d.person_ref, "bbox_xyxy": list(d.bbox_xyxy)}
            for d in sample.distractors
        ],
    }


def resolve_effective_reference_preview(
    artifact: ptr2.PhysicalReferenceArtifact, t_s: float
) -> dict[str, Any]:
    """Resolve the effective v2 reference shown by the annotation UI.

    Exact timestamps are explicit human keyframes, including the legal
    right-boundary anchor. Every non-exact timestamp delegates geometry and
    state resolution to the evaluator canonical resolver. This is read-only.
    """

    t = float(t_s)
    window = artifact.provenance.evaluation_window
    if t < window.start_s or t > window.end_s:
        return {
            "classification": PREVIEW_GAP,
            "identity_state": None,
            "identity_context": None,
            "target_bbox_xyxy": None,
            "distractors": [],
        }

    for sample in artifact.samples:
        if abs(sample.t_s - t) <= PREVIEW_EXACT_TOLERANCE_S:
            return _sample_preview(sample)

    resolved = resolve_reference_interval(artifact.samples, t)
    if resolved.condition == REF_COVERED:
        return {
            "classification": PREVIEW_INTERPOLATED,
            "identity_state": ptr2.STATE_PRESENT_SCORED,
            "identity_context": resolved.identity_context,
            "target_bbox_xyxy": list(resolved.target_bbox_xyxy),
            "distractors": [
                {"person_ref": d.person_ref, "bbox_xyxy": list(d.bbox_xyxy)}
                for d in resolved.distractors
            ],
        }

    classification = {
        REF_GAP: PREVIEW_GAP,
        REF_TARGET_ABSENT: PREVIEW_ABSENT,
        REF_UNAVAILABLE: PREVIEW_UNAVAILABLE,
    }[resolved.condition]
    identity_state = {
        REF_GAP: None,
        REF_TARGET_ABSENT: ptr2.STATE_ABSENT,
        REF_UNAVAILABLE: ptr2.STATE_PRESENT_REFERENCE_UNAVAILABLE,
    }[resolved.condition]
    return {
        "classification": classification,
        "identity_state": identity_state,
        "identity_context": None,
        "target_bbox_xyxy": None,
        "distractors": [],
    }


def build_effective_reference_previews(
    payload: dict[str, Any], times_s: list[float]
) -> list[dict[str, Any]]:
    """Validate an in-memory artifact and resolve a read-only preview batch."""

    artifact = ptr2.parse_physical_reference(payload)
    ptr2.validate_physical_reference(artifact)
    return [
        {"t_s": float(t), **resolve_effective_reference_preview(artifact, float(t))}
        for t in times_s
    ]


def _clip_box_to_image(
    box: tuple[float, float, float, float], width: int, height: int
) -> tuple[float, float, float, float] | None:
    clipped = (
        max(0.0, min(float(box[0]), float(width))),
        max(0.0, min(float(box[1]), float(height))),
        max(0.0, min(float(box[2]), float(width))),
        max(0.0, min(float(box[3]), float(height))),
    )
    return normalize_rect(*clipped)


def _propagate_one_box(
    previous_gray: np.ndarray,
    next_gray: np.ndarray,
    box: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float] | None, dict[str, Any]]:
    """Propagate one bbox by deterministic median sparse-flow translation."""

    height, width = previous_gray.shape[:2]
    clipped = _clip_box_to_image(box, width, height)
    if clipped is None:
        return None, {"point_count": 0, "median_error": None}

    x1, y1, x2, y2 = clipped
    mask = np.zeros(previous_gray.shape, dtype=np.uint8)
    ix1, iy1 = max(0, int(math.floor(x1))), max(0, int(math.floor(y1)))
    ix2, iy2 = min(width, int(math.ceil(x2))), min(height, int(math.ceil(y2)))
    if ix2 - ix1 < 2 or iy2 - iy1 < 2:
        return None, {"point_count": 0, "median_error": None}
    mask[iy1:iy2, ix1:ix2] = 255

    points = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=40,
        qualityLevel=0.01,
        minDistance=3,
        mask=mask,
        blockSize=3,
    )
    if points is None or len(points) < 3:
        return None, {"point_count": 0, "median_error": None}

    moved, status, errors = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        next_gray,
        points,
        None,
        winSize=(21, 21),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
    )
    if moved is None or status is None:
        return None, {"point_count": 0, "median_error": None}

    valid = status.reshape(-1).astype(bool)
    p0 = points.reshape(-1, 2)[valid]
    p1 = moved.reshape(-1, 2)[valid]
    if len(p0) < 3:
        return None, {"point_count": int(len(p0)), "median_error": None}

    displacement = p1 - p0
    finite = np.isfinite(displacement).all(axis=1)
    valid_errors = errors.reshape(-1)[valid] if errors is not None else None
    if valid_errors is not None:
        finite &= np.isfinite(valid_errors)
    displacement = displacement[finite]
    if len(displacement) < 3:
        return None, {"point_count": int(len(displacement)), "median_error": None}

    dx, dy = np.median(displacement, axis=0)
    shifted = _clip_box_to_image((x1 + dx, y1 + dy, x2 + dx, y2 + dy), width, height)
    median_error = (
        float(np.median(valid_errors[finite]))
        if valid_errors is not None
        else None
    )
    return shifted, {
        "point_count": int(len(displacement)),
        "median_error": median_error,
    }


def propose_geometry_with_optical_flow(
    images: list[np.ndarray],
    anchor_frame_index: int,
    target_frame_index: int,
    target_bbox_xyxy: list[float],
    distractors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Propose nearby geometry while preserving human-established identity.

    It starts only from explicit human geometry, retains supplied person refs,
    never reads detector/tracker output, and never writes an artifact.
    """

    if not images:
        raise PhysicalReferenceUIError("No source frames are loaded.")
    anchor = int(anchor_frame_index)
    target = int(target_frame_index)
    if not (0 <= anchor < len(images)) or not (0 <= target < len(images)):
        raise PhysicalReferenceUIError("Proposal frame index is outside the loaded source.")
    distance = abs(target - anchor)
    if distance == 0:
        raise PhysicalReferenceUIError("Current frame is already the proposal anchor.")
    if distance > MAX_OPTICAL_FLOW_FRAME_DISTANCE:
        raise PhysicalReferenceUIError(
            f"Proposal is {distance} frames from its anchor; maximum is "
            f"{MAX_OPTICAL_FLOW_FRAME_DISTANCE}. Add/review a nearer explicit anchor first."
        )

    normalized_target = normalize_rect(*[float(v) for v in target_bbox_xyxy])
    if normalized_target is None:
        raise PhysicalReferenceUIError("Proposal anchor target bbox is invalid.")

    states: list[dict[str, Any]] = [
        {"role": "target", "person_ref": None, "bbox": normalized_target}
    ]
    for entry in distractors:
        ref = str(entry.get("person_ref", ""))
        if not ptr2.PERSON_REF_PATTERN.match(ref):
            raise PhysicalReferenceUIError(f"Invalid proposal person_ref: {ref!r}")
        raw_box = entry.get("bbox_xyxy")
        if not isinstance(raw_box, list) or len(raw_box) != 4:
            raise PhysicalReferenceUIError(f"Proposal bbox missing for {ref}.")
        box = normalize_rect(*[float(v) for v in raw_box])
        if box is None:
            raise PhysicalReferenceUIError(f"Proposal bbox is invalid for {ref}.")
        states.append({"role": "distractor", "person_ref": ref, "bbox": box})

    direction = 1 if target > anchor else -1
    per_person_quality = {
        state["person_ref"] or "target": {
            "minimum_point_count": None,
            "maximum_median_error": 0.0,
        }
        for state in states
    }

    for previous_index in range(anchor, target, direction):
        next_index = previous_index + direction
        previous_gray = cv2.cvtColor(images[previous_index], cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(images[next_index], cv2.COLOR_BGR2GRAY)
        for state in states:
            moved_box, quality = _propagate_one_box(
                previous_gray, next_gray, state["bbox"]
            )
            label = state["person_ref"] or "target"
            if moved_box is None:
                raise PhysicalReferenceUIError(
                    f"Optical-flow proposal became ambiguous for {label} between "
                    f"frames {previous_index} and {next_index}; no geometry was guessed."
                )
            state["bbox"] = moved_box
            q = per_person_quality[label]
            count = quality["point_count"]
            q["minimum_point_count"] = (
                count
                if q["minimum_point_count"] is None
                else min(q["minimum_point_count"], count)
            )
            if quality["median_error"] is not None:
                q["maximum_median_error"] = max(
                    q["maximum_median_error"], quality["median_error"]
                )

    return {
        "method": OPTICAL_FLOW_METHOD,
        "anchor_frame_index": anchor,
        "target_frame_index": target,
        "frame_distance": distance,
        "target_bbox_xyxy": list(states[0]["bbox"]),
        "distractors": [
            {"person_ref": state["person_ref"], "bbox_xyxy": list(state["bbox"])}
            for state in sorted(states[1:], key=lambda item: str(item["person_ref"]))
        ],
        "quality": per_person_quality,
        "identity_source": "human_anchor_person_refs_only",
        "accepted": False,
    }


def load_physical_reference_v2_for_ui(path_text: str, repo_root: Path) -> dict[str, Any]:
    """Load and validate a v2 physical-reference artifact for UI
    population. A v1 artifact is rejected here with an explicit,
    UI-friendly message -- it is never silently migrated or edited as v2
    (contract: no automatic v1 -> v2 migration)."""

    rel = safe_physical_reference_relpath(path_text)
    path = repo_root / rel

    if not path.exists():
        raise PhysicalReferenceUIError(f"Physical reference does not exist: {rel}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw_schema_version = (raw.get("provenance") or {}).get("schema_version")
    if raw_schema_version == 1:
        raise PhysicalReferenceUIError(
            f"{rel} is a legacy tim_physical_target_bbox_v1 artifact. "
            "This v2 workspace never edits or silently migrates v1 "
            "artifacts -- start a new v2 artifact instead."
        )

    artifact = ptr2.load_physical_reference(path)
    serialized = ptr2.serialize_physical_reference(artifact)
    return {
        "path": str(rel),
        "known_person_refs": known_person_refs(serialized["samples"]),
        **serialized,
    }


def save_physical_reference_v2_for_ui(
    path_text: str, payload: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Validate (backend-authoritative) and atomically save a v2
    physical-reference artifact constructed by the UI. ``payload`` must
    already have the shape produced by
    ``physical_target_reference_v2.serialize_physical_reference``. Invalid
    payloads raise before any file (or its parent directory) is created --
    see ``physical_target_reference_v2.write_physical_reference``."""

    rel = safe_physical_reference_relpath(path_text)
    path = repo_root / rel

    artifact = ptr2.parse_physical_reference(payload)
    ptr2.validate_physical_reference(artifact)

    ptr2.write_physical_reference(path, artifact)

    serialized = ptr2.serialize_physical_reference(artifact)
    return {
        "path": str(rel),
        "sample_count": len(artifact.samples),
        "known_person_refs": known_person_refs(serialized["samples"]),
        **serialized,
    }
