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


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: candidate appearance availability and "
        "mandatory ID-switch appearance validation are not implemented in main."
    ),
)
def test_new_id_with_conflicting_appearance_cannot_reacquire_on_geometry_alone():
    """A geometrically stable distractor must not replace the selected identity.

    This reproduces the structural May failure: after the selected tracker ID
    disappears, a single nearby new ID is geometrically strong. Because there
    is no second candidate, appearance_ambiguous_only does not add appearance
    to ranking. The current implementation can therefore accept the new ID
    even when its available appearance is incompatible with the selected
    target.
    """
    selected_appearance = feat([1.0, 0.0, 0.0])
    distractor_appearance = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        TargetMemoryConfig(
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
            appearance_conservative_enabled=True,
            appearance_conservative_require_appearance=False,
            appearance_conservative_min_similarity=0.65,
            appearance_conservative_margin=0.05,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=True,
            short_gap_new_id_allow_total=0.70,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected_appearance,
        )
    )

    stable = tim.update(
        [
            tr(
                1,
                (102, 100, 162, 240),
                appearance=selected_appearance,
            )
        ]
    )
    assert stable.state == TargetState.LOCKED
    assert stable.target_track_id == 1

    conflicting_new_id = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=distractor_appearance,
            )
        ]
    )

    assert conflicting_new_id.best_score is not None
    assert conflicting_new_id.best_score.track_id == 2
    assert conflicting_new_id.best_score.total >= 0.70
    assert conflicting_new_id.best_score.appearance_available
    assert conflicting_new_id.best_score.appearance_evaluated
    assert not conflicting_new_id.best_score.appearance_used
    assert conflicting_new_id.best_score.appearance_raw < 0.10

    # Required safety behaviour:
    # available contradictory appearance must prevent an ID switch, even when
    # the candidate is alone and geometrically convincing.
    assert conflicting_new_id.target_track_id == 1
    assert conflicting_new_id.state in {
        TargetState.UNCERTAIN,
        TargetState.LOST,
    }
    assert not conflicting_new_id.visible
    assert not conflicting_new_id.control_valid


def test_target_like_duplicate_does_not_become_hard_negative():
    """A duplicate or target fragment must not poison negative memory."""
    selected_appearance = feat([1.0, 0.0, 0.0])
    target_like_duplicate = feat([0.995, 0.100, 0.0])

    tim = TargetIdentityMemory(
        TargetMemoryConfig(
            image_width=640,
            image_height=480,
            appearance_enabled=True,
            appearance_ambiguous_only=True,
            appearance_conservative_enabled=True,
            hard_negative_memory_enabled=True,
            hard_negative_min_candidate_similarity=0.70,
            hard_negative_max_positive_similarity=0.95,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
            hard_negative_min_geometry=0.20,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected_appearance,
        )
    )

    out = tim.update(
        [
            tr(
                1,
                (102, 100, 162, 240),
                appearance=selected_appearance,
            ),
            tr(
                2,
                (104, 101, 164, 241),
                appearance=target_like_duplicate,
            ),
        ]
    )

    assert out.state == TargetState.LOCKED
    assert out.target_track_id == 1

    # Required safety behaviour: a candidate almost identical to the selected
    # positive identity is more plausibly a duplicate/fragment than a reliable
    # distractor prototype.
    assert len(tim._hard_negative_memory) == 0


@pytest.mark.xfail(
    run=False,
    reason=(
        "Unresolved specification: safe handling of same-ID hard-negative "
        "conflicts requires trusted-lineage and persistence semantics."
    ),
)
def test_uninterrupted_same_id_is_not_rejected_after_appearance_shift():
    """A learned distractor must not suppress uninterrupted target continuity.

    A legitimate nearby distractor is first stored as a hard negative because
    it is similar, but not almost identical, to the selected appearance.
    Afterwards, the selected person's pose changes and its current embedding
    becomes closer to that stored negative.

    The tracker ID remains uninterrupted and the geometry remains strong. This
    models the Seq01 failure where hard-negative memory suppresses the physical
    target without any tracker-ID handover.
    """
    selected_appearance = feat([1.0, 0.0, 0.0])
    learned_distractor = feat([0.94, 0.341, 0.0])
    shifted_target = feat([0.98, 0.199, 0.0])

    tim = TargetIdentityMemory(
        TargetMemoryConfig(
            image_width=640,
            image_height=480,
            appearance_enabled=True,
            appearance_ambiguous_only=True,
            appearance_update_alpha=0.0,
            appearance_conservative_enabled=True,
            appearance_conservative_require_appearance=False,
            appearance_conservative_min_similarity=0.65,
            appearance_conservative_margin=0.05,
            hard_negative_memory_enabled=True,
            hard_negative_min_candidate_similarity=0.70,
            hard_negative_max_positive_similarity=0.95,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
            hard_negative_min_geometry=0.20,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected_appearance,
        )
    )

    learned = tim.update(
        [
            tr(
                1,
                (102, 100, 162, 240),
                appearance=selected_appearance,
            ),
            tr(
                2,
                (125, 100, 185, 240),
                appearance=learned_distractor,
            ),
        ]
    )

    assert learned.state == TargetState.LOCKED
    assert learned.target_track_id == 1
    assert len(tim._hard_negative_memory) == 1

    continued = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                appearance=shifted_target,
            )
        ]
    )

    assert continued.best_score is not None
    assert continued.best_score.track_id == 1
    assert continued.best_score.appearance_evaluated
    assert continued.best_score.appearance_raw > 0.95
    assert continued.best_score.hard_negative_reject

    # Required safety behaviour: a hard negative may challenge an ID switch or
    # recovered lineage, but must not immediately invalidate uninterrupted,
    # geometrically strong, current-frame same-ID continuity.
    assert continued.state == TargetState.LOCKED
    assert continued.target_track_id == 1
    assert continued.visible
    assert continued.control_valid
