"""Tests for the Issue #26 event and recovery report CLI."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


CLI_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "evaluate_tim_event_recovery.py"
)
ANALYSIS_DIR = CLI_PATH.parent

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

SPEC = importlib.util.spec_from_file_location(
    "evaluate_tim_event_recovery_tested",
    CLI_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SHARED = sys.modules["tim_evaluation"]


def annotation(
    start_s: float,
    end_s: float,
    *,
    visible: bool,
    correct_id: int,
    event_type: str,
):
    return SHARED.AnnotationInterval(
        bag_name="test_bag",
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


def slice_row(
    t_s: float,
    classification: str,
    *,
    output_id: int,
    correct_id: int,
    event_type: str,
):
    return SHARED.ClassifiedSlice(
        annotation_index=0,
        bag_name="test_bag",
        event_type=event_type,
        t_s=t_s,
        duration_s=0.1,
        classification=classification,
        output_track_id=output_id,
        correct_target_track_id=correct_id,
        freshness_status="fresh",
    )


def status(
    t_s: float,
    *,
    state: str,
    candidate_id,
    suppression: str = "",
):
    return SHARED.parse_status_payload(
        t_s,
        json.dumps(
            {
                "state": state,
                "target_track_id": 1,
                "candidate_track_id": candidate_id,
                "publication_suppressed_reason": suppression,
                "positive_memory_updated": False,
                "positive_memory_update_reason": "",
                "positive_memory_bootstrap_event": None,
                "hard_negative_events": [],
            }
        ),
    )


def duration_row(stream: str):
    return {
        "stream": stream,
        "correct_target_duration_s": "0.100000",
        "wrong_target_duration_s": "0.100000",
        "lost_target_duration_s": "0.100000",
        "target_not_visible_duration_s": "0.100000",
        "target_absent_but_output_valid_duration_s": "0.000000",
        "no_target_selected_duration_s": "0.000000",
        "visible_target_duration_s": "0.300000",
        "stale_output_duration_s": "0.000000",
        "correct_target_ratio": "0.333333",
        "wrong_target_ratio": "0.333333",
        "lost_target_ratio": "0.333333",
    }


def synthetic_report():
    annotations = [
        annotation(
            0.0,
            0.2,
            visible=True,
            correct_id=1,
            event_type="clean_visible",
        ),
        annotation(
            0.2,
            0.3,
            visible=False,
            correct_id=0,
            event_type="target_absent",
        ),
        annotation(
            0.3,
            0.6,
            visible=True,
            correct_id=2,
            event_type="reentry",
        ),
    ]

    raw_slices = [
        slice_row(
            0.0,
            "correct",
            output_id=1,
            correct_id=1,
            event_type="clean_visible",
        ),
        slice_row(
            0.1,
            "wrong",
            output_id=3,
            correct_id=1,
            event_type="clean_visible",
        ),
        slice_row(
            0.2,
            "target_absent_clear",
            output_id=0,
            correct_id=0,
            event_type="target_absent",
        ),
        slice_row(
            0.3,
            "lost",
            output_id=0,
            correct_id=2,
            event_type="reentry",
        ),
        slice_row(
            0.4,
            "correct",
            output_id=2,
            correct_id=2,
            event_type="reentry",
        ),
        slice_row(
            0.5,
            "correct",
            output_id=2,
            correct_id=2,
            event_type="reentry",
        ),
    ]
    tim_slices = list(raw_slices)

    statuses = [
        status(
            0.0,
            state="LOCKED",
            candidate_id=1,
        ),
        status(
            0.3,
            state="LOST",
            candidate_id=2,
            suppression="confirmation_pending",
        ),
        status(
            0.4,
            state="REACQUIRED",
            candidate_id=2,
        ),
        status(
            0.5,
            state="LOCKED",
            candidate_id=2,
        ),
    ]

    return MODULE.build_report(
        bag_path=Path("bag"),
        annotation_path=Path("annotations.csv"),
        annotations=annotations,
        raw_slices=raw_slices,
        tim_slices=tim_slices,
        status_samples=statuses,
        raw_duration_row=duration_row("raw_target"),
        tim_duration_row=duration_row(
            "tim_target_memory"
        ),
        timebase="header",
        step_s=0.1,
        max_output_age_s=0.9,
        stable_duration_s=0.2,
        time_origin_ns=123,
        raw_topic="/target",
        tim_topic="/target_memory_mars",
        status_topic="/target_memory_mars/status",
    )


def test_report_has_versioned_complete_sections():
    report = synthetic_report()

    assert (
        report["schema_version"]
        == MODULE.REPORT_SCHEMA_VERSION
    )
    assert report["provenance"]["time_origin_ns"] == 123
    assert set(report["duration_metrics"]) == {
        "raw_target",
        "tim_target_memory",
    }
    assert report["event_rows"]
    assert report["burst_rows"]
    assert report["recovery_rows"]
    assert report["state_rows"]
    assert report["recovery_attempt_rows"]


def test_report_preserves_status_availability():
    report = synthetic_report()

    availability = report["status_schema_availability"]

    assert availability["state"] is True
    assert availability["candidate_track_id"] is True
    assert (
        availability["publication_suppressed_reason"]
        is True
    )
    assert (
        report["status_recovery_metrics"][
            "recovery_attempts_available"
        ]
        is True
    )


def test_write_report_is_deterministic(tmp_path):
    report = synthetic_report()

    first = tmp_path / "first"
    second = tmp_path / "second"

    MODULE.write_report(first, report)
    MODULE.write_report(second, report)

    filenames = [
        "report.json",
        "summary.csv",
        "events.csv",
        "bursts.csv",
        "recovery_episodes.csv",
        "state_occupancy.csv",
        "recovery_attempts.csv",
        "memory_events.csv",
        "summary.md",
    ]

    for filename in filenames:
        assert (
            first.joinpath(filename).read_bytes()
            == second.joinpath(filename).read_bytes()
        )


def test_json_has_no_nan_and_csv_has_stable_headers(tmp_path):
    report = synthetic_report()
    MODULE.write_report(tmp_path, report)

    parsed = json.loads(
        (tmp_path / "report.json").read_text()
    )
    assert parsed["schema_version"] == (
        MODULE.REPORT_SCHEMA_VERSION
    )

    with (tmp_path / "summary.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames is not None
    assert reader.fieldnames[0] == "stream"
    assert [row["stream"] for row in rows] == [
        "raw_target",
        "tim_target_memory",
    ]


def test_missing_status_is_explicitly_unavailable():
    report = MODULE.build_report(
        bag_path=Path("bag"),
        annotation_path=Path("annotations.csv"),
        annotations=[],
        raw_slices=[],
        tim_slices=[],
        status_samples=[],
        raw_duration_row=duration_row("raw_target"),
        tim_duration_row=duration_row(
            "tim_target_memory"
        ),
        timebase="bag",
        step_s=0.1,
        max_output_age_s=0.9,
        stable_duration_s=0.25,
        time_origin_ns=0,
        raw_topic="/target",
        tim_topic="/target_memory_mars",
        status_topic="/target_memory_mars/status",
    )

    assert (
        report["status_recovery_metrics"][
            "recovery_attempts_available"
        ]
        is False
    )
    assert report["state_occupancy"]["available"] is False
    assert (
        report["memory_event_metrics"][
            "hard_negative_events_available"
        ]
        is False
    )


def test_cli_defaults():
    args = MODULE.parse_args(
        [
            "bag",
            "--annotations",
            "annotations.csv",
        ]
    )

    assert args.timebase == "header"
    assert args.step_s == pytest.approx(0.05)
    assert args.max_output_age_s == pytest.approx(
        SHARED.DEFAULT_MAX_OUTPUT_AGE_S
    )
    assert (
        args.stable_recovery_duration_s
        == pytest.approx(
            SHARED.DEFAULT_STABLE_RECOVERY_S
        )
    )
    assert args.raw_topic == SHARED.TARGET_TOPIC_RAW
    assert args.tim_topic == SHARED.TARGET_TOPIC_TIM
    assert args.status_topic == MODULE.DEFAULT_STATUS_TOPIC
