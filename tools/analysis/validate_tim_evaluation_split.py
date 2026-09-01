#!/usr/bin/env python3
"""Validate the frozen TIM-MARS development/final-test split."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


READY = "ready"
PENDING = "reserved_pending_capture"
SET_NAMES = (
    "development",
    "legacy_validation",
    "final_held_out",
)

FULL_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_git(
    repo_root: Path,
    *args: str,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def validate_git_freeze(
    *,
    repo_root: Path,
    algorithm_commit: str,
    config_path: str,
    config_sha256: str,
) -> list[str]:
    errors: list[str] = []

    if not FULL_GIT_COMMIT_RE.fullmatch(algorithm_commit):
        return errors

    commit_check = _run_git(
        repo_root,
        "cat-file",
        "-e",
        f"{algorithm_commit}^{{commit}}",
    )
    if commit_check.returncode != 0:
        errors.append(
            "frozen algorithm commit does not exist in repository: "
            f"{algorithm_commit}"
        )
        return errors

    frozen_config = _run_git(
        repo_root,
        "show",
        f"{algorithm_commit}:{config_path}",
    )
    if frozen_config.returncode != 0:
        errors.append(
            "canonical config is missing from frozen algorithm commit: "
            f"{algorithm_commit}:{config_path}"
        )
    elif sha256_bytes(frozen_config.stdout) != config_sha256:
        errors.append(
            "frozen commit canonical config SHA-256 mismatch"
        )

    ancestry = _run_git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        algorithm_commit,
        "HEAD",
    )
    if ancestry.returncode == 1:
        errors.append(
            "current HEAD does not descend from frozen algorithm commit"
        )
    elif ancestry.returncode != 0:
        errors.append(
            "unable to verify frozen algorithm commit ancestry"
        )

    return errors


def _comparison_file_records(
    value: Any,
) -> list[dict[str, Any]]:
    """Collect explicit path/size/SHA records recursively."""
    records: list[dict[str, Any]] = []

    if isinstance(value, dict):
        if (
            isinstance(value.get("path"), str)
            and isinstance(value.get("size_bytes"), int)
            and isinstance(value.get("sha256"), str)
        ):
            records.append(value)

        for child in value.values():
            records.extend(_comparison_file_records(child))

    elif isinstance(value, list):
        for child in value:
            records.extend(_comparison_file_records(child))

    return records


def validate_final_comparison_contract(
    manifest: dict[str, Any],
    *,
    freeze: dict[str, Any],
    final_entries: list[dict[str, Any]],
    repo_root: Path,
    verify_hashes: bool,
) -> list[str]:
    errors: list[str] = []

    reference = freeze.get("final_comparison_contract")
    if reference is None:
        return errors

    if not isinstance(reference, dict):
        return ["freeze.final_comparison_contract must be an object"]

    for field in ("path", "sha256", "contract_id"):
        _require_text(
            reference,
            field,
            "final_comparison_contract",
            errors,
        )

    reference_path = reference.get("path")
    if not isinstance(reference_path, str) or not reference_path:
        return errors

    contract_path = repo_root / reference_path
    if not contract_path.is_file():
        errors.append(
            "final comparison contract missing: "
            f"{reference_path}"
        )
        return errors

    if verify_hashes:
        actual_contract_hash = sha256_file(contract_path)
        if actual_contract_hash != reference.get("sha256"):
            errors.append(
                "final comparison contract SHA-256 mismatch"
            )
            return errors

    try:
        contract = load_manifest(contract_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(
            f"unable to load final comparison contract: {exc}"
        )
        return errors

    if contract.get("schema_version") != 1:
        errors.append(
            "final comparison contract schema_version must be 1"
        )

    if contract.get("contract_id") != reference.get("contract_id"):
        errors.append(
            "final comparison contract_id does not match split"
        )

    algorithm_commit = freeze.get("algorithm_commit")
    if contract.get("algorithm_freeze_commit") != algorithm_commit:
        errors.append(
            "final comparison algorithm freeze commit does not "
            "match split freeze"
        )

    held_out = contract.get("held_out_split")
    if not isinstance(held_out, dict):
        errors.append(
            "final comparison held_out_split must be an object"
        )
    else:
        if held_out.get("split_id") != manifest.get("split_id"):
            errors.append(
                "final comparison split_id does not match manifest"
            )

        expected_sequence_ids = [
            str(entry.get("id", ""))
            for entry in final_entries
        ]
        if held_out.get("sequence_ids") != expected_sequence_ids:
            errors.append(
                "final comparison held-out sequence IDs do not "
                "match manifest"
            )

    architectures = contract.get("primary_architectures")
    if not isinstance(architectures, list):
        errors.append(
            "final comparison primary_architectures must be a list"
        )
    else:
        architecture_ids = [
            entry.get("id")
            for entry in architectures
            if isinstance(entry, dict)
        ]
        expected_architecture_ids = [
            "bytetrack_raw",
            "target_reid_090",
            "bytetrack_tim_mars",
            "deepsort_raw",
        ]
        if architecture_ids != expected_architecture_ids:
            errors.append(
                "final comparison primary architecture set/order "
                "does not match frozen contract"
            )

        target_reid_entries = [
            entry
            for entry in architectures
            if isinstance(entry, dict)
            and entry.get("id") == "target_reid_090"
        ]
        if (
            len(target_reid_entries) != 1
            or target_reid_entries[0].get("threshold") != 0.90
        ):
            errors.append(
                "final comparison Target-ReID threshold must be 0.90"
            )

    if verify_hashes:
        seen_paths: set[str] = set()

        for record in _comparison_file_records(contract):
            frozen_path = str(record["path"])

            if frozen_path in seen_paths:
                continue
            seen_paths.add(frozen_path)

            file_path = repo_root / frozen_path
            if not file_path.is_file():
                errors.append(
                    "final comparison frozen asset missing: "
                    f"{frozen_path}"
                )
                continue

            actual_size = file_path.stat().st_size
            if actual_size != record["size_bytes"]:
                errors.append(
                    "final comparison frozen asset size mismatch: "
                    f"{frozen_path}"
                )

            if sha256_file(file_path) != record["sha256"]:
                errors.append(
                    "final comparison frozen asset SHA-256 mismatch: "
                    f"{frozen_path}"
                )

        source_freeze = contract.get("source_code_freeze")
        if not isinstance(source_freeze, dict):
            errors.append(
                "final comparison source_code_freeze must be an object"
            )
        else:
            source_commit = source_freeze.get("commit")
            source_paths = source_freeze.get(
                "required_unchanged_paths"
            )

            if source_commit != algorithm_commit:
                errors.append(
                    "final comparison source-code commit does not "
                    "match algorithm freeze"
                )

            if (
                not isinstance(source_paths, list)
                or not source_paths
                or not all(
                    isinstance(item, str) and item
                    for item in source_paths
                )
            ):
                errors.append(
                    "final comparison required_unchanged_paths "
                    "must be a non-empty string list"
                )
            elif isinstance(source_commit, str):
                for source_path in source_paths:
                    at_freeze = _run_git(
                        repo_root,
                        "cat-file",
                        "-e",
                        f"{source_commit}:{source_path}",
                    )
                    if at_freeze.returncode != 0:
                        errors.append(
                            "frozen source path missing at algorithm "
                            f"commit: {source_path}"
                        )

                drift = _run_git(
                    repo_root,
                    "diff",
                    "--quiet",
                    source_commit,
                    "--",
                    *source_paths,
                )
                if drift.returncode == 1:
                    errors.append(
                        "behavior-bearing source code differs from "
                        "frozen algorithm commit"
                    )
                elif drift.returncode != 0:
                    errors.append(
                        "unable to verify behavior-bearing source "
                        "freeze"
                    )

    return errors


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

    algorithm_commit = freeze.get("algorithm_commit")
    if (
        isinstance(algorithm_commit, str)
        and algorithm_commit
        and not FULL_GIT_COMMIT_RE.fullmatch(algorithm_commit)
    ):
        errors.append(
            "freeze.algorithm_commit must be a full 40-character "
            "lowercase Git commit SHA"
        )

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

    if (
        verify_hashes
        and isinstance(algorithm_commit, str)
        and isinstance(config.get("path"), str)
        and isinstance(config.get("sha256"), str)
    ):
        errors.extend(
            validate_git_freeze(
                repo_root=repo_root,
                algorithm_commit=algorithm_commit,
                config_path=config["path"],
                config_sha256=config["sha256"],
            )
        )

    errors.extend(
        validate_final_comparison_contract(
            manifest,
            freeze=freeze,
            final_entries=final_entries,
            repo_root=repo_root,
            verify_hashes=verify_hashes,
        )
    )

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
            "docs/data/splits/tim_mars_split_v2.json"
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
