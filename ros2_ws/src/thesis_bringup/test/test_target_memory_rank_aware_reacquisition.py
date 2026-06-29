import numpy as np

from thesis_bringup.tim_mars.target_memory import (
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
