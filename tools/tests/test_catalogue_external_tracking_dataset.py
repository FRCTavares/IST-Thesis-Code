"""Tests for deterministic local external-dataset cataloguing."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "analysis"
    / "catalogue_external_tracking_dataset.py"
)
FIXTURE_ROOT = (
    ROOT
    / "tools"
    / "tests"
    / "fixtures"
    / "external_catalogue"
)
REGISTRY_PATH = FIXTURE_ROOT / "dataset_sources.json"

SPEC = importlib.util.spec_from_file_location(
    "catalogue_external_tracking_dataset",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def catalogue():
    registry = MODULE.load_registry(REGISTRY_PATH)
    return MODULE.catalogue_local_datasets(
        registry,
        repository_root=FIXTURE_ROOT,
    )


def test_catalogue_order_and_dataset_coverage_are_stable():
    records = catalogue()

    assert [
        (
            record.dataset,
            record.split,
            record.sequence_name,
        )
        for record in records
    ] == [
        ("dancetrack", "val", "dancetrack0001"),
        ("mot17", "train", "MOT17-02-FRCNN"),
        ("mot17", "train", "MOT17-02-DPM"),
        (
            "visdrone_mot",
            "val",
            "uav0000013_00000_v",
        ),
    ]


def test_mot17_variants_share_one_scene_key():
    records = [
        record
        for record in catalogue()
        if record.dataset == "mot17"
    ]

    assert {record.scene_key for record in records} == {
        "MOT17-02"
    }
    assert {
        record.canonical_sequence_name
        for record in records
    } == {
        "MOT17-02-FRCNN"
    }

    canonical = next(
        record
        for record in records
        if record.sequence_name == "MOT17-02-FRCNN"
    )
    duplicate = next(
        record
        for record in records
        if record.sequence_name == "MOT17-02-DPM"
    )

    assert canonical.duplicate_variant is False
    assert duplicate.duplicate_variant is True


def test_all_synthetic_structures_are_valid():
    records = catalogue()

    assert records
    assert all(
        record.structure_valid
        for record in records
    )
    assert all(
        record.validation_errors == ()
        for record in records
    )


def test_canonical_records_remove_mot17_duplicate_variant():
    canonical = MODULE.canonical_records(catalogue())

    assert [
        record.sequence_name
        for record in canonical
    ] == [
        "dancetrack0001",
        "MOT17-02-FRCNN",
        "uav0000013_00000_v",
    ]


def test_serialised_catalogue_is_json_safe_and_deterministic():
    first = MODULE.serialise_catalogue(catalogue())
    second = MODULE.serialise_catalogue(catalogue())

    assert first == second
    assert first["record_count"] == 4
    assert first["valid_record_count"] == 4
    assert first["duplicate_variant_count"] == 1

    rendered = json.dumps(
        first,
        sort_keys=True,
    )
    assert "MOT17-02-FRCNN" in rendered


def test_missing_ground_truth_is_reported(tmp_path):
    registry = MODULE.load_registry(REGISTRY_PATH)
    root = tmp_path

    sequence = (
        root
        / "installed"
        / "dancetrack"
        / "val"
        / "dancetrack9999"
    )

    (sequence / "img1").mkdir(parents=True)
    (sequence / "img1" / "00000001.jpg").write_bytes(b"")

    (sequence / "seqinfo.ini").write_text(
        "[Sequence]\n"
        "name=dancetrack9999\n"
        "imDir=img1\n"
        "frameRate=20\n"
        "seqLength=1\n"
        "imWidth=1920\n"
        "imHeight=1080\n"
        "imExt=.jpg\n",
        encoding="utf-8",
    )

    records = MODULE.catalogue_local_datasets(
        registry,
        repository_root=root,
    )

    assert len(records) == 1
    assert records[0].structure_valid is False
    assert records[0].validation_errors == (
        "missing_ground_truth",
    )
