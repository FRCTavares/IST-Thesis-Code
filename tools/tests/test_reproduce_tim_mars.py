"""Tests for the top-level TIM-MARS reproducibility command."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "reproduce_tim_mars.py"

SPEC = importlib.util.spec_from_file_location(
    "reproduce_tim_mars",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_aggregate(
    directory: Path,
    *,
    csv_wrong: float = 1.25,
    json_wrong: float = 1.25,
) -> tuple[Path, Path]:
    csv_path = directory / "matrix_aggregate.csv"
    json_path = directory / "matrix_aggregate.json"

    row = {
        "sequence_id": "aggregate",
        "row_id": MODULE.FINAL_ROW_ID,
        "label": "Final simplified TIM-MARS",
        "wrong_target_duration_s": csv_wrong,
        "safe_vs_raw": True,
    }

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(row),
        )
        writer.writeheader()
        writer.writerow(row)

    json_row = dict(row)
    json_row["wrong_target_duration_s"] = json_wrong
    json_path.write_text(
        json.dumps([json_row]),
        encoding="utf-8",
    )
    return csv_path, json_path


def test_split_validator_uses_positional_manifest():
    split = REPO_ROOT / "split.json"

    command = MODULE.validate_split_command(
        repo_root=REPO_ROOT,
        split_path=split,
        set_name="development",
    )

    assert command[2] == str(split)
    assert "--split" not in command
    assert "--verify-hashes" in command
    assert "--require-final-ready" not in command


def test_final_split_validation_is_fail_closed():
    split = REPO_ROOT / "split.json"

    command = MODULE.validate_split_command(
        repo_root=REPO_ROOT,
        split_path=split,
        set_name="final_held_out",
    )

    assert "--require-final-ready" in command


def test_matrix_command_uses_explicit_output_roots(tmp_path):
    command = MODULE.matrix_command(
        repo_root=REPO_ROOT,
        set_name="development",
        output_root=tmp_path / "bags",
        report_root=tmp_path / "reports",
        model_path=tmp_path / "model.pb",
        sequence_ids=["seq_a", "seq_b"],
        resume=True,
        dry_run=True,
    )

    assert "--output-root" in command
    assert "--report-root" in command
    assert command.count("--sequence") == 2
    assert "--resume" in command
    assert "--dry-run" in command
    assert "--skip-source-hash" not in command


def test_matching_csv_and_json_pass(tmp_path):
    csv_path, json_path = write_aggregate(tmp_path)

    assert MODULE.verify_csv_json_consistency(
        csv_path,
        json_path,
    ) == []


def test_inconsistent_csv_and_json_fail(tmp_path):
    csv_path, json_path = write_aggregate(
        tmp_path,
        csv_wrong=1.25,
        json_wrong=1.50,
    )

    errors = MODULE.verify_csv_json_consistency(
        csv_path,
        json_path,
    )

    assert errors
    assert "wrong_target_duration_s" in errors[0]


def test_fingerprint_validation_detects_tampering(tmp_path):
    target = tmp_path / "artifact.json"
    fingerprint = tmp_path / "artifact.sha256"

    target.write_text('{"value": 1}\n', encoding="utf-8")
    fingerprint.write_text(
        f"{MODULE.sha256_file(target)}  {target.name}\n",
        encoding="utf-8",
    )

    assert MODULE.verify_fingerprint(fingerprint, target) == []

    target.write_text('{"value": 2}\n', encoding="utf-8")
    errors = MODULE.verify_fingerprint(fingerprint, target)

    assert errors
    assert "SHA-256 mismatch" in errors[0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("True", True),
        ("False", False),
        ("1", 1),
        ("1.25", 1.25),
        ("text", "text"),
    ],
)
def test_parse_scalar(value, expected):
    assert MODULE.parse_scalar(value) == expected
