"""Synthetic sequence-clustered inference checks for Issue #125."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues"
    / "p125"
    / "analyse_visdrone_selected_person_statistics.py"
)
SPEC = importlib.util.spec_from_file_location("p125_clustered_statistics", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def episode(sequence, key, tim_wrong, byte_wrong, tim_correct, byte_correct):
    return MODULE.PairedEpisode(
        sequence, key, tim_wrong, byte_wrong, tim_correct, byte_correct
    )


def test_cluster_aggregates_keep_all_episodes_from_each_sequence():
    records = [
        episode("a", "1", 1.0, 0.0, 0.0, 1.0),
        episode("b", "1", 0.0, 1.0, 1.0, 0.0),
        episode("a", "2", 1.0, 0.0, 0.0, 1.0),
    ]
    assert MODULE._clusters(records) == [
        ("a", 2, 2.0, -2.0),
        ("b", 1, -1.0, 1.0),
    ]
    result = MODULE.analyse(records, seed=7, bootstrap_replicates=200, sign_flip_draws=300)
    wrong = result["wrong_fraction_tim_minus_bytetrack"]
    assert wrong["episode_macro_mean"] == pytest.approx(1 / 3)
    assert wrong["cluster_bootstrap_95_percentile_ci"] == pytest.approx([-1.0, 1.0])
    assert result["correct_fraction_tim_minus_bytetrack"]["episode_macro_mean"] == pytest.approx(-1 / 3)


def test_seed_and_input_order_reproduce_exact_statistics():
    records = [
        episode("b", "1", 0.1, 0.5, 0.7, 0.3),
        episode("a", "1", 0.8, 0.3, 0.1, 0.6),
        episode("a", "2", 0.3, 0.2, 0.5, 0.4),
    ]
    first = MODULE.analyse(records, seed=99, bootstrap_replicates=100, sign_flip_draws=200)
    second = MODULE.analyse(list(reversed(records)), seed=99, bootstrap_replicates=100, sign_flip_draws=200)
    assert first == second


def test_all_zero_wrong_differences_have_p_one():
    records = [episode("a", "1", 0.2, 0.2, 0.3, 0.1)]
    result = MODULE.analyse(records, bootstrap_replicates=5, sign_flip_draws=5)
    assert result["wrong_fraction_tim_minus_bytetrack"]["two_sided_cluster_sign_flip_p_value"] == 1.0


def test_empty_duplicate_and_invalid_input_are_rejected():
    with pytest.raises(ValueError, match="at least one"):
        MODULE.analyse([])
    record = episode("a", "1", 0.2, 0.1, 0.4, 0.3)
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.analyse([record, record])
    with pytest.raises(ValueError, match="fractions"):
        episode("a", "2", 1.1, 0.0, 0.0, 0.0)
