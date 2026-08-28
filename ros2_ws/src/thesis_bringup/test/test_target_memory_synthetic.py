from thesis_bringup.tim_mars.target_memory import (
    bbox_iou,
    CandidateTrack,
    centre_distance_norm,
    ControlMode,
    scale_similarity,
    score_candidate,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)


def tr(track_id, bbox, score=0.9):
    return CandidateTrack(track_id=track_id, bbox=bbox, score=score)


def cfg(**overrides):
    base = {
        "image_width": 640,
        "image_height": 480,
        "max_uncertain_frames": 2,
    }
    base.update(overrides)
    return TargetMemoryConfig(**base)


def test_bbox_iou_basic_cases():
    assert bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert bbox_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert round(bbox_iou((0, 0, 10, 10), (5, 0, 15, 10)), 3) == 0.333


def test_distance_and_scale_similarity_are_high_for_nearby_same_size_boxes():
    c = cfg()
    a = (100, 100, 150, 220)
    b = (104, 103, 154, 223)
    assert centre_distance_norm(a, b, c.image_width, c.image_height) < 0.02
    assert scale_similarity(a, b, c.scale_sigma) > 0.95


def test_no_target_before_operator_selection():
    tim = TargetIdentityMemory(cfg())
    out = tim.update([tr(1, (100, 100, 150, 220))])
    assert out.state == TargetState.NO_TARGET
    assert out.control_mode == ControlMode.NO_CONTROL
    assert out.target_track_id is None
    assert not out.control_valid


def test_operator_selection_locks_target():
    tim = TargetIdentityMemory(cfg())
    out = tim.select(tr(5, (100, 100, 150, 220), 0.82))
    assert out.state == TargetState.LOCKED
    assert out.target_track_id == 5
    assert out.control_mode == ControlMode.NORMAL
    assert out.control_valid


def test_same_id_update_remains_locked():
    tim = TargetIdentityMemory(cfg())
    tim.select(tr(5, (100, 100, 150, 220), 0.82))
    out = tim.update([tr(5, (105, 102, 155, 222), 0.78)])
    assert out.state == TargetState.LOCKED
    assert out.target_track_id == 5
    assert out.visible
    assert out.reason == "accepted_candidate"


def test_id_switch_recovery_uses_memory_not_raw_tracker_id():
    tim = TargetIdentityMemory(cfg())
    tim.select(tr(5, (100, 100, 150, 220), 0.90))

    # Tracker changes raw ID from 5 to 12, but geometry/scale/confidence still
    # strongly match the selected target memory.
    out = tim.update([tr(12, (104, 102, 154, 222), 0.88)])

    assert out.state == TargetState.REACQUIRED
    assert out.target_track_id == 5
    assert out.candidate_track_id == 12
    assert out.reacquired
    assert not out.visible
    assert out.control_mode == ControlMode.CONFIRM

    out2 = tim.update([tr(12, (108, 104, 158, 224), 0.88)])
    assert out2.state == TargetState.LOCKED
    assert out2.target_track_id == 12
    assert out2.visible


def test_id_switch_recovery_disabled_rejects_different_id():
    tim = TargetIdentityMemory(cfg(allow_id_switch_recovery=False))
    tim.select(tr(5, (100, 100, 150, 220), 0.90))

    out = tim.update([tr(12, (104, 102, 154, 222), 0.88)])

    assert out.state == TargetState.UNCERTAIN
    assert out.target_track_id == 5
    assert not out.visible
    assert out.control_mode == ControlMode.YAW_ONLY
    assert not out.control_valid
    assert out.reason == "id_switch_recovery_disabled"


def test_id_switch_recovery_disabled_still_accepts_same_id():
    tim = TargetIdentityMemory(cfg(allow_id_switch_recovery=False))
    tim.select(tr(5, (100, 100, 150, 220), 0.90))

    out = tim.update([tr(5, (104, 102, 154, 222), 0.88)])

    assert out.state == TargetState.LOCKED
    assert out.target_track_id == 5
    assert out.visible
    assert out.control_valid
    assert out.reason == "accepted_candidate"


def test_id_switch_recovery_disabled_rejects_wrong_id_after_lost():
    tim = TargetIdentityMemory(cfg(allow_id_switch_recovery=False, max_uncertain_frames=1))
    tim.select(tr(5, (100, 100, 150, 220), 0.90))

    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update([tr(36, (103, 101, 153, 221), 0.90)])

    assert out.state == TargetState.LOST
    assert out.target_track_id == 5
    assert not out.visible
    assert not out.control_valid
    assert out.reason == "id_switch_recovery_disabled"


def test_short_missing_period_becomes_uncertain_then_lost():
    tim = TargetIdentityMemory(cfg(max_uncertain_frames=2))
    tim.select(tr(5, (100, 100, 150, 220), 0.9))

    out1 = tim.update([])
    assert out1.state == TargetState.UNCERTAIN
    assert out1.control_mode == ControlMode.YAW_ONLY
    assert out1.frames_since_seen == 1

    out2 = tim.update([])
    assert out2.state == TargetState.UNCERTAIN
    assert out2.frames_since_seen == 2

    out3 = tim.update([])
    assert out3.state == TargetState.LOST
    assert out3.control_mode == ControlMode.HOVER
    assert out3.frames_since_seen == 3


def test_reacquire_after_temporary_loss():
    tim = TargetIdentityMemory(cfg(max_uncertain_frames=1))
    tim.select(tr(5, (100, 100, 150, 220), 0.9))
    tim.update([])
    lost = tim.update([])
    assert lost.state == TargetState.LOST

    out = tim.update([tr(9, (103, 101, 153, 221), 0.90)])
    assert out.state == TargetState.REACQUIRED
    assert out.reacquired
    assert out.target_track_id == 5
    assert out.candidate_track_id == 9
    assert not out.visible

    committed = tim.update(
        [tr(9, (105, 102, 155, 222), 0.90)]
    )
    assert committed.state == TargetState.LOCKED
    assert committed.target_track_id == 9
    assert committed.visible


def test_ambiguous_best_candidate_is_rejected_when_not_same_id():
    # Make ambiguity sensitivity high for this synthetic case.
    tim = TargetIdentityMemory(cfg(ambiguity_margin=0.15))
    tim.select(tr(5, (100, 100, 150, 220), 0.90))

    # Force memory to be uncertain so candidates with new IDs compete.
    tim.update([])

    out = tim.update([
        tr(10, (103, 100, 153, 220), 0.90),
        tr(11, (106, 100, 156, 220), 0.89),
    ])

    assert out.state == TargetState.UNCERTAIN
    assert out.target_track_id == 5  # do not switch on ambiguous evidence
    assert out.best_score is not None
    assert out.best_score.ambiguous
    assert out.reason == "ambiguous_best_candidate"


def test_far_candidate_below_threshold_is_rejected():
    tim = TargetIdentityMemory(cfg())
    tim.select(tr(5, (100, 100, 150, 220), 0.9))

    out = tim.update([tr(99, (450, 300, 510, 430), 0.95)])
    assert out.state == TargetState.UNCERTAIN
    assert out.target_track_id == 5
    assert out.reason.startswith("best_below_threshold")


def test_scoring_prefers_memory_consistent_candidate_over_higher_confidence_far_candidate():
    c = cfg()
    ref = (100, 100, 150, 220)
    near = tr(2, (103, 101, 153, 221), 0.70)
    far = tr(3, (400, 300, 460, 430), 0.99)

    s_near = score_candidate(ref, near, current_track_id=None, cfg=c)
    s_far = score_candidate(ref, far, current_track_id=None, cfg=c)

    assert s_near.total > s_far.total


def test_clear_returns_to_no_target():
    tim = TargetIdentityMemory(cfg())
    tim.select(tr(5, (100, 100, 150, 220), 0.9))
    out = tim.clear()
    assert out.state == TargetState.NO_TARGET
    assert out.control_mode == ControlMode.NO_CONTROL
    assert out.target_track_id is None


def test_output_exposes_candidate_belief_when_publication_is_suppressed():
    tim = TargetIdentityMemory(
        cfg(
            allow_id_switch_recovery=False,
            max_uncertain_frames=1,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), score=0.95))

    tim.update([])
    tim.update([])
    assert tim.state == TargetState.LOST

    out = tim.update([
        tr(7, (102, 100, 162, 240), score=0.95),
    ])

    assert out.visible is False
    assert out.target_track_id == 1
    assert out.candidate_track_id == 7
    assert out.candidate_score > 0.0
    assert out.publication_suppressed_reason == "id_switch_recovery_disabled"


def test_output_has_no_suppression_reason_when_visible():
    tim = TargetIdentityMemory(cfg())
    tim.select(tr(1, (100, 100, 160, 240), score=0.95))

    out = tim.update([
        tr(1, (102, 100, 162, 240), score=0.95),
    ])

    assert out.visible is True
    assert out.target_track_id == 1
    assert out.candidate_track_id == 1
    assert out.candidate_score > 0.0
    assert out.publication_suppressed_reason == ""


def test_candidate_belief_buffer_suppresses_new_id_until_confirmed():
    tim = TargetIdentityMemory(
        cfg(
            candidate_belief_enabled=True,
            candidate_belief_min_score=0.20,
            candidate_belief_confirm_frames=2,
            allow_id_switch_recovery=True,
            max_uncertain_frames=1,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), score=0.95))

    tim.update([])
    tim.update([])
    assert tim.state == TargetState.LOST

    candidate = [tr(7, (102, 100, 162, 240), score=0.95)]

    first = tim.update(candidate)
    assert first.visible is False
    assert first.target_track_id == 1
    assert first.candidate_track_id == 7
    assert first.publication_suppressed_reason.startswith("candidate_belief_confirmation_pending:")

    second = tim.update(candidate)
    assert second.visible
    assert second.target_track_id == 7
    assert second.candidate_track_id == 7
    assert second.state == TargetState.LOCKED
    assert second.reacquired
    assert second.publication_suppressed_reason == ""


def test_candidate_belief_disabled_still_uses_recovery_persistence():
    tim = TargetIdentityMemory(
        cfg(
            candidate_belief_enabled=False,
            allow_id_switch_recovery=True,
            max_uncertain_frames=1,
        )
    )
    tim.select(tr(1, (100, 100, 160, 240), score=0.95))

    tim.update([])
    tim.update([])
    assert tim.state == TargetState.LOST

    out = tim.update([
        tr(7, (102, 100, 162, 240), score=0.95),
    ])

    assert not out.visible
    assert out.target_track_id == 1
    assert out.candidate_track_id == 7
    assert out.state == TargetState.REACQUIRED
    assert out.reacquired
    assert out.publication_suppressed_reason.startswith(
        "recovery_persistence_pending:"
    )

    committed = tim.update([
        tr(7, (104, 101, 164, 241), score=0.95),
    ])

    assert committed.visible
    assert committed.target_track_id == 7
    assert committed.candidate_track_id == 7
    assert committed.state == TargetState.LOCKED
    assert committed.reacquired
    assert committed.publication_suppressed_reason == ""


def test_short_gap_new_id_is_suppressed_and_same_id_return_is_preferred():
    cfg = TargetMemoryConfig(
        image_width=640,
        image_height=480,
        max_uncertain_frames=6,
        appearance_conservative_enabled=False,
        accept_score_locked=0.45,
        short_gap_same_id_grace_frames=4,
        short_gap_same_id_min_total=0.20,
        short_gap_new_id_suppression_enabled=True,
        short_gap_new_id_allow_total=0.70,
        short_gap_same_id_priority_enabled=True,
    )
    tim = TargetIdentityMemory(cfg)

    tim.select(tr(1, (360, 180, 390, 290), score=0.90))

    # The old ID disappears briefly and a nearby distractor becomes plausible.
    # TIM must not immediately rewrite memory from id=1 to id=2.
    for _ in range(3):
        out = tim.update([tr(2, (365, 235, 415, 355), score=0.80)])
        assert out.target_track_id == 1
        assert out.reason.startswith("short_gap_new_id_suppressed:")

    # When the original ID returns during the short gap, prefer it even if the
    # distractor is still nearby and has higher detector confidence.
    out = tim.update([
        tr(2, (366, 236, 416, 356), score=0.80),
        tr(1, (378, 182, 412, 282), score=0.50),
    ])

    assert out.target_track_id == 1
    assert out.best_score is not None
    assert out.best_score.track_id == 1
