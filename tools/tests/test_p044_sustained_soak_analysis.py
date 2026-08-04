from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
PATH = (
    ROOT
    / "tools/experiments/analyze_p044_sustained_soak.py"
)

SPEC = importlib.util.spec_from_file_location(
    "p044_sustained_soak_analysis_under_test",
    PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_metric_summary_reports_percentiles() -> None:
    summary = MODULE.metric_summary(
        [None, 1.0, 2.0, 3.0, 4.0]
    )

    assert summary["count"] == 4
    assert summary["minimum"] == pytest.approx(1.0)
    assert summary["mean"] == pytest.approx(2.5)
    assert summary["p50"] == pytest.approx(2.5)
    assert summary["maximum"] == pytest.approx(4.0)


def test_window_classification_uses_three_equal_regions() -> None:
    start = 1_000
    duration = 900

    assert MODULE.classify_window(
        1_000,
        start_ns=start,
        duration_ns=duration,
    ) == "early"

    assert MODULE.classify_window(
        1_350,
        start_ns=start,
        duration_ns=duration,
    ) == "middle"

    assert MODULE.classify_window(
        1_700,
        start_ns=start,
        duration_ns=duration,
    ) == "late"


def test_windowed_metric_filters_records() -> None:
    rows = [
        {
            "received_monotonic_ns": 1_000,
            "type": "timing",
            "infer_ms": 5.0,
        },
        {
            "received_monotonic_ns": 1_350,
            "type": "other",
            "infer_ms": 99.0,
        },
        {
            "received_monotonic_ns": 1_700,
            "type": "timing",
            "infer_ms": 6.0,
        },
    ]

    summary = MODULE.windowed_metric(
        rows,
        timestamp_key="received_monotonic_ns",
        value_key="infer_ms",
        start_ns=1_000,
        duration_ns=900,
        predicate=lambda row: row["type"] == "timing",
    )

    assert summary["early"]["count"] == 1
    assert summary["middle"]["count"] == 0
    assert summary["late"]["count"] == 1


def test_drift_limit_accepts_absolute_allowance() -> None:
    assert MODULE.drift_within_limit(
        5.0,
        6.5,
        maximum_ratio=1.1,
        absolute_allowance=2.0,
    )

    assert not MODULE.drift_within_limit(
        5.0,
        9.0,
        maximum_ratio=1.1,
        absolute_allowance=2.0,
    )
