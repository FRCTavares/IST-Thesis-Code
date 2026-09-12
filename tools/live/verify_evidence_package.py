#!/usr/bin/env python3
"""Verify the completeness of a retained #50/#74 trial evidence package.

Issue #50/#74 field hardening. Run after ``stop_stack`` finalizes a retained
trial. Checks the runtime-side artifacts that the Pi produces, distinguishing:

- **required and present** vs **required and missing** -> incomplete runtime
  evidence;
- **optional and present** vs **optional and absent** -> recorded, not a
  failure;
- **pending post-flight** artifacts that must never be fabricated on the Pi:
  the physical-v2 annotation and the native ArduPilot / Pixhawk DataFlash
  ``.bin``.

Writes ``evidence_package_status.json`` beside the bag. ``status`` is one of:

- ``complete_runtime_evidence``
- ``incomplete_runtime_evidence``
- ``pending_postflight_annotation``
- ``pending_pixhawk_dataflash``

A package is never "scientifically final" just because the runtime files
exist; the pending post-flight items are always reported explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_NAME = "evidence_package_status.json"
SCHEMA_VERSION = 1

STATUS_COMPLETE = "complete_runtime_evidence"
STATUS_INCOMPLETE = "incomplete_runtime_evidence"
STATUS_PENDING_ANNOTATION = "pending_postflight_annotation"
STATUS_PENDING_DATAFLASH = "pending_pixhawk_dataflash"


def _json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _validate_provenance(run_metadata: Path, repo_root: Path) -> dict[str, Any]:
    validator = repo_root / "tools/live/validate_live_run_metadata.py"
    if not run_metadata.is_file():
        return {"ran": False, "reason": "run_metadata.json missing"}
    if not validator.is_file():
        return {"ran": False, "reason": "validator not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(validator), str(run_metadata)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ran": False, "reason": str(exc)}
    return {"ran": True, "returncode": result.returncode, "passed": result.returncode == 0}


def _find_annotation(bag_dir: Path) -> str | None:
    for pattern in ("*physical_v2*.json", "*physical_reference*.json", "*_physical_target_bbox_v2*.json"):
        for match in bag_dir.glob(pattern):
            if match.is_file():
                return match.name
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_dataflash_manifest(
    manifest_path: Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "manifest_present": manifest_path.is_file(),
        "valid": False,
        "reasons": [],
        "archived_file": None,
    }
    reasons: list[str] = result["reasons"]

    manifest = _json(manifest_path)
    if manifest is None:
        reasons.append("manifest missing or unreadable")
        return result

    result["schema_version"] = manifest.get("schema_version")
    if manifest.get("schema_version") != 1:
        reasons.append("unexpected manifest schema_version")

    if manifest.get("run_id") != run_id:
        reasons.append("manifest run_id does not match evidence-package run_id")

    if manifest.get("sha256_match") is not True:
        reasons.append("manifest sha256_match is not true")

    archived = manifest.get("archived")
    if not isinstance(archived, dict):
        reasons.append("manifest archived entry missing or invalid")
        return result

    name = archived.get("name")
    if not isinstance(name, str) or not name or Path(name).name != name:
        reasons.append("archived DataFlash name missing or unsafe")
        return result
    if not name.lower().endswith(".bin"):
        reasons.append("archived DataFlash file is not a .bin")

    archived_path = manifest_path.parent / name
    result["archived_file"] = str(archived_path)
    if not archived_path.is_file():
        reasons.append("archived DataFlash .bin is missing")
        return result

    expected_bytes = archived.get("bytes")
    if not isinstance(expected_bytes, int) or expected_bytes <= 0:
        reasons.append("archived DataFlash byte count missing or invalid")
    elif archived_path.stat().st_size != expected_bytes:
        reasons.append("archived DataFlash byte count does not match manifest")

    expected_sha = archived.get("sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        reasons.append("archived DataFlash SHA-256 missing or invalid")
    elif _sha256(archived_path) != expected_sha.lower():
        reasons.append("archived DataFlash SHA-256 does not match manifest")

    result["valid"] = not reasons
    return result


def verify_package(
    *,
    bag_dir: Path,
    run_id: str,
    control_trial: bool,
    field_record: bool,
    expect_operator_events: bool,
    repo_root: Path,
) -> tuple[str, dict[str, Any]]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "bag_dir": str(bag_dir),
        "run_id": run_id,
        "trial_kind": "control_field" if control_trial else "recording",
        "required": {},
        "optional": {},
        "pending_postflight": {},
        "problems": [],
    }
    problems: list[str] = report["problems"]

    def require(name: str, path: Path, note: str = "") -> bool:
        ok = path.is_file()
        report["required"][name] = {"present": ok, "path": str(path)}
        if note:
            report["required"][name]["note"] = note
        if not ok:
            problems.append(f"required artifact missing: {name}")
        return ok

    def optional(name: str, path: Path) -> bool:
        ok = path.is_file()
        report["optional"][name] = {"present": ok, "path": str(path)}
        return ok

    if not bag_dir.is_dir():
        problems.append(f"bag directory not found: {bag_dir}")
        report["status"] = STATUS_INCOMPLETE
        return STATUS_INCOMPLETE, report

    logs = bag_dir / "run_logs"

    require("metadata_yaml", bag_dir / "metadata.yaml")
    require("run_metadata_json", bag_dir / "run_metadata.json")
    require("flight_metadata_txt", bag_dir / "flight_metadata.txt")
    require("target_authority_events_jsonl", bag_dir / "target_authority_events.jsonl")
    require("bag_integrity_json", bag_dir / "bag_integrity.json")
    require("archive_manifest_json", logs / "archive_manifest.json")
    require("control_log", logs / "control.log")
    require("dashboard_bridge_log", logs / "dashboard_bridge.log")
    require("target_memory_mars_log", logs / "target_memory_mars.log")

    mcap = sorted(bag_dir.glob("*.mcap"))
    report["required"]["mcap_storage_file"] = {
        "present": bool(mcap),
        "files": [p.name for p in mcap],
    }
    if not mcap:
        problems.append("required artifact missing: mcap_storage_file")

    op_events = logs / "operator_events.jsonl"
    if expect_operator_events:
        require("operator_events_jsonl", op_events, note="operator recorded events")
    else:
        optional("operator_events_jsonl", op_events)

    # --- bag integrity ---
    integrity = _json(bag_dir / "bag_integrity.json")
    if integrity is None:
        problems.append("bag_integrity.json missing or unreadable")
        report["bag_integrity_passed"] = None
    else:
        report["bag_integrity_passed"] = bool(integrity.get("passed"))
        if not integrity.get("passed"):
            problems.append("bag integrity check did not pass")
        counts = integrity.get("topic_message_counts", {}) or {}
        if control_trial and int(counts.get("/control_ref/diagnostics", 0)) <= 0:
            problems.append(
                "control field trial: /control_ref/diagnostics has no messages"
            )
        report["diagnostics_message_count"] = int(
            counts.get("/control_ref/diagnostics", 0)
        )

    # --- archive manifest completeness ---
    manifest = _json(logs / "archive_manifest.json")
    if manifest is not None:
        report["archive_manifest_complete"] = bool(manifest.get("complete"))
        if not manifest.get("complete"):
            problems.append("run-log archival manifest is incomplete")

    # --- recorder finalization outcome ---
    outcome_path = logs / "recorder_finalize_outcome.txt"
    if outcome_path.is_file():
        outcome = outcome_path.read_text(encoding="utf-8").strip()
        report["recorder_finalize_outcome"] = outcome
        if outcome == "escalated":
            problems.append("recorder finalization required escalation")
    else:
        report["recorder_finalize_outcome"] = "unknown"

    # --- provenance validity ---
    prov = _validate_provenance(bag_dir / "run_metadata.json", repo_root)
    report["provenance_validation"] = prov
    if prov.get("ran") and not prov.get("passed"):
        problems.append("run_metadata.json failed the provenance validator")

    # --- pending post-flight artifacts (never fabricated) ---
    annotation = _find_annotation(bag_dir)
    report["pending_postflight"]["physical_v2_annotation"] = {
        "present": annotation is not None,
        "file": annotation,
    }
    dataflash = bag_dir / "pixhawk_dataflash" / "dataflash_manifest.json"
    df_check = _validate_dataflash_manifest(dataflash, run_id=run_id)
    df_present = bool(df_check["valid"])
    df_check["present"] = df_present
    df_check["manifest"] = str(dataflash) if dataflash.is_file() else None
    df_check["applies"] = control_trial or field_record
    report["pending_postflight"]["pixhawk_dataflash"] = df_check

    runtime_ok = not problems
    report["runtime_status"] = (
        STATUS_COMPLETE if runtime_ok else STATUS_INCOMPLETE
    )

    pending: list[str] = []
    if (control_trial or field_record) and not df_present:
        pending.append(STATUS_PENDING_DATAFLASH)
    if annotation is None:
        pending.append(STATUS_PENDING_ANNOTATION)
    report["pending"] = pending

    if not runtime_ok:
        status = STATUS_INCOMPLETE
    elif STATUS_PENDING_DATAFLASH in pending:
        status = STATUS_PENDING_DATAFLASH
    elif STATUS_PENDING_ANNOTATION in pending:
        status = STATUS_PENDING_ANNOTATION
    else:
        status = STATUS_COMPLETE
    report["status"] = status
    return status, report


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--control-trial", action="store_true")
    parser.add_argument("--field-record", action="store_true")
    parser.add_argument("--expect-operator-events", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    bag_dir = args.bag_dir.resolve()
    repo_root = (
        args.repo_root.resolve()
        if args.repo_root
        else Path(__file__).resolve().parents[2]
    )

    status, report = verify_package(
        bag_dir=bag_dir,
        run_id=args.run_id,
        control_trial=args.control_trial,
        field_record=args.field_record,
        expect_operator_events=args.expect_operator_events,
        repo_root=repo_root,
    )

    out = args.out or (bag_dir / REPORT_NAME)
    try:
        _write_atomic(out, report)
    except OSError as exc:
        print(f"[warn] could not write {out}: {exc}", file=sys.stderr)

    print(f"[evidence] package status: {status}")
    for problem in report.get("problems", []):
        print(f"           - {problem}")
    for item in report.get("pending", []):
        print(f"           - {item}")

    return 0 if status == STATUS_COMPLETE else 1


if __name__ == "__main__":
    sys.exit(main())
