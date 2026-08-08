#!/usr/bin/env python3
"""Materialize, validate, and (eventually) run the frozen Issue #31
TIM-MARS parameter-sensitivity OFAT matrix.

This tool mirrors the architecture of
``tools/experiments/run_tim_component_ablation.py`` (manifest -> validated,
materialized per-configuration YAML -> deterministic replay ->
evaluation -> aggregation) adapted for a 7-dimension, 29-configuration
sensitivity sweep instead of a fixed 7-row ablation matrix. It does not
duplicate TIM-MARS algorithm logic: replay is delegated to
``run_deterministic_tim_replay.py`` and evaluation to
``evaluate_tim_event_recovery.py``, exactly as the ablation runner
delegates to the same replay tool.

Protocol-freeze stage usage (no TIM replay execution)::

    run_tim_parameter_sensitivity.py --print-matrix
    run_tim_parameter_sensitivity.py --materialize-only

Later, outcome-producing usage::

    run_tim_parameter_sensitivity.py --run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


NODE_NAME = "target_memory_mars_node"
BASELINE_ID = "baseline"
EXPECTED_DIMENSIONS = 7
EXPECTED_PERTURBATIONS_PER_DIMENSION = 4
EXPECTED_CONFIGURATIONS = 29
EXPECTED_DEVELOPMENT_SEQUENCES = 4
EXPECTED_RUNS = 116
ACCEPTANCE_PAIR_GAP = 0.08
ACCEPTANCE_PAIR_DIMENSION_ID = "acceptance_pair"
CONFIRMATION_TIME_DIMENSION_ID = "confirmation_time"
CONFIRMATION_TIME_PARAMETER = "min_confirm_frames_after_reacquire"

FORBIDDEN_SPLIT_SETS = ("legacy_validation", "final_held_out")

DEFAULT_TIMEBASE = "header"
DEFAULT_STEP_S = 0.05
DEFAULT_MAX_OUTPUT_AGE_S = 0.90
DEFAULT_STABLE_RECOVERY_S = 0.25


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def command_text(command: Iterable[str]) -> str:
    return shlex.join(str(item) for item in command)


def git_value(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


# --------------------------------------------------------------------------
# Canonical-hash verification (fail closed)
# --------------------------------------------------------------------------


class CanonicalHashMismatch(ValueError):
    """Raised when the live canonical YAML does not match the pinned hash."""


def verify_canonical_hash(
    manifest: dict[str, Any],
    canonical_path: Path,
) -> str:
    expected = manifest["canonical_config"]["sha256"]
    actual = sha256_file(canonical_path)
    if actual != expected:
        raise CanonicalHashMismatch(
            "canonical TIM-MARS YAML does not match the Issue #31 "
            f"frozen pin: expected {expected}, got {actual} "
            f"({canonical_path})"
        )
    return actual


# --------------------------------------------------------------------------
# Manifest structural validation
# --------------------------------------------------------------------------


def validate_manifest_schema(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported parameter-sensitivity manifest schema")
    if manifest.get("issue") != 31:
        raise ValueError("manifest is not scoped to issue 31")
    if manifest.get("raw_target_mode") != "source":
        raise ValueError(
            "primary Issue #31 sensitivity study requires "
            "raw_target_mode: source"
        )

    dimensions = manifest.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("manifest must declare a non-empty dimensions list")
    if len(dimensions) != EXPECTED_DIMENSIONS:
        raise ValueError(
            f"expected {EXPECTED_DIMENSIONS} dimensions, found "
            f"{len(dimensions)}"
        )

    seen_dimension_ids: set[str] = set()
    for dimension in dimensions:
        dimension_id = str(dimension.get("id", ""))
        if not dimension_id:
            raise ValueError("dimension is missing an id")
        if dimension_id in seen_dimension_ids:
            raise ValueError(f"duplicate dimension id: {dimension_id}")
        seen_dimension_ids.add(dimension_id)

        parameters = dimension.get("parameters")
        if not isinstance(parameters, list) or not parameters:
            raise ValueError(f"{dimension_id} must declare parameters")

        canonical_values = dimension.get("canonical_values")
        if not isinstance(canonical_values, dict):
            raise ValueError(f"{dimension_id} must declare canonical_values")
        if set(canonical_values) != set(parameters):
            raise ValueError(
                f"{dimension_id} canonical_values keys must exactly match "
                "parameters"
            )

        perturbations = dimension.get("perturbations")
        if not isinstance(perturbations, list):
            raise ValueError(f"{dimension_id} must declare perturbations")
        if len(perturbations) != EXPECTED_PERTURBATIONS_PER_DIMENSION:
            raise ValueError(
                f"{dimension_id} must declare exactly "
                f"{EXPECTED_PERTURBATIONS_PER_DIMENSION} perturbations, "
                f"found {len(perturbations)}"
            )

        seen_perturbation_ids: set[str] = set()
        for perturbation in perturbations:
            perturbation_id = str(perturbation.get("id", ""))
            if not perturbation_id:
                raise ValueError(f"{dimension_id} has a perturbation with no id")
            if perturbation_id in seen_perturbation_ids:
                raise ValueError(
                    f"duplicate perturbation id: {perturbation_id}"
                )
            seen_perturbation_ids.add(perturbation_id)

            values = perturbation.get("values")
            if not isinstance(values, dict) or set(values) != set(parameters):
                raise ValueError(
                    f"{perturbation_id} values must set exactly "
                    f"{sorted(parameters)}"
                )
            for parameter in parameters:
                if values[parameter] == canonical_values[parameter]:
                    raise ValueError(
                        f"{perturbation_id} does not perturb "
                        f"{parameter} away from its canonical value"
                    )

    sequences = development_sequences(manifest)
    if len(sequences) != EXPECTED_DEVELOPMENT_SEQUENCES:
        raise ValueError(
            f"expected {EXPECTED_DEVELOPMENT_SEQUENCES} development "
            f"sequences, found {len(sequences)}"
        )


def development_sequences(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        sequences = manifest["development_set"]["sequences"]
    except (KeyError, TypeError) as exc:
        raise ValueError("manifest is missing development_set.sequences") from exc
    if not isinstance(sequences, list):
        raise ValueError("development_set.sequences must be a list")
    for sequence in sequences:
        split_membership_id = str(sequence.get("split_membership_id", ""))
        for forbidden in FORBIDDEN_SPLIT_SETS:
            if forbidden in split_membership_id:
                raise ValueError(
                    f"development sequence {sequence.get('id')!r} "
                    f"references a forbidden split set: {forbidden}"
                )
    return sequences


def verify_split_membership(
    manifest: dict[str, Any],
    split: dict[str, Any],
) -> None:
    """Cross-check every declared sequence against the frozen split file.

    Every ``split_membership_id`` referenced by the manifest must exist in
    the split's ``development`` set (never ``legacy_validation`` or
    ``final_held_out``), confirming docs/data/splits/tim_mars_split_v1.json
    remains the authority for development-set membership.
    """
    try:
        development = split["sets"]["development"]
    except (KeyError, TypeError) as exc:
        raise ValueError("split file has no development set") from exc
    known_ids = {str(item.get("id")) for item in development}

    forbidden_ids: set[str] = set()
    for set_name in FORBIDDEN_SPLIT_SETS:
        for item in split.get("sets", {}).get(set_name, []) or []:
            forbidden_ids.add(str(item.get("id")))

    for sequence in development_sequences(manifest):
        membership_id = str(sequence.get("split_membership_id", ""))
        if membership_id in forbidden_ids:
            raise ValueError(
                f"{sequence.get('id')} maps to a forbidden split set "
                f"member: {membership_id}"
            )
        if membership_id not in known_ids:
            raise ValueError(
                f"{sequence.get('id')} references unknown split "
                f"development member: {membership_id}"
            )


# --------------------------------------------------------------------------
# Configuration derivation (deterministic, from dimensions only)
# --------------------------------------------------------------------------


def derive_configurations(
    manifest: dict[str, Any],
    canonical: dict[str, Any],
) -> list[dict[str, Any]]:
    """Deterministically derive the full ordered 29-configuration matrix.

    The manifest stores only ``dimensions`` (each with 4 perturbations);
    this function is the single source of truth for turning that into the
    flat, ordered configuration list, so there is no separately maintained
    "configurations" list that could drift out of sync with the dimensions.
    """
    canonical_keys = set(canonical)
    configurations: list[dict[str, Any]] = [
        {
            "id": BASELINE_ID,
            "order": 0,
            "dimension_id": None,
            "dimension_label": None,
            "overrides": {},
            "parameters": dict(canonical),
        }
    ]

    order = 1
    for dimension in manifest["dimensions"]:
        dimension_id = str(dimension["id"])
        dimension_parameters = set(dimension["parameters"])
        unknown = dimension_parameters - canonical_keys
        if unknown:
            raise ValueError(
                f"{dimension_id} references unknown canonical "
                f"parameters: {sorted(unknown)}"
            )
        for canonical_key in dimension_parameters:
            if canonical[canonical_key] != dimension["canonical_values"][canonical_key]:
                raise ValueError(
                    f"{dimension_id} canonical_values disagree with the "
                    f"live canonical YAML for {canonical_key}"
                )

        for perturbation in dimension["perturbations"]:
            overrides = dict(perturbation["values"])
            parameters = dict(canonical)
            parameters.update(overrides)
            configurations.append(
                {
                    "id": str(perturbation["id"]),
                    "order": order,
                    "dimension_id": dimension_id,
                    "dimension_label": dimension.get("label", dimension_id),
                    "overrides": overrides,
                    "parameters": parameters,
                }
            )
            order += 1

    return configurations


def validate_configurations(
    configurations: list[dict[str, Any]],
    canonical: dict[str, Any],
) -> None:
    if len(configurations) != EXPECTED_CONFIGURATIONS:
        raise ValueError(
            f"expected {EXPECTED_CONFIGURATIONS} configurations, found "
            f"{len(configurations)}"
        )

    ids = [str(config["id"]) for config in configurations]
    if len(set(ids)) != len(ids):
        raise ValueError("configuration ids must be unique")

    baseline = [c for c in configurations if c["id"] == BASELINE_ID]
    if len(baseline) != 1:
        raise ValueError("canonical baseline must appear exactly once")
    if baseline[0]["overrides"]:
        raise ValueError("baseline configuration must not override anything")
    if baseline[0]["parameters"] != canonical:
        raise ValueError("baseline configuration must resolve to canonical")

    for config in configurations:
        if config["id"] == BASELINE_ID:
            continue
        overrides = config["overrides"]
        if not overrides:
            raise ValueError(f"{config['id']} does not override anything")

        # OFAT isolation: the resolved parameters must differ from
        # canonical at exactly the overridden keys, and those keys must be
        # exactly the ones declared for this configuration's own dimension.
        actual_diff_keys = {
            key
            for key, value in config["parameters"].items()
            if value != canonical.get(key)
        }
        if actual_diff_keys != set(overrides):
            raise ValueError(
                f"{config['id']} changes parameters beyond its declared "
                f"overrides: diff={sorted(actual_diff_keys)} "
                f"overrides={sorted(overrides)}"
            )

        if config["dimension_id"] == ACCEPTANCE_PAIR_DIMENSION_ID:
            locked = config["parameters"]["accept_score_locked"]
            lost = config["parameters"]["accept_score_lost"]
            gap = round(lost - locked, 10)
            if gap != ACCEPTANCE_PAIR_GAP:
                raise ValueError(
                    f"{config['id']} breaks the canonical "
                    f"{ACCEPTANCE_PAIR_GAP} LOST-LOCKED gap: {gap}"
                )

        if config["dimension_id"] == CONFIRMATION_TIME_DIMENSION_ID:
            configured = config["parameters"][CONFIRMATION_TIME_PARAMETER]
            if configured < 0:
                raise ValueError(
                    f"{config['id']} sets a negative confirmation-time "
                    f"value: {configured}"
                )


def effective_confirmation_frames(configured: int) -> int:
    return int(configured) + 1


# --------------------------------------------------------------------------
# Materialization
# --------------------------------------------------------------------------


def materialize_configurations(
    *,
    manifest_path: Path,
    canonical_path: Path,
    output_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    manifest = load_yaml_mapping(manifest_path)
    validate_manifest_schema(manifest)
    canonical_document = load_yaml_mapping(canonical_path)
    canonical = canonical_parameters(canonical_document)
    verify_canonical_hash(manifest, canonical_path)

    configurations = derive_configurations(manifest, canonical)
    validate_configurations(configurations, canonical)

    config_dir = output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_entries: list[dict[str, Any]] = []

    for config in configurations:
        config_path = config_dir / f"{config['id']}.yaml"
        if config["id"] == BASELINE_ID:
            config_path.write_bytes(canonical_path.read_bytes())
        else:
            document = {NODE_NAME: {"ros__parameters": config["parameters"]}}
            config_path.write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
        config_entries.append(
            {
                "id": config["id"],
                "order": config["order"],
                "dimension_id": config["dimension_id"],
                "path": str(config_path),
                "sha256": sha256_file(config_path),
                "overrides": config["overrides"],
            }
        )

    baseline_entry = next(
        entry for entry in config_entries if entry["id"] == BASELINE_ID
    )
    if baseline_entry["sha256"] != sha256_file(canonical_path):
        raise ValueError(
            "materialized baseline configuration is not byte-identical to "
            "the canonical YAML"
        )

    sequences = development_sequences(manifest)
    status = git_value(repo_root, "status", "--short").splitlines()
    lock = {
        "schema_version": 1,
        "manifest_id": manifest["manifest_id"],
        "issue": 31,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "root": str(repo_root),
            "commit": git_value(repo_root, "rev-parse", "HEAD"),
            "branch": git_value(repo_root, "branch", "--show-current"),
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
        "raw_target_mode": manifest["raw_target_mode"],
        "development_sequence_ids": [str(s["id"]) for s in sequences],
        "expected_counts": manifest["expected_counts"],
        "materialized_configs": config_entries,
    }
    write_json(output_dir / "parameter_sensitivity_lock.json", lock)
    return lock


# --------------------------------------------------------------------------
# Matrix printing (dry-run / validation-only, no TIM execution)
# --------------------------------------------------------------------------


def print_matrix(
    manifest: dict[str, Any],
    configurations: list[dict[str, Any]],
    sequences: list[dict[str, Any]],
) -> None:
    print(f"Issue #{manifest['issue']} parameter-sensitivity matrix")
    print(f"manifest_id: {manifest['manifest_id']}")
    print(f"raw_target_mode: {manifest['raw_target_mode']}")
    print(
        f"canonical_config sha256: {manifest['canonical_config']['sha256']}"
    )
    print()
    print(f"{'#':>3}  {'config_id':<38} {'dimension':<32} overrides")
    for config in configurations:
        overrides = config["overrides"]
        if config["dimension_id"] == CONFIRMATION_TIME_DIMENSION_ID:
            configured = overrides[CONFIRMATION_TIME_PARAMETER]
            effective = effective_confirmation_frames(configured)
            override_text = (
                f"{CONFIRMATION_TIME_PARAMETER}={configured} "
                f"(effective={effective} frames)"
            )
        else:
            override_text = ", ".join(
                f"{key}={value}" for key, value in overrides.items()
            ) or "(canonical)"
        dimension_label = config["dimension_label"] or "(baseline)"
        print(
            f"{config['order']:>3}  {config['id']:<38} "
            f"{dimension_label:<32} {override_text}"
        )
    print()
    print(f"development sequences ({len(sequences)}):")
    for sequence in sequences:
        print(
            f"  - {sequence['id']} "
            f"(split_membership_id={sequence['split_membership_id']}, "
            f"provenance={sequence['provenance']})"
        )
    total_runs = len(configurations) * len(sequences)
    print()
    print(
        f"accounting: {len(configurations)} configurations x "
        f"{len(sequences)} sequences = {total_runs} deterministic TIM "
        "replay experiments"
    )
    if total_runs != EXPECTED_RUNS:
        raise ValueError(
            f"matrix accounting mismatch: expected {EXPECTED_RUNS}, "
            f"computed {total_runs}"
        )


# --------------------------------------------------------------------------
# Replay / evaluation command construction (used by --run; not executed
# during the protocol-freeze stage)
# --------------------------------------------------------------------------


def replay_command(
    *,
    replay_script: Path,
    source_bag: Path,
    output_bag: Path,
    config_path: Path,
    model_path: Path,
    selected_target_id: int,
    image_topic: str,
    skip_source_hash: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(replay_script),
        str(source_bag),
        str(output_bag),
        "--config",
        str(config_path),
        "--model",
        str(model_path),
        "--selected-track-id",
        str(selected_target_id),
        "--image-topic",
        image_topic,
        "--raw-target-mode",
        "source",
        "--compact-output",
        "--overwrite",
    ]
    if skip_source_hash:
        command.append("--skip-source-hash")
    return command


def evaluate_command(
    *,
    evaluator_script: Path,
    output_bag: Path,
    annotation_path: Path,
    out_dir: Path,
    timebase: str,
    step_s: float,
    max_output_age_s: float,
    stable_recovery_duration_s: float,
) -> list[str]:
    return [
        sys.executable,
        str(evaluator_script),
        str(output_bag),
        "--annotations",
        str(annotation_path),
        "--out-dir",
        str(out_dir),
        "--timebase",
        timebase,
        "--step-s",
        str(step_s),
        "--max-output-age-s",
        str(max_output_age_s),
        "--stable-recovery-duration-s",
        str(stable_recovery_duration_s),
    ]


def read_event_recovery_summary(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    by_stream: dict[str, dict[str, str]] = {}
    for row in rows:
        by_stream[str(row["stream"])] = dict(row)
    required = {"raw_target", "tim_target_memory"}
    if set(by_stream) != required:
        raise ValueError(f"summary streams must be {sorted(required)}: {path}")
    return by_stream


def assert_raw_invariant(
    *,
    sequence_id: str,
    config_id: str,
    current_raw: dict[str, str],
    reference_raw: dict[str, str],
) -> None:
    """Fail loudly if a config's raw/ByteTrack stream drifted.

    The raw stream is a property of the source bag/detector/tracker only
    and must not change as TIM-MARS parameters are perturbed. A repeated
    raw stream must be *verified* equal to the sequence's first-observed
    raw stream, never counted as new independent baseline evidence.
    """
    if current_raw != reference_raw:
        raise ValueError(
            f"raw/ByteTrack reference stream changed for {sequence_id} "
            f"at configuration {config_id}; this indicates a tooling or "
            "non-determinism bug, not new evidence"
        )


class MissingCellError(ValueError):
    """Raised when an expected config x sequence cell has no evaluation."""


def expected_cells(
    configurations: list[dict[str, Any]],
    sequences: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    return {
        (config["id"], sequence["id"])
        for config in configurations
        for sequence in sequences
    }


def missing_cells(
    expected: set[tuple[str, str]],
    completed: set[tuple[str, str]],
) -> set[tuple[str, str]]:
    return expected - completed


def require_no_missing_cells(
    expected: set[tuple[str, str]],
    completed: set[tuple[str, str]],
) -> None:
    missing = missing_cells(expected, completed)
    if missing:
        raise MissingCellError(
            "aggregation attempted with missing config x sequence cells: "
            f"{sorted(missing)}"
        )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description=(
            "Materialize, validate, and (with --run) execute the frozen "
            "Issue #31 TIM-MARS parameter-sensitivity OFAT matrix."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repo_root
        / "docs/data/parameter_sensitivity/tim_mars_parameter_sensitivity_v1.yaml",
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
        "--model",
        type=Path,
        default=repo_root / "models/reid/mars-small128.pb",
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--image-topic", default="auto")
    parser.add_argument("--timebase", choices=("bag", "header"), default=DEFAULT_TIMEBASE)
    parser.add_argument("--step-s", type=float, default=DEFAULT_STEP_S)
    parser.add_argument(
        "--max-output-age-s", type=float, default=DEFAULT_MAX_OUTPUT_AGE_S
    )
    parser.add_argument(
        "--stable-recovery-duration-s",
        type=float,
        default=DEFAULT_STABLE_RECOVERY_S,
    )
    parser.add_argument(
        "--sequence",
        action="append",
        default=[],
        help="Restrict to this development sequence id; may be repeated.",
    )
    parser.add_argument(
        "--config-id",
        action="append",
        default=[],
        help="Restrict to this configuration id; may be repeated.",
    )
    parser.add_argument("--skip-source-hash", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--print-matrix",
        action="store_true",
        help="Print the full 29-configuration matrix and exit. No TIM "
        "execution, no materialization required.",
    )
    parser.add_argument(
        "--materialize-only",
        action="store_true",
        help="Validate the manifest, materialize per-configuration YAML "
        "files and the lock file, and exit. No TIM execution.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print every replay/evaluate command that --run would "
        "execute, without executing them.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the 116-cell replay/evaluation matrix. Must not be "
        "used until the frozen protocol has been reviewed and committed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    canonical_path = args.canonical_config.expanduser().resolve()
    split_path = args.split.expanduser().resolve()

    manifest = load_yaml_mapping(manifest_path)
    validate_manifest_schema(manifest)
    canonical_document = load_yaml_mapping(canonical_path)
    canonical = canonical_parameters(canonical_document)
    verify_canonical_hash(manifest, canonical_path)

    split = load_json_mapping(split_path)
    verify_split_membership(manifest, split)

    configurations = derive_configurations(manifest, canonical)
    validate_configurations(configurations, canonical)
    sequences = development_sequences(manifest)

    if args.sequence:
        requested = set(args.sequence)
        sequences = [s for s in sequences if s["id"] in requested]
        missing = requested - {s["id"] for s in sequences}
        if missing:
            raise ValueError(f"unknown requested sequences: {sorted(missing)}")

    if args.config_id:
        requested_configs = set(args.config_id)
        configurations = [
            c for c in configurations if c["id"] in requested_configs
        ]
        missing = requested_configs - {c["id"] for c in configurations}
        if missing:
            raise ValueError(
                f"unknown requested configurations: {sorted(missing)}"
            )

    if args.print_matrix:
        print_matrix(manifest, configurations, sequences)
        return 0

    commit = git_value(repo_root, "rev-parse", "--short=8", "HEAD")
    run_id = f"p031_parameter_sensitivity_{commit}_{date.today().isoformat()}"
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

    lock = materialize_configurations(
        manifest_path=manifest_path,
        canonical_path=canonical_path,
        output_dir=report_root,
        repo_root=repo_root,
    )
    print(f"[ok] materialized {len(lock['materialized_configs'])} configurations: {report_root}")

    if args.materialize_only:
        return 0

    if not (args.dry_run or args.run):
        print(
            "[ok] manifest and matrix validated; pass --print-matrix, "
            "--dry-run, or --run for further action",
        )
        return 0

    if not args.model.expanduser().resolve().is_file() and args.run:
        raise ValueError(f"MARS model does not exist: {args.model}")

    replay_script = repo_root / "tools/experiments/run_deterministic_tim_replay.py"
    evaluator_script = repo_root / "tools/analysis/evaluate_tim_event_recovery.py"
    config_by_id = {
        entry["id"]: Path(entry["path"]) for entry in lock["materialized_configs"]
    }

    command_log: list[str] = []
    completed_cells: set[tuple[str, str]] = set()
    reference_raw: dict[str, dict[str, str]] = {}

    for sequence in sequences:
        sequence_id = str(sequence["id"])
        source_bag = repo_root / str(sequence["source_path"])
        annotation = repo_root / str(sequence["annotation_path"])
        selected_id = int(sequence["selected_target_id"])
        if args.run:
            if not (source_bag / "metadata.yaml").is_file():
                raise ValueError(f"source bag is missing: {source_bag}")
            if not annotation.is_file():
                raise ValueError(f"annotation is missing: {annotation}")

        for config in configurations:
            config_id = str(config["id"])
            output_bag = output_root / sequence_id / config_id
            evaluation_dir = report_root / "sequences" / sequence_id / config_id
            summary_path = evaluation_dir / "summary.csv"

            complete = summary_path.is_file()
            if not (args.resume and complete):
                replay_cmd = replay_command(
                    replay_script=replay_script,
                    source_bag=source_bag,
                    output_bag=output_bag,
                    config_path=config_by_id[config_id],
                    model_path=args.model,
                    selected_target_id=selected_id,
                    image_topic=args.image_topic,
                    skip_source_hash=args.skip_source_hash,
                )
                command_log.append(command_text(replay_cmd))
                print(f"[run] {command_log[-1]}", flush=True)

                eval_cmd = evaluate_command(
                    evaluator_script=evaluator_script,
                    output_bag=output_bag,
                    annotation_path=annotation,
                    out_dir=evaluation_dir,
                    timebase=args.timebase,
                    step_s=args.step_s,
                    max_output_age_s=args.max_output_age_s,
                    stable_recovery_duration_s=args.stable_recovery_duration_s,
                )
                command_log.append(command_text(eval_cmd))
                print(f"[run] {command_log[-1]}", flush=True)

                if args.run:
                    subprocess.run(replay_cmd, check=True)
                    subprocess.run(eval_cmd, check=True)

            if not args.run:
                continue

            summary = read_event_recovery_summary(summary_path)
            if sequence_id not in reference_raw:
                reference_raw[sequence_id] = summary["raw_target"]
            else:
                assert_raw_invariant(
                    sequence_id=sequence_id,
                    config_id=config_id,
                    current_raw=summary["raw_target"],
                    reference_raw=reference_raw[sequence_id],
                )
            completed_cells.add((config_id, sequence_id))

    provenance = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_lock": "parameter_sensitivity_lock.json",
        "sequence_ids": [str(s["id"]) for s in sequences],
        "configuration_ids": [str(c["id"]) for c in configurations],
        "raw_target_mode": manifest["raw_target_mode"],
        "split": {
            "path": str(split_path),
            "sha256": sha256_file(split_path),
            "split_id": split.get("split_id"),
        },
        "model": {
            "path": str(args.model),
            "sha256": sha256_file(args.model)
            if args.model.expanduser().resolve().is_file()
            else None,
        },
        "runtime": {
            "image_topic": args.image_topic,
            "timebase": args.timebase,
            "step_s": args.step_s,
            "max_output_age_s": args.max_output_age_s,
            "stable_recovery_duration_s": args.stable_recovery_duration_s,
            "skip_source_hash": bool(args.skip_source_hash),
        },
        "command": command_text(sys.argv),
        "child_commands": command_log,
    }
    write_json(report_root / "run_provenance.json", provenance)

    if args.dry_run:
        print("[ok] dry-run commands validated")
        return 0

    expected = expected_cells(configurations, sequences)
    require_no_missing_cells(expected, completed_cells)
    print(
        f"[ok] all {len(completed_cells)} config x sequence cells "
        f"completed: {report_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
