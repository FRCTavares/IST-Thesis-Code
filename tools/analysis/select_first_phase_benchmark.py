#!/usr/bin/env python3
"""Deterministic pre-outcome selection for the Issue #30 first benchmark phase.

Selects DanceTrack and VisDrone-MOT validation sequences and their physical
target candidates using only annotation-derived facts already computed by
``profile_external_tracking_dataset``. No tracker or TIM-MARS outcome is
inspected anywhere in this module.

This module also renders the selected sequences into
``sequence_manifest.json`` entries validated against
``manifest.schema.json``. It does not itself set the manifest root status to
``frozen``; the freeze is a deliberate separate step performed once every
benchmark phase (including the internal ROS 2 sequences) is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from external_sequence_selection import SelectionPolicy
from profile_external_tracking_dataset import (
    profile_external_tracking_dataset,
)
from validate_external_dataset_sources import load_registry


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT / "docs" / "data" / "external_benchmark" / "dataset_sources.json"
)
DEFAULT_MANIFEST = (
    ROOT / "docs" / "data" / "external_benchmark" / "sequence_manifest.json"
)
DEFAULT_SCHEMA = (
    ROOT / "docs" / "data" / "external_benchmark" / "manifest.schema.json"
)

# Frozen initialization-matching defaults from
# tools/analysis/external_target_initialization.py InitializationConfig.
INITIALIZATION_MINIMUM_IOU = 0.50
INITIALIZATION_MINIMUM_MARGIN = 0.10
INITIALIZATION_CONFIRMATION_FRAMES = 2

ADAPTER_SCHEMA_VERSION = 1


def eligible_candidates(
    sequence: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in sequence["candidates"]
        if candidate["eligible"] and candidate["initialization_eligible"]
    ]


def stratified_selection(
    sequences: list[dict[str, Any]],
    *,
    count: int,
) -> list[dict[str, Any]]:
    """Deterministically pick ``count`` sequences spread across crowd density.

    Sequences are ordered by (candidate_count, sequence_name) to give a
    reproducible density ranking, then ``count`` evenly spaced positions are
    taken across that ranking so the selection spans low- to high-density
    scenes rather than clustering at one end. This uses only the annotated
    candidate_count and never a tracker or TIM-MARS outcome.
    """

    if count <= 0:
        raise ValueError("count must be positive")

    ordered = sorted(
        sequences,
        key=lambda item: (
            item["candidate_count"],
            item["sequence_name"],
        ),
    )

    total = len(ordered)

    if count > total:
        raise ValueError(
            f"cannot select {count} sequences from {total} available"
        )

    if count == 1:
        positions = [0]
    else:
        positions = [
            round(index * (total - 1) / (count - 1))
            for index in range(count)
        ]

    seen: set[int] = set()
    picked: list[dict[str, Any]] = []

    for position in positions:
        while position in seen:
            position += 1
        seen.add(position)
        picked.append(ordered[position])

    return sorted(
        picked,
        key=lambda item: item["sequence_name"],
    )


def select_physical_target(
    sequence: dict[str, Any],
) -> dict[str, Any]:
    """Pick the physical target candidate using duration facts only.

    The eligible, initialization-eligible candidate with the greatest total
    visible-frame count is selected, breaking ties by the longest
    consecutive visible run and then by the lowest dataset identity. This is
    an availability rule, not a difficulty or outcome preference.
    """

    candidates = eligible_candidates(sequence)

    if not candidates:
        raise ValueError(
            f"{sequence['sequence_name']}: no eligible "
            "initialization candidate"
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate["visible_frame_count"],
            -candidate["longest_consecutive_run"],
            candidate["identity"],
        ),
    )[0]


def classify_scene(
    sequence: dict[str, Any],
    candidate: dict[str, Any],
    *,
    dataset_id: str,
) -> tuple[int, str, list[str]]:
    """Derive scene facts and event-category tags from annotation stats only."""

    visible = max(candidate["visible_frame_count"], 1)
    overlap_ratio = candidate["overlapping_person_frames"] / visible
    border_ratio = candidate["border_touch_frames"] / visible

    event_categories: list[str] = []

    if overlap_ratio >= 0.30:
        event_categories.append("crowd_crossing")
        primary_challenge = "crowd_crossing"
    elif border_ratio >= 0.20:
        event_categories.append("partial_crop")
        primary_challenge = "partial_crop"
    else:
        primary_challenge = "moderate_visibility_tracking"

    if candidate["median_height_px"] < 60.0:
        event_categories.append("small_target")

    if dataset_id == "visdrone_mot":
        event_categories.append("camera_motion")

    if dataset_id == "dancetrack":
        event_categories.append("similar_clothing")
        event_categories.append("appearance_ambiguity")

    if not event_categories:
        event_categories.append("clean_tracking")

    return (
        sequence["candidate_count"],
        primary_challenge,
        sorted(set(event_categories)),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def current_repository_commit(*, repository_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    commit = result.stdout.strip()
    return commit or None


def build_manifest_entry(
    *,
    dataset_id: str,
    split: str,
    sequence: dict[str, Any],
    candidate: dict[str, Any],
    dataset_registry_entry: dict[str, Any],
    repository_root: Path,
    repository_commit: Optional[str],
) -> dict[str, Any]:
    approximate_people, primary_challenge, event_categories = classify_scene(
        sequence,
        candidate,
        dataset_id=dataset_id,
    )

    timing = sequence["timing_contract"]
    image_count = sequence["image_count"]
    source_index_base = dataset_registry_entry["source_frame_index_base"]

    acquisitions = {
        acquisition["split"]: acquisition
        for acquisition in dataset_registry_entry["acquisitions"]
    }
    acquisition = acquisitions[split]

    annotation_path = (
        repository_root / sequence["annotation_relative_path"]
    )
    annotation_sha256 = sha256_file(annotation_path)

    camera_motion = "moving" if dataset_id == "visdrone_mot" else "unknown"

    return {
        "id": f"{dataset_id}_{split}_{sequence['sequence_name']}",
        "dataset": dataset_id,
        "sequence_name": sequence["sequence_name"],
        "split": split,
        "role": "external_stress_test",
        "status": "selected",
        "source": {
            "official_reference": dataset_registry_entry[
                "official_reference"
            ],
            "local_relative_path": sequence["source_relative_path"],
            "version": f"{split}:{acquisition['verified_date']}",
            "archive_sha256": acquisition["archive_sha256"],
        },
        "frame_contract": {
            "source_index_base": source_index_base,
            "source_start_frame": source_index_base,
            "source_end_frame_inclusive": (
                source_index_base + image_count - 1
            ),
            "normalized_start_index": 0,
            "normalized_end_index_inclusive": image_count - 1,
            "frame_rate": timing["analysis_frame_rate_hz"],
        },
        "image": {
            "width": sequence["image_width"],
            "height": sequence["image_height"],
            "camera_motion": camera_motion,
        },
        "target": {
            "dataset_identity": candidate["identity"],
            "initialization_start_frame": candidate[
                "initialization_start_frame"
            ],
            "initialization_end_frame_inclusive": candidate[
                "initialization_end_frame_inclusive"
            ],
            "initialization_rule": (
                "physical_identity_selected_by_max_visible_frame_count_"
                "among_eligible_annotation_candidates_v1"
            ),
            "candidate_match_rule": (
                "frozen_target_unique_iou_confirmation_v1"
            ),
            "minimum_match_iou": INITIALIZATION_MINIMUM_IOU,
            "minimum_match_margin": INITIALIZATION_MINIMUM_MARGIN,
            "confirmation_frames": INITIALIZATION_CONFIRMATION_FRAMES,
            "initial_tracker_identity": None,
            "fixed_after_initialization": True,
            "reselection_enabled": False,
            "minimum_visible_frames": SelectionPolicy().minimum_visible_frames,
            "selected_before_outcome_review": True,
        },
        "scene": {
            "approximate_people": approximate_people,
            "primary_challenge": primary_challenge,
        },
        "event_categories": event_categories,
        "evaluation_modes": [
            "oracle_candidate",
            "detector_bytetrack_tim",
        ],
        "selection_reason": (
            "Selected by stratified candidate_count density sampling across "
            f"the {dataset_id}:{split} catalogue (annotation-derived crowd "
            "density proxy only); physical target chosen as the eligible, "
            "initialization-eligible candidate with the greatest total "
            "visible-frame count. No tracker or TIM-MARS outcome was "
            "inspected."
        ),
        "exclusions": [],
        "provenance": {
            "adapter": "external_tracking_dataset.py",
            "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
            "annotation_sha256": annotation_sha256,
            "repository_commit": repository_commit,
        },
    }


def select_dataset_sequences(
    *,
    registry: dict[str, Any],
    repository_root: Path,
    dataset_id: str,
    split: str,
    explicit_frame_rate: Optional[float],
    select_count: int,
    repository_commit: Optional[str],
) -> list[dict[str, Any]]:
    payload = profile_external_tracking_dataset(
        registry,
        repository_root=repository_root,
        dataset_id=dataset_id,
        split=split,
        explicit_frame_rate=explicit_frame_rate,
        policy=SelectionPolicy(),
    )

    if payload["error_count"]:
        raise ValueError(
            f"{dataset_id}:{split} profiling errors: {payload['errors']}"
        )

    candidate_sequences = [
        sequence
        for sequence in payload["sequences"]
        if eligible_candidates(sequence)
    ]

    chosen_sequences = stratified_selection(
        candidate_sequences,
        count=select_count,
    )

    dataset_registry_entry = next(
        dataset
        for dataset in registry["datasets"]
        if dataset["id"] == dataset_id
    )

    entries = []

    for sequence in chosen_sequences:
        candidate = select_physical_target(sequence)
        entries.append(
            build_manifest_entry(
                dataset_id=dataset_id,
                split=split,
                sequence=sequence,
                candidate=candidate,
                dataset_registry_entry=dataset_registry_entry,
                repository_root=repository_root,
                repository_commit=repository_commit,
            )
        )

    return entries


def merge_manifest_entries(
    manifest: dict[str, Any],
    new_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    new_ids = {entry["id"] for entry in new_entries}
    kept = [
        entry
        for entry in manifest["sequences"]
        if entry["id"] not in new_ids
    ]
    manifest = dict(manifest)
    manifest["sequences"] = kept + new_entries
    return manifest


def validate_against_schema(
    manifest: dict[str, Any],
    *,
    schema_path: Path,
) -> None:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=manifest, schema=schema)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--repository-root", type=Path, default=ROOT
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--dancetrack-count", type=int, default=5)
    parser.add_argument("--visdrone-count", type=int, default=4)
    parser.add_argument(
        "--visdrone-frame-rate",
        type=float,
        default=24.0,
    )
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    registry = load_registry(arguments.registry)
    repository_root = arguments.repository_root.resolve()
    repository_commit = current_repository_commit(
        repository_root=repository_root
    )

    dancetrack_entries = select_dataset_sequences(
        registry=registry,
        repository_root=repository_root,
        dataset_id="dancetrack",
        split="val",
        explicit_frame_rate=None,
        select_count=arguments.dancetrack_count,
        repository_commit=repository_commit,
    )

    visdrone_entries = select_dataset_sequences(
        registry=registry,
        repository_root=repository_root,
        dataset_id="visdrone_mot",
        split="val",
        explicit_frame_rate=arguments.visdrone_frame_rate,
        select_count=arguments.visdrone_count,
        repository_commit=repository_commit,
    )

    all_entries = dancetrack_entries + visdrone_entries

    manifest = json.loads(
        arguments.manifest.read_text(encoding="utf-8")
    )
    manifest = merge_manifest_entries(manifest, all_entries)
    manifest["sequences"] = sorted(
        manifest["sequences"],
        key=lambda entry: entry["id"],
    )

    validate_against_schema(manifest, schema_path=arguments.schema)

    rendered = json.dumps(manifest, indent=2, sort_keys=False) + "\n"

    if arguments.write:
        arguments.manifest.write_text(rendered, encoding="utf-8")
        print(f"wrote {len(all_entries)} entries to {arguments.manifest}")
    else:
        print(rendered)

    for entry in all_entries:
        print(
            f"selected {entry['id']}: identity="
            f"{entry['target']['dataset_identity']} "
            f"people~={entry['scene']['approximate_people']} "
            f"challenge={entry['scene']['primary_challenge']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
