"""Transactional safety-gate contracts for TIM-MARS.

These tests isolate structural bypasses and pre-verdict mutations. They do not
change scoring thresholds or define the later hard-negative lifecycle policy.
"""

import numpy as np

from thesis_bringup.tim_mars.target_memory import (
    CandidateScore,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def feature(values):
    """Return a normalised appearance feature vector."""
    array = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array
    return array / norm


def track(
    track_id,
    bbox,
    *,
    score=0.95,
    appearance=None,
    memory_eligible=True,
):
    """Build a candidate track for transactional-gate tests."""
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
        appearance_memory_update_eligible=memory_eligible,
    )


def config(**overrides):
    """Build a minimal configurable target-memory profile."""
    values = {
        'image_width': 640,
        'image_height': 480,
        'max_uncertain_frames': 1,
        'min_confirm_frames_after_reacquire': 1,
        'allow_id_switch_recovery': True,
        'accept_score_locked': 0.52,
        'accept_score_lost': 0.60,
        'appearance_enabled': True,
        'appearance_weight': 0.0,
        'appearance_min_similarity': 0.0,
        'appearance_ambiguous_only': False,
        'appearance_update_alpha': 0.0,
        'appearance_conservative_enabled': False,
        'hard_negative_memory_enabled': False,
        'rank_aware_reacquisition_enabled': False,
        'candidate_belief_enabled': False,
        'absence_recovery_enabled': False,
        'short_gap_new_id_suppression_enabled': False,
    }
    values.update(overrides)
    return TargetMemoryConfig(**values)


def proposal_score(
    track_id,
    *,
    hard_negative=False,
):
    """Build a proposal score for final-gate tests."""
    return CandidateScore(
        track_id=track_id,
        total=0.90,
        iou=0.90,
        distance=0.95,
        scale=1.0,
        confidence=0.95,
        id_bonus=0.0,
        appearance=1.0,
        appearance_used=True,
        appearance_raw=1.0,
        appearance_gate_passed=True,
        geometry_allows_appearance=True,
        hard_negative_similarity=(
            0.82 if hard_negative else 0.0
        ),
        hard_negative_margin=(
            -0.12 if hard_negative else 1.0
        ),
        hard_negative_reject=hard_negative,
    )


def test_candidate_preparation_cannot_bootstrap_legacy_positive_memory():
    """Keep candidate preparation free of positive-memory mutation."""
    target = feature([1.0, 0.0, 0.0])

    memory = TargetIdentityMemory(config())
    memory.select(
        track(
            5,
            (100, 100, 150, 220),
            appearance=None,
        )
    )

    assert memory._m.appearance is None

    prepared = memory._prepare_update_candidates(
        [
            track(
                5,
                (102, 100, 152, 220),
                appearance=target,
            )
        ]
    )

    assert prepared is not None
    assert memory._m.appearance is None


def test_rank_aware_proposal_respects_disabled_id_switch_recovery():
    """Apply ID-switch permission to rank-aware proposals."""
    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.0, 1.0, 0.0])

    memory = TargetIdentityMemory(
        config(
            allow_id_switch_recovery=False,
            rank_aware_reacquisition_enabled=True,
            rank_aware_lost_min_total=0.20,
            rank_aware_lost_min_geom=0.10,
            rank_aware_lost_min_app=0.10,
            rank_aware_lost_app_margin=0.05,
            rank_aware_confirm_frames=1,
        )
    )
    memory.select(
        track(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )

    memory.update([])
    lost = memory.update([])
    assert lost.state == TargetState.LOST

    output = memory.update(
        [
            track(
                6,
                (103, 103, 163, 243),
                appearance=distractor,
            ),
            track(
                11,
                (130, 100, 190, 240),
                appearance=target,
            ),
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.LOST
    assert not output.visible
    assert output.reason == 'id_switch_recovery_disabled'


def test_short_gap_proposal_cannot_bypass_hard_negative_rejection():
    """Apply hard-negative rejection to short-gap proposals."""
    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.8, 0.6, 0.0])

    memory = TargetIdentityMemory(
        config(
            max_uncertain_frames=6,
            hard_negative_memory_enabled=True,
            hard_negative_min_candidate_similarity=0.70,
            hard_negative_max_positive_similarity=1.01,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
            hard_negative_min_geometry=0.20,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
        )
    )
    memory.select(
        track(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )

    locked = memory.update(
        [
            track(
                1,
                (102, 100, 162, 240),
                appearance=target,
            ),
            track(
                2,
                (125, 100, 185, 240),
                appearance=distractor,
            ),
        ]
    )

    assert locked.state == TargetState.LOCKED
    assert len(memory._hard_negative_memory) == 1

    missing = memory.update([])
    assert missing.state == TargetState.UNCERTAIN

    output = memory.update(
        [
            track(
                1,
                (104, 101, 164, 241),
                appearance=distractor,
            )
        ]
    )

    assert output.best_score is not None
    assert output.best_score.hard_negative_reject
    assert output.state in {
        TargetState.UNCERTAIN,
        TargetState.LOST,
    }
    assert not output.visible
    assert output.reason.startswith('hard_negative_reject:')


def test_rejected_proposal_does_not_mutate_acceptance_transaction_state():
    """Keep acceptance-only state unchanged after rejection."""
    target = feature([1.0, 0.0, 0.0])
    contradictory = feature([0.0, 1.0, 0.0])

    memory = TargetIdentityMemory(
        config(
            max_uncertain_frames=6,
            appearance_update_cooldown_after_reacquire_frames=5,
            appearance_conservative_enabled=True,
            appearance_conservative_require_appearance=True,
            appearance_conservative_min_similarity=0.95,
            appearance_conservative_margin=0.05,
            short_gap_same_id_priority_enabled=True,
            short_gap_same_id_grace_frames=8,
            short_gap_same_id_min_total=0.20,
        )
    )
    memory.select(
        track(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )

    memory.update([])

    bbox_before = memory._m.bbox
    appearance_before = memory._m.appearance.copy()
    cooldown_before = (
        memory.appearance_update_cooldown_frames_remaining
    )

    output = memory.update(
        [
            track(
                1,
                (104, 101, 164, 241),
                appearance=contradictory,
            )
        ]
    )

    assert output.reason.startswith(
        'appearance_conservative_reject:'
    )
    assert not output.visible
    assert memory._m.track_id == 1
    assert memory._m.bbox == bbox_before
    assert np.array_equal(
        memory._m.appearance,
        appearance_before,
    )
    assert (
        memory.appearance_update_cooldown_frames_remaining
        == cooldown_before
    )


def test_confirmation_preview_is_side_effect_free_until_verdict_commit():
    """Commit temporal evidence only after the gate returns its verdict."""
    target = feature([1.0, 0.0, 0.0])
    memory = TargetIdentityMemory(
        config(
            candidate_belief_enabled=True,
            candidate_belief_confirm_frames=2,
        )
    )
    memory.select(
        track(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )
    memory._m.state = TargetState.LOST

    candidate = track(
        7,
        (104, 101, 164, 241),
        appearance=target,
    )
    score = proposal_score(7)

    proposal = memory._make_candidate_proposal(
        candidate=candidate,
        score=score,
        all_scores=[score],
        candidates=[candidate],
        proposal_source='normal_selection',
        diagnostic_reason='normal_candidate',
        minimum_total=0.20,
        confirmation_requirements=(
            ('candidate_belief', 2),
        ),
    )

    assert (
        memory._candidate_belief_confirmation
        .confirm_count
        == 0
    )
    assert proposal.confirmations[0].count == 1

    verdict = memory._evaluate_candidate_proposal(
        proposal
    )

    assert verdict.status.value == 'pending'
    assert (
        memory._candidate_belief_confirmation
        .confirm_count
        == 0
    )

    output = memory._finalize_candidate_proposal(
        proposal
    )

    assert output.reason.startswith(
        'candidate_belief_confirmation_pending:'
    )
    assert (
        memory._candidate_belief_confirmation
        .confirm_count
        == 1
    )


def test_rejected_proposal_cannot_advance_temporal_confirmation():
    """Discard temporal evidence when an earlier safety check rejects."""
    target = feature([1.0, 0.0, 0.0])
    memory = TargetIdentityMemory(
        config(
            candidate_belief_enabled=True,
            candidate_belief_confirm_frames=2,
            hard_negative_memory_enabled=True,
            hard_negative_reject_similarity=0.80,
            hard_negative_reject_margin=0.03,
        )
    )
    memory.select(
        track(
            1,
            (100, 100, 160, 240),
            appearance=target,
        )
    )
    memory._m.state = TargetState.LOST

    candidate = track(
        7,
        (104, 101, 164, 241),
        appearance=target,
    )
    score = proposal_score(
        7,
        hard_negative=True,
    )

    proposal = memory._make_candidate_proposal(
        candidate=candidate,
        score=score,
        all_scores=[score],
        candidates=[candidate],
        proposal_source='normal_selection',
        diagnostic_reason='normal_candidate',
        minimum_total=0.20,
        confirmation_requirements=(
            ('candidate_belief', 2),
        ),
    )

    verdict = memory._evaluate_candidate_proposal(
        proposal
    )

    assert verdict.status.value == 'rejected'
    assert (
        memory._candidate_belief_confirmation
        .confirm_count
        == 0
    )

    output = memory._finalize_candidate_proposal(
        proposal
    )

    assert output.reason.startswith(
        'hard_negative_reject:'
    )
    assert (
        memory._candidate_belief_confirmation
        .confirm_count
        == 0
    )
