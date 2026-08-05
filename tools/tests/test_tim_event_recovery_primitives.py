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
