"""Specify transactional hard-negative memory behaviour for TIM-MARS.

These tests define the required ordering between candidate evidence preparation,
final identity acceptance, and hard-negative memory mutation.

They are marked as unresolved specifications until the implementation moves
negative-memory mutation out of candidate preparation.
"""

import numpy as np
import pytest

from thesis_bringup.tim_mars.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def feat(values):
    array = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array
    return array / norm


def tr(track_id, bbox, score=0.95, appearance=None):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
    )


def cfg(**overrides):
    values = dict(
        image_width=640,
        image_height=480,
        appearance_enabled=True,
        appearance_ambiguous_only=True,
        appearance_update_alpha=0.0,
        appearance_conservative_enabled=False,
        hard_negative_memory_enabled=True,
        hard_negative_min_candidate_similarity=0.70,
        hard_negative_reject_similarity=1.01,
        hard_negative_reject_margin=0.03,
        hard_negative_min_geometry=0.20,
        rank_aware_reacquisition_enabled=False,
        candidate_belief_enabled=False,
        absence_recovery_enabled=False,
        short_gap_new_id_suppression_enabled=False,
    )
    values.update(overrides)
    return TargetMemoryConfig(**values)


def select_stable_target(tim, appearance):
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=appearance,
        )
    )

    output = tim.update(
        [
            tr(
                1,
                (102, 100, 162, 240),
                appearance=appearance,
            )
        ]
    )

    assert output.state == TargetState.LOCKED
    assert output.target_track_id == 1


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: candidate preparation currently mutates "
        "hard-negative memory before the proposal is accepted or rejected."
    ),
)
def test_candidate_preparation_is_side_effect_free():
    target = feat([1.0, 0.0, 0.0])
    distractor = feat([0.8, 0.6, 0.0])

    tim = TargetIdentityMemory(cfg())
    select_stable_target(tim, target)

    assert len(tim._hard_negative_memory) == 0

    tim._prepare_update_candidates(
        [
            tr(
                1,
                (104, 101, 164, 241),
                appearance=target,
            ),
            tr(
                2,
                (125, 101, 185, 241),
                appearance=distractor,
            ),
        ]
    )

    assert len(tim._hard_negative_memory) == 0


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: a candidate can currently enter negative "
        "memory before its final role in the frame has been resolved."
    ),
)
def test_candidate_cannot_become_negative_before_role_resolution():
    target = feat([1.0, 0.0, 0.0])
    candidate = feat([0.8, 0.6, 0.0])

    tim = TargetIdentityMemory(cfg())
    select_stable_target(tim, target)

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=candidate,
            )
        ]
    )

    assert output.target_track_id == 2
    assert output.state == TargetState.REACQUIRED
    assert len(tim._hard_negative_memory) == 0


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: negative memory has no reconciliation when "
        "a previously stored identity becomes the selected lineage."
    ),
)
def test_selected_identity_is_reconciled_out_of_negative_memory():
    target = feat([1.0, 0.0, 0.0])
    candidate = feat([0.8, 0.6, 0.0])

    tim = TargetIdentityMemory(cfg())
    select_stable_target(tim, target)

    tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                appearance=target,
            ),
            tr(
                2,
                (125, 101, 185, 241),
                appearance=candidate,
            ),
        ]
    )

    assert len(tim._hard_negative_memory) == 1

    tim.select(
        tr(
            2,
            (125, 101, 185, 241),
            appearance=candidate,
        )
    )

    assert (
        tim._hard_negative_memory.similarity(
            candidate,
            tim.cfg,
        )
        == 0.0
    )


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: hard-negative mutation must be explicitly "
        "restricted to trusted accepted LOCKED frames."
    ),
)
@pytest.mark.parametrize(
    "state",
    [
        TargetState.UNCERTAIN,
        TargetState.LOST,
        TargetState.REACQUIRED,
    ],
)
def test_untrusted_states_cannot_add_hard_negatives(state):
    target = feat([1.0, 0.0, 0.0])
    distractor = feat([0.8, 0.6, 0.0])

    tim = TargetIdentityMemory(cfg())
    select_stable_target(tim, target)

    tim._m.state = state

    tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                appearance=target,
            ),
            tr(
                2,
                (125, 101, 185, 241),
                appearance=distractor,
            ),
        ]
    )

    assert len(tim._hard_negative_memory) == 0
