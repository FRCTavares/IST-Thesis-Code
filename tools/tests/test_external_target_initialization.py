"""Tests for frozen physical-target initialization mapping."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "external_target_initialization.py"
)

SPEC = importlib.util.spec_from_file_location(
    "external_target_initialization",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def target(frame, identity=42, bbox=(10.0, 10.0, 30.0, 50.0)):
    return MODULE.PhysicalTargetObservation(
        normalized_frame_index=frame,
        dataset_identity=identity,
        bbox_xyxy=bbox,
    )


def candidate(
    frame,
    tracker_identity,
    bbox,
    score=0.9,
):
    return MODULE.TrackerCandidateObservation(
        normalized_frame_index=frame,
        tracker_identity=tracker_identity,
        bbox_xyxy=bbox,
        score=score,
    )


def config(**changes):
    values = {
        "start_frame_index": 0,
        "end_frame_index_inclusive": 4,
        "minimum_iou": 0.5,
        "minimum_margin": 0.1,
        "confirmation_frames": 2,
    }
    values.update(changes)
    return MODULE.InitializationConfig(**values)


def test_bbox_iou_identical_boxes():
    assert MODULE.bbox_iou(
        (0.0, 0.0, 10.0, 10.0),
        (0.0, 0.0, 10.0, 10.0),
    ) == pytest.approx(1.0)


def test_larger_distractor_does_not_replace_frozen_target():
    targets = [target(0), target(1)]
    candidates = [
        candidate(0, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(0, 9, (0.0, 0.0, 90.0, 90.0), score=0.99),
        candidate(1, 7, (11.0, 10.0, 31.0, 50.0)),
        candidate(1, 9, (0.0, 0.0, 90.0, 90.0), score=0.99),
    ]

    result = MODULE.initialize_frozen_target(
        dataset_identity=42,
        target_observations=targets,
        tracker_candidates=candidates,
        config=config(),
    )

    assert result.success is True
    assert result.initial_tracker_identity == 7
    assert result.initialization_frame_index == 1


def test_tracker_match_requires_consecutive_confirmation():
    targets = [target(0), target(1), target(2)]
    candidates = [
        candidate(0, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(1, 8, (10.0, 10.0, 30.0, 50.0)),
        candidate(2, 8, (10.0, 10.0, 30.0, 50.0)),
    ]

    result = MODULE.initialize_frozen_target(
        dataset_identity=42,
        target_observations=targets,
        tracker_candidates=candidates,
        config=config(),
    )

    assert result.success is True
    assert result.initial_tracker_identity == 8
    assert result.initialization_frame_index == 2


def test_ambiguous_spatial_match_is_rejected():
    targets = [target(0), target(1)]
    candidates = [
        candidate(0, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(0, 8, (10.5, 10.0, 30.5, 50.0)),
        candidate(1, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(1, 8, (10.5, 10.0, 30.5, 50.0)),
    ]

    result = MODULE.initialize_frozen_target(
        dataset_identity=42,
        target_observations=targets,
        tracker_candidates=candidates,
        config=config(
            end_frame_index_inclusive=1,
            minimum_margin=0.1,
        ),
    )

    assert result.success is False
    assert len(result.frame_matches) == 2
    assert all(
        match.reason == "ambiguous_candidate_margin"
        for match in result.frame_matches
    )


def test_missing_target_visibility_resets_confirmation():
    targets = [target(0), target(2), target(3)]
    candidates = [
        candidate(0, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(2, 7, (10.0, 10.0, 30.0, 50.0)),
        candidate(3, 7, (10.0, 10.0, 30.0, 50.0)),
    ]

    result = MODULE.initialize_frozen_target(
        dataset_identity=42,
        target_observations=targets,
        tracker_candidates=candidates,
        config=config(),
    )

    assert result.success is True
    assert result.initialization_frame_index == 3
    assert result.frame_matches[1].reason == (
        "physical_target_not_visible"
    )


def test_no_reselection_of_another_physical_identity():
    targets = [
        target(0, identity=99),
        target(1, identity=99),
    ]
    candidates = [
        candidate(0, 3, (10.0, 10.0, 30.0, 50.0)),
        candidate(1, 3, (10.0, 10.0, 30.0, 50.0)),
    ]

    result = MODULE.initialize_frozen_target(
        dataset_identity=42,
        target_observations=targets,
        tracker_candidates=candidates,
        config=config(),
    )

    assert result.success is False
    assert result.initial_tracker_identity is None
    assert all(
        match.reason == "physical_target_not_visible"
        for match in result.frame_matches
    )


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        MODULE.InitializationConfig(
            start_frame_index=5,
            end_frame_index_inclusive=4,
        )


def test_duplicate_tracker_identity_in_one_frame_is_rejected():
    targets = [target(0)]
    candidates = [
        candidate(
            0,
            7,
            (10.0, 10.0, 30.0, 50.0),
        ),
        candidate(
            0,
            7,
            (11.0, 10.0, 31.0, 50.0),
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate tracker identity in frame 0: 7",
    ):
        MODULE.initialize_frozen_target(
            dataset_identity=42,
            target_observations=targets,
            tracker_candidates=candidates,
            config=config(
                end_frame_index_inclusive=0,
                confirmation_frames=1,
            ),
        )
