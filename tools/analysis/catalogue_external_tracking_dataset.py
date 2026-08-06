#!/usr/bin/env python3
"""Catalogue locally installed external tracking datasets.

The scanner is read-only. It verifies expected directory structure and emits
deterministic records. It does not download data, choose benchmark targets, or
inspect TIM-MARS outcomes.
"""

from __future__ import annotations

import argparse
import configparser
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "dataset_sources.json"
)

MOT17_PATTERN = re.compile(
    r"^(MOT17-\d{2})-(DPM|FRCNN|SDP)$"
)


@dataclass(frozen=True)
class LocalSequenceRecord:
    dataset: str
    split: str
    sequence_name: str
    scene_key: str
    canonical_sequence_name: str
    source_relative_path: str
    metadata_relative_path: Optional[str]
    annotation_relative_path: str
    image_directory_relative_path: str
    frame_rate: Optional[float]
    sequence_length: Optional[int]
    image_width: Optional[int]
    image_height: Optional[int]
    image_extension: Optional[str]
    image_count: int
    structure_valid: bool
    validation_errors: tuple[str, ...]
    duplicate_variant: bool


def load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError("source registry root must be an object")

    return value


def repository_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def parse_seqinfo(path: Path) -> dict[str, Any]:
    parser = configparser.ConfigParser(
        interpolation=None,
        strict=True,
    )

    with path.open(encoding="utf-8") as handle:
        parser.read_file(handle)

    if "Sequence" not in parser:
        raise ValueError("missing [Sequence] section")

    section = parser["Sequence"]

    required = (
        "name",
        "imDir",
        "frameRate",
        "seqLength",
        "imWidth",
        "imHeight",
        "imExt",
    )

    missing = [
        key for key in required
        if key not in section
    ]
    if missing:
        raise ValueError(
            f"missing seqinfo fields: {missing}"
        )

    return {
        "name": section["name"].strip(),
        "image_directory": section["imDir"].strip(),
        "frame_rate": float(section["frameRate"]),
        "sequence_length": int(section["seqLength"]),
        "image_width": int(section["imWidth"]),
        "image_height": int(section["imHeight"]),
        "image_extension": section["imExt"].strip(),
    }


def count_images(
    directory: Path,
    extension: Optional[str],
) -> int:
    if not directory.is_dir():
        return 0

    if extension:
        return sum(
            1
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() == extension.lower()
        )

    return sum(
        1
        for path in directory.iterdir()
        if path.is_file()
    )


def mot17_scene_identity(
    sequence_name: str,
    canonical_variant: str,
) -> tuple[str, str, bool]:
    match = MOT17_PATTERN.fullmatch(sequence_name)
    if match is None:
        return sequence_name, sequence_name, False

    scene_key = match.group(1)
    variant = match.group(2)
    canonical_name = f"{scene_key}-{canonical_variant}"

    return (
        scene_key,
        canonical_name,
        variant != canonical_variant,
    )


def scan_mot_style_split(
    *,
    dataset_id: str,
    split: str,
    split_root: Path,
    repository_root: Path,
    canonical_variant: Optional[str],
) -> list[LocalSequenceRecord]:
    if not split_root.is_dir():
        return []

    records: list[LocalSequenceRecord] = []

    for sequence_root in sorted(
        path
        for path in split_root.iterdir()
        if path.is_dir()
    ):
        errors: list[str] = []
        metadata_path = sequence_root / "seqinfo.ini"
        annotation_path = sequence_root / "gt" / "gt.txt"

        metadata: Optional[dict[str, Any]] = None

        if not metadata_path.is_file():
            errors.append("missing_seqinfo")
        else:
            try:
                metadata = parse_seqinfo(metadata_path)
            except (
                ValueError,
                configparser.Error,
            ) as exc:
                errors.append(
                    f"invalid_seqinfo:{exc}"
                )

        if not annotation_path.is_file():
            errors.append("missing_ground_truth")

        image_directory_name = (
            metadata["image_directory"]
            if metadata is not None
            else "img1"
        )
        image_directory = (
            sequence_root / image_directory_name
        )

        if not image_directory.is_dir():
            errors.append("missing_image_directory")

        image_extension = (
            metadata["image_extension"]
            if metadata is not None
            else None
        )
        image_count = count_images(
            image_directory,
            image_extension,
        )

        if metadata is not None:
            if metadata["name"] != sequence_root.name:
                errors.append("seqinfo_name_mismatch")

            if (
                image_count
                != metadata["sequence_length"]
            ):
                errors.append("image_count_mismatch")

        if (
            dataset_id == "mot17"
            and canonical_variant is not None
        ):
            (
                scene_key,
                canonical_name,
                duplicate_variant,
            ) = mot17_scene_identity(
                sequence_root.name,
                canonical_variant,
            )
        else:
            scene_key = sequence_root.name
            canonical_name = sequence_root.name
            duplicate_variant = False

        records.append(
            LocalSequenceRecord(
                dataset=dataset_id,
                split=split,
                sequence_name=sequence_root.name,
                scene_key=scene_key,
                canonical_sequence_name=canonical_name,
                source_relative_path=repository_relative(
                    sequence_root,
                    repository_root,
                ),
                metadata_relative_path=(
                    repository_relative(
                        metadata_path,
                        repository_root,
                    )
                    if metadata_path.is_file()
                    else None
                ),
                annotation_relative_path=repository_relative(
                    annotation_path,
                    repository_root,
                ),
                image_directory_relative_path=(
                    repository_relative(
                        image_directory,
                        repository_root,
                    )
                ),
                frame_rate=(
                    metadata["frame_rate"]
                    if metadata is not None
                    else None
                ),
                sequence_length=(
                    metadata["sequence_length"]
                    if metadata is not None
                    else None
                ),
                image_width=(
                    metadata["image_width"]
                    if metadata is not None
                    else None
                ),
                image_height=(
                    metadata["image_height"]
                    if metadata is not None
                    else None
                ),
                image_extension=image_extension,
                image_count=image_count,
                structure_valid=not errors,
                validation_errors=tuple(errors),
                duplicate_variant=duplicate_variant,
            )
        )

    return records


def scan_visdrone_split(
    *,
    split: str,
    split_root: Path,
    repository_root: Path,
) -> list[LocalSequenceRecord]:
    if not split_root.is_dir():
        return []

    sequence_root = split_root / "sequences"
    annotation_root = split_root / "annotations"

    if not sequence_root.is_dir():
        return []

    records: list[LocalSequenceRecord] = []

    for image_directory in sorted(
        path
        for path in sequence_root.iterdir()
        if path.is_dir()
    ):
        sequence_name = image_directory.name
        annotation_path = (
            annotation_root / f"{sequence_name}.txt"
        )

        errors: list[str] = []

        if not annotation_path.is_file():
            errors.append("missing_ground_truth")

        image_files = sorted(
            path
            for path in image_directory.iterdir()
            if path.is_file()
        )
        image_count = len(image_files)

        image_extension = (
            image_files[0].suffix
            if image_files
            else None
        )

        if image_count == 0:
            errors.append("no_images")

        records.append(
            LocalSequenceRecord(
                dataset="visdrone_mot",
                split=split,
                sequence_name=sequence_name,
                scene_key=sequence_name,
                canonical_sequence_name=sequence_name,
                source_relative_path=repository_relative(
                    split_root,
                    repository_root,
                ),
                metadata_relative_path=None,
                annotation_relative_path=repository_relative(
                    annotation_path,
                    repository_root,
                ),
                image_directory_relative_path=(
                    repository_relative(
                        image_directory,
                        repository_root,
                    )
                ),
                frame_rate=None,
                sequence_length=image_count,
                image_width=None,
                image_height=None,
                image_extension=image_extension,
                image_count=image_count,
                structure_valid=not errors,
                validation_errors=tuple(errors),
                duplicate_variant=False,
            )
        )

    return records


def catalogue_local_datasets(
    registry: dict[str, Any],
    *,
    repository_root: Path,
) -> list[LocalSequenceRecord]:
    records: list[LocalSequenceRecord] = []

    for dataset in registry["datasets"]:
        dataset_id = dataset["id"]
        local_root = (
            repository_root / dataset["local_root"]
        )

        canonical_variant = dataset[
            "scene_deduplication"
        ].get("canonical_variant")

        for split in dataset["admissible_splits"]:
            split_root = local_root / split

            if dataset_id in {
                "mot17",
                "dancetrack",
            }:
                records.extend(
                    scan_mot_style_split(
                        dataset_id=dataset_id,
                        split=split,
                        split_root=split_root,
                        repository_root=repository_root,
                        canonical_variant=canonical_variant,
                    )
                )
            elif dataset_id == "visdrone_mot":
                records.extend(
                    scan_visdrone_split(
                        split=split,
                        split_root=split_root,
                        repository_root=repository_root,
                    )
                )
            else:
                raise ValueError(
                    f"unsupported dataset: {dataset_id}"
                )

    return sorted(
        records,
        key=lambda item: (
            item.dataset,
            item.split,
            item.scene_key,
            item.duplicate_variant,
            item.sequence_name,
        ),
    )


def canonical_records(
    records: Iterable[LocalSequenceRecord],
) -> list[LocalSequenceRecord]:
    return [
        record
        for record in records
        if not record.duplicate_variant
    ]


def serialise_catalogue(
    records: Iterable[LocalSequenceRecord],
) -> dict[str, Any]:
    ordered = list(records)

    return {
        "schema_version": 1,
        "record_count": len(ordered),
        "valid_record_count": sum(
            record.structure_valid
            for record in ordered
        ),
        "duplicate_variant_count": sum(
            record.duplicate_variant
            for record in ordered
        ),
        "records": [
            {
                **asdict(record),
                "validation_errors": list(
                    record.validation_errors
                ),
            }
            for record in ordered
        ],
    }


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
        "--output",
        type=Path,
    )
    parser.add_argument(
        "--canonical-only",
        action="store_true",
    )
    arguments = parser.parse_args()

    registry = load_registry(arguments.registry)
    records = catalogue_local_datasets(
        registry,
        repository_root=arguments.repository_root,
    )

    if arguments.canonical_only:
        records = canonical_records(records)

    output = serialise_catalogue(records)
    rendered = json.dumps(
        output,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        arguments.output.write_text(
            rendered,
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
