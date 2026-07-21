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
        hard_negative_confirm_observations=1,
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
    return memory.update(
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


def test_hard_negative_requires_repeated_trusted_observations():
    selected = feat([1.0, 0.0, 0.0])
    distractor_a = feat([0.8, 0.6, 0.0])
    distractor_b = feat([0.79, 0.61, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_confirm_observations=2,
    )

    staged = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_a,
        candidate_track_id=2,
        cfg=cfg,
    )

    assert len(memory) == 0
    assert len(memory.pending_entries) == 1
    assert len(staged) == 1
    stage_event = staged[0]
    assert stage_event.action == "stage"
    assert stage_event.source_track_ids == (2,)
    assert stage_event.selected_track_ids == (1,)
    assert stage_event.observations == 1
    assert stage_event.memory_size == 0

    inserted = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_b,
        candidate_track_id=3,
        cfg=cfg,
    )

    assert len(memory) == 1
    assert memory.pending_entries == ()
    assert len(inserted) == 1
    insert_event = inserted[0]
    assert insert_event.action == "insert"
    assert insert_event.source_track_ids == (2, 3)
    assert insert_event.selected_track_ids == (1,)
    assert insert_event.observations == 2
    assert insert_event.prototype_similarity > 0.99
    assert insert_event.memory_size == 1


def test_selected_identity_discards_pending_negative_evidence():
    selected = feat([1.0, 0.0, 0.0])
    distractor = feat([0.8, 0.6, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_confirm_observations=2,
    )

    learn_negative(
        memory,
        selected=selected,
        candidate=distractor,
        candidate_track_id=2,
        cfg=cfg,
    )

    events = memory.reconcile_selected(
        distractor,
        cfg,
        selected_track_id=2,
    )

    assert len(memory) == 0
    assert memory.pending_entries == ()
    assert len(events) == 1
    event = events[0]
    assert event.action == "discard_pending"
    assert event.source == "trusted_locked_distractor_pending"
    assert event.selected_track_id == 2
    assert event.source_track_ids == (2,)
    assert event.selected_track_ids == (1,)
    assert event.observations == 1
    assert event.prototype_similarity > 0.99
    assert event.memory_size == 0



def test_pending_hard_negative_cannot_affect_rejection_similarity():
    selected = feat([1.0, 0.0, 0.0])
    distractor = feat([0.8, 0.6, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_confirm_observations=2,
    )

    events = learn_negative(
        memory,
        selected=selected,
        candidate=distractor,
        candidate_track_id=2,
        cfg=cfg,
    )

    assert len(events) == 1
    assert events[0].action == "stage"
    assert len(memory) == 0
    assert len(memory.pending_entries) == 1
    assert memory.similarity(distractor, cfg) == 0.0


def test_pending_hard_negative_expires_without_consecutive_observation():
    selected = feat([1.0, 0.0, 0.0])
    distractor_a = feat([0.8, 0.6, 0.0])
    distractor_b = feat([0.79, 0.61, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_confirm_observations=2,
    )

    staged = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_a,
        candidate_track_id=2,
        cfg=cfg,
    )

    assert [event.action for event in staged] == ["stage"]
    assert len(memory) == 0
    assert len(memory.pending_entries) == 1

    expired = memory.update(
        candidates=[tr(1, selected)],
        scores_sorted=[],
        selected_track_id=1,
        positive_appearance=selected,
        state=TargetState.LOCKED,
        cfg=cfg,
    )

    assert [event.action for event in expired] == [
        "expire_pending"
    ]
    assert len(memory) == 0
    assert memory.pending_entries == ()

    restaged = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_b,
        candidate_track_id=3,
        cfg=cfg,
    )

    assert [event.action for event in restaged] == ["stage"]
    assert len(memory) == 0
    assert len(memory.pending_entries) == 1


def test_same_frame_candidates_cannot_satisfy_confirmation():
    selected = feat([1.0, 0.0, 0.0])
    distractor_a = feat([0.8, 0.6, 0.0])
    distractor_b = feat([0.79, 0.61, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg(
        hard_negative_confirm_observations=2,
    )

    events = memory.update(
        candidates=[
            tr(1, selected),
            tr(2, distractor_a),
            tr(3, distractor_b),
        ],
        scores_sorted=[
            candidate_score(
                2,
                cosine_similarity(selected, distractor_a),
            ),
            candidate_score(
                3,
                cosine_similarity(selected, distractor_b),
            ),
        ],
        selected_track_id=1,
        positive_appearance=selected,
        state=TargetState.LOCKED,
        cfg=cfg,
    )

    assert len(memory) == 0
    assert len(memory.pending_entries) == 2
    assert [event.action for event in events] == [
        "stage",
        "stage",
    ]
    assert all(event.observations == 1 for event in events)

def test_hard_negative_entry_records_merged_provenance():
    selected = feat([1.0, 0.0, 0.0])
    distractor_a = feat([0.8, 0.6, 0.0])
    distractor_b = feat([0.79, 0.61, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg()

    insert_events = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_a,
        candidate_track_id=2,
        cfg=cfg,
    )
    merge_events = learn_negative(
        memory,
        selected=selected,
        candidate=distractor_b,
        candidate_track_id=3,
        cfg=cfg,
    )

    assert len(memory) == 1
    assert len(insert_events) == 1
    insert_event = insert_events[0]
    assert insert_event.action == "insert"
    assert insert_event.source_track_id == 2
    assert insert_event.selected_track_id == 1
    assert insert_event.source_track_ids == (2,)
    assert insert_event.selected_track_ids == (1,)
    assert insert_event.observations == 1
    assert insert_event.memory_size == 1

    assert len(merge_events) == 1
    merge_event = merge_events[0]
    assert merge_event.action == "merge"
    assert merge_event.source_track_id == 3
    assert merge_event.selected_track_id == 1
    assert merge_event.source_track_ids == (2, 3)
    assert merge_event.selected_track_ids == (1,)
    assert merge_event.observations == 2
    assert merge_event.prototype_similarity > 0.99
    assert merge_event.memory_size == 1

    entry = memory.entries[0]
    assert entry.source == "trusted_locked_distractor"
    assert entry.source_track_ids == (2, 3)
    assert entry.selected_track_ids == (1,)
    assert entry.observations == 2
    assert 0.78 < entry.positive_similarity < 0.81
    assert entry.geometry_strength == 0.80


def test_reconcile_event_records_removed_selected_lineage():
    selected = feat([1.0, 0.0, 0.0])
    distractor = feat([0.8, 0.6, 0.0])

    memory = HardNegativeMemory()
    cfg = negative_cfg()

    learn_negative(
        memory,
        selected=selected,
        candidate=distractor,
        candidate_track_id=2,
        cfg=cfg,
    )

    events = memory.reconcile_selected(
        distractor,
        cfg,
        selected_track_id=2,
    )

    assert len(memory) == 0
    assert len(events) == 1
    event = events[0]
    assert event.action == "reconcile"
    assert event.source == "trusted_locked_distractor"
    assert event.selected_track_id == 2
    assert event.source_track_ids == (2,)
    assert event.selected_track_ids == (1,)
    assert event.observations == 1
    assert event.prototype_similarity > 0.99
    assert event.memory_size == 0


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

    events_by_track_id = {}
    for track_id, appearance in distractors:
        events_by_track_id[track_id] = learn_negative(
            memory,
            selected=selected,
            candidate=appearance,
            candidate_track_id=track_id,
            cfg=cfg,
        )

    assert len(events_by_track_id[2]) == 1
    assert events_by_track_id[2][0].action == "insert"
    assert len(events_by_track_id[3]) == 1
    assert events_by_track_id[3][0].action == "insert"

    final_events = events_by_track_id[4]
    assert len(final_events) == 2
    assert final_events[0].action == "insert"
    assert final_events[0].source_track_id == 4
    assert final_events[0].memory_size == 2

    eviction = final_events[1]
    assert eviction.action == "evict"
    assert eviction.source == "trusted_locked_distractor"
    assert eviction.selected_track_id == 1
    assert eviction.source_track_ids == (2,)
    assert eviction.selected_track_ids == (1,)
    assert eviction.observations == 1
    assert eviction.memory_size == 2

    assert len(memory) == 2
    assert [
        entry.source_track_ids
        for entry in memory.entries
    ] == [
        (3,),
        (4,),
    ]
