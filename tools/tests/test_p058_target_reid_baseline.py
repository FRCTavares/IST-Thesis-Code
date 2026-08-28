"""Tests for the deliberately simple Issue #58 Target-ReID baseline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "analysis" / "p058_target_reid_baseline.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "p058_target_reid_baseline",
    MODULE_PATH,
)

Candidate = MODULE.TargetReIdCandidate


def candidate(track_id, appearance):
    return Candidate(
        track_id=track_id,
        bbox_xyxy=(10.0, 20.0, 30.0, 60.0),
        appearance=np.asarray(appearance, dtype=np.float32),
    )


def test_selects_highest_anchor_similarity():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(
            candidate(7, [0.8, 0.6]),
            candidate(9, [1.0, 0.0]),
        ),
        threshold=0.5,
    )

    assert decision.published
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.track_id == 9
    assert decision.similarity == pytest.approx(1.0)


def test_returns_lost_when_best_similarity_is_below_threshold():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(
            candidate(7, [0.6, 0.8]),
            candidate(9, [0.5, 0.8660254]),
        ),
        threshold=0.7,
    )

    assert not decision.published
    assert decision.selected_candidate is None
    assert decision.similarity == pytest.approx(0.6)


def test_returns_lost_when_no_candidates_exist():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(),
        threshold=0.5,
    )

    assert not decision.published
    assert decision.selected_candidate is None
    assert decision.similarity is None


def test_returns_lost_when_anchor_is_unusable():
    decision = MODULE.select_target_reid_candidate(
        anchor=None,
        candidates=(candidate(7, [1.0, 0.0]),),
        threshold=0.5,
    )

    assert not decision.published
    assert decision.selected_candidate is None
    assert decision.similarity is None


def test_ignores_candidates_without_usable_appearance():
    invalid = Candidate(
        track_id=7,
        bbox_xyxy=(10.0, 20.0, 30.0, 60.0),
        appearance=None,
    )

    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(
            invalid,
            candidate(9, [1.0, 0.0]),
        ),
        threshold=0.5,
    )

    assert decision.published
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.track_id == 9


def test_threshold_is_inclusive():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(candidate(7, [0.6, 0.8]),),
        threshold=0.6,
    )

    assert decision.published
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.track_id == 7
    assert decision.similarity == pytest.approx(0.6)


def test_equal_similarity_tie_keeps_input_order():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(
            candidate(11, [1.0, 0.0]),
            candidate(3, [1.0, 0.0]),
        ),
        threshold=0.5,
    )

    assert decision.published
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.track_id == 11


def test_tracker_id_does_not_affect_ranking():
    decision = MODULE.select_target_reid_candidate(
        anchor=np.asarray([1.0, 0.0], dtype=np.float32),
        candidates=(
            candidate(1, [0.8, 0.6]),
            candidate(99, [1.0, 0.0]),
        ),
        threshold=0.5,
    )

    assert decision.selected_candidate is not None
    assert decision.selected_candidate.track_id == 99


def test_rejects_nonfinite_threshold():
    with pytest.raises(ValueError, match="threshold must be finite"):
        MODULE.select_target_reid_candidate(
            anchor=np.asarray([1.0, 0.0], dtype=np.float32),
            candidates=(),
            threshold=float("nan"),
        )
