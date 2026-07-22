import numpy as np

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity
from thesis_bringup.tim_mars.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def feat(values):
    arr = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr
    return arr / norm


def tr(
    track_id,
    bbox,
    score=0.9,
    appearance=None,
    memory_eligible=True,
):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
        appearance_memory_update_eligible=memory_eligible,
    )


def cfg(**overrides):
    base = {
        "image_width": 640,
        "image_height": 480,
        "max_uncertain_frames": 1,
    }
    base.update(overrides)
    return TargetMemoryConfig(**base)


def test_appearance_disabled_does_not_affect_matching():
    target_feat = feat([1.0, 0.0, 0.0])
    other_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=False,
            appearance_weight=1.0,
            appearance_ambiguous_only=False,
            ambiguity_margin=0.001,
        )
    )
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=target_feat))

    out = tim.update(
        [
            tr(10, (102, 100, 152, 220), 0.90, appearance=other_feat),
            tr(11, (118, 100, 168, 220), 0.90, appearance=target_feat),
        ]
    )

    assert out.best_score is not None
    assert out.best_score.track_id == 10
    assert out.best_score.appearance == 0.0
    assert not out.best_score.appearance_used


def test_appearance_breaks_geometry_tie_for_correct_candidate():
    target_feat = feat([1.0, 0.0, 0.0])
    other_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_min_similarity=0.30,
            appearance_ambiguous_only=False,
            ambiguity_margin=0.001,
        )
    )
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=target_feat))

    out = tim.update(
        [
            tr(10, (102, 100, 152, 220), 0.90, appearance=other_feat),
            tr(11, (118, 100, 168, 220), 0.90, appearance=target_feat),
        ]
    )

    assert out.best_score is not None
    assert out.best_score.track_id == 11
    assert out.best_score.appearance_used
    assert out.target_track_id == 11
    assert out.state == TargetState.REACQUIRED


def test_appearance_memory_does_not_update_while_lost_or_reacquired():
    target_feat = feat([1.0, 0.0, 0.0])
    new_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_ambiguous_only=False,
            appearance_update_alpha=0.50,
            max_uncertain_frames=1,
        )
    )
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=target_feat))

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update([tr(9, (103, 101, 153, 221), 0.90, appearance=new_feat)])

    assert out.state == TargetState.REACQUIRED
    assert cosine_similarity(tim._m.appearance, target_feat) > 0.99
    assert cosine_similarity(tim._m.appearance, new_feat) < 0.01


def test_appearance_cannot_rescue_impossible_geometry():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_ambiguous_only=False,
        )
    )
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=target_feat))

    out = tim.update([tr(99, (450, 300, 510, 430), 0.95, appearance=target_feat)])

    assert out.state == TargetState.UNCERTAIN
    assert out.target_track_id == 5
    assert out.reason.startswith("best_below_threshold")


def test_appearance_memory_updates_only_when_locked():
    target_feat = feat([1.0, 0.0, 0.0])
    updated_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_ambiguous_only=False,
            appearance_update_alpha=0.50,
        )
    )
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=target_feat))

    before = tim._m.appearance.copy()
    out = tim.update([tr(5, (104, 102, 154, 222), 0.95, appearance=updated_feat)])
    after = tim._m.appearance

    assert out.state == TargetState.LOCKED
    assert not np.allclose(before, after)
    assert cosine_similarity(after, updated_feat) > cosine_similarity(before, updated_feat)


def test_positive_appearance_bootstraps_after_selection_without_feature():
    target_feat = feat([1.0, 0.0, 0.0])
    other_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_min_similarity=0.30,
            appearance_ambiguous_only=False,
        )
    )

    # Operator selection happened before MARS produced an embedding.
    tim.select(tr(5, (100, 100, 150, 220), 0.9, appearance=None))
    assert tim._m.appearance is None

    out = tim.update(
        [
            tr(5, (102, 100, 152, 220), 0.90, appearance=target_feat),
            tr(6, (118, 100, 168, 220), 0.90, appearance=other_feat),
        ]
    )

    assert tim._m.appearance is not None
    assert out.best_score is not None
    assert out.best_score.appearance_raw > 0.90


def test_hard_negative_memory_rejects_negative_like_candidate():
    target_feat = feat([1.0, 0.0, 0.0])
    negative_feat = feat([0.6, 0.8, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_min_similarity=0.30,
            appearance_ambiguous_only=False,
            hard_negative_memory_enabled=True,
            hard_negative_min_candidate_similarity=0.50,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.08,
            hard_negative_min_geometry=0.20,
        )
    )

    tim.select(tr(1, (100, 100, 160, 240), 0.90, appearance=target_feat))

    # The first trusted observation stages non-rejecting evidence.
    staged = tim.update(
        [
            tr(1, (102, 100, 162, 240), 0.90, appearance=target_feat),
            tr(2, (125, 100, 185, 240), 0.90, appearance=negative_feat),
        ]
    )

    assert staged.state == TargetState.LOCKED
    assert len(tim._hard_negative_memory) == 0
    assert len(tim._hard_negative_memory.pending_entries) == 1

    # A second trusted temporal observation promotes the distractor.
    learned = tim.update(
        [
            tr(1, (103, 100, 163, 240), 0.90, appearance=target_feat),
            tr(2, (126, 100, 186, 240), 0.90, appearance=negative_feat),
        ]
    )

    assert learned.state == TargetState.LOCKED
    assert len(tim._hard_negative_memory) == 1
    assert tim._hard_negative_memory.pending_entries == ()

    # The selected tracker ID now looks like the learned negative.
    # This models same-ID tracker drift after a crossing.
    out = tim.update(
        [
            tr(1, (104, 100, 164, 240), 0.90, appearance=negative_feat),
        ]
    )

    assert out.best_score is not None
    assert out.best_score.hard_negative_similarity > 0.95
    assert out.best_score.hard_negative_reject
    assert out.reason.startswith("hard_negative_reject")
    assert not out.control_valid


def test_operator_selection_ignores_ineligible_appearance():
    target_feat = feat([1.0, 0.0, 0.0])
    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
        )
    )

    tim.select(
        tr(
            5,
            (100, 100, 150, 220),
            appearance=target_feat,
            memory_eligible=False,
        )
    )

    assert tim._m.appearance is None


def test_ineligible_appearance_cannot_bootstrap_positive_memory():
    target_feat = feat([1.0, 0.0, 0.0])
    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
        )
    )

    tim.select(
        tr(
            5,
            (100, 100, 150, 220),
            appearance=None,
        )
    )

    tim.update(
        [
            tr(
                5,
                (102, 100, 152, 220),
                appearance=target_feat,
                memory_eligible=False,
            )
        ]
    )

    assert tim._m.appearance is None


def test_ineligible_locked_crop_cannot_update_positive_memory():
    target_feat = feat([1.0, 0.0, 0.0])
    new_feat = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_update_alpha=0.50,
        )
    )

    tim.select(
        tr(
            5,
            (100, 100, 150, 220),
            appearance=target_feat,
        )
    )

    before = tim._m.appearance.copy()

    output = tim.update(
        [
            tr(
                5,
                (104, 102, 154, 222),
                appearance=new_feat,
                memory_eligible=False,
            )
        ]
    )

    assert output.state == TargetState.LOCKED
    assert np.allclose(tim._m.appearance, before)


def test_id_switch_rejects_missing_candidate_appearance_when_enabled():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.UNCERTAIN
    assert not output.visible
    assert not output.control_valid
    assert (
        output.reason
        == "id_switch_recovery_reject:no_candidate_appearance"
    )


def test_same_id_continuity_allows_missing_candidate_appearance():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    output = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOCKED
    assert output.visible
    assert output.control_valid
    assert output.reason == "accepted_candidate"


def test_appearance_disabled_preserves_geometry_only_id_switch():
    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=None,
        )
    )

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 2
    assert output.state == TargetState.REACQUIRED
    assert output.reacquired


def test_id_switch_rejects_low_appearance_similarity():
    target_feat = feat([1.0, 0.0, 0.0])
    low_match = feat([0.70, 0.714142842, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=True,
            id_switch_min_appearance_similarity=0.78,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                score=0.95,
                appearance=low_match,
            )
        ]
    )

    assert output.best_score is not None
    assert 0.69 < output.best_score.appearance_raw < 0.71
    assert not output.best_score.appearance_used
    assert output.target_track_id == 1
    assert output.state == TargetState.UNCERTAIN
    assert not output.visible
    assert (
        output.reason
        == "id_switch_recovery_reject:"
        "appearance 0.700<0.780"
    )


def test_id_switch_accepts_high_raw_similarity_when_not_blended():
    target_feat = feat([1.0, 0.0, 0.0])
    high_match = feat([0.85, 0.526782688, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=True,
            id_switch_min_appearance_similarity=0.78,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                score=0.95,
                appearance=high_match,
            )
        ]
    )

    assert output.best_score is not None
    assert 0.84 < output.best_score.appearance_raw < 0.86
    assert not output.best_score.appearance_used
    assert output.target_track_id == 2
    assert output.state == TargetState.REACQUIRED
    assert output.reacquired


def test_same_id_reacquisition_rejects_missing_appearance_after_uncertain():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_same_id_priority_enabled=False,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    missing = tim.update([])
    assert missing.state == TargetState.UNCERTAIN

    output = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOST
    assert output.frames_since_seen == 2
    assert not output.visible
    assert not output.control_valid
    assert (
        output.reason
        == "same_id_reacquisition_reject:"
        "no_candidate_appearance"
    )


def test_short_gap_same_id_priority_requires_appearance_after_uncertain():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    tim.update([])

    output = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOST
    assert output.frames_since_seen == 2
    assert not output.visible
    assert (
        output.reason
        == "same_id_reacquisition_reject:"
        "no_candidate_appearance"
    )


def test_same_id_reacquisition_rejects_missing_appearance_after_lost():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    tim.update([])
    lost = tim.update([])

    assert lost.state == TargetState.LOST

    output = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOST
    assert output.frames_since_seen == 3
    assert not output.visible
    assert not output.control_valid
    assert (
        output.reason
        == "same_id_reacquisition_reject:"
        "no_candidate_appearance"
    )


def test_same_id_reacquisition_with_appearance_remains_allowed():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    tim.update([])

    output = tim.update(
        [
            tr(
                1,
                (104, 101, 164, 241),
                score=0.95,
                appearance=target_feat,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.REACQUIRED
    assert output.reacquired
    assert not output.visible


def test_evidence_backed_reacquired_id_can_confirm_without_fresh_appearance():
    target_feat = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(
        cfg(
            appearance_enabled=True,
            appearance_ambiguous_only=False,
            id_switch_min_appearance_similarity=0.78,
            appearance_conservative_enabled=False,
            hard_negative_memory_enabled=False,
            rank_aware_reacquisition_enabled=False,
            candidate_belief_enabled=False,
            absence_recovery_enabled=False,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
            short_gap_new_id_suppression_enabled=False,
        )
    )

    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=target_feat,
        )
    )

    tim.update([])

    reacquired = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                score=0.95,
                appearance=target_feat,
            )
        ]
    )

    assert reacquired.target_track_id == 2
    assert reacquired.state == TargetState.REACQUIRED
    assert reacquired.reacquired
    assert not reacquired.visible
    assert not reacquired.control_valid

    output = tim.update(
        [
            tr(
                2,
                (108, 103, 168, 243),
                score=0.95,
                appearance=None,
            )
        ]
    )

    assert output.target_track_id == 2
    assert output.state == TargetState.LOCKED
    assert output.frames_since_seen == 0
    assert output.visible
    assert output.control_valid
    assert output.reason == "accepted_candidate"
