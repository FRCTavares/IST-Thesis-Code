"""Tests for the Issue #58 SORT+TIM calibration runner.

These validate the manifest/tooling contract before any calibration outcome
exists: reused-grid determinism, manifest scope guards, canonical-hash
fail-closed materialization, and held-out/pending-annotation rejection.
None of them execute TIM-MARS or require the real SORT replay bags.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "tools" / "experiments" / "run_tim_tracker_calibration.py"
MANIFEST_PATH = (
    REPO_ROOT
    / "docs"
    / "data"
    / "lightweight_vs_integrated_tracking"
    / "p058_sort_tim_calibration_v1.yaml"
)
GRID_SOURCE_PATH = (
    REPO_ROOT
    / "docs"
    / "data"
    / "parameter_sensitivity"
    / "tim_mars_parameter_sensitivity_v1.yaml"
)
CANONICAL_PATH = (
    REPO_ROOT
    / "ros2_ws"
    / "src"
    / "thesis_bringup"
    / "config"
    / "tim_mars_canonical.yaml"
)

SPEC = importlib.util.spec_from_file_location(
    "run_tim_tracker_calibration", RUNNER_PATH
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_manifest_scoped_to_issue_58_and_sort():
    manifest = MODULE.load_calibration_manifest()
    assert manifest["issue"] == 58
    assert manifest["tracker_type"] == "sort"
    assert manifest["schema_version"] == 1


def test_manifest_declares_exactly_one_calibration_sequence():
    # SORT annotations currently exist only for dev_may_hard_reentry; the
    # manifest must not silently claim broader coverage.
    manifest = MODULE.load_calibration_manifest()
    assert len(manifest["calibration_sequences"]) == 1
    assert manifest["calibration_sequences"][0]["id"] == "dev_may_hard_reentry"


def test_dev_june_seq01_is_rejected_if_present(tmp_path, monkeypatch):
    manifest_dict = yaml.safe_load(MANIFEST_PATH.read_text())
    # Replace (not append) so the sequence-count guard doesn't fire first;
    # this isolates the dev_june_seq01-specific rejection being tested.
    manifest_dict["calibration_sequences"] = [
        {
            "id": "dev_june_seq01",
            "split_membership_id": "dev_june_seq01",
            "sort_tracks_bag": "unused",
            "annotation_path": "unused",
            "selected_track_id": 1,
        }
    ]
    bad_path = tmp_path / "bad_manifest.yaml"
    bad_path.write_text(yaml.safe_dump(manifest_dict))
    monkeypatch.setattr(MODULE, "CALIBRATION_MANIFEST_PATH", bad_path)

    with pytest.raises(ValueError, match="pending"):
        MODULE.load_calibration_manifest()


def test_held_out_split_member_is_rejected(tmp_path, monkeypatch):
    manifest_dict = yaml.safe_load(MANIFEST_PATH.read_text())
    manifest_dict["calibration_sequences"][0]["split_membership_id"] = (
        "H01_final_held_out"
    )
    bad_path = tmp_path / "bad_manifest.yaml"
    bad_path.write_text(yaml.safe_dump(manifest_dict))
    monkeypatch.setattr(MODULE, "CALIBRATION_MANIFEST_PATH", bad_path)

    with pytest.raises(ValueError, match="held-out"):
        MODULE.load_calibration_manifest()


def test_reused_grid_produces_29_configurations_matching_issue_31():
    canonical = MODULE.canonical_parameters(
        MODULE.load_yaml_mapping(CANONICAL_PATH)
    )
    configurations = MODULE.derive_grid(canonical)
    assert len(configurations) == 29
    ids = [c["id"] for c in configurations]
    assert len(set(ids)) == 29
    assert ids[0] == "baseline"
    dimensions = {c["dimension_id"] for c in configurations if c["dimension_id"]}
    assert len(dimensions) == 7


def test_dimension_grid_is_read_not_copied():
    # The runner must not embed its own copy of the 7-dimension grid; it
    # must load the real, currently-committed Issue #31 manifest file.
    assert MODULE.DIMENSION_GRID_SOURCE == GRID_SOURCE_PATH
    assert MODULE.DIMENSION_GRID_SOURCE.is_file()


def test_materialize_writes_issue_58_scoped_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "output_root", lambda: tmp_path / "out")
    canonical = MODULE.canonical_parameters(
        MODULE.load_yaml_mapping(CANONICAL_PATH)
    )
    configurations = MODULE.derive_grid(canonical)
    manifest = MODULE.load_calibration_manifest()

    lock = MODULE.materialize(configurations, manifest)

    assert lock["issue"] == 58
    assert lock["purpose"] == "sort_tim_calibration"
    assert lock["tracker_type"] == "sort"
    assert len(lock["materialized_configs"]) == 29
    assert lock["canonical_config"]["sha256"] == (
        "e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931"
    )


def test_materialized_baseline_is_byte_identical_to_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "output_root", lambda: tmp_path / "out")
    canonical = MODULE.canonical_parameters(
        MODULE.load_yaml_mapping(CANONICAL_PATH)
    )
    configurations = MODULE.derive_grid(canonical)
    manifest = MODULE.load_calibration_manifest()

    MODULE.materialize(configurations, manifest)

    baseline_path = tmp_path / "out" / "configs" / "baseline.yaml"
    assert baseline_path.read_bytes() == CANONICAL_PATH.read_bytes()


def test_canonical_yaml_is_never_modified_by_materialization(tmp_path, monkeypatch):
    before = CANONICAL_PATH.read_bytes()
    monkeypatch.setattr(MODULE, "output_root", lambda: tmp_path / "out")
    canonical = MODULE.canonical_parameters(
        MODULE.load_yaml_mapping(CANONICAL_PATH)
    )
    configurations = MODULE.derive_grid(canonical)
    manifest = MODULE.load_calibration_manifest()
    MODULE.materialize(configurations, manifest)
    assert CANONICAL_PATH.read_bytes() == before


def test_expected_cell_count_is_29():
    assert MODULE.EXPECTED_CELLS == 29
    assert MODULE.EXPECTED_SEQUENCES == 1
    assert MODULE.EXPECTED_CONFIGURATIONS == 29
