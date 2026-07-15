#!/usr/bin/env python3
"""Write reproducibility metadata for a TIM-MARS experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"expected KEY=VALUE, received {value!r}"
        )

    key, field_value = value.split("=", 1)
    key = key.strip()

    if not key:
        raise argparse.ArgumentTypeError("assignment key cannot be empty")

    return key, field_value


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    lowered = normalized.lower()

    if lowered == "true":
        return True

    if lowered == "false":
        return False

    if lowered in {"none", "null"}:
        return None

    try:
        return int(normalized)
    except ValueError:
        pass

    try:
        return float(normalized)
    except ValueError:
        return value


def assignments_to_dict(
    assignments: list[tuple[str, str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in assignments:
        if key in result:
            raise ValueError(f"duplicate assignment key: {key}")

        result[key] = parse_scalar(value)

    return result


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record TIM-MARS configuration and repository provenance."
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--command", required=True)
    parser.add_argument(
        "--effective-command",
        help=(
            "Fully resolved replay command including effective environment "
            "values. Defaults to --command for runners that have not yet "
            "provided explicit value-source provenance."
        ),
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        type=parse_assignment,
        metavar="KEY=SOURCE",
        help="Origin of an effective replay value.",
    )
    parser.add_argument(
        "--runtime",
        action="append",
        default=[],
        type=parse_assignment,
        metavar="KEY=VALUE",
        help="Effective ROS runtime override.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        type=parse_assignment,
        metavar="KEY=VALUE",
        help="Experiment context that is not a TIM ROS parameter.",
    )
    args = parser.parse_args()

    effective_command = args.effective_command or args.command

    repo_root = args.repo_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    config_path = args.config.expanduser().resolve()
    runner_path = args.runner.expanduser().resolve()

    if not repo_root.is_dir():
        parser.error(f"repository root does not exist: {repo_root}")

    if not config_path.is_file():
        parser.error(f"TIM configuration does not exist: {config_path}")

    if not runner_path.is_file():
        parser.error(f"runner does not exist: {runner_path}")

    try:
        value_sources = assignments_to_dict(args.source)
        runtime_overrides = assignments_to_dict(args.runtime)
        experiment_fields = assignments_to_dict(args.field)
    except ValueError as exc:
        parser.error(str(exc))

    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_copy = output_dir / "tim_mars_canonical_config.yaml"
    shutil.copy2(config_path, canonical_copy)
    canonical_sha256 = sha256_file(canonical_copy)

    resolved_runtime: dict[str, Any] = {
        "schema_version": 2,
        "canonical_config": {
            "copy": canonical_copy.name,
            "sha256": canonical_sha256,
            "source": str(config_path),
        },
        "runtime_overrides": runtime_overrides,
        "experiment_fields": experiment_fields,
        "value_sources": value_sources,
    }

    resolved_runtime_path = output_dir / "tim_mars_resolved_runtime.json"
    write_json(resolved_runtime_path, resolved_runtime)
    resolved_runtime_sha256 = sha256_file(resolved_runtime_path)

    resolved_fingerprint_path = (
        output_dir / "tim_mars_resolved_runtime.sha256"
    )
    resolved_fingerprint_path.write_text(
        f"{resolved_runtime_sha256}  {resolved_runtime_path.name}\n",
        encoding="utf-8",
    )

    git_status = run_git(repo_root, "status", "--short")

    metadata: dict[str, Any] = {
        "schema_version": 3,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(repo_root),
        "git_commit": run_git(repo_root, "rev-parse", "HEAD"),
        "git_commit_short": run_git(
            repo_root,
            "rev-parse",
            "--short",
            "HEAD",
        ),
        "git_branch": run_git(repo_root, "branch", "--show-current"),
        "git_dirty": bool(git_status),
        "git_status_short": git_status.splitlines(),
        "runner": str(runner_path),
        "command": args.command,
        "effective_command": effective_command,
        "value_sources": value_sources,
        "canonical_config": {
            "source": str(config_path),
            "copy": canonical_copy.name,
            "sha256": canonical_sha256,
        },
        "resolved_runtime": {
            "file": resolved_runtime_path.name,
            "fingerprint_file": resolved_fingerprint_path.name,
            "sha256": resolved_runtime_sha256,
        },
        "environment": {
            "ROS_DOMAIN_ID": os.environ.get("ROS_DOMAIN_ID", ""),
            "THESIS_ROOT": os.environ.get("THESIS_ROOT", ""),
        },
    }

    metadata_path = output_dir / "run_metadata.json"
    write_json(metadata_path, metadata)

    print(f"[ok] metadata: {metadata_path}")
    print(f"[ok] canonical configuration: {canonical_copy}")
    print(f"[ok] canonical SHA-256: {canonical_sha256}")
    print(f"[ok] resolved runtime: {resolved_runtime_path}")
    print(f"[ok] resolved runtime SHA-256: {resolved_runtime_sha256}")

    if metadata["git_dirty"]:
        print(
            "[warn] repository had uncommitted changes when metadata was written",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
