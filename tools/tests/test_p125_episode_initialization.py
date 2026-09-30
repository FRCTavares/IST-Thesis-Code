"""Synthetic GT-to-tracker initialization and authority timing checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues" / "p125" / "resolve_episode_initialization.py"
)
SPEC = importlib.util.spec_from_file_location("p125_episode_initialization", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BOX = (1.0, 2.0, 11.0, 12.0)
EPISODE = {
    "dataset_identity": 3,
    "selection_frame_index": 0,
    "initialization_end_frame_inclusive": 2,
}


def gt_row(frame):
    return SimpleNamespace(
        normalized_frame_index=frame,
        identity=3,
        bbox_xyxy=BOX,
        include_as_person_candidate=True,
        class_id=1,
    )


def tracker_frame(frame, identities):
    return {
        "normalized_frame_index": frame,
        "tracks": [
            {"track_id": identity, "bbox_xyxy": list(BOX), "score": 0.8}
            for identity in identities
        ],
    }


def test_confirmation_starts_raw_authority_on_confirmation_frame():
    frames = [
        tracker_frame(0, [7]),
        tracker_frame(1, [7]),
        tracker_frame(2, []),
    ]
    result = MODULE.resolve_initialization(
        episode=EPISODE,
        gt_rows=[gt_row(0), gt_row(1), gt_row(2)],
        tracker_frames=frames,
    )
    assert result.success
    assert (result.initial_tracker_identity, result.initialization_frame_index) == (7, 1)
    boxes, identities = MODULE.raw_authority_maps(
        tracker_frames=frames, initialization=result
    )
    assert boxes == {0: None, 1: BOX, 2: None}
    assert identities == {0: None, 1: 7, 2: None}
    evaluator_path = MODULE_PATH.with_name("evaluate_visdrone_selected_person.py")
    evaluator_spec = importlib.util.spec_from_file_location("p125_init_evaluator", evaluator_path)
    assert evaluator_spec is not None and evaluator_spec.loader is not None
    evaluator = importlib.util.module_from_spec(evaluator_spec)
    sys.modules[evaluator_spec.name] = evaluator
    evaluator_spec.loader.exec_module(evaluator)
    score = evaluator.evaluate_episode(
        split="val",
        sequence_name="synthetic",
        dataset_identity=3,
        selection_frame_index=0,
        source_frame_indices=[0, 1, 2],
        gt_rows=[gt_row(0), gt_row(1), gt_row(2)],
        output_bboxes_by_frame=boxes,
        output_tracker_ids_by_frame=identities,
        config=evaluator.AttributionConfig(),
    )
    assert score["scoring"]["counts"][evaluator.CORRECT] == 1
    assert score["scoring"]["counts"][evaluator.LOST_SUPPRESSED] == 2


def test_ambiguous_match_retains_failure_and_suppresses_all_output():
    frames = [
        tracker_frame(0, [7, 8]),
        tracker_frame(1, [7, 8]),
        tracker_frame(2, [7, 8]),
    ]
    result = MODULE.resolve_initialization(
        episode=EPISODE,
        gt_rows=[gt_row(0), gt_row(1), gt_row(2)],
        tracker_frames=frames,
    )
    assert not result.success
    boxes, identities = MODULE.raw_authority_maps(
        tracker_frames=frames, initialization=result
    )
    assert all(value is None for value in boxes.values())
    assert all(value is None for value in identities.values())


def test_raw_sequence_scoring_retains_initialization_failure(tmp_path):
    scorer_path = MODULE_PATH.with_name("score_raw_tracker_sequence.py")
    scorer_spec = importlib.util.spec_from_file_location("p125_raw_sequence_scorer", scorer_path)
    assert scorer_spec is not None and scorer_spec.loader is not None
    scorer = importlib.util.module_from_spec(scorer_spec)
    sys.modules[scorer_spec.name] = scorer
    scorer_spec.loader.exec_module(scorer)
    episodes = [{
        **EPISODE, "split": "val", "sequence_name": "synthetic"
    }]
    frames = [
        {
            **tracker_frame(index, [7, 8]),
            "source_frame_number": index + 1,
            "logical_frame_stamp_ns": (index + 1) * 33_333_333,
        }
        for index in range(3)
    ]
    replay = {
        "schema": "p125_raw_tracker_sequence_replay_v1",
        "arm": "sort_raw",
        "split": "val",
        "sequence_name": "synthetic",
        "protocol_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "freeze_commit": "c" * 40,
        "detector_cache_sha256": "d" * 64,
        "tracker_config_sha256": "e" * 64,
        "logical_frame_tick_ns": 33_333_333,
        "logical_tick_is_physical_time": False,
        "frame_count": 3,
        "frames": frames,
    }
    validated = scorer.validate_raw_replay(
        replay,
        arm="sort_raw",
        split="val",
        sequence_name="synthetic",
        source_frame_numbers=[1, 2, 3],
        protocol_sha256="a" * 64,
        manifest_sha256="b" * 64,
        freeze_commit="c" * 40,
        detector_cache_sha256="d" * 64,
        tracker_config_sha256="e" * 64,
    )
    with pytest.raises(ValueError, match="detector_cache_sha256"):
        scorer.validate_raw_replay(
            replay,
            arm="sort_raw",
            split="val",
            sequence_name="synthetic",
            source_frame_numbers=[1, 2, 3],
            protocol_sha256="a" * 64,
            manifest_sha256="b" * 64,
            freeze_commit="c" * 40,
            detector_cache_sha256="f" * 64,
            tracker_config_sha256="e" * 64,
        )
    results = scorer.score_raw_episodes(
        split="val",
        sequence_name="synthetic",
        episodes=episodes,
        gt_rows=[gt_row(0), gt_row(1), gt_row(2)],
        tracker_frames=validated,
        initialization_rules={
            "minimum_match_iou": 0.5,
            "minimum_match_margin": 0.1,
            "confirmation_frames": 2,
        },
        evaluation_rules={
            "target_iou_threshold": 0.3,
            "unique_iou_margin": 0.1,
            "ambiguous_region_output_coverage_threshold": 0.5,
        },
    )
    assert results[0]["initialization"]["success"] is False
    assert results[0]["evaluation"]["scoring"]["counts"]["lost_suppressed"] == 3


def test_missing_tracker_window_endpoint_is_rejected():
    with pytest.raises(ValueError, match="endpoint"):
        MODULE.resolve_initialization(
            episode=EPISODE,
            gt_rows=[gt_row(0), gt_row(1), gt_row(2)],
            tracker_frames=[tracker_frame(0, [7]), tracker_frame(1, [7])],
        )
