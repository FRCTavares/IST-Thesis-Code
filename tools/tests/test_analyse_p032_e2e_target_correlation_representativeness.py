from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "analysis"
    / "analyse_p032_e2e_target_correlation_representativeness.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_e2e_target_representativeness",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(bag_time_ns, e2e_target_ms, pub_dt_ms=200.0, e2e_det_ms=12.0, track_ms=4.0):
    return {
        "bag_time_ns": bag_time_ns,
        "e2e_target_ms": e2e_target_ms,
        "pub_dt_ms": pub_dt_ms,
        "e2e_det_ms": e2e_det_ms,
        "track_ms": track_ms,
    }


def test_analyse_rejects_empty_input() -> None:
    module = load_module()

    with pytest.raises(ValueError):
        module.analyse({}, {})


def test_coverage_rate_matches_hit_count() -> None:
    module = load_module()

    timing_target = {
        i: _sample(i * 1_000_000_000, 20.0 if i % 4 == 0 else 0.0)
        for i in range(1, 21)
    }
    timing_tracker = {i: _sample(i * 1_000_000_000, 0.0, track_ms=3.5) for i in range(1, 21)}

    summary = module.analyse(timing_target, timing_tracker, window_count=4)

    assert summary["total_timing_target_samples"] == 20
    assert summary["genuine_measurement_count"] == 5
    assert summary["coverage_rate"] == pytest.approx(0.25)


def test_windowed_miss_rate_detects_a_declining_coverage_trend() -> None:
    module = load_module()

    # First half: every sample hits. Second half: every sample misses.
    timing_target = {}
    for i in range(1, 11):
        timing_target[i] = _sample(i * 1_000_000_000, 20.0)
    for i in range(11, 21):
        timing_target[i] = _sample(i * 1_000_000_000, 0.0)
    timing_tracker = {}

    summary = module.analyse(timing_target, timing_tracker, window_count=2)

    windows = summary["windows"]
    assert windows[0]["coverage_rate"] == pytest.approx(1.0)
    assert windows[1]["coverage_rate"] == pytest.approx(0.0)
    assert summary["coverage_rate_drift"]["ratio_last_over_first"] == pytest.approx(0.0)


def test_stable_coverage_has_drift_ratio_near_one() -> None:
    module = load_module()

    timing_target = {
        i: _sample(i * 1_000_000_000, 20.0 if i % 4 == 0 else 0.0)
        for i in range(1, 41)
    }
    timing_tracker = {}

    summary = module.analyse(timing_target, timing_tracker, window_count=4)

    ratio = summary["coverage_rate_drift"]["ratio_last_over_first"]
    assert ratio is not None
    assert 0.5 <= ratio <= 2.0


def test_covariate_comparison_detects_a_real_association() -> None:
    """If misses systematically occur during high-cadence-latency periods,
    the miss group's mean pub_dt_ms must differ from the hit group's.

    pub_dt_ms/e2e_det_ms are only meaningfully populated on /timing (the
    detector-side message), not on /timing_target itself, so this must be
    looked up via a separate timing dict keyed by the same frame_id.
    """
    module = load_module()

    timing_target = {}
    timing = {}
    for i in range(1, 11):
        # Hits during low pub_dt_ms.
        timing_target[i] = _sample(i * 1_000_000_000, 20.0)
        timing[i] = _sample(i * 1_000_000_000, 0.0, pub_dt_ms=100.0)
    for i in range(11, 21):
        # Misses during high pub_dt_ms.
        timing_target[i] = _sample(i * 1_000_000_000, 0.0)
        timing[i] = _sample(i * 1_000_000_000, 0.0, pub_dt_ms=900.0)
    timing_tracker = {}

    summary = module.analyse(
        timing_target, timing_tracker, timing, window_count=2
    )
    comparison = summary["covariate_comparison_hit_vs_miss"]["pub_dt_ms"]

    assert comparison["hit_mean"] == pytest.approx(100.0)
    assert comparison["miss_mean"] == pytest.approx(900.0)


def test_covariate_comparison_looks_up_track_ms_by_exact_frame_id() -> None:
    module = load_module()

    timing_target = {
        5: _sample(5_000_000_000, 20.0),
        6: _sample(6_000_000_000, 0.0),
    }
    timing_tracker = {
        5: _sample(5_000_000_000, 0.0, track_ms=3.0),
        6: _sample(6_000_000_000, 0.0, track_ms=9.0),
    }

    summary = module.analyse(timing_target, timing_tracker, window_count=1)
    comparison = summary["covariate_comparison_hit_vs_miss"]["track_ms"]

    assert comparison["hit_mean"] == pytest.approx(3.0)
    assert comparison["miss_mean"] == pytest.approx(9.0)


def test_frame_id_gaps_are_reported_separately_from_correlation_misses() -> None:
    module = load_module()

    timing_target = {
        1: _sample(1_000_000_000, 20.0),
        2: _sample(2_000_000_000, 20.0),
        5: _sample(3_000_000_000, 20.0),  # gap: 3, 4 missing
    }
    timing_tracker = {}

    summary = module.analyse(timing_target, timing_tracker, window_count=1)

    assert summary["frame_id_gap_count"] == 1
    # All three present samples are genuine hits -- a frame_id gap must not
    # be conflated with a correlation-miss sentinel.
    assert summary["genuine_measurement_count"] == 3
