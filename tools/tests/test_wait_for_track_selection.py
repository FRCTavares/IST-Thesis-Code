"""Tests for typed live /tracks target selection."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "experiments" / "wait_for_track_selection.py"

SPEC = importlib.util.spec_from_file_location(
    "wait_for_track_selection",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def track(track_id, width, height, score):
    return SimpleNamespace(
        id=track_id,
        w=width,
        h=height,
        score=score,
    )


def message(*tracks):
    return SimpleNamespace(tracks=list(tracks))


def test_largest_selection_preserves_area_rule_and_minimum_height():
    msg = message(
        track(1, 100.0, 39.0, 0.99),
        track(2, 30.0, 100.0, 0.70),
        track(3, 50.0, 80.0, 0.60),
    )

    assert MODULE.select_largest_track_id(msg, min_height=40.0) == 3


def test_largest_selection_preserves_score_and_id_tie_breaks():
    msg = message(
        track(4, 40.0, 100.0, 0.80),
        track(5, 50.0, 80.0, 0.90),
        track(6, 50.0, 80.0, 0.90),
    )

    assert MODULE.select_largest_track_id(msg, min_height=40.0) == 6


def test_largest_selection_returns_none_without_usable_tracks():
    msg = message(
        track(1, 0.0, 100.0, 0.9),
        track(2, 30.0, 20.0, 0.9),
    )

    assert MODULE.select_largest_track_id(msg, min_height=40.0) is None


def test_exact_id_presence_does_not_apply_largest_track_size_filter():
    msg = message(
        track(7, 10.0, 20.0, 0.5),
        track(8, 50.0, 100.0, 0.9),
    )

    assert MODULE.contains_target_id(msg, 7) is True
    assert MODULE.contains_target_id(msg, 9) is False
