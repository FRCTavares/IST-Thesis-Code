"""Issue #50/#74: retained evidence-package completeness verifier (no ROS)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools/live/verify_evidence_package.py"
WRITER = REPO_ROOT / "tools/live/write_live_run_metadata.py"

CONTROL_DUMP = (
    "/control_ref_node:\n"
    "  ros__parameters:\n"
    "    enable_yaw_recovery: false\n"
    "    enable_diagnostics: true\n"
    "    rate_hz: 30.0\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("verify_evidence_package", MODULE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


vep = _load()


def _passing_run_metadata(dest: Path, tmp_path: Path) -> None:
    dump = tmp_path / "control_dump.yaml"
    dump.write_text(CONTROL_DUMP, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(WRITER), "--output", str(dest),
         "--run-id", "evp_test", "--command", "start_live_stack.sh --field-record",
         "--repo-root", str(REPO_ROOT), "--bag-kind", "video",
         "--bag-out-dir", str(dest.parent),
         "--recorded-topic", "/control_ref/cmd_vel",
         "--param", "tracker_node:tracker_type=bytetrack",
         "--skip-topic-introspection",
         "--resolved-node-params-file", f"control_ref_node={dump}",
         "--expect-param", "control_ref_node:enable_yaw_recovery=false"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def _integrity(passed: bool, diag_count: int = 600) -> dict:
    return {
        "schema_version": 1,
        "passed": passed,
        "topic_message_counts": {
            "/control_ref/cmd_vel": 600,
            "/control_ref/diagnostics": diag_count,
        },
    }


def _build_package(tmp_path: Path, *, control: bool = True,
                   with_diag: bool = True, with_operator: bool = True,
                   integrity_passed: bool = True, archive_complete: bool = True,
                   recorder_outcome: str = "graceful",
                   passing_provenance: bool = True) -> Path:
    bag = tmp_path / "run__video"
    logs = bag / "run_logs"
    logs.mkdir(parents=True)

    (bag / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    (bag / "run__video_0.mcap").write_bytes(b"x" * 4096)
    (bag / "flight_metadata.txt").write_text("run_id=evp_test\n")
    (bag / "target_authority_events.jsonl").write_text('{"event":"startup"}\n')
    (logs / "control.log").write_text("controller log\n")
    (logs / "dashboard_bridge.log").write_text("dashboard log\n")
    (logs / "target_memory_mars.log").write_text("tim log\n")
    (logs / "recorder_finalize_outcome.txt").write_text(recorder_outcome + "\n")
    if with_operator:
        (logs / "operator_events.jsonl").write_text('{"event":"trial_start"}\n')

    (logs / "archive_manifest.json").write_text(
        json.dumps({"schema_version": 1, "complete": archive_complete})
    )

    diag = 600 if with_diag else 0
    (bag / "bag_integrity.json").write_text(
        json.dumps(_integrity(integrity_passed, diag))
    )

    if passing_provenance:
        _passing_run_metadata(bag / "run_metadata.json", tmp_path)
    else:
        (bag / "run_metadata.json").write_text('{"schema_version": 1}\n')

    return bag


def _add_valid_dataflash(bag: Path, run_id: str = "evp_test") -> Path:
    df = bag / "pixhawk_dataflash"
    df.mkdir()
    archived = df / "00000001.BIN"
    payload = b"pixhawk-dataflash-test"
    archived.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "sha256_match": True,
        "archived": {
            "name": archived.name,
            "bytes": len(payload),
            "sha256": digest,
        },
    }
    (df / "dataflash_manifest.json").write_text(json.dumps(manifest))
    return archived


# --------------------------------------------------------------------------- #
def test_complete_runtime_evidence_when_all_present(tmp_path):
    bag = _build_package(tmp_path)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    # pending post-flight items are still reported, so the top-level status is
    # a pending marker -- but the runtime layer is complete
    assert report["runtime_status"] == "complete_runtime_evidence"
    assert report["problems"] == []
    assert "pending_pixhawk_dataflash" in report["pending"]
    assert "pending_postflight_annotation" in report["pending"]
    assert status == "pending_pixhawk_dataflash"


def test_dataflash_present_advances_to_pending_annotation(tmp_path):
    bag = _build_package(tmp_path)
    _add_valid_dataflash(bag)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert "pending_pixhawk_dataflash" not in report["pending"]
    assert status == "pending_postflight_annotation"


def test_both_postflight_present_is_complete(tmp_path):
    bag = _build_package(tmp_path)
    _add_valid_dataflash(bag)
    (bag / "trial_physical_v2.json").write_text("{}\n")
    status, _ = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "complete_runtime_evidence"


def test_empty_dataflash_manifest_remains_pending(tmp_path):
    bag = _build_package(tmp_path)
    df = bag / "pixhawk_dataflash"
    df.mkdir()
    (df / "dataflash_manifest.json").write_text("{}\n")
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    evidence = report["pending_postflight"]["pixhawk_dataflash"]
    assert evidence["manifest_present"] is True
    assert evidence["present"] is False
    assert evidence["valid"] is False
    assert "pending_pixhawk_dataflash" in report["pending"]
    assert status == "pending_pixhawk_dataflash"


def test_dataflash_wrong_run_id_remains_pending(tmp_path):
    bag = _build_package(tmp_path)
    _add_valid_dataflash(bag, run_id="different_run")
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "pending_pixhawk_dataflash"
    assert any(
        "run_id" in reason
        for reason in report["pending_postflight"]["pixhawk_dataflash"]["reasons"]
    )


def test_tampered_dataflash_archive_remains_pending(tmp_path):
    bag = _build_package(tmp_path)
    archived = _add_valid_dataflash(bag)
    archived.write_bytes(b"tampered")
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "pending_pixhawk_dataflash"
    evidence = report["pending_postflight"]["pixhawk_dataflash"]
    assert evidence["valid"] is False
    assert any(
        "byte count" in reason or "SHA-256" in reason
        for reason in evidence["reasons"]
    )


# F. missing required runtime artifact -> incomplete, nothing deleted
def test_missing_required_runtime_artifact_is_incomplete(tmp_path):
    bag = _build_package(tmp_path)
    (bag / "run_logs" / "control.log").unlink()
    before = sorted(str(p) for p in bag.rglob("*"))
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"
    assert any("control_log" in p for p in report["problems"])
    # nothing was removed
    assert all(Path(p).exists() for p in before)


# H. control field trial without /control_ref/diagnostics -> fail
def test_control_trial_without_diagnostics_is_incomplete(tmp_path):
    bag = _build_package(tmp_path, with_diag=False)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"
    assert any("/control_ref/diagnostics" in p for p in report["problems"])


# I. a non-control recording is not forced to require control/MAVROS evidence
def test_non_control_recording_not_forced_to_require_control(tmp_path):
    bag = _build_package(tmp_path, control=False, with_diag=False,
                         with_operator=False)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False, field_record=False,
        expect_operator_events=False, repo_root=REPO_ROOT,
    )
    # /control_ref/diagnostics not required here; operator events optional
    assert not any("/control_ref/diagnostics" in p for p in report["problems"])
    assert report["optional"]["operator_events_jsonl"]["present"] is False
    assert report["runtime_status"] == "complete_runtime_evidence"


def test_recorder_escalation_makes_package_incomplete(tmp_path):
    bag = _build_package(tmp_path, recorder_outcome="escalated")
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"
    assert any("escalation" in p for p in report["problems"])


def test_incomplete_archive_manifest_makes_package_incomplete(tmp_path):
    bag = _build_package(tmp_path, archive_complete=False)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"


def test_failed_bag_integrity_makes_package_incomplete(tmp_path):
    bag = _build_package(tmp_path, integrity_passed=False)
    status, _ = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"


def test_invalid_provenance_makes_package_incomplete(tmp_path):
    bag = _build_package(tmp_path, passing_provenance=False)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"
    assert report["provenance_validation"]["ran"] is True
    assert report["provenance_validation"]["passed"] is False


def test_missing_operator_events_optional_when_not_expected(tmp_path):
    bag = _build_package(tmp_path, with_operator=False)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=False, repo_root=REPO_ROOT,
    )
    assert report["optional"]["operator_events_jsonl"]["present"] is False
    assert report["runtime_status"] == "complete_runtime_evidence"
