from thesis_bringup.tim_mars.reacquisition_policy import (
    CandidatePersistenceTracker,
)


def observe(
    tracker,
    track_id,
    *,
    required=3,
    bbox=(10, 20, 30, 40),
):
    return tracker.observe(
        track_id,
        required_observations=required,
        source="recovery_persistence",
        bbox=bbox,
        score=0.8,
    )


def test_preview_is_side_effect_free():
    tracker = CandidatePersistenceTracker()

    assert tracker.preview(7) == 1
    assert tracker.candidate_id is None
    assert tracker.observation_count == 0
    assert not tracker.pending


def test_repeated_candidate_advances_observations():
    tracker = CandidatePersistenceTracker()

    assert observe(tracker, 7) == 1
    assert observe(
        tracker,
        7,
        bbox=(11, 21, 31, 41),
    ) == 2

    assert tracker.candidate_id == 7
    assert tracker.observation_count == 2
    assert tracker.required_observations == 3
    assert tracker.bbox == (11, 21, 31, 41)
    assert not tracker.confirmed


def test_candidate_change_restarts_observations():
    tracker = CandidatePersistenceTracker()

    observe(tracker, 7)
    observe(tracker, 7)

    assert observe(tracker, 8) == 1
    assert tracker.candidate_id == 8
    assert tracker.observation_count == 1


def test_tracker_reports_confirmation_at_threshold():
    tracker = CandidatePersistenceTracker()

    observe(tracker, 7, required=2)
    assert not tracker.confirmed

    observe(tracker, 7, required=2)
    assert tracker.confirmed


def test_reset_clears_pending_candidate_metadata():
    tracker = CandidatePersistenceTracker()
    observe(tracker, 7, required=1)

    tracker.reset()

    assert tracker.candidate_id is None
    assert tracker.observation_count == 0
    assert tracker.required_observations == 0
    assert tracker.source == ""
    assert tracker.bbox is None
    assert tracker.score == 0.0
    assert not tracker.pending
    assert not tracker.confirmed


def test_legacy_confirm_count_alias_matches_observation_count():
    tracker = CandidatePersistenceTracker()

    tracker.observe(7)

    assert tracker.confirm_count == 1
    assert tracker.observation_count == 1

    tracker.confirm_count = 4

    assert tracker.observation_count == 4


def test_legacy_observe_call_remains_supported_temporarily():
    tracker = CandidatePersistenceTracker()

    assert tracker.observe(7) == 1
    assert tracker.observe(7) == 2
    assert tracker.confirm_count == 2


def test_identity_evidence_is_retained_for_same_candidate():
    tracker = CandidatePersistenceTracker()

    tracker.observe(
        7,
        required_observations=2,
        identity_evidence_confirmed=True,
    )
    tracker.observe(
        7,
        required_observations=2,
        identity_evidence_confirmed=False,
    )

    assert tracker.identity_evidence_confirmed
    assert tracker.confirmed


def test_identity_evidence_does_not_transfer_to_new_candidate():
    tracker = CandidatePersistenceTracker()

    tracker.observe(
        7,
        identity_evidence_confirmed=True,
    )
    tracker.observe(
        8,
        identity_evidence_confirmed=False,
    )

    assert tracker.candidate_id == 8
    assert not tracker.identity_evidence_confirmed


def test_reset_clears_identity_evidence():
    tracker = CandidatePersistenceTracker()

    tracker.observe(
        7,
        identity_evidence_confirmed=True,
    )
    tracker.reset()

    assert not tracker.identity_evidence_confirmed
