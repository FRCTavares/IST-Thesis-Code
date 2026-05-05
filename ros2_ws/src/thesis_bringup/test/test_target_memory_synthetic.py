from thesis_bringup.target_memory import (
    CandidateTrack,
    ControlMode,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
    bbox_iou,
    centre_distance_norm,
    scale_similarity,
    score_candidate,
)


def tr(track_id, bbox, score=0.9):
    return CandidateTrack(track_id=track_id, bbox=bbox, score=score)


def cfg(**overrides):
    base = dict(image_width=640, image_height=480, max_uncertain_frames=2, max_lost_frames=8)
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
    assert out.target_track_id == 12
    assert out.reacquired
    assert out.control_mode == ControlMode.CONFIRM

    out2 = tim.update([tr(12, (108, 104, 158, 224), 0.88)])
    assert out2.state == TargetState.LOCKED
    assert out2.target_track_id == 12


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
    assert out.target_track_id == 9


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
