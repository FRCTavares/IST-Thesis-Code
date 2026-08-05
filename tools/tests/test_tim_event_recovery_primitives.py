"""Synthetic tests for Issue #26 event and episode primitives."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "tim_evaluation.py"
)

SPEC = importlib.util.spec_from_file_location(
    "tim_event_recovery_primitives",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def interval(
    start_s: float,
    end_s: float,
    *,
    correct_id: int = 1,
    label: str = "CORRECT_TARGET",
    visible: bool = True,
    event_type: str = "clean_visible",
):
    return MODULE.AnnotationInterval(
        bag_name="test_bag",
        start_s=start_s,
        end_s=end_s,
        target_label=label,
        target_visible=visible,
        correct_target_track_id=correct_id,
        distractor_track_ids="",
        event_type=event_type,
        notes="",
    )



def test_decimal_boundary_does_not_create_phantom_slice():
    slices = list(
        MODULE.iter_interval_slices(
            interval(0.5, 0.6),
            step_s=0.1,
        )
    )

    assert len(slices) == 1
    assert slices[0].t_s == pytest.approx(0.5)
    assert slices[0].duration_s == pytest.approx(0.1)



def test_slice_classification_preserves_authoritative_categories():
    annotations = [
        interval(0.0, 0.1),
        interval(0.1, 0.2),
        interval(0.2, 0.3),
        interval(
            0.3,
            0.4,
            label="TARGET_NOT_VISIBLE",
            visible=False,
            event_type="target_absent",
        ),
        interval(
            0.4,
            0.5,
            label="TARGET_NOT_VISIBLE",
            visible=False,
            event_type="target_absent",
        ),
        interval(
            0.5,
            0.6,
            label="NO_TARGET_SELECTED",
            visible=False,
            event_type="other",
        ),
    ]
    samples = [
        MODULE.TargetSample(t_s=0.0, track_id=1),
        MODULE.TargetSample(t_s=0.1, track_id=2),
        MODULE.TargetSample(t_s=0.2, track_id=0),
        MODULE.TargetSample(t_s=0.3, track_id=8),
        MODULE.TargetSample(t_s=0.4, track_id=0),
    ]

    slices = MODULE.classify_interval_slices(
        annotations,
        samples,
        step_s=0.1,
    )

    assert [
        item.classification
        for item in slices
    ] == [
        "correct",
        "wrong",
        "lost",
        "target_absent_output",
        "target_absent_clear",
        "no_target_selected",
    ]


def test_classified_totals_match_existing_duration_evaluator():
    annotations = [
        interval(0.0, 0.2),
        interval(
            0.2,
            0.4,
            label="TARGET_NOT_VISIBLE",
            visible=False,
            event_type="target_absent",
        ),
    ]
    samples = [
        MODULE.TargetSample(t_s=0.0, track_id=1),
        MODULE.TargetSample(t_s=0.1, track_id=7),
        MODULE.TargetSample(t_s=0.2, track_id=8),
        MODULE.TargetSample(t_s=0.3, track_id=0),
    ]

    legacy = MODULE.evaluate_stream(
        annotations,
        samples,
        step_s=0.1,
    )
    slices = MODULE.classify_interval_slices(
        annotations,
        samples,
        step_s=0.1,
    )

    totals = {}
    for item in slices:
        totals[item.classification] = (
            totals.get(item.classification, 0.0)
            + item.duration_s
        )

    assert totals["correct"] == pytest.approx(
        legacy.correct_target_duration_s
    )
    assert totals["wrong"] == pytest.approx(
        legacy.wrong_target_duration_s
    )
    assert totals.get("lost", 0.0) == pytest.approx(
        legacy.lost_target_duration_s
    )
    assert totals["target_absent_output"] == pytest.approx(
        legacy.target_absent_but_output_valid_duration_s
    )


def test_stale_output_is_classified_lost_and_keeps_provenance():
    slices = MODULE.classify_interval_slices(
        [interval(0.0, 0.4)],
        [MODULE.TargetSample(t_s=0.0, track_id=1)],
        step_s=0.1,
        max_output_age_s=0.2,
    )

    assert [
        item.classification
        for item in slices
    ] == ["correct", "correct", "correct", "lost"]
    assert slices[-1].freshness_status == "stale_source"
    assert slices[-1].output_track_id == 0


def test_wrong_slices_merge_across_wrong_track_handover():
    slices = [
        MODULE.ClassifiedSlice(
            annotation_index=0,
            bag_name="bag",
            event_type="occlusion_ambiguity",
            t_s=0.0,
            duration_s=0.1,
            classification="wrong",
            output_track_id=2,
            correct_target_track_id=1,
            freshness_status="fresh",
        ),
        MODULE.ClassifiedSlice(
            annotation_index=0,
            bag_name="bag",
            event_type="occlusion_ambiguity",
            t_s=0.1,
            duration_s=0.1,
            classification="wrong",
            output_track_id=3,
            correct_target_track_id=1,
            freshness_status="fresh",
        ),
    ]

    episodes = MODULE.contiguous_episodes(
        slices,
        classification="wrong",
    )

    assert len(episodes) == 1
    assert episodes[0].duration_s == pytest.approx(0.2)
    assert episodes[0].slice_count == 2
    assert episodes[0].output_track_ids == (2, 3)


def test_gaps_and_event_boundaries_split_episodes():
    slices = [
        MODULE.ClassifiedSlice(
            annotation_index=0,
            bag_name="bag",
            event_type="reentry",
            t_s=0.0,
            duration_s=0.1,
            classification="wrong",
            output_track_id=2,
            correct_target_track_id=1,
            freshness_status="fresh",
        ),
        MODULE.ClassifiedSlice(
            annotation_index=1,
            bag_name="bag",
            event_type="id_switch_fragmentation",
            t_s=0.1,
            duration_s=0.1,
            classification="wrong",
            output_track_id=2,
            correct_target_track_id=1,
            freshness_status="fresh",
        ),
        MODULE.ClassifiedSlice(
            annotation_index=1,
            bag_name="bag",
            event_type="id_switch_fragmentation",
            t_s=0.3,
            duration_s=0.1,
            classification="wrong",
            output_track_id=2,
            correct_target_track_id=1,
            freshness_status="fresh",
        ),
    ]

    episodes = MODULE.contiguous_episodes(
        slices,
        classification="wrong",
    )

    assert len(episodes) == 3
    assert [item.event_type for item in episodes] == [
        "reentry",
        "id_switch_fragmentation",
        "id_switch_fragmentation",
    ]


def test_empty_episode_input_is_supported():
    assert MODULE.contiguous_episodes([]) == []


def test_negative_episode_tolerance_is_rejected():
    with pytest.raises(
        ValueError,
        match="finite and non-negative",
    ):
        MODULE.contiguous_episodes(
            [],
            tolerance_s=-0.1,
        )


def classified_slice(
    t_s: float,
    *,
    duration_s: float = 0.1,
    classification: str = "wrong",
    output_id: int = 2,
    event_type: str = "occlusion_ambiguity",
    bag_name: str = "bag",
):
    return MODULE.ClassifiedSlice(
        annotation_index=0,
        bag_name=bag_name,
        event_type=event_type,
        t_s=t_s,
        duration_s=duration_s,
        classification=classification,
        output_track_id=output_id,
        correct_target_track_id=1,
        freshness_status="fresh",
    )


def test_episode_metrics_count_wrong_bursts_and_longest_duration():
    slices = [
        classified_slice(0.0),
        classified_slice(0.1),
        classified_slice(
            0.2,
            classification="correct",
            output_id=1,
        ),
        classified_slice(0.3),
        classified_slice(0.4),
        classified_slice(0.5),
    ]

    metrics = MODULE.summarise_episode_metrics(slices)

    assert metrics.wrong_target_burst_count == 2
    assert metrics.wrong_target_total_duration_s == pytest.approx(0.5)
    assert metrics.longest_wrong_target_burst_s == pytest.approx(0.3)


def test_wrong_handover_counts_selected_id_transitions_inside_burst():
    slices = [
        classified_slice(0.0, output_id=2),
        classified_slice(0.1, output_id=2),
        classified_slice(0.2, output_id=3),
        classified_slice(0.3, output_id=4),
        classified_slice(
            0.4,
            classification="correct",
            output_id=1,
        ),
        classified_slice(0.5, output_id=4),
        classified_slice(0.6, output_id=5),
    ]

    metrics = MODULE.summarise_episode_metrics(slices)

    assert metrics.wrong_target_burst_count == 2
    assert metrics.wrong_handover_count == 3


def test_wrong_handover_does_not_cross_event_or_gap_boundary():
    slices = [
        classified_slice(
            0.0,
            output_id=2,
            event_type="reentry",
        ),
        classified_slice(
            0.1,
            output_id=3,
            event_type="id_switch_fragmentation",
        ),
        classified_slice(
            0.3,
            output_id=4,
            event_type="id_switch_fragmentation",
        ),
    ]

    metrics = MODULE.summarise_episode_metrics(slices)

    assert metrics.wrong_target_burst_count == 3
    assert metrics.wrong_handover_count == 0


def test_target_absent_output_episode_metrics_are_separate():
    slices = [
        classified_slice(
            0.0,
            classification="target_absent_output",
            output_id=7,
            event_type="target_absent",
        ),
        classified_slice(
            0.1,
            classification="target_absent_output",
            output_id=7,
            event_type="target_absent",
        ),
        classified_slice(
            0.2,
            classification="target_absent_clear",
            output_id=0,
            event_type="target_absent",
        ),
        classified_slice(
            0.3,
            classification="target_absent_output",
            output_id=8,
            event_type="target_absent",
        ),
    ]

    metrics = MODULE.summarise_episode_metrics(slices)

    assert metrics.wrong_target_burst_count == 0
    assert metrics.target_absent_output_episode_count == 2
    assert (
        metrics.target_absent_output_total_duration_s
        == pytest.approx(0.3)
    )
    assert (
        metrics.longest_target_absent_output_episode_s
        == pytest.approx(0.2)
    )


def test_empty_episode_metrics_are_zero():
    metrics = MODULE.summarise_episode_metrics([])

    assert metrics.wrong_target_burst_count == 0
    assert metrics.wrong_target_total_duration_s == pytest.approx(0.0)
    assert metrics.longest_wrong_target_burst_s == pytest.approx(0.0)
    assert metrics.wrong_handover_count == 0
    assert metrics.target_absent_output_episode_count == 0
    assert (
        metrics.target_absent_output_total_duration_s
        == pytest.approx(0.0)
    )
    assert (
        metrics.longest_target_absent_output_episode_s
        == pytest.approx(0.0)
    )


def recovery_interval(
    start_s: float,
    end_s: float,
    *,
    visible: bool,
    correct_id: int = 0,
    event_type: str,
    bag_name: str = "recovery_bag",
):
    return MODULE.AnnotationInterval(
        bag_name=bag_name,
        start_s=start_s,
        end_s=end_s,
        target_label=(
            "CORRECT_TARGET"
            if visible
            else "TARGET_NOT_VISIBLE"
        ),
        target_visible=visible,
        correct_target_track_id=correct_id,
        distractor_track_ids="",
        event_type=event_type,
        notes="",
    )


def recovery_slice(
    t_s: float,
    classification: str,
    *,
    output_id: int,
    correct_id: int = 9,
    duration_s: float = 0.1,
    bag_name: str = "recovery_bag",
):
    return MODULE.ClassifiedSlice(
        annotation_index=0,
        bag_name=bag_name,
        event_type="reentry",
        t_s=t_s,
        duration_s=duration_s,
        classification=classification,
        output_track_id=output_id,
        correct_target_track_id=correct_id,
        freshness_status="fresh",
    )


def test_absence_recovery_succeeds_after_stable_new_id_return():
    annotations = [
        recovery_interval(
            0.0,
            0.5,
            visible=True,
            correct_id=1,
            event_type="clean_visible",
        ),
        recovery_interval(
            0.5,
            1.0,
            visible=False,
            event_type="target_absent",
        ),
        recovery_interval(
            1.0,
            2.0,
            visible=True,
            correct_id=9,
            event_type="reentry",
        ),
    ]
    slices = [
        recovery_slice(1.0, "lost", output_id=0),
        recovery_slice(1.1, "wrong", output_id=4),
        recovery_slice(1.2, "correct", output_id=9),
        recovery_slice(1.3, "correct", output_id=9),
        recovery_slice(1.4, "correct", output_id=9),
    ]

    episodes = MODULE.build_absence_recovery_episodes(
        annotations,
        slices,
        stable_duration_s=0.25,
    )

    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.result == "success"
    assert episode.first_eligible_recovery_s == pytest.approx(1.0)
    assert episode.first_correct_output_s == pytest.approx(1.2)
    assert (
        episode.first_stable_correct_output_s
        == pytest.approx(1.2)
    )
    assert episode.first_correct_latency_s == pytest.approx(0.2)
    assert episode.stable_correct_latency_s == pytest.approx(0.2)
    assert (
        episode.wrong_target_duration_before_recovery_s
        == pytest.approx(0.1)
    )
    assert (
        episode.lost_duration_before_recovery_s
        == pytest.approx(0.1)
    )
    assert episode.recovery_identity == "new_id"


def test_one_correct_slice_is_not_stable_recovery():
    annotations = [
        recovery_interval(
            0.0,
            0.5,
            visible=True,
            correct_id=1,
            event_type="clean_visible",
        ),
        recovery_interval(
            0.5,
            1.0,
            visible=False,
            event_type="target_absent",
        ),
        recovery_interval(
            1.0,
            1.5,
            visible=True,
            correct_id=1,
            event_type="reentry",
        ),
        recovery_interval(
            1.5,
            2.0,
            visible=False,
            event_type="target_absent",
        ),
    ]
    slices = [
        recovery_slice(
            1.0,
            "correct",
            output_id=1,
            correct_id=1,
        ),
        recovery_slice(
            1.1,
            "wrong",
            output_id=3,
            correct_id=1,
        ),
        recovery_slice(
            1.2,
            "lost",
            output_id=0,
            correct_id=1,
        ),
    ]

    episodes = MODULE.build_absence_recovery_episodes(
        annotations,
        slices,
        stable_duration_s=0.25,
    )

    assert episodes[0].first_correct_output_s == pytest.approx(1.0)
    assert episodes[0].first_stable_correct_output_s is None
    assert episodes[0].result == "failure"
    assert episodes[0].recovery_identity == "same_id"


def test_visible_return_without_recovery_until_sequence_end_is_censored():
    annotations = [
        recovery_interval(
            0.0,
            0.5,
            visible=True,
            correct_id=1,
            event_type="clean_visible",
        ),
        recovery_interval(
            0.5,
            1.0,
            visible=False,
            event_type="target_absent",
        ),
        recovery_interval(
            1.0,
            1.5,
            visible=True,
            correct_id=8,
            event_type="reentry",
        ),
    ]
    slices = [
        recovery_slice(
            1.0,
            "wrong",
            output_id=4,
            correct_id=8,
        ),
        recovery_slice(
            1.1,
            "lost",
            output_id=0,
            correct_id=8,
        ),
        recovery_slice(
            1.2,
            "wrong",
            output_id=4,
            correct_id=8,
        ),
    ]

    episodes = MODULE.build_absence_recovery_episodes(
        annotations,
        slices,
        stable_duration_s=0.25,
    )

    assert episodes[0].result == "censored"
    assert episodes[0].first_correct_output_s is None
    assert episodes[0].first_stable_correct_output_s is None


def test_final_absence_without_visible_return_is_censored():
    annotations = [
        recovery_interval(
            0.0,
            0.5,
            visible=True,
            correct_id=1,
            event_type="clean_visible",
        ),
        recovery_interval(
            0.5,
            1.0,
            visible=False,
            event_type="target_absent",
        ),
    ]

    episodes = MODULE.build_absence_recovery_episodes(
        annotations,
        [],
        stable_duration_s=0.25,
    )

    assert len(episodes) == 1
    assert episodes[0].result == "censored"
    assert episodes[0].first_eligible_recovery_s is None
    assert episodes[0].recovery_identity == "unavailable"


def test_invalid_stable_recovery_duration_is_rejected():
    with pytest.raises(
        ValueError,
        match="finite and greater than zero",
    ):
        MODULE.build_absence_recovery_episodes(
            [],
            [],
            stable_duration_s=0.0,
        )


def test_status_parser_supports_current_rich_schema():
    payload = {
        "state": "LOST",
        "target_track_id": 1,
        "candidate_track_id": 42,
        "publication_suppressed_reason": "appearance_margin",
        "positive_memory_updated": False,
        "positive_memory_update_reason": "state_not_locked",
        "hard_negative_events": [
            {"event": "promoted", "track_id": 7},
            {"event": "expired", "track_id": 8},
        ],
    }

    sample = MODULE.parse_status_payload(
        1.25,
        __import__("json").dumps(payload),
    )

    assert sample.payload_valid is True
    assert sample.state == "LOST"
    assert sample.target_track_id == 1
    assert sample.candidate_track_id == 42
    assert (
        sample.publication_suppressed_reason
        == "appearance_margin"
    )
    assert sample.positive_memory_updated is False
    assert len(sample.hard_negative_events) == 2
    assert (
        MODULE.STATUS_FIELD_CANDIDATE_TRACK_ID
        in sample.available_fields
    )


def test_status_parser_preserves_older_schema_unavailability():
    sample = MODULE.parse_status_payload(
        0.0,
        '{"state":"LOCKED","target_track_id":1,"visible":true}',
    )

    availability = MODULE.status_schema_availability([sample])

    assert sample.payload_valid is True
    assert sample.state == "LOCKED"
    assert sample.candidate_track_id is None
    assert sample.publication_suppressed_reason is None
    assert sample.positive_memory_updated is None
    assert sample.hard_negative_events == ()
    assert availability[MODULE.STATUS_FIELD_STATE] is True
    assert (
        availability[MODULE.STATUS_FIELD_CANDIDATE_TRACK_ID]
        is False
    )
    assert (
        availability[MODULE.STATUS_FIELD_SUPPRESSION_REASON]
        is False
    )
    assert (
        availability[
            MODULE.STATUS_FIELD_POSITIVE_MEMORY_UPDATED
        ]
        is False
    )


def test_invalid_status_json_is_retained_as_invalid():
    sample = MODULE.parse_status_payload(
        0.0,
        "{not valid json",
    )

    assert sample.payload_valid is False
    assert sample.state is None
    assert sample.available_fields == frozenset()


def test_state_occupancy_uses_half_open_status_intervals():
    samples = [
        MODULE.parse_status_payload(
            0.0,
            '{"state":"LOCKED"}',
        ),
        MODULE.parse_status_payload(
            1.0,
            '{"state":"UNCERTAIN"}',
        ),
        MODULE.parse_status_payload(
            1.5,
            '{"state":"LOST"}',
        ),
        MODULE.parse_status_payload(
            2.5,
            '{"state":"LOCKED"}',
        ),
    ]

    occupancy = MODULE.compute_state_occupancy(
        samples,
        end_s=3.0,
    )

    assert occupancy.available is True
    assert occupancy.sample_count == 4
    assert occupancy.total_duration_s == pytest.approx(3.0)
    assert occupancy.duration_by_state_s == pytest.approx(
        {
            "LOCKED": 1.5,
            "UNCERTAIN": 0.5,
            "LOST": 1.0,
        }
    )


def test_state_occupancy_replaces_duplicate_timestamp():
    samples = [
        MODULE.parse_status_payload(
            0.0,
            '{"state":"LOCKED"}',
        ),
        MODULE.parse_status_payload(
            1.0,
            '{"state":"UNCERTAIN"}',
        ),
        MODULE.parse_status_payload(
            1.0,
            '{"state":"LOST"}',
        ),
    ]

    occupancy = MODULE.compute_state_occupancy(
        samples,
        end_s=2.0,
    )

    assert occupancy.sample_count == 2
    assert occupancy.duration_by_state_s == pytest.approx(
        {
            "LOCKED": 1.0,
            "LOST": 1.0,
        }
    )


def test_state_occupancy_reports_missing_status_as_unavailable():
    occupancy = MODULE.compute_state_occupancy([])

    assert occupancy.available is False
    assert occupancy.total_duration_s == pytest.approx(0.0)
    assert occupancy.duration_by_state_s == {}
    assert occupancy.sample_count == 0


def test_state_occupancy_counts_invalid_payloads():
    samples = [
        MODULE.parse_status_payload(
            0.0,
            "{invalid",
        ),
        MODULE.parse_status_payload(
            0.5,
            '{"state":"LOCKED"}',
        ),
    ]

    occupancy = MODULE.compute_state_occupancy(
        samples,
        end_s=1.0,
    )

    assert occupancy.available is True
    assert occupancy.invalid_payload_count == 1
    assert occupancy.duration_by_state_s == pytest.approx(
        {"LOCKED": 0.5}
    )


def rich_status(
    t_s: float,
    *,
    state: str,
    candidate_id,
    suppression_reason: str = "",
):
    payload = {
        "state": state,
        "candidate_track_id": candidate_id,
        "publication_suppressed_reason": suppression_reason,
    }
    return MODULE.parse_status_payload(
        t_s,
        __import__("json").dumps(payload),
    )


def test_recovery_attempts_merge_repeated_same_candidate():
    statuses = [
        rich_status(
            0.0,
            state="LOST",
            candidate_id=7,
        ),
        rich_status(
            0.1,
            state="LOST",
            candidate_id=7,
        ),
        rich_status(
            0.2,
            state="REACQUIRED",
            candidate_id=7,
        ),
        rich_status(
            0.3,
            state="LOCKED",
            candidate_id=7,
        ),
    ]

    attempts = MODULE.recovery_attempts_from_status(
        statuses,
        end_s=0.4,
    )

    assert attempts is not None
    assert len(attempts) == 1
    assert attempts[0].candidate_track_id == 7
    assert attempts[0].start_s == pytest.approx(0.0)
    assert attempts[0].end_s == pytest.approx(0.3)
    assert attempts[0].duration_s == pytest.approx(0.3)
    assert attempts[0].initial_state == "LOST"
    assert attempts[0].final_state == "REACQUIRED"
    assert attempts[0].sample_count == 3


def test_candidate_change_starts_new_recovery_attempt():
    statuses = [
        rich_status(
            0.0,
            state="LOST",
            candidate_id=7,
        ),
        rich_status(
            0.1,
            state="LOST",
            candidate_id=8,
        ),
        rich_status(
            0.2,
            state="UNCERTAIN",
            candidate_id=8,
        ),
        rich_status(
            0.3,
            state="LOST",
            candidate_id=None,
        ),
    ]

    attempts = MODULE.recovery_attempts_from_status(
        statuses,
        end_s=0.4,
    )

    assert attempts is not None
    assert [item.candidate_track_id for item in attempts] == [
        7,
        8,
    ]
    assert attempts[0].end_s == pytest.approx(0.1)
    assert attempts[1].end_s == pytest.approx(0.3)


def test_locked_candidate_is_not_a_recovery_attempt():
    statuses = [
        rich_status(
            0.0,
            state="LOCKED",
            candidate_id=1,
        ),
        rich_status(
            0.1,
            state="LOCKED",
            candidate_id=1,
        ),
    ]

    attempts = MODULE.recovery_attempts_from_status(
        statuses,
        end_s=0.2,
    )

    assert attempts == []


def test_old_status_schema_makes_attempts_unavailable():
    statuses = [
        MODULE.parse_status_payload(
            0.0,
            '{"state":"LOST","target_track_id":1}',
        )
    ]

    assert (
        MODULE.recovery_attempts_from_status(statuses)
        is None
    )


def test_correct_candidate_suppressed_duration():
    slices = [
        classified_slice(
            0.0,
            classification="lost",
            output_id=0,
        ),
        classified_slice(
            0.1,
            classification="wrong",
            output_id=3,
        ),
        classified_slice(
            0.2,
            classification="correct",
            output_id=1,
        ),
        classified_slice(
            0.3,
            classification="lost",
            output_id=0,
        ),
    ]

    statuses = [
        rich_status(
            0.0,
            state="LOST",
            candidate_id=1,
            suppression_reason="appearance_margin",
        ),
        rich_status(
            0.2,
            state="LOCKED",
            candidate_id=1,
            suppression_reason="",
        ),
        rich_status(
            0.3,
            state="LOST",
            candidate_id=2,
            suppression_reason="appearance_margin",
        ),
    ]

    result = MODULE.correct_candidate_suppression_metrics(
        slices,
        statuses,
    )

    assert result is not None
    duration_s, episode_count = result
    assert duration_s == pytest.approx(0.2)
    assert episode_count == 1


def test_correct_output_is_not_counted_as_suppressed():
    slices = [
        classified_slice(
            0.0,
            classification="correct",
            output_id=1,
        )
    ]
    statuses = [
        rich_status(
            0.0,
            state="REACQUIRED",
            candidate_id=1,
            suppression_reason="confirmation_pending",
        )
    ]

    result = MODULE.correct_candidate_suppression_metrics(
        slices,
        statuses,
    )

    assert result == pytest.approx((0.0, 0))


def test_old_schema_makes_suppression_unavailable():
    slices = [
        classified_slice(
            0.0,
            classification="lost",
            output_id=0,
        )
    ]
    statuses = [
        MODULE.parse_status_payload(
            0.0,
            '{"state":"LOST","target_track_id":1}',
        )
    ]

    assert (
        MODULE.correct_candidate_suppression_metrics(
            slices,
            statuses,
        )
        is None
    )


def test_status_recovery_summary_preserves_availability():
    slices = [
        classified_slice(
            0.0,
            classification="lost",
            output_id=0,
        )
    ]
    statuses = [
        rich_status(
            0.0,
            state="LOST",
            candidate_id=1,
            suppression_reason="appearance_margin",
        ),
        rich_status(
            0.1,
            state="LOCKED",
            candidate_id=1,
        ),
    ]

    metrics = MODULE.summarise_status_recovery_metrics(
        slices,
        statuses,
        end_s=0.2,
    )

    assert metrics.recovery_attempts_available is True
    assert metrics.recovery_attempt_count == 1
    assert (
        metrics.correct_candidate_suppressed_available
        is True
    )
    assert (
        metrics.correct_candidate_suppressed_duration_s
        == pytest.approx(0.1)
    )
    assert (
        metrics.correct_candidate_suppressed_episode_count
        == 1
    )


def memory_status(
    t_s: float,
    *,
    hard_negative_events=None,
    positive_updated=False,
    bootstrap_event=None,
):
    payload = {
        "state": "LOCKED",
        "positive_memory_updated": positive_updated,
        "positive_memory_update_reason": (
            "trusted_locked_update"
            if positive_updated
            else ""
        ),
        "positive_memory_bootstrap_event": bootstrap_event,
        "hard_negative_events": (
            []
            if hard_negative_events is None
            else hard_negative_events
        ),
    }
    return MODULE.parse_status_payload(
        t_s,
        __import__("json").dumps(payload),
    )


def test_memory_event_counts_all_hard_negative_actions():
    statuses = [
        memory_status(
            0.0,
            hard_negative_events=[
                {
                    "action": "stage",
                    "source_track_id": 2,
                },
                {
                    "action": "insert",
                    "source_track_ids": [2, 3],
                },
            ],
        ),
        memory_status(
            0.1,
            hard_negative_events=[
                {
                    "action": "expire",
                    "source_track_ids": [2],
                },
                {
                    "action": "discard_pending",
                    "source_track_ids": [3],
                },
            ],
        ),
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        [],
        statuses,
    )

    assert metrics.hard_negative_events_available is True
    assert metrics.hard_negative_event_count == 4
    assert metrics.hard_negative_action_counts == {
        "discard_pending": 1,
        "expire": 1,
        "insert": 1,
        "stage": 1,
    }


def test_correct_target_learned_as_negative_is_contamination():
    slices = [
        classified_slice(
            0.0,
            classification="correct",
            output_id=1,
        ),
        classified_slice(
            0.1,
            classification="lost",
            output_id=0,
        ),
    ]
    statuses = [
        memory_status(
            0.0,
            hard_negative_events=[
                {
                    "action": "stage",
                    "source_track_id": 1,
                },
                {
                    "action": "merge",
                    "source_track_ids": [1, 3],
                },
                {
                    "action": "expire",
                    "source_track_ids": [1],
                },
            ],
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        slices,
        statuses,
    )

    assert metrics.hard_negative_event_count == 3
    assert metrics.hard_negative_contamination_count == 2
    assert metrics.total_memory_contamination_count == 2


def test_expiry_of_correct_target_negative_is_not_new_contamination():
    slices = [
        classified_slice(
            0.0,
            classification="correct",
            output_id=1,
        )
    ]
    statuses = [
        memory_status(
            0.0,
            hard_negative_events=[
                {
                    "action": "expire",
                    "source_track_id": 1,
                },
                {
                    "action": "reconcile",
                    "source_track_ids": [1],
                },
                {
                    "action": "discard_pending",
                    "source_track_ids": [1],
                },
            ],
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        slices,
        statuses,
    )

    assert metrics.hard_negative_event_count == 3
    assert metrics.hard_negative_contamination_count == 0


def test_positive_update_while_wrong_is_contamination():
    slices = [
        classified_slice(
            0.0,
            classification="wrong",
            output_id=3,
        ),
        classified_slice(
            0.1,
            classification="correct",
            output_id=1,
        ),
    ]
    statuses = [
        memory_status(
            0.0,
            positive_updated=True,
        ),
        memory_status(
            0.1,
            positive_updated=True,
        ),
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        slices,
        statuses,
    )

    assert metrics.positive_memory_events_available is True
    assert metrics.positive_memory_update_count == 2
    assert metrics.positive_memory_contamination_count == 1
    assert metrics.total_memory_contamination_count == 1


def test_wrong_bootstrap_track_id_is_contamination():
    slices = [
        classified_slice(
            0.0,
            classification="lost",
            output_id=0,
        )
    ]
    statuses = [
        memory_status(
            0.0,
            bootstrap_event={
                "action": "protected_anchor_bootstrap",
                "track_id": 9,
            },
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        slices,
        statuses,
    )

    assert metrics.positive_memory_bootstrap_count == 1
    assert metrics.positive_memory_contamination_count == 1


def test_correct_bootstrap_is_not_contamination():
    slices = [
        classified_slice(
            0.0,
            classification="lost",
            output_id=0,
        )
    ]
    statuses = [
        memory_status(
            0.0,
            bootstrap_event={
                "action": "protected_anchor_bootstrap",
                "track_id": 1,
            },
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        slices,
        statuses,
    )

    assert metrics.positive_memory_bootstrap_count == 1
    assert metrics.positive_memory_contamination_count == 0


def test_old_schema_memory_metrics_are_unavailable():
    statuses = [
        MODULE.parse_status_payload(
            0.0,
            '{"state":"LOCKED","target_track_id":1}',
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        [],
        statuses,
    )

    assert metrics.hard_negative_events_available is False
    assert metrics.positive_memory_events_available is False
    assert metrics.hard_negative_event_count == 0
    assert metrics.positive_memory_update_count == 0
    assert metrics.total_memory_contamination_count == 0


def test_empty_current_memory_event_lists_are_available():
    statuses = [
        memory_status(
            0.0,
            hard_negative_events=[],
            positive_updated=False,
            bootstrap_event=None,
        )
    ]

    metrics = MODULE.summarise_memory_event_metrics(
        [],
        statuses,
    )

    assert metrics.hard_negative_events_available is True
    assert metrics.positive_memory_events_available is True
    assert metrics.hard_negative_event_count == 0
    assert metrics.hard_negative_action_counts == {}


def test_evaluation_bag_samples_retains_shared_origin():
    result = MODULE.EvaluationBagSamples(
        target_samples={
            "/target": [
                MODULE.TargetSample(
                    t_s=0.2,
                    track_id=7,
                    bbox_valid=True,
                )
            ]
        },
        status_samples={
            "/status": [
                MODULE.parse_status_payload(
                    0.2,
                    '{"state":"LOCKED"}',
                )
            ]
        },
        time_origin_ns=123456789,
    )

    assert result.time_origin_ns == 123456789
    assert result.target_samples["/target"][0].t_s == pytest.approx(
        result.status_samples["/status"][0].t_s
    )


def test_target_reader_is_compatibility_wrapper(monkeypatch):
    expected = MODULE.EvaluationBagSamples(
        target_samples={
            "/target": [
                MODULE.TargetSample(
                    t_s=0.0,
                    track_id=4,
                )
            ]
        },
        status_samples={},
        time_origin_ns=10,
    )
    calls = []

    def fake_reader(
        bag_path,
        target_topics,
        status_topics,
        timebase,
    ):
        calls.append(
            (
                bag_path,
                tuple(target_topics),
                tuple(status_topics),
                timebase,
            )
        )
        return expected

    monkeypatch.setattr(
        MODULE,
        "read_evaluation_samples_from_bag",
        fake_reader,
    )

    result = MODULE.read_target_samples_from_bag(
        __import__("pathlib").Path("bag"),
        topics=["/target"],
        timebase="header",
    )

    assert result is expected.target_samples
    assert calls == [
        (
            __import__("pathlib").Path("bag"),
            ("/target",),
            (),
            "header",
        )
    ]


def test_status_reader_is_compatibility_wrapper(monkeypatch):
    expected = MODULE.EvaluationBagSamples(
        target_samples={},
        status_samples={
            "/status": [
                MODULE.parse_status_payload(
                    0.0,
                    '{"state":"LOST"}',
                )
            ]
        },
        time_origin_ns=10,
    )
    calls = []

    def fake_reader(
        bag_path,
        target_topics,
        status_topics,
        timebase,
    ):
        calls.append(
            (
                bag_path,
                tuple(target_topics),
                tuple(status_topics),
                timebase,
            )
        )
        return expected

    monkeypatch.setattr(
        MODULE,
        "read_evaluation_samples_from_bag",
        fake_reader,
    )

    result = MODULE.read_status_samples_from_bag(
        __import__("pathlib").Path("bag"),
        topics=["/status"],
        timebase="bag",
    )

    assert result is expected.status_samples
    assert calls == [
        (
            __import__("pathlib").Path("bag"),
            (),
            ("/status",),
            "bag",
        )
    ]


def test_missing_requested_status_topic_returns_empty_list(
    monkeypatch,
):
    expected = MODULE.EvaluationBagSamples(
        target_samples={},
        status_samples={"/missing": []},
        time_origin_ns=10,
    )

    monkeypatch.setattr(
        MODULE,
        "read_evaluation_samples_from_bag",
        lambda **kwargs: expected,
    )

    result = MODULE.read_status_samples_from_bag(
        __import__("pathlib").Path("bag"),
        topics=["/missing"],
        timebase="bag",
    )

    assert result == {"/missing": []}


def test_headerless_status_uses_image_header_bag_offset():
    resolved = MODULE.evaluation_message_time_ns(
        bag_time_ns=1_500_000_000,
        message_header_time_ns=None,
        timebase="header",
        header_from_bag_offset_ns=8_000_000_000,
    )

    assert resolved == 9_500_000_000


def test_headered_message_keeps_its_header_timestamp():
    resolved = MODULE.evaluation_message_time_ns(
        bag_time_ns=1_500_000_000,
        message_header_time_ns=9_600_000_000,
        timebase="header",
        header_from_bag_offset_ns=8_000_000_000,
    )

    assert resolved == 9_600_000_000


def test_bag_timebase_ignores_header_and_offset():
    resolved = MODULE.evaluation_message_time_ns(
        bag_time_ns=1_500_000_000,
        message_header_time_ns=9_600_000_000,
        timebase="bag",
        header_from_bag_offset_ns=8_000_000_000,
    )

    assert resolved == 1_500_000_000


def test_headerless_message_without_mapping_is_unavailable():
    resolved = MODULE.evaluation_message_time_ns(
        bag_time_ns=1_500_000_000,
        message_header_time_ns=None,
        timebase="header",
        header_from_bag_offset_ns=None,
        header_anchors=[],
    )

    assert resolved is None


def test_headerless_message_uses_nearest_target_anchor():
    resolved = MODULE.evaluation_message_time_ns(
        bag_time_ns=1_510_000_000,
        message_header_time_ns=None,
        timebase="header",
        header_from_bag_offset_ns=None,
        header_anchors=[
            (1_500_000_000, 9_500_000_000),
            (1_550_000_000, 9_550_000_000),
        ],
    )

    assert resolved == 9_510_000_000


def test_nearest_anchor_prefers_earlier_on_equal_distance():
    resolved = MODULE.nearest_header_anchor_time_ns(
        bag_time_ns=1_525_000_000,
        anchors=[
            (1_500_000_000, 9_500_000_000),
            (1_550_000_000, 9_550_000_000),
        ],
    )

    assert resolved == 9_525_000_000
