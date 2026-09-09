#!/usr/bin/env python3
"""Frozen Issue #58 final architecture-comparison orchestrator.

The runner implements the active Stage-7 prospective freeze:
``tim_mars_final_comparison_v3_2026_09_08`` bound to
``tim_mars_split_v4_2026_09_08`` (algorithm authority
``79f11b631688889bf5ffbeb3c16ef543a53f9973``). The superseded
``tim_mars_final_comparison_v2_2026_09_05`` contract is rejected, not executed.

Verification split
------------------
* The repository split validator (``validate_tim_evaluation_split.py``) is used
  only for structural validity and, in final-held-out mode, the
  ``--require-final-ready`` release gate (final_ready = 3/3). ``--verify-hashes``
  is deliberately NOT delegated to it: that path also fires on non-behavioural
  documentation edits under a frozen directory.
* Every frozen identity this runner depends on is verified by the runner
  itself, before any architecture execution: :func:`verify_frozen_git_paths`
  (behaviour-bearing frozen source), :func:`verify_contract_files` (path /
  size / SHA-256 of every file the comparison contract records) and
  :func:`verify_sequence_inputs` (per-sequence physical-v2 reference SHA-256,
  the development common-input MCAP SHA-256, and — for a final-held-out
  sequence — the frozen ``source_files`` path / size / SHA-256 records).

Scientific safety rules
-----------------------
* Development-check mode may use only frozen development inputs.
* Final-held-out mode fails closed unless the split passes the structural +
  ``--require-final-ready`` gate AND every held-out entry status is ``ready``
  AND every frozen source-file record for the selected sequences verifies.
* H01/H02/H03 source bags are the already-frozen common detector evidence:
  capture records /camera/image_raw + /detections once with YOLOv8s while
  tracker, TIM-MARS and control are disabled. Detector inference is not rerun.
* All ByteTrack-derived primary architectures consume one canonical ByteTrack
  candidate stream per sequence.
* DeepSORT is generated independently from the same source image/detection
  stream.
* Bootstrap is resolved only at the predetermined initial instant
  (max bootstrap lag = one tracker frame). Failure is retained as a result;
  bootstrap time is never moved using later architecture performance.
* Every MARS/TensorFlow replay subprocess runs under the Stage-7 pinned
  numerical environment
  (docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh),
  passed explicitly per subprocess; the orchestrator's own environment is
  never mutated.
* Frozen algorithms, models, tracker settings, TIM-MARS settings and physical-v2
  evaluation rules are never modified by this orchestrator.

Frozen-path guard
-----------------
The comparison contract's ``source_code_freeze.change_rule`` freezes
*behaviour-affecting* change, not documentation prose. The guard therefore
enumerates the tracked, non-documentation files under the frozen paths as of
the algorithm-authority commit and blocks if any of those changed since, or if
a new non-documentation file was added under a frozen path. Documentation-only
files (``README``/``LICENSE``/``*.md``/``*.rst``/``*.txt``) are exempt so
repository-structure cleanup cannot trip the guard, but no behaviour-bearing
file type is silently exempted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Active Stage-7 prospective-freeze authorities -----------------------------
ACTIVE_CONTRACT_ID = "tim_mars_final_comparison_v3_2026_09_08"
ACTIVE_SPLIT_ID = "tim_mars_split_v4_2026_09_08"
ACTIVE_ALGORITHM_FREEZE_COMMIT = (
    "79f11b631688889bf5ffbeb3c16ef543a53f9973"
)
ACTIVE_CANONICAL_TIM_CONFIG_SHA256 = (
    "b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c"
)
SUPERSEDED_CONTRACT_IDS = frozenset({"tim_mars_final_comparison_v2_2026_09_05"})

DEFAULT_CONTRACT = (
    REPO_ROOT / "docs/data/splits/tim_mars_final_comparison_v3.json"
)
DEFAULT_SPLIT = REPO_ROOT / "docs/data/splits/tim_mars_split_v4.json"
DEV_MANIFEST = (
    REPO_ROOT
    / "docs/data/tracker_sensitivity/bytetrack_tim_sensitivity_v1.yaml"
)

PINNED_REPLAY_ENV_SCRIPT = (
    REPO_ROOT
    / "docs/results/selected_target_tracking"
    / "tim_pinned_replay_env_20260908.sh"
)

# Documentation-only files may change under a frozen directory without a new
# prospective freeze: the contract freezes behaviour, not prose. Every other
# tracked file type under a frozen path is treated as behaviour-bearing.
_DOC_ONLY_SUFFIXES = frozenset({".md", ".rst", ".txt"})
_DOC_ONLY_STEMS = frozenset(
    {"README", "LICENSE", "LICENCE", "NOTICE", "CHANGELOG", "AUTHORS"}
)

SPLIT_VALIDATOR = (
    REPO_ROOT / "tools/analysis/validate_tim_evaluation_split.py"
)
TRACKER_REPLAY = (
    REPO_ROOT / "tools/experiments/run_deterministic_tracker_replay.py"
)
TIM_REPLAY = (
    REPO_ROOT / "tools/experiments/run_deterministic_tim_replay.py"
)
TARGET_REID_REPLAY = (
    REPO_ROOT / "tools/experiments/run_p058_target_reid_replay.py"
)
BOOTSTRAP_RESOLVER = (
    REPO_ROOT / "tools/analysis/resolve_bootstrap_target.py"
)
PHYSICAL_V2_EVAL = (
    REPO_ROOT / "tools/analysis/evaluate_physical_target_bbox_v2.py"
)

ARCHITECTURE_ORDER = (
    "bytetrack_raw",
    "target_reid_090",
    "bytetrack_tim_mars",
    "deepsort_raw",
)

# P027_HELDOUT_CAPTURE_RUNBOOK: held-out H01-H03 source is recorded at
# 640x480, YOLOv8s detector evidence frozen, control/tracker/TIM disabled.
HELDOUT_SOURCE_IMAGE_WIDTH = 640
HELDOUT_SOURCE_IMAGE_HEIGHT = 480

DEFAULT_DEV_SEQUENCE_IDS = (
    "dev_june_seq03",
    "dev_june_seq04",
)

PRIMARY_BUCKETS = (
    "correct_target_output_duration_s",
    "wrong_person_output_duration_s",
    "identity_unresolved_duration_s",
    "lost_or_suppressed_duration_s",
)

ADDITIONAL_BUCKETS = (
    "target_absent_duration_s",
    "target_absent_with_output_duration_s",
    "reference_unavailable_duration_s",
    "reference_gap_duration_s",
)

ALL_BUCKETS = PRIMARY_BUCKETS + ADDITIONAL_BUCKETS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def architecture_map(
    contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    architectures = contract.get("primary_architectures")
    if not isinstance(architectures, list):
        raise ValueError("primary_architectures must be a list")

    ids = [str(a.get("id")) for a in architectures]
    if tuple(ids) != ARCHITECTURE_ORDER:
        raise ValueError(
            "primary architecture order mismatch: "
            f"{ids!r} != {list(ARCHITECTURE_ORDER)!r}"
        )

    return {
        str(architecture["id"]): architecture
        for architecture in architectures
    }


def contract_file_records(
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    records.append(contract["common_detector"]["model"])
    records.append(contract["common_appearance_model"]["model"])

    for architecture in contract["primary_architectures"]:
        tracker = architecture.get("tracker")
        if isinstance(tracker, dict):
            config = tracker.get("config")
            if isinstance(config, dict):
                records.append(config)

        candidate_tracker = architecture.get("candidate_tracker")
        if isinstance(candidate_tracker, dict):
            config = candidate_tracker.get("config")
            if isinstance(config, dict):
                records.append(config)

        implementation = architecture.get("implementation")
        if isinstance(implementation, list):
            records.extend(
                record
                for record in implementation
                if isinstance(record, dict)
            )

        tim = architecture.get("tim_mars")
        if isinstance(tim, dict):
            config = tim.get("config")
            if isinstance(config, dict):
                records.append(config)

    records.extend(
        contract["physical_reference_and_evaluation"]["files"]
    )

    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        deduped[str(record["path"])] = record
    return list(deduped.values())


def verify_frozen_file_records(
    records: Iterable[dict[str, Any]],
    *,
    context: str,
) -> dict[str, str]:
    """Verify a list of frozen ``{path, size_bytes, sha256}`` records.

    For each record: resolve the repository-relative ``path``, require the
    file to exist, require its current byte size to equal ``size_bytes`` and
    its SHA-256 to equal ``sha256``. Fail closed (``SystemExit``) on any
    mismatch. Returns ``{path: verified_sha256}``.
    """
    verified: dict[str, str] = {}

    for record in records:
        rel = str(record["path"])
        path = REPO_ROOT / rel
        if not path.is_file():
            raise SystemExit(f"{context}: frozen file missing: {rel}")

        expected_size = int(record["size_bytes"])
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise SystemExit(
                f"{context}: frozen file size mismatch: {rel} "
                f"{actual_size} != {expected_size}"
            )

        actual_hash = sha256_file(path)
        expected_hash = str(record["sha256"])
        if actual_hash != expected_hash:
            raise SystemExit(
                f"{context}: frozen file SHA-256 mismatch: {rel}"
            )

        verified[rel] = actual_hash

    return verified


def verify_contract_files(
    contract: dict[str, Any],
) -> dict[str, str]:
    return verify_frozen_file_records(
        contract_file_records(contract),
        context="comparison contract",
    )


def _is_documentation_only(path_str: str) -> bool:
    """Return whether a repo-relative path is a documentation-only file.

    The comparison contract freezes behaviour, not README/manual prose, so
    these files may change under a frozen directory without a new prospective
    freeze. Everything else is treated as behaviour-bearing.
    """
    posix = PurePosixPath(path_str)
    if posix.suffix.lower() in _DOC_ONLY_SUFFIXES:
        return True
    if posix.suffix == "" and posix.stem in _DOC_ONLY_STEMS:
        return True
    return False


def behaviour_bearing_frozen_files(
    freeze_commit: str,
    required_unchanged_paths: list[str],
) -> list[str]:
    """Every tracked, non-documentation file under the frozen paths.

    The set is derived from ``git ls-tree`` at the algorithm-authority commit
    (directory entries in ``required_unchanged_paths`` are expanded; explicit
    file entries are kept), then documentation-only files are removed.
    """
    listed = subprocess.run(
        [
            "git", "-C", str(REPO_ROOT),
            "ls-tree", "-r", "--name-only", freeze_commit,
            "--", *required_unchanged_paths,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    return sorted(
        path
        for path in listed
        if not _is_documentation_only(path)
    )


def frozen_guard_violations(
    *,
    changed_behaviour_files: list[str],
    added_paths: list[str],
    working_tree_status: str,
) -> list[str]:
    """Pure classification of frozen-path guard inputs.

    ``changed_behaviour_files`` is already restricted to behaviour-bearing
    files (see :func:`behaviour_bearing_frozen_files`); any entry is a
    violation. ``added_paths`` may contain documentation; only
    non-documentation additions are violations. Any working-tree
    modification of a frozen path is a violation, documentation included,
    as a defensive check against an in-progress edit.
    """
    violations: list[str] = []
    for path in sorted(changed_behaviour_files):
        violations.append(
            f"behaviour-bearing frozen file changed: {path}"
        )
    for path in sorted(added_paths):
        if not _is_documentation_only(path):
            violations.append(
                f"behaviour-bearing file added under a frozen path: {path}"
            )
    if working_tree_status.strip():
        violations.append(
            "working tree modifies a frozen path:\n"
            + working_tree_status.strip()
        )
    return violations


def _git_lines(*args: str) -> list[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.split()


def verify_frozen_git_paths(
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Enforce the behaviour-affecting freeze contract deterministically.

    Blocks when: (1) any behaviour-bearing tracked file under the frozen
    paths changed since the algorithm-authority commit; (2) a new
    non-documentation file was added under a frozen path since that commit;
    (3) the working tree modifies any frozen path at all. Documentation-only
    changes under a frozen directory (README/LICENSE/*.md/*.rst/*.txt) do
    not trip the guard, matching the contract's "behavior-affecting change"
    rule; no behaviour-bearing file type is exempted.
    """
    freeze = contract["source_code_freeze"]
    freeze_commit = str(freeze["commit"])
    required_paths = [str(p) for p in freeze["required_unchanged_paths"]]

    behaviour_files = behaviour_bearing_frozen_files(
        freeze_commit, required_paths
    )
    if not behaviour_files:
        raise SystemExit(
            "no behaviour-bearing frozen file resolved from "
            f"{freeze_commit}; refusing to run"
        )

    changed_behaviour = _git_lines(
        "diff", "--name-only", freeze_commit, "HEAD",
        "--", *behaviour_files,
    )
    added_paths = _git_lines(
        "diff", "--name-only", "--diff-filter=A",
        freeze_commit, "HEAD", "--", *required_paths,
    )
    working_status = subprocess.run(
        [
            "git", "-C", str(REPO_ROOT),
            "status", "--porcelain", "--", *required_paths,
        ],
        check=False,
        capture_output=True,
        text=True,
    ).stdout

    violations = frozen_guard_violations(
        changed_behaviour_files=changed_behaviour,
        added_paths=added_paths,
        working_tree_status=working_status,
    )
    if violations:
        raise SystemExit(
            "frozen-path guard blocked execution "
            f"(algorithm authority {freeze_commit}):\n"
            + "\n".join(violations)
            + "\nA new explicitly versioned prospective freeze is "
            "required for any behaviour-affecting change."
        )

    return {
        "algorithm_authority_commit": freeze_commit,
        "behaviour_bearing_frozen_file_count": len(behaviour_files),
        "documentation_only_exemption": {
            "stems": sorted(_DOC_ONLY_STEMS),
            "suffixes": sorted(_DOC_ONLY_SUFFIXES),
        },
    }


def validate_contract(
    contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Validate the supplied contract against the active Stage-7 freeze.

    The supplied ``--contract`` is authoritative: it is never swapped for a
    default. It is, however, rejected unless it is the active Stage-7 final
    comparison contract, so a superseded contract cannot be executed as the
    final held-out comparison.
    """
    contract_id = contract.get("contract_id")
    if contract_id in SUPERSEDED_CONTRACT_IDS:
        raise SystemExit(
            f"contract {contract_id!r} is superseded by the Stage-7 freeze "
            f"{ACTIVE_CONTRACT_ID!r}; it must not run as the final held-out "
            "comparison."
        )
    if contract_id != ACTIVE_CONTRACT_ID:
        raise SystemExit(
            f"contract {contract_id!r} is not the active Stage-7 final "
            f"comparison contract {ACTIVE_CONTRACT_ID!r}."
        )

    if str(contract.get("algorithm_freeze_commit")) != (
        ACTIVE_ALGORITHM_FREEZE_COMMIT
    ):
        raise SystemExit(
            "contract algorithm_freeze_commit "
            f"{contract.get('algorithm_freeze_commit')!r} != Stage-7 "
            f"authority {ACTIVE_ALGORITHM_FREEZE_COMMIT!r}"
        )
    if str(
        contract.get("source_code_freeze", {}).get("commit")
    ) != ACTIVE_ALGORITHM_FREEZE_COMMIT:
        raise SystemExit(
            "contract source_code_freeze.commit != Stage-7 authority "
            f"{ACTIVE_ALGORITHM_FREEZE_COMMIT!r}"
        )
    if str(
        contract.get("held_out_split", {}).get("split_id")
    ) != ACTIVE_SPLIT_ID:
        raise SystemExit(
            "contract held_out_split.split_id != active split "
            f"{ACTIVE_SPLIT_ID!r}"
        )

    architectures = architecture_map(contract)

    target_reid = architectures["target_reid_090"]
    if float(target_reid["threshold"]) != 0.90:
        raise ValueError("Target-ReID threshold must remain 0.90")

    tim = architectures["bytetrack_tim_mars"]["tim_mars"]
    if tim.get("appearance_request_policy") != "all_candidates":
        raise ValueError(
            "canonical TIM-MARS appearance policy must be all_candidates"
        )

    # The authoritative canonical TIM-MARS configuration hash lives in the
    # contract itself. Assert it equals the Stage-7 authority here;
    # verify_contract_files() then enforces it byte-for-byte against the
    # live working tree.
    recorded_tim_sha = str(tim.get("config", {}).get("sha256"))
    if recorded_tim_sha != ACTIVE_CANONICAL_TIM_CONFIG_SHA256:
        raise SystemExit(
            "contract canonical TIM-MARS config sha256 "
            f"{recorded_tim_sha} != Stage-7 authority "
            f"{ACTIVE_CANONICAL_TIM_CONFIG_SHA256}"
        )

    return architectures


def run_split_validator(
    split_path: Path,
    *,
    require_final_ready: bool,
) -> None:
    """Run the repository split validator for structural validity and the
    final-ready release gate.

    ``--verify-hashes`` is intentionally NOT delegated here. That path in the
    repository validator includes a blunt ``git diff --quiet`` behaviour check
    that also fires on non-behavioural documentation edits under a frozen
    directory. This runner performs its own stronger, behaviour-aware
    verification instead: :func:`verify_frozen_git_paths` (behaviour-bearing
    frozen source), :func:`verify_contract_files` (byte-hash of every frozen
    file the contract records) and :func:`verify_sequence_inputs` (per-sequence
    bag and physical-v2 reference hashes).
    """
    command = [
        sys.executable,
        str(SPLIT_VALIDATOR),
        str(split_path),
    ]
    if require_final_ready:
        command.append("--require-final-ready")

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        if require_final_ready:
            raise SystemExit(
                "FINAL HELD-OUT ACCESS REFUSED: final execution requires "
                "a structurally valid split with final_ready=3/3."
            )
        raise SystemExit("active split validation failed")


def final_pending_ids(split: dict[str, Any]) -> list[str]:
    return [
        str(entry["id"])
        for entry in split["sets"]["final_held_out"]
        if entry.get("status") != "ready"
    ]


def select_ids(
    available: Iterable[str],
    requested: list[str] | None,
) -> list[str]:
    available_list = list(available)
    if not requested:
        return available_list

    unknown = sorted(set(requested) - set(available_list))
    if unknown:
        raise SystemExit(
            f"unknown sequence selection: {', '.join(unknown)}"
        )

    requested_set = set(requested)
    return [
        sequence_id
        for sequence_id in available_list
        if sequence_id in requested_set
    ]


def development_sequences(
    requested: list[str] | None,
) -> list[dict[str, Any]]:
    manifest = load_yaml(DEV_MANIFEST)
    source_sequences = manifest["development_set"]["sequences"]

    selected_by_id = {
        str(sequence["id"]): sequence
        for sequence in source_sequences
        if str(sequence["id"]) in DEFAULT_DEV_SEQUENCE_IDS
    }

    ids = select_ids(DEFAULT_DEV_SEQUENCE_IDS, requested)
    result = []

    for sequence_id in ids:
        sequence = dict(selected_by_id[sequence_id])
        split_membership = str(sequence["split_membership_id"])
        if split_membership.startswith("heldout_"):
            raise SystemExit(
                "development-check mode attempted to reference held-out data"
            )

        common = sequence["common_input"]
        reference = sequence["physical_reference"]

        result.append(
            {
                "id": sequence_id,
                "split_membership_id": split_membership,
                "source_path": str(common["path"]),
                "source_kind": str(common["kind"]),
                "source_mcap_sha256": str(common["mcap_sha256"]),
                "image_topic": str(common["image_topic"]),
                "detections_topic": str(common["detections_topic"]),
                "physical_reference": str(reference["path"]),
                "physical_reference_sha256": str(reference["sha256"]),
                "image_width": int(sequence["image_width"]),
                "image_height": int(sequence["image_height"]),
                "evidence_role": "development_check",
            }
        )

    return result


def final_sequences(
    contract: dict[str, Any],
    split: dict[str, Any],
    requested: list[str] | None,
) -> list[dict[str, Any]]:
    """Resolve the frozen held-out sequences from the v4 split schema.

    Deterministic H01/H02/H03 ordering comes from the contract's
    ``held_out_split.sequence_ids``. Each held-out entry must have status
    ``ready``; the physical-v2 reference is derived from the split's
    ``planned_physical_v2_reference_path`` (no separate hard-coded map).
    """
    ordered_ids = [
        str(sid) for sid in contract["held_out_split"]["sequence_ids"]
    ]
    by_id = {
        str(entry["id"]): entry
        for entry in split["sets"]["final_held_out"]
    }
    missing = [sid for sid in ordered_ids if sid not in by_id]
    if missing:
        raise SystemExit(
            "held-out split is missing contract sequences: "
            + ", ".join(missing)
        )

    ids = select_ids(ordered_ids, requested)
    result = []

    for sequence_id in ids:
        entry = by_id[sequence_id]
        if entry.get("status") != "ready":
            raise SystemExit(
                f"{sequence_id} status={entry.get('status')!r}; held-out "
                "execution refused until every H01-H03 sequence is 'ready'"
            )

        source_rel = str(entry["expected_source_path"])
        reference_rel = str(entry["planned_physical_v2_reference_path"])
        reference = REPO_ROOT / reference_rel
        if not reference.is_file():
            raise SystemExit(
                f"held-out physical-v2 reference missing: {reference_rel}"
            )

        result.append(
            {
                "id": sequence_id,
                "split_membership_id": sequence_id,
                "source_path": source_rel,
                "source_kind":
                    "prospective_frozen_source_detector_stream",
                "source_files": entry.get("files", []),
                "image_topic": "/camera/image_raw",
                "detections_topic": "/detections",
                "physical_reference": reference_rel,
                "physical_reference_sha256":
                    sha256_file(reference),
                "image_width": HELDOUT_SOURCE_IMAGE_WIDTH,
                "image_height": HELDOUT_SOURCE_IMAGE_HEIGHT,
                "scenario": entry.get("scenario"),
                "people_group": entry.get("people_group"),
                "clothing_group": entry.get("clothing_group"),
                "overlap_record": entry.get("overlap_record"),
                "evidence_role": "final_held_out",
            }
        )

    return result


def verify_sequence_inputs(
    sequence: dict[str, Any],
) -> None:
    source = REPO_ROOT / sequence["source_path"]
    reference = REPO_ROOT / sequence["physical_reference"]

    if not source.is_dir():
        raise SystemExit(
            f"source bag missing for {sequence['id']}: "
            f"{sequence['source_path']}"
        )
    if not reference.is_file():
        raise SystemExit(
            f"physical reference missing for {sequence['id']}: "
            f"{sequence['physical_reference']}"
        )

    actual_reference_hash = sha256_file(reference)
    if actual_reference_hash != sequence["physical_reference_sha256"]:
        raise SystemExit(
            f"physical reference hash mismatch for {sequence['id']}"
        )

    expected_mcap_hash = sequence.get("source_mcap_sha256")
    if expected_mcap_hash:
        mcaps = sorted(source.glob("*.mcap"))
        if len(mcaps) != 1:
            raise SystemExit(
                f"{sequence['id']} development common input expected "
                f"exactly one MCAP, found {len(mcaps)}"
            )
        if sha256_file(mcaps[0]) != expected_mcap_hash:
            raise SystemExit(
                f"development common-input MCAP hash mismatch for "
                f"{sequence['id']}"
            )

    # Final-held-out sequences carry the frozen source payload as explicit
    # {path, size_bytes, sha256} records copied from the v4 split. Verify
    # every one before any architecture replay so a post-freeze change to a
    # ready H01/H02/H03 source cannot pass unnoticed.
    source_files = sequence.get("source_files") or []
    if source_files:
        verify_frozen_file_records(
            source_files,
            context=(
                f"held-out source files for {sequence['id']}"
            ),
        )


def bootstrap_command(
    tracker_bag: Path,
    reference: Path,
    output_json: Path,
    max_bootstrap_lag_frames: int = 1,
) -> list[str]:
    return [
        sys.executable,
        str(BOOTSTRAP_RESOLVER),
        str(tracker_bag),
        "--physical-reference", str(reference),
        "--tracks-topic", "/tracks",
        "--min-iou", "0.5",
        "--max-bootstrap-lag-frames",
        str(max_bootstrap_lag_frames),
        "--out", str(output_json),
    ]


def bootstrap_is_at_predetermined_frame(
    bootstrap: dict[str, Any] | None,
    expected_frame_index: int,
) -> bool:
    return bool(
        bootstrap
        and bootstrap.get("ok")
        and bootstrap.get("bootstrap_frame_index")
        == expected_frame_index
    )


def load_pinned_replay_env() -> dict[str, str]:
    """Parse ``export KEY=VALUE`` lines from the Stage-7 pinned numerical
    environment script.

    The script is parsed rather than sourced so the orchestrator's own
    environment is never mutated; the pins are handed explicitly to each
    MARS/TensorFlow replay subprocess.
    """
    if not PINNED_REPLAY_ENV_SCRIPT.is_file():
        raise SystemExit(
            f"pinned replay environment script missing: "
            f"{relative(PINNED_REPLAY_ENV_SCRIPT)}"
        )
    pinned: dict[str, str] = {}
    for raw in PINNED_REPLAY_ENV_SCRIPT.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw.strip()
        if not line.startswith("export "):
            continue
        assignment = line[len("export "):].strip()
        if "=" not in assignment:
            continue
        key, _, value = assignment.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            pinned[key] = value
    if not pinned:
        raise SystemExit(
            "no pinned environment variables parsed from "
            f"{relative(PINNED_REPLAY_ENV_SCRIPT)}"
        )
    return pinned


def run_logged(
    command: list[str],
    log_path: Path,
    env: dict[str, str] | None = None,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n$ " + " ".join(command) + "\n")
        if env is not None:
            handle.write(
                "  [pinned replay env: "
                + " ".join(sorted(env)) + "]\n"
            )
        handle.flush()
        completed = subprocess.run(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
            env=(
                {**os.environ, **env}
                if env is not None
                else None
            ),
        )
    return int(completed.returncode)


def tracker_replay_command(
    *,
    sequence: dict[str, Any],
    config_path: Path,
    input_bag: Path,
    output_bag: Path,
    selected_track_id: int,
    model_path: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(TRACKER_REPLAY),
        str(input_bag),
        str(output_bag),
        "--config", str(config_path),
        "--image-topic", str(sequence["image_topic"]),
        "--detections-topic", str(sequence["detections_topic"]),
        "--selection-mode", "fixed_id",
        "--selected-track-id", str(selected_track_id),
        "--overwrite",
    ]
    if model_path is not None:
        command.extend(["--model", str(model_path)])
    return command


def tracker_digest(bag: Path) -> str | None:
    metadata = bag / "tracker_freeze_metadata.json"
    if not metadata.is_file():
        return None
    value = load_json(metadata)
    return (
        value.get("determinism", {})
        .get("generated_semantic_sha256")
    )


def bag_payload_hashes(bag: Path) -> list[dict[str, Any]]:
    result = []
    if not bag.is_dir():
        return result

    for path in sorted(bag.glob("*.mcap")):
        result.append(
            {
                "path": relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def evaluate_single_topic(
    *,
    bag: Path,
    topic: str,
    reference: Path,
    out_dir: Path,
    log_path: Path,
) -> dict[str, Any] | None:
    rc = run_logged(
        [
            sys.executable,
            str(PHYSICAL_V2_EVAL),
            str(bag),
            "--physical-reference", str(reference),
            "--out-dir", str(out_dir),
            "--raw-topic", topic,
            "--tim-topic", topic,
        ],
        log_path,
    )
    report = out_dir / "raw_target.json"
    if rc != 0 or not report.is_file():
        return None
    return load_json(report)


def evaluate_tim(
    *,
    bag: Path,
    reference: Path,
    out_dir: Path,
    log_path: Path,
) -> dict[str, Any] | None:
    rc = run_logged(
        [
            sys.executable,
            str(PHYSICAL_V2_EVAL),
            str(bag),
            "--physical-reference", str(reference),
            "--out-dir", str(out_dir),
        ],
        log_path,
    )
    report = out_dir / "tim_target_memory.json"
    if rc != 0 or not report.is_file():
        return None
    return load_json(report)


def compact_evaluation(
    report: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "duration_buckets": report["duration_buckets"],
        "coverage": report["coverage"],
        "localisation": report.get("localisation", {}),
        "reconciliation": report["reconciliation"],
    }


def architecture_cell(
    *,
    sequence_id: str,
    architecture_id: str,
    status: str,
    bootstrap: dict[str, Any] | None,
    evaluation: dict[str, Any] | None = None,
    generated_digest: str | None = None,
    payload_hashes: list[dict[str, Any]] | None = None,
    returncode: int | None = None,
    pinned_env_applied: bool = False,
) -> dict[str, Any]:
    return {
        "sequence_id": sequence_id,
        "architecture_id": architecture_id,
        "status": status,
        "bootstrap": bootstrap,
        "evaluation": compact_evaluation(evaluation),
        "generated_semantic_sha256": generated_digest,
        "payload_hashes": payload_hashes or [],
        "returncode": returncode,
        "pinned_replay_env_applied": bool(pinned_env_applied),
    }


def prune_generated_payloads(root: Path) -> list[str]:
    removed: list[str] = []
    if not root.is_dir():
        return removed
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".mcap", ".db3"}:
            removed.append(relative(path))
            path.unlink()
    return removed


def common_appearance_model_path(
    contract: dict[str, Any],
) -> Path:
    return (
        REPO_ROOT
        / contract["common_appearance_model"]["model"]["path"]
    )


def run_sequence(
    *,
    sequence: dict[str, Any],
    architectures: dict[str, dict[str, Any]],
    contract: dict[str, Any],
    output_root: Path,
    keep_bags: bool,
    pinned_env: dict[str, str],
) -> list[dict[str, Any]]:
    sequence_id = sequence["id"]
    source = REPO_ROOT / sequence["source_path"]
    reference = REPO_ROOT / sequence["physical_reference"]

    sequence_root = output_root / "sequences" / sequence_id
    bag_root = sequence_root / "generated_bags"
    eval_root = sequence_root / "evaluation"
    log_path = sequence_root / "execution.log"

    byte_config = (
        REPO_ROOT
        / architectures["bytetrack_raw"]["tracker"]["config"]["path"]
    )
    deep_config = (
        REPO_ROOT
        / architectures["deepsort_raw"]["tracker"]["config"]["path"]
    )
    mars_model = common_appearance_model_path(contract)

    cells: list[dict[str, Any]] = []

    # ---------------------------------------------------------------
    # ByteTrack bootstrap stream.
    #
    # selected-track-id=1 is only a harmless placeholder for /target.
    # /tracks generation is independent of this fixed raw-target choice.
    # The generated /target is never scored from this bootstrap bag.
    # ---------------------------------------------------------------
    byte_bootstrap_bag = bag_root / "bytetrack_bootstrap"
    rc = run_logged(
        tracker_replay_command(
            sequence=sequence,
            config_path=byte_config,
            input_bag=source,
            output_bag=byte_bootstrap_bag,
            selected_track_id=1,
        ),
        log_path,
    )

    byte_bootstrap_json = sequence_root / "bytetrack_bootstrap.json"
    byte_bootstrap: dict[str, Any] | None = None

    if rc == 0:
        bootstrap_rc = run_logged(
            bootstrap_command(
                byte_bootstrap_bag,
                reference,
                byte_bootstrap_json,
            ),
            log_path,
        )
        if byte_bootstrap_json.is_file():
            byte_bootstrap = load_json(byte_bootstrap_json)
        if bootstrap_rc not in (0, 2):
            byte_bootstrap = None

    if not byte_bootstrap or not byte_bootstrap.get("ok"):
        for architecture_id in (
            "bytetrack_raw",
            "target_reid_090",
            "bytetrack_tim_mars",
        ):
            cells.append(
                architecture_cell(
                    sequence_id=sequence_id,
                    architecture_id=architecture_id,
                    status="bootstrap_failure",
                    bootstrap=byte_bootstrap,
                    returncode=rc,
                )
            )
    else:
        selected_id = int(byte_bootstrap["resolved_track_id"])

        # One canonical fixed-ID ByteTrack candidate stream is reused by
        # ByteTrack raw, Target-ReID and TIM-MARS.
        byte_fixed_bag = bag_root / "bytetrack_fixed"
        rc = run_logged(
            tracker_replay_command(
                sequence=sequence,
                config_path=byte_config,
                input_bag=source,
                output_bag=byte_fixed_bag,
                selected_track_id=selected_id,
            ),
            log_path,
        )

        if rc != 0:
            for architecture_id in (
                "bytetrack_raw",
                "target_reid_090",
                "bytetrack_tim_mars",
            ):
                cells.append(
                    architecture_cell(
                        sequence_id=sequence_id,
                        architecture_id=architecture_id,
                        status="tracker_replay_failed",
                        bootstrap=byte_bootstrap,
                        returncode=rc,
                    )
                )
        else:
            byte_digest = tracker_digest(byte_fixed_bag)

            # ByteTrack raw.
            raw_report = evaluate_single_topic(
                bag=byte_fixed_bag,
                topic="/target",
                reference=reference,
                out_dir=eval_root / "bytetrack_raw",
                log_path=log_path,
            )
            cells.append(
                architecture_cell(
                    sequence_id=sequence_id,
                    architecture_id="bytetrack_raw",
                    status=(
                        "ok"
                        if raw_report
                        and raw_report["reconciliation"]["ok"]
                        else "evaluation_failed"
                    ),
                    bootstrap=byte_bootstrap,
                    evaluation=raw_report,
                    generated_digest=byte_digest,
                )
            )

            # Simple Target-ReID 0.90 from exactly the same ByteTrack stream.
            target_reid_bag = bag_root / "target_reid_090"
            target_reid = architectures["target_reid_090"]
            rc_target_reid = run_logged(
                [
                    sys.executable,
                    str(TARGET_REID_REPLAY),
                    str(byte_fixed_bag),
                    str(target_reid_bag),
                    "--model", str(mars_model),
                    "--selected-track-id", str(selected_id),
                    "--threshold", str(target_reid["threshold"]),
                    "--image-width", str(sequence["image_width"]),
                    "--image-height", str(sequence["image_height"]),
                    "--image-topic", str(sequence["image_topic"]),
                    "--tracks-topic", "/tracks",
                    "--max-image-age-ms",
                    str(
                        target_reid["runtime_parameters"][
                            "max_image_age_ms"
                        ]
                    ),
                ],
                log_path,
                env=pinned_env,
            )

            target_reid_hashes = (
                bag_payload_hashes(target_reid_bag)
                if rc_target_reid == 0
                else []
            )
            target_reid_report = (
                evaluate_single_topic(
                    bag=target_reid_bag,
                    topic="/target_reid",
                    reference=reference,
                    out_dir=eval_root / "target_reid_090",
                    log_path=log_path,
                )
                if rc_target_reid == 0
                else None
            )
            cells.append(
                architecture_cell(
                    sequence_id=sequence_id,
                    architecture_id="target_reid_090",
                    status=(
                        "ok"
                        if target_reid_report
                        and target_reid_report["reconciliation"]["ok"]
                        else (
                            "target_reid_replay_failed"
                            if rc_target_reid != 0
                            else "evaluation_failed"
                        )
                    ),
                    bootstrap=byte_bootstrap,
                    evaluation=target_reid_report,
                    payload_hashes=target_reid_hashes,
                    returncode=rc_target_reid,
                    pinned_env_applied=True,
                )
            )

            # Canonical TIM-MARS from exactly the same ByteTrack stream.
            tim_bag = bag_root / "bytetrack_tim_mars"
            tim_config = (
                REPO_ROOT
                / architectures["bytetrack_tim_mars"]["tim_mars"][
                    "config"
                ]["path"]
            )
            rc_tim = run_logged(
                [
                    sys.executable,
                    str(TIM_REPLAY),
                    str(byte_fixed_bag),
                    str(tim_bag),
                    "--config", str(tim_config),
                    "--model", str(mars_model),
                    "--selected-track-id", str(selected_id),
                    "--image-topic", str(sequence["image_topic"]),
                    "--tracks-topic", "/tracks",
                    "--raw-target-topic", "/target",
                    "--raw-target-mode", "source",
                    "--image-width", str(sequence["image_width"]),
                    "--image-height", str(sequence["image_height"]),
                    "--compact-output",
                    "--overwrite",
                ],
                log_path,
                env=pinned_env,
            )

            tim_report = (
                evaluate_tim(
                    bag=tim_bag,
                    reference=reference,
                    out_dir=eval_root / "bytetrack_tim_mars",
                    log_path=log_path,
                )
                if rc_tim == 0
                else None
            )
            tim_digest = None
            if rc_tim == 0:
                metadata = tim_bag / "tim_replay_metadata.json"
                if metadata.is_file():
                    tim_digest = (
                        load_json(metadata)
                        .get("determinism", {})
                        .get("generated_semantic_sha256")
                    )

            cells.append(
                architecture_cell(
                    sequence_id=sequence_id,
                    architecture_id="bytetrack_tim_mars",
                    status=(
                        "ok"
                        if tim_report
                        and tim_report["reconciliation"]["ok"]
                        else (
                            "tim_replay_failed"
                            if rc_tim != 0
                            else "evaluation_failed"
                        )
                    ),
                    bootstrap=byte_bootstrap,
                    evaluation=tim_report,
                    generated_digest=tim_digest,
                    returncode=rc_tim,
                    pinned_env_applied=True,
                )
            )

    # ---------------------------------------------------------------
    # DeepSORT: same source detector evidence, independent tracker.
    # ---------------------------------------------------------------
    deep_bootstrap_bag = bag_root / "deepsort_bootstrap"
    rc_deep_bootstrap = run_logged(
        tracker_replay_command(
            sequence=sequence,
            config_path=deep_config,
            input_bag=source,
            output_bag=deep_bootstrap_bag,
            selected_track_id=1,
            model_path=mars_model,
        ),
        log_path,
        env=pinned_env,
    )

    deep_bootstrap_json = sequence_root / "deepsort_bootstrap.json"
    deep_bootstrap: dict[str, Any] | None = None

    if rc_deep_bootstrap == 0:
        bootstrap_rc = run_logged(
            bootstrap_command(
                deep_bootstrap_bag,
                reference,
                deep_bootstrap_json,
                max_bootstrap_lag_frames=3,
            ),
            log_path,
        )
        if deep_bootstrap_json.is_file():
            deep_bootstrap = load_json(deep_bootstrap_json)
        if bootstrap_rc not in (0, 2):
            deep_bootstrap = None

    deep_bootstrap_at_predetermined_frame = (
        bootstrap_is_at_predetermined_frame(
            deep_bootstrap,
            expected_frame_index=2,
        )
    )

    if not deep_bootstrap_at_predetermined_frame:
        cells.append(
            architecture_cell(
                sequence_id=sequence_id,
                architecture_id="deepsort_raw",
                status="bootstrap_failure",
                bootstrap=deep_bootstrap,
                returncode=rc_deep_bootstrap,
                pinned_env_applied=True,
            )
        )
    else:
        selected_id = int(deep_bootstrap["resolved_track_id"])
        deep_fixed_bag = bag_root / "deepsort_fixed"

        rc_deep = run_logged(
            tracker_replay_command(
                sequence=sequence,
                config_path=deep_config,
                input_bag=source,
                output_bag=deep_fixed_bag,
                selected_track_id=selected_id,
                model_path=mars_model,
            ),
            log_path,
            env=pinned_env,
        )

        deep_report = (
            evaluate_single_topic(
                bag=deep_fixed_bag,
                topic="/target",
                reference=reference,
                out_dir=eval_root / "deepsort_raw",
                log_path=log_path,
            )
            if rc_deep == 0
            else None
        )

        cells.append(
            architecture_cell(
                sequence_id=sequence_id,
                architecture_id="deepsort_raw",
                status=(
                    "ok"
                    if deep_report
                    and deep_report["reconciliation"]["ok"]
                    else (
                        "tracker_replay_failed"
                        if rc_deep != 0
                        else "evaluation_failed"
                    )
                ),
                bootstrap=deep_bootstrap,
                evaluation=deep_report,
                generated_digest=(
                    tracker_digest(deep_fixed_bag)
                    if rc_deep == 0
                    else None
                ),
                returncode=rc_deep,
                pinned_env_applied=True,
            )
        )

    # Stable contract ordering.
    order = {
        architecture_id: index
        for index, architecture_id in enumerate(ARCHITECTURE_ORDER)
    }
    cells.sort(key=lambda cell: order[cell["architecture_id"]])

    if not keep_bags:
        removed = prune_generated_payloads(bag_root)
        write_json(sequence_root / "pruned_payloads.json", removed)

    write_json(sequence_root / "cells.json", cells)
    return cells


def bucket(
    cell: dict[str, Any],
    key: str,
) -> float | None:
    evaluation = cell.get("evaluation")
    if not isinstance(evaluation, dict):
        return None
    buckets = evaluation.get("duration_buckets")
    if not isinstance(buckets, dict):
        return None
    value = buckets.get(key)
    return float(value) if value is not None else None


def write_aggregate(
    cells: list[dict[str, Any]],
    output_root: Path,
) -> None:
    architecture_order = {
        architecture_id: index
        for index, architecture_id in enumerate(ARCHITECTURE_ORDER)
    }
    ordered = sorted(
        cells,
        key=lambda cell: (
            cell["sequence_id"],
            architecture_order[cell["architecture_id"]],
        ),
    )

    write_json(output_root / "comparison_by_architecture.json", ordered)

    rows = []
    for cell in ordered:
        row = {
            "sequence_id": cell["sequence_id"],
            "architecture_id": cell["architecture_id"],
            "status": cell["status"],
            "bootstrap_ok": (
                cell.get("bootstrap", {}).get("ok")
                if isinstance(cell.get("bootstrap"), dict)
                else None
            ),
            "bootstrap_track_id": (
                cell.get("bootstrap", {}).get("resolved_track_id")
                if isinstance(cell.get("bootstrap"), dict)
                else None
            ),
            "bootstrap_iou": (
                cell.get("bootstrap", {}).get("bootstrap_iou")
                if isinstance(cell.get("bootstrap"), dict)
                else None
            ),
        }
        for key in ALL_BUCKETS:
            row[key] = bucket(cell, key)
        rows.append(row)

    csv_path = output_root / "comparison_by_architecture.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else [
                "sequence_id",
                "architecture_id",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Issue #58 frozen architecture comparison",
        "",
        "This report is generated directly from the prospectively frozen "
        "Issue #58 architecture contract.",
        "",
        "| sequence | architecture | status | correct s | wrong s | "
        "unresolved s | LOST s | absent-with-output s |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        def fmt(value: Any) -> str:
            return "NA" if value is None else f"{float(value):.9f}"

        lines.append(
            f"| `{row['sequence_id']}` "
            f"| `{row['architecture_id']}` "
            f"| {row['status']} "
            f"| {fmt(row.get('correct_target_output_duration_s'))} "
            f"| {fmt(row.get('wrong_person_output_duration_s'))} "
            f"| {fmt(row.get('identity_unresolved_duration_s'))} "
            f"| {fmt(row.get('lost_or_suppressed_duration_s'))} "
            f"| {fmt(row.get('target_absent_with_output_duration_s'))} |"
        )

    lines.extend(
        [
            "",
            "No automatic architecture ranking or retuning decision is "
            "performed by this runner.",
            "",
        ]
    )

    (output_root / "comparison_by_architecture.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=DEFAULT_SPLIT,
    )
    parser.add_argument(
        "--set",
        choices=("development_check", "final_held_out"),
        required=True,
    )
    parser.add_argument(
        "--sequence",
        action="append",
        default=None,
    )
    parser.add_argument(
        "--run-id",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--keep-bags",
        action="store_true",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--run", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    contract_path = args.contract.resolve()
    split_path = args.split.resolve()

    contract = load_json(contract_path)
    split = load_json(split_path)

    architectures = validate_contract(contract)

    # Contract <-> split binding must be the active Stage-7 pair.
    if str(split.get("split_id")) != ACTIVE_SPLIT_ID:
        raise SystemExit(
            f"split_id {split.get('split_id')!r} != active split "
            f"{ACTIVE_SPLIT_ID!r}"
        )
    split_contract = (
        split.get("freeze", {})
        .get("final_comparison_contract", {})
        .get("contract_id")
    )
    if str(split_contract) != ACTIVE_CONTRACT_ID:
        raise SystemExit(
            "split freeze.final_comparison_contract.contract_id "
            f"{split_contract!r} != active contract {ACTIVE_CONTRACT_ID!r}"
        )

    # These checks happen before sequence planning and before any replay.
    frozen_path_guard = verify_frozen_git_paths(contract)
    verified_files = verify_contract_files(contract)
    pinned_env = load_pinned_replay_env()

    if args.set == "final_held_out":
        # Hard prospective release gate. No architecture runner outcome is
        # generated or inspected before all three held-out sequences are ready.
        run_split_validator(
            split_path,
            require_final_ready=True,
        )
        sequences = final_sequences(contract, split, args.sequence)
    else:
        run_split_validator(
            split_path,
            require_final_ready=False,
        )
        sequences = development_sequences(args.sequence)

    for sequence in sequences:
        verify_sequence_inputs(sequence)

    run_id = args.run_id or (
        "p058_final_architecture_"
        + time.strftime("%Y%m%d_%H%M%S")
    )
    output_root = (
        args.output_dir.resolve()
        if args.output_dir
        else (
            REPO_ROOT
            / "reports"
            / "p058_final_architecture_comparison"
            / run_id
        )
    )

    if output_root.exists():
        if not args.overwrite:
            raise SystemExit(
                f"output directory already exists: {output_root}"
            )
        shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)

    lock = {
        "schema_version": 1,
        "runner": relative(Path(__file__)),
        "runner_repo_commit": git_output("rev-parse", "HEAD"),
        "runner_repo_dirty": bool(
            git_output("status", "--porcelain")
        ),
        "evaluation_set": args.set,
        "contract": {
            "path": relative(contract_path),
            "sha256": sha256_file(contract_path),
            "contract_id": contract["contract_id"],
        },
        "split": {
            "path": relative(split_path),
            "sha256": sha256_file(split_path),
            "split_id": split["split_id"],
        },
        "algorithm_freeze_commit":
            contract["algorithm_freeze_commit"],
        "architecture_order": list(ARCHITECTURE_ORDER),
        "verified_frozen_files": verified_files,
        "frozen_path_guard": frozen_path_guard,
        "pinned_replay_environment": {
            "script": relative(PINNED_REPLAY_ENV_SCRIPT),
            "sha256": sha256_file(PINNED_REPLAY_ENV_SCRIPT),
            "applied_variables": {
                key: pinned_env[key] for key in sorted(pinned_env)
            },
            "applied_to_architectures": [
                "target_reid_090",
                "bytetrack_tim_mars",
                "deepsort_raw",
            ],
            "note": (
                "Parsed, not sourced; passed explicitly to every "
                "MARS/TensorFlow replay subprocess. The orchestrator "
                "environment is never mutated."
            ),
        },
        "bootstrap_rule": {
            "authority": "physical_reference_v2",
            "min_iou": 0.5,
            "predetermined_instants": {
                "bytetrack_family": {
                    "frame_index": 0,
                    "resolver_frame_budget": 1,
                },
                "deepsort_raw": {
                    "frame_index": 2,
                    "resolver_frame_budget": 3,
                    "basis":
                        "Frozen DeepSORT n_init=3; first confirmed-track "
                        "instant is frame index 2.",
                },
            },
            "failure_rule":
                "Record failure at the architecture's predetermined "
                "initial instant; never move bootstrap time using later "
                "outcomes.",
        },
        "common_detector_rule": (
            "Use the already-frozen image+detection source stream. "
            "Do not rerun detector inference before tracker fan-out."
        ),
        "sequences": sequences,
    }
    write_json(output_root / "manifest_lock.json", lock)

    print(
        f"[validated] set={args.set} "
        f"sequences={len(sequences)} "
        f"architectures={len(ARCHITECTURE_ORDER)}"
    )
    for sequence in sequences:
        print(
            f"  {sequence['id']}: "
            f"{sequence['source_path']} -> "
            f"{sequence['physical_reference']}"
        )

    if args.dry_run or args.validate_only:
        print(f"[no replay] manifest lock: {output_root}")
        return 0

    cells: list[dict[str, Any]] = []
    for index, sequence in enumerate(sequences, start=1):
        print(
            f"[sequence {index}/{len(sequences)}] "
            f"{sequence['id']}",
            flush=True,
        )
        sequence_cells = run_sequence(
            sequence=sequence,
            architectures=architectures,
            contract=contract,
            output_root=output_root,
            keep_bags=args.keep_bags,
            pinned_env=pinned_env,
        )
        cells.extend(sequence_cells)

        for cell in sequence_cells:
            print(
                f"    {cell['architecture_id']}: "
                f"{cell['status']}",
                flush=True,
            )

    write_aggregate(cells, output_root)

    provenance = {
        "schema_version": 1,
        "run_id": run_id,
        "evaluation_set": args.set,
        "repo_commit": git_output("rev-parse", "HEAD"),
        "repo_dirty": bool(git_output("status", "--porcelain")),
        "cells_total": len(cells),
        "cells_ok": sum(
            1 for cell in cells if cell["status"] == "ok"
        ),
        "cells_bootstrap_failure": sum(
            1
            for cell in cells
            if cell["status"] == "bootstrap_failure"
        ),
        "cells_other_failure": sum(
            1
            for cell in cells
            if cell["status"] not in {"ok", "bootstrap_failure"}
        ),
        "manifest_lock": "manifest_lock.json",
        "comparison_json": "comparison_by_architecture.json",
        "comparison_csv": "comparison_by_architecture.csv",
        "comparison_markdown": "comparison_by_architecture.md",
    }
    write_json(output_root / "run_provenance.json", provenance)

    print(
        f"[done] {provenance['cells_ok']}/"
        f"{provenance['cells_total']} cells ok -> "
        f"{output_root}"
    )

    return (
        0
        if provenance["cells_ok"] == provenance["cells_total"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
