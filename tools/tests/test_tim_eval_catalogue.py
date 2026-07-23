"""Contracts for the canonical TIM-MARS evidence catalogue."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "tools/catalogue/build_tim_eval_catalogue.py"
CATALOGUE_PATH = ROOT / "docs/data/catalogue/tim_eval_catalogue.yaml"
NOVELTY_PATH = ROOT / "docs" / "NOVELTY.md"


def load_generator():
    """Load the catalogue generator as a Python module."""
    spec = importlib.util.spec_from_file_location(
        "build_tim_eval_catalogue",
        GENERATOR_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_catalogue():
    """Load the committed catalogue."""
    with CATALOGUE_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_committed_catalogue_matches_generator():
    """The committed catalogue must be deterministic and current."""
    generator = load_generator()
    generated = generator.build_catalogue()
    committed = load_catalogue()
    assert committed == generated


def test_final_rows_have_complete_classification_and_lineage():
    """Every promoted row must carry both classifications and full lineage."""
    catalogue = load_catalogue()
    rows = catalogue["final_rows"]

    assert len(rows) == 7

    valid_selection = {
        "autonomous",
        "annotation-driven diagnostic",
    }
    valid_replay = {
        "memory-only replay",
        "full-pipeline replay",
    }

    required_lineage = {
        "source_bag",
        "output_bag",
        "selected_track_id",
        "replay_repository_commit",
        "canonical_config_sha256",
        "mars_model_sha256",
        "replay_metadata",
        "source_manifest",
    }

    for row in rows:
        assert row["status"] == "final evidence"
        assert row["selection_provenance"] in valid_selection
        assert row["replay_scope"] in valid_replay
        assert required_lineage <= set(row["lineage"])

        assert re.fullmatch(
            r"[0-9a-f]{64}",
            row["annotation"]["sha256"],
        )
        assert re.fullmatch(
            r"[0-9a-f]{64}",
            row["report"]["sha256"],
        )
        assert re.fullmatch(
            r"[0-9a-f]{64}",
            row["evaluation"]["sha256"],
        )
        assert re.fullmatch(
            r"[0-9a-f]{40}",
            row["lineage"]["replay_repository_commit"],
        )

        assert (ROOT / row["annotation"]["path"]).is_file()
        assert (ROOT / row["report"]["path"]).is_file()
        assert (ROOT / row["evaluation"]["path"]).is_file()
        assert (
            ROOT / row["lineage"]["replay_metadata"]["path"]
        ).is_file()

        assert row["lineage"]["source_manifest"]

        if row["id"].startswith("p004_"):
            resolved_runtime = row["lineage"]["resolved_runtime"]
            assert re.fullmatch(
                r"[0-9a-f]{64}",
                resolved_runtime["sha256"],
            )
            assert re.fullmatch(
                r"[0-9a-f]{64}",
                resolved_runtime["fingerprint_sha256"],
            )
            assert (
                ROOT / resolved_runtime["path"]
            ).is_file()
            assert (
                ROOT / resolved_runtime["fingerprint_path"]
            ).is_file()
            assert (
                row["lineage"]["replay_repository_commit"]
                == "1b7dc4002c19e5235703913826e174df1025f1d0"
            )


def test_no_unproven_full_pipeline_row_is_promoted():
    """Reject unproven full-pipeline final evidence.

    Annotation compatibility must be explicit.
    """
    catalogue = load_catalogue()
    assert all(
        row["replay_scope"] == "memory-only replay"
        for row in catalogue["final_rows"]
    )
    assert catalogue["summary"]["full_pipeline_final_row_count"] == 0


def test_seq02_is_explicitly_non_final():
    """Seq02 legacy target-zero results must remain excluded."""
    catalogue = load_catalogue()
    exclusion = next(
        item
        for item in catalogue["excluded_candidates"]
        if item["id"] == "legacy_seq02_catalogue_rows"
    )

    assert exclusion["status"] == "non-final"
    assert exclusion["expected_target_ids"] == [1, 15, 23, 28, 40, 46]
    assert "target 0" in exclusion["reason"]


def test_p014_is_diagnostic_not_final():
    """P0.14 lacks the row-level lineage required for final promotion."""
    catalogue = load_catalogue()

    assert all(
        row["id"] != "p014_protected_appearance"
        for row in catalogue["final_rows"]
    )

    diagnostic = next(
        item
        for item in catalogue["diagnostic_reports"]
        if item["id"] == "p014_protected_appearance"
    )
    assert diagnostic["status"] == "diagnostic only"
    assert "does not preserve source bag" in diagnostic["reason"]


def test_legacy_valid_for_evaluation_flag_is_removed():
    """The ambiguous legacy promotion flag must not survive schema v2."""
    text = CATALOGUE_PATH.read_text(encoding="utf-8")
    assert "valid_for_evaluation" not in text
    assert "recommended_annotation" not in text


def test_novelty_tables_match_promoted_p004_reports():
    """Curated thesis-facing tables must match the promoted report rows."""
    catalogue = load_catalogue()
    novelty = NOVELTY_PATH.read_text(encoding="utf-8")

    matrix_rows = {
        row["tracker"]: row
        for row in catalogue["final_rows"]
        if row["id"].startswith("p004_matrix_")
    }

    for tracker, label in (
        ("bytetrack", "ByteTrack"),
        ("sort", "SORT"),
        ("ocsort", "OC-SORT"),
        ("deepsort", "DeepSORT"),
    ):
        row = matrix_rows[tracker]
        raw = row["result"]["raw"]
        tim = row["result"]["tim"]

        expected = (
            f"| {label} | "
            f"{raw['correct_ratio']:.3f} / "
            f"{raw['wrong_ratio']:.3f} / "
            f"{raw['lost_ratio']:.3f} | "
            f"{tim['correct_ratio']:.3f} / "
            f"{tim['wrong_ratio']:.3f} / "
            f"{tim['lost_ratio']:.3f} |"
        )
        assert expected in novelty

    sequence_rows = {
        row["sequence"]: row
        for row in catalogue["final_rows"]
        if row["id"].startswith("p004_ocsort_")
    }

    expected_seq03 = (
        "| Seq03 crossing ambiguity | "
        "0.340 / 0.001 / 0.659 | "
        "0.850 / 0.015 / 0.135 |"
    )
    expected_seq04 = (
        "| Seq04 occlusion/no-exit | "
        "0.644 / 0.002 / 0.354 | "
        "0.702 / 0.003 / 0.295 |"
    )

    assert sequence_rows["seq03"]["result"]["tim"]["correct_ratio"] == 0.85
    assert sequence_rows["seq04"]["result"]["tim"]["correct_ratio"] == 0.702
    assert expected_seq03 in novelty
    assert expected_seq04 in novelty
