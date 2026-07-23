"""Tests for event-level selected-target evaluation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "evaluate_tim_by_event_type.py"
)

SPEC = importlib.util.spec_from_file_location(
    "evaluate_tim_by_event_type",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_interval(
    start_s: float,
    end_s: float,
    target_label: str,
    target_visible: bool,
    correct_id: int,
    event_type: str,
):
    """Construct one authoritative annotation interval."""
    return MODULE.AnnotationInterval(
        bag_name="test_bag",
        start_s=start_s,
        end_s=end_s,
        target_label=target_label,
        target_visible=target_visible,
        correct_target_track_id=correct_id,
        distractor_track_ids="",
        event_type=event_type,
        notes="",
    )


def aggregate(
    grouped: dict[str, dict[str, float]],
    field: str,
) -> float:
    """Sum one duration field across all event categories."""
    return sum(
        values.get(field, 0.0)
        for values in grouped.values()
    )


def test_event_totals_match_authoritative_evaluator():
    """Preserve the authoritative grid and ID classification exactly."""
    intervals = [
        make_interval(
            0.00,
            0.11,
            "CORRECT_TARGET",
            True,
            1,
            "clean_visible",
        ),
        make_interval(
            0.11,
            0.21,
            "CORRECT_TARGET",
            True,
            2,
            "id_switch_fragmentation",
        ),
        make_interval(
            0.21,
            0.31,
            "CORRECT_TARGET",
            False,
            0,
            "target_absent",
        ),
        make_interval(
            0.31,
            0.36,
            "NO_TARGET_SELECTED",
            False,
            0,
            "no_selection",
        ),
    ]

    samples = [
        MODULE.TargetSample(t_s=0.00, track_id=1),
        MODULE.TargetSample(t_s=0.10, track_id=0),
        MODULE.TargetSample(t_s=0.15, track_id=3),
        MODULE.TargetSample(t_s=0.20, track_id=2),
        MODULE.TargetSample(t_s=0.25, track_id=4),
        MODULE.TargetSample(t_s=0.30, track_id=0),
        MODULE.TargetSample(t_s=0.32, track_id=7),
    ]

    authoritative = MODULE.evaluate_authoritative_stream(
        intervals,
        samples,
        0.05,
    )
    grouped = MODULE.evaluate_by_event_type(
        samples,
        intervals,
        0.05,
    )

    assert aggregate(
        grouped,
        "correct_s",
    ) == pytest.approx(
        authoritative.correct_target_duration_s
    )
    assert aggregate(
        grouped,
        "wrong_s",
    ) == pytest.approx(
        authoritative.wrong_target_duration_s
    )
    assert aggregate(
        grouped,
        "lost_s",
    ) == pytest.approx(
        authoritative.lost_target_duration_s
    )
    assert aggregate(
        grouped,
        "target_not_visible_s",
    ) == pytest.approx(
        authoritative.target_not_visible_duration_s
    )
    assert aggregate(
        grouped,
        "target_absent_but_output_s",
    ) == pytest.approx(
        authoritative.target_absent_but_output_valid_duration_s
    )
    assert aggregate(
        grouped,
        "no_target_selected_s",
    ) == pytest.approx(
        authoritative.no_target_selected_duration_s
    )
    assert aggregate(
        grouped,
        "visible_s",
    ) == pytest.approx(
        authoritative.visible_target_duration_s
    )


def test_evaluate_bag_loads_both_streams_with_one_timebase(
    monkeypatch,
    tmp_path,
):
    """Require one shared origin rather than per-stream target origins."""
    intervals = [
        make_interval(
            0.0,
            0.1,
            "CORRECT_TARGET",
            True,
            1,
            "clean_visible",
        )
    ]
    calls = []

    monkeypatch.setattr(
        MODULE,
        "load_annotations",
        lambda _path: intervals,
    )

    def fake_read_target_samples(
        bag,
        topics,
        timebase,
    ):
        calls.append(
            {
                "bag": bag,
                "topics": list(topics),
                "timebase": timebase,
            }
        )
        return {
            "/raw_test": [
                MODULE.TargetSample(
                    t_s=0.0,
                    track_id=1,
                )
            ],
            "/tim_test": [
                MODULE.TargetSample(
                    t_s=0.0,
                    track_id=1,
                )
            ],
        }

    monkeypatch.setattr(
        MODULE,
        "read_target_samples_from_bag",
        fake_read_target_samples,
    )

    rows = MODULE.evaluate_bag(
        bag=tmp_path / "bag",
        annotations_path=tmp_path / "annotations.csv",
        step_s=0.05,
        timebase="header",
        raw_topic="/raw_test",
        tim_topic="/tim_test",
    )

    assert calls == [
        {
            "bag": tmp_path / "bag",
            "topics": [
                "/raw_test",
                "/tim_test",
            ],
            "timebase": "header",
        }
    ]
    assert [
        row["stream"]
        for row in rows
    ] == [
        "raw_target",
        "tim_target_memory",
    ]


def test_cli_defaults_to_authoritative_header_contract(
    monkeypatch,
):
    """Keep the paper-facing event evaluator on header time by default."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(MODULE_PATH),
            "bag",
            "--annotations",
            "annotations.csv",
            "--out",
            "result.csv",
        ],
    )

    args = MODULE.parse_args()

    assert args.timebase == "header"
    assert args.dt == 0.05
    assert args.raw_topic == MODULE.TARGET_TOPIC_RAW
    assert args.tim_topic == MODULE.TARGET_TOPIC_TIM
    assert (
        args.max_output_age_s
        == MODULE.DEFAULT_MAX_OUTPUT_AGE_S
    )


def test_event_evaluator_records_stale_output_as_lost():
    intervals = [
        make_interval(
            0.0,
            0.5,
            "CORRECT_TARGET",
            True,
            1,
            "clean_visible",
        )
    ]
    samples = [MODULE.TargetSample(t_s=0.0, track_id=1)]

    grouped = MODULE.evaluate_by_event_type(
        samples,
        intervals,
        step_s=0.1,
        max_output_age_s=0.2,
    )

    values = grouped["clean_visible"]
    assert values["correct_s"] == pytest.approx(0.3)
    assert values["lost_s"] == pytest.approx(0.2)
    assert values["stale_output_s"] == pytest.approx(0.2)


def test_event_evaluator_treats_invalid_bbox_as_lost():
    intervals = [
        make_interval(
            0.0,
            0.1,
            "CORRECT_TARGET",
            True,
            1,
            "clean_visible",
        )
    ]
    samples = [
        MODULE.TargetSample(
            t_s=0.0,
            track_id=1,
            bbox_valid=False,
        )
    ]

    grouped = MODULE.evaluate_by_event_type(
        samples,
        intervals,
        step_s=0.1,
    )

    values = grouped["clean_visible"]
    assert values.get("correct_s", 0.0) == pytest.approx(0.0)
    assert values.get("wrong_s", 0.0) == pytest.approx(0.0)
    assert values["lost_s"] == pytest.approx(0.1)
