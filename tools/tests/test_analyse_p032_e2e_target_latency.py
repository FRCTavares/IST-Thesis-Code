from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "analysis" / "analyse_p032_e2e_target_latency.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_e2e_target_latency",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_analyse_rejects_empty_samples() -> None:
    module = load_module()

    with pytest.raises(ValueError):
        module.analyse([])


def test_unavailable_sentinel_zeros_are_excluded_from_percentiles() -> None:
    """A majority-zero population must not drag genuine percentiles down
    to 0.0 -- that would misreport correlation misses as real
    sub-millisecond latency."""
    module = load_module()

    samples = (
        [(i, 0.0) for i in range(80)]
        + [(80 + i, 20.0) for i in range(20)]
    )

    summary = module.analyse(samples)

    assert summary["total_samples"] == 100
    assert summary["genuine_measurement_count"] == 20
    assert summary["unavailable_sentinel_count"] == 80
    assert summary["coverage_rate"] == pytest.approx(0.20)
    assert summary["e2e_target_ms"]["p50"] == 20.0
    assert summary["e2e_target_ms"]["count"] == 20


def test_coverage_rate_is_one_when_every_sample_is_genuine() -> None:
    module = load_module()

    samples = [(i, float(i + 1)) for i in range(10)]
    summary = module.analyse(samples)

    assert summary["coverage_rate"] == 1.0
    assert summary["unavailable_sentinel_count"] == 0


def test_all_unavailable_yields_null_percentiles_not_zero() -> None:
    module = load_module()

    samples = [(i, 0.0) for i in range(5)]
    summary = module.analyse(samples)

    assert summary["coverage_rate"] == 0.0
    assert summary["e2e_target_ms"]["p50"] is None
    assert summary["e2e_target_ms"]["mean"] is None


def test_percentile_matches_known_values() -> None:
    module = load_module()

    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    assert module.percentile(values, 0.0) == 10.0
    assert module.percentile(values, 1.0) == 50.0
    assert module.percentile(values, 0.5) == 30.0
