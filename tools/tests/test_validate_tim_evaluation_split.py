"""Tests for the frozen tuning/final-test split gate."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "validate_tim_evaluation_split.py"
)
SPEC = importlib.util.spec_from_file_location(
    "validate_tim_evaluation_split",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze_git_repo(root: Path) -> str:
    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test User"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "config",
            "user.email",
            "test@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "add",
            "config.yaml",
            "source.py",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "commit",
            "-q",
            "-m",
            "freeze config",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def ready_entry(
    root: Path,
    entry_id: str,
    set_name: str,
):
    source = root / "bags" / set_name / entry_id
    source.mkdir(parents=True)
    bag_data = f"bag:{entry_id}".encode()
    bag = source / "bag.mcap"
    bag.write_bytes(bag_data)

    annotation = root / "annotations" / f"{entry_id}.csv"
    annotation.parent.mkdir(parents=True, exist_ok=True)
    annotation_data = f"annotation:{entry_id}".encode()
    annotation.write_bytes(annotation_data)

    return {
        "id": entry_id,
        "status": "ready",
        "scenario": f"scenario {entry_id}",
        "source_path": str(source.relative_to(root)),
        "annotation_path": str(annotation.relative_to(root)),
        "annotation_sha256": digest(annotation_data),
        "selected_target_id": 1,
        "people_group": f"people_{entry_id}",
        "clothing_group": f"clothing_{entry_id}",
        "overlap_record": "explicitly recorded",
        "historical_exposure": "none",
        "files": [
            {
                "path": str(bag.relative_to(root)),
                "size_bytes": len(bag_data),
                "sha256": digest(bag_data),
            }
        ],
    }


def pending_entry(entry_id: str):
    return {
        "id": entry_id,
        "status": "reserved_pending_capture",
        "scenario": f"scenario {entry_id}",
        "expected_source_path": f"bags/final/{entry_id}",
        "people_group": "pending_capture",
        "clothing_group": "pending_capture",
        "overlap_record": "pending explicit record",
        "files": [],
    }


def manifest(root: Path, *, final_ready: bool):
    config_data = b"canonical: true\n"
    config = root / "config.yaml"
    config.write_bytes(config_data)
    source = root / "source.py"
    source.write_text("frozen = True\n")
    algorithm_commit = freeze_git_repo(root)

    if final_ready:
        final = [
            ready_entry(root, f"final_{index}", "final")
            for index in range(3)
        ]
    else:
        final = [
            pending_entry(f"final_{index}")
            for index in range(3)
        ]

    return {
        "schema_version": 1,
        "split_id": "test_split",
        "freeze": {
            "created_date": "2026-07-23",
            "algorithm_commit": algorithm_commit,
            "canonical_config": {
                "path": "config.yaml",
                "sha256": digest(config_data),
            },
            "policy": {
                "tuning_allowed_sets": ["development"],
                "final_held_out_outcome_access": "integrity only",
                "threshold_change_after_final_access": "new split",
                "legacy_validation_use": "diagnostic only",
            },
        },
        "sets": {
            "development": [
                ready_entry(root, "dev_1", "development")
            ],
            "legacy_validation": [],
            "final_held_out": final,
        },
    }


def validate(value, root, **overrides):
    return MODULE.validate_manifest(
        value,
        repo_root=root,
        verify_hashes=overrides.get("verify_hashes", False),
        require_final_ready=overrides.get(
            "require_final_ready",
            False,
        ),
    )


def test_reserved_final_set_passes_freeze_but_not_release_gate(
    tmp_path,
):
    value = manifest(tmp_path, final_ready=False)

    assert validate(value, tmp_path) == []
    errors = validate(
        value,
        tmp_path,
        require_final_ready=True,
    )
    assert len(errors) == 1
    assert "final held-out set is not ready" in errors[0]


def test_complete_final_set_passes_hash_and_release_gate(
    tmp_path,
):
    value = manifest(tmp_path, final_ready=True)

    assert validate(
        value,
        tmp_path,
        verify_hashes=True,
        require_final_ready=True,
    ) == []


def test_source_path_cannot_appear_in_two_sets(tmp_path):
    value = manifest(tmp_path, final_ready=True)
    value["sets"]["final_held_out"][0]["source_path"] = (
        value["sets"]["development"][0]["source_path"]
    )

    errors = validate(value, tmp_path)

    assert any(
        "source path appears in more than one set" in error
        for error in errors
    )


def test_hash_mutation_is_detected(tmp_path):
    value = manifest(tmp_path, final_ready=True)
    frozen_file = value["sets"]["development"][0]["files"][0]
    (tmp_path / frozen_file["path"]).write_bytes(b"mutated")
    frozen_file["size_bytes"] = len(b"mutated")

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any("SHA-256 mismatch" in error for error in errors)


def test_people_and_clothing_overlap_record_is_mandatory(
    tmp_path,
):
    value = manifest(tmp_path, final_ready=True)
    value["sets"]["final_held_out"][1]["overlap_record"] = ""

    errors = validate(value, tmp_path)

    assert any(
        "missing non-empty overlap_record" in error
        for error in errors
    )


def test_only_development_set_may_be_used_for_tuning(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    value["freeze"]["policy"]["tuning_allowed_sets"] = [
        "development",
        "final_held_out",
    ]

    errors = validate(value, tmp_path)

    assert any("tuning_allowed_sets" in error for error in errors)

def test_algorithm_commit_must_be_full_sha(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    value["freeze"]["algorithm_commit"] = "abc123"

    errors = validate(value, tmp_path)

    assert any(
        "full 40-character lowercase Git commit SHA" in error
        for error in errors
    )


def test_missing_frozen_algorithm_commit_is_detected(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    value["freeze"]["algorithm_commit"] = "f" * 40

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any(
        "frozen algorithm commit does not exist" in error
        for error in errors
    )


def test_frozen_commit_config_hash_must_match_manifest(tmp_path):
    value = manifest(tmp_path, final_ready=False)

    changed = b"canonical: changed\n"
    config = tmp_path / "config.yaml"
    config.write_bytes(changed)

    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "config.yaml"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "commit",
            "-q",
            "-m",
            "change config after freeze",
        ],
        check=True,
    )

    value["freeze"]["canonical_config"]["sha256"] = digest(changed)

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert not any(
        error == "canonical config SHA-256 mismatch"
        for error in errors
    )
    assert any(
        "frozen commit canonical config SHA-256 mismatch" in error
        for error in errors
    )
def bind_final_comparison_contract(root, value):
    asset = root / "asset.bin"
    asset_data = b"frozen comparison asset"
    asset.write_bytes(asset_data)

    contract = {
        "schema_version": 1,
        "contract_id": "test_final_comparison",
        "algorithm_freeze_commit": value["freeze"][
            "algorithm_commit"
        ],
        "held_out_split": {
            "path": "split.json",
            "split_id": value["split_id"],
            "sequence_ids": [
                entry["id"]
                for entry in value["sets"]["final_held_out"]
            ],
        },
        "common_detector": {
            "model": {
                "path": "asset.bin",
                "size_bytes": len(asset_data),
                "sha256": digest(asset_data),
            },
        },
        "primary_architectures": [
            {"id": "bytetrack_raw"},
            {
                "id": "target_reid_090",
                "threshold": 0.90,
            },
            {"id": "bytetrack_tim_mars"},
            {"id": "deepsort_raw"},
        ],
        "source_code_freeze": {
            "commit": value["freeze"]["algorithm_commit"],
            "required_unchanged_paths": ["source.py"],
        },
    }

    contract_path = root / "comparison.json"
    contract_path.write_text(
        __import__("json").dumps(contract, indent=2) + "\n"
    )

    value["freeze"]["final_comparison_contract"] = {
        "path": "comparison.json",
        "sha256": digest(contract_path.read_bytes()),
        "contract_id": "test_final_comparison",
    }

    return contract_path


def test_bound_final_comparison_contract_passes(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    bind_final_comparison_contract(tmp_path, value)

    assert validate(
        value,
        tmp_path,
        verify_hashes=True,
    ) == []


def test_final_comparison_contract_mutation_is_detected(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    contract_path = bind_final_comparison_contract(
        tmp_path,
        value,
    )

    contract_path.write_text("{}\n")

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any(
        "final comparison contract SHA-256 mismatch" in error
        for error in errors
    )


def test_final_comparison_asset_mutation_is_detected(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    bind_final_comparison_contract(tmp_path, value)

    (tmp_path / "asset.bin").write_bytes(b"mutated asset")

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any(
        "final comparison frozen asset" in error
        for error in errors
    )


def test_behavior_source_drift_is_detected(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    bind_final_comparison_contract(tmp_path, value)

    (tmp_path / "source.py").write_text("frozen = False\n")

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any(
        "behavior-bearing source code differs" in error
        for error in errors
    )


def test_target_reid_final_threshold_is_frozen(tmp_path):
    value = manifest(tmp_path, final_ready=False)
    contract_path = bind_final_comparison_contract(
        tmp_path,
        value,
    )

    import json

    contract = json.loads(contract_path.read_text())
    contract["primary_architectures"][1]["threshold"] = 0.85
    contract_path.write_text(
        json.dumps(contract, indent=2) + "\n"
    )

    value["freeze"]["final_comparison_contract"]["sha256"] = (
        digest(contract_path.read_bytes())
    )

    errors = validate(
        value,
        tmp_path,
        verify_hashes=True,
    )

    assert any(
        "Target-ReID threshold must be 0.90" in error
        for error in errors
    )
