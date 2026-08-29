"""Tests freezing the Issue #58 Target-ReID development sweep domain."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "tools" / "analysis" / "p058_target_reid_sweep_spec.py"

spec = importlib.util.spec_from_file_location(
    "p058_target_reid_sweep_spec",
    PATH,
)
assert spec is not None
assert spec.loader is not None

MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_threshold_grid_is_frozen_before_sweep():
    assert MODULE.THRESHOLDS == tuple(
        round(step * 0.05, 2)
        for step in range(20)
    )


def test_threshold_grid_has_expected_bounds():
    assert MODULE.THRESHOLDS[0] == 0.0
    assert MODULE.THRESHOLDS[-1] == 0.95
    assert len(MODULE.THRESHOLDS) == 20


def test_calibration_sequence_is_development_only():
    assert MODULE.SEQUENCE_ID == "dev_may_hard_reentry"


def test_calibration_rule_matches_frozen_selector():
    assert MODULE.CALIBRATION_RULE == {
        "wrong_tolerance_s": 0.05,
        "absence_output_tolerance_s": 0.05,
        "primary": "minimum_wrong_person_duration",
        "secondary": "minimum_lost_or_suppressed_duration",
        "final_deterministic_tie_break": "higher_threshold",
    }
