"""Tests for the Issue #54 live-run provenance writer and validator.

Covers schema completeness, hash re-verification (including a genuine
tamper-detection case), the initial/final target-selection derivation from
the runtime switch-history log, atomic-write behavior, and the validator's
real exit codes (0 = pass, 1 = validation failure, 2 = usage/IO error).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRITER = REPO_ROOT / "tools/live/write_live_run_metadata.py"
VALIDATOR = REPO_ROOT / "tools/live/validate_live_run_metadata.py"

REQUIRED_KEYS = (
    "schema_version",
    "run_id",
    "recorded_at_utc",
    "bag",
    "invocation",
    "git",
    "hardware_software",
    "hashes",
    "resolved_parameters",
    "topic_qos_inventory",
    "target",
    "runtime_switch_history",
)


def _write_metadata(tmp_path: Path, *, extra_args: list[str] | None = None) -> Path:
    output = tmp_path / "run_metadata.json"
    args = [
        "python3",
        str(WRITER),
        "--output",
        str(output),
        "--run-id",
        "unit_test_run",
        "--scenario-tag",
        "unit",
        "--command",
        "start_live_stack.sh --record --tag unit",
        "--repo-root",
        str(REPO_ROOT),
        "--ros-distro",
        "jazzy",
        "--bag-kind",
        "video",
        "--bag-out-dir",
        str(tmp_path / "bag"),
        "--recorded-topic",
        "/camera/dashboard",
        "--param",
        "tracker_node:tracker_type=bytetrack",
        "--param",
        "tracker_node:max_age=30",
        "--skip-topic-introspection",
    ]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    return output


def test_writer_produces_all_required_schema_keys(tmp_path):
    output = _write_metadata(tmp_path)
    payload = json.loads(output.read_text(encoding="utf-8"))

    for key in REQUIRED_KEYS:
        assert key in payload, f"missing required key: {key}"
    assert payload["schema_version"] == 1


def test_writer_captures_a_real_git_commit_sha(tmp_path):
    output = _write_metadata(tmp_path)
    payload = json.loads(output.read_text(encoding="utf-8"))

    commit = payload["git"]["commit"]
    assert isinstance(commit, str)
    assert len(commit) == 40
    assert all(c in "0123456789abcdef" for c in commit)


def test_resolved_parameters_grouped_by_node(tmp_path):
    output = _write_metadata(
        tmp_path,
        extra_args=[
            "--param",
            "dashboard_bridge_node:camera_ref_w=640",
        ],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    params = payload["resolved_parameters"]
    assert params["tracker_node"] == {"tracker_type": "bytetrack", "max_age": "30"}
    assert params["dashboard_bridge_node"] == {"camera_ref_w": "640"}


def test_hash_file_records_sha256_for_existing_file_and_null_for_missing(tmp_path):
    real_file = tmp_path / "model.bin"
    real_file.write_bytes(b"hello world")
    expected_hash = hashlib.sha256(b"hello world").hexdigest()

    output = _write_metadata(
        tmp_path,
        extra_args=[
            "--hash-file",
            f"model={real_file}",
            "--hash-file",
            f"missing_model={tmp_path / 'does_not_exist.bin'}",
        ],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["hashes"]["model"]["exists"] is True
    assert payload["hashes"]["model"]["sha256"] == expected_hash
    assert payload["hashes"]["missing_model"]["exists"] is False
    assert payload["hashes"]["missing_model"]["sha256"] is None


def test_switch_history_initial_selection_is_the_literal_first_event_not_first_pick(tmp_path):
    log_path = tmp_path / "switch.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "generation": 0,
                        "reason": "startup",
                        "requested_target_id": None,
                        "authority_state": "cleared",
                    }
                ),
                json.dumps(
                    {
                        "generation": 1,
                        "reason": "operator_select",
                        "requested_target_id": 3,
                        "authority_state": "selection_requested",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    output = _write_metadata(
        tmp_path, extra_args=["--switch-history-log", str(log_path)]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["target"]["initial_selection"] is None
    assert payload["target"]["final_selection"] == 3
    assert payload["target"]["switch_count"] == 2
    assert len(payload["runtime_switch_history"]) == 2


def test_switch_history_final_selection_is_null_when_run_ends_cleared(tmp_path):
    log_path = tmp_path / "switch.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "generation": 0,
                        "reason": "startup",
                        "requested_target_id": None,
                        "authority_state": "cleared",
                    }
                ),
                json.dumps(
                    {
                        "generation": 1,
                        "reason": "operator_select",
                        "requested_target_id": 5,
                        "authority_state": "selection_requested",
                    }
                ),
                json.dumps(
                    {
                        "generation": 2,
                        "reason": "operator_clear",
                        "requested_target_id": None,
                        "authority_state": "cleared",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    output = _write_metadata(
        tmp_path, extra_args=["--switch-history-log", str(log_path)]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["target"]["final_selection"] is None
    assert payload["target"]["switch_count"] == 3


def test_write_is_atomic_no_leftover_temp_files(tmp_path):
    _write_metadata(tmp_path)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_validator_passes_on_well_formed_metadata(tmp_path):
    output = _write_metadata(tmp_path)
    result = subprocess.run(
        ["python3", str(VALIDATOR), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS]" in result.stdout


def test_validator_fails_when_hashed_file_is_tampered_after_the_run(tmp_path):
    real_file = tmp_path / "model.bin"
    real_file.write_bytes(b"original content")

    output = _write_metadata(
        tmp_path, extra_args=["--hash-file", f"model={real_file}"]
    )

    real_file.write_bytes(b"tampered content")

    result = subprocess.run(
        ["python3", str(VALIDATOR), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "does not match current file content" in result.stdout


def test_validator_fails_on_recorded_topic_with_zero_publishers(tmp_path):
    output = _write_metadata(tmp_path)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["topic_qos_inventory"]["/camera/dashboard"] = {
        "publisher_count": 0,
        "subscription_count": 1,
        "qos": {},
    }
    output.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        ["python3", str(VALIDATOR), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "had zero publishers at capture time" in result.stdout


def test_validator_exits_2_on_missing_file(tmp_path):
    result = subprocess.run(
        ["python3", str(VALIDATOR), str(tmp_path / "nope.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_validator_exits_2_on_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")

    result = subprocess.run(
        ["python3", str(VALIDATOR), str(bad)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_validator_rejects_missing_required_key(tmp_path):
    output = _write_metadata(tmp_path)
    payload = json.loads(output.read_text(encoding="utf-8"))
    del payload["git"]
    output.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        ["python3", str(VALIDATOR), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing required top-level key: git" in result.stdout
