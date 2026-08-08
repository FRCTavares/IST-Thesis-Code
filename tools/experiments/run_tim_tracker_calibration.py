#!/usr/bin/env python3
"""Calibrate TIM-MARS for a non-canonical tracker (Issue #58).

Issue #31 froze a 7-dimension, 29-configuration OFAT sensitivity grid for
ByteTrack + TIM-MARS. That grid is a property of TIM-MARS's own decision
parameters, not of ByteTrack specifically, so this tool reuses it verbatim
(imported from ``run_tim_parameter_sensitivity``, never copied) and replays
it against a different tracker's already-materialized ``/tracks`` stream
to search for a configuration that passes the same asymmetric safety gate
Issue #31 used.

This does not retune canonical ByteTrack + TIM-MARS and does not touch the
canonical YAML on disk. It searches for a *separate*, tracker-specific
configuration, exactly as Issue #58's fairness contract requires
("documented tracker-specific calibration using development data only").

Development data only: the three calibration sequences are
``dev_may_hard_reentry``, ``dev_june_seq03``, ``dev_june_seq04`` -- the
frozen development set, never H01-H03.

Protocol-freeze stage usage (no replay execution)::

    run_tim_tracker_calibration.py --print-matrix
    run_tim_tracker_calibration.py --materialize-only

Later, outcome-producing usage::

    run_tim_tracker_calibration.py --run --resume
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "experiments"))

from run_tim_parameter_sensitivity import (  # noqa: E402
    NODE_NAME,
    BASELINE_ID,
    canonical_parameters,
    derive_configurations,
    evaluate_command,
    expected_cells,
    git_value,
    load_yaml_mapping,
    missing_cells,
    read_event_recovery_summary,
    replay_command,
    sha256_file,
    validate_configurations,
    write_json,
)

DIMENSION_GRID_SOURCE = (
    REPO_ROOT / "docs" / "data" / "parameter_sensitivity"
    / "tim_mars_parameter_sensitivity_v1.yaml"
)
CANONICAL_CONFIG_PATH = (
    REPO_ROOT / "ros2_ws" / "src" / "thesis_bringup" / "config"
    / "tim_mars_canonical.yaml"
)
CALIBRATION_MANIFEST_PATH = (
    REPO_ROOT / "docs" / "data" / "lightweight_vs_integrated_tracking"
    / "p058_sort_tim_calibration_v1.yaml"
)
REPLAY_SCRIPT = REPO_ROOT / "tools" / "experiments" / "run_deterministic_tim_replay.py"
EVALUATOR_SCRIPT = REPO_ROOT / "tools" / "analysis" / "evaluate_tim_event_recovery.py"
MARS_MODEL_PATH = REPO_ROOT / "models" / "reid" / "mars-small128.pb"

DEFAULT_TIMEBASE = "header"
DEFAULT_STEP_S = 0.05
DEFAULT_MAX_OUTPUT_AGE_S = 0.90
DEFAULT_STABLE_RECOVERY_S = 0.25
EXPECTED_CONFIGURATIONS = 29
EXPECTED_SEQUENCES = 1  # SORT annotation exists only for dev_may_hard_reentry
EXPECTED_CELLS = EXPECTED_CONFIGURATIONS * EXPECTED_SEQUENCES


def load_calibration_manifest() -> dict[str, Any]:
    manifest = load_yaml_mapping(CALIBRATION_MANIFEST_PATH)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported calibration manifest schema")
    if manifest.get("issue") != 58:
        raise ValueError("calibration manifest is not scoped to issue 58")
    if manifest.get("tracker_type") != "sort":
        raise ValueError("this runner is frozen to tracker_type: sort")
    sequences = manifest.get("calibration_sequences")
    if not isinstance(sequences, list) or len(sequences) != EXPECTED_SEQUENCES:
        raise ValueError(
            f"expected {EXPECTED_SEQUENCES} calibration sequences, found "
            f"{len(sequences) if isinstance(sequences, list) else 'none'}"
        )
    for sequence in sequences:
        if sequence["id"] in {"dev_june_seq01"}:
            raise ValueError(
                "dev_june_seq01 has no SORT annotation yet (pending "
                "manual annotation); it must not enter the calibration set"
            )
        if "final_held_out" in str(sequence.get("split_membership_id", "")):
            raise ValueError(
                f"{sequence['id']} references a held-out split member; "
                "calibration must use development data only"
            )
    return manifest


def derive_grid(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    grid_manifest = load_yaml_mapping(DIMENSION_GRID_SOURCE)
    configurations = derive_configurations(grid_manifest, canonical)
    validate_configurations(configurations, canonical)
    if len(configurations) != EXPECTED_CONFIGURATIONS:
        raise ValueError(
            f"expected {EXPECTED_CONFIGURATIONS} configurations from the "
            f"reused dimension grid, found {len(configurations)}"
        )
    return configurations


def output_root() -> Path:
    return REPO_ROOT / "reports" / "p058_sort_tim_calibration_6231fdc1_2026_08_08"


def materialize(configurations: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    out = output_root()
    config_dir = out / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for config in configurations:
        config_path = config_dir / f"{config['id']}.yaml"
        if config["id"] == BASELINE_ID:
            config_path.write_bytes(CANONICAL_CONFIG_PATH.read_bytes())
        else:
            document = {NODE_NAME: {"ros__parameters": config["parameters"]}}
            config_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        entries.append(
            {
                "id": config["id"],
                "order": config["order"],
                "dimension_id": config["dimension_id"],
                "path": str(config_path),
                "sha256": sha256_file(config_path),
                "overrides": config["overrides"],
            }
        )

    baseline_entry = next(e for e in entries if e["id"] == BASELINE_ID)
    if baseline_entry["sha256"] != sha256_file(CANONICAL_CONFIG_PATH):
        raise ValueError("materialized baseline is not byte-identical to canonical")

    status = git_value(REPO_ROOT, "status", "--short").splitlines()
    lock = {
        "schema_version": 1,
        "manifest_id": manifest["manifest_id"],
        "issue": 58,
        "purpose": "sort_tim_calibration",
        "tracker_type": "sort",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "root": str(REPO_ROOT),
            "commit": git_value(REPO_ROOT, "rev-parse", "HEAD"),
            "branch": git_value(REPO_ROOT, "branch", "--show-current"),
            "status_short": status,
            "dirty": bool(status),
        },
        "dimension_grid_source": {
            "path": str(DIMENSION_GRID_SOURCE),
            "sha256": sha256_file(DIMENSION_GRID_SOURCE),
            "note": "reused verbatim from Issue #31; never copied or edited",
        },
        "canonical_config": {
            "path": str(CANONICAL_CONFIG_PATH),
            "sha256": sha256_file(CANONICAL_CONFIG_PATH),
        },
        "calibration_sequence_ids": [s["id"] for s in manifest["calibration_sequences"]],
        "expected_counts": {
            "unique_configurations": EXPECTED_CONFIGURATIONS,
            "calibration_sequences": EXPECTED_SEQUENCES,
            "total_replay_runs": EXPECTED_CELLS,
        },
        "materialized_configs": entries,
    }
    write_json(out / "sort_calibration_lock.json", lock)
    return lock


def print_matrix(configurations: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    print(f"[matrix] {len(configurations)} configurations x "
          f"{len(manifest['calibration_sequences'])} sequences = "
          f"{len(configurations) * len(manifest['calibration_sequences'])} SORT+TIM calibration cells")
    for config in configurations:
        label = config["dimension_id"] or "canonical"
        print(f"  order={config['order']:>2} id={config['id']:<48} dimension={label}")


def sequence_cell_dirs(out: Path, sequence_id: str) -> Path:
    return out / "sequences" / sequence_id


def scan_completed(out: Path, sequence_ids: list[str]) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    for sequence_id in sequence_ids:
        seq_dir = sequence_cell_dirs(out, sequence_id)
        if not seq_dir.is_dir():
            continue
        for config_dir in seq_dir.iterdir():
            if (config_dir / "report.json").is_file():
                completed.add((config_dir.name, sequence_id))
    return completed


def run(configurations: list[dict[str, Any]], manifest: dict[str, Any], resume: bool) -> int:
    out = output_root()
    lock = materialize(configurations, manifest)
    sequences = manifest["calibration_sequences"]
    sequence_ids = [s["id"] for s in sequences]

    expected = expected_cells(configurations, [{"id": s} for s in sequence_ids])
    completed = scan_completed(out, sequence_ids) if resume else set()
    to_run = sorted(expected - completed)

    print(f"[ok] materialized {len(configurations)} configurations: {out}")
    child_commands: list[str] = []

    for config_id, sequence_id in to_run:
        sequence = next(s for s in sequences if s["id"] == sequence_id)
        config_entry = next(c for c in lock["materialized_configs"] if c["id"] == config_id)
        cell_dir = sequence_cell_dirs(out, sequence_id) / config_id
        cell_dir.mkdir(parents=True, exist_ok=True)
        replay_out = REPO_ROOT / "bags" / "replay" / out.name / sequence_id / config_id

        r_cmd = replay_command(
            replay_script=REPLAY_SCRIPT,
            source_bag=Path(sequence["sort_tracks_bag"]),
            output_bag=replay_out,
            config_path=Path(config_entry["path"]),
            model_path=MARS_MODEL_PATH,
            selected_target_id=int(sequence["selected_track_id"]),
            image_topic="auto",
            skip_source_hash=False,
        )
        print("[run]", " ".join(r_cmd))
        child_commands.append(" ".join(r_cmd))
        result = subprocess.run(r_cmd, check=False)
        if result.returncode != 0:
            print(f"[error] replay failed for {sequence_id}/{config_id}", file=sys.stderr)
            return 1

        e_cmd = evaluate_command(
            evaluator_script=EVALUATOR_SCRIPT,
            output_bag=replay_out,
            annotation_path=Path(sequence["annotation_path"]),
            out_dir=cell_dir,
            timebase=DEFAULT_TIMEBASE,
            step_s=DEFAULT_STEP_S,
            max_output_age_s=DEFAULT_MAX_OUTPUT_AGE_S,
            stable_recovery_duration_s=DEFAULT_STABLE_RECOVERY_S,
        )
        print("[run]", " ".join(e_cmd))
        child_commands.append(" ".join(e_cmd))
        result = subprocess.run(e_cmd, check=False)
        if result.returncode != 0:
            print(f"[error] evaluation failed for {sequence_id}/{config_id}", file=sys.stderr)
            return 1

    write_json(
        out / "run_provenance.json",
        {
            "schema_version": 1,
            "command": "run_tim_tracker_calibration.py --run --resume",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "configuration_ids": [c["id"] for c in configurations],
            "sequence_ids": sequence_ids,
            "child_commands": child_commands,
            "model": {"path": str(MARS_MODEL_PATH), "sha256": sha256_file(MARS_MODEL_PATH)},
        },
    )

    completed_final = scan_completed(out, sequence_ids)
    missing = missing_cells(expected, completed_final)
    if missing:
        print(f"[error] {len(missing)} missing cells after run: {sorted(missing)}", file=sys.stderr)
        return 1

    print(f"[ok] all {len(expected)} config x sequence cells completed: {out}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--print-matrix", action="store_true")
    group.add_argument("--materialize-only", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_calibration_manifest()
    canonical = canonical_parameters(load_yaml_mapping(CANONICAL_CONFIG_PATH))
    configurations = derive_grid(canonical)

    if args.print_matrix:
        print_matrix(configurations, manifest)
        return 0
    if args.materialize_only:
        materialize(configurations, manifest)
        return 0
    if args.run:
        return run(configurations, manifest, resume=args.resume)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
