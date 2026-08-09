#!/usr/bin/env python3
"""Validate a live-run metadata record before it can be promoted as evidence.

Issue #54 acceptance criteria require that every retained live run pass a
machine-readable provenance validator, and that no promoted dataset be
missing the image stream (or any other topic) it claims to contain. This
checks schema completeness, re-verifies recorded file hashes against the
files on disk, and flags any recorded topic that had zero publishers at
capture time -- the exact failure mode Issue #54's own audit evidence
described for /camera/image_raw and /camera/fps.

Exit codes: 0 = PASS, 1 = validation failure, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA_VERSIONS = (1,)

REQUIRED_TOP_LEVEL_KEYS = (
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


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in payload:
            errors.append(f"missing required top-level key: {key}")

    if errors:
        return errors, warnings

    schema_version = payload["schema_version"]
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            f"unsupported schema_version {schema_version!r}; "
            f"expected one of {SUPPORTED_SCHEMA_VERSIONS}"
        )

    git_info = payload.get("git", {})
    commit = git_info.get("commit")
    if not commit or not isinstance(commit, str) or len(commit) != 40:
        errors.append(f"git.commit missing or not a 40-char SHA: {commit!r}")
    if git_info.get("dirty") is True:
        warnings.append(
            f"repository was dirty at capture time "
            f"({git_info.get('dirty_file_count', '?')} file(s) changed)"
        )

    invocation = payload.get("invocation", {})
    if not invocation.get("command"):
        errors.append("invocation.command is missing or empty")

    bag = payload.get("bag", {})
    recorded_topics = bag.get("recorded_topics") or []
    if not recorded_topics:
        errors.append("bag.recorded_topics is empty")

    resolved_parameters = payload.get("resolved_parameters") or {}
    if not resolved_parameters:
        errors.append("resolved_parameters is empty -- no node parameters captured")

    hashes = payload.get("hashes") or {}
    for label, entry in hashes.items():
        recorded_hash = entry.get("sha256")
        path_str = entry.get("path")
        if entry.get("exists") and not recorded_hash:
            errors.append(f"hashes.{label}: marked exists=true but sha256 is null")
            continue
        if not path_str or recorded_hash is None:
            continue
        current_hash = sha256_file(Path(path_str))
        if current_hash is None:
            warnings.append(
                f"hashes.{label}: file no longer exists on disk ({path_str}); "
                "cannot re-verify"
            )
        elif current_hash != recorded_hash:
            errors.append(
                f"hashes.{label}: recorded sha256 {recorded_hash[:12]}... does not "
                f"match current file content {current_hash[:12]}... ({path_str})"
            )

    topic_qos_inventory = payload.get("topic_qos_inventory") or {}
    for topic in recorded_topics:
        info = topic_qos_inventory.get(topic)
        if info is None:
            warnings.append(f"topic {topic}: no QoS inventory entry captured")
            continue
        if "error" in info:
            warnings.append(f"topic {topic}: introspection failed: {info['error']}")
            continue
        publisher_count = info.get("publisher_count")
        if publisher_count == 0:
            errors.append(
                f"topic {topic}: listed as recorded but had zero publishers at "
                "capture time -- the bag will contain no data for this topic"
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_path", type=Path, help="Path to run_metadata.json")
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON result to stdout"
    )
    args = parser.parse_args()

    if not args.metadata_path.is_file():
        print(f"[error] metadata file not found: {args.metadata_path}", file=sys.stderr)
        return 2

    try:
        payload = json.loads(args.metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[error] metadata file is not valid JSON: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(payload)
    passed = len(errors) == 0

    if args.json:
        print(
            json.dumps(
                {
                    "metadata_path": str(args.metadata_path),
                    "passed": passed,
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for warning in warnings:
            print(f"[warn] {warning}")
        for error in errors:
            print(f"[error] {error}")
        print(f"[{'PASS' if passed else 'FAIL'}] {args.metadata_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
