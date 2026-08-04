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
    / "experiments"
    / "sample_process_groups.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p044_process_group_sampler",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_group_accepts_named_positive_pgid() -> None:
    module = load_module()

    group = module.parse_group(
        "perception=1234"
    )

    assert group.name == "perception"
    assert group.pgid == 1234


@pytest.mark.parametrize(
    "raw_value",
    (
        "",
        "perception",
        "=123",
        "perception=0",
        "perception=-1",
        "perception=invalid",
    ),
)
def test_parse_group_rejects_invalid_values(
    raw_value: str,
) -> None:
    module = load_module()

    with pytest.raises(ValueError):
        module.parse_group(raw_value)


def test_metric_summary_reports_interpolated_p95() -> None:
    module = load_module()

    summary = module.metric_summary(
        [1.0, 2.0, 3.0, 4.0]
    )

    assert summary["count"] == 4
    assert summary["mean"] == pytest.approx(2.5)
    assert summary["p50"] == pytest.approx(2.5)
    assert summary["p95"] == pytest.approx(3.85)
    assert summary["maximum"] == pytest.approx(4.0)


def test_summarize_records_keeps_group_ownership() -> None:
    module = load_module()

    records = [
        {
            "group": "perception",
            "cpu_percent": None,
            "rss_kib": 100,
            "member_count": 2,
            "members": [
                {
                    "pid": 10,
                    "command": "ros2 run wrapper",
                },
                {
                    "pid": 11,
                    "command": (
                        "perception_pipeline_node"
                    ),
                },
            ],
        },
        {
            "group": "perception",
            "cpu_percent": 50.0,
            "rss_kib": 120,
            "member_count": 2,
            "members": [
                {
                    "pid": 10,
                    "command": "ros2 run wrapper",
                },
                {
                    "pid": 11,
                    "command": (
                        "perception_pipeline_node"
                    ),
                },
            ],
        },
    ]

    summary = module.summarize_records(
        records,
        {"perception": 10},
    )
    group = summary["groups"]["perception"]

    assert group["pgid"] == 10
    assert group["sample_count"] == 2
    assert group["cpu_percent"]["count"] == 1
    assert group["cpu_percent"]["mean"] == 50.0
    assert group["rss_kib"]["mean"] == 110.0
    assert group["maximum_member_count"] == 2
    assert group["observed_pids"] == [10, 11]
    assert any(
        "perception_pipeline_node" in command
        for command in group["observed_commands"]
    )
