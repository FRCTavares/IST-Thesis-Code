from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
PATH = (
    ROOT
    / "tools/experiments/sample_p044_hardware_health.py"
)

SPEC = importlib.util.spec_from_file_location(
    "p044_hardware_health_under_test",
    PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_vcgencmd_parsers() -> None:
    assert MODULE.parse_temperature("temp=57.6'C") == pytest.approx(57.6)
    assert MODULE.parse_throttled("throttled=0x0") == 0
    assert MODULE.parse_throttled("throttled=0x50005") == 0x50005
    assert MODULE.parse_frequency("frequency(0)=2000020352") == 2_000_020_352
    assert MODULE.parse_voltage("volt=0.8027V") == pytest.approx(0.8027)


def test_invalid_vcgencmd_values_are_missing() -> None:
    assert MODULE.parse_temperature("unavailable") is None
    assert MODULE.parse_throttled("unavailable") is None
    assert MODULE.parse_frequency("unavailable") is None
    assert MODULE.parse_voltage("unavailable") is None


def test_finite_summary_ignores_missing_values() -> None:
    summary = MODULE.finite_summary(
        [None, 50.0, 60.0]
    )

    assert summary == {
        "count": 2,
        "minimum": 50.0,
        "mean": 55.0,
        "maximum": 60.0,
    }


def test_summary_records_nonzero_throttle_samples() -> None:
    samples = [
        {
            "temperature_c": 55.0,
            "arm_frequency_hz": 2_000_000_000,
            "core_voltage_v": 0.8,
            "mem_available_kib": 1_000,
            "throttled": 0,
            "errors": {},
        },
        {
            "temperature_c": 56.0,
            "arm_frequency_hz": 1_500_000_000,
            "core_voltage_v": 0.79,
            "mem_available_kib": 900,
            "throttled": 1,
            "errors": {},
        },
    ]

    summary = MODULE.build_summary(
        samples,
        MODULE.time.monotonic_ns(),
    )

    assert summary["sample_count"] == 2
    assert summary["throttle_sample_count"] == 2
    assert summary["nonzero_throttle_sample_count"] == 1
    assert summary["maximum_throttle_value"] == 1
