"""Focused tests for Issue #125 GT-only VisDrone corpus audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues"
    / "p125"
    / "audit_visdrone_selected_person_corpus.py"
)

SPEC = importlib.util.spec_from_file_location(
    "p125_visdrone_corpus_audit",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(
    identity: int,
    frame: int,
    *,
    height: float = 40.0,
    truncation: int | None = 0,
    occlusion: int | None = 0,
    included: bool = True,
):
    return SimpleNamespace(
        identity=identity,
        source_frame_number=frame + 1,
        normalized_frame_index=frame,
        bbox_xyxy=(10.0, 10.0, 30.0, 10.0 + height),
        truncation=truncation,
        occlusion=occlusion,
        include_as_person_candidate=included,
    )


def test_reconcile_frame_domain_reports_both_mismatch_directions():
    report = MODULE.reconcile_frame_domain(
        [1, 2, 3, 5],
        [1, 2, 4, 5],
    )

    assert report["image_frame_count"] == 4
    assert report["annotation_frame_count"] == 4
    assert report["intersection_frame_count"] == 3
    assert report["image_only_frames"] == [3]
    assert report["annotation_only_frames"] == [4]


def test_contiguous_segments_preserves_annotation_gaps():
    assert MODULE.contiguous_segments([1, 2, 3, 7, 8, 11]) == [
        (1, 3),
        (7, 8),
        (11, 11),
    ]


def test_eligibility_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        MODULE.EligibilityConfig(minimum_selection_height_px=0.0)

    with pytest.raises(ValueError):
        MODULE.EligibilityConfig(minimum_target_present_frames=0)

    with pytest.raises(ValueError):
        MODULE.EligibilityConfig(maximum_selection_occlusion=-1)

    with pytest.raises(ValueError):
        MODULE.EligibilityConfig(initialization_window_frames=0)


def test_episode_selection_uses_earliest_frame_passing_all_gt_gates():
    rows = [row(7, frame) for frame in range(35)]
    rows[0] = row(7, 0, height=19.0)
    rows[1] = row(7, 1, height=30.0, occlusion=2)
    rows[2] = row(7, 2, height=30.0, truncation=1, occlusion=1)

    episodes, exclusions = MODULE.build_episode_candidates(
        rows,
        split="val",
        sequence_name="synthetic",
        config=MODULE.EligibilityConfig(),
    )

    assert exclusions == {}
    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.dataset_identity == 7
    assert episode.selection_frame_index == 2
    assert episode.initialization_end_frame_inclusive == 11
    assert episode.target_present_frames_from_selection == 33


def test_episode_selection_requires_minimum_remaining_target_present_frames():
    rows = [row(9, frame) for frame in range(20)]

    episodes, exclusions = MODULE.build_episode_candidates(
        rows,
        split="train",
        sequence_name="short",
        config=MODULE.EligibilityConfig(
            minimum_target_present_frames=30,
        ),
    )

    assert episodes == []
    assert exclusions == {"insufficient_target_present_frames": 1}


def test_group_or_ignored_rows_cannot_create_episode():
    rows = [
        row(5, frame, included=False)
        for frame in range(40)
    ]

    episodes, exclusions = MODULE.build_episode_candidates(
        rows,
        split="val",
        sequence_name="excluded",
        config=MODULE.EligibilityConfig(),
    )

    assert episodes == []
    assert exclusions == {}


def test_heavy_occlusion_and_small_bbox_leave_no_selection_frame():
    rows = [
        row(3, frame, height=15.0)
        if frame % 2 == 0
        else row(3, frame, height=30.0, occlusion=2)
        for frame in range(40)
    ]

    episodes, exclusions = MODULE.build_episode_candidates(
        rows,
        split="val",
        sequence_name="no_selection",
        config=MODULE.EligibilityConfig(),
    )

    assert episodes == []
    assert exclusions == {"no_eligible_selection_frame": 1}


def test_initialization_window_is_capped_at_sequence_end():
    rows = [row(1, frame) for frame in range(35)]
    config = MODULE.EligibilityConfig(
        minimum_target_present_frames=1,
        initialization_window_frames=10,
    )

    for index in range(34):
        rows[index] = row(1, index, height=10.0)

    episodes, _ = MODULE.build_episode_candidates(
        rows,
        split="val",
        sequence_name="tail",
        config=config,
    )

    assert len(episodes) == 1
    assert episodes[0].selection_frame_index == 34
    assert episodes[0].initialization_end_frame_inclusive == 34


def test_parse_image_frame_number_is_strictly_positive_numeric():
    assert MODULE.parse_image_frame_number(Path("000001.jpg")) == 1

    with pytest.raises(ValueError, match="non-numeric"):
        MODULE.parse_image_frame_number(Path("frame_1.jpg"))

    with pytest.raises(ValueError, match="positive"):
        MODULE.parse_image_frame_number(Path("000000.jpg"))
