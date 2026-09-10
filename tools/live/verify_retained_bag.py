#!/usr/bin/env python3
"""Deterministic integrity check of a finalized retained rosbag2 bag.

Issue #50/#74 field hardening. After a retained video / field bag's recorder
exits, this verifies -- from the finalized ``metadata.yaml`` alone, so it
needs no ROS and never re-opens the bag while the recorder holds it -- that:

- the bag directory and ``metadata.yaml`` exist and parse;
- at least one storage file exists and is non-empty;
- the storage identifier matches what was requested (default ``mcap``);
- every required topic is present;
- topics that are scientifically required to carry data have a non-zero
  message count.

It writes a machine-readable ``bag_integrity.json`` beside the bag and exits
non-zero on failure. It never deletes or modifies the bag.

A best-effort ``ros2 bag info`` is run as an independent cross-check when the
CLI is available; its result is recorded but a failure there alone does not
fail verification (the finalized metadata is authoritative).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_NAME = "bag_integrity.json"
SCHEMA_VERSION = 1


def _load_metadata(bag_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    meta_path = bag_dir / "metadata.yaml"
    if not meta_path.is_file():
        return None, f"metadata.yaml missing in {bag_dir}"
    try:
        import yaml

        raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any parse failure is a hard fail
        return None, f"metadata.yaml not parseable: {exc}"
    if not isinstance(raw, dict):
        return None, "metadata.yaml is not a mapping"
    info = raw.get("rosbag2_bagfile_information", raw)
    if not isinstance(info, dict):
        return None, "metadata.yaml has no rosbag2_bagfile_information block"
    return info, None


def _topic_counts(info: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in info.get("topics_with_message_count", []) or []:
        meta = entry.get("topic_metadata", {}) if isinstance(entry, dict) else {}
        name = meta.get("name")
        if not name:
            continue
        try:
            counts[str(name)] = int(entry.get("message_count", 0))
        except (TypeError, ValueError):
            counts[str(name)] = 0
    return counts


def _storage_files(bag_dir: Path, info: dict[str, Any]) -> list[dict[str, Any]]:
    names = list(info.get("relative_file_paths", []) or [])
    if not names:
        names = sorted(
            p.name
            for p in bag_dir.iterdir()
            if p.suffix in {".mcap", ".db3"} and p.is_file()
        )
    files: list[dict[str, Any]] = []
    for name in names:
        path = bag_dir / name
        files.append(
            {
                "name": str(name),
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return files


def _ros2_bag_info(bag_dir: Path) -> dict[str, Any]:
    if shutil.which("ros2") is None:
        return {"ran": False, "reason": "ros2 not on PATH"}
    try:
        result = subprocess.run(
            ["ros2", "bag", "info", str(bag_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ran": False, "reason": str(exc)}
    return {
        "ran": True,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
    }


def verify_bag(
    *,
    bag_dir: Path,
    required_topics: list[str],
    require_nonzero: list[str],
    expected_storage: str,
    run_ros2_bag_info: bool = True,
) -> tuple[bool, dict[str, Any]]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "bag_dir": str(bag_dir),
        "method": "finalized_metadata.yaml",
        "expected_storage": expected_storage,
        "required_topics": sorted(required_topics),
        "required_nonzero_topics": sorted(require_nonzero),
        "checks": {},
        "errors": [],
    }
    errors: list[str] = report["errors"]

    if not bag_dir.is_dir():
        errors.append(f"bag directory not found: {bag_dir}")
        report["passed"] = False
        return False, report
    report["checks"]["bag_dir_exists"] = True

    info, meta_err = _load_metadata(bag_dir)
    if info is None:
        errors.append(meta_err or "metadata.yaml unreadable")
        report["checks"]["metadata_parseable"] = False
        report["passed"] = False
        return False, report
    report["checks"]["metadata_parseable"] = True

    storage_identifier = str(info.get("storage_identifier", "")).strip()
    report["storage_identifier"] = storage_identifier
    if expected_storage and storage_identifier != expected_storage:
        errors.append(
            f"storage identifier {storage_identifier!r} != "
            f"expected {expected_storage!r}"
        )
    report["checks"]["storage_identifier_ok"] = (
        not expected_storage or storage_identifier == expected_storage
    )

    files = _storage_files(bag_dir, info)
    report["storage_files"] = files
    total_bytes = sum(f["bytes"] for f in files)
    report["total_bytes"] = total_bytes
    non_empty = [f for f in files if f["exists"] and f["bytes"] > 0]
    if not files:
        errors.append("no storage files listed or found")
    if not non_empty:
        errors.append("no non-empty storage file present")
    report["checks"]["storage_file_nonempty"] = bool(non_empty)

    counts = _topic_counts(info)
    report["topic_message_counts"] = dict(sorted(counts.items()))
    try:
        report["message_count_total"] = int(info.get("message_count", 0))
    except (TypeError, ValueError):
        report["message_count_total"] = sum(counts.values())
    duration = info.get("duration", {})
    if isinstance(duration, dict):
        report["duration_ns"] = duration.get("nanoseconds")

    missing = [t for t in required_topics if t not in counts]
    report["missing_topics"] = sorted(missing)
    if missing:
        errors.append(f"required topics absent from bag: {sorted(missing)}")
    report["checks"]["required_topics_present"] = not missing

    empty = sorted(t for t, c in counts.items() if c == 0)
    report["empty_topics"] = empty
    failed_nonzero = [
        t for t in require_nonzero if counts.get(t, 0) <= 0
    ]
    report["failed_nonzero_topics"] = sorted(failed_nonzero)
    if failed_nonzero:
        errors.append(
            f"topics required to carry data are empty: {sorted(failed_nonzero)}"
        )
    report["checks"]["required_nonzero_ok"] = not failed_nonzero

    if run_ros2_bag_info:
        report["ros2_bag_info"] = _ros2_bag_info(bag_dir)

    passed = not errors
    report["passed"] = passed
    return passed, report


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
    parser.add_argument(
        "--require-topic", action="append", default=[], dest="required_topics"
    )
    parser.add_argument(
        "--require-nonzero", action="append", default=[], dest="require_nonzero"
    )
    parser.add_argument("--expect-storage", default="mcap")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--no-ros2-bag-info",
        action="store_true",
        help="Skip the best-effort `ros2 bag info` cross-check.",
    )
    args = parser.parse_args(argv)

    bag_dir = args.bag_dir.resolve()
    passed, report = verify_bag(
        bag_dir=bag_dir,
        required_topics=list(args.required_topics),
        require_nonzero=list(args.require_nonzero),
        expected_storage=args.expect_storage,
        run_ros2_bag_info=not args.no_ros2_bag_info,
    )

    out = args.out or (bag_dir / REPORT_NAME)
    try:
        _write_atomic(out, report)
    except OSError as exc:
        print(f"[warn] could not write {out}: {exc}", file=sys.stderr)

    if passed:
        print(f"[ok] retained bag integrity verified: {bag_dir}")
    else:
        print("[error] retained bag integrity check FAILED", file=sys.stderr)
        for err in report.get("errors", []):
            print(f"        - {err}", file=sys.stderr)
        print(f"        report: {out}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
