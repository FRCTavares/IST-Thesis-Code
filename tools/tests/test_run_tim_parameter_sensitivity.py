"""Tests for the frozen issue #31 parameter-sensitivity sweep runner.

These tests validate the manifest/tooling *before* any TIM replay outcome
exists: they check determinism, OFAT isolation, the acceptance-pair gap,
canonical-hash fail-closed behaviour, split-membership provenance, and cell
accounting. None of them execute TIM-MARS or require a MARS model.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = (
    REPO_ROOT / "tools" / "experiments" / "run_tim_parameter_sensitivity.py"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "docs"
    / "data"
    / "parameter_sensitivity"
    / "tim_mars_parameter_sensitivity_v1.yaml"
)
CANONICAL_PATH = (
    REPO_ROOT
    / "ros2_ws"
    / "src"
    / "thesis_bringup"
    / "config"
    / "tim_mars_canonical.yaml"
)
SPLIT_PATH = REPO_ROOT / "docs" / "data" / "splits" / "tim_mars_split_v1.json"

SPEC = importlib.util.spec_from_file_location(
    "run_tim_parameter_sensitivity",
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


def _configurations():
    manifest, canonical = _manifest_and_canonical()
    configs = MODULE.derive_configurations(manifest, canonical)
    MODULE.validate_configurations(configs, canonical)
    return manifest, canonical, configs


# --------------------------------------------------------------------------
# 1. Manifest structure sanity
# --------------------------------------------------------------------------


def test_manifest_schema_is_valid():
    manifest, _ = _manifest_and_canonical()
    MODULE.validate_manifest_schema(manifest)


def test_manifest_pins_the_live_canonical_hash():
    manifest, _ = _manifest_and_canonical()
    assert (
        manifest["canonical_config"]["sha256"]
        == MODULE.sha256_file(CANONICAL_PATH)
    )


def test_raw_target_mode_is_source():
    manifest, _ = _manifest_and_canonical()
    assert manifest["raw_target_mode"] == "source"


# --------------------------------------------------------------------------
# 2/3. Baseline uniqueness and total configuration count
# --------------------------------------------------------------------------


def test_exactly_29_unique_configurations_with_one_baseline():
    _, _, configs = _configurations()
    assert len(configs) == MODULE.EXPECTED_CONFIGURATIONS == 29
    ids = [c["id"] for c in configs]
    assert len(set(ids)) == len(ids)
    baseline = [c for c in configs if c["id"] == MODULE.BASELINE_ID]
    assert len(baseline) == 1
    assert baseline[0]["overrides"] == {}


def test_seven_dimensions_four_perturbations_each():
    manifest, _ = _manifest_and_canonical()
    dimensions = manifest["dimensions"]
    assert len(dimensions) == 7
    for dimension in dimensions:
        assert len(dimension["perturbations"]) == 4


# --------------------------------------------------------------------------
# 4. 116 config x sequence cell accounting
# --------------------------------------------------------------------------


def test_expected_116_cells():
    _, _, configs = _configurations()
    manifest, _ = _manifest_and_canonical()
    sequences = MODULE.development_sequences(manifest)
    assert len(sequences) == 4
    cells = MODULE.expected_cells(configs, sequences)
    assert len(cells) == 29 * 4 == 116 == MODULE.EXPECTED_RUNS


# --------------------------------------------------------------------------
# 1 & 11. Determinism of derived configurations and their ordering
# --------------------------------------------------------------------------


def test_derivation_is_deterministic_across_repeated_calls():
    manifest, canonical = _manifest_and_canonical()
    first = MODULE.derive_configurations(manifest, canonical)
    second = MODULE.derive_configurations(manifest, canonical)
    assert first == second
    assert [c["id"] for c in first] == [c["id"] for c in second]


def test_configuration_order_is_stable_and_baseline_first():
    _, _, configs = _configurations()
    orders = [c["order"] for c in configs]
    assert orders == sorted(orders)
    assert configs[0]["id"] == MODULE.BASELINE_ID
    assert orders[0] == 0


# --------------------------------------------------------------------------
# 5. Each perturbation changes only its own conceptual dimension
# --------------------------------------------------------------------------


def test_each_perturbation_touches_only_its_declared_dimension():
    manifest, canonical, configs = _configurations()
    dimensions_by_id = {d["id"]: d for d in manifest["dimensions"]}
    for config in configs:
        if config["id"] == MODULE.BASELINE_ID:
            continue
        dimension = dimensions_by_id[config["dimension_id"]]
        expected_keys = set(dimension["parameters"])
        diff_keys = {
            key
            for key, value in config["parameters"].items()
            if value != canonical.get(key)
        }
        assert diff_keys == expected_keys == set(config["overrides"])


def test_dimensions_do_not_share_parameters():
    manifest, _ = _manifest_and_canonical()
    seen: dict[str, str] = {}
    for dimension in manifest["dimensions"]:
        for parameter in dimension["parameters"]:
            assert parameter not in seen, (
                f"{parameter} claimed by both {seen.get(parameter)} and "
                f"{dimension['id']}"
            )
            seen[parameter] = dimension["id"]


# --------------------------------------------------------------------------
# 6. Acceptance-pair gap
# --------------------------------------------------------------------------


def test_acceptance_pair_always_preserves_point_zero_eight_gap():
    _, _, configs = _configurations()
    acceptance_configs = [
        c for c in configs if c["dimension_id"] == "acceptance_pair"
    ]
    assert len(acceptance_configs) == 4
    for config in acceptance_configs:
        locked = config["parameters"]["accept_score_locked"]
        lost = config["parameters"]["accept_score_lost"]
        assert round(lost - locked, 10) == MODULE.ACCEPTANCE_PAIR_GAP


def test_acceptance_pair_gap_violation_is_rejected():
    _, canonical, configs = _configurations()
    broken = copy.deepcopy(configs)
    target = next(c for c in broken if c["id"] == "acceptance_pair_lower_2")
    target["parameters"]["accept_score_lost"] = 0.90  # breaks the 0.08 gap
    with pytest.raises(ValueError, match="LOST-LOCKED gap"):
        MODULE.validate_configurations(broken, canonical)


# --------------------------------------------------------------------------
# 7. Canonical YAML is never modified
# --------------------------------------------------------------------------


def test_materialize_never_modifies_canonical_yaml(tmp_path):
    before = CANONICAL_PATH.read_bytes()
    MODULE.materialize_configurations(
        manifest_path=MANIFEST_PATH,
        canonical_path=CANONICAL_PATH,
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    after = CANONICAL_PATH.read_bytes()
    assert before == after


def test_baseline_materialized_config_is_byte_identical_to_canonical(
    tmp_path,
):
    lock = MODULE.materialize_configurations(
        manifest_path=MANIFEST_PATH,
        canonical_path=CANONICAL_PATH,
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    baseline_entry = next(
        e
        for e in lock["materialized_configs"]
        if e["id"] == MODULE.BASELINE_ID
    )
    assert baseline_entry["sha256"] == MODULE.sha256_file(CANONICAL_PATH)


# --------------------------------------------------------------------------
# 8. Canonical hash verification fails safely on mismatch
# --------------------------------------------------------------------------


def test_canonical_hash_mismatch_fails_closed(tmp_path):
    manifest = copy.deepcopy(MODULE.load_yaml_mapping(MANIFEST_PATH))
    manifest["canonical_config"]["sha256"] = "0" * 64
    with pytest.raises(MODULE.CanonicalHashMismatch):
        MODULE.verify_canonical_hash(manifest, CANONICAL_PATH)


def test_canonical_hash_matches_verifies_cleanly():
    manifest, _ = _manifest_and_canonical()
    digest = MODULE.verify_canonical_hash(manifest, CANONICAL_PATH)
    assert digest == manifest["canonical_config"]["sha256"]


# --------------------------------------------------------------------------
# 9. No legacy_validation / final_held_out sequence enters the matrix
# --------------------------------------------------------------------------


def test_no_forbidden_split_set_enters_the_matrix():
    manifest, _ = _manifest_and_canonical()
    sequences = MODULE.development_sequences(manifest)
    for sequence in sequences:
        for forbidden in MODULE.FORBIDDEN_SPLIT_SETS:
            assert forbidden not in sequence["split_membership_id"]


def test_split_membership_cross_check_passes_against_frozen_split():
    manifest, _ = _manifest_and_canonical()
    split = MODULE.load_json_mapping(SPLIT_PATH)
    MODULE.verify_split_membership(manifest, split)


def test_split_membership_rejects_legacy_validation_reference():
    manifest = copy.deepcopy(MODULE.load_yaml_mapping(MANIFEST_PATH))
    split = MODULE.load_json_mapping(SPLIT_PATH)
    manifest["development_set"]["sequences"][0]["split_membership_id"] = (
        "legacy_june_seq02"
    )
    with pytest.raises(ValueError, match="forbidden split set"):
        MODULE.verify_split_membership(manifest, split)


# --------------------------------------------------------------------------
# 10. Seq03/Seq04 corrected ByteTrack mapping is explicit
# --------------------------------------------------------------------------


def test_seq03_seq04_use_corrected_bytetrack_provenance():
    manifest, _ = _manifest_and_canonical()
    by_id = {
        s["id"]: s for s in MODULE.development_sequences(manifest)
    }
    for sequence_id in ("dev_june_seq03", "dev_june_seq04"):
        sequence = by_id[sequence_id]
        assert sequence["tracker"] == "bytetrack"
        assert sequence["provenance"] == "corrected_bytetrack_issue_30_slice_15"
        assert "_ocsort" in sequence["split_membership_id"]
        assert sequence["stale_split_reference"]["tracker"] == "ocsort"
        assert "issue_30_evidence" in sequence

    for sequence_id in ("dev_may_hard_reentry", "dev_june_seq01"):
        sequence = by_id[sequence_id]
        assert sequence["provenance"] == "unchanged_from_split"


def test_all_four_development_sequences_present():
    manifest, _ = _manifest_and_canonical()
    ids = {s["id"] for s in MODULE.development_sequences(manifest)}
    assert ids == {
        "dev_may_hard_reentry",
        "dev_june_seq01",
        "dev_june_seq03",
        "dev_june_seq04",
    }


# --------------------------------------------------------------------------
# 12. Invalid ranges/combinations are rejected
# --------------------------------------------------------------------------


def test_perturbation_equal_to_canonical_is_rejected():
    manifest = copy.deepcopy(MODULE.load_yaml_mapping(MANIFEST_PATH))
    dimension = next(
        d for d in manifest["dimensions"] if d["id"] == "ambiguity_margin"
    )
    dimension["perturbations"][0]["values"]["ambiguity_margin"] = (
        dimension["canonical_values"]["ambiguity_margin"]
    )
    with pytest.raises(ValueError, match="does not perturb"):
        MODULE.validate_manifest_schema(manifest)


def test_configuration_touching_extra_parameter_is_rejected():
    _, canonical, configs = _configurations()
    broken = copy.deepcopy(configs)
    target = next(c for c in broken if c["id"] == "ambiguity_margin_lower_2")
    target["parameters"]["accept_score_locked"] = 0.10
    with pytest.raises(ValueError, match="changes parameters beyond"):
        MODULE.validate_configurations(broken, canonical)


def test_negative_confirmation_time_is_rejected():
    _, canonical, configs = _configurations()
    broken = copy.deepcopy(configs)
    target = next(c for c in broken if c["id"] == "confirmation_time_lower_1")
    target["parameters"]["min_confirm_frames_after_reacquire"] = -1
    target["overrides"]["min_confirm_frames_after_reacquire"] = -1
    with pytest.raises(ValueError, match="negative confirmation-time"):
        MODULE.validate_configurations(broken, canonical)


def test_wrong_configuration_count_is_rejected():
    _, canonical, configs = _configurations()
    with pytest.raises(ValueError, match="expected 29 configurations"):
        MODULE.validate_configurations(configs[:-1], canonical)


def test_duplicate_baseline_is_rejected():
    _, canonical, configs = _configurations()
    duplicated = configs + [copy.deepcopy(configs[0])]
    with pytest.raises(ValueError):
        MODULE.validate_configurations(duplicated, canonical)


# --------------------------------------------------------------------------
# 13. Confirmation configured/effective values
# --------------------------------------------------------------------------


def test_effective_confirmation_frames_mapping():
    assert [MODULE.effective_confirmation_frames(v) for v in range(5)] == [
        1,
        2,
        3,
        4,
        5,
    ]


def test_confirmation_time_perturbations_match_declared_effective_map():
    manifest, _ = _manifest_and_canonical()
    dimension = next(
        d for d in manifest["dimensions"] if d["id"] == "confirmation_time"
    )
    for perturbation in dimension["perturbations"]:
        configured = perturbation["values"]["min_confirm_frames_after_reacquire"]
        assert (
            MODULE.effective_confirmation_frames(configured)
            == perturbation["effective_frames"]
        )
    canonical_configured = dimension["canonical_values"][
        "min_confirm_frames_after_reacquire"
    ]
    assert MODULE.effective_confirmation_frames(canonical_configured) == 2


# --------------------------------------------------------------------------
# 14. Raw-target mode is source (manifest + CLI plumbing)
# --------------------------------------------------------------------------


def test_replay_command_always_requests_source_raw_target_mode(tmp_path):
    command = MODULE.replay_command(
        replay_script=Path("replay.py"),
        source_bag=Path("bag"),
        output_bag=tmp_path / "out",
        config_path=tmp_path / "config.yaml",
        model_path=Path("model.pb"),
        selected_target_id=1,
        image_topic="auto",
        skip_source_hash=False,
    )
    assert "--raw-target-mode" in command
    assert command[command.index("--raw-target-mode") + 1] == "source"


# --------------------------------------------------------------------------
# 15. Provenance records runtime overrides (full --dry-run over the real
#     manifest; no subprocess is ever invoked in dry-run mode)
# --------------------------------------------------------------------------


def test_dry_run_writes_provenance_with_runtime_overrides(tmp_path, monkeypatch):
    output_root = tmp_path / "bags"
    report_root = tmp_path / "reports"
    argv = [
        "run_tim_parameter_sensitivity.py",
        "--repo-root",
        str(REPO_ROOT),
        "--manifest",
        str(MANIFEST_PATH),
        "--canonical-config",
        str(CANONICAL_PATH),
        "--split",
        str(SPLIT_PATH),
        "--output-root",
        str(output_root),
        "--report-root",
        str(report_root),
        "--sequence",
        "dev_may_hard_reentry",
        "--step-s",
        "0.1",
        "--dry-run",
    ]
    monkeypatch.setattr("sys.argv", argv)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = MODULE.main()
    assert exit_code == 0

    provenance = json.loads(
        (report_root / "run_provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["raw_target_mode"] == "source"
    assert provenance["runtime"]["step_s"] == 0.1
    assert provenance["sequence_ids"] == ["dev_may_hard_reentry"]
    assert len(provenance["configuration_ids"]) == 29
    # 29 configs x 1 sequence x 2 commands (replay + evaluate) per cell.
    assert len(provenance["child_commands"]) == 29 * 2
    for command in provenance["child_commands"]:
        if "run_deterministic_tim_replay.py" in command:
            assert "--raw-target-mode source" in command


def test_print_matrix_reports_116_run_accounting(capsys):
    manifest, canonical, configs = _configurations()
    sequences = MODULE.development_sequences(manifest)
    MODULE.print_matrix(manifest, configs, sequences)
    output = capsys.readouterr().out
    assert "116 deterministic TIM" in output
    assert "baseline" in output


# --------------------------------------------------------------------------
# 16. Failed/missing cells cannot silently disappear from aggregation
# --------------------------------------------------------------------------


def test_missing_cells_block_aggregation():
    _, _, configs = _configurations()
    manifest, _ = _manifest_and_canonical()
    sequences = MODULE.development_sequences(manifest)
    expected = MODULE.expected_cells(configs, sequences)
    completed = set(list(expected)[:-1])  # one cell missing
    with pytest.raises(MODULE.MissingCellError):
        MODULE.require_no_missing_cells(expected, completed)


def test_complete_cells_do_not_block_aggregation():
    _, _, configs = _configurations()
    manifest, _ = _manifest_and_canonical()
    sequences = MODULE.development_sequences(manifest)
    expected = MODULE.expected_cells(configs, sequences)
    MODULE.require_no_missing_cells(expected, expected)


def test_raw_invariant_accepts_identical_and_rejects_drifted_stream():
    reference = {"correct_target_duration_s": "5.0", "wrong_target_duration_s": "0.0"}
    MODULE.assert_raw_invariant(
        sequence_id="dev_may_hard_reentry",
        config_id="baseline",
        current_raw=dict(reference),
        reference_raw=reference,
    )
    drifted = dict(reference)
    drifted["wrong_target_duration_s"] = "1.0"
    with pytest.raises(ValueError, match="raw/ByteTrack reference stream changed"):
        MODULE.assert_raw_invariant(
            sequence_id="dev_may_hard_reentry",
            config_id="ambiguity_margin_lower_2",
            current_raw=drifted,
            reference_raw=reference,
        )
