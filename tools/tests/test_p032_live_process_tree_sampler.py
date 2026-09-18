"""Tests for the non-intrusive Issue #32 live process-tree sampler."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "experiments"
    / "sample_p032_live_process_trees.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "p032_live_process_tree_sampler",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_root_accepts_named_positive_pid() -> None:
    module = load_module()
    root = module.parse_root("detector=1234")
    assert root.name == "detector"
    assert root.pid == 1234


@pytest.mark.parametrize(
    "raw",
    ("", "detector", "=123", "detector=0", "detector=-1", "detector=x"),
)
def test_parse_root_rejects_invalid_values(raw: str) -> None:
    module = load_module()
    with pytest.raises(ValueError):
        module.parse_root(raw)


def test_tree_members_requires_original_root_identity() -> None:
    module = load_module()
    Proc = module.Proc

    processes = {
        10: Proc(10, 1, 100, 20, 1000, "root"),
        11: Proc(11, 10, 101, 5, 500, "child"),
        12: Proc(12, 11, 102, 2, 250, "grandchild"),
        20: Proc(20, 1, 200, 7, 100, "unrelated"),
    }

    members = module.tree_members(processes, 10, 100)
    assert [member.pid for member in members] == [10, 11, 12]

    assert module.tree_members(processes, 10, 999) == ()


def test_summary_retains_root_identity_and_missing_count() -> None:
    module = load_module()

    rows = [
        {
            "group": "detector",
            "cpu_percent": None,
            "rss_kib": 100,
            "member_count": 2,
            "root_identity_alive": True,
        },
        {
            "group": "detector",
            "cpu_percent": 50.0,
            "rss_kib": 120,
            "member_count": 0,
            "root_identity_alive": False,
        },
    ]

    summary = module.summarize_records(
        rows,
        {"detector": (123, 456)},
    )
    group = summary["groups"]["detector"]

    assert summary["schema"] == "p032_live_process_tree_resources_v1"
    assert group["root_pid"] == 123
    assert group["root_starttime_ticks"] == 456
    assert group["root_missing_count"] == 1
    assert group["cpu_percent"]["mean"] == 50.0


def test_tree_members_rejects_child_older_than_reused_parent() -> None:
    module = load_module()
    Proc = module.Proc
    processes = {
        10: Proc(10, 1, 200, 20, 100, "root"),
        11: Proc(11, 10, 100, 5, 50, "older orphan"),
    }
    assert [member.pid for member in module.tree_members(processes, 10, 200)] == [10]


def test_zombie_root_is_not_accepted_as_live() -> None:
    module = load_module()
    Proc = module.Proc
    processes = {10: Proc(10, 1, 100, 20, 0, "root", "Z")}
    assert module.tree_members(processes, 10, 100) == ()


def test_overlapping_roots_are_rejected_before_totals() -> None:
    module = load_module()
    Proc = module.Proc
    root = Proc(10, 1, 100, 20, 100, "root")
    child = Proc(11, 10, 101, 5, 50, "child")
    with pytest.raises(ValueError, match="belongs to both"):
        module.require_disjoint_trees({
            "detector": (root, child), "tracker": (child,),
        })
