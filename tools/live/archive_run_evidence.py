#!/usr/bin/env python3
"""Archive the controller/live run logs into a retained flight-evidence package.

Issue #50/#74 evidence retention: after a retained physical closed-loop trial
the controller-facing evidence must be reconstructible from the retained bag
directory alone. The live launcher already archives
``target_authority_events.jsonl`` next to the bag, but the per-node runtime
logs (``control.log``, ``dashboard_bridge.log``, ``target_memory_mars.log``)
and the operator event log only live under
``ros2_ws/log/live_stack/<run-id>/`` and are lost as soon as that run
directory is pruned or the ``latest`` symlink is repointed.

This helper copies an explicit, named set of run-local files into a
deterministic ``<bag>/run_logs/`` subdirectory and writes a machine-readable
``archive_manifest.json`` recording exactly what was copied, what was missing,
and the source run directory. It:

- resolves the run directory from an explicit ``--run-dir`` / ``--run-id``,
  never from a "newest run" or ``latest`` lookup;
- refuses to overwrite an existing retained evidence destination;
- never deletes or mutates the source logs;
- records a missing required log explicitly instead of fabricating an
  empty placeholder;
- copies exact file bytes (``shutil.copy2``), never a symlink.

Exit codes:
    0  every required log copied, manifest written
    1  one or more required logs missing or a copy failed (manifest still
       written, marked incomplete)
    2  usage / IO error (bad run dir, bad bag dir)
    3  refused: the destination already contains retained evidence
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_NAME = "archive_manifest.json"
MANIFEST_SCHEMA_VERSION = 1


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _copy_one(source: Path, dest: Path) -> dict[str, Any]:
    if not source.exists():
        return {"status": "missing", "source": str(source)}
    if source.is_symlink():
        # Copy the real bytes the link points at, never the link itself.
        source = source.resolve()
    if not source.is_file():
        return {"status": "not_a_file", "source": str(source)}
    try:
        shutil.copy2(source, dest, follow_symlinks=True)
    except OSError as exc:
        return {"status": "copy_failed", "source": str(source), "error": str(exc)}
    return {
        "status": "copied",
        "source": str(source),
        "bytes": dest.stat().st_size,
        "sha256": _sha256(dest),
    }


def archive_run_evidence(
    *,
    run_dir: Path,
    run_id: str,
    bag_dir: Path,
    required_logs: list[str],
    optional_files: list[str],
    subdir: str,
) -> tuple[int, dict[str, Any]]:
    if not run_dir.is_dir():
        return 2, {"error": f"run directory not found: {run_dir}"}
    if not bag_dir.is_dir():
        return 2, {"error": f"bag directory not found: {bag_dir}"}

    dest_dir = bag_dir / subdir
    tracked_names = set(required_logs) | set(optional_files) | {MANIFEST_NAME}
    if dest_dir.exists():
        existing = {
            child.name for child in dest_dir.iterdir() if child.name in tracked_names
        }
        if existing:
            return 3, {
                "error": (
                    f"refusing to overwrite existing retained evidence at "
                    f"{dest_dir} (already contains: {sorted(existing)})"
                )
            }

    dest_dir.mkdir(parents=True, exist_ok=True)

    logs_result: dict[str, Any] = {}
    missing_required: list[str] = []
    copy_failed: list[str] = []
    for name in required_logs:
        outcome = _copy_one(run_dir / name, dest_dir / name)
        logs_result[name] = outcome
        if outcome["status"] == "missing":
            missing_required.append(name)
        elif outcome["status"] not in {"copied"}:
            copy_failed.append(name)

    optional_result: dict[str, Any] = {}
    for name in optional_files:
        outcome = _copy_one(run_dir / name, dest_dir / name)
        if outcome["status"] == "missing":
            # An optional file that was never produced is a legitimate,
            # explicitly-recorded condition -- not a fabricated placeholder.
            outcome = {"status": "absent", "source": str(run_dir / name)}
        optional_result[name] = outcome

    complete = not missing_required and not copy_failed

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "bag_dir": str(bag_dir),
        "evidence_subdir": subdir,
        "required_logs": logs_result,
        "optional_files": optional_result,
        "missing_required": sorted(missing_required),
        "copy_failed": sorted(copy_failed),
        "complete": complete,
    }
    _write_manifest_atomic(dest_dir / MANIFEST_NAME, manifest)

    return (0 if complete else 1), manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        dest="logs",
        help="Required run-local log file name (repeatable).",
    )
    parser.add_argument(
        "--optional-file",
        action="append",
        default=[],
        dest="optional_files",
        help="Optional run-local file name; 'absent' is recorded, never faked.",
    )
    parser.add_argument("--subdir", default="run_logs")
    args = parser.parse_args(argv)

    logs = args.logs or [
        "control.log",
        "dashboard_bridge.log",
        "target_memory_mars.log",
    ]

    code, result = archive_run_evidence(
        run_dir=args.run_dir.resolve(),
        run_id=args.run_id,
        bag_dir=args.bag_dir.resolve(),
        required_logs=logs,
        optional_files=list(args.optional_files),
        subdir=args.subdir,
    )

    if code == 2 or code == 3:
        print(f"[error] {result.get('error', 'archive failed')}", file=sys.stderr)
        return code

    dest = args.bag_dir.resolve() / args.subdir
    if code == 0:
        print(f"[ok] archived retained run-evidence logs under {dest}")
    else:
        missing = ", ".join(result.get("missing_required", [])) or "-"
        failed = ", ".join(result.get("copy_failed", [])) or "-"
        print(
            f"[warn] retained run-evidence archival incomplete "
            f"(missing: {missing}; copy_failed: {failed}); manifest: "
            f"{dest / MANIFEST_NAME}",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
