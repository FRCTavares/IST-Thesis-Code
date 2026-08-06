"""Tests for the Issue #30 external dataset source registry."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "analysis"
    / "validate_external_dataset_sources.py"
)
REGISTRY_PATH = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "dataset_sources.json"
)

SPEC = importlib.util.spec_from_file_location(
    "validate_external_dataset_sources",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def registry():
    return json.loads(
        REGISTRY_PATH.read_text(encoding="utf-8")
    )


def dataset(value, dataset_id):
    return next(
        item
        for item in value["datasets"]
        if item["id"] == dataset_id
    )


def acquisition(split="val"):
    return {
        "split": split,
        "status": "verified",
        "archive_filename": f"archive-{split}.zip",
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 100,
        "local_relative_path": (
            f"data/datasets/external/visdrone_mot/{split}"
        ),
        "sequence_count": 1,
        "annotation_count": 1,
        "image_count": 1,
        "verified_date": "2026-08-06",
    }


def test_tracked_registry_is_valid():
    MODULE.validate_registry(registry())


def test_dataset_order_is_stable():
    value = registry()
    value["datasets"] = list(reversed(value["datasets"]))

    with pytest.raises(ValueError, match="dataset ordering"):
        MODULE.validate_registry(value)


def test_automatic_download_is_forbidden():
    value = registry()
    value["large_data_policy"]["download_automatically"] = True

    with pytest.raises(
        ValueError,
        match="download_automatically",
    ):
        MODULE.validate_registry(value)


def test_test_split_without_ground_truth_is_forbidden():
    value = registry()
    dataset(value, "mot17")[
        "admissible_splits"
    ].append("test")

    with pytest.raises(
        ValueError,
        match="test splits without local GT",
    ):
        MODULE.validate_registry(value)


def test_mot17_scene_deduplication_is_required():
    value = registry()
    dataset(value, "mot17")[
        "scene_deduplication"
    ]["enabled"] = False

    with pytest.raises(
        ValueError,
        match="MOT17 scene deduplication",
    ):
        MODULE.validate_registry(value)


def test_valid_partial_acquisition_is_accepted():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "partially_verified"
    source["acquisitions"] = [acquisition()]

    MODULE.validate_registry(value)


def test_legacy_flat_archive_fields_are_rejected():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["archive_filename"] = "legacy.zip"
    source["archive_sha256"] = "a" * 64

    with pytest.raises(
        ValueError,
        match="legacy dataset-level archive fields",
    ):
        MODULE.validate_registry(value)


def test_status_must_match_verified_split_coverage():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "fully_verified"
    source["acquisitions"] = [acquisition()]

    with pytest.raises(
        ValueError,
        match="acquisition_status must be",
    ):
        MODULE.validate_registry(value)


def test_duplicate_acquisition_split_is_rejected():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "partially_verified"
    source["acquisitions"] = [
        acquisition(),
        acquisition(),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate acquisition split",
    ):
        MODULE.validate_registry(value)


def test_archive_hash_must_be_lowercase_hex():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "partially_verified"
    record = acquisition()
    record["archive_sha256"] = "A" * 64
    source["acquisitions"] = [record]

    with pytest.raises(
        ValueError,
        match="64 lowercase hexadecimal",
    ):
        MODULE.validate_registry(value)


def test_visdrone_timing_provenance_is_required():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source.pop("timing_provenance")

    with pytest.raises(
        ValueError,
        match="timing_provenance must be an object",
    ):
        MODULE.validate_registry(value)


def test_visdrone_exported_cadence_must_remain_unknown():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    timing = source["timing_provenance"]
    timing["exported_sequence_frame_rate_hz"] = 24.0
    timing["exported_sequence_cadence_known"] = True

    with pytest.raises(
        ValueError,
        match="exported sequence frame rate must remain null",
    ):
        MODULE.validate_registry(value)


def test_visdrone_capture_rate_is_not_exported_rate():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["timing_provenance"][
        "original_capture_frame_rate_hz"
    ] = 30.0

    with pytest.raises(
        ValueError,
        match="original capture rate must equal 24 FPS",
    ):
        MODULE.validate_registry(value)


def test_visdrone_time_policy_remains_frame_index_only():
    value = copy.deepcopy(registry())
    source = dataset(value, "visdrone_mot")
    source["timing_provenance"][
        "benchmark_time_policy"
    ] = "normalized_frame_index_divided_by_24"

    with pytest.raises(
        ValueError,
        match="frame-index-only",
    ):
        MODULE.validate_registry(value)


def test_other_datasets_cannot_inherit_visdrone_timing():
    value = copy.deepcopy(registry())
    mot17 = dataset(value, "mot17")
    visdrone = dataset(value, "visdrone_mot")

    mot17["timing_provenance"] = copy.deepcopy(
        visdrone["timing_provenance"]
    )

    with pytest.raises(
        ValueError,
        match="timing_provenance is only defined for VisDrone",
    ):
        MODULE.validate_registry(value)
