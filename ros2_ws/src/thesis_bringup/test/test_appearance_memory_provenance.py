"""P1.4 gallery bounds and hard-negative provenance contracts."""

import numpy as np

from thesis_bringup.tim_mars.appearance_memory import (
    cosine_similarity,
)
from thesis_bringup.tim_mars.hard_negative_memory import (
    HardNegativeMemory,
)
from thesis_bringup.tim_mars.positive_appearance_memory import (
    PositiveAppearanceMemory,
)
from thesis_bringup.tim_mars.types import (
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)


def feat(values):
    array = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array
    return array / norm


def tr(track_id, appearance):
    return CandidateTrack(
        track_id=track_id,
        bbox=(100.0, 100.0, 160.0, 240.0),
        score=0.95,
        appearance=appearance,
        appearance_memory_update_eligible=True,
    )


def candidate_score(track_id, positive_similarity):
    return CandidateScore(
        track_id=track_id,
        total=0.80,
        iou=0.40,
        distance=0.80,
        scale=0.80,
        confidence=0.95,
        id_bonus=0.0,
        appearance_raw=float(positive_similarity),
        geometry_allows_appearance=True,
    )


def negative_cfg(**overrides):
    values = dict(
        appearance_enabled=True,
        hard_negative_memory_enabled=True,
        hard_negative_max_entries=2,
        hard_negative_update_alpha=0.50,
        hard_negative_min_candidate_similarity=0.70,
        hard_negative_max_positive_similarity=0.95,
        hard_negative_reject_similarity=0.80,
        hard_negative_reject_margin=0.03,
        hard_negative_min_geometry=0.20,
    )
    values.update(overrides)
    return TargetMemoryConfig(**values)


def learn_negative(
    memory,
    *,
    selected,
    candidate,
    candidate_track_id,
    cfg,
):
    similarity = cosine_similarity(
        selected,
        candidate,
    )
    memory.update(
        candidates=[
            tr(1, selected),
            tr(candidate_track_id, candidate),
        ],
        scores_sorted=[
            candidate_score(
                candidate_track_id,
                similarity,
            )
        ],
        selected_track_id=1,
        positive_appearance=selected,
        state=TargetState.LOCKED,
        cfg=cfg,
    )


def test_trusted_gallery_is_bounded_and_anchor_is_immutable():
    anchor = feat([1.0, 0.0, 0.0])
    pose_a = feat([0.8, 0.6, 0.0])
    pose_b = feat([0.8, 0.0, 0.6])
    pose_c = feat([0.8, -0.6, 0.0])

    memory = PositiveAppearanceMemory()
    assert memory.select_operator(
        track_id=1,
        appearance=anchor,
    )

    anchor_before = memory.protected_anchor.copy()

    assert memory.observe_locked(
        track_id=1,
        required_frames=2,
    )

    for pose in (pose_a, pose_b, pose_c):
        assert memory.update_trusted(
            appearance=pose,
            alpha=0.50,
            gallery_max_entries=2,
        )

    assert len(memory.trusted_gallery) == 2
    assert np.array_equal(
        memory.protected_anchor,
        anchor_before,
    )

    (
        protected_similarity,
        source,
        anchor_similarity,
        gallery_similarity,
        adaptive_similarity,
    ) = memory.effective_similarity(
        appearance=pose_c,
        protected_only=True,
    )

    assert source == "trusted_gallery"
    assert gallery_similarity > 0.99
    assert protected_similarity == gallery_similarity
    assert anchor_similarity < gallery_similarity
    assert adaptive_similarity > 0.0


def test_target_like_duplicate_is_excluded_from_negative_memory():
    selected = feat([1.0, 0.0, 0.0])
    duplicate = feat([0.995, 0.100, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_max_positive_similarity=0.95,
    )

    learn_negative(
        memory,
        selected=selected,
        candidate=duplicate,
        candidate_track_id=2,
        cfg=cfg,
    )

    assert len(memory) == 0


def test_hard_negative_entry_records_merged_provenance():
    selected = feat([1.0, 0.0, 0.0])
    distractor_a = feat([0.8, 0.6, 0.0])
    distractor_b = feat([0.79, 0.61, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg()

    learn_negative(
        memory,
        selected=selected,
        candidate=distractor_a,
        candidate_track_id=2,
        cfg=cfg,
    )
    learn_negative(
        memory,
        selected=selected,
        candidate=distractor_b,
        candidate_track_id=3,
        cfg=cfg,
    )

    assert len(memory) == 1

    entry = memory.entries[0]
    assert entry.source == "trusted_locked_distractor"
    assert entry.source_track_ids == (2, 3)
    assert entry.selected_track_ids == (1,)
    assert entry.observations == 2
    assert 0.78 < entry.positive_similarity < 0.81
    assert entry.geometry_strength == 0.80


def test_hard_negative_gallery_keeps_only_latest_bounded_entries():
    selected = feat([1.0, 0.0, 0.0])
    distractors = (
        (2, feat([0.8, 0.6, 0.0])),
        (3, feat([0.8, 0.0, 0.6])),
        (4, feat([0.8, -0.6, 0.0])),
    )

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_max_entries=2,
    )

    for track_id, appearance in distractors:
        learn_negative(
            memory,
            selected=selected,
            candidate=appearance,
            candidate_track_id=track_id,
            cfg=cfg,
        )

    assert len(memory) == 2
    assert [
        entry.source_track_ids
        for entry in memory.entries
    ] == [
        (3,),
        (4,),
    ]
