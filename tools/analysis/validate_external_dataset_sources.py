#!/usr/bin/env python3
"""Validate the Issue #30 external dataset source registry."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
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

ALLOWED_DATASET_ACQUISITION_STATUSES = {
    "not_downloaded",
    "partially_verified",
    "fully_verified",
}

REQUIRED_ACQUISITION_FIELDS = {
    "split",
    "status",
    "archive_filename",
    "archive_sha256",
    "archive_size_bytes",
    "local_relative_path",
    "sequence_count",
    "annotation_count",
    "image_count",
    "verified_date",
}

LEGACY_ARCHIVE_FIELDS = {
    "archive_filename",
    "archive_sha256",
}

VISDRONE_TIMING_FIELDS = {
    "status",
    "original_capture_frame_rate_hz",
    "exported_sequence_frame_rate_hz",
    "exported_sequence_cadence_known",
    "evidence_authority",
    "evidence_reference",
    "evidence_retrieved_date",
    "evidence_scope",
    "benchmark_time_policy",
}

VISDRONE_TIMING_STATUS = (
    "capture_rate_known_export_cadence_unknown"
)

VISDRONE_TIMING_POLICY = (
    "frame_index_only_until_cadence_resolved"
)

VISDRONE_TIMING_REFERENCE = "https://aiskyeye.com/faq/"

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


def require_positive_integer(
    value: Any,
    *,
    field: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError(f"{field} must be a positive integer")

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


def validate_verified_date(
    value: Any,
    *,
    field: str,
) -> None:
    text = require_nonempty_text(value, field=field)

    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"{field} must use ISO YYYY-MM-DD format"
        ) from exc

    if parsed.isoformat() != text:
        raise ValueError(
            f"{field} must use canonical ISO YYYY-MM-DD format"
        )


def validate_acquisitions(
    dataset: dict[str, Any],
    *,
    dataset_id: str,
    admissible_splits: list[str],
    local_root: str,
) -> None:
    legacy = sorted(
        field
        for field in LEGACY_ARCHIVE_FIELDS
        if field in dataset
    )
    if legacy:
        raise ValueError(
            f"{dataset_id}: legacy dataset-level archive fields "
            f"are forbidden: {legacy}"
        )

    acquisitions = dataset.get("acquisitions")

    if not isinstance(acquisitions, list):
        raise ValueError(
            f"{dataset_id}.acquisitions must be a list"
        )

    split_order = {
        split: index
        for index, split in enumerate(admissible_splits)
    }

    seen_splits: set[str] = set()
    previous_order = -1

    for index, acquisition in enumerate(acquisitions):
        context = f"{dataset_id}.acquisitions[{index}]"

        if not isinstance(acquisition, dict):
            raise ValueError(f"{context} must be an object")

        fields = set(acquisition)
        missing = sorted(REQUIRED_ACQUISITION_FIELDS - fields)
        extra = sorted(fields - REQUIRED_ACQUISITION_FIELDS)

        if missing or extra:
            raise ValueError(
                f"{context} fields mismatch: "
                f"missing={missing}, extra={extra}"
            )

        split = require_nonempty_text(
            acquisition.get("split"),
            field=f"{context}.split",
        )

        if split not in split_order:
            raise ValueError(
                f"{context}.split is not admissible: {split!r}"
            )

        if split in seen_splits:
            raise ValueError(
                f"{dataset_id}: duplicate acquisition split {split!r}"
            )

        current_order = split_order[split]

        if current_order <= previous_order:
            raise ValueError(
                f"{dataset_id}: acquisitions must follow "
                "admissible split order"
            )

        seen_splits.add(split)
        previous_order = current_order

        if acquisition.get("status") != "verified":
            raise ValueError(
                f"{context}.status must equal 'verified'"
            )

        filename = require_nonempty_text(
            acquisition.get("archive_filename"),
            field=f"{context}.archive_filename",
        )

        if (
            Path(filename).name != filename
            or "/" in filename
            or chr(92) in filename
        ):
            raise ValueError(
                f"{context}.archive_filename must be a basename"
            )

        digest = acquisition.get("archive_sha256")

        if (
            not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            raise ValueError(
                f"{context}.archive_sha256 must be "
                "64 lowercase hexadecimal characters"
            )

        require_positive_integer(
            acquisition.get("archive_size_bytes"),
            field=f"{context}.archive_size_bytes",
        )
        require_positive_integer(
            acquisition.get("sequence_count"),
            field=f"{context}.sequence_count",
        )
        require_positive_integer(
            acquisition.get("annotation_count"),
            field=f"{context}.annotation_count",
        )
        require_positive_integer(
            acquisition.get("image_count"),
            field=f"{context}.image_count",
        )

        expected_local_path = f"{local_root}/{split}"

        if (
            acquisition.get("local_relative_path")
            != expected_local_path
        ):
            raise ValueError(
                f"{context}.local_relative_path must equal "
                f"{expected_local_path!r}"
            )

        validate_verified_date(
            acquisition.get("verified_date"),
            field=f"{context}.verified_date",
        )

    status = dataset.get("acquisition_status")

    if status not in ALLOWED_DATASET_ACQUISITION_STATUSES:
        raise ValueError(
            f"{dataset_id}: invalid acquisition_status {status!r}"
        )

    acquired_splits = set(seen_splits)
    admissible_set = set(admissible_splits)

    if not acquired_splits:
        expected_status = "not_downloaded"
    elif acquired_splits == admissible_set:
        expected_status = "fully_verified"
    else:
        expected_status = "partially_verified"

    if status != expected_status:
        raise ValueError(
            f"{dataset_id}: acquisition_status must be "
            f"{expected_status!r} for verified splits "
            f"{sorted(acquired_splits)}"
        )



def validate_dataset_timing_provenance(
    dataset: dict[str, Any],
    *,
    dataset_id: str,
) -> None:
    timing = dataset.get("timing_provenance")

    if dataset_id != "visdrone_mot":
        if timing is not None:
            raise ValueError(
                f"{dataset_id}: timing_provenance is only "
                "defined for VisDrone until another dataset "
                "requires registry-level timing evidence"
            )

        return

    if not isinstance(timing, dict):
        raise ValueError(
            "visdrone_mot.timing_provenance must be an object"
        )

    fields = set(timing)
    missing = sorted(VISDRONE_TIMING_FIELDS - fields)
    extra = sorted(fields - VISDRONE_TIMING_FIELDS)

    if missing or extra:
        raise ValueError(
            "visdrone_mot.timing_provenance fields mismatch: "
            f"missing={missing}, extra={extra}"
        )

    if timing.get("status") != VISDRONE_TIMING_STATUS:
        raise ValueError(
            "visdrone_mot timing status must distinguish "
            "original capture rate from exported cadence"
        )

    capture_rate = timing.get(
        "original_capture_frame_rate_hz"
    )

    if (
        not isinstance(capture_rate, (int, float))
        or isinstance(capture_rate, bool)
        or float(capture_rate) != 24.0
    ):
        raise ValueError(
            "visdrone_mot original capture rate must equal 24 FPS"
        )

    if timing.get("exported_sequence_frame_rate_hz") is not None:
        raise ValueError(
            "visdrone_mot exported sequence frame rate "
            "must remain null"
        )

    if timing.get("exported_sequence_cadence_known") is not False:
        raise ValueError(
            "visdrone_mot exported sequence cadence "
            "must remain explicitly unknown"
        )

    authority = require_nonempty_text(
        timing.get("evidence_authority"),
        field=(
            "visdrone_mot.timing_provenance."
            "evidence_authority"
        ),
    )

    if authority != "AISKYEYE official FAQ":
        raise ValueError(
            "visdrone_mot timing evidence authority "
            "must remain the AISKYEYE official FAQ"
        )

    reference = require_nonempty_text(
        timing.get("evidence_reference"),
        field=(
            "visdrone_mot.timing_provenance."
            "evidence_reference"
        ),
    )

    if reference != VISDRONE_TIMING_REFERENCE:
        raise ValueError(
            "visdrone_mot timing evidence reference "
            "must remain the official FAQ"
        )

    validate_official_reference(
        reference,
        dataset_id="visdrone_mot.timing_provenance",
    )

    validate_verified_date(
        timing.get("evidence_retrieved_date"),
        field=(
            "visdrone_mot.timing_provenance."
            "evidence_retrieved_date"
        ),
    )

    if timing.get("evidence_scope") != (
        "dataset_original_videos_and_annotated_frame_extraction"
    ):
        raise ValueError(
            "visdrone_mot timing evidence scope must distinguish "
            "the original videos from extracted annotation frames"
        )

    if (
        timing.get("benchmark_time_policy")
        != VISDRONE_TIMING_POLICY
    ):
        raise ValueError(
            "visdrone_mot benchmark time policy must remain "
            "frame-index-only until exported cadence is resolved"
        )


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != 2:
        raise ValueError("schema_version must equal 2")

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
            "minimum free space after acquisition must be "
            "at least 20 GiB"
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
                f"{dataset_id}: expected local_root "
                f"{expected_root!r}"
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
                f"{dataset_id}.admissible_splits "
                "contains duplicates"
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

        validate_dataset_timing_provenance(
            dataset,
            dataset_id=dataset_id,
        )

        validate_acquisitions(
            dataset,
            dataset_id=dataset_id,
            admissible_splits=splits,
            local_root=expected_root,
        )

        deduplication = dataset.get("scene_deduplication")

        if not isinstance(deduplication, dict):
            raise ValueError(
                f"{dataset_id}.scene_deduplication "
                "must be an object"
            )

        if dataset_id == "mot17":
            if deduplication.get("enabled") is not True:
                raise ValueError(
                    "MOT17 scene deduplication must be enabled"
                )

            suffixes = deduplication.get("variant_suffixes")

            if suffixes != ["DPM", "FRCNN", "SDP"]:
                raise ValueError(
                    "MOT17 detector suffixes must be "
                    "DPM/FRCNN/SDP"
                )

            if (
                deduplication.get("canonical_variant")
                != "FRCNN"
            ):
                raise ValueError(
                    "MOT17 canonical storage variant "
                    "must be FRCNN"
                )
        elif deduplication.get("enabled") is not False:
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

    print("OK: external dataset source registry is valid.")
    print("OK: acquisition remains manually reviewed.")
    print("OK: verified archives are recorded per split.")
    print("OK: partial acquisition cannot imply full coverage.")
    print("OK: only splits with local official GT are admissible.")
    print("OK: MOT17 scene duplication remains explicit.")
    print(
        "OK: VisDrone capture rate and exported cadence "
        "remain distinct."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
