"""P1.4 contracts for protected and adaptive appearance memory."""

import numpy as np

from thesis_bringup.tim_mars.appearance_memory import (
    cosine_similarity,
)
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


def tr(
    track_id,
    bbox,
    *,
    score=0.95,
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


def protected_cfg(**overrides):
    values = {
        "image_width": 640,
        "image_height": 480,
        "max_uncertain_frames": 6,
        "min_confirm_frames_after_reacquire": 1,
        "allow_id_switch_recovery": True,
        "accept_score_locked": 0.52,
        "appearance_enabled": True,
        "appearance_weight": 0.12,
        "appearance_min_similarity": 0.35,
        "appearance_ambiguous_only": True,
        "appearance_update_alpha": 0.50,
        "appearance_update_cooldown_after_reacquire_frames": 0,
        "appearance_protected_memory_enabled": True,
        "appearance_trusted_gallery_max_entries": 4,
        "appearance_trusted_lock_frames_before_update": 2,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": False,
        "rank_aware_reacquisition_enabled": False,
        "candidate_belief_enabled": False,
        "absence_recovery_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
    }
    values.update(overrides)
    return TargetMemoryConfig(**values)


def test_geometrically_stable_wrong_reacquisition_cannot_replace_anchor():
    selected = feat([1.0, 0.0, 0.0])
    wrong = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.0,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected,
        )
    )

    anchor_before = (
        tim._positive_appearance
        .protected_anchor
        .copy()
    )
    adaptive_before = (
        tim._positive_appearance
        .adaptive_prototype
        .copy()
    )

    first = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=wrong,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert first.target_track_id == 1
    assert first.candidate_track_id == 2
    assert not first.visible
    assert not first.positive_memory_updated

    committed = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=wrong,
            )
        ]
    )

    assert committed.state == TargetState.LOCKED
    assert committed.target_track_id == 2
    assert not committed.positive_memory_updated

    assert np.array_equal(
        tim._positive_appearance.protected_anchor,
        anchor_before,
    )
    assert np.array_equal(
        tim._positive_appearance.adaptive_prototype,
        adaptive_before,
    )
    assert cosine_similarity(
        tim._positive_appearance.protected_anchor,
        selected,
    ) > 0.99
    assert cosine_similarity(
        tim._positive_appearance.protected_anchor,
        wrong,
    ) < 0.01


def test_candidate_scoring_cannot_bootstrap_protected_anchor():
    selected = feat([1.0, 0.0, 0.0])

    tim = TargetIdentityMemory(protected_cfg())
    tim.select(
        tr(
            5,
            (100, 100, 150, 220),
            appearance=None,
        )
    )

    assert (
        tim._positive_appearance.protected_anchor
        is None
    )

    prepared = tim._prepare_update_candidates(
        [
            tr(
                5,
                (102, 100, 152, 220),
                appearance=selected,
            )
        ]
    )

    assert prepared is not None
    assert (
        tim._positive_appearance.protected_anchor
        is None
    )

    output = tim.update(
        [
            tr(
                5,
                (102, 100, 152, 220),
                appearance=selected,
            )
        ]
    )

    assert output.state == TargetState.LOCKED
    assert output.positive_memory_updated
    assert (
        output.positive_memory_update_reason
        == "protected_anchor_bootstrap"
    )
    assert np.array_equal(
        tim._positive_appearance.protected_anchor,
        selected,
    )

    event = output.positive_memory_bootstrap_event
    assert event is not None
    assert event.action == "protected_anchor_bootstrap"
    assert event.track_id == 5
    assert event.accepted_bbox == (102, 100, 152, 220)
    assert event.memory_update_eligible
    assert not event.ambiguous
    assert not event.hard_negative_reject
    assert event.operator_track_id == 5
    assert event.current_lineage_track_id == 5
    assert event.current_lineage_supported
    assert event.frame_id is None
    assert event.track_timestamp_ns is None


def test_reacquired_same_id_cannot_bootstrap_first_protected_anchor():
    """An unsupported same-ID return must not define operator appearance.

    The operator selects a target before an embedding is available. After
    continuity is broken, the same tracker ID may belong to another physical
    person. Its first embedding must not become the immutable operator anchor.
    """
    hijacker = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
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
            5,
            (100, 100, 150, 220),
            appearance=None,
        )
    )

    assert tim._positive_appearance.protected_anchor is None
    assert tim._positive_appearance.current_lineage_supported

    missed = tim.update([])

    assert missed.state == TargetState.UNCERTAIN
    assert tim._positive_appearance.protected_anchor is None

    output = None
    for offset in (2, 4, 6):
        output = tim.update(
            [
                tr(
                    5,
                    (
                        100 + offset,
                        100,
                        150 + offset,
                        220,
                    ),
                    appearance=hijacker,
                )
            ]
        )
        if output.state == TargetState.LOCKED:
            break

    assert output is not None
    assert output.state == TargetState.LOCKED

    # Required Issue #15 behaviour: accepted tracker continuity may remain
    # controller-visible, but an unsupported lineage cannot define immutable
    # operator identity memory.
    assert not tim._positive_appearance.current_lineage_supported
    assert tim._positive_appearance.protected_anchor is None
    assert tim._positive_appearance.adaptive_prototype is None
    assert not output.positive_memory_updated
    assert output.positive_memory_bootstrap_event is None


def test_adaptive_similarity_cannot_authorize_id_switch():
    selected = feat([1.0, 0.0, 0.0])
    adaptive_only_match = feat([0.0, 1.0, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected,
        )
    )

    tim._positive_appearance.adaptive_prototype = (
        adaptive_only_match.copy()
    )

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=adaptive_only_match,
            )
        ]
    )

    assert output.best_score is not None
    assert (
        output.best_score.protected_anchor_similarity
        < 0.01
    )
    assert output.best_score.adaptive_similarity > 0.99
    assert output.best_score.positive_similarity < 0.01
    assert (
        output.best_score.positive_support_source
        == "none"
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.UNCERTAIN
    assert output.reason.startswith(
        "id_switch_recovery_reject:appearance"
    )


def test_protected_anchor_records_id_switch_support_source():
    selected = feat([1.0, 0.0, 0.0])
    same_identity_new_pose = feat(
        [0.85, 0.526782688, 0.0]
    )

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=selected,
        )
    )

    first = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=same_identity_new_pose,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert first.target_track_id == 1
    assert first.candidate_track_id == 2
    assert not first.visible
    assert first.acceptance_memory_source == "none"
    assert first.best_score is not None
    assert (
        first.best_score.positive_support_source
        == "protected_anchor"
    )
    assert (
        0.84
        < first.best_score.protected_anchor_similarity
        < 0.86
    )
    assert not first.positive_memory_updated

    committed = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=same_identity_new_pose,
            )
        ]
    )

    assert committed.state == TargetState.LOCKED
    assert committed.target_track_id == 2
    assert committed.visible
    assert (
        committed.acceptance_memory_source
        == "protected_anchor"
    )


def test_gallery_supported_switch_requires_anchor_agreement():
    anchor = feat([1.0, 0.0, 0.0])
    gallery_pose = feat([0.60, 0.80, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
            appearance_gallery_min_anchor_similarity=0.75,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=anchor,
        )
    )
    tim._positive_appearance.trusted_gallery = [
        gallery_pose.copy()
    ]

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=gallery_pose,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.UNCERTAIN
    assert output.best_score is not None
    assert (
        output.best_score.positive_support_source
        == "trusted_gallery"
    )
    assert (
        output.best_score.trusted_gallery_similarity
        > 0.99
    )
    assert (
        0.59
        < output.best_score.protected_anchor_similarity
        < 0.61
    )
    assert output.reason.startswith(
        "protected_gallery_reacquisition_reject:"
        "anchor"
    )


def test_gallery_supported_switch_rejects_untrusted_crop():
    anchor = feat([1.0, 0.0, 0.0])
    gallery_pose = feat([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
            appearance_gallery_min_anchor_similarity=0.75,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=anchor,
        )
    )
    tim._positive_appearance.trusted_gallery = [
        gallery_pose.copy()
    ]

    output = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=gallery_pose,
                memory_eligible=False,
            )
        ]
    )

    assert output.target_track_id == 1
    assert output.state == TargetState.UNCERTAIN
    assert output.reason == (
        "protected_gallery_reacquisition_reject:"
        "untrusted_crop"
    )


def test_gallery_supported_switch_passes_with_anchor_agreement():
    anchor = feat([1.0, 0.0, 0.0])
    gallery_pose = feat([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
            appearance_gallery_min_anchor_similarity=0.75,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=anchor,
        )
    )
    tim._positive_appearance.trusted_gallery = [
        gallery_pose.copy()
    ]

    first = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=gallery_pose,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert first.target_track_id == 1
    assert first.candidate_track_id == 2
    assert not first.visible
    assert first.acceptance_memory_source == "none"
    assert first.best_score is not None
    assert (
        first.best_score.positive_support_source
        == "trusted_gallery"
    )
    assert (
        first.best_score.protected_anchor_similarity
        > 0.79
    )
    assert not first.positive_memory_updated

    committed = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=gallery_pose,
            )
        ]
    )

    assert committed.state == TargetState.LOCKED
    assert committed.target_track_id == 2
    assert committed.visible
    assert (
        committed.acceptance_memory_source
        == "trusted_gallery"
    )


def test_direct_anchor_support_is_not_subject_to_gallery_floor():
    anchor = feat([1.0, 0.0, 0.0])
    anchor_match = feat([0.85, 0.526782688, 0.0])

    tim = TargetIdentityMemory(
        protected_cfg(
            id_switch_min_appearance_similarity=0.78,
            appearance_gallery_min_anchor_similarity=0.99,
        )
    )
    tim.select(
        tr(
            1,
            (100, 100, 160, 240),
            appearance=anchor,
        )
    )

    first = tim.update(
        [
            tr(
                2,
                (104, 101, 164, 241),
                appearance=anchor_match,
            )
        ]
    )

    assert first.state == TargetState.REACQUIRED
    assert first.target_track_id == 1
    assert first.candidate_track_id == 2
    assert not first.visible
    assert first.acceptance_memory_source == "none"
    assert first.best_score is not None
    assert (
        first.best_score.positive_support_source
        == "protected_anchor"
    )

    committed = tim.update(
        [
            tr(
                2,
                (106, 102, 166, 242),
                appearance=anchor_match,
            )
        ]
    )

    assert committed.state == TargetState.LOCKED
    assert committed.target_track_id == 2
    assert committed.visible
    assert (
        committed.acceptance_memory_source
        == "protected_anchor"
    )
