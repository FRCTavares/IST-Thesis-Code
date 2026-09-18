"""Checks for attaching resource measurement to tracked live roots."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/experiments/measure_p032_live_resources.py"
SPEC = importlib.util.spec_from_file_location("p032_live_measurement_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_resolve_roots_requires_requested_names_and_pins_identity(tmp_path: Path) -> None:
    pid_file = tmp_path / "pids.txt"
    pid_file.write_text("123 perception_camera\n456 dashboard_bridge\n")
    original = MODULE.process_starttime
    try:
        MODULE.process_starttime = lambda pid: {123: 999}[pid]
        assert MODULE.resolve_roots(pid_file, ("detector",)) == {"detector": (123, 999)}
        with pytest.raises(ValueError, match="required live process absent"):
            MODULE.resolve_roots(pid_file, ("detector", "tracker"))
    finally:
        MODULE.process_starttime = original


def test_resolve_roots_rejects_duplicate_or_shared_pids(tmp_path: Path) -> None:
    pid_file = tmp_path / "pids.txt"
    pid_file.write_text("123 perception_camera\n123 tracker\n")
    original = MODULE.process_starttime
    try:
        MODULE.process_starttime = lambda pid: 999
        with pytest.raises(ValueError, match="distinct PIDs"):
            MODULE.resolve_roots(pid_file, ("detector", "tracker"))
        pid_file.write_text("123 perception_camera\n456 perception_camera\n")
        with pytest.raises(ValueError, match="duplicate live process name"):
            MODULE.resolve_roots(pid_file, ("detector",))
    finally:
        MODULE.process_starttime = original


def test_result_rejects_lost_root() -> None:
    roots = {"detector": (123, 999)}
    resource = {"groups": {"detector": {
        "root_pid": 123, "root_starttime_ticks": 999,
        "root_missing_count": 1, "sample_count": 20,
    }}}
    analysis = {"integrity": {}, "architecture_total": {}}
    with pytest.raises(ValueError, match="root missing"):
        MODULE.check_result(resource, analysis, roots)


def test_sample_coverage_detects_sparse_stream(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    path.write_text(
        '{"sample_monotonic_ns":0,"group":"detector"}\n'
        '{"sample_monotonic_ns":1000000000,"group":"detector"}\n'
        '{"sample_monotonic_ns":5000000000,"group":"detector"}\n'
    )
    with pytest.raises(ValueError, match="coverage gap"):
        MODULE.sample_coverage(
            path, "sample_monotonic_ns", ("detector",),
            0, 5_000_000_000, 1.0,
        )
