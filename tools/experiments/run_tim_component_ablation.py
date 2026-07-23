#!/usr/bin/env python3
"""Materialize and run the frozen TIM-MARS component-ablation matrix."""

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

import yaml


REQUIRED_ROW_IDS = (
    "raw_tracker",
    "geometry_only",
    "geometry_positive_appearance",
    "geometry_appearance_margin",
    "geometry_hard_negatives",
    "geometry_persistence",
    "final_simplified_tim_mars",
)
FINAL_ROW_ID = "final_simplified_tim_mars"
DEFAULT_WRONG_TOLERANCE_S = 0.05
NODE_NAME = "target_memory_mars_node"

EXPECTED_FEATURES = {
    "raw_tracker": set(),
    "geometry_only": {"geometry_core"},
    "geometry_positive_appearance": {
        "geometry_core",
        "positive_appearance",
    },
    "geometry_appearance_margin": {
        "geometry_core",
        "positive_appearance",
        "appearance_margin",
    },
    "geometry_hard_negatives": {
        "geometry_core",
        "positive_appearance",
        "hard_negatives",
    },
    "geometry_persistence": {
        "geometry_core",
        "persistence",
    },
    "final_simplified_tim_mars": {
        "geometry_core",
        "positive_appearance",
        "appearance_margin",
        "hard_negatives",
        "persistence",
        "rank_aware_reacquisition",
    },
}

EXPECTED_FLAGS = {
    "geometry_only": {
        "appearance_enabled": False,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": False,
        "short_gap_same_id_priority_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
        "rank_aware_reacquisition_enabled": False,
    },
    "geometry_positive_appearance": {
        "appearance_enabled": True,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": False,
        "short_gap_same_id_priority_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
        "rank_aware_reacquisition_enabled": False,
    },
    "geometry_appearance_margin": {
        "appearance_enabled": True,
        "appearance_conservative_enabled": True,
        "hard_negative_memory_enabled": False,
        "short_gap_same_id_priority_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
        "rank_aware_reacquisition_enabled": False,
    },
    "geometry_hard_negatives": {
        "appearance_enabled": True,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": True,
        "short_gap_same_id_priority_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
        "rank_aware_reacquisition_enabled": False,
    },
    "geometry_persistence": {
        "appearance_enabled": False,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": False,
        "short_gap_same_id_priority_enabled": True,
        "short_gap_new_id_suppression_enabled": True,
        "rank_aware_reacquisition_enabled": False,
    },
}

DURATION_KEYS = (
    "correct_target_duration_s",
    "wrong_target_duration_s",
    "lost_target_duration_s",
    "target_not_visible_duration_s",
    "target_absent_but_output_valid_duration_s",
    "no_target_selected_duration_s",
    "visible_target_duration_s",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping: {path}")
    return payload


def load_json_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON mapping: {path}")
    return payload


def canonical_parameters(document: dict[str, Any]) -> dict[str, Any]:
    try:
        parameters = document[NODE_NAME]["ros__parameters"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid canonical TIM-MARS YAML structure") from exc
    if not isinstance(parameters, dict):
        raise ValueError("canonical ROS parameters must be a mapping")
    return dict(parameters)


def validate_manifest(
    manifest: dict[str, Any],
    canonical: dict[str, Any],
) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported ablation manifest schema")

    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise ValueError("ablation rows must be a list")

    ordered = sorted(rows, key=lambda row: int(row.get("order", 0)))
    row_ids = tuple(str(row.get("id", "")) for row in ordered)
    if row_ids != REQUIRED_ROW_IDS:
        raise ValueError(
            "ablation rows/order do not match issue #28: "
            f"{row_ids!r}"
        )

    canonical_keys = set(canonical)
    for expected_order, row in enumerate(ordered, start=1):
        row_id = str(row["id"])
        if int(row["order"]) != expected_order:
            raise ValueError(f"invalid order for {row_id}")
        if set(row.get("features", [])) != EXPECTED_FEATURES[row_id]:
            raise ValueError(f"invalid feature set for {row_id}")

        kind = row.get("kind")
        if kind not in {"raw", "tim"}:
            raise ValueError(f"invalid row kind for {row_id}: {kind!r}")
        if row_id == "raw_tracker" and kind != "raw":
            raise ValueError("raw_tracker must be a raw row")
        if row_id != "raw_tracker" and kind != "tim":
            raise ValueError(f"{row_id} must be a TIM row")

        overrides = row.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError(f"overrides must be a mapping for {row_id}")
        unknown = set(overrides) - canonical_keys
        if unknown:
            raise ValueError(
                f"unknown canonical overrides for {row_id}: "
                f"{sorted(unknown)}"
            )

        if row_id == FINAL_ROW_ID and overrides:
            raise ValueError("final row must not override canonical values")

        if kind == "tim":
            resolved = dict(canonical)
            resolved.update(overrides)
            for flag, expected in EXPECTED_FLAGS.get(row_id, {}).items():
                if resolved.get(flag) is not expected:
                    raise ValueError(
                        f"{row_id} must set {flag}={expected!r}"
                    )

            if not resolved.get("appearance_enabled", False):
                if resolved.get(
                    "id_switch_min_appearance_similarity",
                    0.0,
                ) != 0.0:
                    raise ValueError(
                        f"{row_id} disables appearance but retains an "
                        "appearance-only ID-switch threshold"
                    )

    return ordered


def resolved_tim_rows(
    manifest: dict[str, Any],
    canonical: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows = validate_manifest(manifest, canonical)
    resolved: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        if row["kind"] != "tim":
            continue
        parameters = dict(canonical)
        parameters.update(row.get("overrides", {}))
        resolved.append((row, parameters))
    return resolved


def git_value(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def materialize_configs(
    *,
    manifest_path: Path,
    canonical_path: Path,
    output_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    manifest = load_yaml_mapping(manifest_path)
    canonical_document = load_yaml_mapping(canonical_path)
    canonical = canonical_parameters(canonical_document)
    rows = validate_manifest(manifest, canonical)

    config_dir = output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_entries: list[dict[str, Any]] = []

    for row, parameters in resolved_tim_rows(manifest, canonical):
        config_path = config_dir / f"{row['id']}.yaml"
        if row["id"] == FINAL_ROW_ID:
            config_path.write_bytes(canonical_path.read_bytes())
        else:
            document = {
                NODE_NAME: {
                    "ros__parameters": parameters,
                }
            }
            config_path.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
        config_entries.append(
            {
                "row_id": row["id"],
                "path": str(config_path),
                "sha256": sha256_file(config_path),
                "overrides": row.get("overrides", {}),
            }
        )

    final_entry = next(
        entry
        for entry in config_entries
        if entry["row_id"] == FINAL_ROW_ID
    )
    if final_entry["sha256"] != sha256_file(canonical_path):
        raise ValueError(
            "final materialized configuration is not byte-identical to "
            "the canonical YAML"
        )

    status = git_value(repo_root, "status", "--short").splitlines()
    lock = {
        "schema_version": 1,
        "matrix_id": manifest["matrix_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "issue": 28,
        "repository": {
            "root": str(repo_root),
            "commit": git_value(repo_root, "rev-parse", "HEAD"),
            "branch": git_value(
                repo_root,
                "branch",
                "--show-current",
            ),
            "status_short": status,
            "dirty": bool(status),
        },
        "manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "canonical_config": {
            "path": str(canonical_path),
            "sha256": sha256_file(canonical_path),
        },
        "rows": [
            {
                "id": row["id"],
                "order": row["order"],
                "label": row["label"],
                "kind": row["kind"],
                "features": row["features"],
                "overrides": row.get("overrides", {}),
            }
            for row in rows
        ],
        "materialized_configs": config_entries,
    }
    write_json(output_dir / "ablation_lock.json", lock)
    return lock


def split_sequences(
    split: dict[str, Any],
    *,
    set_name: str,
    requested_ids: set[str],
) -> list[dict[str, Any]]:
    try:
        sequences = split["sets"][set_name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"split has no set named {set_name!r}") from exc
    if not isinstance(sequences, list):
        raise ValueError(f"split set {set_name!r} must be a list")

    selected = [
        sequence
        for sequence in sequences
        if not requested_ids or sequence.get("id") in requested_ids
    ]
    found = {str(sequence.get("id")) for sequence in selected}
    missing = requested_ids - found
    if missing:
        raise ValueError(f"unknown requested sequences: {sorted(missing)}")
    if not selected:
        raise ValueError("no sequences selected")

    for sequence in selected:
        sequence_id = str(sequence.get("id", ""))
        if sequence.get("status") != "ready":
            raise ValueError(f"sequence is not ready: {sequence_id}")
        for field in (
            "source_path",
            "annotation_path",
            "selected_target_id",
        ):
            if field not in sequence:
                raise ValueError(
                    f"{sequence_id} is missing required field {field}"
                )
    return selected


def command_text(command: Iterable[str]) -> str:
    return shlex.join(str(item) for item in command)


def run_command(
    command: list[str],
    *,
    dry_run: bool,
    command_log: list[str],
) -> None:
    command_log.append(command_text(command))
    print(f"[run] {command_log[-1]}", flush=True)
    if not dry_run:
        subprocess.run(command, check=True)


def read_summary(path: Path) -> dict[str, dict[str, float]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    by_stream: dict[str, dict[str, float]] = {}
    for row in rows:
        stream_name = str(row["stream"])
        by_stream[stream_name] = {
            key: float(row[key])
            for key in DURATION_KEYS
        }
    required = {"raw_target", "tim_target_memory"}
    if set(by_stream) != required:
        raise ValueError(
            f"summary streams must be {sorted(required)}: {path}"
        )
    return by_stream


def metrics_row(
    *,
    sequence_id: str,
    row_id: str,
    label: str,
    stream: dict[str, float],
    raw: dict[str, float],
    wrong_tolerance_s: float,
) -> dict[str, Any]:
    visible = stream["visible_target_duration_s"]
    correct = stream["correct_target_duration_s"]
    wrong = stream["wrong_target_duration_s"]
    lost = stream["lost_target_duration_s"]
    wrong_delta = wrong - raw["wrong_target_duration_s"]
    absent_delta = (
        stream["target_absent_but_output_valid_duration_s"]
        - raw["target_absent_but_output_valid_duration_s"]
    )
    return {
        "sequence_id": sequence_id,
        "row_id": row_id,
        "label": label,
        **stream,
        "correct_target_ratio": correct / visible if visible else math.nan,
        "wrong_target_ratio": wrong / visible if visible else math.nan,
        "lost_target_ratio": lost / visible if visible else math.nan,
        "wrong_delta_vs_raw_s": wrong_delta,
        "absent_output_delta_vs_raw_s": absent_delta,
        "safe_vs_raw": (
            wrong_delta <= wrong_tolerance_s
            and absent_delta <= wrong_tolerance_s
        ),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def aggregate_rows(
    rows: list[dict[str, Any]],
    *,
    wrong_tolerance_s: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["row_id"]), []).append(row)

    raw_group = grouped["raw_tracker"]
    raw_totals = {
        key: sum(float(row[key]) for row in raw_group)
        for key in DURATION_KEYS
    }
    labels = {
        str(row["row_id"]): str(row["label"])
        for row in rows
    }
    aggregated: list[dict[str, Any]] = []
    for row_id in REQUIRED_ROW_IDS:
        group = grouped[row_id]
        totals = {
            key: sum(float(row[key]) for row in group)
            for key in DURATION_KEYS
        }
        aggregated.append(
            metrics_row(
                sequence_id="aggregate",
                row_id=row_id,
                label=labels[row_id],
                stream=totals,
                raw=raw_totals,
                wrong_tolerance_s=wrong_tolerance_s,
            )
        )
    return aggregated


def format_float(value: Any) -> str:
    number = float(value)
    if math.isnan(number):
        return "n/a"
    return f"{number:.3f}"


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    set_name: str,
    wrong_tolerance_s: float,
) -> None:
    lines = [
        "# TIM-MARS component-ablation summary",
        "",
        f"- Evaluation set: `{set_name}`",
        f"- Wrong/absence safety tolerance: `{wrong_tolerance_s:.3f} s`",
        "",
        "| Row | Correct s | Wrong s | Lost s | Correct ratio | "
        "Wrong Δ vs raw s | Absent-output Δ s | Safe |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} "
            f"| {format_float(row['correct_target_duration_s'])} "
            f"| {format_float(row['wrong_target_duration_s'])} "
            f"| {format_float(row['lost_target_duration_s'])} "
            f"| {format_float(row['correct_target_ratio'])} "
            f"| {format_float(row['wrong_delta_vs_raw_s'])} "
            f"| {format_float(row['absent_output_delta_vs_raw_s'])} "
            f"| {'yes' if row['safe_vs_raw'] else 'NO'} |"
        )
    lines.extend(
        [
            "",
            "The final row is promotable only when every sequence and the "
            "aggregate remain within the safety tolerance.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Run the issue #28 TIM-MARS component ablations."
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repo_root
        / "docs/data/ablations/tim_mars_component_ablation_v1.yaml",
    )
    parser.add_argument(
        "--canonical-config",
        type=Path,
        default=repo_root
        / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml",
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=repo_root / "docs/data/splits/tim_mars_split_v1.json",
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
        help="Run only this split sequence ID; may be repeated.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=repo_root / "models/reid/mars-small128.pb",
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--image-topic", default="auto")
    parser.add_argument(
        "--timebase",
        choices=("bag", "header"),
        default="header",
    )
    parser.add_argument("--step-s", type=float, default=0.05)
    parser.add_argument(
        "--wrong-tolerance-s",
        type=float,
        default=DEFAULT_WRONG_TOLERANCE_S,
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--skip-source-hash", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    canonical_path = args.canonical_config.expanduser().resolve()
    split_path = args.split.expanduser().resolve()
    model_path = args.model.expanduser().resolve()

    commit = git_value(repo_root, "rev-parse", "--short=8", "HEAD")
    run_id = f"p028_component_ablation_{commit}_{date.today().isoformat()}"
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

    lock = materialize_configs(
        manifest_path=manifest_path,
        canonical_path=canonical_path,
        output_dir=report_root,
        repo_root=repo_root,
    )
    if args.materialize_only:
        print(f"[ok] materialized matrix: {report_root}")
        return 0

    if not model_path.is_file():
        raise ValueError(f"MARS model does not exist: {model_path}")

    split = load_json_mapping(split_path)
    sequences = split_sequences(
        split,
        set_name=args.set,
        requested_ids=set(args.sequence),
    )
    if args.set == "final_held_out":
        validator = repo_root / "tools/analysis/validate_tim_evaluation_split.py"
        subprocess.run(
            [
                sys.executable,
                str(validator),
                "--split",
                str(split_path),
                "--verify-hashes",
                "--require-final-ready",
            ],
            cwd=repo_root,
            check=True,
        )

    rows_by_id = {
        str(row["id"]): row
        for row in lock["rows"]
    }
    config_by_id = {
        str(entry["row_id"]): Path(entry["path"])
        for entry in lock["materialized_configs"]
    }
    replay_script = (
        repo_root / "tools/experiments/run_deterministic_tim_replay.py"
    )
    evaluator = (
        repo_root / "tools/analysis/evaluate_tim_target_correctness.py"
    )
    event_evaluator = (
        repo_root / "tools/analysis/evaluate_tim_by_event_type.py"
    )
    command_log: list[str] = []
    all_rows: list[dict[str, Any]] = []

    for sequence in sequences:
        sequence_id = str(sequence["id"])
        source_bag = repo_root / str(sequence["source_path"])
        annotation = repo_root / str(sequence["annotation_path"])
        selected_id = int(sequence["selected_target_id"])
        if not (source_bag / "metadata.yaml").is_file():
            raise ValueError(f"source bag is missing: {source_bag}")
        if not annotation.is_file():
            raise ValueError(f"annotation is missing: {annotation}")

        raw_reference: dict[str, float] | None = None
        sequence_rows: list[dict[str, Any]] = []
        for row_id in REQUIRED_ROW_IDS[1:]:
            row = rows_by_id[row_id]
            output_bag = output_root / sequence_id / row_id
            evaluation_dir = (
                report_root / "sequences" / sequence_id / row_id
            )
            summary_path = evaluation_dir / "summary.csv"
            event_path = evaluation_dir / "by_event_type.csv"
            metadata_path = output_bag / "tim_replay_metadata.json"

            complete = (
                summary_path.is_file()
                and event_path.is_file()
                and metadata_path.is_file()
            )
            if not (args.resume and complete):
                replay_command = [
                    sys.executable,
                    str(replay_script),
                    str(source_bag),
                    str(output_bag),
                    "--config",
                    str(config_by_id[row_id]),
                    "--model",
                    str(model_path),
                    "--selected-track-id",
                    str(selected_id),
                    "--image-topic",
                    args.image_topic,
                    "--raw-target-mode",
                    "source",
                    "--compact-output",
                    "--overwrite",
                ]
                if args.skip_source_hash:
                    replay_command.append("--skip-source-hash")
                run_command(
                    replay_command,
                    dry_run=args.dry_run,
                    command_log=command_log,
                )
                run_command(
                    [
                        sys.executable,
                        str(evaluator),
                        str(output_bag),
                        "--annotations",
                        str(annotation),
                        "--out-dir",
                        str(evaluation_dir),
                        "--timebase",
                        args.timebase,
                        "--step-s",
                        str(args.step_s),
                    ],
                    dry_run=args.dry_run,
                    command_log=command_log,
                )
                run_command(
                    [
                        sys.executable,
                        str(event_evaluator),
                        str(output_bag),
                        "--annotations",
                        str(annotation),
                        "--out",
                        str(event_path),
                        "--timebase",
                        args.timebase,
                        "--dt",
                        str(args.step_s),
                    ],
                    dry_run=args.dry_run,
                    command_log=command_log,
                )

            if args.dry_run:
                continue
            streams = read_summary(summary_path)
            raw = streams["raw_target"]
            if raw_reference is None:
                raw_reference = raw
                raw_row = rows_by_id["raw_tracker"]
                sequence_rows.append(
                    metrics_row(
                        sequence_id=sequence_id,
                        row_id="raw_tracker",
                        label=str(raw_row["label"]),
                        stream=raw,
                        raw=raw,
                        wrong_tolerance_s=args.wrong_tolerance_s,
                    )
                )
            elif raw != raw_reference:
                raise ValueError(
                    f"raw baseline changed across rows for {sequence_id}"
                )

            sequence_rows.append(
                metrics_row(
                    sequence_id=sequence_id,
                    row_id=row_id,
                    label=str(row["label"]),
                    stream=streams["tim_target_memory"],
                    raw=raw_reference,
                    wrong_tolerance_s=args.wrong_tolerance_s,
                )
            )

        if args.dry_run:
            continue
        write_csv(
            report_root / "sequences" / sequence_id / "matrix.csv",
            sequence_rows,
        )
        all_rows.extend(sequence_rows)

    provenance = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_lock": "ablation_lock.json",
        "set": args.set,
        "sequence_ids": [str(item["id"]) for item in sequences],
        "split": {
            "path": str(split_path),
            "sha256": sha256_file(split_path),
            "split_id": split.get("split_id"),
        },
        "model": {
            "path": str(model_path),
            "sha256": sha256_file(model_path),
        },
        "runtime": {
            "image_topic": args.image_topic,
            "timebase": args.timebase,
            "step_s": args.step_s,
            "wrong_tolerance_s": args.wrong_tolerance_s,
            "compact_output": True,
            "skip_source_hash": bool(args.skip_source_hash),
        },
        "command": command_text(sys.argv),
        "child_commands": command_log,
    }
    write_json(report_root / "run_provenance.json", provenance)

    if args.dry_run:
        print("[ok] dry-run commands validated")
        return 0

    aggregate = aggregate_rows(
        all_rows,
        wrong_tolerance_s=args.wrong_tolerance_s,
    )
    write_csv(report_root / "matrix_all_sequences.csv", all_rows)
    write_csv(report_root / "matrix_aggregate.csv", aggregate)
    write_json(report_root / "matrix_aggregate.json", aggregate)
    write_markdown(
        report_root / "README.md",
        aggregate,
        set_name=args.set,
        wrong_tolerance_s=args.wrong_tolerance_s,
    )

    final_by_sequence = [
        row
        for row in all_rows
        if row["row_id"] == FINAL_ROW_ID
    ]
    final_aggregate = next(
        row
        for row in aggregate
        if row["row_id"] == FINAL_ROW_ID
    )
    final_safe = (
        all(bool(row["safe_vs_raw"]) for row in final_by_sequence)
        and bool(final_aggregate["safe_vs_raw"])
    )
    print(f"[ok] report: {report_root}")
    if not final_safe:
        print(
            "[blocked] final TIM-MARS increases wrong-target or "
            "target-absence output duration",
            file=sys.stderr,
        )
        return 2
    print("[ok] final TIM-MARS passed the raw-baseline safety gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
