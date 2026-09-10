#!/usr/bin/env python3
"""Associate an ArduPilot / Pixhawk DataFlash ``.bin`` with a retained trial.

Issue #50/#74 field hardening. The native FCU log is retrieved with the
actual field tooling (Mission Planner / MAVProxy / QGroundControl / a wired
SD-card copy) -- this helper does **not** talk to an FCU and does **not** pick
"the latest log". The operator identifies the exact file for the trial and
passes it in explicitly:

    python3 tools/live/archive_pixhawk_dataflash.py \\
        --run-id "$RUN_ID" \\
        --bag-dir <exact retained bag dir> \\
        --source-bin /path/to/<trial>.bin

It requires an explicit RUN_ID, an explicit retained evidence directory and an
explicit ``.bin`` path; refuses to overwrite an existing archived file or
manifest; preserves the source; copies exact bytes; records SHA-256 of both
source and archived copy; and writes ``pixhawk_dataflash/dataflash_manifest.json``.

Real-hardware retrieval verification is **pending** -- there is no Pixhawk to
test against; ``hardware_verification`` in the manifest is ``pending`` until a
field session confirms the end-to-end download step.
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

MANIFEST_NAME = "dataflash_manifest.json"
SCHEMA_VERSION = 1
DEFAULT_SUBDIR = "pixhawk_dataflash"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
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


def archive_dataflash(
    *,
    run_id: str,
    bag_dir: Path,
    source_bin: Path,
    subdir: str = DEFAULT_SUBDIR,
) -> tuple[int, dict[str, Any]]:
    if not run_id.strip():
        return 2, {"error": "explicit --run-id required"}
    if not bag_dir.is_dir():
        return 2, {"error": f"retained bag directory not found: {bag_dir}"}
    if not source_bin.is_file():
        return 2, {"error": f"--source-bin is not a file: {source_bin}"}

    dest_dir = bag_dir / subdir
    dest_path = dest_dir / source_bin.name
    manifest_path = dest_dir / MANIFEST_NAME

    if dest_path.exists() or manifest_path.exists():
        return 3, {
            "error": (
                f"refusing to overwrite existing DataFlash archive in {dest_dir} "
                f"(dest exists: {dest_path.exists()}, manifest exists: "
                f"{manifest_path.exists()})"
            )
        }

    dest_dir.mkdir(parents=True, exist_ok=True)

    source_sha = _sha256(source_bin)
    source_bytes = source_bin.stat().st_size

    shutil.copy2(source_bin, dest_path, follow_symlinks=True)

    archived_sha = _sha256(dest_path)
    archived_bytes = dest_path.stat().st_size
    match = archived_sha == source_sha and archived_bytes == source_bytes

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bag_dir": str(bag_dir),
        "retrieval_method": "explicit_operator_supplied_file",
        "hardware_verification": "pending",
        "source": {
            "path": str(source_bin),
            "name": source_bin.name,
            "bytes": source_bytes,
            "sha256": source_sha,
        },
        "archived": {
            "path": str(dest_path),
            "name": dest_path.name,
            "bytes": archived_bytes,
            "sha256": archived_sha,
        },
        "sha256_match": match,
    }
    _write_atomic(manifest_path, manifest)

    if not match:
        return 1, manifest
    return 0, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument("--source-bin", required=True, type=Path)
    parser.add_argument("--subdir", default=DEFAULT_SUBDIR)
    args = parser.parse_args(argv)

    code, result = archive_dataflash(
        run_id=args.run_id,
        bag_dir=args.bag_dir.resolve(),
        source_bin=args.source_bin.resolve(),
        subdir=args.subdir,
    )

    if code in (2, 3):
        print(f"[error] {result.get('error', 'archive failed')}", file=sys.stderr)
        return code
    if code == 1:
        print(
            "[error] archived DataFlash SHA-256 does not match the source; "
            "the copy is corrupt",
            file=sys.stderr,
        )
        return 1
    print(
        f"[ok] archived {result['archived']['name']} "
        f"({result['archived']['bytes']} bytes, "
        f"sha256 {result['archived']['sha256'][:12]}...) -> "
        f"{result['archived']['path']}"
    )
    print("[note] real-hardware retrieval verification remains pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
