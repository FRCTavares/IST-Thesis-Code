"""Boundary and validity matrix for selected-target evaluators."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
    "target_correctness_matrix_id",
    "evaluate_tim_target_correctness.py",
)
BBOX_EVAL = load(
    "target_correctness_matrix_bbox",
    "evaluate_tim_target_bbox_correctness.py",
)
SHARED_EVAL = sys.modules["tim_evaluation"]


def interval(
    start_s: float,
    end_s: float,
    *,
    correct_id: int = 7,
    label: str = "CORRECT_TARGET",
    visible: bool = True,
    bag_name: str = "bag",
):
    return ID_EVAL.AnnotationInterval(
        bag_name=bag_name,
        start_s=start_s,
        end_s=end_s,
        target_label=label,
        target_visible=visible,
        correct_target_track_id=correct_id,
        distractor_track_ids="",
        event_type="test",
        notes="",
    )


def test_interval_boundaries_are_half_open_and_exact():
    annotations = [
        interval(0.0, 0.2, correct_id=1),
        interval(0.2, 0.4, correct_id=2),
    ]
    samples = [
        ID_EVAL.TargetSample(t_s=0.0, track_id=1),
        ID_EVAL.TargetSample(t_s=0.2, track_id=2),
    ]

    stats = ID_EVAL.evaluate_stream(
        annotations,
        samples,
        step_s=0.1,
    )

    assert ID_EVAL.make_time_grid(
        annotations[0],
        0.1,
    ) == pytest.approx([0.0, 0.1])
    assert stats.visible_target_duration_s == pytest.approx(0.4)
    assert stats.correct_target_duration_s == pytest.approx(0.4)
    assert stats.wrong_target_duration_s == pytest.approx(0.0)
    assert stats.lost_target_duration_s == pytest.approx(0.0)


def test_annotation_gaps_are_unscored():
    annotations = [
        interval(0.0, 0.1),
        interval(0.2, 0.3),
    ]
    samples = [ID_EVAL.TargetSample(t_s=0.0, track_id=7)]

    stats = ID_EVAL.evaluate_stream(
        annotations,
        samples,
        step_s=0.05,
    )

    assert stats.visible_target_duration_s == pytest.approx(0.2)
    assert stats.correct_target_duration_s == pytest.approx(0.2)


def test_overlapping_annotation_intervals_are_rejected():
    with pytest.raises(
        ValueError,
        match="Overlapping annotation intervals",
    ):
        ID_EVAL.validate_annotations(
            [
                interval(0.0, 0.2),
                interval(0.1, 0.3),
            ]
        )


def test_zero_duration_annotation_is_allowed_and_ignored():
    annotations = [
        interval(0.0, 0.0),
        interval(0.0, 0.1),
    ]
    ID_EVAL.validate_annotations(annotations)

    stats = ID_EVAL.evaluate_stream(
        annotations,
        [ID_EVAL.TargetSample(t_s=0.0, track_id=7)],
        step_s=0.05,
    )

    assert ID_EVAL.make_time_grid(
        annotations[0],
        0.05,
    ) == []
    assert stats.visible_target_duration_s == pytest.approx(0.1)
    assert stats.correct_target_duration_s == pytest.approx(0.1)


def test_negative_duration_annotation_is_rejected():
    with pytest.raises(
        ValueError,
        match="negative duration",
    ):
        ID_EVAL.validate_annotations(
            [interval(0.2, 0.1)]
        )


def test_missing_messages_are_lost_for_visible_target():
    stats = ID_EVAL.evaluate_stream(
        [interval(0.0, 0.3)],
        [],
        step_s=0.1,
    )

    assert stats.visible_target_duration_s == pytest.approx(0.3)
    assert stats.correct_target_duration_s == pytest.approx(0.0)
    assert stats.lost_target_duration_s == pytest.approx(0.3)
    assert stats.stale_output_duration_s == pytest.approx(0.0)


def test_stale_last_output_is_lost_at_shared_boundary():
    stats = ID_EVAL.evaluate_stream(
        [interval(0.0, 0.5)],
        [ID_EVAL.TargetSample(t_s=0.0, track_id=7)],
        step_s=0.1,
        max_output_age_s=0.2,
    )

    assert stats.correct_target_duration_s == pytest.approx(0.3)
    assert stats.lost_target_duration_s == pytest.approx(0.2)
    assert stats.stale_output_duration_s == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("label", "visible"),
    [
        ("TARGET_NOT_VISIBLE", True),
        ("CORRECT_TARGET", False),
    ],
)
def test_target_not_visible_with_valid_output_is_counted(
    label,
    visible,
):
    stats = ID_EVAL.evaluate_stream(
        [
            interval(
                0.0,
                0.2,
                label=label,
                visible=visible,
            )
        ],
        [ID_EVAL.TargetSample(t_s=0.0, track_id=7)],
        step_s=0.1,
    )

    assert stats.target_not_visible_duration_s == pytest.approx(0.2)
    assert (
        stats.target_absent_but_output_valid_duration_s
        == pytest.approx(0.2)
    )
    assert stats.visible_target_duration_s == pytest.approx(0.0)


def test_different_stream_start_times_are_not_rebased():
    annotations = [interval(0.0, 0.3)]
    early = [ID_EVAL.TargetSample(t_s=0.0, track_id=7)]
    delayed = [ID_EVAL.TargetSample(t_s=0.2, track_id=7)]

    early_stats = ID_EVAL.evaluate_stream(
        annotations,
        early,
        step_s=0.1,
    )
    delayed_stats = ID_EVAL.evaluate_stream(
        annotations,
        delayed,
        step_s=0.1,
    )

    assert early_stats.correct_target_duration_s == pytest.approx(0.3)
    assert delayed_stats.correct_target_duration_s == pytest.approx(0.1)
    assert delayed_stats.lost_target_duration_s == pytest.approx(0.2)


def _stamp(seconds: int):
    return SimpleNamespace(sec=seconds, nanosec=0)


def _message(track_id: int, header_seconds: int):
    return SimpleNamespace(
        track_id=track_id,
        header=SimpleNamespace(stamp=_stamp(header_seconds)),
        cx=10.0,
        cy=20.0,
        w=5.0,
        h=10.0,
    )


def test_bag_and_header_time_use_distinct_shared_origins(
    monkeypatch,
    tmp_path,
):
    records = [
        ("/target", _message(7, 100), 1_000_000_000),
        (
            "/camera/dashboard",
            SimpleNamespace(
                header=SimpleNamespace(stamp=_stamp(110))
            ),
            2_000_000_000,
        ),
        (
            "/target_memory_mars",
            _message(8, 111),
            3_000_000_000,
        ),
    ]
    topic_types = {
        "/target": "Target",
        "/camera/dashboard": "Image",
        "/target_memory_mars": "Target",
    }

    class FakeReader:
        def open(self, _storage, _converter):
            self.index = 0

        def get_all_topics_and_types(self):
            return [
                SimpleNamespace(name=name, type=type_name)
                for name, type_name in topic_types.items()
            ]

        def has_next(self):
            return self.index < len(records)

        def read_next(self):
            record = records[self.index]
            self.index += 1
            return record

    class Options:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(
        SHARED_EVAL,
        "import_rosbag_tools",
        lambda: (
            FakeReader,
            Options,
            Options,
            lambda data, _msg_type: data,
            lambda _type_name: object,
        ),
    )

    topics = ["/target", "/target_memory_mars"]
    bag_samples = ID_EVAL.read_target_samples_from_bag(
        tmp_path,
        topics,
        timebase="bag",
    )
    header_samples = ID_EVAL.read_target_samples_from_bag(
        tmp_path,
        topics,
        timebase="header",
    )

    assert bag_samples["/target"][0].t_s == pytest.approx(0.0)
    assert (
        bag_samples["/target_memory_mars"][0].t_s
        == pytest.approx(2.0)
    )
    assert header_samples["/target"][0].t_s == pytest.approx(-10.0)
    assert (
        header_samples["/target_memory_mars"][0].t_s
        == pytest.approx(1.0)
    )


@pytest.mark.parametrize(
    ("track_id", "box"),
    [
        (0, (10.0, 10.0, 5.0, 10.0)),
        (7, (10.0, 10.0, 0.0, 10.0)),
        (7, (10.0, 10.0, 5.0, float("nan"))),
    ],
)
def test_inconsistent_id_bbox_output_is_lost(
    track_id,
    box,
):
    tracks = [
        BBOX_EVAL.TrackSample(
            t_s=0.0,
            tracks={7: (10.0, 10.0, 5.0, 10.0)},
        ),
        BBOX_EVAL.TrackSample(
            t_s=0.1,
            tracks={7: (10.0, 10.0, 5.0, 10.0)},
        ),
    ]
    outputs = [
        BBOX_EVAL.TargetSample(
            t_s=0.0,
            id=track_id,
            box=box,
        )
    ]
    annotations = [
        BBOX_EVAL.Interval(
            start_s=0.0,
            end_s=0.1,
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
    )

    assert stats.correct_target_duration_s == pytest.approx(0.0)
    assert stats.wrong_target_duration_s == pytest.approx(0.0)
    assert stats.lost_target_duration_s == pytest.approx(0.1)


def test_id_evaluator_rejects_nonzero_id_with_invalid_bbox():
    sample = ID_EVAL.TargetSample(
        t_s=0.0,
        track_id=7,
        bbox_valid=False,
    )

    assert ID_EVAL.sample_id_at_time([sample], 0.0) == 0
    stats = ID_EVAL.evaluate_stream(
        [interval(0.0, 0.1)],
        [sample],
        step_s=0.1,
    )
    assert stats.lost_target_duration_s == pytest.approx(0.1)
