#!/usr/bin/env python3
"""Annotation CSV helpers for the TIM-MARS clean annotation UI."""

from __future__ import annotations

import csv
from pathlib import Path


ANNOTATION_FIELDS = [
    "bag_name",
    "start_s",
    "end_s",
    "target_label",
    "target_visible",
    "correct_target_track_id",
    "distractor_track_ids",
    "event_type",
    "notes",
]

ANNOTATION_EVENT_TYPES = [
    ("clean_visible", "Clean visible"),
    ("target_absent", "Target absent"),
    ("reentry", "Re-entry"),
    ("occlusion_ambiguity", "Occlusion / ambiguity"),
    ("id_switch_fragmentation", "ID switch / fragmentation"),
    ("other", "Other"),
]

ANNOTATION_EVENT_VALUES = {value for value, _label in ANNOTATION_EVENT_TYPES}

LEGACY_EVENT_TYPE_MAP = {
    "manual_interval": "clean_visible",
    "visible_id_interval": "clean_visible",
    "target_not_visible": "target_absent",
    "not_visible": "target_absent",
    "occlusion": "occlusion_ambiguity",
    "crossing_ambiguity": "occlusion_ambiguity",
    "distractor_confusion": "occlusion_ambiguity",
}


def safe_annotation_relpath(path_text: str) -> Path:
    """Validate an annotation CSV path relative to the repository root."""
    rel = Path(str(path_text).strip())

    if rel.is_absolute():
        raise ValueError("Annotation path must be relative to repository root")
    if ".." in rel.parts:
        raise ValueError("Annotation path cannot contain '..'")
    if rel.suffix.lower() != ".csv":
        raise ValueError("Annotation path must end with .csv")
    if not str(rel).startswith("docs/data/annotations/"):
        raise ValueError("Annotation path must be under docs/data/annotations/")

    return rel


def load_annotation_rows(path_text: str, repo_root: Path) -> tuple[Path, list[dict[str, str]]]:
    """Load annotation intervals from a repository-relative CSV path."""
    rel = safe_annotation_relpath(path_text)
    path = repo_root / rel

    if not path.exists():
        raise FileNotFoundError(f"Annotation does not exist: {rel}")

    rows: list[dict[str, str]] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {field: str(row.get(field, "") or "").strip() for field in ANNOTATION_FIELDS}
            clean["event_type"] = LEGACY_EVENT_TYPE_MAP.get(clean["event_type"], clean["event_type"])
            rows.append(clean)

    return rel, rows


def normalise_annotation_rows(rows: list[dict]) -> list[dict[str, str]]:
    """Validate and normalise annotation rows before saving."""
    normalised: list[dict[str, str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        clean = {field: str(row.get(field, "")).strip() for field in ANNOTATION_FIELDS}

        try:
            start_s = float(clean["start_s"])
            end_s = float(clean["end_s"])
        except ValueError as exc:
            raise ValueError(f"Invalid interval times: {clean}") from exc

        if end_s <= start_s:
            raise ValueError(f"Invalid interval with end <= start: {clean}")

        label = clean["target_label"].strip().upper() or "CORRECT_TARGET"
        clean["target_label"] = label

        visible = clean["target_visible"].strip().lower()
        if visible in {"true", "1", "yes", "y"}:
            clean["target_visible"] = "true"
        elif visible in {"false", "0", "no", "n"}:
            clean["target_visible"] = "false"
        else:
            clean["target_visible"] = "true" if label == "CORRECT_TARGET" else "false"

        event_type = clean["event_type"].strip()
        event_type = LEGACY_EVENT_TYPE_MAP.get(event_type, event_type)
        if event_type not in ANNOTATION_EVENT_VALUES:
            event_type = "target_absent" if clean["target_visible"] == "false" else "clean_visible"

        # Invisible rows may still be occlusion/ambiguity when the physical
        # target is hidden but still in-scene. Only force labels that require a
        # visible tracked target into target_absent.
        if clean["target_visible"] == "false" and event_type in {
            "clean_visible",
            "id_switch_fragmentation",
            "reentry",
        }:
            event_type = "target_absent"

        clean["event_type"] = event_type

        if label in {"NO_TARGET_SELECTED", "TARGET_NOT_VISIBLE"}:
            clean["target_visible"] = "false"
            clean["event_type"] = "target_absent"

        normalised.append(clean)

    normalised.sort(key=lambda r: (float(r["start_s"]), float(r["end_s"])))
    return normalised


def save_annotation_rows(path_text: str, rows: list[dict], repo_root: Path) -> tuple[Path, list[dict[str, str]]]:
    """Validate and save annotation intervals to a repository-relative CSV path."""
    rel = safe_annotation_relpath(path_text)
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)

    normalised = normalise_annotation_rows(rows)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(normalised)

    return rel, normalised
