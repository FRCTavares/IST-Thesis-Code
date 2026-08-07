"""Tests for verified external-dataset acquisition checks."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = ROOT / "tools" / "analysis"
MODULE_PATH = (
    ANALYSIS_ROOT
    / "verify_external_dataset_acquisition.py"
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
    "verify_external_dataset_acquisition",
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


def create_fixture(tmp_path):
    value = copy.deepcopy(tracked_registry())

    for item in value["datasets"]:
        item["acquisition_status"] = "not_downloaded"
        item["acquisitions"] = []

    source = dataset(value, "visdrone_mot")
    source["acquisition_status"] = "partially_verified"

    local_root = (
        tmp_path
        / "data"
        / "datasets"
        / "external"
        / "visdrone_mot"
    )
    archive_root = local_root / "_archives"
    sequence_root = (
        local_root
        / "val"
        / "sequences"
        / "sequence_a"
    )
    annotation_root = (
        local_root
        / "val"
        / "annotations"
    )

    archive_root.mkdir(parents=True)
    sequence_root.mkdir(parents=True)
    annotation_root.mkdir(parents=True)

    archive = archive_root / "fixture.zip"
    archive.write_bytes(b"fixture archive bytes")

    (sequence_root / "0000001.jpg").write_bytes(
        b"synthetic image bytes"
    )
    (annotation_root / "sequence_a.txt").write_text(
        "1,1,10,10,20,20,1,1,0,0" + chr(10),
        encoding="utf-8",
    )

    source["acquisitions"] = [
        {
            "split": "val",
            "status": "verified",
            "archive_filename": archive.name,
            "archive_sha256": hashlib.sha256(
                archive.read_bytes()
            ).hexdigest(),
            "archive_size_bytes": archive.stat().st_size,
            "local_relative_path": (
                "data/datasets/external/visdrone_mot/val"
            ),
            "sequence_count": 1,
            "annotation_count": 1,
            "image_count": 1,
            "verified_date": "2026-08-06",
        }
    ]

    return value, archive, annotation_root


def test_valid_synthetic_acquisition_passes(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    payload, errors = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert errors == []
    assert payload["verified_acquisition_count"] == 1
    assert payload["error_count"] == 0
    assert payload["acquisitions"][0]["status"] == "valid"


def test_verification_output_is_deterministic(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    first = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )
    second = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert first == second


def test_missing_archive_is_rejected(tmp_path):
    value, archive, _ = create_fixture(tmp_path)
    archive.unlink()

    _, errors = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert any("archive missing" in error for error in errors)


def test_archive_hash_mismatch_is_rejected(tmp_path):
    value, archive, _ = create_fixture(tmp_path)
    archive.write_bytes(b"changed archive bytes")

    _, errors = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert any(
        "archive SHA-256 mismatch" in error
        for error in errors
    )


def test_recorded_counts_are_verified(tmp_path):
    value, _, _ = create_fixture(tmp_path)
    source = dataset(value, "visdrone_mot")
    source["acquisitions"][0]["image_count"] = 2

    _, errors = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert any(
        "image_count mismatch" in error
        for error in errors
    )


def test_invalid_catalogue_record_is_rejected(tmp_path):
    value, _, annotation_root = create_fixture(tmp_path)
    (annotation_root / "sequence_a.txt").unlink()

    _, errors = MODULE.verify_registry_acquisitions(
        value,
        repository_root=tmp_path,
    )

    assert any(
        "invalid sequence sequence_a" in error
        for error in errors
    )

def run_json_cli(tmp_path, value):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(value),
        encoding="utf-8",
    )

    return subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--registry",
            str(registry_path),
            "--repository-root",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_json_cli_emits_one_valid_document(tmp_path):
    value, _, _ = create_fixture(tmp_path)

    completed = run_json_cli(tmp_path, value)

    assert completed.returncode == 0
    assert completed.stderr == ""

    payload = json.loads(completed.stdout)

    assert payload["error_count"] == 0
    assert payload["errors"] == []
    assert payload["verified_acquisition_count"] == 1
    assert "OK:" not in completed.stdout


def test_json_cli_reports_failures_structurally(tmp_path):
    value, archive, _ = create_fixture(tmp_path)
    archive.write_bytes(b"changed archive bytes")

    completed = run_json_cli(tmp_path, value)

    assert completed.returncode == 1
    assert completed.stderr == ""

    payload = json.loads(completed.stdout)

    assert payload["error_count"] >= 1
    assert any(
        "archive SHA-256 mismatch" in error
        for error in payload["errors"]
    )
    assert "ERROR:" not in completed.stdout
