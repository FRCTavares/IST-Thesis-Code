"""Focused tests for the Issue #58 Target-ReID replay wrapper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from thesis_msgs.msg import Track2D, Track2DArray


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "tools" / "experiments"
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = EXPERIMENT_DIR / "run_p058_target_reid_replay.py"

for path in (EXPERIMENT_DIR, ANALYSIS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "run_p058_target_reid_replay",
    MODULE_PATH,
)


def tracks_message() -> Track2DArray:
    message = Track2DArray()
    message.frame_id = 17
    message.src_stamp_ns = 123456789
    message.t_cam_msg_seen_ns = 123450000

    target = Track2D()
    target.id = 9
    target.cx = 0.4
    target.cy = 0.5
    target.w = 0.2
    target.h = 0.3
    target.score = 0.88

    message.tracks = [target]
    return message


def test_lost_decision_produces_zero_id_target():
    message = tracks_message()
    result = SimpleNamespace(
        decision=SimpleNamespace(
            published=False,
            selected_candidate=None,
            similarity=0.42,
        )
    )

    target = MODULE.make_target_message(message, result)

    assert target.frame_id == 17
    assert target.src_stamp_ns == 123456789
    assert target.id == 0
    assert target.cx == pytest.approx(0.0)
    assert target.score == pytest.approx(0.0)


def test_published_decision_copies_selected_track_geometry():
    message = tracks_message()
    result = SimpleNamespace(
        decision=SimpleNamespace(
            published=True,
            selected_candidate=SimpleNamespace(track_id=9),
            similarity=0.91,
        )
    )

    target = MODULE.make_target_message(message, result)

    assert target.id == 9
    assert target.cx == pytest.approx(0.4)
    assert target.cy == pytest.approx(0.5)
    assert target.w == pytest.approx(0.2)
    assert target.h == pytest.approx(0.3)
    assert target.score == pytest.approx(0.91)
    assert target.quality == pytest.approx(0.91)


def test_missing_selected_track_fails_closed():
    message = tracks_message()
    result = SimpleNamespace(
        decision=SimpleNamespace(
            published=True,
            selected_candidate=SimpleNamespace(track_id=99),
            similarity=0.95,
        )
    )

    target = MODULE.make_target_message(message, result)

    assert target.id == 0
    assert target.score == pytest.approx(0.0)
