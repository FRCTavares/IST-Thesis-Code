"""Tests for the frozen issue #28 component-ablation runner."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = (
    REPO_ROOT
    / "tools"
    / "experiments"
    / "run_tim_component_ablation.py"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "docs"
    / "data"
    / "ablations"
    / "tim_mars_component_ablation_v1.yaml"
)
CANONICAL_PATH = (
    REPO_ROOT
    / "ros2_ws"
    / "src"
    / "thesis_bringup"
    / "config"
    / "tim_mars_canonical.yaml"
)

SPEC = importlib.util.spec_from_file_location(
    "run_tim_component_ablation",
    RUNNER_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest_and_canonical():
    manifest = MODULE.load_yaml_mapping(MANIFEST_PATH)
    canonical = MODULE.canonical_parameters(
        MODULE.load_yaml_mapping(CANONICAL_PATH)
    )
    return manifest, canonical


def _durations(
    *,
    correct=5.0,
    wrong=0.0,
    lost=5.0,
    absent_output=0.0,
):
    return {
        "correct_target_duration_s": correct,
        "wrong_target_duration_s": wrong,
        "lost_target_duration_s": lost,
        "target_not_visible_duration_s": 1.0,
        "target_absent_but_output_valid_duration_s": absent_output,
        "no_target_selected_duration_s": 0.0,
        "visible_target_duration_s": 10.0,
    }


def test_manifest_matches_exact_issue_28_rows():
    manifest, canonical = _manifest_and_canonical()
    rows = MODULE.validate_manifest(manifest, canonical)

    assert tuple(row["id"] for row in rows) == (
        MODULE.REQUIRED_ROW_IDS
    )


def test_final_row_resolves_to_canonical_without_overrides():
    manifest, canonical = _manifest_and_canonical()
    resolved = dict(
        (
            row["id"],
            parameters,
        )
        for row, parameters in MODULE.resolved_tim_rows(
            manifest,
            canonical,
        )
    )

    assert resolved[MODULE.FINAL_ROW_ID] == canonical


def test_geometry_only_disables_appearance_only_id_switch_gate():
    manifest, canonical = _manifest_and_canonical()
    resolved = dict(
        (
            row["id"],
            parameters,
        )
        for row, parameters in MODULE.resolved_tim_rows(
            manifest,
            canonical,
        )
    )

    geometry = resolved["geometry_only"]
    assert geometry["appearance_enabled"] is False
    assert geometry["id_switch_min_appearance_similarity"] == 0.0
    assert geometry["hard_negative_memory_enabled"] is False
    assert geometry["short_gap_new_id_suppression_enabled"] is False


def test_manifest_rejects_unknown_override():
    manifest, canonical = _manifest_and_canonical()
    changed = deepcopy(manifest)
    changed["rows"][1]["overrides"]["not_a_real_parameter"] = True

    with pytest.raises(ValueError, match="unknown canonical overrides"):
        MODULE.validate_manifest(changed, canonical)


def test_manifest_rejects_final_override():
    manifest, canonical = _manifest_and_canonical()
    changed = deepcopy(manifest)
    changed["rows"][-1]["overrides"]["appearance_enabled"] = False

    with pytest.raises(ValueError, match="final row must not override"):
        MODULE.validate_manifest(changed, canonical)


def test_materialized_final_config_is_byte_identical(tmp_path):
    lock = MODULE.materialize_configs(
        manifest_path=MANIFEST_PATH,
        canonical_path=CANONICAL_PATH,
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    final = next(
        entry
        for entry in lock["materialized_configs"]
        if entry["row_id"] == MODULE.FINAL_ROW_ID
    )

    assert Path(final["path"]).read_bytes() == (
        CANONICAL_PATH.read_bytes()
    )


def test_pending_final_sequence_is_rejected():
    split = {
        "sets": {
            "final_held_out": [
                {
                    "id": "h01",
                    "status": "reserved_pending_capture",
                }
            ]
        }
    }

    with pytest.raises(ValueError, match="sequence is not ready"):
        MODULE.split_sequences(
            split,
            set_name="final_held_out",
            requested_ids=set(),
        )


def test_wrong_target_increase_fails_row_safety():
    raw = _durations(wrong=0.0)
    row = MODULE.metrics_row(
        sequence_id="seq",
        row_id=MODULE.FINAL_ROW_ID,
        label="Final",
        stream=_durations(wrong=0.10, lost=4.90),
        raw=raw,
        wrong_tolerance_s=0.05,
    )

    assert row["safe_vs_raw"] is False
    assert row["wrong_delta_vs_raw_s"] == pytest.approx(0.10)


def test_annotated_id_increase_blocks_spatially_optimistic_row():
    raw = _durations(wrong=0.0)
    row = MODULE.metrics_row(
        sequence_id="seq",
        row_id=MODULE.FINAL_ROW_ID,
        label="Final",
        stream=_durations(wrong=0.0),
        raw=raw,
        id_stream=_durations(wrong=0.95),
        id_raw=_durations(wrong=0.10),
        wrong_tolerance_s=0.05,
    )

    assert row["safe_vs_raw"] is False
    assert row["spatial_oracle_safe_vs_raw"] is True
    assert row["annotated_id_oracle_safe_vs_raw"] is False
    assert row["wrong_target_duration_s"] == 0.0
    assert row[
        "annotated_id_wrong_target_duration_s"
    ] == pytest.approx(0.95)
    assert row[
        "annotated_id_wrong_delta_vs_raw_s"
    ] == pytest.approx(0.85)
    assert row["zero_wrong_target_claim_supported"] is False


def test_zero_wrong_claim_requires_both_oracles_to_be_zero():
    raw = _durations(wrong=1.0)
    row = MODULE.metrics_row(
        sequence_id="may",
        row_id=MODULE.FINAL_ROW_ID,
        label="Final",
        stream=_durations(wrong=0.0),
        raw=raw,
        id_stream=_durations(wrong=0.10),
        id_raw=_durations(wrong=2.0),
        wrong_tolerance_s=0.05,
    )

    assert row["safe_vs_raw"] is True
    assert row["wrong_target_duration_s"] == 0.0
    assert row[
        "annotated_id_wrong_target_duration_s"
    ] == pytest.approx(0.10)
    assert row["wrong_oracle_disagreement_s"] == pytest.approx(0.10)
    assert row["zero_wrong_target_claim_supported"] is False


def test_aggregate_uses_duration_weighted_ratios():
    rows = []
    for sequence_id in ("a", "b"):
        raw = _durations(correct=4.0, wrong=0.0, lost=6.0)
        for row_id in MODULE.REQUIRED_ROW_IDS:
            stream = (
                raw
                if row_id == "raw_tracker"
                else _durations(
                    correct=8.0,
                    wrong=0.0,
                    lost=2.0,
                )
            )
            rows.append(
                MODULE.metrics_row(
                    sequence_id=sequence_id,
                    row_id=row_id,
                    label=row_id,
                    stream=stream,
                    raw=raw,
                    wrong_tolerance_s=0.05,
                )
            )

    aggregate = MODULE.aggregate_rows(
        rows,
        wrong_tolerance_s=0.05,
    )
    final = next(
        row
        for row in aggregate
        if row["row_id"] == MODULE.FINAL_ROW_ID
    )

    assert final["correct_target_duration_s"] == 16.0
    assert final["visible_target_duration_s"] == 20.0
    assert final["correct_target_ratio"] == pytest.approx(0.8)
