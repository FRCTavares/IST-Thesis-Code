#!/usr/bin/env python3
"""Backend helpers for the Issue #25 physical-reference bbox annotation mode.

This module is a thin adapter between the annotation UI and
``tools/analysis/physical_target_reference.py`` -- it does not duplicate
schema parsing/validation/serialization; it only converts between the UI's
JSON request/response shapes and that module's dataclasses, and provides
the one piece of new pure logic the UI genuinely needs: normalising a
mouse-drawn rectangle (reverse-drag direction, zero-area rejection).

Coordinate mapping from browser display pixels to source-image pixels
happens client-side (the canvas's internal pixel buffer is set to the
source image's native width/height, so a mouse event's canvas-buffer
coordinates already are source-image coordinates -- see
tim_physical_reference_ui.js). This module's normalize_rect() is the
backend-side safety net applied to whatever rectangle the frontend
submits, before physical_target_reference.py's own bounds validation runs.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_reference as ptr  # noqa: E402


PHYSICAL_REFERENCE_ROOT = "docs/data/physical_target_references"


class PhysicalReferenceUIError(ValueError):
    """Raised for any UI-facing physical-reference request error."""


def safe_physical_reference_relpath(path_text: str) -> Path:
    """Validate a physical-reference JSON path relative to the repository
    root, mirroring tim_ui_annotations.safe_annotation_relpath."""

    rel = Path(str(path_text).strip())

    if rel.is_absolute():
        raise PhysicalReferenceUIError("Path must be relative to repository root")
    if ".." in rel.parts:
        raise PhysicalReferenceUIError("Path cannot contain '..'")
    if rel.suffix.lower() != ".json":
        raise PhysicalReferenceUIError("Path must end with .json")
    if not str(rel).startswith(f"{PHYSICAL_REFERENCE_ROOT}/"):
        raise PhysicalReferenceUIError(
            f"Path must be under {PHYSICAL_REFERENCE_ROOT}/"
        )

    return rel


def normalize_rect(
    x1: float, y1: float, x2: float, y2: float
) -> tuple[float, float, float, float] | None:
    """Normalise a mouse-drawn rectangle to (x1, y1, x2, y2) with x1<x2 and
    y1<y2, regardless of drag direction. Returns None for a zero-area (or
    inverted-to-zero) box -- the caller must reject, not save, that case."""

    lo_x, hi_x = (x1, x2) if x1 <= x2 else (x2, x1)
    lo_y, hi_y = (y1, y2) if y1 <= y2 else (y2, y1)

    if hi_x <= lo_x or hi_y <= lo_y:
        return None

    return (float(lo_x), float(lo_y), float(hi_x), float(hi_y))


def load_physical_reference_for_ui(path_text: str, repo_root: Path) -> dict[str, Any]:
    """Load and validate a physical-reference artifact for UI population."""

    rel = safe_physical_reference_relpath(path_text)
    path = repo_root / rel

    if not path.exists():
        raise PhysicalReferenceUIError(f"Physical reference does not exist: {rel}")

    artifact = ptr.load_physical_reference(path)
    return {"path": str(rel), **ptr.serialize_physical_reference(artifact)}


def save_physical_reference_for_ui(
    path_text: str, payload: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Validate (backend-authoritative) and atomically save a
    physical-reference artifact constructed by the UI.

    ``payload`` must already have the shape produced by
    physical_target_reference.serialize_physical_reference (i.e. a
    "provenance" dict and a "samples" list). Invalid payloads raise
    PhysicalReferenceUIError / physical_target_reference.PhysicalReferenceValidationError
    and are never written.
    """

    rel = safe_physical_reference_relpath(path_text)
    path = repo_root / rel

    artifact = ptr.parse_physical_reference(payload)
    ptr.validate_physical_reference(artifact)

    ptr.write_physical_reference(path, artifact)

    return {
        "path": str(rel),
        "sample_count": len(artifact.samples),
        **ptr.serialize_physical_reference(artifact),
    }


def discover_physical_references(repo_root: Path | str = ".") -> list[str]:
    repo_root = Path(repo_root)
    root = repo_root / PHYSICAL_REFERENCE_ROOT
    if not root.exists():
        return []

    out = []
    for json_path in sorted(root.rglob("*.json")):
        try:
            rel = str(json_path.relative_to(repo_root))
        except ValueError:
            rel = str(json_path)
        out.append(rel)
    return out


def image_topic_hint(bag_path: Path) -> str | None:
    """Best-effort label of which camera topic this bag's displayed frames
    most likely came from, for provenance display only -- never used to
    redecide which frames tim_ui_bag_cache.load_bag_cache actually loads."""

    try:
        import rosbag2_py

        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
            rosbag2_py.ConverterOptions(
                input_serialization_format="cdr", output_serialization_format="cdr"
            ),
        )
        topics = {t.name for t in reader.get_all_topics_and_types()}
    except Exception:
        return None

    if "/camera/image_raw" in topics:
        return "/camera/image_raw"
    if "/camera/dashboard" in topics:
        return "/camera/dashboard"
    return None


# --- Coordinate-convention auto-resolution ----------------------------------
#
# Issue #53's tim_mars_source_pixels_resize_v1 contract closed on this date.
# Any bag whose own capture date (embedded in its directory name, per this
# repository's established RUN_ID convention YYYY-MM-DD__HH-MM-SS__...)
# predates this date cannot carry that contract's header -- it did not exist
# yet -- so source_pixels_historical_pre_p53 is not a guess for such a bag,
# it is a logical certainty given a genuine embedded date. This is the same
# rule already verified by direct header inspection for the May hard-reentry
# sequence in docs/issues/p1-10-improve-bbox-evaluation.md section F.
P53_CONTRACT_CLOSURE_DATE = date(2026, 7, 22)

_MODERN_CONTRACT_HEADER_PREFIX = "tim_mars_source_pixels_resize_v1"
_BAG_DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _extract_bag_capture_date(bag_path: str) -> date | None:
    """Best-effort extraction of a YYYY-MM-DD capture date embedded in the
    bag's own directory name."""

    name = Path(bag_path).name
    match = _BAG_DATE_PATTERN.search(name) or _BAG_DATE_PATTERN.search(str(bag_path))
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _detections_header_frame_id(bag_path: str) -> str | None:
    """Best-effort read of the first /detections header.frame_id, used only
    to check for the modern contract string -- never to guess a resolution
    when it is absent (absence is not evidence of the historical case)."""

    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message

        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
            rosbag2_py.ConverterOptions(
                input_serialization_format="cdr", output_serialization_format="cdr"
            ),
        )
        topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
        if "/detections" not in topic_types:
            return None
        msg_type = get_message(topic_types["/detections"])
        while reader.has_next():
            topic, data, _t = reader.read_next()
            if topic == "/detections":
                msg = deserialize_message(data, msg_type)
                return str(msg.header.frame_id)
    except Exception:
        return None
    return None


def resolve_coordinate_convention(bag_path: str) -> dict[str, str | None] | None:
    """Deterministically resolve a bag's coordinate_convention and, where
    applicable, its required historical evidence.

    Returns None when resolution is not deterministic -- callers (the UI)
    must never silently substitute a default in that case; the annotator
    must choose deliberately. This never overrides
    docs/issues/p1-10-improve-bbox-evaluation.md section E/F's frozen
    coordinate semantics; it only decides which of the two frozen values
    applies to a given source.
    """

    capture_date = _extract_bag_capture_date(bag_path)
    if capture_date is not None and capture_date < P53_CONTRACT_CLOSURE_DATE:
        return {
            "coordinate_convention": "source_pixels_historical_pre_p53",
            "coordinate_convention_evidence": (
                f"Bag directory name embeds capture date {capture_date.isoformat()}, "
                "before Issue #53's tim_mars_source_pixels_resize_v1 contract "
                f"closed on {P53_CONTRACT_CLOSURE_DATE.isoformat()}; a bag captured "
                "on this date cannot carry that header. Automatically resolved by "
                "tools/bag_annotation_ui/tim_ui_physical_reference.py"
                ".resolve_coordinate_convention; see "
                "docs/issues/p1-10-improve-bbox-evaluation.md section F for the "
                "May hard-reentry sequence's direct header-inspection confirmation "
                "of this same rule."
            ),
        }

    header = _detections_header_frame_id(bag_path)
    if header and header.startswith(_MODERN_CONTRACT_HEADER_PREFIX):
        return {
            "coordinate_convention": "source_pixels_p53_contract",
            "coordinate_convention_evidence": None,
        }

    return None
