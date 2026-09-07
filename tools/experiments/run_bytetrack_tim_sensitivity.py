#!/usr/bin/env python3
"""Deterministic runner for the frozen ByteTrack / TIM-MARS configuration
sensitivity experiment.

Pipeline per (sequence, configuration) cell:

    frozen recorded images + detections
        -> run_deterministic_tracker_replay.py  (candidate ByteTrack YAML)
        -> /tracks + fixed-ID /target
        -> resolve_bootstrap_target.py           (spatial, physical-v2 reference)
        -> run_deterministic_tim_replay.py       (canonical TIM-MARS, unchanged)
        -> /target_memory_mars + /target
        -> evaluate_physical_target_bbox_v2.py   (identity-independent)
        -> analyse_tracker_target_continuity.py  (raw tracker diagnostics)
        -> analyse_tim_state_occupancy.py        (TIM state occupancy)

The canonical ByteTrack YAML and TIM-MARS are never modified. Candidate YAMLs
are materialized into the run report directory. Failed bootstraps are
preserved as cells, not dropped.

    run_bytetrack_tim_sensitivity.py --materialize-only
    run_bytetrack_tim_sensitivity.py --dry-run
    run_bytetrack_tim_sensitivity.py --run [--repeatability] [--resume]
        [--sequence ID ...] [--config-id ID ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_NAME = "tracker_node"
BASELINE_ID = "canonical_baseline"
DEFAULT_MANIFEST = REPO_ROOT / "docs/data/tracker_sensitivity/bytetrack_tim_sensitivity_v1.yaml"
DEFAULT_MODEL = REPO_ROOT / "models/reid/mars-small128.pb"
TRACKER_REPLAY = REPO_ROOT / "tools/experiments/run_deterministic_tracker_replay.py"
TIM_REPLAY = REPO_ROOT / "tools/experiments/run_deterministic_tim_replay.py"
BOOTSTRAP_RESOLVER = REPO_ROOT / "tools/analysis/resolve_bootstrap_target.py"
PHYSICAL_V2_EVAL = REPO_ROOT / "tools/analysis/evaluate_physical_target_bbox_v2.py"
CONTINUITY_ANALYSER = REPO_ROOT / "tools/analysis/analyse_tracker_target_continuity.py"
STATE_ANALYSER = REPO_ROOT / "tools/analysis/analyse_tim_state_occupancy.py"

EXPECTED_UNIQUE_CONFIGURATIONS = 7
PINNED_NEW_TRACK_THRESH = 0.6


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{path} is not a mapping")
    return document


def canonical_parameters(document: dict[str, Any]) -> dict[str, Any]:
    return dict(document[NODE_NAME]["ros__parameters"])


def git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


# --------------------------------------------------------------------------
# Manifest -> configuration derivation
# --------------------------------------------------------------------------


def verify_canonical_hash(manifest: dict[str, Any], canonical_path: Path) -> str:
    expected = manifest["canonical_tracker_config"]["sha256"]
    actual = sha256_file(canonical_path)
    if actual != expected:
        raise SystemExit(
            f"canonical ByteTrack YAML sha256 mismatch: manifest {expected} "
            f"live {actual}"
        )
    return actual


def derive_configurations(
    manifest: dict[str, Any], canonical: dict[str, Any]
) -> list[dict[str, Any]]:
    canonical_keys = set(canonical)
    configurations = [
        {
            "id": BASELINE_ID,
            "order": 0,
            "dimension_id": None,
            "dimension_label": "canonical baseline",
            "overrides": {},
            "parameters": dict(canonical),
        }
    ]
    order = 1
    for dimension in manifest["dimensions"]:
        dimension_id = str(dimension["id"])
        params = set(dimension["parameters"])
        unknown = params - canonical_keys
        if unknown:
            raise ValueError(f"{dimension_id} references unknown parameters: {sorted(unknown)}")
        for key in params:
            if canonical[key] != dimension["canonical_values"][key]:
                raise ValueError(
                    f"{dimension_id} canonical_values disagree with the live "
                    f"canonical YAML for {key}: live {canonical[key]!r} "
                    f"manifest {dimension['canonical_values'][key]!r}"
                )
        for perturbation in dimension["perturbations"]:
            overrides = dict(perturbation["values"])
            merged = dict(canonical)
            merged.update(overrides)
            configurations.append(
                {
                    "id": str(perturbation["id"]),
                    "order": order,
                    "dimension_id": dimension_id,
                    "dimension_label": dimension.get("label", dimension_id),
                    "overrides": overrides,
                    "parameters": merged,
                }
            )
            order += 1
    return configurations


def validate_configurations(
    configurations: list[dict[str, Any]], canonical: dict[str, Any]
) -> None:
    if len(configurations) != EXPECTED_UNIQUE_CONFIGURATIONS:
        raise ValueError(
            f"expected {EXPECTED_UNIQUE_CONFIGURATIONS} configurations, found "
            f"{len(configurations)}"
        )
    ids = [config["id"] for config in configurations]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate configuration ids: {ids}")
    if configurations[0]["id"] != BASELINE_ID:
        raise ValueError("first configuration must be the canonical baseline")

    for config in configurations:
        params = config["parameters"]
        if float(params["new_track_thresh"]) != PINNED_NEW_TRACK_THRESH:
            raise ValueError(
                f"{config['id']} has new_track_thresh "
                f"{params['new_track_thresh']!r}; it must stay pinned at "
                f"{PINNED_NEW_TRACK_THRESH}"
            )
        changed = {
            key
            for key in params
            if key in canonical and params[key] != canonical[key]
        }
        if config["id"] == BASELINE_ID:
            if changed:
                raise ValueError(f"baseline changed parameters: {sorted(changed)}")
        else:
            if changed != set(config["overrides"]):
                raise ValueError(
                    f"{config['id']} changes {sorted(changed)} but its "
                    f"declared overrides are {sorted(config['overrides'])}"
                )


def materialize_configurations(
    manifest: dict[str, Any],
    manifest_path: Path,
    canonical_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    canonical = canonical_parameters(load_yaml_mapping(canonical_path))
    canonical_sha = verify_canonical_hash(manifest, canonical_path)
    configurations = derive_configurations(manifest, canonical)
    validate_configurations(configurations, canonical)

    config_dir = output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for config in configurations:
        config_path = config_dir / f"{config['id']}.yaml"
        if config["id"] == BASELINE_ID:
            config_path.write_bytes(canonical_path.read_bytes())
        else:
            header = (
                f"# Materialized experiment configuration for "
                f"{manifest['manifest_id']}.\n"
                f"# config_id: {config['id']}\n"
                f"# dimension: {config['dimension_id']}\n"
                f"# overrides vs canonical: {config['overrides']}\n"
                f"# This file is generated. It is NOT a canonical tracker "
                f"profile and must not be promoted.\n"
            )
            document = {NODE_NAME: {"ros__parameters": config["parameters"]}}
            config_path.write_text(
                header + yaml.safe_dump(document, sort_keys=True),
                encoding="utf-8",
            )
        entries.append(
            {
                "id": config["id"],
                "order": config["order"],
                "dimension_id": config["dimension_id"],
                "dimension_label": config["dimension_label"],
                "overrides": config["overrides"],
                "parameters": config["parameters"],
                "path": _rel(config_path),
                "sha256": sha256_file(config_path),
            }
        )

    baseline_entry = next(e for e in entries if e["id"] == BASELINE_ID)
    if baseline_entry["sha256"] != canonical_sha:
        raise ValueError("materialized baseline is not byte-identical to the canonical YAML")

    lock = {
        "schema_version": 1,
        "manifest_id": manifest["manifest_id"],
        "manifest_path": _rel(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "canonical_tracker_config": {
            "path": _rel(canonical_path),
            "sha256": canonical_sha,
        },
        "tim_mars_config": {
            "path": manifest["tim_mars_config"]["path"],
            "sha256": sha256_file(REPO_ROOT / manifest["tim_mars_config"]["path"]),
        },
        "repo_commit": git_value("rev-parse", "HEAD"),
        "repo_status_short": git_value("status", "--short").splitlines(),
        "configurations": entries,
    }
    write_json(output_dir / "manifest_lock.json", lock)
    return lock


# --------------------------------------------------------------------------
# Cell execution
# --------------------------------------------------------------------------


def run_subprocess(command: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n$ {' '.join(command)}\n")
        handle.flush()
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
    return completed.returncode


def read_generated_digest(bag_dir: Path, metadata_name: str) -> str | None:
    path = bag_dir / metadata_name
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data.get("determinism", {}).get("generated_semantic_sha256")


def run_cell(
    *,
    sequence: dict[str, Any],
    config_entry: dict[str, Any],
    run_id: str,
    report_root: Path,
    log_root: Path,
    bag_root: Path,
    repeat_index: int | None,
    resume: bool,
) -> dict[str, Any]:
    seq_id = sequence["id"]
    config_id = config_entry["id"]
    suffix = "" if repeat_index is None else f"_r{repeat_index}"
    cell_id = f"{seq_id}__{config_id}{suffix}"

    eval_dir = report_root / "cells" / cell_id
    cell_json = eval_dir / "cell.json"
    if resume and cell_json.is_file():
        try:
            existing = json.loads(cell_json.read_text())
            if existing.get("status") in {"ok", "bootstrap_failure"}:
                existing["resumed"] = True
                return existing
        except Exception:
            pass

    eval_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"{cell_id}.log"
    bag_dir = bag_root / cell_id
    tracker_bag = bag_dir / "tracker"
    tim_bag = bag_dir / "tim"

    common_input = REPO_ROOT / sequence["common_input"]["path"]
    reference = REPO_ROOT / sequence["physical_reference"]["path"]
    config_path = REPO_ROOT / config_entry["path"]

    started = time.time()
    cell: dict[str, Any] = {
        "cell_id": cell_id,
        "run_id": run_id,
        "sequence_id": seq_id,
        "config_id": config_id,
        "repeat_index": repeat_index,
        "config_overrides": config_entry["overrides"],
        "config_sha256": config_entry["sha256"],
        "common_input": sequence["common_input"]["path"],
        "physical_reference": sequence["physical_reference"]["path"],
        "physical_reference_sha256": sequence["physical_reference"]["sha256"],
        "image_width": sequence["image_width"],
        "image_height": sequence["image_height"],
        "status": "running",
    }

    # 1. tracker replay
    rc = run_subprocess(
        [
            sys.executable, str(TRACKER_REPLAY), str(common_input), str(tracker_bag),
            "--config", str(config_path),
            "--image-topic", sequence["common_input"]["image_topic"],
            "--detections-topic", sequence["common_input"]["detections_topic"],
            "--selection-mode", "largest_first_eligible",
            "--overwrite", "--skip-source-hash",
        ],
        log_path,
    )
    if rc != 0:
        cell.update(status="tracker_replay_failed", returncode=rc, duration_s=round(time.time() - started, 2))
        write_json(cell_json, cell)
        return cell
    cell["tracker_generated_digest"] = read_generated_digest(tracker_bag, "tracker_freeze_metadata.json")

    # 2. bootstrap resolution
    bootstrap_json = eval_dir / "bootstrap.json"
    run_subprocess(
        [
            sys.executable, str(BOOTSTRAP_RESOLVER), str(tracker_bag),
            "--physical-reference", str(reference),
            "--out", str(bootstrap_json),
        ],
        log_path,
    )
    bootstrap = json.loads(bootstrap_json.read_text())
    cell["bootstrap"] = bootstrap
    if not bootstrap.get("ok"):
        cell.update(status="bootstrap_failure", duration_s=round(time.time() - started, 2))
        write_json(cell_json, cell)
        return cell
    resolved_id = int(bootstrap["resolved_track_id"])

    # 3. TIM replay (canonical TIM-MARS, unchanged)
    rc = run_subprocess(
        [
            sys.executable, str(TIM_REPLAY), str(tracker_bag), str(tim_bag),
            "--config", str(REPO_ROOT / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"),
            "--model", str(DEFAULT_MODEL),
            "--selected-track-id", str(resolved_id),
            "--image-topic", "/camera/image_raw",
            "--tracks-topic", "/tracks",
            "--raw-target-topic", "/target",
            "--raw-target-mode", "selected_id",
            "--image-width", str(sequence["image_width"]),
            "--image-height", str(sequence["image_height"]),
            "--compact-output", "--skip-source-hash", "--overwrite",
        ],
        log_path,
    )
    if rc != 0:
        cell.update(status="tim_replay_failed", returncode=rc, duration_s=round(time.time() - started, 2))
        write_json(cell_json, cell)
        return cell
    cell["tim_generated_digest"] = read_generated_digest(tim_bag, "tim_replay_metadata.json")

    # 4. physical-v2 evaluation (raw + TIM in one pass)
    rc = run_subprocess(
        [
            sys.executable, str(PHYSICAL_V2_EVAL), str(tim_bag),
            "--physical-reference", str(reference),
            "--out-dir", str(eval_dir / "physical_v2"),
        ],
        log_path,
    )
    physical = {}
    for stream in ("raw_target", "tim_target_memory"):
        stream_json = eval_dir / "physical_v2" / f"{stream}.json"
        if stream_json.is_file():
            physical[stream] = json.loads(stream_json.read_text())
    cell["physical_v2_returncode"] = rc
    cell["physical_v2"] = {
        stream: {
            "duration_buckets": physical[stream]["duration_buckets"],
            "coverage": physical[stream]["coverage"],
            "localisation": physical[stream].get("localisation", {}),
            "reconciliation": physical[stream]["reconciliation"],
        }
        for stream in physical
    }

    # 5. raw tracker continuity diagnostics
    continuity_json = eval_dir / "raw_tracker_continuity.json"
    run_subprocess(
        [
            sys.executable, str(CONTINUITY_ANALYSER), str(tracker_bag),
            "--physical-reference", str(reference),
            "--out", str(continuity_json),
        ],
        log_path,
    )
    if continuity_json.is_file():
        cell["raw_tracker_continuity"] = json.loads(continuity_json.read_text())

    # 6. TIM state occupancy
    state_json = eval_dir / "tim_state_occupancy.json"
    run_subprocess(
        [sys.executable, str(STATE_ANALYSER), str(tim_bag), "--out", str(state_json)],
        log_path,
    )
    if state_json.is_file():
        cell["tim_state_occupancy"] = json.loads(state_json.read_text())

    ok = bool(physical) and all(
        cell["physical_v2"][s]["reconciliation"]["ok"] for s in cell["physical_v2"]
    )
    cell.update(status="ok" if ok else "evaluation_incomplete", duration_s=round(time.time() - started, 2))
    write_json(cell_json, cell)
    return cell


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


def _bucket(cell: dict[str, Any], stream: str, key: str) -> float | None:
    try:
        return float(cell["physical_v2"][stream]["duration_buckets"][key])
    except (KeyError, TypeError):
        return None


def aggregate(cells: list[dict[str, Any]], report_root: Path) -> None:
    write_json(report_root / "cells.json", cells)

    tim_rows = []
    raw_rows = []
    for cell in sorted(cells, key=lambda c: (c["sequence_id"], c.get("repeat_index") or 0, c["config_id"])):
        base = {
            "cell_id": cell["cell_id"],
            "sequence_id": cell["sequence_id"],
            "config_id": cell["config_id"],
            "repeat_index": cell.get("repeat_index"),
            "status": cell["status"],
            "bootstrap_ok": cell.get("bootstrap", {}).get("ok"),
            "bootstrap_track_id": cell.get("bootstrap", {}).get("resolved_track_id"),
            "bootstrap_iou": cell.get("bootstrap", {}).get("bootstrap_iou"),
        }
        tim_rows.append(
            {
                **base,
                "correct_s": _bucket(cell, "tim_target_memory", "correct_target_output_duration_s"),
                "wrong_s": _bucket(cell, "tim_target_memory", "wrong_person_output_duration_s"),
                "lost_s": _bucket(cell, "tim_target_memory", "lost_or_suppressed_duration_s"),
                "absent_with_output_s": _bucket(
                    cell, "tim_target_memory", "target_absent_with_output_duration_s"
                ),
                "iou_weighted_mean": (
                    cell.get("physical_v2", {})
                    .get("tim_target_memory", {})
                    .get("localisation", {})
                    .get("iou_duration_weighted_mean")
                ),
                "transitions_into_lost": cell.get("tim_state_occupancy", {}).get("transitions_into_lost"),
                "transitions_into_reacquired": cell.get("tim_state_occupancy", {}).get(
                    "transitions_into_reacquired"
                ),
                "authority_changes": cell.get("tim_state_occupancy", {}).get("target_authority_change_count"),
            }
        )
        cont = cell.get("raw_tracker_continuity", {})
        raw_rows.append(
            {
                **base,
                "raw_correct_s": _bucket(cell, "raw_target", "correct_target_output_duration_s"),
                "raw_wrong_s": _bucket(cell, "raw_target", "wrong_person_output_duration_s"),
                "raw_lost_s": _bucket(cell, "raw_target", "lost_or_suppressed_duration_s"),
                "target_id_switches": cont.get("target_id_switch_count"),
                "target_fragments": cont.get("target_track_fragment_count"),
                "target_visible_coverage": cont.get("target_visible_coverage_fraction"),
                "tracks_matching_target_mean": cont.get("tracks_matching_target_mean"),
                "false_continuation_absence_s": cont.get("false_continuation_during_absence_s"),
                "disappearance_delay_s": cont.get("disappearance_delay_s"),
            }
        )

    _write_csv(report_root / "tim_metrics.csv", tim_rows)
    _write_csv(report_root / "raw_tracker_metrics.csv", raw_rows)
    _write_csv(
        report_root / "cells.csv",
        [
            {
                "cell_id": c["cell_id"],
                "sequence_id": c["sequence_id"],
                "config_id": c["config_id"],
                "repeat_index": c.get("repeat_index"),
                "status": c["status"],
                "duration_s": c.get("duration_s"),
                "tracker_digest": c.get("tracker_generated_digest"),
                "tim_digest": c.get("tim_generated_digest"),
            }
            for c in sorted(cells, key=lambda c: c["cell_id"])
        ],
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    columns = list(rows[0].keys())
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join("" if row.get(c) is None else str(row.get(c)) for c in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def selected_sequences(manifest: dict[str, Any], only: Iterable[str] | None) -> list[dict[str, Any]]:
    sequences = manifest["development_set"]["sequences"]
    reserved = set(manifest["development_set"]["reserved_held_out_ids"])
    for sequence in sequences:
        if sequence["id"] in reserved or sequence.get("split_membership_id") in reserved:
            raise SystemExit(f"reserved held-out sequence in matrix: {sequence['id']}")
    if only:
        wanted = set(only)
        sequences = [s for s in sequences if s["id"] in wanted]
        if not sequences:
            raise SystemExit(f"no manifest sequence matched {sorted(wanted)}")
    return sequences


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--report-root", type=Path, default=None)
    parser.add_argument("--sequence", action="append", default=None)
    parser.add_argument("--config-id", action="append", default=None)
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--repeatability", action="store_true", help="Also run canonical baseline x2 per sequence.")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = load_yaml_mapping(manifest_path)
    canonical_path = REPO_ROOT / manifest["canonical_tracker_config"]["path"]

    run_id = args.run_id or f"pXX_bytetrack_tim_sensitivity_{git_value('rev-parse', '--short', 'HEAD')}_{time.strftime('%Y%m%d_%H%M%S')}"
    report_root = (args.report_root or (REPO_ROOT / "reports" / run_id)).resolve()
    log_root = REPO_ROOT / "ros2_ws/log" / run_id
    bag_root = REPO_ROOT / "bags/replay" / run_id
    report_root.mkdir(parents=True, exist_ok=True)

    lock = materialize_configurations(manifest, manifest_path, canonical_path, report_root)
    print(f"[ok] materialized {len(lock['configurations'])} configurations -> {report_root}")

    if args.materialize_only:
        return 0

    sequences = selected_sequences(manifest, args.sequence)
    config_entries = lock["configurations"]
    if args.config_id:
        wanted = set(args.config_id)
        config_entries = [c for c in config_entries if c["id"] in wanted]

    plan: list[tuple[dict[str, Any], dict[str, Any], int | None]] = []
    for sequence in sequences:
        for config_entry in config_entries:
            plan.append((sequence, config_entry, None))
    if args.repeatability:
        baseline = next(c for c in lock["configurations"] if c["id"] == BASELINE_ID)
        for sequence in sequences:
            for repeat_index in (1, 2):
                plan.append((sequence, baseline, repeat_index))

    if args.dry_run or not args.run:
        print(f"[plan] run_id={run_id}")
        for sequence, config_entry, repeat_index in plan:
            tag = "" if repeat_index is None else f" repeat={repeat_index}"
            print(f"  {sequence['id']:22s} {config_entry['id']:22s}{tag}")
        print(f"[plan] {len(plan)} cells; report_root={report_root}")
        if not args.run:
            return 0

    cells: list[dict[str, Any]] = []
    for index, (sequence, config_entry, repeat_index) in enumerate(plan, start=1):
        tag = "" if repeat_index is None else f" r{repeat_index}"
        print(f"[cell {index}/{len(plan)}] {sequence['id']} / {config_entry['id']}{tag}", flush=True)
        cell = run_cell(
            sequence=sequence,
            config_entry=config_entry,
            run_id=run_id,
            report_root=report_root,
            log_root=log_root,
            bag_root=bag_root,
            repeat_index=repeat_index,
            resume=args.resume,
        )
        cells.append(cell)
        print(f"    -> {cell['status']} ({cell.get('duration_s')}s)", flush=True)

    aggregate(cells, report_root)

    provenance = {
        "run_id": run_id,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_commit": git_value("rev-parse", "HEAD"),
        "repo_status_short": git_value("status", "--short").splitlines(),
        "manifest_lock": "manifest_lock.json",
        "split": {
            "path": manifest["development_set"]["split_authority"],
            "id": manifest["development_set"]["split_id"],
            "sha256": sha256_file(REPO_ROOT / manifest["development_set"]["split_authority"]),
        },
        "model": {
            "path": _rel(DEFAULT_MODEL),
            "sha256": sha256_file(DEFAULT_MODEL),
        },
        "cells_total": len(cells),
        "cells_ok": sum(1 for c in cells if c["status"] == "ok"),
        "cells_bootstrap_failure": sum(1 for c in cells if c["status"] == "bootstrap_failure"),
        "cells_other": sum(1 for c in cells if c["status"] not in {"ok", "bootstrap_failure"}),
        "report_root": _rel(report_root),
        "bag_root": _rel(bag_root),
        "log_root": _rel(log_root),
    }
    write_json(report_root / "run_provenance.json", provenance)
    print(f"[done] {provenance['cells_ok']}/{provenance['cells_total']} ok -> {report_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
