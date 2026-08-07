#!/usr/bin/env python3
"""Verify tracked external-dataset acquisitions against local storage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from catalogue_external_tracking_dataset import (
    canonical_records,
    catalogue_local_datasets,
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def verify_registry_acquisitions(
    registry: dict[str, Any],
    *,
    repository_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    validate_registry(registry)

    root = repository_root.resolve()
    records = canonical_records(
        catalogue_local_datasets(
            registry,
            repository_root=root,
        )
    )

    errors: list[str] = []
    verified: list[dict[str, Any]] = []

    datasets = {
        dataset["id"]: dataset
        for dataset in registry["datasets"]
    }

    for dataset_id in (
        "mot17",
        "dancetrack",
        "visdrone_mot",
    ):
        dataset = datasets[dataset_id]
        local_root = Path(dataset["local_root"])

        for acquisition in dataset["acquisitions"]:
            split = acquisition["split"]
            context = f"{dataset_id}:{split}"

            archive_relative_path = (
                local_root
                / "_archives"
                / acquisition["archive_filename"]
            )
            archive_path = root / archive_relative_path
            installed_path = (
                root / acquisition["local_relative_path"]
            )

            if not archive_path.is_file():
                errors.append(
                    f"{context}: archive missing: "
                    f"{archive_relative_path.as_posix()}"
                )
                continue

            actual_size = archive_path.stat().st_size

            if actual_size != acquisition["archive_size_bytes"]:
                errors.append(
                    f"{context}: archive size mismatch: "
                    f"expected={acquisition['archive_size_bytes']} "
                    f"actual={actual_size}"
                )

            actual_sha256 = sha256_file(archive_path)

            if actual_sha256 != acquisition["archive_sha256"]:
                errors.append(
                    f"{context}: archive SHA-256 mismatch"
                )

            if not installed_path.is_dir():
                errors.append(
                    f"{context}: installed split missing: "
                    f"{acquisition['local_relative_path']}"
                )

            split_records = [
                record
                for record in records
                if record.dataset == dataset_id
                and record.split == split
            ]

            invalid_records = [
                record
                for record in split_records
                if not record.structure_valid
            ]

            for record in invalid_records:
                errors.append(
                    f"{context}: invalid sequence "
                    f"{record.sequence_name}: "
                    f"{list(record.validation_errors)}"
                )

            actual_sequence_count = len(split_records)
            actual_image_count = sum(
                record.image_count
                for record in split_records
            )
            actual_annotation_count = sum(
                1
                for record in split_records
                if (
                    root
                    / record.annotation_relative_path
                ).is_file()
            )

            expected_counts = {
                "sequence_count": actual_sequence_count,
                "annotation_count": actual_annotation_count,
                "image_count": actual_image_count,
            }

            for field, actual_value in expected_counts.items():
                expected_value = acquisition[field]

                if actual_value != expected_value:
                    errors.append(
                        f"{context}: {field} mismatch: "
                        f"expected={expected_value} "
                        f"actual={actual_value}"
                    )

            verified.append(
                {
                    "dataset": dataset_id,
                    "split": split,
                    "status": (
                        "valid"
                        if not any(
                            error.startswith(f"{context}:")
                            for error in errors
                        )
                        else "invalid"
                    ),
                    "archive_relative_path": (
                        archive_relative_path.as_posix()
                    ),
                    "archive_sha256": actual_sha256,
                    "archive_size_bytes": actual_size,
                    "local_relative_path": (
                        acquisition["local_relative_path"]
                    ),
                    "sequence_count": actual_sequence_count,
                    "annotation_count": actual_annotation_count,
                    "image_count": actual_image_count,
                }
            )

    payload = {
        "schema_version": 1,
        "registry_schema_version": registry["schema_version"],
        "verified_acquisition_count": len(verified),
        "error_count": len(errors),
        "errors": errors,
        "acquisitions": verified,
    }

    return payload, errors


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
        "--json",
        action="store_true",
    )
    arguments = parser.parse_args()

    registry = load_registry(arguments.registry)
    payload, errors = verify_registry_acquisitions(
        registry,
        repository_root=arguments.repository_root,
    )

    if arguments.json:
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if errors else 0

    for acquisition in payload["acquisitions"]:
        print(
            acquisition["dataset"],
            acquisition["split"],
            acquisition["status"],
            f"sequences={acquisition['sequence_count']}",
            f"annotations={acquisition['annotation_count']}",
            f"images={acquisition['image_count']}",
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OK: every tracked acquisition matches local storage.")
    print("OK: archive hashes, sizes, structures and counts match.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
