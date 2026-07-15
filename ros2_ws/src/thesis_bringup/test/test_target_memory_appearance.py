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


def tr(track_id, bbox, score=0.9, appearance=None):
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=score,
        appearance=appearance,
    )


def cfg(**overrides):
    base = dict(
        image_width=640,
        image_height=480,
        max_uncertain_frames=1,
    )
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

    # Trusted lock with a nearby non-selected candidate, learns negative memory.
    tim.update(
        [
            tr(1, (102, 100, 162, 240), 0.90, appearance=target_feat),
            tr(2, (125, 100, 185, 240), 0.90, appearance=negative_feat),
        ]
    )

    assert len(tim._hard_negative_memory) >= 1

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
