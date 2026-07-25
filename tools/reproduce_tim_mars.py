#!/usr/bin/env python3
"""Run and verify the canonical TIM-MARS reproducibility workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shlex
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FINAL_ROW_ID = "final_simplified_tim_mars"
TIM_ROW_IDS = (
    "geometry_only",
    "geometry_positive_appearance",
    "geometry_appearance_margin",
    "geometry_hard_negatives",
    "geometry_persistence",
    FINAL_ROW_ID,
)
REQUIRED_REPORT_FILES = (
    "ablation_lock.json",
    "run_provenance.json",
    "matrix_all_sequences.csv",
    "matrix_aggregate.csv",
    "matrix_aggregate.json",
    "README.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_value(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def command_text(command: Iterable[str]) -> str:
    return shlex.join(str(item) for item in command)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    command_log: list[str],
) -> int:
    rendered = command_text(command)
    command_log.append(rendered)
    print(f"[run] {rendered}", flush=True)

    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
    )
    return int(result.returncode)


def parse_scalar(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()

    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None

    try:
        return int(stripped)
    except ValueError:
        pass

    try:
        return float(stripped)
    except ValueError:
        return value


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return [
            {
                key: parse_scalar(value)
                for key, value in row.items()
            }
            for row in csv.DictReader(stream)
        ]


def values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right

    if isinstance(left, (int, float)) and isinstance(
        right,
        (int, float),
    ):
        if math.isnan(float(left)) and math.isnan(float(right)):
            return True
        return math.isclose(
            float(left),
            float(right),
            rel_tol=1e-12,
            abs_tol=1e-12,
        )

    return left == right


def verify_csv_json_consistency(
    csv_path: Path,
    json_path: Path,
) -> list[str]:
    errors: list[str] = []
    csv_rows = read_csv_rows(csv_path)
    json_rows = load_json(json_path)

    if not isinstance(json_rows, list):
        return [f"{json_path}: expected a JSON list"]

    if len(csv_rows) != len(json_rows):
        errors.append(
            f"aggregate row count mismatch: "
            f"CSV={len(csv_rows)} JSON={len(json_rows)}"
        )
        return errors

    for index, (csv_row, json_row) in enumerate(
        zip(csv_rows, json_rows),
    ):
        if not isinstance(json_row, dict):
            errors.append(f"JSON row {index} is not an object")
            continue

        if set(csv_row) != set(json_row):
            errors.append(
                f"aggregate row {index} columns differ: "
                f"CSV-only={sorted(set(csv_row) - set(json_row))}, "
                f"JSON-only={sorted(set(json_row) - set(csv_row))}"
            )
            continue

        for key in csv_row:
            if not values_equal(csv_row[key], json_row[key]):
                errors.append(
                    f"aggregate row {index} field {key!r} differs: "
                    f"CSV={csv_row[key]!r} JSON={json_row[key]!r}"
                )

    return errors


def verify_markdown_consistency(
    markdown_path: Path,
    aggregate_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    text = markdown_path.read_text(encoding="utf-8")
    text_lines = text.splitlines()

    for row in aggregate_rows:
        label = str(row["label"])
        row_line = next(
            (
                line
                for line in text_lines
                if line.startswith(f"| {label} ")
            ),
            "",
        )

        if not row_line:
            errors.append(
                f"Markdown aggregate table is missing row {label!r}"
            )
            continue

        numeric_fields = (
            "correct_target_duration_s",
            "wrong_target_duration_s",
            "annotated_id_wrong_target_duration_s",
            "lost_target_duration_s",
            "wrong_delta_vs_raw_s",
            "annotated_id_wrong_delta_vs_raw_s",
        )

        for field in numeric_fields:
            if field not in row:
                errors.append(
                    f"aggregate row {label!r} lacks {field}"
                )
                continue

            formatted = f"{float(row[field]):.3f}"
            if formatted not in row_line:
                errors.append(
                    f"Markdown row {label!r} does not contain "
                    f"{field}={formatted}"
                )

        expected_safe = (
            "yes"
            if bool(row["safe_vs_raw"])
            else "NO"
        )
        if f"| {expected_safe} |" not in row_line:
            errors.append(
                f"Markdown row {label!r} has inconsistent safety value"
            )

    return errors


def verify_fingerprint(
    fingerprint_path: Path,
    target_path: Path,
) -> list[str]:
    if not fingerprint_path.is_file():
        return [f"missing fingerprint: {fingerprint_path}"]
    if not target_path.is_file():
        return [f"missing fingerprint target: {target_path}"]

    fields = fingerprint_path.read_text(
        encoding="utf-8"
    ).strip().split()

    if len(fields) < 2:
        return [f"invalid fingerprint format: {fingerprint_path}"]

    expected_hash = fields[0]
    expected_name = fields[-1]

    errors = []
    if expected_name != target_path.name:
        errors.append(
            f"{fingerprint_path}: target name "
            f"{expected_name!r} != {target_path.name!r}"
        )

    actual_hash = sha256_file(target_path)
    if actual_hash != expected_hash:
        errors.append(
            f"{fingerprint_path}: SHA-256 mismatch "
            f"{actual_hash} != {expected_hash}"
        )

    return errors


def validate_split_command(
    *,
    repo_root: Path,
    split_path: Path,
    set_name: str,
) -> list[str]:
    validator = (
        repo_root
        / "tools"
        / "analysis"
        / "validate_tim_evaluation_split.py"
    )
    command = [
        sys.executable,
        str(validator),
        str(split_path),
        "--repo-root",
        str(repo_root),
        "--verify-hashes",
    ]

    if set_name == "final_held_out":
        command.append("--require-final-ready")

    return command


def matrix_command(
    *,
    repo_root: Path,
    set_name: str,
    output_root: Path,
    report_root: Path,
    model_path: Path,
    sequence_ids: list[str],
    resume: bool,
    dry_run: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(
            repo_root
            / "tools"
            / "experiments"
            / "run_tim_component_ablation.py"
        ),
        "--set",
        set_name,
        "--model",
        str(model_path),
        "--output-root",
        str(output_root),
        "--report-root",
        str(report_root),
    ]

    for sequence_id in sequence_ids:
        command.extend(["--sequence", sequence_id])

    if resume:
        command.append("--resume")
    if dry_run:
        command.append("--dry-run")

    return command


def verify_report(
    *,
    repo_root: Path,
    output_root: Path,
    report_root: Path,
    expected_commit: str,
    allow_dirty: bool,
) -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_REPORT_FILES:
        path = report_root / relative
        if not path.is_file():
            errors.append(f"missing report artifact: {path}")

    if errors:
        return errors

    lock = load_json(report_root / "ablation_lock.json")
    provenance = load_json(report_root / "run_provenance.json")
    aggregate_json = load_json(report_root / "matrix_aggregate.json")

    if not isinstance(lock, dict):
        return ["ablation_lock.json must contain an object"]
    if not isinstance(provenance, dict):
        return ["run_provenance.json must contain an object"]
    if not isinstance(aggregate_json, list):
        return ["matrix_aggregate.json must contain a list"]

    repository = lock.get("repository", {})
    if repository.get("commit") != expected_commit:
        errors.append(
            "ablation lock commit differs from orchestration commit: "
            f"{repository.get('commit')} != {expected_commit}"
        )

    if not allow_dirty and repository.get("dirty") is not False:
        errors.append("ablation lock records a dirty repository")

    canonical = lock.get("canonical_config", {})
    canonical_path = Path(str(canonical.get("path", "")))
    if not canonical_path.is_absolute():
        canonical_path = repo_root / canonical_path

    if not canonical_path.is_file():
        errors.append(
            f"canonical configuration copy/source missing: "
            f"{canonical_path}"
        )
    elif sha256_file(canonical_path) != canonical.get("sha256"):
        errors.append("ablation lock canonical SHA-256 is inconsistent")

    errors.extend(
        verify_csv_json_consistency(
            report_root / "matrix_aggregate.csv",
            report_root / "matrix_aggregate.json",
        )
    )
    errors.extend(
        verify_markdown_consistency(
            report_root / "README.md",
            aggregate_json,
        )
    )

    split = provenance.get("split", {})
    split_path = Path(str(split.get("path", "")))
    if not split_path.is_absolute():
        split_path = repo_root / split_path

    if not split_path.is_file():
        errors.append(f"provenance split is missing: {split_path}")
    elif sha256_file(split_path) != split.get("sha256"):
        errors.append("run provenance split SHA-256 is inconsistent")

    model = provenance.get("model", {})
    model_path = Path(str(model.get("path", "")))
    if not model_path.is_absolute():
        model_path = repo_root / model_path

    if not model_path.is_file():
        errors.append(f"provenance model is missing: {model_path}")
    elif sha256_file(model_path) != model.get("sha256"):
        errors.append("run provenance model SHA-256 is inconsistent")

    materialized = {
        str(entry["row_id"]): entry
        for entry in lock.get("materialized_configs", [])
        if isinstance(entry, dict) and "row_id" in entry
    }
    sequence_ids = [
        str(value)
        for value in provenance.get("sequence_ids", [])
    ]

    for sequence_id in sequence_ids:
        for row_id in TIM_ROW_IDS:
            bag = output_root / sequence_id / row_id
            metadata_path = bag / "tim_replay_metadata.json"
            metadata_fingerprint = (
                bag / "tim_replay_metadata.sha256"
            )
            runtime_path = bag / "tim_mars_resolved_runtime.json"
            runtime_fingerprint = (
                bag / "tim_mars_resolved_runtime.sha256"
            )

            errors.extend(
                verify_fingerprint(
                    metadata_fingerprint,
                    metadata_path,
                )
            )
            errors.extend(
                verify_fingerprint(
                    runtime_fingerprint,
                    runtime_path,
                )
            )

            if not metadata_path.is_file():
                continue

            metadata = load_json(metadata_path)
            if not isinstance(metadata, dict):
                errors.append(
                    f"{metadata_path}: metadata must be an object"
                )
                continue

            replay_repo = metadata.get("repository", {})
            if replay_repo.get("commit") != expected_commit:
                errors.append(
                    f"{sequence_id}/{row_id}: replay commit "
                    f"{replay_repo.get('commit')} != {expected_commit}"
                )

            if (
                not allow_dirty
                and replay_repo.get("status_short") not in ([], None)
            ):
                errors.append(
                    f"{sequence_id}/{row_id}: replay records "
                    "a dirty repository"
                )

            expected_config = materialized.get(row_id, {})
            actual_config = metadata.get("canonical_config", {})
            if (
                actual_config.get("sha256")
                != expected_config.get("sha256")
            ):
                errors.append(
                    f"{sequence_id}/{row_id}: canonical configuration "
                    "fingerprint differs from the matrix lock"
                )

            resolved = metadata.get("resolved_runtime", {})
            if runtime_path.is_file():
                actual_runtime_hash = sha256_file(runtime_path)
                if resolved.get("sha256") != actual_runtime_hash:
                    errors.append(
                        f"{sequence_id}/{row_id}: resolved-runtime "
                        "metadata SHA-256 is inconsistent"
                    )

            metadata_model = metadata.get("model", {})
            if metadata_model.get("sha256") != model.get("sha256"):
                errors.append(
                    f"{sequence_id}/{row_id}: model fingerprint "
                    "differs from run provenance"
                )

    final_rows = [
        row
        for row in aggregate_json
        if row.get("row_id") == FINAL_ROW_ID
    ]
    if len(final_rows) != 1:
        errors.append(
            "aggregate outputs must contain exactly one final TIM-MARS row"
        )
    elif not bool(final_rows[0].get("safe_vs_raw")):
        errors.append(
            "final TIM-MARS aggregate row failed the raw-baseline "
            "safety gate"
        )

    return errors


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description=(
            "Validate, build, run, and verify the canonical TIM-MARS "
            "reproducibility workflow."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root,
    )
    parser.add_argument(
        "--set",
        choices=("development", "final_held_out"),
        default="development",
    )
    parser.add_argument(
        "--sequence",
        action="append",
        default=[],
        help="Restrict the matrix to one split sequence; may be repeated.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=repo_root / "models/reid/mars-small128.pb",
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--report-root", type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate source hashes and contracts without building or replaying.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the workspace build. Intended only for focused diagnostics.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the generated matrix commands without replaying.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permit an uncommitted repository for implementation testing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    split_path = (
        repo_root / "docs/data/splits/tim_mars_split_v1.json"
    )
    model_path = args.model.expanduser().resolve()

    if not repo_root.is_dir():
        print(
            f"[error] repository root does not exist: {repo_root}",
            file=sys.stderr,
        )
        return 2

    commit = git_value(repo_root, "rev-parse", "HEAD")
    commit_short = git_value(
        repo_root,
        "rev-parse",
        "--short=8",
        "HEAD",
    )
    status_short = git_value(
        repo_root,
        "status",
        "--short",
    ).splitlines()

    if status_short and not args.allow_dirty:
        print(
            "[error] repository is dirty; commit or stash changes before "
            "producing reproducibility evidence",
            file=sys.stderr,
        )
        for line in status_short:
            print(f"[error] {line}", file=sys.stderr)
        return 2

    run_id = (
        f"p037_reproducibility_{commit_short}_{date.today().isoformat()}"
    )
    output_root = (
        args.output_root.expanduser().resolve()
        if args.output_root
        else repo_root / "bags/replay" / run_id
    )
    report_root = (
        args.report_root.expanduser().resolve()
        if args.report_root
        else repo_root / "reports" / run_id
    )

    command_log: list[str] = []
    summary_path = report_root / "reproducibility_summary.json"

    summary: dict[str, Any] = {
        "schema_version": 1,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed_at_utc": None,
        "status": "running",
        "set": args.set,
        "sequence_ids": list(args.sequence),
        "repository": {
            "root": str(repo_root),
            "commit": commit,
            "branch": git_value(
                repo_root,
                "branch",
                "--show-current",
            ),
            "dirty": bool(status_short),
            "status_short": status_short,
        },
        "output_root": str(output_root),
        "report_root": str(report_root),
        "commands": command_log,
        "verification_errors": [],
    }
    write_json(summary_path, summary)

    split_command = validate_split_command(
        repo_root=repo_root,
        split_path=split_path,
        set_name=args.set,
    )
    status = run_command(
        split_command,
        cwd=repo_root,
        command_log=command_log,
    )
    if status != 0:
        summary["status"] = "split_validation_failed"
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        write_json(summary_path, summary)
        return status

    split = load_json(split_path)
    canonical = split["freeze"]["canonical_config"]
    canonical_path = repo_root / canonical["path"]

    if sha256_file(canonical_path) != canonical["sha256"]:
        summary["status"] = "canonical_fingerprint_failed"
        summary["verification_errors"] = [
            "canonical configuration SHA-256 differs from the frozen split"
        ]
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        write_json(summary_path, summary)
        print(
            "[error] canonical configuration fingerprint differs from "
            "the frozen split",
            file=sys.stderr,
        )
        return 2

    if not model_path.is_file():
        summary["status"] = "model_missing"
        summary["verification_errors"] = [
            f"MARS model does not exist: {model_path}"
        ]
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        write_json(summary_path, summary)
        print(
            f"[error] MARS model does not exist: {model_path}",
            file=sys.stderr,
        )
        return 2

    if args.validate_only:
        summary["status"] = "validated"
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        summary["canonical_config"] = {
            "path": str(canonical_path),
            "sha256": sha256_file(canonical_path),
        }
        summary["model"] = {
            "path": str(model_path),
            "sha256": sha256_file(model_path),
        }
        write_json(summary_path, summary)
        print(f"[ok] reproducibility validation: {summary_path}")
        return 0

    if not args.skip_build:
        build_command = [
            str(repo_root / "tools/thesis_build.sh"),
        ]
        status = run_command(
            build_command,
            cwd=repo_root,
            command_log=command_log,
        )
        if status != 0:
            summary["status"] = "build_failed"
            summary["completed_at_utc"] = datetime.now(
                timezone.utc
            ).isoformat()
            write_json(summary_path, summary)
            return status

    matrix = matrix_command(
        repo_root=repo_root,
        set_name=args.set,
        output_root=output_root,
        report_root=report_root,
        model_path=model_path,
        sequence_ids=list(args.sequence),
        resume=args.resume,
        dry_run=args.dry_run,
    )
    status = run_command(
        matrix,
        cwd=repo_root,
        command_log=command_log,
    )
    if status != 0:
        summary["status"] = "matrix_failed"
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        write_json(summary_path, summary)
        return status

    if args.dry_run:
        summary["status"] = "dry_run_validated"
        summary["completed_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()
        write_json(summary_path, summary)
        print(f"[ok] reproducibility dry-run: {summary_path}")
        return 0

    errors = verify_report(
        repo_root=repo_root,
        output_root=output_root,
        report_root=report_root,
        expected_commit=commit,
        allow_dirty=args.allow_dirty,
    )
    summary["verification_errors"] = errors
    summary["completed_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    if errors:
        summary["status"] = "verification_failed"
        write_json(summary_path, summary)
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 2

    summary["status"] = "passed"
    summary["canonical_config"] = {
        "path": str(canonical_path),
        "sha256": sha256_file(canonical_path),
    }
    summary["model"] = {
        "path": str(model_path),
        "sha256": sha256_file(model_path),
    }
    write_json(summary_path, summary)

    print(f"[ok] reproducibility report: {report_root}")
    print(f"[ok] orchestration summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
