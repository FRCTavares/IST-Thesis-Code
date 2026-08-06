#!/usr/bin/env python3
"""Validate the Issue #30 external dataset source registry."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "dataset_sources.json"
)

EXPECTED_DATASET_ORDER = (
    "mot17",
    "dancetrack",
    "visdrone_mot",
)

EXPECTED_LOCAL_ROOTS = {
    "mot17": "data/datasets/external/mot17",
    "dancetrack": "data/datasets/external/dancetrack",
    "visdrone_mot": "data/datasets/external/visdrone_mot",
}

ALLOWED_ACQUISITION_STATUSES = {
    "not_downloaded",
    "downloaded_unverified",
    "verified",
}

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError("registry root must be a JSON object")

    return value


def require_nonempty_text(
    value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")

    return value


def validate_official_reference(
    value: Any,
    *,
    dataset_id: str,
) -> None:
    text = require_nonempty_text(
        value,
        field=f"{dataset_id}.official_reference",
    )
    parsed = urlparse(text)

    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(
            f"{dataset_id}.official_reference must be an HTTPS URL"
        )


def validate_sha256_pair(
    dataset: dict[str, Any],
    *,
    dataset_id: str,
) -> None:
    archive_sha256 = dataset.get("archive_sha256")
    archive_filename = dataset.get("archive_filename")

    if archive_sha256 is None and archive_filename is None:
        return

    if archive_sha256 is None or archive_filename is None:
        raise ValueError(
            f"{dataset_id}: archive filename and SHA-256 "
            "must be recorded together"
        )

    if not isinstance(archive_sha256, str) or not SHA256_PATTERN.fullmatch(
        archive_sha256
    ):
        raise ValueError(
            f"{dataset_id}.archive_sha256 must be 64 lowercase hex"
        )

    require_nonempty_text(
        archive_filename,
        field=f"{dataset_id}.archive_filename",
    )


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")

    policy = registry.get("large_data_policy")
    if not isinstance(policy, dict):
        raise ValueError("large_data_policy must be an object")

    if policy.get("download_automatically") is not False:
        raise ValueError(
            "download_automatically must remain false"
        )

    if policy.get("require_manual_source_review") is not True:
        raise ValueError(
            "require_manual_source_review must remain true"
        )

    if policy.get("require_free_space_check") is not True:
        raise ValueError(
            "require_free_space_check must remain true"
        )

    minimum_free = policy.get(
        "minimum_free_space_after_acquisition_gib"
    )
    if not isinstance(minimum_free, int) or minimum_free < 20:
        raise ValueError(
            "minimum free space after acquisition must be at least 20 GiB"
        )

    if policy.get("commit_raw_datasets") is not False:
        raise ValueError("raw datasets must not be committed")

    datasets = registry.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("datasets must be a list")

    dataset_ids = tuple(
        dataset.get("id")
        for dataset in datasets
        if isinstance(dataset, dict)
    )

    if dataset_ids != EXPECTED_DATASET_ORDER:
        raise ValueError(
            "dataset ordering must be "
            f"{EXPECTED_DATASET_ORDER}, got {dataset_ids}"
        )

    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise ValueError("each dataset must be an object")

        dataset_id = require_nonempty_text(
            dataset.get("id"),
            field="dataset.id",
        )

        validate_official_reference(
            dataset.get("official_reference"),
            dataset_id=dataset_id,
        )

        require_nonempty_text(
            dataset.get("source_authority"),
            field=f"{dataset_id}.source_authority",
        )
        require_nonempty_text(
            dataset.get("license_or_terms"),
            field=f"{dataset_id}.license_or_terms",
        )
        require_nonempty_text(
            dataset.get("ground_truth_policy"),
            field=f"{dataset_id}.ground_truth_policy",
        )
        require_nonempty_text(
            dataset.get("public_detection_policy"),
            field=f"{dataset_id}.public_detection_policy",
        )

        if dataset.get("acquisition_method") != (
            "manual_from_official_reference"
        ):
            raise ValueError(
                f"{dataset_id}: acquisition must remain manual"
            )

        expected_root = EXPECTED_LOCAL_ROOTS[dataset_id]
        if dataset.get("local_root") != expected_root:
            raise ValueError(
                f"{dataset_id}: expected local_root {expected_root!r}"
            )

        splits = dataset.get("admissible_splits")
        if (
            not isinstance(splits, list)
            or not splits
            or not all(
                isinstance(split, str) and split
                for split in splits
            )
        ):
            raise ValueError(
                f"{dataset_id}.admissible_splits must be non-empty"
            )

        if len(splits) != len(set(splits)):
            raise ValueError(
                f"{dataset_id}.admissible_splits contains duplicates"
            )

        if "test" in splits or "test-dev" in splits:
            raise ValueError(
                f"{dataset_id}: test splits without local GT "
                "must not be admissible"
            )

        if dataset.get("source_frame_index_base") != 1:
            raise ValueError(
                f"{dataset_id}: source frame index base must be 1"
            )

        status = dataset.get("acquisition_status")
        if status not in ALLOWED_ACQUISITION_STATUSES:
            raise ValueError(
                f"{dataset_id}: invalid acquisition_status {status!r}"
            )

        validate_sha256_pair(
            dataset,
            dataset_id=dataset_id,
        )

        deduplication = dataset.get("scene_deduplication")
        if not isinstance(deduplication, dict):
            raise ValueError(
                f"{dataset_id}.scene_deduplication must be an object"
            )

        if dataset_id == "mot17":
            if deduplication.get("enabled") is not True:
                raise ValueError(
                    "MOT17 scene deduplication must be enabled"
                )

            suffixes = deduplication.get("variant_suffixes")
            if suffixes != ["DPM", "FRCNN", "SDP"]:
                raise ValueError(
                    "MOT17 detector suffixes must be DPM/FRCNN/SDP"
                )

            if deduplication.get("canonical_variant") != "FRCNN":
                raise ValueError(
                    "MOT17 canonical storage variant must be FRCNN"
                )
        else:
            if deduplication.get("enabled") is not False:
                raise ValueError(
                    f"{dataset_id}: scene deduplication must be false"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=DEFAULT_REGISTRY,
    )
    arguments = parser.parse_args()

    registry = load_registry(arguments.registry)
    validate_registry(registry)

    print(
        "OK: external dataset source registry is valid."
    )
    print(
        "OK: acquisition remains manual and no download URL is guessed."
    )
    print(
        "OK: only splits with local official ground truth are admissible."
    )
    print(
        "OK: MOT17 detector-labelled scene duplication is explicit."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
