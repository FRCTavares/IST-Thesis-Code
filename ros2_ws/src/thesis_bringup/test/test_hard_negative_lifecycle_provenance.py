import json

import numpy as np

from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
)
from thesis_bringup.tim_mars.ros_messages import (
    status_only_json,
)
from thesis_bringup.tim_mars.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)
from thesis_bringup.tim_mars.types import (
    AppearanceObservationProvenance,
)


def feature(values):
    value = np.asarray(values, dtype=float)
    return value / np.linalg.norm(value)


def crop_quality(width):
    return AppearanceCropQuality(
        crop_width_px=float(width),
        crop_height_px=120.0,
        clipping_fraction=0.0,
        aspect_ratio=0.5,
        max_iou_with_other=0.05,
        min_centre_distance_norm=0.10,
        encoding_eligible=True,
        memory_update_eligible=True,
    )


def candidate(
    track_id,
    bbox,
    appearance,
    *,
    frame_id,
    timestamp_ns,
    confidence=0.95,
    quality=None,
    appearance_source_frame_id=None,
):
    provenance = None
    if quality is not None:
        provenance = AppearanceObservationProvenance(
            source_frame_id=appearance_source_frame_id,
            source_image_timestamp_ns=(
                timestamp_ns - 5_000_000
            ),
            embedded_ns=timestamp_ns - 4_000_000,
            embedding_age_ms=4.0,
            frame_generation=2,
            track_generation=3,
            source_bbox=bbox,
            source_crop_quality=quality,
        )

    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=confidence,
        tracker_frame_id=frame_id,
        tracker_timestamp_ns=timestamp_ns,
        appearance=appearance,
        appearance_crop_quality=quality,
        appearance_memory_update_eligible=True,
        appearance_provenance=provenance,
    )


def config():
    return TargetMemoryConfig(
        image_width=640,
        image_height=480,
        appearance_enabled=True,
        appearance_ambiguous_only=True,
        appearance_update_alpha=0.0,
        appearance_conservative_enabled=False,
        appearance_protected_memory_enabled=False,
        hard_negative_memory_enabled=True,
        hard_negative_min_candidate_similarity=0.70,
        hard_negative_confirm_observations=2,
        hard_negative_max_positive_similarity=1.01,
        hard_negative_reject_similarity=1.01,
        hard_negative_reject_margin=0.03,
        hard_negative_min_geometry=0.20,
        hard_negative_max_age_frames=0,
        hard_negative_decay_policy="none_until_expiry",
        rank_aware_reacquisition_enabled=False,
        candidate_belief_enabled=False,
        absence_recovery_enabled=False,
        short_gap_new_id_suppression_enabled=False,
    )


def test_stage_insert_merge_retains_complete_provenance():
    target = feature([1.0, 0.0, 0.0])
    distractor_a = feature([0.80, 0.60, 0.0])
    distractor_b = feature([0.79, 0.61, 0.0])
    distractor_c = feature([0.78, 0.62, 0.0])

    tim = TargetIdentityMemory(config())

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )

    stable = tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )
    assert stable.state == TargetState.LOCKED

    quality_a = crop_quality(60)
    staged = tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor_a,
                frame_id=10,
                timestamp_ns=2_000_000_000,
                confidence=0.87,
                quality=quality_a,
                appearance_source_frame_id=9,
            ),
        ]
    )

    assert staged.state == TargetState.LOCKED
    assert len(tim._hard_negative_memory.entries) == 0
    assert len(tim._hard_negative_memory.pending_entries) == 1

    pending = tim._hard_negative_memory.pending_entries[0]
    assert pending.source_track_ids == (2,)
    assert pending.selected_track_ids == (1,)
    assert pending.observations == 1
    assert pending.first_frame_id == 10
    assert pending.last_frame_id == 10
    assert pending.first_timestamp_ns == 2_000_000_000
    assert pending.last_timestamp_ns == 2_000_000_000
    assert pending.latest_bbox == (125, 101, 185, 241)
    assert pending.latest_confidence == 0.87
    assert pending.latest_crop_quality == quality_a
    assert pending.appearance_source_frame_id == 9
    assert (
        pending.appearance_source_image_timestamp_ns
        == 1_995_000_000
    )
    assert pending.appearance_frame_generation == 2
    assert pending.appearance_track_generation == 3
    assert pending.appearance_source_bbox == (
        125,
        101,
        185,
        241,
    )
    assert pending.appearance_source_crop_quality == quality_a

    quality_b = crop_quality(62)
    inserted = tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                3,
                (127, 101, 189, 241),
                distractor_b,
                frame_id=11,
                timestamp_ns=2_100_000_000,
                confidence=0.88,
                quality=quality_b,
                appearance_source_frame_id=10,
            ),
        ]
    )

    assert inserted.state == TargetState.LOCKED
    assert tim._hard_negative_memory.pending_entries == ()
    assert len(tim._hard_negative_memory.entries) == 1

    committed = tim._hard_negative_memory.entries[0]
    assert committed.source_track_ids == (2, 3)
    assert committed.selected_track_ids == (1,)
    assert committed.observations == 2
    assert committed.first_frame_id == 10
    assert committed.last_frame_id == 11
    assert committed.first_timestamp_ns == 2_000_000_000
    assert committed.last_timestamp_ns == 2_100_000_000
    assert committed.latest_bbox == (127, 101, 189, 241)
    assert committed.latest_confidence == 0.88
    assert committed.latest_crop_quality == quality_b
    assert committed.appearance_source_frame_id == 10
    assert committed.latest_iou >= 0.0
    assert committed.latest_distance >= 0.0
    assert committed.latest_scale >= 0.0
    assert committed.latest_geometry_score >= 0.0

    quality_c = crop_quality(64)
    merged = tim.update(
        [
            candidate(
                1,
                (108, 101, 168, 241),
                target,
                frame_id=12,
                timestamp_ns=2_200_000_000,
            ),
            candidate(
                4,
                (129, 101, 193, 241),
                distractor_c,
                frame_id=12,
                timestamp_ns=2_200_000_000,
                confidence=0.89,
                quality=quality_c,
                appearance_source_frame_id=11,
            ),
        ]
    )

    assert merged.state == TargetState.LOCKED

    entry = tim._hard_negative_memory.entries[0]
    assert entry.source_track_ids == (2, 3, 4)
    assert entry.selected_track_ids == (1,)
    assert entry.observations == 3

    # Earliest observation remains stable.
    assert entry.first_frame_id == 10
    assert entry.first_timestamp_ns == 2_000_000_000

    # Latest context advances atomically with the merged prototype.
    assert entry.last_frame_id == 12
    assert entry.last_timestamp_ns == 2_200_000_000
    assert entry.latest_bbox == (129, 101, 193, 241)
    assert entry.latest_confidence == 0.89
    assert entry.latest_crop_quality == quality_c
    assert entry.appearance_source_frame_id == 11
    assert entry.appearance_source_crop_quality == quality_c


def test_legacy_raw_feature_entries_remain_supported():
    appearance = feature([0.8, 0.6, 0.0])
    tim = TargetIdentityMemory(config())

    tim._hard_negative_memory._memory = [appearance]

    entries = tim._hard_negative_memory.entries

    assert len(entries) == 1
    assert entries[0].source == "legacy_unattributed"
    assert entries[0].observations == 1
    assert entries[0].first_frame_id is None
    assert entries[0].last_frame_id is None
    assert entries[0].latest_bbox is None


def test_output_snapshots_report_pending_committed_and_age():
    target = feature([1.0, 0.0, 0.0])
    distractor_a = feature([0.80, 0.60, 0.0])
    distractor_b = feature([0.79, 0.61, 0.0])

    tim = TargetIdentityMemory(config())

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )
    tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )

    staged = tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor_a,
                frame_id=10,
                timestamp_ns=2_000_000_000,
                quality=crop_quality(60),
                appearance_source_frame_id=9,
            ),
        ]
    )

    assert staged.hard_negative_current_frame_id == 10
    assert staged.hard_negative_entries == ()
    assert len(staged.hard_negative_pending_entries) == 1

    pending = staged.hard_negative_pending_entries[0]
    assert pending.lifecycle_state == "pending"
    assert pending.first_frame_id == 10
    assert pending.last_frame_id == 10
    assert pending.age_frames == 0
    assert pending.expires_at_frame_id is None
    assert pending.expired is False
    assert pending.max_age_frames == 0
    assert pending.decay_policy == "none_until_expiry"

    inserted = tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                3,
                (127, 101, 189, 241),
                distractor_b,
                frame_id=11,
                timestamp_ns=2_100_000_000,
                quality=crop_quality(62),
                appearance_source_frame_id=10,
            ),
        ]
    )

    assert inserted.hard_negative_pending_entries == ()
    assert len(inserted.hard_negative_entries) == 1

    committed = inserted.hard_negative_entries[0]
    assert committed.lifecycle_state == "committed"
    assert committed.first_frame_id == 10
    assert committed.last_frame_id == 11
    assert committed.age_frames == 0
    assert committed.latest_bbox == (
        127,
        101,
        189,
        241,
    )

    aged = tim.update(
        [],
        frame_id=15,
        timestamp_ns=2_500_000_000,
    )

    assert aged.hard_negative_current_frame_id == 15
    assert len(aged.hard_negative_entries) == 1
    assert aged.hard_negative_entries[0].age_frames == 4

    # Canonical max age remains disabled, so diagnostics must not
    # claim that the full-strength prototype has expired.
    assert aged.hard_negative_max_age_frames == 0
    assert aged.hard_negative_entries[0].expired is False
    assert (
        aged.hard_negative_decay_policy
        == "none_until_expiry"
    )


def test_snapshot_reports_finite_expiry_boundary_without_mutation():
    cfg = config()
    cfg.hard_negative_max_age_frames = 3

    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(cfg)

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )
    tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )

    learned = tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
        ],
        frame_id=10,
        timestamp_ns=2_000_000_000,
    )
    assert learned.hard_negative_pending_entries

    learned = tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                2,
                (127, 101, 187, 241),
                distractor,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
        ],
        frame_id=11,
        timestamp_ns=2_100_000_000,
    )

    snapshot = learned.hard_negative_entries[0]
    assert snapshot.expires_at_frame_id == 15
    assert snapshot.age_frames == 0
    assert snapshot.expired is False

    boundary = tim.update([], frame_id=14)
    assert boundary.hard_negative_entries[0].age_frames == 3
    assert boundary.hard_negative_entries[0].expired is False

    beyond = tim.update([], frame_id=15)
    assert beyond.hard_negative_entries[0].age_frames == 4
    assert beyond.hard_negative_entries[0].expired is True

    # This stage is diagnostics only; expiry mutation is implemented
    # and tested separately.
    assert len(tim._hard_negative_memory.entries) == 1


def test_status_json_serializes_hard_negative_snapshots():
    cfg = config()
    cfg.hard_negative_max_age_frames = 3

    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(cfg)

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )

    tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )

    staged = tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor,
                frame_id=10,
                timestamp_ns=2_000_000_000,
                confidence=0.87,
                quality=crop_quality(60),
                appearance_source_frame_id=9,
            ),
        ]
    )

    staged_payload = json.loads(
        status_only_json(staged)
    )

    assert staged_payload[
        "hard_negative_current_frame_id"
    ] == 10
    assert staged_payload[
        "hard_negative_max_age_frames"
    ] == 3
    assert staged_payload[
        "hard_negative_decay_policy"
    ] == "none_until_expiry"
    assert staged_payload["hard_negative_entries"] == []

    pending = staged_payload[
        "hard_negative_pending_entries"
    ][0]
    assert pending["lifecycle_state"] == "pending"
    assert pending["source_track_ids"] == [2]
    assert pending["selected_track_ids"] == [1]
    assert pending["observations"] == 1
    assert pending["first_frame_id"] == 10
    assert pending["last_frame_id"] == 10
    assert pending["age_frames"] == 0
    assert pending["expires_at_frame_id"] == 14
    assert pending["expired"] is False
    assert pending["latest_bbox"] == [
        125.0,
        101.0,
        185.0,
        241.0,
    ]
    assert pending["latest_confidence"] == 0.87
    assert (
        pending["latest_crop_quality"]["crop_width_px"]
        == 60.0
    )
    assert pending["appearance_source_frame_id"] == 9
    assert pending["max_age_frames"] == 3
    assert pending["decay_policy"] == "none_until_expiry"

    inserted = tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                3,
                (127, 101, 189, 241),
                distractor,
                frame_id=11,
                timestamp_ns=2_100_000_000,
                confidence=0.88,
                quality=crop_quality(62),
                appearance_source_frame_id=10,
            ),
        ]
    )

    inserted_payload = json.loads(
        status_only_json(inserted)
    )

    assert inserted_payload[
        "hard_negative_pending_entries"
    ] == []

    committed = inserted_payload[
        "hard_negative_entries"
    ][0]
    assert committed["lifecycle_state"] == "committed"
    assert committed["source_track_ids"] == [2, 3]
    assert committed["selected_track_ids"] == [1]
    assert committed["observations"] == 2
    assert committed["first_frame_id"] == 10
    assert committed["last_frame_id"] == 11
    assert committed["first_timestamp_ns"] == 2_000_000_000
    assert committed["last_timestamp_ns"] == 2_100_000_000
    assert committed["age_frames"] == 0
    assert committed["expires_at_frame_id"] == 15
    assert committed["expired"] is False
    assert committed["latest_bbox"] == [
        127.0,
        101.0,
        189.0,
        241.0,
    ]
    assert committed["latest_confidence"] == 0.88
    assert (
        committed["latest_crop_quality"]["crop_width_px"]
        == 62.0
    )
    assert committed["appearance_source_frame_id"] == 10
    assert (
        committed[
            "appearance_source_crop_quality"
        ]["crop_width_px"]
        == 62.0
    )

    aged = tim.update([], frame_id=15)
    aged_payload = json.loads(status_only_json(aged))
    aged_entry = aged_payload[
        "hard_negative_entries"
    ][0]

    assert aged_entry["age_frames"] == 4
    assert aged_entry["expired"] is True

    # Serialization remains observational at this stage.
    assert len(tim._hard_negative_memory.entries) == 1


def test_committed_expiry_requires_trusted_locked_continuity():
    cfg = config()
    cfg.hard_negative_max_age_frames = 3

    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(cfg)

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )
    tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )

    tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor,
                frame_id=10,
                timestamp_ns=2_000_000_000,
                confidence=0.87,
                quality=crop_quality(60),
                appearance_source_frame_id=9,
            ),
        ]
    )

    learned = tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                3,
                (127, 101, 189, 241),
                distractor,
                frame_id=11,
                timestamp_ns=2_100_000_000,
                confidence=0.88,
                quality=crop_quality(62),
                appearance_source_frame_id=10,
            ),
        ]
    )

    assert learned.state == TargetState.LOCKED
    assert len(tim._hard_negative_memory.entries) == 1

    # The entry is now over age, but uncertainty must preserve it because
    # removing identity protection during recovery would be unsafe.
    uncertain = tim.update(
        [],
        frame_id=15,
        timestamp_ns=2_500_000_000,
    )

    assert uncertain.state == TargetState.UNCERTAIN
    assert uncertain.hard_negative_events == ()
    assert len(tim._hard_negative_memory.entries) == 1
    assert uncertain.hard_negative_entries[0].age_frames == 4
    assert uncertain.hard_negative_entries[0].expired is True

    # Complete any recovery confirmation. The first accepted frame restores
    # LOCKED state but is not uninterrupted trusted continuity, so it must
    # still retain the negative.
    recovered = None
    recovery_frame = None
    for frame_id in range(16, 22):
        recovered = tim.update(
            [
                candidate(
                    1,
                    (
                        106 + frame_id,
                        101,
                        166 + frame_id,
                        241,
                    ),
                    target,
                    frame_id=frame_id,
                    timestamp_ns=(
                        2_500_000_000
                        + (frame_id - 15)
                        * 100_000_000
                    ),
                )
            ],
            frame_id=frame_id,
        )

        if (
            recovered.state == TargetState.LOCKED
            and recovered.visible
        ):
            recovery_frame = frame_id
            break

    assert recovered is not None
    assert recovery_frame is not None
    assert len(tim._hard_negative_memory.entries) == 1
    assert not any(
        event.action == "expire"
        for event in recovered.hard_negative_events
    )

    # Only the following accepted LOCKED -> LOCKED frame is allowed to
    # commit expiry.
    trusted_frame = recovery_frame + 1
    expired = tim.update(
        [
            candidate(
                1,
                (
                    106 + trusted_frame,
                    101,
                    166 + trusted_frame,
                    241,
                ),
                target,
                frame_id=trusted_frame,
                timestamp_ns=(
                    2_500_000_000
                    + (trusted_frame - 15)
                    * 100_000_000
                ),
            )
        ],
        frame_id=trusted_frame,
    )

    assert expired.state == TargetState.LOCKED
    assert expired.visible
    assert len(tim._hard_negative_memory.entries) == 0
    assert expired.hard_negative_entries == ()

    expiry_events = [
        event
        for event in expired.hard_negative_events
        if event.action == "expire"
    ]
    assert len(expiry_events) == 1

    event = expiry_events[0]
    assert event.source == "trusted_locked_distractor"
    assert event.selected_track_id == 1
    assert event.source_track_ids == (2, 3)
    assert event.selected_track_ids == (1,)
    assert event.observations == 2
    assert event.memory_size == 0
    assert event.snapshot is not None

    snapshot = event.snapshot
    assert snapshot.lifecycle_state == "expired"
    assert snapshot.first_frame_id == 10
    assert snapshot.last_frame_id == 11
    assert snapshot.age_frames == trusted_frame - 11
    assert snapshot.expired is True
    assert snapshot.latest_bbox == (
        127,
        101,
        189,
        241,
    )
    assert snapshot.latest_confidence == 0.88
    assert snapshot.latest_crop_quality == crop_quality(62)
    assert snapshot.appearance_source_frame_id == 10
    assert snapshot.decay_policy == "none_until_expiry"

    payload = json.loads(status_only_json(expired))
    payload_event = next(
        item
        for item in payload["hard_negative_events"]
        if item["action"] == "expire"
    )

    assert payload_event["memory_size"] == 0
    assert payload_event["snapshot"] is not None
    assert (
        payload_event["snapshot"]["lifecycle_state"]
        == "expired"
    )
    assert payload_event["snapshot"]["source_track_ids"] == [
        2,
        3,
    ]
    assert payload_event["snapshot"]["expired"] is True
    assert (
        payload_event["snapshot"]["latest_crop_quality"][
            "crop_width_px"
        ]
        == 62.0
    )


def test_zero_max_age_preserves_canonical_behaviour():
    cfg = config()
    cfg.hard_negative_max_age_frames = 0

    target = feature([1.0, 0.0, 0.0])
    distractor = feature([0.80, 0.60, 0.0])

    tim = TargetIdentityMemory(cfg)

    tim.select(
        candidate(
            1,
            (100, 100, 160, 240),
            target,
            frame_id=1,
            timestamp_ns=1_000_000_000,
        )
    )
    tim.update(
        [
            candidate(
                1,
                (102, 100, 162, 240),
                target,
                frame_id=2,
                timestamp_ns=1_100_000_000,
            )
        ]
    )

    tim.update(
        [
            candidate(
                1,
                (104, 101, 164, 241),
                target,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
            candidate(
                2,
                (125, 101, 185, 241),
                distractor,
                frame_id=10,
                timestamp_ns=2_000_000_000,
            ),
        ]
    )
    tim.update(
        [
            candidate(
                1,
                (106, 101, 166, 241),
                target,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
            candidate(
                3,
                (127, 101, 189, 241),
                distractor,
                frame_id=11,
                timestamp_ns=2_100_000_000,
            ),
        ]
    )

    output = tim.update(
        [
            candidate(
                1,
                (140, 101, 200, 241),
                target,
                frame_id=1000,
                timestamp_ns=9_000_000_000,
            )
        ],
        frame_id=1000,
        timestamp_ns=9_000_000_000,
    )

    assert output.state == TargetState.LOCKED
    assert len(tim._hard_negative_memory.entries) == 1
    assert not any(
        event.action == "expire"
        for event in output.hard_negative_events
    )
    assert output.hard_negative_entries[0].expired is False


def test_unsupported_decay_policy_fails_loudly():
    tim = TargetIdentityMemory(config())

    try:
        tim._hard_negative_memory.expire_committed(
            current_frame_id=10,
            max_age_frames=3,
            decay_policy="silent_similarity_decay",
            selected_track_id=1,
        )
    except ValueError as error:
        assert "Unsupported hard-negative decay policy" in str(
            error
        )
    else:
        raise AssertionError(
            "unsupported decay policy was silently accepted"
        )
