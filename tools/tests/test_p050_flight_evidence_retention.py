"""Tests for Issue #50/#74 retained-flight evidence plumbing.

Covers:
 - exact-RUN_ID run-log archival (never a `latest` lookup);
 - refusal to overwrite an existing retained evidence destination;
 - explicit (never fabricated) handling of a missing required log;
 - the live `control_ref_node` parameter capture in run provenance,
   including that a failed query is not silently replaced with defaults;
 - append-only operator event log semantics;
 - abort events requiring a class and reason;
 - per-RUN_ID operator-event file separation;
 - operator-event archival into the retained package.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE = REPO_ROOT / "tools" / "live"
WRITER = LIVE / "write_live_run_metadata.py"
VALIDATOR = LIVE / "validate_live_run_metadata.py"

REQUIRED_CONTROL_PARAMS = (
    "rate_hz",
    "img_w",
    "img_h",
    "desired_h_norm",
    "stale_timeout_s",
    "yaw_kp",
    "forward_kp",
    "lateral_kp",
    "deadband_ex",
    "deadband_h",
    "max_yaw_z",
    "max_vx",
    "max_vy",
    "max_delta_yaw_z",
    "max_delta_vx",
    "max_delta_vy",
    "use_lateral",
    "enable_yaw_recovery",
    "recovery_yaw_rate",
    "recovery_max_duration_s",
    "recovery_max_integrated_yaw_rad",
    "recovery_last_trusted_max_age_s",
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, LIVE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


archive_run_evidence = _load("archive_run_evidence")
operator_event = _load("operator_event")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_run_dir(root: Path, name: str, logs: dict[str, str]) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    for filename, content in logs.items():
        (run_dir / filename).write_text(content, encoding="utf-8")
    return run_dir


CONTROL_DUMP_YAML = (
    "/control_ref_node:\n"
    "  ros__parameters:\n"
    + "".join(
        f"    {name}: {value}\n"
        for name, value in {
            "rate_hz": "30.0",
            "img_w": "640.0",
            "img_h": "640.0",
            "desired_h_norm": "0.25",
            "stale_timeout_s": "0.9",
            "future_tolerance_s": "0.25",
            "yaw_kp": "0.4",
            "forward_kp": "0.4",
            "lateral_kp": "0.0",
            "deadband_ex": "0.03",
            "deadband_h": "0.02",
            "max_yaw_z": "0.1",
            "max_vx": "0.1",
            "max_vy": "0.1",
            "max_delta_yaw_z": "0.03",
            "max_delta_vx": "0.03",
            "max_delta_vy": "0.03",
            "use_lateral": "false",
            "invert_yaw": "false",
            "enable_yaw_recovery": "false",
            "recovery_yaw_rate": "0.1",
            "recovery_max_duration_s": "1.0",
            "recovery_max_integrated_yaw_rad": "0.1",
            "recovery_last_trusted_max_age_s": "1.0",
        }.items()
    )
)


def _write_provenance(tmp_path: Path, extra_args: list[str]) -> Path:
    output = tmp_path / "run_metadata.json"
    args = [
        sys.executable,
        str(WRITER),
        "--output",
        str(output),
        "--run-id",
        "unit_flight_run",
        "--command",
        "start_live_stack.sh --field-record --control-mavros --tag unit",
        "--repo-root",
        str(REPO_ROOT),
        "--bag-kind",
        "video",
        "--bag-out-dir",
        str(tmp_path / "bag"),
        "--recorded-topic",
        "/control_ref/cmd_vel",
        "--param",
        "tracker_node:tracker_type=bytetrack",
        "--skip-topic-introspection",
        *extra_args,
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return output


def _validate(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# A. exact-run log archival
# --------------------------------------------------------------------------- #
def test_archival_uses_explicit_run_id_not_latest(tmp_path):
    logs_a = {
        "control.log": "RUN A controller\n",
        "dashboard_bridge.log": "RUN A dashboard\n",
        "target_memory_mars.log": "RUN A tim\n",
    }
    run_a = _make_run_dir(tmp_path, "run_a", logs_a)
    run_b = _make_run_dir(
        tmp_path,
        "run_b",
        {k: v.replace("RUN A", "RUN B") for k, v in logs_a.items()},
    )
    latest = tmp_path / "latest"
    latest.symlink_to(run_b, target_is_directory=True)

    bag = tmp_path / "bag_a"
    bag.mkdir()

    code = archive_run_evidence.main(
        ["--run-dir", str(run_a), "--run-id", "run_a", "--bag-dir", str(bag)]
    )
    assert code == 0

    dest = bag / "run_logs"
    assert (dest / "control.log").read_text() == "RUN A controller\n"
    assert (dest / "target_memory_mars.log").read_text() == "RUN A tim\n"

    manifest = json.loads((dest / "archive_manifest.json").read_text())
    assert manifest["run_dir"] == str(run_a.resolve())
    assert manifest["run_id"] == "run_a"
    assert manifest["complete"] is True
    assert Path(manifest["run_dir"]) != run_b.resolve()


# --------------------------------------------------------------------------- #
# B. no overwrite
# --------------------------------------------------------------------------- #
def test_archival_refuses_to_overwrite_existing_evidence(tmp_path):
    run = _make_run_dir(
        tmp_path,
        "run",
        {
            "control.log": "fresh\n",
            "dashboard_bridge.log": "fresh\n",
            "target_memory_mars.log": "fresh\n",
        },
    )
    bag = tmp_path / "bag"
    (bag / "run_logs").mkdir(parents=True)
    sentinel = bag / "run_logs" / "control.log"
    sentinel.write_text("ALREADY RETAINED - DO NOT TOUCH\n", encoding="utf-8")

    code = archive_run_evidence.main(
        ["--run-dir", str(run), "--run-id", "run", "--bag-dir", str(bag)]
    )
    assert code == 3
    assert sentinel.read_text() == "ALREADY RETAINED - DO NOT TOUCH\n"
    assert not (bag / "run_logs" / "archive_manifest.json").exists()
    # source logs untouched
    assert (run / "control.log").read_text() == "fresh\n"


# --------------------------------------------------------------------------- #
# C. missing required log
# --------------------------------------------------------------------------- #
def test_archival_records_missing_required_log_without_faking_it(tmp_path):
    run = _make_run_dir(
        tmp_path,
        "run",
        {
            "control.log": "c\n",
            "dashboard_bridge.log": "d\n",
            # target_memory_mars.log deliberately absent
        },
    )
    bag = tmp_path / "bag"
    bag.mkdir()

    code = archive_run_evidence.main(
        ["--run-dir", str(run), "--run-id", "run", "--bag-dir", str(bag)]
    )
    assert code == 1

    dest = bag / "run_logs"
    manifest = json.loads((dest / "archive_manifest.json").read_text())
    assert manifest["missing_required"] == ["target_memory_mars.log"]
    assert manifest["complete"] is False
    assert manifest["required_logs"]["target_memory_mars.log"]["status"] == "missing"
    # no fabricated placeholder file
    assert not (dest / "target_memory_mars.log").exists()
    # the logs that do exist were still copied
    assert (dest / "control.log").read_text() == "c\n"


# --------------------------------------------------------------------------- #
# D. controller provenance
# --------------------------------------------------------------------------- #
def test_control_ref_params_captured_from_runtime_query_and_validate(tmp_path):
    dump = tmp_path / "control_dump.yaml"
    dump.write_text(CONTROL_DUMP_YAML, encoding="utf-8")

    output = _write_provenance(
        tmp_path,
        [
            "--resolved-node-params-file",
            f"control_ref_node={dump}",
            "--expect-param",
            "control_ref_node:enable_yaw_recovery=false",
        ],
    )
    payload = json.loads(output.read_text())

    control = payload["resolved_parameters"]["control_ref_node"]
    for name in REQUIRED_CONTROL_PARAMS:
        assert name in control, f"missing captured control param: {name}"
    assert control["enable_yaw_recovery"] == "false"

    meta = payload["resolved_parameters_meta"]["control_ref_node"]
    assert meta["query_ok"] is True
    assert meta["source"] == "file"
    assert payload["expected_parameters"]["control_ref_node"] == {
        "enable_yaw_recovery": "false"
    }

    result = _validate(output)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS]" in result.stdout


def test_failed_control_query_is_not_replaced_with_defaults_and_fails_validation(
    tmp_path,
):
    # A live query that is skipped/unavailable must be recorded as a failure,
    # never backfilled from source-code defaults.
    output = _write_provenance(
        tmp_path,
        [
            "--resolved-node-params",
            "control_ref_node",
            "--skip-node-param-query",
            "--expect-param",
            "control_ref_node:enable_yaw_recovery=false",
        ],
    )
    payload = json.loads(output.read_text())

    assert "control_ref_node" not in payload["resolved_parameters"]
    meta = payload["resolved_parameters_meta"]["control_ref_node"]
    assert meta["query_ok"] is False
    assert "error" in meta

    result = _validate(output)
    assert result.returncode == 1
    assert "parameter query failed" in result.stdout
    assert "control_ref_node" in result.stdout


def test_expect_param_value_mismatch_fails_validation(tmp_path):
    dump = tmp_path / "control_dump.yaml"
    dump.write_text(
        CONTROL_DUMP_YAML.replace(
            "enable_yaw_recovery: false", "enable_yaw_recovery: true"
        ),
        encoding="utf-8",
    )
    output = _write_provenance(
        tmp_path,
        [
            "--resolved-node-params-file",
            f"control_ref_node={dump}",
            "--expect-param",
            "control_ref_node:enable_yaw_recovery=false",
        ],
    )
    result = _validate(output)
    assert result.returncode == 1
    assert "expected parameter control_ref_node:enable_yaw_recovery" in result.stdout


# --------------------------------------------------------------------------- #
# E. operator events append
# --------------------------------------------------------------------------- #
def test_operator_events_append_in_order_without_truncation(tmp_path):
    common = ["--run-id", "run_e", "--log-dir", str(tmp_path)]
    assert (
        operator_event.main(
            ["trial_start", *common, "--condition", "baseline", "--scenario", "following"]
        )
        == 0
    )
    assert (
        operator_event.main(
            ["abort", *common, "--abort-class", "safety", "--reason", "wrong target"]
        )
        == 0
    )

    log_path = tmp_path / "run_e" / "operator_events.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["event"] == "trial_start"
    assert second["event"] == "abort"
    for record in (first, second):
        assert record["schema_version"] == 1
        assert record["run_id"] == "run_e"
        assert operator_event.validate_event(record) == []

    # a third append must not truncate the first two
    assert (
        operator_event.main(
            ["trial_end", *common, "--end-reason", "nominal_complete"]
        )
        == 0
    )
    lines_after = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after) == 3
    assert lines_after[:2] == lines


# --------------------------------------------------------------------------- #
# F. abort reason required
# --------------------------------------------------------------------------- #
def test_abort_without_class_or_reason_is_rejected(tmp_path):
    with pytest.raises(SystemExit) as exc:
        operator_event.main(
            ["abort", "--run-id", "run_f", "--log-dir", str(tmp_path), "--abort-class", "safety"]
        )
    assert exc.value.code == 2
    assert not (tmp_path / "run_f").exists()


def test_validate_event_flags_abort_without_reason():
    bad = {
        "schema_version": 1,
        "event": "abort",
        "ts_utc": "2026-09-09T12:00:00Z",
        "run_id": "x",
        "detail": {"abort_class": "safety"},
    }
    problems = operator_event.validate_event(bad)
    assert any("reason" in p for p in problems)

    bad["detail"] = {"abort_class": "not-a-class", "reason": "x"}
    assert any("abort_class" in p for p in operator_event.validate_event(bad))

    good = {
        "schema_version": 1,
        "event": "abort",
        "ts_utc": "2026-09-09T12:00:00Z",
        "run_id": "x",
        "detail": {"abort_class": "safety", "reason": "wrong-target authority"},
    }
    assert operator_event.validate_event(good) == []


# --------------------------------------------------------------------------- #
# G. trial file separation
# --------------------------------------------------------------------------- #
def test_two_run_ids_never_share_an_event_file(tmp_path):
    operator_event.main(
        ["trial_start", "--run-id", "run_g1", "--log-dir", str(tmp_path),
         "--condition", "baseline", "--scenario", "following"]
    )
    operator_event.main(
        ["trial_start", "--run-id", "run_g2", "--log-dir", str(tmp_path),
         "--condition", "candidate", "--scenario", "loss_reacq"]
    )
    g1 = json.loads((tmp_path / "run_g1" / "operator_events.jsonl").read_text())
    g2 = json.loads((tmp_path / "run_g2" / "operator_events.jsonl").read_text())
    assert g1["run_id"] == "run_g1"
    assert g2["run_id"] == "run_g2"
    assert g1["detail"]["condition"] == "baseline"
    assert g2["detail"]["condition"] == "candidate"


# --------------------------------------------------------------------------- #
# H. operator events archived with the package
# --------------------------------------------------------------------------- #
def test_operator_event_log_is_archived_into_the_retained_package(tmp_path):
    run = _make_run_dir(
        tmp_path,
        "run_h",
        {
            "control.log": "c\n",
            "dashboard_bridge.log": "d\n",
            "target_memory_mars.log": "t\n",
            "operator_events.jsonl": '{"event":"trial_start"}\n',
        },
    )
    bag = tmp_path / "bag"
    bag.mkdir()

    code = archive_run_evidence.main(
        [
            "--run-dir", str(run), "--run-id", "run_h", "--bag-dir", str(bag),
            "--optional-file", "operator_events.jsonl",
        ]
    )
    assert code == 0
    dest = bag / "run_logs"
    assert (dest / "operator_events.jsonl").read_text() == '{"event":"trial_start"}\n'
    manifest = json.loads((dest / "archive_manifest.json").read_text())
    assert manifest["optional_files"]["operator_events.jsonl"]["status"] == "copied"
    assert manifest["run_dir"] == str(run.resolve())


def test_absent_optional_operator_log_is_recorded_not_fabricated(tmp_path):
    run = _make_run_dir(
        tmp_path,
        "run_i",
        {
            "control.log": "c\n",
            "dashboard_bridge.log": "d\n",
            "target_memory_mars.log": "t\n",
        },
    )
    bag = tmp_path / "bag"
    bag.mkdir()

    code = archive_run_evidence.main(
        [
            "--run-dir", str(run), "--run-id", "run_i", "--bag-dir", str(bag),
            "--optional-file", "operator_events.jsonl",
        ]
    )
    assert code == 0  # required logs all present
    dest = bag / "run_logs"
    assert not (dest / "operator_events.jsonl").exists()
    manifest = json.loads((dest / "archive_manifest.json").read_text())
    assert manifest["optional_files"]["operator_events.jsonl"]["status"] == "absent"
