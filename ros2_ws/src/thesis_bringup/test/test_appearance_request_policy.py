"""Tests for the pure TIM-MARS appearance request policy."""

from copy import deepcopy

import pytest

from thesis_bringup.tim_mars.appearance_request_policy import (
    AppearanceRequestPolicy,
    select_appearance_request_candidates,
)
from thesis_bringup.tim_mars.types import (
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)


def candidate(
    track_id,
    bbox=(100.0, 100.0, 160.0, 240.0),
    score=0.9,
):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
    )


def config(**overrides):
    values = {
        "image_width": 640.0,
        "image_height": 640.0,
        "min_candidate_score": 0.10,
    }
    values.update(overrides)
    return TargetMemoryConfig(**values)


def decide(candidates, **overrides):
    values = {
        "policy": AppearanceRequestPolicy.GEOMETRY_WINNER,
        "candidates": candidates,
        "target_state": TargetState.LOCKED,
        "reference_bbox": (
            100.0,
            100.0,
            160.0,
            240.0,
        ),
        "current_track_id": 1,
        "target_config": config(),
        "pending_select_id": None,
        "auto_select_largest": False,
    }
    values.update(overrides)
    return select_appearance_request_candidates(**values)


def test_all_candidates_preserves_input_order():
    candidates = [
        candidate(8),
        candidate(3),
        candidate(11),
    ]

    decision = decide(
        candidates,
        policy=AppearanceRequestPolicy.ALL_CANDIDATES,
    )

    assert decision.requested_indices == (0, 1, 2)
    assert decision.requested_track_ids == (8, 3, 11)
    assert decision.reason == "all_candidates"
    assert decision.ranked_candidates == ()


def test_empty_candidate_list_requests_nothing():
    decision = decide([])

    assert decision.requested_indices == ()
    assert decision.requested_track_ids == ()
    assert decision.reason == "no_candidates"


def test_pending_operator_selection_has_priority():
    candidates = [
        candidate(
            1,
            bbox=(100.0, 100.0, 160.0, 240.0),
        ),
        candidate(
            9,
            bbox=(450.0, 450.0, 510.0, 590.0),
        ),
    ]

    decision = decide(
        candidates,
        target_state=TargetState.NO_TARGET,
        reference_bbox=None,
        current_track_id=None,
        pending_select_id=9,
    )

    assert decision.requested_indices == (1,)
    assert decision.requested_track_ids == (9,)
    assert decision.reason == "pending_operator_selection"


def test_missing_pending_selection_does_not_speculate():
    decision = decide(
        [candidate(1), candidate(2)],
        target_state=TargetState.NO_TARGET,
        reference_bbox=None,
        current_track_id=None,
        pending_select_id=99,
    )

    assert decision.requested_track_ids == ()
    assert decision.reason == (
        "pending_operator_selection_not_visible"
    )


def test_no_selected_target_requests_nothing_by_default():
    decision = decide(
        [candidate(1), candidate(2)],
        target_state=TargetState.NO_TARGET,
        reference_bbox=None,
        current_track_id=None,
    )

    assert decision.requested_track_ids == ()
    assert decision.reason == "no_selected_target"


def test_auto_select_largest_uses_area_then_confidence():
    candidates = [
        candidate(
            7,
            bbox=(0.0, 0.0, 20.0, 30.0),
            score=1.0,
        ),
        candidate(
            8,
            bbox=(0.0, 0.0, 40.0, 80.0),
            score=0.4,
        ),
    ]

    decision = decide(
        candidates,
        target_state=TargetState.NO_TARGET,
        reference_bbox=None,
        current_track_id=None,
        auto_select_largest=True,
    )

    assert decision.requested_indices == (1,)
    assert decision.requested_track_ids == (8,)
    assert decision.reason == "auto_select_largest"


def test_geometry_winner_uses_stateless_base_score():
    candidates = [
        candidate(
            1,
            bbox=(500.0, 500.0, 560.0, 640.0),
            score=1.0,
        ),
        candidate(
            2,
            bbox=(102.0, 101.0, 162.0, 241.0),
            score=0.7,
        ),
        candidate(
            3,
            bbox=(180.0, 100.0, 240.0, 240.0),
            score=0.9,
        ),
    ]

    decision = decide(candidates)

    assert decision.requested_indices == (1,)
    assert decision.requested_track_ids == (2,)
    assert decision.reason == "geometry_winner"
    assert decision.ranked_candidates[0].track_id == 2
    assert all(
        rank.score.appearance_available is False
        for rank in decision.ranked_candidates
    )


def test_impossible_geometry_is_not_promoted():
    decision = decide(
        [
            candidate(
                9,
                bbox=(520.0, 500.0, 620.0, 640.0),
                score=1.0,
            )
        ],
        current_track_id=1,
    )

    assert decision.requested_track_ids == ()
    assert decision.reason == (
        "no_geometry_plausible_candidate"
    )
    assert (
        decision.ranked_candidates[0]
        .geometry_plausible
        is False
    )


def test_equal_geometry_scores_preserve_input_order():
    candidates = [
        candidate(12),
        candidate(4),
    ]

    decision = decide(
        candidates,
        current_track_id=None,
        target_state=TargetState.LOCKED,
    )

    assert decision.reason == "no_selected_target"

    decision = decide(
        candidates,
        current_track_id=99,
    )

    assert decision.requested_indices == (0,)
    assert decision.requested_track_ids == (12,)
    assert [
        rank.track_id
        for rank in decision.ranked_candidates
    ] == [12, 4]


def test_policy_does_not_mutate_inputs():
    candidates = [
        candidate(1),
        candidate(
            2,
            bbox=(180.0, 100.0, 240.0, 240.0),
        ),
    ]
    cfg = config()

    candidates_before = deepcopy(candidates)
    cfg_before = deepcopy(cfg)

    decision = decide(
        candidates,
        target_config=cfg,
    )

    assert decision.requested_track_ids
    assert candidates == candidates_before
    assert cfg == cfg_before
    assert all(
        item.appearance is None
        for item in candidates
    )


def test_duplicate_track_ids_are_rejected():
    with pytest.raises(
        ValueError,
        match="unique track IDs",
    ):
        decide(
            [
                candidate(5),
                candidate(5),
            ]
        )


def test_unknown_policy_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported appearance request policy",
    ):
        decide(
            [candidate(1)],
            policy="not_a_policy",
        )
