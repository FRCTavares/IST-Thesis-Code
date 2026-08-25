"""Tests for the Issue #25 evaluator CLI's non-bag-I/O helpers, and for the
CLI's explicit distinction from the legacy tracker-ID evaluator (section 20).

Bag reading itself is not exercised here (no real physical-reference-backed
bag exists yet -- this milestone is scoped to prove the scoring contract
with synthetic data; see test_physical_target_bbox_evaluation.py for the
full join/Stage-A/Stage-B/bucket pipeline).
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools" / "analysis" / "evaluate_physical_target_bbox.py"
LEGACY_MODULE_PATH = (
    REPO_ROOT / "tools" / "analysis" / "evaluate_tim_target_bbox_correctness.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "evaluate_physical_target_bbox", MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = _load_module()


def _msg(id_, cx, cy, w, h):
    return SimpleNamespace(id=id_, cx=cx, cy=cy, w=w, h=h)


def test_msg_box_xyxy_converts_cxcywh_correctly():
    box = CLI.msg_box_xyxy(_msg(1, 100.0, 100.0, 40.0, 60.0))
    assert box == pytest.approx((80.0, 70.0, 120.0, 130.0))


def test_msg_box_xyxy_zero_id_is_none():
    assert CLI.msg_box_xyxy(_msg(0, 100.0, 100.0, 40.0, 60.0)) is None


def test_msg_box_xyxy_non_positive_size_is_none():
    assert CLI.msg_box_xyxy(_msg(1, 100.0, 100.0, 0.0, 60.0)) is None
    assert CLI.msg_box_xyxy(_msg(1, 100.0, 100.0, 40.0, -1.0)) is None


def test_msg_box_xyxy_nan_is_none():
    nan = float("nan")
    assert CLI.msg_box_xyxy(_msg(1, nan, 100.0, 40.0, 60.0)) is None


def test_sha256_file_matches_known_hash(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"hello world")
    assert CLI.sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_git_commit_and_dirty_reads_real_repo_state():
    commit, dirty = CLI.git_commit_and_dirty(REPO_ROOT)
    assert commit is not None
    assert len(commit) == 40
    assert dirty in (True, False)


def test_default_report_dir_is_under_reports_p025():
    out_dir = CLI.default_report_dir(Path("some_bag_dir"))
    assert "reports/p025_physical_target_bbox" in str(out_dir)
    assert out_dir.name == "some_bag_dir"


def test_cli_help_clearly_distinguishes_from_legacy_evaluator():
    result = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    help_text = result.stdout
    assert "NOT" in help_text
    assert "correct_target_track_id" in help_text
    assert "evaluate_tim_target_bbox_correctness.py" in help_text
    assert "tim_physical_target_bbox_v1" in help_text


def test_legacy_evaluator_file_is_untouched_by_this_milestone():
    # Sanity: the legacy evaluator still exists and this module does not
    # import or wrap it.
    assert LEGACY_MODULE_PATH.is_file()
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "evaluate_tim_target_bbox_correctness" not in source.replace(
        "evaluate_tim_target_bbox_correctness.py", ""
    )
