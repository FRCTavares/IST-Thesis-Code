"""Synthetic physical-person attribution checks for Issue #125."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues"
    / "p125"
    / "evaluate_visdrone_selected_person.py"
)
SPEC = importlib.util.spec_from_file_location("p125_frame_attribution", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

TARGET = (0.0, 0.0, 10.0, 10.0)
OTHER = (20.0, 0.0, 30.0, 10.0)
FAR = (50.0, 0.0, 60.0, 10.0)
CONFIG = MODULE.AttributionConfig()


def classify(output, *, target=TARGET, others=((2, OTHER),), regions=()):
    return MODULE.classify_frame(
        target_bbox=target,
        target_identity=1,
        other_people=others,
        ambiguous_regions=regions,
        output_bbox=output,
        config=CONFIG,
    )


def test_unique_target_and_other_person_attribution():
    correct = classify(TARGET)
    wrong = classify(OTHER)
    assert (correct.bucket, correct.matched_identity) == (MODULE.CORRECT, 1)
    assert (wrong.bucket, wrong.matched_identity) == (MODULE.WRONG_PERSON, 2)


def test_unmatched_output_and_person_tie_are_unresolved():
    assert classify(FAR).bucket == MODULE.IDENTITY_UNRESOLVED
    tied = classify(TARGET, others=((2, TARGET),))
    assert tied.bucket == MODULE.IDENTITY_UNRESOLVED
    assert tied.reason == "person_attribution_not_unique"


def test_group_region_overlap_prevents_person_attribution():
    result = classify(TARGET, regions=(TARGET,))
    assert result.bucket == MODULE.IDENTITY_UNRESOLVED
    assert result.reason == "ambiguous_region_overlap"


def test_no_output_is_lost_but_missing_target_gt_is_reference_gap():
    lost = classify(None)
    gap = classify(OTHER, target=None)
    assert lost.bucket == MODULE.LOST_SUPPRESSED
    assert gap.bucket == MODULE.REFERENCE_UNAVAILABLE


def test_primary_counts_exclude_reference_gaps_and_reconcile():
    frames = [
        classify(TARGET),
        classify(OTHER),
        classify(FAR),
        classify(None),
        classify(TARGET, target=None),
    ]
    summary = MODULE.summarize_target_present(frames)
    assert summary["target_present_scored_frames"] == 4
    assert summary["reference_gap_frames"] == 1
    assert list(summary["counts"].values()) == [1, 1, 1, 1]
    assert sum(summary["fractions"].values()) == 1.0


def test_invalid_box_and_duplicate_physical_identity_rejected():
    with pytest.raises(ValueError, match="positive area"):
        classify((1.0, 1.0, 1.0, 2.0))
    with pytest.raises(ValueError, match="unique"):
        classify(TARGET, others=((1, OTHER),))


def gt_row(frame, identity, bbox, *, class_id=1, included=True):
    return SimpleNamespace(
        normalized_frame_index=frame,
        identity=identity,
        bbox_xyxy=bbox,
        class_id=class_id,
        include_as_person_candidate=included,
    )


def test_episode_scoring_keeps_gt_gap_outside_four_bucket_denominator():
    rows = [
        gt_row(0, 1, TARGET),
        gt_row(1, 1, TARGET),
        gt_row(1, 2, OTHER),
        gt_row(3, 1, TARGET),
        gt_row(4, 1, TARGET),
    ]
    result = MODULE.evaluate_episode(
        split="train",
        sequence_name="synthetic",
        dataset_identity=1,
        selection_frame_index=0,
        source_frame_indices=[0, 1, 2, 3, 4, 5],
        gt_rows=rows,
        output_bboxes_by_frame={
            0: TARGET, 1: OTHER, 2: OTHER, 3: FAR, 4: None, 5: OTHER,
        },
        config=CONFIG,
    )
    assert result["last_target_observation_frame_index"] == 4
    assert [frame["bucket"] for frame in result["frames"]] == [
        MODULE.CORRECT,
        MODULE.WRONG_PERSON,
        MODULE.REFERENCE_UNAVAILABLE,
        MODULE.IDENTITY_UNRESOLVED,
        MODULE.LOST_SUPPRESSED,
    ]
    assert result["scoring"]["target_present_scored_frames"] == 4
    assert result["scoring"]["reference_gap_frames"] == 1
    assert list(result["scoring"]["counts"].values()) == [1, 1, 1, 1]
    assert result["events"]["wrong_person_event_count"] == 1
    assert result["events"]["correct_to_wrong_handover_count"] == 1
    assert result["events"]["reference_gap_reappearance_count"] == 1
    assert result["events"]["successful_correct_reacquisition_count"] == 0


def test_episode_rejects_missing_source_image_and_invalid_selection():
    with pytest.raises(ValueError, match="no source image"):
        MODULE.evaluate_episode(
            split="val",
            sequence_name="synthetic",
            dataset_identity=1,
            selection_frame_index=0,
            source_frame_indices=[0],
            gt_rows=[gt_row(1, 1, TARGET)],
            output_bboxes_by_frame={},
            config=CONFIG,
        )
    with pytest.raises(ValueError, match="lacks valid target GT"):
        MODULE.evaluate_episode(
            split="val",
            sequence_name="synthetic",
            dataset_identity=1,
            selection_frame_index=0,
            source_frame_indices=[0, 1],
            gt_rows=[gt_row(1, 1, TARGET)],
            output_bboxes_by_frame={},
            config=CONFIG,
        )


def event_record(frame, bucket, identity=None):
    return {
        "normalized_frame_index": frame,
        "bucket": bucket,
        "matched_identity": identity,
    }


def test_event_runs_and_reappearance_recovery_use_source_frames():
    events = MODULE.derive_events([
        event_record(0, MODULE.CORRECT, 1),
        event_record(1, MODULE.WRONG_PERSON, 2),
        event_record(2, MODULE.WRONG_PERSON, 2),
        event_record(3, MODULE.LOST_SUPPRESSED),
        event_record(4, MODULE.LOST_SUPPRESSED),
        event_record(5, MODULE.REFERENCE_UNAVAILABLE),
        event_record(6, MODULE.IDENTITY_UNRESOLVED),
        event_record(7, MODULE.CORRECT, 1),
    ])
    assert events["wrong_person_events"] == [{
        "start_frame_index": 1,
        "end_frame_index": 2,
        "matched_identity": 2,
    }]
    assert events["correct_to_wrong_handover_count"] == 1
    assert events["lost_runs"] == [{
        "start_frame_index": 3,
        "end_frame_index": 4,
        "length_frames": 2,
    }]
    assert events["reference_gap_reappearances"] == [{
        "reference_gap_start_frame_index": 5,
        "first_reappearance_frame_index": 6,
        "first_correct_frame_index": 7,
        "frames_to_correct_reacquisition": 1,
    }]


def test_wrong_identity_change_starts_new_event_and_frame_gap_breaks_run():
    events = MODULE.derive_events([
        event_record(0, MODULE.WRONG_PERSON, 2),
        event_record(1, MODULE.WRONG_PERSON, 3),
        event_record(3, MODULE.WRONG_PERSON, 3),
    ])
    assert events["wrong_person_event_count"] == 3
    assert events["correct_to_wrong_handover_count"] == 0
