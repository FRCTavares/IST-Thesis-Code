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
import sys
from pathlib import Path
from typing import Any

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_reference_v2 as ptr2  # noqa: E402

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
