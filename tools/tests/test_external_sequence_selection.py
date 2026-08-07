"""Tests for deterministic external target-candidate analysis."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "external_tracking"
    / "sequence_selection_gt.txt"
)

ADAPTER_PATH = ANALYSIS_DIR / "external_tracking_dataset.py"
SELECTION_PATH = ANALYSIS_DIR / "external_sequence_selection.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER = load_module(
    "external_tracking_dataset",
    ADAPTER_PATH,
)
SELECTION = load_module(
    "external_sequence_selection",
    SELECTION_PATH,
)


def rows():
    return ADAPTER.parse_motchallenge_annotations(
        FIXTURE,
        dataset="mot17",
        sequence_name="synthetic_selection",
        split="train",
        geometry=ADAPTER.SequenceGeometry(
            image_width=640,
            image_height=480,
            frame_rate=10.0,
            source_index_base=1,
        ),
        person_class_ids={1},
    )


def policy(**changes):
    values = {
        "minimum_visible_frames": 5,
        "minimum_consecutive_frames": 5,
        "initialization_window_frames": 5,
        "minimum_initialization_height_px": 40.0,
        "minimum_visibility": 0.4,
        "border_margin_px": 2.0,
        "competition_iou_threshold": 0.05,
        "close_centre_distance_norm": 0.15,
    }
    values.update(changes)
    return SELECTION.SelectionPolicy(**values)


def test_candidate_analysis_is_deterministically_ranked():
    results = SELECTION.analyse_target_candidates(
        rows(),
        policy=policy(),
    )

    assert [result.identity for result in results] == [1, 2, 3]

    first = results[0]
    assert first.identity == 1
    assert first.eligible is True
    assert first.visible_frame_count == 10
    assert first.longest_consecutive_run == 10
    assert first.initialization_start_frame == 0
    assert first.initialization_end_frame_inclusive == 4
    assert first.median_height_px == pytest.approx(140.0)
    assert first.minimum_height_px == pytest.approx(140.0)
    assert first.competing_person_frames == 10
    assert first.close_person_frames > 0
    assert first.overlapping_person_frames > 0


def test_short_small_border_target_is_excluded_with_reasons():
    result = next(
        item
        for item in SELECTION.analyse_target_candidates(
            rows(),
            policy=policy(),
        )
        if item.identity == 3
    )

    assert result.eligible is False
    assert result.visible_frame_count == 3
    assert result.longest_consecutive_run == 1
    assert result.border_touch_frames == 3
    assert result.initialization_eligible is False
    assert result.exclusion_reasons == (
        "insufficient_visible_frames",
        "insufficient_consecutive_visibility",
        "no_clean_initialization_window",
    )


def test_analysis_does_not_use_tim_outcomes():
    field_names = {
        field.name
        for field in SELECTION.TargetCandidateAnalysis.__dataclass_fields__.values()
    }

    forbidden = {
        "correct_target_ratio",
        "wrong_target_ratio",
        "tim_score",
        "recovery_count",
        "lost_target_duration",
    }

    assert field_names.isdisjoint(forbidden)


def test_input_must_belong_to_one_sequence():
    annotations = rows()
    changed = ADAPTER.ExternalObjectAnnotation(
        **{
            **annotations[0].__dict__,
            "sequence_name": "different_sequence",
        }
    )

    with pytest.raises(
        ValueError,
        match="exactly one sequence geometry",
    ):
        SELECTION.analyse_target_candidates(
            [annotations[0], changed],
            policy=policy(),
        )


def test_empty_candidate_set_returns_empty_list():
    excluded = [
        ADAPTER.ExternalObjectAnnotation(
            **{
                **row.__dict__,
                "include_as_person_candidate": False,
                "exclusion_reason": "synthetic_exclusion",
            }
        )
        for row in rows()
    ]

    assert SELECTION.analyse_target_candidates(
        excluded,
        policy=policy(),
    ) == []


def test_invalid_policy_is_rejected():
    with pytest.raises(ValueError):
        SELECTION.SelectionPolicy(
            minimum_visible_frames=0,
        )
