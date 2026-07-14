"""Characterize known TIM-MARS identity-integrity failure modes.

These tests intentionally record behaviour that is currently unsafe. They are
not desired-behaviour regressions. They provide a stable starting point for
structural repairs to proposal validation, lineage trust, and memory updates.
"""

import numpy as np

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity
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


def unsafe_id_switch_config(**overrides):
    values = dict(
        image_width=640,
        image_height=480,
        max_uncertain_frames=6,
        min_confirm_frames_after_reacquire=1,
        allow_id_switch_recovery=True,
        accept_score_locked=0.52,
        appearance_enabled=True,
        appearance_weight=0.12,
        appearance_min_similarity=0.35,
        appearance_ambiguous_only=True,
        appearance_update_alpha=0.50,
        appearance_conservative_enabled=True,
        appearance_conservative_require_appearance=False,
        appearance_conservative_min_similarity=0.65,
        appearance_conservative_margin=0.05,
        hard_negative_memory_enabled=False,
        rank_aware_reacquisition_enabled=False,
        candidate_belief_enabled=False,
        absence_recovery_enabled=False,
        short_gap_new_id_suppression_enabled=False,
    )
    values.update(overrides)
    return TargetMemoryConfig(**values)


def select_stable_target(tim, target_appearance):
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_appearance,
        )
    )

    stable = tim.update(
        [
            tr(
                1,
                (102, 100, 162, 240),
                appearance=target_appearance,
            )
        ]
    )

    assert stable.state == TargetState.LOCKED
    assert stable.target_track_id == 1


def test_current_single_new_id_can_reacquire_despite_conflicting_appearance():
    """Current ranking can accept geometry while contradictory appearance is unused."""

    selected_appearance = feat([1.0, 0.0, 0.0])
    wrong_appearance = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(unsafe_id_switch_config())
    select_stable_target(tim, selected_appearance)

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=wrong_appearance,
            )
        ]
    )

    assert output.best_score is not None
    assert output.best_score.track_id == 2
    assert output.best_score.total >= 0.70
    assert not output.best_score.appearance_used
    assert output.best_score.appearance_raw < 0.10

    # Characterized unsafe behaviour: the contradictory candidate becomes the
    # selected lineage because appearance was not used for this ranking case.
    assert output.target_track_id == 2
    assert output.state == TargetState.REACQUIRED
    assert output.reacquired
    assert not output.control_valid


def test_current_wrong_reacquisition_becomes_locked_on_next_same_id_frame():
    """A newly accepted wrong ID inherits normal same-ID continuity immediately."""

    selected_appearance = feat([1.0, 0.0, 0.0])
    wrong_appearance = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(unsafe_id_switch_config())
    select_stable_target(tim, selected_appearance)

    first = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=wrong_appearance,
            )
        ]
    )
    assert first.state == TargetState.REACQUIRED
    assert first.target_track_id == 2

    second = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=wrong_appearance,
            )
        ]
    )

    # Characterized unsafe behaviour: REACQUIRED transitions to LOCKED without
    # retaining separate trust status for the operator-selected physical target.
    assert second.state == TargetState.LOCKED
    assert second.target_track_id == 2
    assert second.visible
    assert second.control_valid


def test_current_locked_wrong_lineage_updates_positive_appearance_memory():
    """Once a wrong lineage is LOCKED, adaptive positive memory learns from it."""

    selected_appearance = feat([1.0, 0.0, 0.0])
    wrong_appearance = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        unsafe_id_switch_config(
            appearance_update_alpha=0.50,
        )
    )
    select_stable_target(tim, selected_appearance)

    protected_before = tim._m.appearance.copy()

    reacquired = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=wrong_appearance,
            )
        ]
    )
    assert reacquired.state == TargetState.REACQUIRED

    locked = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=wrong_appearance,
            )
        ]
    )
    assert locked.state == TargetState.LOCKED

    adapted_after = tim._m.appearance

    # Characterized unsafe behaviour: the first LOCKED frame of the accepted
    # lineage changes the only positive prototype toward the wrong identity.
    assert not np.allclose(protected_before, adapted_after)
    assert cosine_similarity(adapted_after, wrong_appearance) > cosine_similarity(
        protected_before,
        wrong_appearance,
    )
    assert cosine_similarity(adapted_after, selected_appearance) < cosine_similarity(
        protected_before,
        selected_appearance,
    )


def test_hard_negative_transaction_reconciles_selected_identity():
    """Keep negative mutation after trusted acceptance."""
    selected_appearance = feat([1.0, 0.0, 0.0])
    candidate_appearance = feat([0.8, 0.6, 0.0])

    tim = TargetIdentityMemory(
        unsafe_id_switch_config(
            hard_negative_memory_enabled=True,
            hard_negative_min_candidate_similarity=0.70,
            hard_negative_reject_similarity=1.01,
            hard_negative_reject_margin=0.03,
            hard_negative_min_geometry=0.20,
        )
    )
    select_stable_target(tim, selected_appearance)

    assert len(tim._hard_negative_memory) == 0

    reacquired = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=candidate_appearance,
            )
        ]
    )

    assert reacquired.target_track_id == 2
    assert reacquired.state == TargetState.REACQUIRED

    # Candidate preparation and ID-switch acceptance are side-effect free for
    # negative memory.
    assert len(tim._hard_negative_memory) == 0
    assert (
        tim._hard_negative_memory.similarity(
            candidate_appearance,
            tim.cfg,
        )
        == 0.0
    )

    locked = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=candidate_appearance,
            )
        ]
    )
    assert locked.state == TargetState.LOCKED
    assert locked.target_track_id == 2

    # The accepted lineage is not represented as a hard negative when it
    # becomes LOCKED.
    assert len(tim._hard_negative_memory) == 0
    assert (
        tim._hard_negative_memory.similarity(
            candidate_appearance,
            tim.cfg,
        )
        == 0.0
    )
