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


def parse_field(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"expected KEY=VALUE, received {value!r}"
        )

    key, field_value = value.split("=", 1)
    key = key.strip()

    if not key:
        raise argparse.ArgumentTypeError("field key cannot be empty")

    return key, field_value


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
        "--field",
        action="append",
        default=[],
        type=parse_field,
        metavar="KEY=VALUE",
    )
    args = parser.parse_args()

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

    output_dir.mkdir(parents=True, exist_ok=True)

    config_copy = output_dir / "tim_mars_resolved_config.yaml"
    shutil.copy2(config_path, config_copy)

    git_status = run_git(repo_root, "status", "--short")

    metadata: dict[str, Any] = {
        "schema_version": 1,
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
        "tim_config_source": str(config_path),
        "tim_config_copy": config_copy.name,
        "tim_config_sha256": sha256_file(config_copy),
        "fields": dict(args.field),
        "environment": {
            "ROS_DOMAIN_ID": os.environ.get("ROS_DOMAIN_ID", ""),
            "THESIS_ROOT": os.environ.get("THESIS_ROOT", ""),
        },
    }

    metadata_path = output_dir / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    fingerprint_path = output_dir / "tim_mars_config.sha256"
    fingerprint_path.write_text(
        f"{metadata['tim_config_sha256']}  {config_copy.name}\n",
        encoding="utf-8",
    )

    print(f"[ok] metadata: {metadata_path}")
    print(f"[ok] configuration copy: {config_copy}")
    print(f"[ok] configuration SHA-256: {metadata['tim_config_sha256']}")

    if metadata["git_dirty"]:
        print(
            "[warn] repository had uncommitted changes when metadata was written",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
