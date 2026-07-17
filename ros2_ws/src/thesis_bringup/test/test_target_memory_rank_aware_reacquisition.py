import numpy as np
import pytest

from thesis_bringup.tim_mars.target_memory import (
    CandidateScore,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def tr(track_id, bbox, score=0.9, appearance=None):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
    )


def feat(values):
    x = np.asarray(values, dtype=np.float32)
    return x / (np.linalg.norm(x) + 1e-9)


def cfg(**kwargs):
    base = dict(
        image_width=640,
        image_height=640,
        max_uncertain_frames=1,
        appearance_enabled=True,
        appearance_ambiguous_only=False,
        appearance_min_similarity=0.0,
        appearance_weight=0.0,
        accept_score_lost=0.60,
        accept_score_locked=0.52,
        rank_aware_lost_min_total=0.20,
        rank_aware_lost_min_geom=0.10,
        rank_aware_lost_min_app=0.10,
        rank_aware_lost_app_margin=0.05,
        rank_aware_confirm_frames=1,
    )
    base.update(kwargs)
    return TargetMemoryConfig(**base)


def test_rank_aware_disabled_preserves_rank0_lost_reacquisition():
    target = feat([1, 0, 0])
    distractor = feat([0, 1, 0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=False,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    # Force LOST.
    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update(
        [
            # Rank-0 by geometry/total, wrong appearance.
            tr(6, (103, 103, 163, 243), 0.95, appearance=distractor),
            # Better appearance, but farther/lower total.
            tr(11, (130, 100, 190, 240), 0.95, appearance=target),
        ]
    )

    assert out.target_track_id == 6


def test_rank_aware_lost_reacquisition_can_choose_rank1_by_appearance():
    target = feat([1, 0, 0])
    distractor = feat([0, 1, 0])

    tim = TargetIdentityMemory(
        cfg(rank_aware_reacquisition_enabled=True)
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    # Force LOST.
    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update(
        [
            # Rank-0 by geometry/total, wrong appearance.
            tr(6, (103, 103, 163, 243), 0.95, appearance=distractor),
            # Rank-1 by geometry/total, correct appearance.
            tr(11, (130, 100, 190, 240), 0.95, appearance=target),
        ]
    )

    assert out.target_track_id == 11
    assert out.state in {TargetState.REACQUIRED, TargetState.LOCKED}
    assert out.reacquired


@pytest.mark.xfail(
    strict=True,
    reason=(
        "REACQUIRED currently overwrites the trusted selected lineage "
        "before probation is complete"
    ),
)
def test_rank_aware_reacquisition_keeps_candidate_probationary():
    """Keep a rank-aware candidate separate from trusted selected memory."""
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=True,
            rank_aware_confirm_frames=1,
            min_confirm_frames_after_reacquire=2,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
        )
    )
    tim.select(
        tr(
            26,
            (100, 100, 160, 240),
            appearance=target,
        )
    )

    trusted_bbox = tim._m.bbox
    trusted_appearance = tim._m.appearance.copy()

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST
    assert tim._m.track_id == 26

    first = tim.update(
        [
            tr(
                29,
                (104, 101, 164, 241),
                score=0.95,
                appearance=target,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    assert not first.control_valid

    # Safety invariant: a proposal in REACQUIRED is probationary. It must not
    # replace the authoritative operator-selected lineage.
    assert tim._m.track_id == 26
    assert tim._m.bbox == trusted_bbox
    assert np.allclose(tim._m.appearance, trusted_appearance)

    assert tim._m.pending_track_id == 29
    assert tim._m.pending_bbox == (104, 101, 164, 241)
    assert tim._m.pending_confirm_count == 1

    second = tim.update(
        [
            tr(
                29,
                (106, 102, 166, 242),
                score=0.95,
                appearance=target,
            )
        ]
    )

    # One subsequent same-ID observation must not automatically inherit
    # trusted continuity or enable controller-facing publication.
    assert second.state == TargetState.REACQUIRED
    assert not second.visible
    assert not second.control_valid
    assert tim._m.track_id == 26
    assert tim._m.pending_track_id == 29
    assert tim._m.pending_confirm_count == 2
    assert np.allclose(tim._m.appearance, trusted_appearance)



def test_rank_aware_reacquisition_respects_confirmation_frames():
    target = feat([1, 0, 0])
    distractor = feat([0, 1, 0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=True,
            rank_aware_confirm_frames=2,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    tim.update([])
    tim.update([])
    assert tim.state == TargetState.LOST

    candidates = [
        tr(6, (103, 103, 163, 243), 0.95, appearance=distractor),
        tr(11, (130, 100, 190, 240), 0.95, appearance=target),
    ]

    first = tim.update(candidates)
    assert first.target_track_id == 1
    assert first.state in {TargetState.UNCERTAIN, TargetState.LOST}

    second = tim.update(candidates)
    assert second.target_track_id == 11
    assert second.reacquired


def test_absence_recovery_blocks_new_id_without_appearance():
    target = feat([1, 0, 0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=False,
            absence_recovery_enabled=True,
            absence_after_missed_frames=1,
            absence_new_id_requires_appearance=True,
            absence_confirm_frames=1,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update([
        tr(7, (102, 100, 162, 240), 0.95, appearance=None),
    ])

    assert out.target_track_id == 1
    assert out.state in {TargetState.UNCERTAIN, TargetState.LOST}
    assert out.visible is False
    assert out.reason == "absence_recovery_reject:no_appearance"


def test_absence_recovery_requires_confirmation_frames():
    target = feat([1, 0, 0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=False,
            absence_recovery_enabled=True,
            absence_after_missed_frames=1,
            absence_new_id_requires_appearance=True,
            absence_min_total=0.20,
            absence_min_distance=0.10,
            absence_min_scale=0.10,
            absence_min_similarity=0.50,
            absence_appearance_margin=0.05,
            absence_confirm_frames=2,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    candidate = [tr(7, (102, 100, 162, 240), 0.95, appearance=target)]

    first = tim.update(candidate)
    assert first.target_track_id == 1
    assert first.visible is False
    assert first.reason.startswith("absence_recovery_pending:")

    second = tim.update(candidate)
    assert second.target_track_id == 7
    assert second.reacquired
    assert second.state in {TargetState.REACQUIRED, TargetState.LOCKED}


def test_absence_recovery_rejects_low_appearance_margin():
    target = feat([1, 0, 0])
    similar_distractor = feat([0.99, 0.10, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=False,
            absence_recovery_enabled=True,
            absence_after_missed_frames=1,
            absence_new_id_requires_appearance=True,
            absence_min_total=0.20,
            absence_min_distance=0.10,
            absence_min_scale=0.10,
            absence_min_similarity=0.50,
            absence_appearance_margin=0.20,
            absence_confirm_frames=1,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), appearance=target))

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update(
        [
            tr(7, (102, 100, 162, 240), 0.95, appearance=target),
            tr(8, (104, 100, 164, 240), 0.95, appearance=similar_distractor),
        ]
    )

    assert out.target_track_id == 1
    assert out.visible is False
    assert out.reason.startswith("absence_recovery_reject:appearance_margin")

def test_rank_aware_reacquisition_cannot_bypass_hard_negative_rejection():
    memory = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=True,
            rank_aware_confirm_frames=1,
            hard_negative_memory_enabled=True,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
        )
    )

    memory._m.selected = True
    memory._m.state = TargetState.LOST
    memory._m.track_id = 1
    memory._m.bbox = (0.10, 0.10, 0.20, 0.40)

    candidate = CandidateTrack(
        track_id=41,
        bbox=(0.11, 0.10, 0.20, 0.40),
        score=0.90,
        appearance=[1.0, 0.0],
    )

    score = CandidateScore(
        track_id=41,
        total=0.73,
        iou=0.95,
        distance=0.99,
        scale=1.0,
        confidence=0.90,
        id_bonus=0.0,
        appearance=0.70,
        appearance_used=True,
        appearance_raw=0.70,
        appearance_gate_passed=True,
        geometry_allows_appearance=True,
        hard_negative_similarity=0.82,
        hard_negative_margin=-0.12,
        hard_negative_reject=True,
    )

    output = memory._handle_rank_aware_reacquisition(
        candidates=[candidate],
        scores_sorted=[score],
        best=score,
    )

    assert output is not None
    assert output.state != TargetState.REACQUIRED
    assert output.reason.startswith(
        "rank_aware_hard_negative_reject:"
    )
    assert memory._m.track_id == 1


def test_rank_aware_id_switch_respects_minimum_appearance_similarity():
    target = feat([1.0, 0.0, 0.0])
    low_match = feat([0.70, 0.714142842, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            rank_aware_reacquisition_enabled=True,
            rank_aware_confirm_frames=1,
            rank_aware_lost_min_app=0.05,
            id_switch_min_appearance_similarity=0.78,
            hard_negative_memory_enabled=False,
            appearance_conservative_enabled=False,
            short_gap_new_id_suppression_enabled=False,
            absence_recovery_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )

    tim.update([])
    tim.update([])

    output = tim.update(
        [
            tr(
                7,
                (104, 101, 164, 241),
                score=0.95,
                appearance=low_match,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOST
    assert not output.visible
    assert (
        output.reason
        == "rank_aware_id_switch_recovery_reject:"
        "appearance 0.700<0.780"
    )
