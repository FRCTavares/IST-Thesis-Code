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
  ``.bin``. The explicitly scoped #32 disarmed runtime characterization may
  mark those two artifacts not applicable only when retained MAVROS state
  evidence proves the run remained connected and disarmed.

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
import importlib.util
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

BCB_TRIALS = {
    "bcb_baseline_a": {
        "condition": "baseline",
        "recovery_enabled": False,
    },
    "bcb_candidate": {
        "condition": "candidate",
        "recovery_enabled": True,
    },
    "bcb_baseline_b": {
        "condition": "baseline",
        "recovery_enabled": False,
    },
}

BCB_OPPORTUNITIES = {
    "O1": "right_loss",
    "O2": "left_loss",
    "O3": "distractor_loss",
}
BCB_OBSERVATION_HORIZON_S = 10.0


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

    retrieval_method = manifest.get("retrieval_method")
    result["retrieval_method"] = retrieval_method
    result["retrieval_provenance"] = {
        "required": False,
        "valid": None,
        "files": [],
        "reasons": [],
    }

    if retrieval_method in (None, "explicit_operator_supplied_file"):
        # Backward compatibility for historical/manual manifests. These do not
        # claim catalogue-based association and therefore have no retained
        # catalogue sidecar contract to verify.
        pass
    elif retrieval_method == "mavros_explicit_id_with_catalogue_association":
        provenance_result = {
            "required": True,
            "valid": False,
            "files": [],
            "reasons": [],
        }
        result["retrieval_provenance"] = provenance_result
        provenance_reasons: list[str] = provenance_result["reasons"]

        provenance = manifest.get("retrieval_provenance")
        expected_names = {
            "before.json",
            "after.json",
            "association.json",
            f"{name}.retrieval.json",
        }

        if not isinstance(provenance, list):
            provenance_reasons.append(
                "manifest retrieval_provenance missing or invalid"
            )
        else:
            by_name: dict[str, dict[str, Any]] = {}

            for index, item in enumerate(provenance):
                if not isinstance(item, dict):
                    provenance_reasons.append(
                        f"retrieval provenance entry {index} is not an object"
                    )
                    continue

                provenance_name = item.get("name")
                if (
                    not isinstance(provenance_name, str)
                    or not provenance_name
                    or Path(provenance_name).name != provenance_name
                ):
                    provenance_reasons.append(
                        f"retrieval provenance entry {index} has an unsafe name"
                    )
                    continue

                if provenance_name in by_name:
                    provenance_reasons.append(
                        f"duplicate retrieval provenance entry: {provenance_name}"
                    )
                    continue

                by_name[provenance_name] = item

            actual_names = set(by_name)
            missing_names = sorted(expected_names - actual_names)
            extra_names = sorted(actual_names - expected_names)

            if missing_names:
                provenance_reasons.append(
                    "retrieval provenance manifest is missing expected entries: "
                    + ", ".join(missing_names)
                )
            if extra_names:
                provenance_reasons.append(
                    "retrieval provenance manifest contains unexpected entries: "
                    + ", ".join(extra_names)
                )

            for provenance_name in sorted(expected_names & actual_names):
                item = by_name[provenance_name]
                provenance_path = manifest_path.parent / provenance_name
                file_result: dict[str, Any] = {
                    "name": provenance_name,
                    "path": str(provenance_path),
                    "present": provenance_path.is_file(),
                    "valid": False,
                }
                provenance_result["files"].append(file_result)

                file_reasons: list[str] = []

                if not provenance_path.is_file():
                    file_reasons.append(
                        f"retrieval provenance file is missing: {provenance_name}"
                    )
                else:
                    provenance_bytes = item.get("bytes")
                    if (
                        not isinstance(provenance_bytes, int)
                        or provenance_bytes <= 0
                    ):
                        file_reasons.append(
                            "retrieval provenance byte count missing or invalid: "
                            f"{provenance_name}"
                        )
                    elif provenance_path.stat().st_size != provenance_bytes:
                        file_reasons.append(
                            "retrieval provenance byte count does not match "
                            f"manifest: {provenance_name}"
                        )

                    provenance_sha = item.get("sha256")
                    if (
                        not isinstance(provenance_sha, str)
                        or len(provenance_sha) != 64
                    ):
                        file_reasons.append(
                            "retrieval provenance SHA-256 missing or invalid: "
                            f"{provenance_name}"
                        )
                    elif _sha256(provenance_path) != provenance_sha.lower():
                        file_reasons.append(
                            "retrieval provenance SHA-256 does not match "
                            f"manifest: {provenance_name}"
                        )

                file_result["valid"] = not file_reasons
                file_result["reasons"] = file_reasons
                provenance_reasons.extend(file_reasons)

        provenance_result["valid"] = not provenance_reasons
        reasons.extend(provenance_reasons)
    else:
        reasons.append(
            f"unsupported DataFlash retrieval_method: {retrieval_method!r}"
        )

    result["valid"] = not reasons
    return result


def _utc_iso_to_ns(value: Any) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    parsed = parsed.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed - epoch

    return (
        (delta.days * 86400 + delta.seconds) * 1_000_000_000
        + delta.microseconds * 1000
    )


def _read_trial_window(
    operator_events_path: Path,
    *,
    run_id: str,
    trial_id: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "valid": False,
        "path": str(operator_events_path),
        "run_id": run_id,
        "trial_id": trial_id,
        "start_utc": None,
        "end_utc": None,
        "start_ns": None,
        "end_ns": None,
        "reasons": [],
    }
    reasons: list[str] = result["reasons"]

    if not operator_events_path.is_file():
        reasons.append("archived operator_events.jsonl is missing")
        return result

    starts: list[dict[str, Any]] = []
    ends: list[dict[str, Any]] = []

    try:
        lines = operator_events_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        reasons.append(f"could not read archived operator events: {exc}")
        return result

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            reasons.append(
                f"operator_events.jsonl line {line_number} is not valid JSON"
            )
            continue

        if not isinstance(record, dict):
            reasons.append(
                f"operator_events.jsonl line {line_number} is not an object"
            )
            continue

        if record.get("run_id") != run_id or record.get("trial_id") != trial_id:
            continue

        event = record.get("event")
        if event == "trial_start":
            starts.append(record)
        elif event == "trial_end":
            ends.append(record)

    if len(starts) != 1:
        reasons.append(
            f"expected exactly one matching trial_start, found {len(starts)}"
        )
    if len(ends) != 1:
        reasons.append(
            f"expected exactly one matching trial_end, found {len(ends)}"
        )

    if reasons:
        return result

    start_utc = starts[0].get("ts_utc")
    end_utc = ends[0].get("ts_utc")
    start_ns = _utc_iso_to_ns(start_utc)
    end_ns = _utc_iso_to_ns(end_utc)

    result["start_utc"] = start_utc
    result["end_utc"] = end_utc
    result["start_ns"] = start_ns
    result["end_ns"] = end_ns

    if start_ns is None:
        reasons.append("trial_start ts_utc is missing or invalid")
    if end_ns is None:
        reasons.append("trial_end ts_utc is missing or invalid")

    if reasons:
        return result

    if end_ns <= start_ns:
        reasons.append("trial_end must occur after trial_start")
        return result

    result["valid"] = True
    return result


def _assess_disarmed_state_samples(
    samples: list[tuple[int, bool, bool]],
    *,
    trial_start_ns: int,
    trial_end_ns: int,
) -> dict[str, Any]:
    in_trial = [
        (timestamp_ns, connected, armed)
        for timestamp_ns, connected, armed in samples
        if trial_start_ns <= timestamp_ns <= trial_end_ns
    ]
    outside = [
        (timestamp_ns, connected, armed)
        for timestamp_ns, connected, armed in samples
        if timestamp_ns < trial_start_ns or timestamp_ns > trial_end_ns
    ]

    disconnected = sum(
        1 for _, connected, _ in in_trial if not connected
    )
    armed = sum(
        1 for _, _, armed_state in in_trial if armed_state
    )

    outside_disconnected = sum(
        1 for _, connected, _ in outside if not connected
    )
    outside_armed = sum(
        1 for _, _, armed_state in outside if armed_state
    )

    reasons: list[str] = []
    if not in_trial:
        reasons.append(
            "retained /mavros/state has zero samples inside the trial interval"
        )
    if disconnected:
        reasons.append(
            f"/mavros/state contains {disconnected} disconnected samples "
            "inside the trial interval"
        )
    if armed:
        reasons.append(
            f"/mavros/state contains {armed} armed samples "
            "inside the trial interval"
        )

    return {
        "valid": not reasons,
        "total_sample_count": len(samples),
        "in_trial_sample_count": len(in_trial),
        "in_trial_connected_false_count": disconnected,
        "in_trial_armed_true_count": armed,
        "outside_trial_sample_count": len(outside),
        "outside_trial_connected_false_count": outside_disconnected,
        "outside_trial_armed_true_count": outside_armed,
        "reasons": reasons,
    }


def _validate_disarmed_runtime_characterization(
    bag_dir: Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Prove the narrow #32 disarmed-runtime scope from retained evidence."""
    result: dict[str, Any] = {
        "valid": False,
        "scenario_tag": None,
        "state_topic": "/mavros/state",
        "trial_window": None,
        "state_assessment": None,
        "reasons": [],
    }
    reasons: list[str] = result["reasons"]

    metadata_path = bag_dir / "run_metadata.json"
    metadata = _json(metadata_path)
    if metadata is None:
        reasons.append("run_metadata.json missing or unreadable")
        return result

    if metadata.get("run_id") != run_id:
        reasons.append(
            "run_metadata run_id does not match evidence-package run_id"
        )

    scenario_tag = metadata.get("scenario_tag")
    result["scenario_tag"] = scenario_tag
    if scenario_tag != "p032_final_mounted_vga":
        reasons.append(
            "disarmed runtime characterization is restricted to "
            "scenario_tag=p032_final_mounted_vga"
        )

    bag_metadata = metadata.get("bag")
    recorded_topics = (
        bag_metadata.get("recorded_topics", [])
        if isinstance(bag_metadata, dict)
        else []
    )
    if "/mavros/state" not in recorded_topics:
        reasons.append(
            "run metadata does not declare retained /mavros/state"
        )

    if reasons:
        return result

    trial_window = _read_trial_window(
        bag_dir / "run_logs" / "operator_events.jsonl",
        run_id=run_id,
        trial_id="p032_final_mounted_vga",
    )
    result["trial_window"] = trial_window

    if not trial_window["valid"]:
        reasons.extend(
            f"trial window: {reason}"
            for reason in trial_window["reasons"]
        )
        return result

    try:
        from rclpy.serialization import deserialize_message
        from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
        from rosidl_runtime_py.utilities import get_message
    except Exception as exc:
        reasons.append(f"ROS bag dependencies unavailable: {exc}")
        return result

    try:
        reader = SequentialReader()
        reader.open(
            StorageOptions(uri=str(bag_dir), storage_id="mcap"),
            ConverterOptions("cdr", "cdr"),
        )
        topic_types = {
            topic.name: topic.type
            for topic in reader.get_all_topics_and_types()
        }
    except Exception as exc:
        reasons.append(f"could not open retained MCAP: {exc}")
        return result

    state_type = topic_types.get("/mavros/state")
    if not state_type:
        reasons.append("retained MCAP is missing /mavros/state")
        return result

    try:
        state_cls = get_message(state_type)
    except Exception as exc:
        reasons.append(f"could not resolve MAVROS State type: {exc}")
        return result

    samples: list[tuple[int, bool, bool]] = []

    try:
        while reader.has_next():
            topic, raw, bag_ns = reader.read_next()
            if topic != "/mavros/state":
                continue

            msg = deserialize_message(raw, state_cls)
            samples.append(
                (
                    int(bag_ns),
                    bool(msg.connected),
                    bool(msg.armed),
                )
            )
    except Exception as exc:
        reasons.append(
            f"could not inspect retained /mavros/state: {exc}"
        )
        return result

    assessment = _assess_disarmed_state_samples(
        samples,
        trial_start_ns=int(trial_window["start_ns"]),
        trial_end_ns=int(trial_window["end_ns"]),
    )
    result["state_assessment"] = assessment

    if not assessment["valid"]:
        reasons.extend(assessment["reasons"])

    result["valid"] = not reasons
    return result


def _load_operator_event_contract(repo_root: Path):
    path = repo_root / "tools/live/operator_event.py"
    spec = importlib.util.spec_from_file_location(
        "_operator_event_contract",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load operator-event contract: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_bcb_operator_events(
    path: Path,
    *,
    run_id: str,
    trial_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    """Validate the frozen final three-flight B-C-B operator-event contract.

    This is intentionally stricter than --expect-operator-events. Historical
    evidence keeps the old existence-only contract; only explicitly identified
    final B-C-B trials use this structural/lifecycle validation.
    """
    result: dict[str, Any] = {
        "path": str(path),
        "run_id": run_id,
        "trial_id": trial_id,
        "valid": False,
        "record_count": 0,
        "problems": [],
        "event_counts": {},
        "opportunity_outcomes": {},
    }
    problems: list[str] = result["problems"]

    expected_trial = BCB_TRIALS.get(trial_id)
    if expected_trial is None:
        problems.append(f"unsupported B-C-B trial id: {trial_id!r}")
        return result

    if not path.is_file():
        problems.append("operator_events.jsonl missing")
        return result

    try:
        operator_event = _load_operator_event_contract(repo_root)
    except Exception as exc:
        problems.append(f"could not load operator-event validator: {exc}")
        return result

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        problems.append(f"could not read operator_events.jsonl: {exc}")
        return result

    if not lines:
        problems.append("operator_events.jsonl is empty")
        return result

    records: list[dict[str, Any]] = []
    record_indices: list[int] = []

    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            problems.append(f"line {line_number}: blank JSONL record")
            continue

        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(
                f"line {line_number}: invalid JSON: {exc.msg}"
            )
            continue

        if not isinstance(record, dict):
            problems.append(f"line {line_number}: record is not a JSON object")
            continue

        records.append(record)
        record_indices.append(line_number - 1)

        for error in operator_event.validate_event(record):
            problems.append(f"line {line_number}: {error}")

        if record.get("run_id") != run_id:
            problems.append(
                f"line {line_number}: run_id {record.get('run_id')!r} "
                f"does not match {run_id!r}"
            )

        if record.get("trial_id") != trial_id:
            problems.append(
                f"line {line_number}: trial_id {record.get('trial_id')!r} "
                f"does not match {trial_id!r}"
            )

    result["record_count"] = len(records)

    by_event: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, record in zip(record_indices, records):
        event = record.get("event")
        if isinstance(event, str):
            by_event.setdefault(event, []).append((index, record))

    result["event_counts"] = {
        event: len(items)
        for event, items in sorted(by_event.items())
    }

    target_selected = by_event.get("target_selected", [])
    trial_starts = by_event.get("trial_start", [])
    trial_ends = by_event.get("trial_end", [])
    trial_verdicts = by_event.get("trial_verdict", [])
    aborts = by_event.get("abort", [])
    takeovers = by_event.get("operator_takeover", [])

    for event_name, items in (
        ("trial_start", trial_starts),
        ("trial_end", trial_ends),
        ("trial_verdict", trial_verdicts),
    ):
        if len(items) != 1:
            problems.append(
                f"expected exactly one {event_name}, found {len(items)}"
            )

    trial_start_index = trial_starts[0][0] if len(trial_starts) == 1 else None
    trial_end_index = trial_ends[0][0] if len(trial_ends) == 1 else None
    verdict_index = (
        trial_verdicts[0][0]
        if len(trial_verdicts) == 1
        else None
    )

    if len(trial_starts) == 1:
        detail = trial_starts[0][1].get("detail", {})
        if detail.get("condition") != expected_trial["condition"]:
            problems.append(
                "trial_start condition does not match B-C-B tag "
                f"({detail.get('condition')!r} != "
                f"{expected_trial['condition']!r})"
            )
        if (
            detail.get("recovery_enabled")
            is not expected_trial["recovery_enabled"]
        ):
            problems.append(
                "trial_start recovery_enabled does not match B-C-B tag "
                f"({detail.get('recovery_enabled')!r} != "
                f"{expected_trial['recovery_enabled']!r})"
            )
        if detail.get("scenario") != "bcb_three_opportunity":
            problems.append(
                "trial_start scenario must be 'bcb_three_opportunity'"
            )

    verdict = None
    if len(trial_verdicts) == 1:
        verdict = trial_verdicts[0][1].get("detail", {}).get("verdict")

    result["trial_disposition"] = verdict

    expected_boundaries = [
        ("O1", "start"),
        ("O1", "end"),
        ("O2", "start"),
        ("O2", "end"),
        ("O3", "start"),
        ("O3", "end"),
    ]

    boundary_records: list[tuple[int, str, str, dict[str, Any]]] = []

    for opportunity_id, expected_scenario in BCB_OPPORTUNITIES.items():
        starts = [
            (index, record)
            for index, record in by_event.get("opportunity_start", [])
            if record.get("detail", {}).get("opportunity_id")
            == opportunity_id
        ]
        ends = [
            (index, record)
            for index, record in by_event.get("opportunity_end", [])
            if record.get("detail", {}).get("opportunity_id")
            == opportunity_id
        ]

        if len(starts) > 1:
            problems.append(
                f"expected at most one {opportunity_id} "
                f"opportunity_start, found {len(starts)}"
            )
        if len(ends) > 1:
            problems.append(
                f"expected at most one {opportunity_id} "
                f"opportunity_end, found {len(ends)}"
            )

        if len(starts) == 1:
            index, record = starts[0]
            detail = record.get("detail", {})
            if detail.get("scenario") != expected_scenario:
                problems.append(
                    f"{opportunity_id} scenario must be "
                    f"{expected_scenario!r}"
                )
            if (
                detail.get("observation_horizon_s")
                != BCB_OBSERVATION_HORIZON_S
            ):
                problems.append(
                    f"{opportunity_id} observation horizon must be "
                    f"{BCB_OBSERVATION_HORIZON_S:.1f} s"
                )
            boundary_records.append(
                (index, opportunity_id, "start", record)
            )

        if len(ends) == 1:
            index, record = ends[0]
            result["opportunity_outcomes"][opportunity_id] = (
                record.get("detail", {}).get("outcome")
            )
            boundary_records.append(
                (index, opportunity_id, "end", record)
            )

    boundary_records.sort(key=lambda item: item[0])
    actual_boundaries = [
        (opportunity_id, kind)
        for _, opportunity_id, kind, _ in boundary_records
    ]

    result["opportunity_boundary_sequence"] = [
        f"{opportunity_id}_{kind}"
        for opportunity_id, kind in actual_boundaries
    ]
    result["full_opportunity_sequence_recorded"] = (
        actual_boundaries == expected_boundaries
    )

    if verdict == "accepted":
        result["contract_path"] = "nominal_complete"

        if actual_boundaries != expected_boundaries:
            for opportunity_id in BCB_OPPORTUNITIES:
                start_count = sum(
                    1
                    for _, op_id, kind, _ in boundary_records
                    if op_id == opportunity_id and kind == "start"
                )
                end_count = sum(
                    1
                    for _, op_id, kind, _ in boundary_records
                    if op_id == opportunity_id and kind == "end"
                )
                if start_count != 1:
                    problems.append(
                        f"accepted B-C-B trial requires exactly one "
                        f"{opportunity_id} opportunity_start, found "
                        f"{start_count}"
                    )
                if end_count != 1:
                    problems.append(
                        f"accepted B-C-B trial requires exactly one "
                        f"{opportunity_id} opportunity_end, found "
                        f"{end_count}"
                    )

            if actual_boundaries != expected_boundaries:
                problems.append(
                    "accepted B-C-B opportunity boundaries must be exactly "
                    "O1 start/end -> O2 start/end -> O3 start/end"
                )

        if len(aborts) != 0:
            problems.append(
                "accepted B-C-B trial must not contain an abort event"
            )

        if takeovers:
            problems.append(
                "accepted B-C-B trial must not contain operator_takeover"
            )

        if not target_selected:
            problems.append(
                "accepted B-C-B trial requires target_selected before O1"
            )

        if (
            trial_start_index is not None
            and boundary_records
            and target_selected
            and not any(
                trial_start_index < index < boundary_records[0][0]
                for index, _ in target_selected
            )
        ):
            problems.append(
                "target_selected must occur after trial_start and before O1"
            )

        if len(trial_ends) == 1:
            end_reason = (
                trial_ends[0][1]
                .get("detail", {})
                .get("end_reason")
            )
            if end_reason != "nominal_complete":
                problems.append(
                    "accepted B-C-B trial_end must use "
                    "end_reason='nominal_complete'"
                )

    elif verdict == "rejected":
        result["contract_path"] = "aborted_prefix"

        if len(aborts) != 1:
            problems.append(
                f"rejected B-C-B trial requires exactly one abort event, "
                f"found {len(aborts)}"
            )

        if len(trial_ends) == 1:
            end_reason = (
                trial_ends[0][1]
                .get("detail", {})
                .get("end_reason")
            )
            if end_reason != "pilot_abort":
                problems.append(
                    "rejected B-C-B trial_end must use "
                    "end_reason='pilot_abort'"
                )

        # A rejected flight may terminate at any point in the frozen sequence.
        # The observed boundaries must therefore be an exact prefix. This
        # permits an opportunity_start with no matching end if the safety abort
        # happened during that opportunity, without fabricating an end marker.
        if (
            len(actual_boundaries) > len(expected_boundaries)
            or actual_boundaries
            != expected_boundaries[:len(actual_boundaries)]
        ):
            problems.append(
                "rejected B-C-B opportunity boundaries must form a "
                "coherent prefix of O1 start/end -> O2 start/end -> "
                "O3 start/end"
            )

        if len(aborts) == 1:
            abort_index = aborts[0][0]

            if (
                trial_start_index is not None
                and abort_index <= trial_start_index
            ):
                problems.append(
                    "abort must occur after trial_start"
                )

            if (
                trial_end_index is not None
                and abort_index >= trial_end_index
            ):
                problems.append(
                    "abort must occur before trial_end"
                )

            if any(
                index > abort_index
                for index, _, _, _ in boundary_records
            ):
                problems.append(
                    "opportunity events must not occur after abort"
                )

            if any(
                index > abort_index
                for index, _ in target_selected
            ):
                problems.append(
                    "target_selected must not occur after abort"
                )

            if boundary_records:
                first_boundary_index = boundary_records[0][0]
                if not any(
                    trial_start_index is not None
                    and trial_start_index < index < first_boundary_index
                    for index, _ in target_selected
                ):
                    problems.append(
                        "an attempted B-C-B opportunity requires "
                        "target_selected before the first opportunity"
                    )

    elif verdict is not None:
        problems.append(
            f"unexpected B-C-B trial verdict: {verdict!r}"
        )

    # Shared lifecycle ordering. A rejected run is valid retained evidence even
    # when it is not a complete comparison flight.
    if (
        trial_start_index is not None
        and trial_end_index is not None
        and verdict_index is not None
    ):
        if not (
            trial_start_index < trial_end_index < verdict_index
        ):
            problems.append(
                "B-C-B lifecycle requires trial_start before trial_end "
                "before trial_verdict"
            )

        if any(
            index <= trial_start_index or index >= trial_end_index
            for index, _, _, _ in boundary_records
        ):
            problems.append(
                "opportunity boundaries must occur inside the trial"
            )

    result["valid"] = not problems
    return result


def verify_package(
    *,
    bag_dir: Path,
    run_id: str,
    control_trial: bool,
    field_record: bool,
    expect_operator_events: bool,
    repo_root: Path,
    expect_bcb_opportunities: str | None = None,
    expect_raw_bag: bool = False,
    expect_visual: bool = False,
    disarmed_runtime_characterization: bool = False,
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
    require("rosbag_log", logs / "rosbag.log")
    require("recorder_transport_status_json", bag_dir / "recorder_transport_status.json")
    if expect_visual:
        visual_file = bag_dir / f"visual_{run_id}.mkv"
        require("visual_file", visual_file)
        require("visual_evidence_status_json", bag_dir / "visual_evidence_status.json")
        require("visual_recorder_log", logs / "visual_record.log")
        visual_report = _json(bag_dir / "visual_evidence_status.json")
        report["visual_evidence"] = visual_report
        if (not isinstance(visual_report, dict) or
            visual_report.get("passed") is not True or
            visual_report.get("recorder_alive_at_stop") is not True or
            visual_report.get("finalization") != "graceful"):
            problems.append("separate visual evidence missing, stopped early, or failed verification")
        elif (visual_report.get("run_id") != run_id or
              visual_report.get("visual_file") != str(visual_file)):
            problems.append("separate visual evidence run/path mismatch")
        provenance = _json(bag_dir / "run_metadata.json")
        visual_metadata = provenance.get("visual") if isinstance(provenance, dict) else None
        if (not isinstance(visual_metadata, dict) or
            visual_metadata.get("file") != str(visual_file) or
            not visual_metadata.get("started_at_utc")):
            problems.append("run metadata has no matching visual file/start timestamp")

    manifest = _json(logs / "archive_manifest.json")
    manifest_required_logs: dict[str, Any] = {}
    if isinstance(manifest, dict):
        candidate_required = manifest.get("required_logs", {})
        if isinstance(candidate_required, dict):
            manifest_required_logs = candidate_required

    control_log = logs / "control.log"
    if control_trial or "control.log" in manifest_required_logs:
        require(
            "control_log",
            control_log,
            note="required whenever the controller ran",
        )
    else:
        optional("control_log", control_log)

    require("dashboard_bridge_log", logs / "dashboard_bridge.log")
    provenance = _json(bag_dir / "run_metadata.json")
    recorded_topics = (provenance or {}).get("bag", {}).get("recorded_topics", [])
    if "/target_memory_mars" in recorded_topics:
        require("target_memory_mars_log", logs / "target_memory_mars.log")
    else:
        optional("target_memory_mars_log", logs / "target_memory_mars.log")

    raw_bag = bag_dir.parent / f"{bag_dir.name}__image_raw"
    if expect_raw_bag:
        report["required"]["raw_image_bag"] = {
            "present": raw_bag.is_dir(), "path": str(raw_bag)
        }
        if not raw_bag.is_dir():
            problems.append("required raw-image bag missing")
        raw_logs = raw_bag / "run_logs"
        require("raw_image_bag_log", raw_logs / "raw_image_bag.log")
        require("raw_archive_manifest_json", raw_logs / "archive_manifest.json")
        raw_manifest = _json(raw_logs / "archive_manifest.json")
        if raw_manifest is None or raw_manifest.get("complete") is not True:
            problems.append("raw recorder log archival manifest missing or incomplete")
        require("raw_bag_integrity_json", raw_bag / "bag_integrity.json")
        raw_integrity = _json(raw_bag / "bag_integrity.json")
        report["raw_bag_integrity_passed"] = (
            raw_integrity.get("passed") if isinstance(raw_integrity, dict) else None
        )
        if report["raw_bag_integrity_passed"] is not True:
            problems.append("raw bag integrity check missing or did not pass")

    mcap = sorted(bag_dir.glob("*.mcap"))
    report["required"]["mcap_storage_file"] = {
        "present": bool(mcap),
        "files": [p.name for p in mcap],
    }
    if not mcap:
        problems.append("required artifact missing: mcap_storage_file")

    op_events = logs / "operator_events.jsonl"
    if expect_bcb_opportunities is not None:
        expect_operator_events = True

    if expect_operator_events:
        require("operator_events_jsonl", op_events, note="operator recorded events")
    else:
        optional("operator_events_jsonl", op_events)

    if expect_bcb_opportunities is not None:
        bcb_validation = _validate_bcb_operator_events(
            op_events,
            run_id=run_id,
            trial_id=expect_bcb_opportunities,
            repo_root=repo_root,
        )
        report["operator_event_validation"] = bcb_validation
        report["required"]["bcb_operator_event_contract"] = {
            "present": op_events.is_file(),
            "valid": bcb_validation["valid"],
            "trial_id": expect_bcb_opportunities,
        }
        if not bcb_validation["valid"]:
            problems.extend(
                f"B-C-B operator-event contract: {reason}"
                for reason in bcb_validation["problems"]
            )

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
        if expect_visual and any(topic in counts for topic in ("/camera/dashboard", "/camera/image_raw")):
            problems.append("structured flight bag contains an image topic")
        if control_trial and int(counts.get("/control_ref/diagnostics", 0)) <= 0:
            problems.append(
                "control field trial: /control_ref/diagnostics has no messages"
            )
        report["diagnostics_message_count"] = int(
            counts.get("/control_ref/diagnostics", 0)
        )

    # --- transport quality is independent of structural MCAP integrity ---
    transport = _json(bag_dir / "recorder_transport_status.json")
    report["recorder_transport"] = transport
    expected_logs = {"main": logs / "rosbag.log"}
    if expect_raw_bag:
        expected_logs["raw_image"] = raw_bag / "run_logs" / "raw_image_bag.log"
    if not isinstance(transport, dict):
        problems.append("recorder transport report missing or unreadable")
    else:
        recorders = transport.get("recorders")
        if not isinstance(recorders, dict):
            problems.append("recorder transport report has no recorder observations")
        else:
            for name, path in expected_logs.items():
                observation = recorders.get(name)
                if not isinstance(observation, dict):
                    problems.append(f"{name} recorder transport observation missing")
                    continue
                if observation.get("source_log") != str(path):
                    problems.append(f"{name} recorder transport source log mismatch")
                status = observation.get("status")
                count = observation.get("reported_transport_loss_count")
                if (
                    status == "observed_zero"
                    and observation.get("parse_ok") is True
                    and count == 0
                    and not isinstance(count, bool)
                ):
                    continue
                if (
                    status == "observed_nonzero"
                    and observation.get("parse_ok") is True
                    and isinstance(count, int)
                    and not isinstance(count, bool)
                    and count > 0
                ):
                    problems.append(f"{name} recorder reported {count} transport losses")
                else:
                    problems.append(f"{name} recorder transport observation unavailable or invalid")
            if not expect_raw_bag and "raw_image" in recorders:
                problems.append("unexpected raw-image recorder observation")
        report["recorder_transport_quality_status"] = transport.get("quality_status")

    # --- archive manifest completeness ---
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

    # --- explicit #32 disarmed-runtime scope ---
    disarmed_scope_valid = False
    if disarmed_runtime_characterization:
        if not control_trial or not field_record:
            problems.append(
                "--disarmed-runtime-characterization requires both "
                "--control-trial and --field-record"
            )
        if expect_bcb_opportunities is not None:
            problems.append(
                "--disarmed-runtime-characterization is incompatible with "
                "final B-C-B opportunity verification"
            )

        disarmed_check = _validate_disarmed_runtime_characterization(
            bag_dir,
            run_id=run_id,
        )
        report["disarmed_runtime_characterization"] = disarmed_check
        disarmed_scope_valid = bool(disarmed_check["valid"])

        if not disarmed_scope_valid:
            detail = "; ".join(disarmed_check.get("reasons", []))
            problems.append(
                "disarmed runtime characterization scope was not proven"
                + (f": {detail}" if detail else "")
            )
    else:
        report["disarmed_runtime_characterization"] = {
            "valid": None,
            "requested": False,
        }

    # --- pending post-flight artifacts (never fabricated) ---
    annotation = _find_annotation(bag_dir)
    annotation_check = {
        "present": annotation is not None,
        "file": annotation,
        "applies": not disarmed_scope_valid,
    }
    if disarmed_scope_valid:
        annotation_check["not_applicable_reason"] = (
            "final #32 disarmed runtime/resource characterization does not "
            "require physical-target correctness annotation"
        )
    report["pending_postflight"]["physical_v2_annotation"] = annotation_check

    dataflash = bag_dir / "pixhawk_dataflash" / "dataflash_manifest.json"
    df_check = _validate_dataflash_manifest(dataflash, run_id=run_id)
    df_present = bool(df_check["valid"])
    df_check["present"] = df_present
    df_check["manifest"] = str(dataflash) if dataflash.is_file() else None
    df_check["applies"] = (control_trial or field_record) and not disarmed_scope_valid
    if disarmed_scope_valid:
        df_check["not_applicable_reason"] = (
            "final #32 characterization remained connected and disarmed; "
            "native DataFlash is not required for the runtime/resource claim"
        )
    report["pending_postflight"]["pixhawk_dataflash"] = df_check

    runtime_ok = not problems
    report["runtime_status"] = (
        STATUS_COMPLETE if runtime_ok else STATUS_INCOMPLETE
    )

    pending: list[str] = []
    if (
        (control_trial or field_record)
        and not disarmed_scope_valid
        and not df_present
    ):
        pending.append(STATUS_PENDING_DATAFLASH)
    if annotation is None and not disarmed_scope_valid:
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
    parser.add_argument("--expect-raw-bag", action="store_true")
    parser.add_argument("--expect-visual", action="store_true")
    parser.add_argument(
        "--disarmed-runtime-characterization",
        action="store_true",
        help=(
            "Narrow #32 scope: physical annotation and DataFlash are not "
            "applicable only when retained p032_final_mounted_vga "
            "/mavros/state proves every sample inside the retained trial "
            "interval connected and disarmed."
        ),
    )
    parser.add_argument("--runtime-only", action="store_true",
                        help="accept a complete runtime package while postflight work remains pending")
    parser.add_argument("--expect-operator-events", action="store_true")
    parser.add_argument(
        "--expect-bcb-opportunities",
        choices=tuple(BCB_TRIALS),
        metavar="TAG",
        default=None,
        help=(
            "Require the strict final B-C-B O1/O2/O3 operator-event "
            "contract for the supplied trial tag."
        ),
    )
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
        expect_bcb_opportunities=args.expect_bcb_opportunities,
        expect_raw_bag=args.expect_raw_bag,
        expect_visual=args.expect_visual,
        disarmed_runtime_characterization=args.disarmed_runtime_characterization,
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

    return 0 if (status == STATUS_COMPLETE or
                 args.runtime_only and report.get("runtime_status") == STATUS_COMPLETE) else 1


if __name__ == "__main__":
    sys.exit(main())
