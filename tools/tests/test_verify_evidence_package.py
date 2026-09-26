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


def _transport_module():
    spec = importlib.util.spec_from_file_location(
        "verify_recorder_transport",
        REPO_ROOT / "tools/live/verify_recorder_transport.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


vrt = _transport_module()


def _recorder_log(count: int) -> str:
    return (
        "[INFO] [1789397885.458867283] [rosbag2_recorder]: Recording stopped\n"
        f"[WARN] [1789397885.458942136] [rosbag2_recorder]: "
        f"Number of messages lost on the transport layer: {count}\n"
    )


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
    (logs / "rosbag.log").write_text(_recorder_log(0))
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

    (bag / vrt.REPORT_NAME).write_text(
        json.dumps(vrt.verify_transport(bag)), encoding="utf-8"
    )
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


def test_disarmed_state_scope_ignores_disconnect_outside_trial():
    result = vep._assess_disarmed_state_samples(
        [
            (90, False, False),
            (110, True, False),
            (150, True, False),
            (190, True, False),
            (210, False, False),
        ],
        trial_start_ns=100,
        trial_end_ns=200,
    )

    assert result["valid"] is True
    assert result["in_trial_sample_count"] == 3
    assert result["in_trial_connected_false_count"] == 0
    assert result["in_trial_armed_true_count"] == 0
    assert result["outside_trial_connected_false_count"] == 2


@pytest.mark.parametrize(
    ("connected", "armed", "reason_fragment"),
    (
        (False, False, "disconnected samples inside the trial interval"),
        (True, True, "armed samples inside the trial interval"),
    ),
)
def test_disarmed_state_scope_rejects_bad_state_inside_trial(
    connected, armed, reason_fragment
):
    result = vep._assess_disarmed_state_samples(
        [
            (110, True, False),
            (150, connected, armed),
            (190, True, False),
        ],
        trial_start_ns=100,
        trial_end_ns=200,
    )

    assert result["valid"] is False
    assert any(
        reason_fragment in reason
        for reason in result["reasons"]
    )


def test_disarmed_state_scope_rejects_empty_trial_window():
    result = vep._assess_disarmed_state_samples(
        [
            (90, True, False),
            (210, True, False),
        ],
        trial_start_ns=100,
        trial_end_ns=200,
    )

    assert result["valid"] is False
    assert any(
        "zero samples inside the trial interval" in reason
        for reason in result["reasons"]
    )


def test_disarmed_trial_window_uses_matching_run_and_trial(tmp_path):
    path = tmp_path / "operator_events.jsonl"
    rows = [
        {
            "schema_version": 1,
            "event": "trial_start",
            "ts_utc": "2026-09-26T09:00:00.000000Z",
            "run_id": "other",
            "trial_id": "p032_final_mounted_vga",
            "detail": {},
        },
        {
            "schema_version": 1,
            "event": "trial_start",
            "ts_utc": "2026-09-26T10:00:00.000000Z",
            "run_id": "evp_test",
            "trial_id": "p032_final_mounted_vga",
            "detail": {},
        },
        {
            "schema_version": 1,
            "event": "trial_end",
            "ts_utc": "2026-09-26T10:21:00.000000Z",
            "run_id": "evp_test",
            "trial_id": "p032_final_mounted_vga",
            "detail": {},
        },
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    result = vep._read_trial_window(
        path,
        run_id="evp_test",
        trial_id="p032_final_mounted_vga",
    )

    assert result["valid"] is True
    assert result["end_ns"] > result["start_ns"]


def test_disarmed_trial_window_requires_exact_start_and_end(tmp_path):
    path = tmp_path / "operator_events.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event": "trial_start",
                "ts_utc": "2026-09-26T10:00:00.000000Z",
                "run_id": "evp_test",
                "trial_id": "p032_final_mounted_vga",
                "detail": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = vep._read_trial_window(
        path,
        run_id="evp_test",
        trial_id="p032_final_mounted_vga",
    )

    assert result["valid"] is False
    assert any(
        "exactly one matching trial_end" in reason
        for reason in result["reasons"]
    )


def test_proven_disarmed_runtime_scope_marks_postflight_items_not_applicable(
    tmp_path, monkeypatch
):
    bag = _build_package(tmp_path)

    monkeypatch.setattr(
        vep,
        "_validate_disarmed_runtime_characterization",
        lambda bag_dir, run_id: {
            "valid": True,
            "scenario_tag": "p032_final_mounted_vga",
            "sample_count": 42,
            "connected_false_count": 0,
            "armed_true_count": 0,
            "reasons": [],
        },
    )

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
        disarmed_runtime_characterization=True,
    )

    assert status == "complete_runtime_evidence"
    assert report["runtime_status"] == "complete_runtime_evidence"
    assert report["pending"] == []
    assert report["pending_postflight"]["pixhawk_dataflash"]["applies"] is False
    assert report["pending_postflight"]["physical_v2_annotation"]["applies"] is False


def test_unproven_disarmed_runtime_scope_is_incomplete(tmp_path, monkeypatch):
    bag = _build_package(tmp_path)

    monkeypatch.setattr(
        vep,
        "_validate_disarmed_runtime_characterization",
        lambda bag_dir, run_id: {
            "valid": False,
            "scenario_tag": "p032_final_mounted_vga",
            "sample_count": 42,
            "connected_false_count": 0,
            "armed_true_count": 1,
            "reasons": ["/mavros/state contains 1 armed samples"],
        },
    )

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
        disarmed_runtime_characterization=True,
    )

    assert status == "incomplete_runtime_evidence"
    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "disarmed runtime characterization scope was not proven" in problem
        for problem in report["problems"]
    )


def test_disarmed_runtime_scope_rejects_wrong_scenario_before_bag_read(tmp_path):
    bag = _build_package(tmp_path)
    result = vep._validate_disarmed_runtime_characterization(
        bag,
        run_id="evp_test",
    )

    assert result["valid"] is False
    assert any(
        "scenario_tag=p032_final_mounted_vga" in reason
        for reason in result["reasons"]
    )


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
def _add_valid_mavros_dataflash(bag: Path, run_id: str = "evp_test"):
    archived = _add_valid_dataflash(bag, run_id=run_id)
    df = archived.parent
    manifest_path = df / "dataflash_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    payloads = {
        "before.json": b'{"schema_version":1,"entries":[{"id":20,"size":100}]}\n',
        "after.json": b'{"schema_version":1,"entries":[{"id":20,"size":100},{"id":21,"size":22}]}\n',
        "association.json": b'{"selected":{"id":21,"size":22}}\n',
        f"{archived.name}.retrieval.json": (
            b'{"log_id":21,"expected_size":22,"received_size":22}\n'
        ),
    }

    sidecars = {}
    provenance = []

    for name, payload in payloads.items():
        path = df / name
        path.write_bytes(payload)
        sidecars[name] = path
        provenance.append(
            {
                "name": name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    manifest["retrieval_method"] = (
        "mavros_explicit_id_with_catalogue_association"
    )
    manifest["retrieval_provenance"] = provenance
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    return archived, sidecars


def test_mavros_dataflash_provenance_sidecars_validate(tmp_path):
    bag = _build_package(tmp_path)
    _archived, sidecars = _add_valid_mavros_dataflash(bag)

    evidence = vep._validate_dataflash_manifest(
        bag / "pixhawk_dataflash" / "dataflash_manifest.json",
        run_id="evp_test",
    )

    assert evidence["valid"] is True
    provenance = evidence["retrieval_provenance"]
    assert provenance["required"] is True
    assert provenance["valid"] is True
    assert {item["name"] for item in provenance["files"]} == set(sidecars)


def test_mavros_dataflash_missing_sidecar_remains_pending(tmp_path):
    bag = _build_package(tmp_path)
    _archived, sidecars = _add_valid_mavros_dataflash(bag)
    sidecars["association.json"].unlink()

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
    )

    assert status == "pending_pixhawk_dataflash"
    evidence = report["pending_postflight"]["pixhawk_dataflash"]
    assert evidence["valid"] is False
    assert any(
        "retrieval provenance file is missing: association.json" in reason
        for reason in evidence["reasons"]
    )


def test_mavros_dataflash_tampered_sidecar_remains_pending(tmp_path):
    bag = _build_package(tmp_path)
    _archived, sidecars = _add_valid_mavros_dataflash(bag)
    sidecars["before.json"].write_bytes(b"tampered-provenance\n")

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
    )

    assert status == "pending_pixhawk_dataflash"
    evidence = report["pending_postflight"]["pixhawk_dataflash"]
    assert evidence["valid"] is False
    assert any(
        (
            "retrieval provenance byte count does not match manifest" in reason
            or "retrieval provenance SHA-256 does not match manifest" in reason
        )
        and "before.json" in reason
        for reason in evidence["reasons"]
    )


def test_mavros_dataflash_manifest_requires_provenance_list(tmp_path):
    bag = _build_package(tmp_path)
    _archived, _sidecars = _add_valid_mavros_dataflash(bag)

    manifest_path = bag / "pixhawk_dataflash" / "dataflash_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("retrieval_provenance")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
    )

    assert status == "pending_pixhawk_dataflash"
    evidence = report["pending_postflight"]["pixhawk_dataflash"]
    assert evidence["valid"] is False
    assert any(
        "retrieval_provenance missing or invalid" in reason
        for reason in evidence["reasons"]
    )


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


def test_no_control_field_recording_allows_absent_control_log(tmp_path):
    bag = _build_package(
        tmp_path,
        control=False,
        with_diag=False,
        with_operator=True,
    )
    (bag / "run_logs" / "control.log").unlink()

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=False,
        field_record=True,
        expect_operator_events=True,
        repo_root=REPO_ROOT,
    )

    assert report["optional"]["control_log"]["present"] is False
    assert not any("control_log" in p for p in report["problems"])
    assert not any(
        "/control_ref/diagnostics" in p
        for p in report["problems"]
    )
    assert report["runtime_status"] == "complete_runtime_evidence"
    assert status == "pending_pixhawk_dataflash"


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


def _refresh_transport(bag: Path, raw: Path | None = None) -> None:
    (bag / vrt.REPORT_NAME).write_text(
        json.dumps(vrt.verify_transport(bag, raw)), encoding="utf-8"
    )


def test_nonzero_main_transport_loss_makes_package_incomplete(tmp_path):
    bag = _build_package(tmp_path)
    (bag / "run_logs/rosbag.log").write_text(_recorder_log(2186))
    _refresh_transport(bag)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert report["bag_integrity_passed"] is True
    assert status == "incomplete_runtime_evidence"
    assert any("2186 transport losses" in problem for problem in report["problems"])


def test_unavailable_transport_loss_is_not_zero(tmp_path):
    bag = _build_package(tmp_path)
    (bag / "run_logs/rosbag.log").write_text(
        "[INFO] [1.0] [rosbag2_recorder]: Recording stopped\n"
    )
    _refresh_transport(bag)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=True, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT,
    )
    assert status == "incomplete_runtime_evidence"
    assert report["recorder_transport"]["recorders"]["main"]["status"] == "unavailable"


def test_paired_raw_transport_loss_and_integrity_are_required(tmp_path):
    bag = _build_package(tmp_path)
    raw = bag.parent / f"{bag.name}__image_raw"
    logs = raw / "run_logs"
    logs.mkdir(parents=True)
    (logs / "raw_image_bag.log").write_text(_recorder_log(3073))
    (logs / "archive_manifest.json").write_text(
        json.dumps({"schema_version": 1, "complete": True})
    )
    (raw / "bag_integrity.json").write_text(
        json.dumps({"schema_version": 1, "passed": True})
    )
    _refresh_transport(bag, raw)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT, expect_raw_bag=True,
    )
    assert status == "incomplete_runtime_evidence"
    assert report["raw_bag_integrity_passed"] is True
    assert any("raw_image recorder reported 3073" in p for p in report["problems"])
    (raw / "bag_integrity.json").unlink()
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False, field_record=True,
        expect_operator_events=True, repo_root=REPO_ROOT, expect_raw_bag=True,
    )
    assert status == "incomplete_runtime_evidence"
    assert any("raw bag integrity" in p for p in report["problems"])


def _add_visual_evidence(bag: Path, *, present: bool = True) -> None:
    visual = bag / "visual_evp_test.mkv"
    if present:
        visual.write_bytes(b"synthetic fixture; standalone verifier has a decode test")
    (bag / "run_logs/visual_record.log").write_text("")
    (bag / "visual_evidence_status.json").write_text(json.dumps({
        "run_id": "evp_test",
        "visual_file": str(visual),
        "passed": present,
        "recorder_alive_at_stop": present,
        "finalization": "graceful" if present else "failed",
    }))
    metadata_path = bag / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["visual"] = {
        "file": str(visual),
        "started_at_utc": "2026-09-14T20:00:00Z",
    }
    metadata_path.write_text(json.dumps(metadata))


def test_structured_visual_package_requires_matching_finalized_file(tmp_path):
    bag = _build_package(tmp_path, control=False)
    _add_visual_evidence(bag)
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False,
        field_record=False, expect_operator_events=False,
        repo_root=REPO_ROOT, expect_visual=True,
    )
    assert report["runtime_status"] == "complete_runtime_evidence"
    assert report["problems"] == []

    (bag / "visual_evp_test.mkv").unlink()
    status, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False,
        field_record=False, expect_operator_events=False,
        repo_root=REPO_ROOT, expect_visual=True,
    )
    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any("visual_file" in problem for problem in report["problems"])


def test_structured_visual_package_rejects_image_topic_and_failed_visual(tmp_path):
    bag = _build_package(tmp_path, control=False)
    _add_visual_evidence(bag, present=False)
    integrity_path = bag / "bag_integrity.json"
    integrity = json.loads(integrity_path.read_text())
    integrity["topic_message_counts"]["/camera/dashboard"] = 100
    integrity_path.write_text(json.dumps(integrity))
    _, report = vep.verify_package(
        bag_dir=bag, run_id="evp_test", control_trial=False,
        field_record=False, expect_operator_events=False,
        repo_root=REPO_ROOT, expect_visual=True,
    )
    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any("image topic" in problem for problem in report["problems"])
    assert any("visual evidence" in problem for problem in report["problems"])


def test_runtime_only_exit_accepts_pending_annotation_but_not_missing_visual(tmp_path):
    bag = _build_package(tmp_path, control=False)
    _add_visual_evidence(bag)
    command = [sys.executable, str(REPO_ROOT / "tools/live/verify_evidence_package.py"),
               "--bag-dir", str(bag), "--run-id", "evp_test", "--expect-visual",
               "--runtime-only"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((bag / "evidence_package_status.json").read_text())
    assert report["status"] == "pending_postflight_annotation"
    assert report["runtime_status"] == "complete_runtime_evidence"
    (bag / "visual_evp_test.mkv").unlink()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
# --------------------------------------------------------------------------- #
# Strict final B-C-B operator-event contract
# --------------------------------------------------------------------------- #

def _bcb_records(tag: str, *, run_id: str = "evp_test") -> list[dict]:
    if tag == "bcb_candidate":
        condition = "candidate"
        recovery_enabled = True
    else:
        condition = "baseline"
        recovery_enabled = False

    def record(event: str, detail: dict, index: int) -> dict:
        return {
            "schema_version": 1,
            "event": event,
            "ts_utc": f"2026-09-25T12:00:{index:02d}Z",
            "ts_monotonic_ns": 1_000_000_000 + index,
            "host": "test-host",
            "run_id": run_id,
            "trial_id": tag,
            "git_sha": "0" * 40,
            "detail": detail,
        }

    rows = [
        record("trial_start", {
            "condition": condition,
            "scenario": "bcb_three_opportunity",
            "recovery_enabled": recovery_enabled,
            "clock_pair": {"monotonic_ns": 1, "system_ns": 2},
        }, 1),
        record("target_selected", {
            "requested_track_id": 7,
            "method": "dashboard",
            "intended_physical_person": "selected test person",
        }, 2),
    ]

    opportunity_specs = (
        ("O1", "right_loss"),
        ("O2", "left_loss"),
        ("O3", "distractor_loss"),
    )
    index = 3
    for opportunity_id, scenario in opportunity_specs:
        rows.append(record("opportunity_start", {
            "opportunity_id": opportunity_id,
            "scenario": scenario,
            "observation_horizon_s": 10.0,
        }, index))
        index += 1
        rows.append(record("opportunity_end", {
            "opportunity_id": opportunity_id,
            "outcome": "completed",
        }, index))
        index += 1

    rows.extend([
        record("trial_end", {"end_reason": "nominal_complete"}, index),
        record("trial_verdict", {
            "verdict": "accepted",
            "integrity_reason": "fixture complete",
        }, index + 1),
    ])
    return rows


def _write_bcb_events(
    bag: Path,
    tag: str,
    *,
    records: list[dict] | None = None,
) -> Path:
    path = bag / "run_logs/operator_events.jsonl"
    rows = records if records is not None else _bcb_records(tag)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "tag",
    ("bcb_baseline_a", "bcb_candidate", "bcb_baseline_b"),
)
def test_strict_bcb_operator_event_contract_accepts_complete_trial(tmp_path, tag):
    bag = _build_package(tmp_path)
    _write_bcb_events(bag, tag)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities=tag,
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "complete_runtime_evidence"
    assert report["operator_event_validation"]["valid"] is True
    assert report["operator_event_validation"]["opportunity_outcomes"] == {
        "O1": "completed",
        "O2": "completed",
        "O3": "completed",
    }


def test_strict_bcb_rejects_malformed_json(tmp_path):
    bag = _build_package(tmp_path)
    path = bag / "run_logs/operator_events.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    status, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert status == "incomplete_runtime_evidence"
    assert any(
        "invalid JSON" in problem
        for problem in report["operator_event_validation"]["problems"]
    )


def test_strict_bcb_rejects_wrong_run_or_trial_identity(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_baseline_a")
    rows[2]["run_id"] = "wrong_run"
    rows[3]["trial_id"] = "bcb_candidate"
    _write_bcb_events(bag, "bcb_baseline_a", records=rows)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    problems = report["operator_event_validation"]["problems"]
    assert any("run_id" in problem for problem in problems)
    assert any("trial_id" in problem for problem in problems)


def test_strict_bcb_rejects_missing_and_duplicate_opportunity_boundaries(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_baseline_a")

    o1_start = next(
        row for row in rows
        if row["event"] == "opportunity_start"
        and row["detail"]["opportunity_id"] == "O1"
    )
    rows.insert(3, dict(o1_start))
    rows = [
        row for row in rows
        if not (
            row["event"] == "opportunity_end"
            and row["detail"]["opportunity_id"] == "O3"
        )
    ]
    _write_bcb_events(bag, "bcb_baseline_a", records=rows)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    problems = report["operator_event_validation"]["problems"]
    assert any("O1 opportunity_start" in problem for problem in problems)
    assert any("O3 opportunity_end" in problem for problem in problems)
    assert report["runtime_status"] == "incomplete_runtime_evidence"


def test_strict_bcb_rejects_changed_scenario_or_horizon(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_baseline_a")

    o1 = next(
        row for row in rows
        if row["event"] == "opportunity_start"
        and row["detail"]["opportunity_id"] == "O1"
    )
    o1["detail"]["scenario"] = "left_loss"

    o2 = next(
        row for row in rows
        if row["event"] == "opportunity_start"
        and row["detail"]["opportunity_id"] == "O2"
    )
    o2["detail"]["observation_horizon_s"] = 5.0

    _write_bcb_events(bag, "bcb_baseline_a", records=rows)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    problems = report["operator_event_validation"]["problems"]
    assert any("scenario" in problem for problem in problems)
    assert any("horizon" in problem for problem in problems)
    assert report["runtime_status"] == "incomplete_runtime_evidence"


def test_strict_bcb_rejects_candidate_with_recovery_disabled(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_candidate")
    rows[0]["detail"]["recovery_enabled"] = False
    _write_bcb_events(bag, "bcb_candidate", records=rows)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_candidate",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "recovery_enabled" in problem
        for problem in report["operator_event_validation"]["problems"]
    )


def test_strict_bcb_rejects_lifecycle_reordering(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_baseline_a")

    o1_end_index = next(
        i for i, row in enumerate(rows)
        if row["event"] == "opportunity_end"
        and row["detail"]["opportunity_id"] == "O1"
    )
    o2_start_index = next(
        i for i, row in enumerate(rows)
        if row["event"] == "opportunity_start"
        and row["detail"]["opportunity_id"] == "O2"
    )
    rows[o1_end_index], rows[o2_start_index] = (
        rows[o2_start_index],
        rows[o1_end_index],
    )

    _write_bcb_events(bag, "bcb_baseline_a", records=rows)

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "accepted B-C-B opportunity boundaries must be exactly" in problem
        for problem in report["operator_event_validation"]["problems"]
    )


def _bcb_rejected_prefix(
    tag: str,
    boundary_count: int,
    *,
    run_id: str = "evp_test",
) -> list[dict]:
    complete = _bcb_records(tag, run_id=run_id)
    boundaries = complete[2:8]

    rows = [complete[0]]

    if boundary_count > 0:
        rows.append(complete[1])

    rows.extend(boundaries[:boundary_count])

    base_index = 20

    def record(event: str, detail: dict, offset: int) -> dict:
        return {
            "schema_version": 1,
            "event": event,
            "ts_utc": f"2026-09-25T12:01:{base_index + offset:02d}Z",
            "ts_monotonic_ns": 2_000_000_000 + offset,
            "host": "test-host",
            "run_id": run_id,
            "trial_id": tag,
            "git_sha": "0" * 40,
            "detail": detail,
        }

    rows.extend([
        record(
            "abort",
            {
                "abort_class": "safety",
                "reason": "fixture safety abort",
            },
            0,
        ),
        record(
            "trial_end",
            {"end_reason": "pilot_abort"},
            1,
        ),
        record(
            "trial_verdict",
            {
                "verdict": "rejected",
                "integrity_reason": "fixture safety abort",
            },
            2,
        ),
    ])

    return rows


@pytest.mark.parametrize("boundary_count", (0, 1, 2, 3, 4, 5, 6))
def test_strict_bcb_accepts_rejected_coherent_prefix(
    tmp_path,
    boundary_count,
):
    bag = _build_package(tmp_path)
    rows = _bcb_rejected_prefix(
        "bcb_baseline_a",
        boundary_count,
    )
    _write_bcb_events(
        bag,
        "bcb_baseline_a",
        records=rows,
    )

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    validation = report["operator_event_validation"]
    assert report["runtime_status"] == "complete_runtime_evidence"
    assert validation["valid"] is True
    assert validation["trial_disposition"] == "rejected"
    assert validation["contract_path"] == "aborted_prefix"


def test_strict_bcb_rejected_prefix_does_not_require_fabricated_end(
    tmp_path,
):
    bag = _build_package(tmp_path)

    # Boundary count 3 means:
    # O1 start, O1 end, O2 start, then immediate abort.
    rows = _bcb_rejected_prefix(
        "bcb_candidate",
        3,
    )
    _write_bcb_events(
        bag,
        "bcb_candidate",
        records=rows,
    )

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_candidate",
        repo_root=REPO_ROOT,
    )

    validation = report["operator_event_validation"]
    assert validation["valid"] is True
    assert validation["opportunity_boundary_sequence"] == [
        "O1_start",
        "O1_end",
        "O2_start",
    ]
    assert validation["full_opportunity_sequence_recorded"] is False


def test_strict_bcb_rejected_run_requires_explicit_abort(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_rejected_prefix(
        "bcb_baseline_a",
        2,
    )
    rows = [
        row for row in rows
        if row["event"] != "abort"
    ]
    _write_bcb_events(
        bag,
        "bcb_baseline_a",
        records=rows,
    )

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "requires exactly one abort" in problem
        for problem
        in report["operator_event_validation"]["problems"]
    )


def test_strict_bcb_rejected_run_rejects_skipped_opportunity(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_rejected_prefix(
        "bcb_baseline_a",
        0,
    )

    complete = _bcb_records("bcb_baseline_a")

    # Insert target selection followed directly by O2 start: this is not a
    # coherent prefix because O1 was skipped.
    rows.insert(1, complete[1])
    rows.insert(2, complete[4])

    _write_bcb_events(
        bag,
        "bcb_baseline_a",
        records=rows,
    )

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "coherent prefix" in problem
        for problem
        in report["operator_event_validation"]["problems"]
    )


def test_strict_bcb_accepted_run_still_requires_full_triplet(tmp_path):
    bag = _build_package(tmp_path)
    rows = _bcb_records("bcb_baseline_a")

    rows = [
        row for row in rows
        if not (
            row["event"] == "opportunity_end"
            and row["detail"]["opportunity_id"] == "O3"
        )
    ]
    _write_bcb_events(
        bag,
        "bcb_baseline_a",
        records=rows,
    )

    _, report = vep.verify_package(
        bag_dir=bag,
        run_id="evp_test",
        control_trial=True,
        field_record=True,
        expect_operator_events=True,
        expect_bcb_opportunities="bcb_baseline_a",
        repo_root=REPO_ROOT,
    )

    assert report["runtime_status"] == "incomplete_runtime_evidence"
    assert any(
        "accepted B-C-B trial requires exactly one O3 opportunity_end"
        in problem
        for problem
        in report["operator_event_validation"]["problems"]
    )



def test_field_run_wrapper_activates_strict_contract_for_only_final_bcb_tags():
    wrapper = (
        REPO_ROOT / "tools/flight/verify_field_run.sh"
    ).read_text(encoding="utf-8")

    for tag in (
        "bcb_baseline_a",
        "bcb_candidate",
        "bcb_baseline_b",
    ):
        assert tag in wrapper

    assert 'ARGS+=(--expect-bcb-opportunities "$TAG")' in wrapper
    assert "final B-C-B tag requires --control-trial" in wrapper
