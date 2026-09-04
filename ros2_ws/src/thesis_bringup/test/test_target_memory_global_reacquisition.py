import numpy as np

from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
)
from thesis_bringup.tim_mars.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def feat(values):
    value = np.asarray(values, dtype=np.float32)
    return value / (np.linalg.norm(value) + 1e-9)


def tr(
    track_id,
    bbox,
    *,
    appearance,
    score=0.95,
    memory_eligible=True,
    crop_quality=None,
):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
        appearance_crop_quality=crop_quality,
        appearance_memory_update_eligible=memory_eligible,
    )


def cfg(**kwargs):
    base = {
        "image_width": 640,
        "image_height": 640,
        "max_uncertain_frames": 1,
        "min_confirm_frames_after_reacquire": 1,
        "appearance_enabled": True,
        "appearance_ambiguous_only": False,
        "appearance_min_similarity": 0.0,
        "appearance_weight": 0.0,
        "appearance_protected_memory_enabled": True,
        "appearance_conservative_enabled": True,
        "appearance_conservative_require_appearance": True,
        "appearance_conservative_min_similarity": 0.80,
        "appearance_conservative_margin": 0.20,
        "appearance_gallery_min_anchor_similarity": 0.0,
        "id_switch_min_appearance_similarity": 0.80,
        "allow_id_switch_recovery": True,
        "id_switch_spatial_gate_enabled": False,
        "short_gap_same_id_priority_enabled": True,
        "short_gap_same_id_grace_frames": 8,
        "rank_aware_reacquisition_enabled": False,
        "absence_recovery_enabled": False,
        "candidate_belief_enabled": False,
        "hard_negative_memory_enabled": False,
        "global_reacquisition_enabled": True,
        "global_reacquisition_after_missed_frames": 4,
    }
    base.update(kwargs)
    return TargetMemoryConfig(**base)


def enter_global_lost(tim):
    output = None
    for _ in range(4):
        output = tim.update([])

    assert output is not None
    assert output.state == TargetState.LOST
    assert tim.state == TargetState.LOST
    assert tim._m.frames_since_seen >= 4
    assert tim._positive_appearance.protected_anchor is not None
    return output


def test_long_gap_new_id_opposite_side_reacquires_by_protected_identity():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    opposite_side = tr(
        44,
        (500, 290, 570, 470),
        appearance=target,
    )

    first = tim.update([opposite_side])

    assert first.state == TargetState.REACQUIRED
    assert first.reacquired
    assert not first.visible
    assert not first.control_valid
    assert first.candidate_track_id == 44
    assert first.best_score is not None
    assert first.best_score.appearance_evaluated
    assert first.best_score.positive_similarity >= 0.99

    # Old spatial memory must not have been replaced while probationary.
    assert tim._m.track_id == 1
    assert tim._m.bbox == (80, 100, 150, 280)

    second = tim.update([opposite_side])

    assert second.state == TargetState.LOCKED
    assert second.visible
    assert second.control_valid
    assert second.reacquired
    assert second.target_track_id == 44


def test_long_gap_distractor_only_scene_remains_lost():
    target = feat([1.0, 0.0, 0.0])
    distractor = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    output = tim.update(
        [
            tr(
                72,
                (500, 290, 570, 470),
                appearance=distractor,
            )
        ]
    )

    assert output.state == TargetState.LOST
    assert not output.visible
    assert not output.control_valid
    assert output.target_track_id == 1
    assert output.best_score is not None
    assert output.best_score.appearance_evaluated
    assert output.reason.startswith(
        "global_identity_recovery_reject:appearance"
    )

    # Rejected observations must not mutate protected positive identity.
    assert tim._m.track_id == 1
    assert len(tim._positive_appearance.trusted_gallery) == 0


def test_long_gap_two_plausible_identities_without_margin_remain_lost():
    target = feat([1.0, 0.0, 0.0])
    near_duplicate = feat([0.995, 0.10, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    output = tim.update(
        [
            tr(
                44,
                (500, 290, 570, 470),
                appearance=target,
            ),
            tr(
                45,
                (360, 120, 430, 300),
                appearance=near_duplicate,
            ),
        ]
    )

    assert output.state == TargetState.LOST
    assert not output.visible
    assert output.best_score is not None
    assert output.best_score.appearance_evaluated
    assert output.reason.startswith(
        "global_identity_recovery_reject:appearance_margin"
    )
    assert tim._m.track_id == 1


def test_global_recovery_bypasses_stale_id_switch_spatial_gate():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            id_switch_spatial_gate_enabled=True,
            id_switch_min_iou=0.99,
            id_switch_min_distance=0.99,
            id_switch_min_scale=0.99,
        )
    )
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    candidate = tr(
        44,
        (500, 290, 570, 470),
        appearance=target,
    )

    first = tim.update([candidate])

    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    assert not first.control_valid

    second = tim.update([candidate])

    assert second.state == TargetState.LOCKED
    assert second.visible
    assert second.control_valid
    assert second.target_track_id == 44


def test_global_recovery_does_not_inherit_absence_geometry_policy():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            absence_recovery_enabled=True,
            absence_after_missed_frames=1,
            absence_min_total=0.99,
            absence_min_distance=0.99,
            absence_min_scale=0.99,
            absence_min_similarity=0.99,
            absence_appearance_margin=0.50,
            absence_confirm_frames=5,
        )
    )
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    candidate = tr(
        44,
        (500, 290, 570, 470),
        appearance=target,
    )

    first = tim.update([candidate])

    # Global recovery keeps the normal generic recovery persistence.
    # It must not inherit the old geometry-based absence policy or
    # that policy's five-frame confirmation requirement.
    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    assert not first.control_valid

    second = tim.update([candidate])

    assert second.state == TargetState.LOCKED
    assert second.visible
    assert second.control_valid
    assert second.target_track_id == 44


def test_protected_identity_survives_indefinite_lost():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )

    anchor_before = (
        tim._positive_appearance.protected_anchor.copy()
    )
    adaptive_before = (
        tim._positive_appearance.adaptive_prototype.copy()
    )
    gallery_before = tuple(
        value.copy()
        for value in tim._positive_appearance.trusted_gallery
    )

    output = None
    for _ in range(120):
        output = tim.update([])

    assert output is not None
    assert output.state == TargetState.LOST
    assert not output.visible
    assert not output.control_valid
    assert tim._m.track_id == 1
    assert tim._m.frames_since_seen >= 120

    assert np.array_equal(
        tim._positive_appearance.protected_anchor,
        anchor_before,
    )
    assert np.array_equal(
        tim._positive_appearance.adaptive_prototype,
        adaptive_before,
    )
    assert len(
        tim._positive_appearance.trusted_gallery
    ) == len(gallery_before)
    for current, expected in zip(
        tim._positive_appearance.trusted_gallery,
        gallery_before,
    ):
        assert np.array_equal(current, expected)


def test_long_gap_new_id_near_old_position_reacquires():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    candidate = tr(
        88,
        (86, 104, 156, 284),
        appearance=target,
    )

    first = tim.update([candidate])
    assert first.state == TargetState.REACQUIRED
    assert not first.control_valid

    second = tim.update([candidate])
    assert second.state == TargetState.LOCKED
    assert second.target_track_id == 88
    assert second.control_valid


def test_long_gap_large_scale_change_reacquires_by_identity():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (90, 120, 150, 300),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    # Much smaller and elsewhere in the frame.
    candidate = tr(
        91,
        (510, 80, 535, 145),
        appearance=target,
    )

    first = tim.update([candidate])

    assert first.state == TargetState.REACQUIRED
    assert first.best_score is not None
    assert first.best_score.appearance_evaluated
    assert first.best_score.positive_similarity >= 0.99
    assert not first.control_valid

    second = tim.update([candidate])

    assert second.state == TargetState.LOCKED
    assert second.target_track_id == 91
    assert second.control_valid


def test_adaptive_prototype_cannot_authorize_global_recovery():
    anchor = feat([1.0, 0.0, 0.0])
    adaptive_only = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=anchor,
        )
    )

    # Deliberately make adaptive memory disagree with protected identity.
    # Global LOST authority must ignore this prototype.
    tim._positive_appearance.adaptive_prototype = (
        adaptive_only.copy()
    )

    enter_global_lost(tim)

    output = tim.update(
        [
            tr(
                77,
                (500, 290, 570, 470),
                appearance=adaptive_only,
            )
        ]
    )

    assert output.state == TargetState.LOST
    assert not output.visible
    assert not output.control_valid
    assert output.best_score is not None
    assert output.best_score.appearance_evaluated
    assert output.best_score.adaptive_similarity > 0.99
    assert output.best_score.positive_similarity < 0.80
    assert (
        output.best_score.positive_support_source
        != "adaptive_prototype"
    )
    assert output.reason.startswith(
        "global_identity_recovery_reject:appearance"
    )
    assert tim._m.track_id == 1


def test_confirmed_hard_negative_blocks_global_recovery():
    target = feat([1.0, 0.0, 0.0])
    hard_negative = feat([0.85, 0.5267827, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            hard_negative_memory_enabled=True,
            hard_negative_confirm_observations=1,
            hard_negative_min_candidate_similarity=0.0,
            hard_negative_max_positive_similarity=0.95,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
            hard_negative_min_geometry=0.0,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 170, 280),
            appearance=target,
        )
    )

    # Direct deterministic committed-negative fixture. The store
    # intentionally supports raw-feature entries for local tests.
    tim._hard_negative_memory._memory = [
        hard_negative.copy()
    ]

    assert len(tim._hard_negative_memory) == 1

    enter_global_lost(tim)

    # Long absence must retain committed negative identity evidence.
    assert len(tim._hard_negative_memory) == 1

    output = tim.update(
        [
            tr(
                44,
                (500, 290, 570, 470),
                appearance=hard_negative,
            )
        ]
    )

    assert output.state == TargetState.LOST
    assert not output.visible
    assert not output.control_valid
    assert output.best_score is not None
    assert output.best_score.appearance_evaluated
    assert output.best_score.appearance_raw >= 0.80
    assert output.best_score.hard_negative_similarity > 0.99
    assert output.best_score.hard_negative_reject
    assert output.reason.startswith(
        "global_identity_recovery_reject:hard_negative"
    )
    assert tim._m.track_id == 1


def test_wide_comparison_only_gallery_crop_can_reacquire_globally():
    anchor = feat([1.0, 0.0, 0.0])
    gallery_pose = feat([0.80, 0.60, 0.0])

    wide_quality = AppearanceCropQuality(
        crop_width_px=480.0,
        crop_height_px=380.0,
        clipping_fraction=0.0,
        aspect_ratio=480.0 / 380.0,
        max_iou_with_other=0.0,
        min_centre_distance_norm=1.0,
        encoding_eligible=True,
        memory_update_eligible=False,
        rejection_reasons=('aspect_ratio_too_wide',),
    )

    tim = TargetIdentityMemory(
        cfg(
            appearance_gallery_min_anchor_similarity=0.75,
        )
    )
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=anchor,
        )
    )
    tim._positive_appearance.trusted_gallery = [
        gallery_pose.copy()
    ]

    enter_global_lost(tim)

    candidate = tr(
        142,
        (430, 210, 610, 390),
        appearance=gallery_pose,
        memory_eligible=False,
        crop_quality=wide_quality,
    )

    gallery_before = [
        value.copy()
        for value in tim._positive_appearance.trusted_gallery
    ]
    adaptive_before = (
        tim._positive_appearance.adaptive_prototype.copy()
    )

    first = tim.update([candidate])

    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    assert not first.control_valid
    assert first.best_score is not None
    assert first.best_score.appearance_evaluated
    assert (
        first.best_score.positive_support_source
        == "trusted_gallery"
    )
    assert not first.positive_memory_updated

    second = tim.update([candidate])

    assert second.state == TargetState.LOCKED
    assert second.target_track_id == 142
    assert second.control_valid
    assert not second.positive_memory_updated

    assert len(
        tim._positive_appearance.trusted_gallery
    ) == len(gallery_before)
    for current, expected in zip(
        tim._positive_appearance.trusted_gallery,
        gallery_before,
    ):
        assert np.array_equal(current, expected)

    assert np.array_equal(
        tim._positive_appearance.adaptive_prototype,
        adaptive_before,
    )


def test_positive_memory_frozen_during_global_reacquisition_probation():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_update_alpha=1.0,
            appearance_trusted_lock_frames_before_update=1,
        )
    )
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    anchor_before = (
        tim._positive_appearance.protected_anchor.copy()
    )
    adaptive_before = (
        tim._positive_appearance.adaptive_prototype.copy()
    )
    gallery_before = [
        value.copy()
        for value in tim._positive_appearance.trusted_gallery
    ]
    lineage_before = (
        tim._positive_appearance.current_lineage_track_id,
        tim._positive_appearance.current_lineage_supported,
        tim._positive_appearance.lineage_trusted,
    )

    first = tim.update(
        [
            tr(
                44,
                (500, 290, 570, 470),
                appearance=target,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    assert not first.control_valid
    assert not first.positive_memory_updated

    # Pending confirmation is side-effect free for authoritative
    # positive identity memory and lineage.
    assert np.array_equal(
        tim._positive_appearance.protected_anchor,
        anchor_before,
    )
    assert np.array_equal(
        tim._positive_appearance.adaptive_prototype,
        adaptive_before,
    )
    assert len(
        tim._positive_appearance.trusted_gallery
    ) == len(gallery_before)
    for current, expected in zip(
        tim._positive_appearance.trusted_gallery,
        gallery_before,
    ):
        assert np.array_equal(current, expected)

    assert (
        tim._positive_appearance.current_lineage_track_id,
        tim._positive_appearance.current_lineage_supported,
        tim._positive_appearance.lineage_trusted,
    ) == lineage_before


def test_operator_clear_prevents_future_global_auto_reacquisition():
    target = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(cfg())
    tim.select(
        tr(
            1,
            (80, 100, 150, 280),
            appearance=target,
        )
    )
    enter_global_lost(tim)

    cleared = tim.clear()

    assert cleared.state == TargetState.NO_TARGET
    assert not cleared.visible
    assert not cleared.control_valid
    assert cleared.target_track_id is None
    assert tim._positive_appearance.protected_anchor is None
    assert tim._positive_appearance.trusted_gallery == []
    assert tim._positive_appearance.adaptive_prototype is None

    output = tim.update(
        [
            tr(
                99,
                (500, 290, 570, 470),
                appearance=target,
            )
        ]
    )

    assert output.state == TargetState.NO_TARGET
    assert not output.visible
    assert not output.control_valid
    assert output.target_track_id is None
    assert output.candidate_track_id is None
    assert output.reason == "no_operator_selected_target"
