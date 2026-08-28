"""Contracts for synchronized TIM-MARS documentation and evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_MAP = (
    REPO_ROOT
    / "docs/data/catalogue/tim_evidence_versions.json"
)
VERSIONS_DOC = REPO_ROOT / "docs/algorithm/tim_mars_versions.md"
EVIDENCE_DOC = (
    REPO_ROOT
    / "docs/algorithm/tim_mars_evidence_versions.md"
)
CANONICAL_CONFIG = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_map() -> dict:
    return json.loads(EVIDENCE_MAP.read_text(encoding="utf-8"))


def evidence_by_id() -> dict[str, dict]:
    return {
        entry["id"]: entry
        for entry in load_map()["evidence_versions"]
    }


def test_current_runtime_hash_and_parameters_match_canonical_yaml():
    """current_runtime must describe the actual current canonical YAML."""
    evidence = load_map()
    current = evidence["current_runtime"]
    assert current["config_path"] == str(
        CANONICAL_CONFIG.relative_to(REPO_ROOT)
    )
    assert current["config_sha256"] == sha256_file(
        CANONICAL_CONFIG
    )

    document = yaml.safe_load(
        CANONICAL_CONFIG.read_text(encoding="utf-8")
    )
    parameters = document[
        "target_memory_mars_node"
    ]["ros__parameters"]
    assert evidence["active_parameters"] == {
        name: parameters[name]
        for name in evidence["active_parameters"]
    }


def test_current_runtime_is_separated_from_frozen_evidence_identity():
    """current_runtime must not carry a frozen evidence version's identity."""
    evidence = load_map()
    current = evidence["current_runtime"]

    # The old schema copied a frozen evidence version's commit/version into
    # current_runtime, which conflated "canonical now" with "what p028 was
    # evaluated with". Those keys must not come back.
    assert "last_evaluated_algorithm_commit" not in current
    assert "evidence_version" not in current

    # current_runtime references the latest frozen evidence version by id only.
    ids = {entry["id"] for entry in evidence["evidence_versions"]}
    assert current["latest_frozen_evidence_version"] in ids

    frozen = evidence_by_id()[current["latest_frozen_evidence_version"]]
    diverged = current["config_sha256"] != frozen["config_sha256"]
    assert current["differs_from_latest_frozen_evidence"] is diverged

    # When the canonical runtime has moved past the latest frozen evidence
    # version, every promotion since is recorded with a real evidence package.
    changes = current["canonical_changes_since_latest_frozen_evidence"]
    if diverged:
        assert changes
    for change in changes:
        assert change["parameters"] and change["promotion_commit"]
        assert change["claim_boundary"]
        if change["evidence_path"] is not None:
            assert (REPO_ROOT / change["evidence_path"]).is_dir()


def test_frozen_evidence_identity_is_immutable():
    """The P0.17/p028 historical fingerprint must never be silently rewritten."""
    p028 = evidence_by_id()["p028_dual_oracle_development"]
    # p028 evidence was produced with exactly this config and algorithm commit.
    # These are historical facts, not the current runtime; do not update them.
    assert (
        p028["config_sha256"]
        == "e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff"
    )
    assert (
        p028["algorithm_commit"]
        == "c5ba9d30997e47c7f555baee5257bc687698508a"
    )
    evidence_doc = EVIDENCE_DOC.read_text(encoding="utf-8")
    assert (
        "| P0.17 dual-oracle development | "
        "`c5ba9d30997e47c7f555baee5257bc687698508a` | "
        "`e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff` |"
    ) in evidence_doc


def test_every_versioned_report_exists_and_rejects_broad_claims():
    evidence = load_map()
    assert evidence["schema_version"] == 2
    entries = evidence["evidence_versions"]
    assert len(entries) == 4
    assert len({entry["id"] for entry in entries}) == len(entries)

    for entry in entries:
        assert entry["report_paths"]
        for relative_path in entry["report_paths"]:
            assert (REPO_ROOT / relative_path).is_file()
        assert entry["tracker_independent_safety_supported"] is False
        assert entry["zero_wrong_target_supported"] is False
        assert entry["final_held_out_supported"] is False


def test_frozen_config_and_commit_fingerprints_match_reports():
    entries = evidence_by_id()

    p004 = entries["p004_clean_cross_tracker"]
    p004_config = (
        REPO_ROOT
        / "reports/p004_tim_matrix_1b7dc400_2026_07_20/"
        "bytetrack/tim_mars_canonical_config.yaml"
    )
    p004_metadata = json.loads(
        (
            REPO_ROOT
            / "reports/p004_tim_matrix_1b7dc400_2026_07_20/"
            "bytetrack/tim_replay_metadata.json"
        ).read_text(encoding="utf-8")
    )
    assert p004["config_sha256"] == sha256_file(p004_config)
    assert (
        p004_metadata["repository"]["commit"]
        == p004["algorithm_commit"]
    )

    p006b = entries["p006b_hard_negative_structure"]
    p006b_root = (
        REPO_ROOT
        / "reports/p006b_hard_negative_03409564_2026_07_21"
    )
    assert (
        (p006b_root / "config.sha256")
        .read_text(encoding="utf-8")
        .split()[0]
        == p006b["config_sha256"]
    )
    assert (
        (p006b_root / "implementation_commit.txt")
        .read_text(encoding="utf-8")
        .strip()
        == p006b["algorithm_commit"]
    )

    p007 = entries["p007_rank_aware_preservation"]
    p007_root = (
        REPO_ROOT
        / "reports/p007_rank_aware_add2b8b8_2026_07_21"
    )
    assert (
        (p007_root / "config.sha256")
        .read_text(encoding="utf-8")
        .split()[0]
        == p007["config_sha256"]
    )
    assert (
        (p007_root / "implementation_commit.txt")
        .read_text(encoding="utf-8")
        .strip()
        == p007["algorithm_commit"]
    )
    assert (
        (p007_root / "base_commit.txt")
        .read_text(encoding="utf-8")
        .strip()
        == p007["replay_base_commit"]
    )


def test_current_documents_state_threshold_motion_and_claim_boundaries():
    versions = VERSIONS_DOC.read_text(encoding="utf-8")
    evidence = EVIDENCE_DOC.read_text(encoding="utf-8")
    combined = versions + evidence

    for text in (
        "`appearance_conservative_margin` | `0.05`",
        "`hard_negative_reject_margin` | `0.03`",
        "`hard_negative_confirm_observations` | `2`",
        "does **not** implement an independent velocity",
        "safety is **not\ntracker-independent**",
        "`1.300 s`",
        "`0.100 s` May distractor handover",
    ):
        assert text in combined

    assert "zero wrong-target duration" not in versions.lower()
    assert "final algorithm has three components" not in versions.lower()


def test_live_launcher_uses_canonical_params_without_threshold_copies():
    defaults = (
        REPO_ROOT / "tools/lib/live_defaults.sh"
    ).read_text(encoding="utf-8")
    launcher = (
        REPO_ROOT / "tools/start_live_stack.sh"
    ).read_text(encoding="utf-8")
    assert "tim_mars_canonical.yaml" in defaults
    assert '--params-file "$TARGET_MEMORY_MARS_CONFIG"' in launcher
    for parameter in load_map()["active_parameters"]:
        assert f"-p {parameter}:=" not in launcher
