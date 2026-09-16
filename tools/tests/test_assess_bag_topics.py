from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "live/assess_bag_topics.py"
spec = importlib.util.spec_from_file_location("assess_bag_topics", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_topic_stats_report_rate_gaps_and_monotonicity():
    stats = mod.topic_stats([1_000_000_000, 1_100_000_000, 1_300_000_000])
    assert stats["message_count"] == 3
    assert stats["first_timestamp_ns"] == 1_000_000_000
    assert stats["last_timestamp_ns"] == 1_300_000_000
    assert stats["duration_s"] == pytest.approx(0.3)
    assert stats["average_rate_hz"] == pytest.approx(2 / 0.3)
    assert stats["gap_p50_s"] == pytest.approx(0.15)
    assert stats["gap_p95_s"] == pytest.approx(0.195)
    assert stats["gap_p99_s"] == pytest.approx(0.199)
    assert stats["gap_max_s"] == pytest.approx(0.2)
    assert stats["timestamp_monotonic"] is True


def test_topic_stats_expose_duplicate_and_backward_timestamps():
    stats = mod.topic_stats([10, 10, 9])
    assert stats["timestamp_monotonic"] is False
    assert stats["duplicate_timestamp_count"] == 1
    assert stats["backward_timestamp_count"] == 1


def test_pairing_requires_same_stamp_count_and_values():
    left = [(10, 1.0, 2.0), (20, 3.0, 4.0)]
    assert mod.pairing(left, list(left))["passed"] is True
    report = mod.pairing(left, [(10, 1.0, 2.0), (20, 3.0, 5.0)])
    assert report["passed"] is False
    assert report["paired_value_mismatch_count"] == 1
