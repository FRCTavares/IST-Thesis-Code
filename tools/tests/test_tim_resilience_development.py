"""Scientific accounting and forensic clock-alignment regression tests."""

import importlib.util
from pathlib import Path
import sys

import pytest


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "analysis"))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RUNNER = module("tim_resilience_runner", TOOLS / "experiments/run_tim_resilience_development.py")
AUDIT = module("tim_resilience_audit", TOOLS / "analysis/analyse_tim_resilience_evidence.py")


def test_normalized_metrics_exclude_absence_and_reference_gaps():
    buckets = {
        "correct_target_output_duration_s": 8.,
        "wrong_person_output_duration_s": .5,
        "identity_unresolved_duration_s": .5,
        "lost_or_suppressed_duration_s": 1.,
        "target_absent_duration_s": 10.,
        "target_absent_with_output_duration_s": 1.,
        "reference_gap_duration_s": 50.,
        "reference_unavailable_duration_s": 50.,
    }
    metrics = RUNNER.normalized(buckets)
    assert metrics["target_present_evaluable_duration_s"] == 10.
    assert metrics["correct_target_pct"] == 80.
    assert metrics["wrong_person_pct"] == 5.
    assert metrics["identity_unresolved_pct"] == 5.
    assert metrics["lost_or_suppressed_pct"] == 10.
    assert metrics["publication_correctness_pct"] == pytest.approx(800 / 9)
    assert metrics["target_absent_with_output_pct"] == 10.


def test_empty_denominators_are_undefined():
    buckets = {key + "_duration_s": 0. for key in (
        "correct_target_output", "wrong_person_output", "identity_unresolved",
        "lost_or_suppressed", "target_absent", "target_absent_with_output",
    )}
    metrics = RUNNER.normalized(buckets)
    assert metrics["correct_target_pct"] is None
    assert metrics["publication_correctness_pct"] is None
    assert metrics["target_absent_with_output_pct"] is None


def test_image_offset_uses_capture_difference_not_absolute_replay_epoch():
    assert AUDIT.source_reference_time(12., 100_000_000_000, 99_900_000_000) == 11.9
    assert AUDIT.source_reference_time(12., 900_000_000_000, 899_900_000_000) == 11.9


def test_source_displacement_accumulates_despite_small_consecutive_steps():
    first = (0., 0., 40., 100.)
    previous = (200., 0., 240., 100.)
    current = (210., 0., 250., 100.)
    assert AUDIT.spatial(previous, current, 640, 480)["centre_distance_norm"] < .25
    assert AUDIT.spatial(first, current, 640, 480)["centre_distance_norm"] > .25
