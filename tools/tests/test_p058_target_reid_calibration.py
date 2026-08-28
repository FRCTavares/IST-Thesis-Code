"""Tests for the Issue #58 Target-ReID threshold selector."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "analysis"
    / "p058_target_reid_calibration.py"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "p058_target_reid_calibration",
    MODULE_PATH,
)

Row = MODULE.TargetReIdCalibrationRow


def row(
    threshold,
    *,
    correct=40.0,
    wrong=1.0,
    unresolved=0.0,
    lost=20.0,
    absent=0.0,
):
    return Row(
        threshold=threshold,
        correct_s=correct,
        wrong_s=wrong,
        unresolved_s=unresolved,
        lost_s=lost,
        absent_with_output_s=absent,
    )


def test_lowest_wrong_duration_wins_even_with_more_lost():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(0.4, wrong=1.0, lost=10.0),
            row(0.6, wrong=0.5, lost=25.0),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)


def test_equal_wrong_duration_uses_lowest_lost_duration():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(0.4, wrong=0.5, lost=20.0),
            row(0.6, wrong=0.5, lost=15.0),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)


def test_final_exact_tie_prefers_higher_threshold():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(0.4, wrong=0.5, lost=15.0),
            row(0.6, wrong=0.5, lost=15.0),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)


def test_wrong_person_gate_is_relative_to_raw_plus_tolerance():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(0.4, wrong=7.051, lost=10.0),
            row(0.6, wrong=7.049, lost=20.0),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)


def test_absence_output_gate_is_enforced():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(0.4, wrong=0.1, lost=10.0, absent=0.051),
            row(0.6, wrong=0.2, lost=20.0, absent=0.049),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)


def test_no_promotable_threshold_fails_closed():
    with pytest.raises(
        ValueError,
        match="no Target-ReID threshold passes",
    ):
        MODULE.select_target_reid_threshold(
            rows=(
                row(0.4, wrong=7.1),
                row(0.6, wrong=7.2),
            ),
            raw_wrong_s=7.0,
            raw_absent_with_output_s=0.0,
        )


def test_unresolved_does_not_change_historical_selector():
    winner = MODULE.select_target_reid_threshold(
        rows=(
            row(
                0.4,
                wrong=0.5,
                lost=10.0,
                unresolved=0.0,
            ),
            row(
                0.6,
                wrong=0.4,
                lost=20.0,
                unresolved=5.0,
            ),
        ),
        raw_wrong_s=7.0,
        raw_absent_with_output_s=0.0,
    )

    assert winner.threshold == pytest.approx(0.6)
