"""Tests for the Issue #32 final resource analyser."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "analysis"
    / "analyse_p032_final_resources.py"
)

SPEC = importlib.util.spec_from_file_location(
    "analyse_p032_final_resources_under_test",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def resource_row(
    timestamp: int,
    group: str,
    cpu: float | None,
    rss: int,
) -> dict[str, object]:
    return {
        "schema": "p044_process_group_sample_v1",
        "sample_monotonic_ns": timestamp,
        "group": group,
        "cpu_percent": cpu,
        "rss_kib": rss,
        "member_count": 2,
    }


def hardware_row(
    timestamp: int,
    temperature: float,
    *,
    throttled: int = 0,
) -> dict[str, object]:
    return {
        "schema": "p044_hardware_health_sample_v1",
        "monotonic_ns": timestamp,
        "temperature_c": temperature,
        "arm_frequency_hz": 2_000_000_000,
        "core_voltage_v": 0.8,
        "mem_available_kib": 1_000_000,
        "throttled": throttled,
        "errors": {},
    }


def test_descriptive_stats_match_runtime_contract() -> None:
    stats = MODULE.descriptive_stats(
        [1.0, 2.0, 3.0]
    )

    assert stats["n"] == 3
    assert stats["mean"] == pytest.approx(2.0)
    assert stats["std"] == pytest.approx(
        0.816496580927726
    )
    assert stats["p50"] == pytest.approx(2.0)
    assert stats["p90"] == pytest.approx(2.8)
    assert stats["p95"] == pytest.approx(2.9)
    assert stats["p99"] == pytest.approx(2.98)
    assert stats["maximum"] == pytest.approx(3.0)


def test_warmup_is_excluded_from_steady_state() -> None:
    resources = [
        resource_row(0, "detector", 100.0, 100),
        resource_row(0, "tracker", 20.0, 20),
        resource_row(2_000_000_000, "detector", 50.0, 110),
        resource_row(2_000_000_000, "tracker", 10.0, 25),
    ]
    hardware = [
        hardware_row(0, 80.0),
        hardware_row(2_000_000_000, 60.0),
    ]

    result = MODULE.analyse(
        resources,
        hardware,
        warm_up_s=1.0,
        architecture_groups=("detector", "tracker"),
        analysis_start_ns=0,
    )

    cpu = result["architecture_total"]["cpu_percent"]

    assert cpu["all"]["n"] == 2
    assert cpu["all"]["mean"] == pytest.approx(90.0)
    assert cpu["steady_state"]["n"] == 1
    assert cpu["steady_state"]["mean"] == pytest.approx(60.0)

    temperature = result["hardware"]["temperature_c"]
    assert temperature["all"]["mean"] == pytest.approx(70.0)
    assert temperature["steady_state"]["mean"] == pytest.approx(60.0)


def test_architecture_total_requires_complete_group_timestamp() -> None:
    resources = [
        resource_row(0, "detector", 100.0, 100),
        resource_row(0, "tracker", 20.0, 20),
        resource_row(1, "detector", 90.0, 110),
    ]

    result = MODULE.build_architecture_totals(
        resources,
        requested_groups=("detector", "tracker"),
        steady_start_ns=0,
    )

    assert result["complete_timestamp_count"] == 1
    assert result["cpu_percent"]["all"]["n"] == 1
    assert result["cpu_percent"]["all"]["mean"] == pytest.approx(120.0)
    assert result["rss_kib"]["all"]["mean"] == pytest.approx(120.0)


def test_missing_requested_group_is_explicit() -> None:
    resources = [
        resource_row(0, "detector", 100.0, 100),
        resource_row(0, "tracker", 20.0, 20),
    ]

    result = MODULE.build_architecture_totals(
        resources,
        requested_groups=(
            "detector",
            "tracker",
            "tim",
            "controller",
        ),
        steady_start_ns=0,
    )

    assert result["included_groups"] == [
        "detector",
        "tracker",
    ]
    assert result["missing_requested_groups"] == [
        "tim",
        "controller",
    ]


def test_throttling_and_power_boundary_are_explicit() -> None:
    resources = [
        resource_row(0, "detector", 50.0, 100),
    ]
    hardware = [
        hardware_row(0, 60.0),
        hardware_row(
            2_000_000_000,
            61.0,
            throttled=1,
        ),
    ]

    result = MODULE.analyse(
        resources,
        hardware,
        warm_up_s=1.0,
        architecture_groups=("detector",),
        analysis_start_ns=0,
    )

    throttle = result["hardware"]["throttling"]
    assert throttle["all"]["nonzero_count"] == 1
    assert throttle["steady_state"]["nonzero_count"] == 1

    boundary = result["claim_boundary"]
    assert boundary["core_voltage_is_power_measurement"] is False
    assert boundary["electrical_power_claim_available"] is False
    assert boundary["raw_sampler_schemas_modified"] is False


def test_known_raw_sampler_schemas_are_checked() -> None:
    result = MODULE.analyse(
        [resource_row(0, "detector", 50.0, 100)],
        [hardware_row(0, 60.0)],
        warm_up_s=0.0,
        architecture_groups=("detector",),
        analysis_start_ns=0,
    )

    integrity = result["integrity"]
    assert integrity[
        "resource_records_have_known_sample_schema"
    ] is True
    assert integrity[
        "hardware_records_have_known_sample_schema"
    ] is True


def test_markdown_contains_required_reporting_boundaries() -> None:
    result = MODULE.analyse(
        [resource_row(0, "detector", 50.0, 100)],
        [hardware_row(0, 60.0)],
        warm_up_s=0.0,
        architecture_groups=("detector",),
        analysis_start_ns=0,
    )

    markdown = MODULE.render_markdown(result)

    assert "Architecture total" in markdown
    assert "p90" in markdown
    assert "p99" in markdown
    assert "steady_state" in markdown
    assert "Core voltage is telemetry, not electrical power." in markdown


def test_explicit_analysis_bounds_exclude_sampler_roll() -> None:
    resources = [
        resource_row(0, "detector", 999.0, 999),
        resource_row(10, "detector", 50.0, 100),
        resource_row(20, "detector", 60.0, 110),
        resource_row(30, "detector", 888.0, 888),
    ]
    hardware = [
        hardware_row(0, 99.0),
        hardware_row(10, 60.0),
        hardware_row(20, 61.0),
        hardware_row(30, 98.0),
    ]

    result = MODULE.analyse(
        resources,
        hardware,
        warm_up_s=0.0,
        architecture_groups=("detector",),
        analysis_start_ns=10,
        analysis_end_ns=20,
    )

    assert result["resource_sample_count"] == 2
    assert result["hardware_sample_count"] == 2
    assert (
        result["architecture_total"]["cpu_percent"]["all"]["mean"]
        == pytest.approx(55.0)
    )
    assert (
        result["hardware"]["temperature_c"]["all"]["mean"]
        == pytest.approx(60.5)
    )
    assert (
        result["measurement_window"]["analysis_start_source"]
        == "explicit_argument"
    )
    assert (
        result["measurement_window"]["analysis_end_source"]
        == "explicit_argument"
    )
