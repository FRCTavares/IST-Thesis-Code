"""Tests for deterministic annotation-only dataset profiles."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = ROOT / "tools" / "analysis"
MODULE_PATH = (
    ANALYSIS_ROOT
    / "profile_external_tracking_dataset.py"
)
REGISTRY_PATH = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "dataset_sources.json"
)

sys.path.insert(0, str(ANALYSIS_ROOT))

SPEC = importlib.util.spec_from_file_location(
    "profile_external_tracking_dataset",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def tracked_registry():
    return json.loads(
        REGISTRY_PATH.read_text(encoding="utf-8")
    )


def dataset(value, dataset_id):
    return next(
        item
        for item in value["datasets"]
        if item["id"] == dataset_id
    )


def png_header(width, height):
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def create_fixture(tmp_path):
    value = copy.deepcopy(tracked_registry())

    for item in value["datasets"]:
        item["acquisition_status"] = "not_downloaded"
        item["acquisitions"] = []

    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "partially_verified"

    split_root = (
        tmp_path
        / "data"
        / "datasets"
        / "external"
        / "visdrone_mot"
        / "val"
    )
    image_root = (
        split_root
        / "sequences"
        / "sequence_a"
    )
    annotation_root = split_root / "annotations"

    image_root.mkdir(parents=True)
    annotation_root.mkdir(parents=True)

    for frame in range(1, 31):
        (image_root / f"{frame:07d}.png").write_bytes(
            png_header(640, 480)
        )

    rows = []

    for frame in range(1, 31):
        rows.append(
            f"{frame},1,100,100,60,100,1,1,0,0"
        )
        rows.append(
            f"{frame},2,300,100,80,120,1,2,0,0"
        )

    annotation_path = (
        annotation_root
        / "sequence_a.txt"
    )
    annotation_path.write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    source["acquisitions"] = [
        {
            "split": "val",
            "status": "verified",
            "archive_filename": "fixture.zip",
            "archive_sha256": "a" * 64,
            "archive_size_bytes": 1,
            "local_relative_path": (
                "data/datasets/external/visdrone_mot/val"
            ),
            "sequence_count": 1,
            "annotation_count": 1,
            "image_count": 30,
            "verified_date": "2026-08-06",
        }
    ]

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(value),
        encoding="utf-8",
    )

    return value, registry_path, annotation_path


def profile(value, tmp_path):
    return MODULE.profile_external_tracking_dataset(
        value,
        repository_root=tmp_path,
        dataset_id="visdrone_mot",
        split="val",
        explicit_frame_rate=24.0,
        policy=MODULE.SelectionPolicy(),
    )


def test_annotation_only_profile_is_deterministic(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    first = profile(value, tmp_path)
    second = profile(value, tmp_path)

    assert first == second
    assert first["annotation_only"] is True
    assert first["tim_outcomes_inspected"] is False
    assert first["tracker_outcomes_inspected"] is False
    assert first["selection_or_freeze_performed"] is False


def test_profile_preserves_candidate_and_exclusion_facts(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    result = profile(value, tmp_path)
    sequence = result["sequences"][0]

    assert result["sequence_count"] == 1
    assert result["annotation_count"] == 60
    assert result["included_person_annotation_count"] == 30
    assert result["excluded_annotation_count"] == 30
    assert result["candidate_count"] == 1
    assert result["eligible_candidate_count"] == 1

    assert sequence["exclusion_reason_counts"] == {
        "group_class_not_single_identity": 30,
    }
    assert sequence["candidates"][0]["identity"] == 1
    assert sequence["candidates"][0]["eligible"] is True


def test_missing_visdrone_frame_rate_is_rejected(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    with pytest.raises(
        ValueError,
        match="pass --frame-rate explicitly",
    ):
        MODULE.profile_external_tracking_dataset(
            value,
            repository_root=tmp_path,
            dataset_id="visdrone_mot",
            split="val",
            explicit_frame_rate=None,
            policy=MODULE.SelectionPolicy(),
        )


def test_explicit_frame_rate_is_marked_unfrozen(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    result = profile(value, tmp_path)
    sequence = result["sequences"][0]

    assert sequence["frame_rate"] == pytest.approx(24.0)
    assert (
        sequence["frame_rate_source"]
        == "explicit_cli_unfrozen"
    )
    assert sequence["frame_rate_assumption_frozen"] is False


def test_invalid_catalogue_structure_is_rejected(tmp_path):
    value, _, annotation_path = create_fixture(tmp_path)
    annotation_path.unlink()

    with pytest.raises(
        ValueError,
        match="invalid catalogue structure",
    ):
        profile(value, tmp_path)


def test_json_cli_emits_one_valid_document(tmp_path):
    _, registry_path, _ = create_fixture(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--registry",
            str(registry_path),
            "--repository-root",
            str(tmp_path),
            "--dataset",
            "visdrone_mot",
            "--split",
            "val",
            "--frame-rate",
            "24",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""

    payload = json.loads(completed.stdout)

    assert payload["error_count"] == 0
    assert payload["errors"] == []
    assert payload["sequence_count"] == 1
    assert "OK:" not in completed.stdout


def test_json_cli_reports_missing_rate_structurally(tmp_path):
    _, registry_path, _ = create_fixture(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--registry",
            str(registry_path),
            "--repository-root",
            str(tmp_path),
            "--dataset",
            "visdrone_mot",
            "--split",
            "val",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""

    payload = json.loads(completed.stdout)

    assert payload["error_count"] == 1
    assert any(
        "pass --frame-rate explicitly" in error
        for error in payload["errors"]
    )


def test_profile_contains_no_outcome_fields(tmp_path):
    value, _, _ = create_fixture(tmp_path)
    result = profile(value, tmp_path)

    keys = set()

    def collect(value):
        if isinstance(value, dict):
            keys.update(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(result)

    assert keys.isdisjoint(
        MODULE.FORBIDDEN_OUTCOME_FIELDS
    )
