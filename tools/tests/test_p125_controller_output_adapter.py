"""Synthetic tests of the six-arm output normalization boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues" / "p125" / "controller_output_adapter.py"
)
SPEC = importlib.util.spec_from_file_location("p125_controller_output_adapter", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BOX = (1.0, 2.0, 11.0, 12.0)


def test_raw_tracker_keeps_only_initialized_id():
    tracks = [
        SimpleNamespace(track_id=8, bbox_xyxy=(20.0, 2.0, 30.0, 12.0)),
        SimpleNamespace(track_id=7, bbox_xyxy=BOX),
    ]
    assert MODULE.from_raw_tracker(tracks, selected_track_id=7) == (
        MODULE.ControllerObservation(BOX, 7)
    )
    assert MODULE.from_raw_tracker(tracks, selected_track_id=9) == MODULE.NO_OUTPUT


def test_raw_tracker_rejects_duplicate_selected_identity():
    track = SimpleNamespace(track_id=7, bbox_xyxy=BOX)
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.from_raw_tracker([track, track], selected_track_id=7)


def test_target_reid_uses_only_published_decision():
    candidate = SimpleNamespace(track_id=7, bbox_xyxy=BOX)
    published = SimpleNamespace(
        decision=SimpleNamespace(published=True, selected_candidate=candidate)
    )
    suppressed = SimpleNamespace(
        decision=SimpleNamespace(published=False, selected_candidate=None)
    )
    assert MODULE.from_target_reid(published) == MODULE.ControllerObservation(BOX, 7)
    assert MODULE.from_target_reid(suppressed) == MODULE.NO_OUTPUT


def test_tim_mars_suppressed_state_never_exposes_candidate_or_stale_box():
    suppressed = SimpleNamespace(output=SimpleNamespace(
        control_valid=False,
        bbox=BOX,
        target_track_id=7,
        candidate_track_id=8,
    ))
    valid = SimpleNamespace(output=SimpleNamespace(
        control_valid=True,
        bbox=BOX,
        target_track_id=7,
        candidate_track_id=8,
    ))
    assert MODULE.from_tim_mars(suppressed) == MODULE.NO_OUTPUT
    assert MODULE.from_tim_mars(valid) == MODULE.ControllerObservation(BOX, 7)


def test_invalid_publication_geometry_and_identity_rejected():
    with pytest.raises(ValueError, match="positive area"):
        MODULE.ControllerObservation((1.0, 2.0, 1.0, 12.0), 7)
    with pytest.raises(ValueError, match="positive tracker identity"):
        MODULE.ControllerObservation(BOX, 0)
    with pytest.raises(ValueError, match="requires a published box"):
        MODULE.ControllerObservation(None, 7)


def test_observation_maps_preserve_explicit_absence_and_reject_duplicates():
    boxes, identities = MODULE.observation_maps([
        (0, MODULE.ControllerObservation(BOX, 7)),
        (1, MODULE.NO_OUTPUT),
    ])
    assert boxes == {0: BOX, 1: None}
    assert identities == {0: 7, 1: None}
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.observation_maps([(0, MODULE.NO_OUTPUT), (0, MODULE.NO_OUTPUT)])
