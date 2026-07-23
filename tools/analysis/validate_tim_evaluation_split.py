#!/usr/bin/env python3
"""Validate the frozen TIM-MARS development/final-test split."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


READY = "ready"
PENDING = "reserved_pending_capture"
SET_NAMES = (
    "development",
    "legacy_validation",
    "final_held_out",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("split manifest must be a JSON object")
    return value


def _require_text(
    entry: dict[str, Any],
    field: str,
    context: str,
    errors: list[str],
) -> None:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: missing non-empty {field}")


def validate_manifest(
    manifest: dict[str, Any],
    *,
    repo_root: Path,
    verify_hashes: bool,
    require_final_ready: bool,
) -> list[str]:
    errors: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    _require_text(manifest, "split_id", "manifest", errors)

    freeze = manifest.get("freeze")
    if not isinstance(freeze, dict):
        errors.append("manifest: freeze must be an object")
        freeze = {}
    for field in ("created_date", "algorithm_commit"):
        _require_text(freeze, field, "freeze", errors)

    config = freeze.get("canonical_config")
    if not isinstance(config, dict):
        errors.append("freeze: canonical_config must be an object")
        config = {}
    _require_text(config, "path", "canonical_config", errors)
    _require_text(config, "sha256", "canonical_config", errors)

    policy = freeze.get("policy")
    if not isinstance(policy, dict):
        errors.append("freeze: policy must be an object")
        policy = {}
    if policy.get("tuning_allowed_sets") != ["development"]:
        errors.append(
            "policy.tuning_allowed_sets must be exactly ['development']"
        )
    for field in (
        "final_held_out_outcome_access",
        "threshold_change_after_final_access",
        "legacy_validation_use",
    ):
        _require_text(policy, field, "policy", errors)

    sets = manifest.get("sets")
    if not isinstance(sets, dict):
        errors.append("manifest: sets must be an object")
        sets = {}

    all_ids: set[str] = set()
    all_source_paths: set[str] = set()
    final_entries: list[dict[str, Any]] = []

    for set_name in SET_NAMES:
        entries = sets.get(set_name)
        if not isinstance(entries, list):
            errors.append(f"sets.{set_name} must be a list")
            continue
        if set_name == "development" and not entries:
            errors.append("development set must not be empty")
        if set_name == "final_held_out":
            final_entries = [
                entry
                for entry in entries
                if isinstance(entry, dict)
            ]
            if len(entries) < 3:
                errors.append(
                    "final_held_out must reserve at least three sequences"
                )

        for index, entry in enumerate(entries):
            context = f"{set_name}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{context} must be an object")
                continue

            for field in (
                "id",
                "status",
                "scenario",
                "people_group",
                "clothing_group",
                "overlap_record",
            ):
                _require_text(entry, field, context, errors)

            entry_id = str(entry.get("id", ""))
            if entry_id in all_ids:
                errors.append(f"duplicate sequence id: {entry_id}")
            all_ids.add(entry_id)

            status = entry.get("status")
            allowed = (
                {READY}
                if set_name != "final_held_out"
                else {READY, PENDING}
            )
            if status not in allowed:
                errors.append(
                    f"{context}: unsupported status {status!r}"
                )

            if status == PENDING:
                _require_text(
                    entry,
                    "expected_source_path",
                    context,
                    errors,
                )
                if entry.get("files") != []:
                    errors.append(
                        f"{context}: pending capture files must be empty"
                    )
                continue

            for field in (
                "source_path",
                "annotation_path",
                "historical_exposure",
            ):
                _require_text(entry, field, context, errors)
            if not isinstance(entry.get("selected_target_id"), int):
                errors.append(
                    f"{context}: selected_target_id must be an integer"
                )

            source_path = str(entry.get("source_path", ""))
            if source_path in all_source_paths:
                errors.append(
                    f"source path appears in more than one set: "
                    f"{source_path}"
                )
            all_source_paths.add(source_path)

            source = repo_root / source_path
            annotation = repo_root / str(
                entry.get("annotation_path", "")
            )
            if not source.is_dir():
                errors.append(
                    f"{context}: source directory missing: {source_path}"
                )
            if not annotation.is_file():
                errors.append(
                    f"{context}: annotation missing: "
                    f"{entry.get('annotation_path', '')}"
                )

            files = entry.get("files")
            if not isinstance(files, list) or not files:
                errors.append(f"{context}: files must be non-empty")
                continue

            for file_index, frozen_file in enumerate(files):
                file_context = f"{context}.files[{file_index}]"
                if not isinstance(frozen_file, dict):
                    errors.append(f"{file_context} must be an object")
                    continue
                _require_text(
                    frozen_file,
                    "path",
                    file_context,
                    errors,
                )
                _require_text(
                    frozen_file,
                    "sha256",
                    file_context,
                    errors,
                )
                if not isinstance(
                    frozen_file.get("size_bytes"),
                    int,
                ):
                    errors.append(
                        f"{file_context}: size_bytes must be an integer"
                    )
                    continue

                file_path = repo_root / str(
                    frozen_file.get("path", "")
                )
                if not file_path.is_file():
                    errors.append(
                        f"{file_context}: file missing: "
                        f"{frozen_file.get('path', '')}"
                    )
                    continue
                actual_size = file_path.stat().st_size
                if actual_size != frozen_file["size_bytes"]:
                    errors.append(
                        f"{file_context}: size mismatch "
                        f"{actual_size} != {frozen_file['size_bytes']}"
                    )
                if verify_hashes:
                    actual_hash = sha256_file(file_path)
                    if actual_hash != frozen_file["sha256"]:
                        errors.append(
                            f"{file_context}: SHA-256 mismatch"
                        )

            if annotation.is_file() and verify_hashes:
                actual_annotation_hash = sha256_file(annotation)
                if (
                    actual_annotation_hash
                    != entry.get("annotation_sha256")
                ):
                    errors.append(
                        f"{context}: annotation SHA-256 mismatch"
                    )

    if config.get("path"):
        config_path = repo_root / str(config["path"])
        if not config_path.is_file():
            errors.append(
                f"canonical config missing: {config['path']}"
            )
        elif verify_hashes:
            if sha256_file(config_path) != config.get("sha256"):
                errors.append("canonical config SHA-256 mismatch")

    if require_final_ready:
        pending = [
            str(entry.get("id", "<missing>"))
            for entry in final_entries
            if entry.get("status") != READY
        ]
        if pending:
            errors.append(
                "final held-out set is not ready: "
                + ", ".join(pending)
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path(
            "docs/data/splits/tim_mars_split_v1.json"
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
    )
    parser.add_argument(
        "--require-final-ready",
        action="store_true",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    errors = validate_manifest(
        manifest,
        repo_root=args.repo_root.resolve(),
        verify_hashes=args.verify_hashes,
        require_final_ready=args.require_final_ready,
    )
    if errors:
        for error in errors:
            print(f"[error] {error}")
        return 2

    final_entries = manifest["sets"]["final_held_out"]
    ready_count = sum(
        entry.get("status") == READY
        for entry in final_entries
    )
    print(
        f"[ok] split={manifest['split_id']} "
        f"development={len(manifest['sets']['development'])} "
        f"legacy={len(manifest['sets']['legacy_validation'])} "
        f"final_ready={ready_count}/{len(final_entries)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
