#!/usr/bin/env python3
"""Backend helpers for the Issue #25 v2 physical-reference bbox annotation
UI mode (``tim_physical_target_bbox_v2``).

Sibling of ``tim_ui_physical_reference.py`` (v1), not a replacement -- v1's
adapter and routes remain valid and untouched (no real v1 artifacts exist
to migrate). This module is the v2-specific analogue: a thin adapter
between the UI and ``tools/analysis/physical_target_reference_v2.py``,
which is the schema authority. It never duplicates that module's
parsing/validation/serialization rules. UI-only helpers cover deterministic
``person_ref`` allocation, evaluator-backed effective preview, and ephemeral
image-space proposal/review computation. None of those helpers changes the
frozen v2 artifact contract or writes canonical evidence: the backend validator
does not care what generated a ``person_ref``, only that it matches the frozen
namespace, and "which person_refs exist in this artifact" is always re-derived
from the artifact's own samples, never stored separately.

``normalize_rect`` and ``safe_physical_reference_relpath`` are reused
directly from ``tim_ui_physical_reference`` (v1) -- reverse-drag/zero-area
box normalisation and repository-relative path safety have no
schema-version dependency at all.
"""

from __future__ import annotations

import hashlib
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
    raw_shifted = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
    shifted = _clip_box_to_image(raw_shifted, width, height)
    median_error = (
        float(np.median(valid_errors[finite]))
        if valid_errors is not None
        else None
    )
    boundary_truncated = bool(
        shifted is not None
        and any(abs(float(a) - float(b)) > 1e-6 for a, b in zip(raw_shifted, shifted))
    )
    return shifted, {
        "point_count": int(len(displacement)),
        "initial_point_count": int(len(points)),
        "tracked_fraction": float(len(displacement) / max(1, len(points))),
        "median_error": median_error,
        "boundary_truncated": boundary_truncated,
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



CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_REVIEW = "review"
CONFIDENCE_AMBIGUOUS = "ambiguous"
CONFIDENCE_LOST = "lost"
CONFIDENCE_ORDER = {
    CONFIDENCE_HIGH: 0,
    CONFIDENCE_MEDIUM: 1,
    CONFIDENCE_REVIEW: 2,
    CONFIDENCE_AMBIGUOUS: 3,
    CONFIDENCE_LOST: 4,
}
SEQUENCE_PROPAGATION_METHOD = "bidirectional_sparse_lk_human_anchors_v1"
DEFAULT_REVIEW_THRESHOLDS = {
    "iou_below": 0.65,
    "centre_ref_height_above": 0.25,
    "scale_delta_above": 0.25,
}


def bbox_comparison_metrics(
    reference_box: list[float] | tuple[float, float, float, float],
    proposal_box: list[float] | tuple[float, float, float, float],
) -> dict[str, float]:
    """Deterministic annotation-review disagreement metrics."""

    a = [float(v) for v in reference_box]
    b = [float(v) for v in proposal_box]
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    iou = intersection / union if union > 0.0 else 0.0
    ref_h = max(1e-9, a[3] - a[1])
    ref_w = max(1e-9, a[2] - a[0])
    prop_h = max(1e-9, b[3] - b[1])
    prop_w = max(1e-9, b[2] - b[0])
    dx = ((b[0] + b[2]) - (a[0] + a[2])) / 2.0
    dy = ((b[1] + b[3]) - (a[1] + a[3])) / 2.0
    return {
        "iou": float(iou),
        "centre_ref_height": float(math.hypot(dx, dy) / ref_h),
        "scale_delta": float(
            max(abs(math.log(prop_w / ref_w)), abs(math.log(prop_h / ref_h)))
        ),
    }


def _metrics_exceed_thresholds(
    metrics: dict[str, float], thresholds: dict[str, float]
) -> bool:
    return bool(
        metrics["iou"] < thresholds["iou_below"]
        or metrics["centre_ref_height"]
        > thresholds["centre_ref_height_above"]
        or metrics["scale_delta"] > thresholds["scale_delta_above"]
    )


def _metrics_severity(
    metrics: dict[str, float], thresholds: dict[str, float]
) -> float:
    terms = [0.0]
    if metrics["iou"] < thresholds["iou_below"]:
        terms.append(
            (thresholds["iou_below"] - metrics["iou"])
            / max(1e-9, thresholds["iou_below"])
        )
    terms.append(
        metrics["centre_ref_height"]
        / max(1e-9, thresholds["centre_ref_height_above"])
        - 1.0
    )
    terms.append(
        metrics["scale_delta"] / max(1e-9, thresholds["scale_delta_above"])
        - 1.0
    )
    return float(max(terms))


def refine_box_with_anonymous_detections(
    propagated_box: list[float], anonymous_detection_boxes: list[list[float]]
) -> dict[str, Any]:
    """Optionally refine geometry using anonymous person boxes only.

    The API deliberately accepts no class IDs, tracker IDs, physical-person
    labels, or detector object identity. A close scoring tie is surfaced as
    ambiguity and the propagated geometry is retained rather than guessed.
    """

    base = normalize_rect(*[float(v) for v in propagated_box])
    if base is None:
        raise PhysicalReferenceUIError("Propagated bbox is invalid.")
    ranked: list[tuple[float, tuple[float, float, float, float], dict[str, float]]] = []
    for raw_candidate in anonymous_detection_boxes or []:
        if not isinstance(raw_candidate, list) or len(raw_candidate) != 4:
            raise PhysicalReferenceUIError(
                "Anonymous detector candidates must be bbox coordinate lists only."
            )
        candidate = normalize_rect(*[float(v) for v in raw_candidate])
        if candidate is None:
            continue
        metrics = bbox_comparison_metrics(base, candidate)
        if (
            metrics["iou"] < 0.20
            or metrics["centre_ref_height"] > 0.65
            or metrics["scale_delta"] > 0.60
        ):
            continue
        score = (
            0.65 * metrics["iou"]
            + 0.20 * max(0.0, 1.0 - metrics["centre_ref_height"])
            + 0.15 * max(0.0, 1.0 - metrics["scale_delta"])
        )
        ranked.append((float(score), candidate, metrics))

    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return {
            "bbox_xyxy": list(base),
            "status": "no_match",
            "candidate_count": 0,
            "used_detector_geometry": False,
        }
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08:
        return {
            "bbox_xyxy": list(base),
            "status": CONFIDENCE_AMBIGUOUS,
            "candidate_count": len(ranked),
            "used_detector_geometry": False,
        }
    best = ranked[0]
    return {
        "bbox_xyxy": list(best[1]),
        "status": "refined",
        "candidate_count": len(ranked),
        "used_detector_geometry": True,
        "match_score": best[0],
        "match_metrics": best[2],
    }


def _flow_confidence(quality: dict[str, Any]) -> str:
    points = int(quality.get("point_count") or 0)
    tracked_fraction = float(quality.get("tracked_fraction", 1.0 if points else 0.0))
    median_error = quality.get("median_error")
    error = float(median_error) if median_error is not None else float("inf")
    if points < 3:
        return CONFIDENCE_LOST
    if quality.get("boundary_truncated"):
        return CONFIDENCE_REVIEW
    if points >= 12 and tracked_fraction >= 0.65 and error <= 12.0:
        return CONFIDENCE_HIGH
    if points >= 6 and tracked_fraction >= 0.40 and error <= 25.0:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_REVIEW


def _boxes_from_sample(sample: ptr2.PhysicalReferenceSample) -> dict[str, list[float]]:
    boxes = {"target": list(sample.target_bbox_xyxy)}
    boxes.update({d.person_ref: list(d.bbox_xyxy) for d in sample.distractors})
    return boxes


def _frame_index_for_time(times_s: list[float], t_s: float) -> int:
    if not times_s:
        raise PhysicalReferenceUIError("No source-frame timestamps are loaded.")
    return min(range(len(times_s)), key=lambda i: abs(float(times_s[i]) - float(t_s)))


def _propagate_direction(
    gray_images: list[np.ndarray],
    anchor_index: int,
    end_index: int,
    anchor_boxes: dict[str, list[float]],
    anonymous_detections_by_frame: dict[int, list[list[float]]] | None,
    progress_callback: Any = None,
) -> dict[int, dict[str, dict[str, Any]]]:
    direction = 1 if end_index > anchor_index else -1
    current = {label: tuple(box) for label, box in anchor_boxes.items()}
    active = {label: True for label in current}
    accumulated_confidence = {label: CONFIDENCE_HIGH for label in current}
    output: dict[int, dict[str, dict[str, Any]]] = {}
    for previous_index in range(anchor_index, end_index, direction):
        next_index = previous_index + direction
        frame_people: dict[str, dict[str, Any]] = {}
        used_detector_boxes: set[tuple[float, float, float, float]] = set()
        for label in sorted(current):
            if not active[label]:
                frame_people[label] = {
                    "bbox_xyxy": None,
                    "confidence": CONFIDENCE_LOST,
                    "reason": "propagation_stopped_after_uncertain_frame",
                }
                continue
            moved, quality = _propagate_one_box(
                gray_images[previous_index], gray_images[next_index], current[label]
            )
            confidence = _flow_confidence(quality)
            if moved is None or confidence == CONFIDENCE_LOST:
                active[label] = False
                frame_people[label] = {
                    "bbox_xyxy": None,
                    "confidence": CONFIDENCE_LOST,
                    "reason": "insufficient_optical_flow_evidence",
                    "flow_quality": quality,
                }
                continue

            detector_result = None
            candidates = (
                (anonymous_detections_by_frame or {}).get(next_index)
                if anonymous_detections_by_frame is not None
                else None
            )
            if candidates:
                detector_result = refine_box_with_anonymous_detections(
                    list(moved), candidates
                )
                if detector_result["status"] == CONFIDENCE_AMBIGUOUS:
                    active[label] = False
                    frame_people[label] = {
                        "bbox_xyxy": None,
                        "confidence": CONFIDENCE_AMBIGUOUS,
                        "reason": "multiple_plausible_anonymous_detections",
                        "flow_quality": quality,
                        "detector_refinement": detector_result,
                    }
                    continue
                if detector_result["used_detector_geometry"]:
                    detector_box = tuple(float(v) for v in detector_result["bbox_xyxy"])
                    if detector_box in used_detector_boxes:
                        active[label] = False
                        frame_people[label] = {
                            "bbox_xyxy": None,
                            "confidence": CONFIDENCE_AMBIGUOUS,
                            "reason": "anonymous_detection_already_matches_another_person",
                            "flow_quality": quality,
                            "detector_refinement": detector_result,
                        }
                        continue
                    used_detector_boxes.add(detector_box)
                    moved = detector_box

            accumulated_confidence[label] = _worse_confidence(
                accumulated_confidence[label], confidence
            )
            current[label] = moved
            frame_people[label] = {
                "bbox_xyxy": list(moved),
                "confidence": accumulated_confidence[label],
                "reason": "image_continuity",
                "flow_quality": quality,
                "detector_refinement": detector_result,
            }
        output[next_index] = frame_people
        if progress_callback is not None:
            progress_callback()
    return output


def _worse_confidence(*values: str) -> str:
    return max(values, key=lambda value: CONFIDENCE_ORDER.get(value, 99))


def _merge_directional_people(
    forward: dict[str, dict[str, Any]] | None,
    backward: dict[str, dict[str, Any]] | None,
    alpha: float,
) -> dict[str, dict[str, Any]]:
    labels = sorted(set((forward or {}).keys()) | set((backward or {}).keys()))
    merged: dict[str, dict[str, Any]] = {}
    for label in labels:
        left = (forward or {}).get(label)
        right = (backward or {}).get(label)
        left_box = left.get("bbox_xyxy") if left else None
        right_box = right.get("bbox_xyxy") if right else None
        if left_box is not None and right_box is not None:
            agreement = bbox_comparison_metrics(left_box, right_box)
            if agreement["iou"] < 0.05 and agreement["centre_ref_height"] > 1.0:
                merged[label] = {
                    "bbox_xyxy": None,
                    "confidence": CONFIDENCE_AMBIGUOUS,
                    "reason": "forward_backward_hypotheses_disagree",
                    "direction_agreement": agreement,
                }
                continue
            box = [
                (1.0 - alpha) * float(a) + alpha * float(b)
                for a, b in zip(left_box, right_box)
            ]
            confidence = _worse_confidence(
                left["confidence"], right["confidence"]
            )
            if _metrics_exceed_thresholds(agreement, DEFAULT_REVIEW_THRESHOLDS):
                confidence = _worse_confidence(confidence, CONFIDENCE_REVIEW)
            merged[label] = {
                "bbox_xyxy": box,
                "confidence": confidence,
                "reason": "bidirectional_image_continuity",
                "direction_agreement": agreement,
                "forward_quality": left.get("flow_quality"),
                "backward_quality": right.get("flow_quality"),
            }
        elif left_box is not None or right_box is not None:
            source = left if left_box is not None else right
            confidence = source["confidence"]
            if confidence == CONFIDENCE_HIGH:
                confidence = CONFIDENCE_MEDIUM
            elif confidence == CONFIDENCE_MEDIUM:
                confidence = CONFIDENCE_REVIEW
            merged[label] = {
                **source,
                "confidence": confidence,
                "reason": "single_direction_image_continuity",
            }
        else:
            states = [
                item["confidence"]
                for item in (left, right)
                if item is not None and item.get("confidence")
            ]
            merged[label] = {
                "bbox_xyxy": None,
                "confidence": _worse_confidence(*states)
                if states
                else CONFIDENCE_LOST,
                "reason": "human_correspondence_confirmation_required",
            }
    return merged


def _serialize_proposal_frame(
    frame_index: int,
    t_s: float,
    people: dict[str, dict[str, Any]],
    classification: str,
) -> dict[str, Any]:
    target = people.get("target") or {
        "bbox_xyxy": None,
        "confidence": CONFIDENCE_LOST,
    }
    distractors = [
        {
            "person_ref": label,
            "bbox_xyxy": people[label].get("bbox_xyxy"),
            "confidence": people[label]["confidence"],
            "reason": people[label].get("reason"),
        }
        for label in sorted(people)
        if label != "target"
    ]
    confidence = _worse_confidence(
        target["confidence"], *[entry["confidence"] for entry in distractors]
    )
    return {
        "frame_index": int(frame_index),
        "t_s": float(t_s),
        "classification": classification,
        "target_bbox_xyxy": target.get("bbox_xyxy"),
        "target_confidence": target["confidence"],
        "distractors": distractors,
        "per_person": people,
        "overall_confidence": confidence,
        "identity_source": "explicit_human_anchor_person_refs_only",
        "accepted": classification == "explicit_anchor",
    }


def _proposal_boxes(frame: dict[str, Any]) -> dict[str, list[float]]:
    boxes: dict[str, list[float]] = {}
    if frame.get("target_bbox_xyxy") is not None:
        boxes["target"] = frame["target_bbox_xyxy"]
    for entry in frame.get("distractors") or []:
        if entry.get("bbox_xyxy") is not None:
            boxes[str(entry["person_ref"])] = entry["bbox_xyxy"]
    return boxes


def compute_review_regions(
    proposals: list[dict[str, Any]],
    effective_previews: list[dict[str, Any]],
    thresholds: dict[str, float] | None = None,
    max_clean_gap_frames: int = 2,
) -> list[dict[str, Any]]:
    """Compare propagation with evaluator preview and group adjacent flags."""

    limits = {**DEFAULT_REVIEW_THRESHOLDS, **(thresholds or {})}
    flagged: list[dict[str, Any]] = []
    for frame, effective in zip(proposals, effective_previews):
        if frame["classification"] in {"explicit_anchor", "explicit_state"}:
            continue
        reasons: list[str] = []
        labels: set[str] = set()
        severity = 0.0
        if frame["overall_confidence"] in {
            CONFIDENCE_REVIEW,
            CONFIDENCE_AMBIGUOUS,
            CONFIDENCE_LOST,
        }:
            reasons.append("low propagation confidence")
        proposed_boxes = _proposal_boxes(frame)
        effective_boxes: dict[str, list[float]] = {}
        if effective.get("target_bbox_xyxy") is not None:
            effective_boxes["target"] = effective["target_bbox_xyxy"]
        effective_boxes.update(
            {
                str(entry["person_ref"]): entry["bbox_xyxy"]
                for entry in effective.get("distractors") or []
            }
        )
        for label in sorted(set(effective_boxes) | set(proposed_boxes)):
            if label not in effective_boxes or label not in proposed_boxes:
                labels.add(label)
                reasons.append(f"{label} geometry unavailable")
                severity = max(severity, 10.0)
                continue
            metrics = bbox_comparison_metrics(
                effective_boxes[label], proposed_boxes[label]
            )
            local_severity = _metrics_severity(metrics, limits)
            if local_severity > 0.0:
                labels.add(label)
                reasons.append(f"{label} interpolation drift")
                severity = max(severity, local_severity)
        if reasons:
            flagged.append(
                {
                    "frame_index": frame["frame_index"],
                    "t_s": frame["t_s"],
                    "labels": sorted(labels),
                    "reasons": sorted(set(reasons)),
                    "severity": float(severity),
                }
            )

    regions: list[list[dict[str, Any]]] = []
    for item in flagged:
        if (
            not regions
            or item["frame_index"] - regions[-1][-1]["frame_index"]
            > max_clean_gap_frames + 1
        ):
            regions.append([item])
        else:
            regions[-1].append(item)
    result = []
    for index, items in enumerate(regions):
        peak = max(items, key=lambda item: item["severity"])
        result.append(
            {
                "region_index": index,
                "start_frame_index": items[0]["frame_index"],
                "end_frame_index": items[-1]["frame_index"],
                "start_t_s": items[0]["t_s"],
                "end_t_s": items[-1]["t_s"],
                "peak_frame_index": peak["frame_index"],
                "peak_t_s": peak["t_s"],
                "labels": sorted({label for item in items for label in item["labels"]}),
                "reasons": sorted({reason for item in items for reason in item["reasons"]}),
                "flagged_frame_count": len(items),
            }
        )
    return result


def suggest_adaptive_anchor_frames(
    proposals: list[dict[str, Any]],
    explicit_anchor_indices: list[int],
    thresholds: dict[str, float] | None = None,
    min_span_frames: int = 12,
    max_suggestions: int = 24,
) -> list[dict[str, Any]]:
    """Recursively split spans at the worst proposal/linear disagreement."""

    limits = {**DEFAULT_REVIEW_THRESHOLDS, **(thresholds or {})}
    by_index = {int(frame["frame_index"]): frame for frame in proposals}
    suggestions: dict[int, dict[str, Any]] = {}

    def inspect_span(left_index: int, right_index: int) -> None:
        if len(suggestions) >= max_suggestions or right_index - left_index < 2 * min_span_frames:
            return
        left_boxes = _proposal_boxes(by_index[left_index])
        right_boxes = _proposal_boxes(by_index[right_index])
        if not left_boxes or set(left_boxes) != set(right_boxes):
            return
        worst: tuple[float, int, list[str]] | None = None
        for frame_index in range(left_index + min_span_frames, right_index - min_span_frames + 1):
            frame = by_index.get(frame_index)
            if frame is None or frame["overall_confidence"] in {
                CONFIDENCE_AMBIGUOUS,
                CONFIDENCE_LOST,
            }:
                continue
            boxes = _proposal_boxes(frame)
            if set(boxes) != set(left_boxes):
                continue
            alpha = (frame_index - left_index) / float(right_index - left_index)
            labels: list[str] = []
            severity = 0.0
            for label in sorted(boxes):
                linear = [
                    (1.0 - alpha) * float(a) + alpha * float(b)
                    for a, b in zip(left_boxes[label], right_boxes[label])
                ]
                metrics = bbox_comparison_metrics(linear, boxes[label])
                local = _metrics_severity(metrics, limits)
                if local > 0.0:
                    labels.append(label)
                    severity = max(severity, local)
            if labels and (worst is None or severity > worst[0]):
                worst = (severity, frame_index, labels)
        if worst is None:
            return
        _, split_index, labels = worst
        frame = by_index[split_index]
        suggestions[split_index] = {
            "frame_index": split_index,
            "t_s": frame["t_s"],
            "labels": labels,
            "confidence": frame["overall_confidence"],
            "all_high_confidence": frame["overall_confidence"] == CONFIDENCE_HIGH,
            "accepted": False,
        }
        inspect_span(left_index, split_index)
        inspect_span(split_index, right_index)

    anchors = sorted(set(int(value) for value in explicit_anchor_indices))
    for left_index, right_index in zip(anchors, anchors[1:]):
        if left_index in by_index and right_index in by_index:
            inspect_span(left_index, right_index)
    return [suggestions[index] for index in sorted(suggestions)]


def sequence_proposal_cache_key(
    artifact_payload: dict[str, Any], times_s: list[float], image_count: int
) -> str:
    material = json.dumps(
        {
            "artifact": artifact_payload,
            "times_s": [float(value) for value in times_s],
            "image_count": int(image_count),
            "method": SEQUENCE_PROPAGATION_METHOD,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def generate_sequence_proposals(
    images: list[np.ndarray],
    times_s: list[float],
    artifact_payload: dict[str, Any],
    anonymous_detections_by_frame: dict[int, list[list[float]]] | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Generate an ephemeral full-sequence proposal cache from human anchors."""

    if len(images) != len(times_s) or not images:
        raise PhysicalReferenceUIError(
            "Loaded source images and frame timestamps must be non-empty and aligned."
        )
    artifact = ptr2.parse_physical_reference(artifact_payload)
    ptr2.validate_physical_reference(artifact)
    payload_snapshot = json.dumps(artifact_payload, sort_keys=True)
    human_anchors = [
        sample
        for sample in artifact.samples
        if sample.identity_state == ptr2.STATE_PRESENT_SCORED
        and sample.target_bbox_xyxy is not None
    ]
    if not human_anchors:
        raise PhysicalReferenceUIError(
            "At least one explicit present_scored human anchor is required."
        )
    gray_images = [cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) for image in images]
    proposals: list[dict[str, Any] | None] = [None] * len(images)
    sample_indices: list[int] = []
    anchor_indices: list[int] = []
    anchor_samples: dict[int, ptr2.PhysicalReferenceSample] = {}
    for sample in artifact.samples:
        index = _frame_index_for_time(times_s, sample.t_s)
        sample_indices.append(index)
        anchor_samples[index] = sample
        if sample.identity_state == ptr2.STATE_PRESENT_SCORED:
            anchor_indices.append(index)
            people = {
                label: {
                    "bbox_xyxy": box,
                    "confidence": CONFIDENCE_HIGH,
                    "reason": "explicit_human_anchor",
                }
                for label, box in _boxes_from_sample(sample).items()
            }
            proposals[index] = _serialize_proposal_frame(
                index, times_s[index], people, "explicit_anchor"
            )
        else:
            proposals[index] = _serialize_proposal_frame(
                index,
                times_s[index],
                {
                    "target": {
                        "bbox_xyxy": None,
                        "confidence": CONFIDENCE_LOST,
                        "reason": f"explicit_human_state_{sample.identity_state}",
                    }
                },
                "explicit_state",
            )

    sample_indices = sorted(set(sample_indices))
    anchor_indices = sorted(set(anchor_indices))

    def supported_span(left_index: int, right_index: int) -> bool:
        left = anchor_samples[left_index]
        right = anchor_samples[right_index]
        return bool(
            left.identity_state == ptr2.STATE_PRESENT_SCORED
            and right.identity_state == ptr2.STATE_PRESENT_SCORED
            and right.interpolate_from_previous
            and set(_boxes_from_sample(left)) == set(_boxes_from_sample(right))
        )

    supported_step_count = sum(
        2 * (right_index - left_index)
        for left_index, right_index in zip(sample_indices, sample_indices[1:])
        if supported_span(left_index, right_index)
    )
    completed_steps = 0

    def on_step() -> None:
        nonlocal completed_steps
        completed_steps += 1
        if progress_callback is not None:
            progress_callback(completed_steps, max(1, supported_step_count))

    for left_index, right_index in zip(sample_indices, sample_indices[1:]):
        left_sample = anchor_samples[left_index]
        right_sample = anchor_samples[right_index]
        left_boxes = (
            _boxes_from_sample(left_sample)
            if left_sample.identity_state == ptr2.STATE_PRESENT_SCORED
            else {}
        )
        right_boxes = (
            _boxes_from_sample(right_sample)
            if right_sample.identity_state == ptr2.STATE_PRESENT_SCORED
            else {}
        )
        if not supported_span(left_index, right_index):
            labels = sorted(set(left_boxes) | set(right_boxes) | {"target"})
            for frame_index in range(left_index + 1, right_index):
                people = {
                    label: {
                        "bbox_xyxy": None,
                        "confidence": CONFIDENCE_LOST,
                        "reason": "human_correspondence_confirmation_required",
                    }
                    for label in labels
                }
                proposals[frame_index] = _serialize_proposal_frame(
                    frame_index, times_s[frame_index], people, "unsupported_reference_span"
                )
            continue
        forward = _propagate_direction(
            gray_images,
            left_index,
            right_index,
            left_boxes,
            anonymous_detections_by_frame,
            on_step,
        )
        backward = _propagate_direction(
            gray_images,
            right_index,
            left_index,
            right_boxes,
            anonymous_detections_by_frame,
            on_step,
        )
        for frame_index in range(left_index + 1, right_index):
            alpha = (frame_index - left_index) / float(right_index - left_index)
            people = _merge_directional_people(
                forward.get(frame_index), backward.get(frame_index), alpha
            )
            proposals[frame_index] = _serialize_proposal_frame(
                frame_index, times_s[frame_index], people, "automatic_proposal"
            )

    for frame_index, proposal in enumerate(proposals):
        if proposal is None:
            proposals[frame_index] = _serialize_proposal_frame(
                frame_index,
                times_s[frame_index],
                {
                    "target": {
                        "bbox_xyxy": None,
                        "confidence": CONFIDENCE_LOST,
                        "reason": "outside_human_anchor_span",
                    }
                },
                "outside_human_anchor_span",
            )

    final_proposals = [proposal for proposal in proposals if proposal is not None]
    effective = build_effective_reference_previews(artifact_payload, times_s)
    regions = compute_review_regions(final_proposals, effective)
    suggestions = suggest_adaptive_anchor_frames(
        final_proposals, anchor_indices
    )
    if json.dumps(artifact_payload, sort_keys=True) != payload_snapshot:
        raise AssertionError("Sequence proposal generation mutated its artifact input.")
    return {
        "method": SEQUENCE_PROPAGATION_METHOD,
        "identity_source": "explicit_human_anchor_person_refs_only",
        "detector_refinement_used": bool(anonymous_detections_by_frame),
        "frame_count": len(final_proposals),
        "source_anchor_frames": anchor_indices,
        "proposals": final_proposals,
        "review_regions": regions,
        "suggested_anchors": suggestions,
        "accepted": False,
        "saved": False,
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
