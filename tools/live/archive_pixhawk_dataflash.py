#!/usr/bin/env python3
"""Associate an ArduPilot / Pixhawk DataFlash ``.bin`` with a retained trial.

Issue #50/#74 field hardening. The native FCU log may be retrieved through
the repository's MAVROS DataFlash helper or another controlled field method.
This archiver does **not** talk to an FCU and does **not** select a log. The
operator identifies the exact file for the trial and passes it in explicitly:

    python3 tools/live/archive_pixhawk_dataflash.py \\
        --run-id "$RUN_ID" \\
        --bag-dir <exact retained bag dir> \\
        --source-bin /path/to/<trial>.bin

It requires an explicit RUN_ID, an explicit retained evidence directory and an
explicit ``.bin`` path; refuses to overwrite an existing archived file or
manifest; preserves the source; copies exact bytes; records SHA-256 of both
source and archived copy; and writes ``pixhawk_dataflash/dataflash_manifest.json``.

The MAVROS catalogue and explicit-ID DataFlash retrieval path was validated on
real hardware while disarmed on 25 September 2026. The archive manifest records
that workflow-level hardware-validation state; the exact source file remains an
explicit operator input.
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
HARDWARE_VERIFICATION = "validated_2026-09-25_mavros_explicit_id"


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
    provenance_dir: Path | None = None,
    subdir: str = DEFAULT_SUBDIR,
) -> tuple[int, dict[str, Any]]:
    if not run_id.strip():
        return 2, {"error": "explicit --run-id required"}
    if not bag_dir.is_dir():
        return 2, {"error": f"retained bag directory not found: {bag_dir}"}
    if not source_bin.is_file():
        return 2, {"error": f"--source-bin is not a file: {source_bin}"}

    provenance_sources: list[Path] = []
    if provenance_dir is not None:
        if not provenance_dir.is_dir():
            return 2, {
                "error": f"--provenance-dir is not a directory: {provenance_dir}"
            }

        provenance_sources = [
            provenance_dir / "before.json",
            provenance_dir / "after.json",
            provenance_dir / "association.json",
            provenance_dir / f"{source_bin.name}.retrieval.json",
        ]

        missing = [str(item) for item in provenance_sources if not item.is_file()]
        if missing:
            return 2, {
                "error": (
                    "explicit DataFlash provenance is incomplete; missing: "
                    + ", ".join(missing)
                )
            }

    dest_dir = bag_dir / subdir
    dest_path = dest_dir / source_bin.name
    manifest_path = dest_dir / MANIFEST_NAME

    provenance_destinations = [
        dest_dir / item.name for item in provenance_sources
    ]
    provenance_conflicts = [
        str(item) for item in provenance_destinations if item.exists()
    ]

    if dest_path.exists() or manifest_path.exists() or provenance_conflicts:
        return 3, {
            "error": (
                f"refusing to overwrite existing DataFlash archive in {dest_dir} "
                f"(dest exists: {dest_path.exists()}, manifest exists: "
                f"{manifest_path.exists()}, provenance conflicts: "
                f"{provenance_conflicts})"
            )
        }

    dest_dir.mkdir(parents=True, exist_ok=True)

    source_sha = _sha256(source_bin)
    source_bytes = source_bin.stat().st_size

    shutil.copy2(source_bin, dest_path, follow_symlinks=True)

    retained_provenance = []
    for source in provenance_sources:
        destination = dest_dir / source.name
        shutil.copy2(source, destination, follow_symlinks=True)

        provenance_source_sha = _sha256(source)
        provenance_destination_sha = _sha256(destination)
        provenance_source_bytes = source.stat().st_size
        provenance_destination_bytes = destination.stat().st_size

        if (
            provenance_source_sha != provenance_destination_sha
            or provenance_source_bytes != provenance_destination_bytes
        ):
            return 1, {
                "error": f"provenance copy mismatch: {source}",
            }

        retained_provenance.append(
            {
                "name": source.name,
                "source_path": str(source),
                "archived_path": str(destination),
                "bytes": provenance_destination_bytes,
                "sha256": provenance_destination_sha,
            }
        )

    archived_sha = _sha256(dest_path)
    archived_bytes = dest_path.stat().st_size
    match = archived_sha == source_sha and archived_bytes == source_bytes

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bag_dir": str(bag_dir),
        "retrieval_method": (
            "mavros_explicit_id_with_catalogue_association"
            if provenance_dir is not None
            else "explicit_operator_supplied_file"
        ),
        "hardware_verification": HARDWARE_VERIFICATION,
        "retrieval_provenance": retained_provenance,
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
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        help=(
            "run-specific directory containing before.json, after.json, "
            "association.json and <source>.retrieval.json"
        ),
    )
    parser.add_argument("--subdir", default=DEFAULT_SUBDIR)
    args = parser.parse_args(argv)

    code, result = archive_dataflash(
        run_id=args.run_id,
        bag_dir=args.bag_dir.resolve(),
        source_bin=args.source_bin.resolve(),
        provenance_dir=(
            args.provenance_dir.resolve()
            if args.provenance_dir is not None
            else None
        ),
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
    print("[note] MAVROS explicit-ID retrieval path hardware-validated 2026-09-25")
    return 0


if __name__ == "__main__":
    sys.exit(main())
