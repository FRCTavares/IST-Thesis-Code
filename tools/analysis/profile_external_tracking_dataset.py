#!/usr/bin/env python3
"""Produce deterministic annotation-only external-dataset profiles.

The profiler reports source, sequence and physical-target candidate facts.
It does not inspect tracker, TIM-MARS, recovery or evaluation outcomes and
does not select or freeze benchmark cases.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from catalogue_external_tracking_dataset import (
    LocalSequenceRecord,
    canonical_records,
    catalogue_local_datasets,
)
from external_sequence_selection import (
    SelectionPolicy,
    analyse_target_candidates,
)
from external_tracking_dataset import (
    ExternalObjectAnnotation,
    SequenceGeometry,
    parse_dancetrack_annotations,
    parse_mot_sequence_metadata,
    parse_motchallenge_annotations,
    parse_visdrone_annotations,
    validate_annotations_against_metadata,
)
from validate_external_dataset_sources import (
    load_registry,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "dataset_sources.json"
)

PROFILE_SCHEMA_VERSION = 1

FORBIDDEN_OUTCOME_FIELDS = {
    "correct_target_ratio",
    "wrong_target_ratio",
    "tim_score",
    "recovery_count",
    "lost_target_duration",
    "tracker_identity",
    "initial_tracker_identity",
}


def read_image_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG or JPEG dimensions without decoding the image."""

    with path.open("rb") as handle:
        header = handle.read(24)

        if (
            len(header) >= 24
            and header[:8] == b"\x89PNG\r\n\x1a\n"
            and header[12:16] == b"IHDR"
        ):
            width = int.from_bytes(header[16:20], "big")
            height = int.from_bytes(header[20:24], "big")

            if width <= 0 or height <= 0:
                raise ValueError(
                    f"{path}: invalid PNG dimensions"
                )

            return width, height

        handle.seek(0)

        if handle.read(2) != b"\xff\xd8":
            raise ValueError(
                f"{path}: unsupported image format; expected PNG or JPEG"
            )

        start_of_frame_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }

        while True:
            prefix = handle.read(1)

            if not prefix:
                break

            if prefix != b"\xff":
                continue

            marker_raw = handle.read(1)

            while marker_raw == b"\xff":
                marker_raw = handle.read(1)

            if not marker_raw:
                break

            marker = marker_raw[0]

            if marker in {
                0x01,
                0xD8,
                0xD9,
                0xD0,
                0xD1,
                0xD2,
                0xD3,
                0xD4,
                0xD5,
                0xD6,
                0xD7,
            }:
                continue

            length_raw = handle.read(2)

            if len(length_raw) != 2:
                break

            segment_length = int.from_bytes(
                length_raw,
                "big",
            )

            if segment_length < 2:
                raise ValueError(
                    f"{path}: invalid JPEG segment length"
                )

            if marker in start_of_frame_markers:
                payload = handle.read(5)

                if len(payload) != 5:
                    break

                height = int.from_bytes(payload[1:3], "big")
                width = int.from_bytes(payload[3:5], "big")

                if width <= 0 or height <= 0:
                    raise ValueError(
                        f"{path}: invalid JPEG dimensions"
                    )

                return width, height

            handle.seek(segment_length - 2, 1)

    raise ValueError(
        f"{path}: JPEG dimensions were not found"
    )


def first_image_path(
    record: LocalSequenceRecord,
    *,
    repository_root: Path,
) -> Path:
    image_directory = (
        repository_root
        / record.image_directory_relative_path
    )

    if not image_directory.is_dir():
        raise FileNotFoundError(
            f"image directory missing: "
            f"{record.image_directory_relative_path}"
        )

    image_files = sorted(
        path
        for path in image_directory.iterdir()
        if path.is_file()
    )

    if not image_files:
        raise ValueError(
            f"{record.dataset}:{record.split}:"
            f"{record.sequence_name}: no source images"
        )

    return image_files[0]


def verified_acquisition(
    registry: dict[str, Any],
    *,
    dataset_id: str,
    split: str,
) -> dict[str, Any]:
    dataset = next(
        (
            item
            for item in registry["datasets"]
            if item["id"] == dataset_id
        ),
        None,
    )

    if dataset is None:
        raise ValueError(
            f"unknown dataset: {dataset_id}"
        )

    if split not in dataset["admissible_splits"]:
        raise ValueError(
            f"{dataset_id}:{split}: split is not admissible"
        )

    acquisition = next(
        (
            item
            for item in dataset["acquisitions"]
            if item["split"] == split
            and item["status"] == "verified"
        ),
        None,
    )

    if acquisition is None:
        raise ValueError(
            f"{dataset_id}:{split}: split is not recorded "
            "as a verified acquisition"
        )

    return dataset


def resolve_frame_rate(
    record: LocalSequenceRecord,
    *,
    explicit_frame_rate: Optional[float],
) -> tuple[float, str]:
    if (
        explicit_frame_rate is not None
        and (
            not math.isfinite(explicit_frame_rate)
            or explicit_frame_rate <= 0.0
        )
    ):
        raise ValueError(
            "explicit frame rate must be finite and positive"
        )

    if record.frame_rate is not None:
        if (
            explicit_frame_rate is not None
            and not math.isclose(
                explicit_frame_rate,
                record.frame_rate,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise ValueError(
                f"{record.dataset}:{record.split}:"
                f"{record.sequence_name}: explicit frame rate "
                "does not match source metadata"
            )

        return record.frame_rate, "source_sequence_metadata"

    if explicit_frame_rate is None:
        raise ValueError(
            f"{record.dataset}:{record.split}:"
            f"{record.sequence_name}: source metadata does not "
            "provide a frame rate; pass --frame-rate explicitly"
        )

    return explicit_frame_rate, "explicit_cli_unfrozen"


def load_sequence_annotations(
    record: LocalSequenceRecord,
    *,
    dataset_source: dict[str, Any],
    repository_root: Path,
    explicit_frame_rate: Optional[float],
) -> tuple[
    list[ExternalObjectAnnotation],
    int,
    int,
    float,
    str,
    str,
]:
    annotation_path = (
        repository_root
        / record.annotation_relative_path
    )

    source_index_base = dataset_source[
        "source_frame_index_base"
    ]

    frame_rate, frame_rate_source = resolve_frame_rate(
        record,
        explicit_frame_rate=explicit_frame_rate,
    )

    if record.dataset in {
        "mot17",
        "dancetrack",
    }:
        if record.metadata_relative_path is None:
            raise ValueError(
                f"{record.dataset}:{record.split}:"
                f"{record.sequence_name}: metadata path is absent"
            )

        metadata_path = (
            repository_root
            / record.metadata_relative_path
        )
        metadata = parse_mot_sequence_metadata(
            metadata_path
        )
        geometry = metadata.geometry(
            source_index_base=source_index_base
        )

        if record.dataset == "mot17":
            annotations = parse_motchallenge_annotations(
                annotation_path,
                dataset="mot17",
                sequence_name=record.sequence_name,
                split=record.split,
                geometry=geometry,
                person_class_ids={1},
            )
        else:
            annotations = parse_dancetrack_annotations(
                annotation_path,
                sequence_name=record.sequence_name,
                split=record.split,
                geometry=geometry,
            )

        annotations = validate_annotations_against_metadata(
            annotations,
            metadata,
        )

        return (
            annotations,
            metadata.image_width,
            metadata.image_height,
            metadata.frame_rate,
            frame_rate_source,
            record.metadata_relative_path,
        )

    if record.dataset != "visdrone_mot":
        raise ValueError(
            f"unsupported dataset: {record.dataset}"
        )

    first_image = first_image_path(
        record,
        repository_root=repository_root,
    )
    image_width, image_height = read_image_dimensions(
        first_image
    )

    geometry = SequenceGeometry(
        image_width=image_width,
        image_height=image_height,
        frame_rate=frame_rate,
        source_index_base=source_index_base,
    )

    annotations = parse_visdrone_annotations(
        annotation_path,
        sequence_name=record.sequence_name,
        split=record.split,
        geometry=geometry,
    )

    sequence_length = record.sequence_length

    if sequence_length is None or sequence_length <= 0:
        raise ValueError(
            f"{record.dataset}:{record.split}:"
            f"{record.sequence_name}: sequence length is absent"
        )

    for annotation in annotations:
        if annotation.normalized_frame_index >= sequence_length:
            raise ValueError(
                f"{record.dataset}:{record.split}:"
                f"{record.sequence_name}: annotation frame exceeds "
                f"sequence length: "
                f"{annotation.normalized_frame_index} >= "
                f"{sequence_length}"
            )

    first_image_relative = first_image.resolve().relative_to(
        repository_root.resolve()
    ).as_posix()

    return (
        annotations,
        image_width,
        image_height,
        frame_rate,
        frame_rate_source,
        first_image_relative,
    )


def serialise_candidate(candidate: Any) -> dict[str, Any]:
    value = asdict(candidate)
    value["exclusion_reasons"] = list(
        candidate.exclusion_reasons
    )
    return value


def profile_sequence(
    record: LocalSequenceRecord,
    *,
    dataset_source: dict[str, Any],
    repository_root: Path,
    explicit_frame_rate: Optional[float],
    policy: SelectionPolicy,
) -> dict[str, Any]:
    if not record.structure_valid:
        raise ValueError(
            f"{record.dataset}:{record.split}:"
            f"{record.sequence_name}: invalid catalogue structure: "
            f"{list(record.validation_errors)}"
        )

    (
        annotations,
        image_width,
        image_height,
        frame_rate,
        frame_rate_source,
        geometry_source_relative_path,
    ) = load_sequence_annotations(
        record,
        dataset_source=dataset_source,
        repository_root=repository_root,
        explicit_frame_rate=explicit_frame_rate,
    )

    candidate_rows = [
        row
        for row in annotations
        if row.include_as_person_candidate
    ]
    excluded_rows = [
        row
        for row in annotations
        if not row.include_as_person_candidate
    ]

    exclusion_reason_counts = Counter(
        row.exclusion_reason
        or "excluded_without_reason"
        for row in excluded_rows
    )

    candidates = analyse_target_candidates(
        annotations,
        policy=policy,
    )

    serialised_candidates = [
        serialise_candidate(candidate)
        for candidate in candidates
    ]

    return {
        "dataset": record.dataset,
        "split": record.split,
        "sequence_name": record.sequence_name,
        "scene_key": record.scene_key,
        "source_relative_path": record.source_relative_path,
        "annotation_relative_path": (
            record.annotation_relative_path
        ),
        "image_directory_relative_path": (
            record.image_directory_relative_path
        ),
        "geometry_source_relative_path": (
            geometry_source_relative_path
        ),
        "image_width": image_width,
        "image_height": image_height,
        "image_count": record.image_count,
        "sequence_length": record.sequence_length,
        "frame_rate": frame_rate,
        "frame_rate_source": frame_rate_source,
        "frame_rate_assumption_frozen": False,
        "annotation_count": len(annotations),
        "included_person_annotation_count": len(
            candidate_rows
        ),
        "excluded_annotation_count": len(
            excluded_rows
        ),
        "exclusion_reason_counts": dict(
            sorted(exclusion_reason_counts.items())
        ),
        "candidate_count": len(candidates),
        "eligible_candidate_count": sum(
            candidate.eligible
            for candidate in candidates
        ),
        "candidates": serialised_candidates,
    }


def profile_external_tracking_dataset(
    registry: dict[str, Any],
    *,
    repository_root: Path,
    dataset_id: str,
    split: str,
    explicit_frame_rate: Optional[float],
    policy: SelectionPolicy,
) -> dict[str, Any]:
    validate_registry(registry)

    root = repository_root.resolve()
    dataset_source = verified_acquisition(
        registry,
        dataset_id=dataset_id,
        split=split,
    )

    records = [
        record
        for record in canonical_records(
            catalogue_local_datasets(
                registry,
                repository_root=root,
            )
        )
        if record.dataset == dataset_id
        and record.split == split
    ]

    if not records:
        raise ValueError(
            f"{dataset_id}:{split}: no installed canonical "
            "sequence records"
        )

    profiles = [
        profile_sequence(
            record,
            dataset_source=dataset_source,
            repository_root=root,
            explicit_frame_rate=explicit_frame_rate,
            policy=policy,
        )
        for record in records
    ]

    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "dataset": dataset_id,
        "split": split,
        "sequence_count": len(profiles),
        "annotation_count": sum(
            item["annotation_count"]
            for item in profiles
        ),
        "included_person_annotation_count": sum(
            item["included_person_annotation_count"]
            for item in profiles
        ),
        "excluded_annotation_count": sum(
            item["excluded_annotation_count"]
            for item in profiles
        ),
        "candidate_count": sum(
            item["candidate_count"]
            for item in profiles
        ),
        "eligible_candidate_count": sum(
            item["eligible_candidate_count"]
            for item in profiles
        ),
        "selection_policy": asdict(policy),
        "annotation_only": True,
        "tim_outcomes_inspected": False,
        "tracker_outcomes_inspected": False,
        "selection_or_freeze_performed": False,
        "error_count": 0,
        "errors": [],
        "sequences": profiles,
    }

    payload_keys = set()

    def collect_keys(value: Any) -> None:
        if isinstance(value, dict):
            payload_keys.update(value)
            for child in value.values():
                collect_keys(child)
        elif isinstance(value, list):
            for child in value:
                collect_keys(child)

    collect_keys(payload)

    forbidden = sorted(
        payload_keys & FORBIDDEN_OUTCOME_FIELDS
    )

    if forbidden:
        raise AssertionError(
            f"forbidden outcome fields entered profile: {forbidden}"
        )

    return payload


def error_payload(
    *,
    dataset_id: str,
    split: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "dataset": dataset_id,
        "split": split,
        "annotation_only": True,
        "tim_outcomes_inspected": False,
        "tracker_outcomes_inspected": False,
        "selection_or_freeze_performed": False,
        "error_count": 1,
        "errors": [message],
        "sequences": [],
    }


def render_human(payload: dict[str, Any]) -> str:
    lines = [
        (
            f"{payload['dataset']} {payload['split']} "
            f"sequences={payload['sequence_count']} "
            f"annotations={payload['annotation_count']} "
            f"candidates={payload['candidate_count']} "
            f"eligible={payload['eligible_candidate_count']}"
        )
    ]

    for sequence in payload["sequences"]:
        lines.append(
            (
                f"{sequence['sequence_name']} "
                f"images={sequence['image_count']} "
                f"annotations={sequence['annotation_count']} "
                f"candidates={sequence['candidate_count']} "
                f"eligible={sequence['eligible_candidate_count']} "
                f"fps={sequence['frame_rate']} "
                f"fps_source={sequence['frame_rate_source']} "
                "frozen=false"
            )
        )

    lines.extend(
        [
            "OK: profile contains annotation-derived facts only.",
            "OK: no sequence, identity or frame range was selected.",
            "OK: no tracker or TIM-MARS outcomes were inspected.",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=ROOT,
    )
    parser.add_argument(
        "--dataset",
        required=True,
    )
    parser.add_argument(
        "--split",
        required=True,
    )
    parser.add_argument(
        "--frame-rate",
        type=float,
    )
    parser.add_argument(
        "--json",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    arguments = parser.parse_args()

    try:
        registry = load_registry(arguments.registry)
        payload = profile_external_tracking_dataset(
            registry,
            repository_root=arguments.repository_root,
            dataset_id=arguments.dataset,
            split=arguments.split,
            explicit_frame_rate=arguments.frame_rate,
            policy=SelectionPolicy(),
        )
        status = 0
    except (
        FileNotFoundError,
        OSError,
        ValueError,
    ) as exc:
        payload = error_payload(
            dataset_id=arguments.dataset,
            split=arguments.split,
            message=str(exc),
        )
        status = 1

    rendered_json = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if arguments.output is not None:
        arguments.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        arguments.output.write_text(
            rendered_json,
            encoding="utf-8",
        )

    if arguments.json:
        print(rendered_json, end="")
    elif status == 0:
        print(render_human(payload))
    else:
        print(f"ERROR: {payload['errors'][0]}")

    return status


if __name__ == "__main__":
    raise SystemExit(main())
