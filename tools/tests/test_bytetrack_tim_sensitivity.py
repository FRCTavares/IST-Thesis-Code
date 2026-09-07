"""Tests for the frozen ByteTrack / TIM-MARS configuration sensitivity runner.

These validate the manifest and tooling *before* any physical-v2 outcome
exists: OFAT isolation, the pinned ``new_track_thresh``, canonical-hash
fail-closed behaviour, reserved held-out rejection, deterministic config
identity, and the classification/repeatability logic. None execute a replay
or require a MARS model.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "tools/experiments/run_bytetrack_tim_sensitivity.py"
AGG_PATH = REPO_ROOT / "tools/analysis/aggregate_bytetrack_tim_sensitivity.py"
MANIFEST_PATH = REPO_ROOT / "docs/data/tracker_sensitivity/bytetrack_tim_sensitivity_v1.yaml"
CANONICAL_PATH = REPO_ROOT / "ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = _load("run_bytetrack_tim_sensitivity", RUNNER_PATH)
AGG = _load("aggregate_bytetrack_tim_sensitivity", AGG_PATH)


def _manifest_and_canonical():
    manifest = RUN.load_yaml_mapping(MANIFEST_PATH)
    canonical = RUN.canonical_parameters(RUN.load_yaml_mapping(CANONICAL_PATH))
    return manifest, canonical


def _configs():
    manifest, canonical = _manifest_and_canonical()
    configs = RUN.derive_configurations(manifest, canonical)
    RUN.validate_configurations(configs, canonical)
    return manifest, canonical, configs


# -- manifest / matrix shape ------------------------------------------------


def test_manifest_declares_three_ofat_dimensions_two_perturbations_each():
    manifest, _ = _manifest_and_canonical()
    dims = manifest["dimensions"]
    assert [d["id"] for d in dims] == ["track_thresh", "match_thresh", "track_buffer"]
    for dim in dims:
        assert len(dim["perturbations"]) == 2


def test_derived_matrix_is_baseline_plus_six_candidates():
    _, _, configs = _configs()
    assert len(configs) == RUN.EXPECTED_UNIQUE_CONFIGURATIONS == 7
    assert configs[0]["id"] == RUN.BASELINE_ID
    assert [c["id"] for c in configs[1:]] == [
        "track_thresh_lower_1", "track_thresh_higher_1",
        "match_thresh_lower_1", "match_thresh_higher_1",
        "track_buffer_lower_1", "track_buffer_higher_1",
    ]


def test_config_ids_are_deterministic_across_two_derivations():
    _, _, a = _configs()
    _, _, b = _configs()
    assert [c["id"] for c in a] == [c["id"] for c in b]
    assert [c["parameters"] for c in a] == [c["parameters"] for c in b]


# -- OFAT isolation -------------------------------------------------------


def test_baseline_parameters_equal_canonical_exactly():
    _, canonical, configs = _configs()
    assert configs[0]["parameters"] == canonical


def test_each_candidate_changes_only_its_declared_override():
    _, canonical, configs = _configs()
    for config in configs[1:]:
        changed = {k for k in config["parameters"] if config["parameters"][k] != canonical[k]}
        assert changed == set(config["overrides"]), config["id"]
        assert len(changed) == 1


def test_new_track_thresh_is_pinned_to_0_6_in_every_configuration():
    _, _, configs = _configs()
    for config in configs:
        assert float(config["parameters"]["new_track_thresh"]) == RUN.PINNED_NEW_TRACK_THRESH


def test_track_thresh_candidates_do_not_move_track_birth():
    _, _, configs = _configs()
    for config in configs:
        if config["dimension_id"] == "track_thresh":
            assert float(config["parameters"]["new_track_thresh"]) == 0.6
            assert config["parameters"]["track_thresh"] in (0.4, 0.6)


def test_expected_perturbation_values():
    _, _, configs = _configs()
    values = {c["id"]: c["overrides"] for c in configs[1:]}
    assert values["track_thresh_lower_1"] == {"track_thresh": 0.40}
    assert values["track_thresh_higher_1"] == {"track_thresh": 0.60}
    assert values["match_thresh_lower_1"] == {"match_thresh": 0.70}
    assert values["match_thresh_higher_1"] == {"match_thresh": 0.90}
    assert values["track_buffer_lower_1"] == {"track_buffer": 15}
    assert values["track_buffer_higher_1"] == {"track_buffer": 45}


# -- validation fail-closed --------------------------------------------------


def test_validate_rejects_wrong_configuration_count():
    _, canonical, configs = _configs()
    with pytest.raises(ValueError):
        RUN.validate_configurations(configs[:-1], canonical)


def test_validate_rejects_baseline_with_a_changed_parameter():
    _, canonical, configs = _configs()
    broken = copy.deepcopy(configs)
    broken[0]["parameters"]["match_thresh"] = 0.7
    with pytest.raises(ValueError):
        RUN.validate_configurations(broken, canonical)


def test_validate_rejects_candidate_changing_an_undeclared_parameter():
    _, canonical, configs = _configs()
    broken = copy.deepcopy(configs)
    broken[1]["parameters"]["match_thresh"] = 0.9
    with pytest.raises(ValueError):
        RUN.validate_configurations(broken, canonical)


def test_validate_rejects_unpinned_new_track_thresh():
    _, canonical, configs = _configs()
    broken = copy.deepcopy(configs)
    broken[1]["parameters"]["new_track_thresh"] = 0.5
    with pytest.raises(ValueError):
        RUN.validate_configurations(broken, canonical)


def test_canonical_hash_mismatch_fails_closed():
    manifest = copy.deepcopy(_manifest_and_canonical()[0])
    manifest["canonical_tracker_config"]["sha256"] = "deadbeef"
    with pytest.raises(SystemExit):
        RUN.verify_canonical_hash(manifest, CANONICAL_PATH)


def test_manifest_pins_the_live_canonical_hash():
    manifest, _ = _manifest_and_canonical()
    assert RUN.verify_canonical_hash(manifest, CANONICAL_PATH) == RUN.sha256_file(CANONICAL_PATH)


# -- development-only / held-out guard ------------------------------------


def test_manifest_sequences_are_all_development_split_entries():
    manifest, _ = _manifest_and_canonical()
    split = json.loads((REPO_ROOT / manifest["development_set"]["split_authority"]).read_text())
    dev_ids = {entry["id"] for entry in split["sets"]["development"]}
    for sequence in manifest["development_set"]["sequences"]:
        assert sequence["split_membership_id"] in dev_ids


def test_selected_sequences_rejects_reserved_held_out_id():
    manifest, _ = _manifest_and_canonical()
    poisoned = copy.deepcopy(manifest)
    poisoned["development_set"]["sequences"][0]["split_membership_id"] = "heldout_h01_exit_reentry"
    with pytest.raises(SystemExit):
        RUN.selected_sequences(poisoned, None)


def test_manifest_reserved_ids_match_split_final_held_out_and_are_never_used():
    manifest, _ = _manifest_and_canonical()
    split = json.loads((REPO_ROOT / manifest["development_set"]["split_authority"]).read_text())
    held_out = {entry["id"] for entry in split["sets"]["final_held_out"]}
    reserved = set(manifest["development_set"]["reserved_held_out_ids"])
    assert reserved == held_out
    used = {
        s.get("id") for s in manifest["development_set"]["sequences"]
    } | {
        s.get("split_membership_id") for s in manifest["development_set"]["sequences"]
    }
    assert used.isdisjoint(reserved)


# -- materialization: canonical never overwritten -------------------------


def test_materialize_writes_byte_identical_baseline_and_never_touches_canonical(tmp_path):
    manifest, _ = _manifest_and_canonical()
    before = CANONICAL_PATH.read_bytes()
    lock = RUN.materialize_configurations(manifest, MANIFEST_PATH, CANONICAL_PATH, tmp_path)
    assert CANONICAL_PATH.read_bytes() == before
    baseline = next(c for c in lock["configurations"] if c["id"] == RUN.BASELINE_ID)
    assert baseline["sha256"] == RUN.sha256_file(CANONICAL_PATH)
    assert (tmp_path / "configs" / "canonical_baseline.yaml").read_bytes() == before
    assert len(lock["configurations"]) == 7


# -- classification logic -----------------------------------------------


def test_classify_flags_wrong_target_increase_as_unsafe():
    verdict, _ = AGG.classify(2.0, 0.5, -2.5, 0.0, False, True)
    assert verdict == "unsafe_regression"


def test_classify_flags_absent_with_output_increase_as_unsafe():
    verdict, _ = AGG.classify(0.0, 0.0, 0.0, 1.0, False, True)
    assert verdict == "unsafe_regression"


def test_classify_improved_requires_correct_gain_without_wrong_increase():
    verdict, _ = AGG.classify(3.0, 0.0, -3.0, 0.0, False, True)
    assert verdict == "improved"


def test_classify_regression_gate_sequence_degradation():
    verdict, _ = AGG.classify(-1.0, 0.0, 1.0, 0.0, True, True)
    assert verdict == "regressed"


def test_classify_small_change_is_neutral():
    verdict, _ = AGG.classify(0.1, 0.0, -0.1, 0.0, False, True)
    assert verdict == "neutral"


def test_classify_bootstrap_failure_is_reported():
    verdict, _ = AGG.classify(0.0, 0.0, 0.0, 0.0, False, False)
    assert verdict == "bootstrap_failure"


def test_repeatability_detects_a_digest_mismatch():
    cells = [
        {
            "sequence_id": "dev_june_seq01", "config_id": "canonical_baseline", "repeat_index": None,
            "tracker_generated_digest": "aaa", "tim_generated_digest": "bbb",
            "bootstrap": {"resolved_track_id": 1},
            "physical_v2": {"tim_target_memory": {"duration_buckets": {
                "correct_target_output_duration_s": 10.0,
                "wrong_person_output_duration_s": 0.0,
                "lost_or_suppressed_duration_s": 0.0}}},
            "tim_state_occupancy": {"state_occupancy_fraction": {"LOCKED": 1.0}},
        },
        {
            "sequence_id": "dev_june_seq01", "config_id": "canonical_baseline", "repeat_index": 1,
            "tracker_generated_digest": "aaa", "tim_generated_digest": "DIFFERENT",
            "bootstrap": {"resolved_track_id": 1},
            "physical_v2": {"tim_target_memory": {"duration_buckets": {
                "correct_target_output_duration_s": 10.0,
                "wrong_person_output_duration_s": 0.0,
                "lost_or_suppressed_duration_s": 0.0}}},
            "tim_state_occupancy": {"state_occupancy_fraction": {"LOCKED": 1.0}},
        },
    ]
    result = AGG.repeatability(cells)
    assert result["deterministic"] is False
    assert result["checks"][0]["passed"] is False


def test_repeatability_passes_on_identical_repeats():
    template = {
        "tracker_generated_digest": "aaa", "tim_generated_digest": "bbb",
        "bootstrap": {"resolved_track_id": 1},
        "physical_v2": {"tim_target_memory": {"duration_buckets": {
            "correct_target_output_duration_s": 10.0,
            "wrong_person_output_duration_s": 0.0,
            "lost_or_suppressed_duration_s": 0.0}}},
        "tim_state_occupancy": {"state_occupancy_fraction": {"LOCKED": 1.0}},
    }
    cells = [
        {**template, "sequence_id": "s", "config_id": "canonical_baseline", "repeat_index": None},
        {**template, "sequence_id": "s", "config_id": "canonical_baseline", "repeat_index": 1},
        {**template, "sequence_id": "s", "config_id": "canonical_baseline", "repeat_index": 2},
    ]
    assert AGG.repeatability(cells)["deterministic"] is True
