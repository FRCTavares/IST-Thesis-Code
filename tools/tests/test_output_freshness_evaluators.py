"""Cross-evaluator tests for the shared maximum-output-age rule."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "tools" / "analysis"


def load(name: str, filename: str):
    path = ANALYSIS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ID_EVAL = load(
    "freshness_id_evaluator",
    "evaluate_tim_target_correctness.py",
)
BBOX_EVAL = load(
    "freshness_bbox_evaluator",
    "evaluate_tim_target_bbox_correctness.py",
)


def interval(end_s: float = 1.1):
    return ID_EVAL.AnnotationInterval(
        bag_name="bag",
        start_s=0.0,
        end_s=end_s,
        target_label="CORRECT_TARGET",
        target_visible=True,
        correct_target_track_id=7,
        distractor_track_ids="",
        event_type="clean_visible",
        notes="",
    )


def test_latest_preceding_output_expires_at_shared_boundary():
    samples = [ID_EVAL.TargetSample(t_s=0.0, track_id=7)]

    assert ID_EVAL.sample_id_at_time(samples, 0.9, 0.9) == 7
    assert ID_EVAL.sample_id_at_time(samples, 0.901, 0.9) == 0


def test_id_evaluator_records_stale_duration_as_lost():
    stats = ID_EVAL.evaluate_stream(
        [interval()],
        [ID_EVAL.TargetSample(t_s=0.0, track_id=7)],
        step_s=0.1,
        max_output_age_s=0.2,
    )

    assert stats.stale_output_duration_s == pytest.approx(0.8)
    assert stats.correct_target_duration_s == pytest.approx(0.3)
    assert stats.lost_target_duration_s == pytest.approx(0.8)


def test_bbox_evaluator_uses_identical_stale_as_lost_rule():
    tracks = [
        BBOX_EVAL.TrackSample(
            t_s=t,
            tracks={7: (10.0, 10.0, 5.0, 10.0)},
        )
        for t in (0.0, 0.1, 0.2, 0.3, 0.4)
    ]
    outputs = [
        BBOX_EVAL.TargetSample(
            t_s=0.0,
            id=7,
            box=(10.0, 10.0, 5.0, 10.0),
        )
    ]
    annotations = [
        BBOX_EVAL.Interval(
            start_s=0.0,
            end_s=0.4,
            target_label="CORRECT_TARGET",
            target_visible=True,
            correct_target_track_id=7,
        )
    ]

    stats = BBOX_EVAL.score_on_tracks_clock(
        tracks,
        outputs,
        annotations,
        iou_threshold=0.5,
        centre_distance_threshold=0.5,
        max_output_age_s=0.2,
    )

    assert stats.correct_target_duration_s == pytest.approx(0.3)
    assert stats.stale_output_duration_s == pytest.approx(0.1)
    assert stats.lost_target_duration_s == pytest.approx(0.1)
