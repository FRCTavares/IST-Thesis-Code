#!/usr/bin/env python3
"""Generate deterministic TIM-MARS event and recovery reports."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Optional

from tim_evaluation import (
    DEFAULT_MAX_OUTPUT_AGE_S,
    DEFAULT_STABLE_RECOVERY_S,
    TARGET_TOPIC_RAW,
    TARGET_TOPIC_TIM,
    AnnotationInterval,
    ClassifiedSlice,
    StatusSample,
    build_absence_recovery_episodes,
    classify_interval_slices,
    compute_state_occupancy,
    contiguous_episodes,
    evaluate_stream,
    fmt_float,
    load_annotations,
    read_evaluation_samples_from_bag,
    stats_to_row,
    status_schema_availability,
    summarise_episode_metrics,
    summarise_memory_event_metrics,
    summarise_status_recovery_metrics,
)

REPORT_SCHEMA_VERSION = "tim-event-recovery-v1"
DEFAULT_STATUS_TOPIC = "/target_memory_mars/status"


def optional_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def csv_optional_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return fmt_float(float(value))


def availability_text(available: bool) -> str:
    return "available" if available else "unavailable"


def sequence_end_s(
    annotations: Iterable[AnnotationInterval],
) -> float:
    materialised = list(annotations)
    if not materialised:
        return 0.0
    return max(interval.end_s for interval in materialised)


def aggregate_event_rows(
    stream: str,
    slices: Iterable[ClassifiedSlice],
) -> list[dict[str, object]]:
    totals: dict[str, dict[str, float]] = {}

    for item in slices:
        event = item.event_type
        row = totals.setdefault(
            event,
            {
                "total_s": 0.0,
                "correct_s": 0.0,
                "wrong_s": 0.0,
                "lost_s": 0.0,
                "target_absent_output_s": 0.0,
                "target_absent_clear_s": 0.0,
                "no_target_selected_s": 0.0,
                "stale_output_s": 0.0,
            },
        )

        row["total_s"] += item.duration_s
        key = f"{item.classification}_s"
        if key in row:
            row[key] += item.duration_s
        if item.freshness_status == "stale":
            row["stale_output_s"] += item.duration_s

    rows: list[dict[str, object]] = []

    for event_type in sorted(totals):
        values = totals[event_type]
        rows.append(
            {
                "stream": stream,
                "event_type": event_type,
                **{
                    key: float(value)
                    for key, value in values.items()
                },
            }
        )

    return rows


def burst_rows(
    stream: str,
    slices: Iterable[ClassifiedSlice],
) -> list[dict[str, object]]:
    materialised = list(slices)
    rows: list[dict[str, object]] = []

    for classification, burst_type in (
        ("wrong", "wrong_target"),
        ("target_absent_output", "target_absent_output"),
    ):
        episodes = contiguous_episodes(
            materialised,
            classification=classification,
        )

        for index, episode in enumerate(episodes, start=1):
            rows.append(
                {
                    "stream": stream,
                    "burst_type": burst_type,
                    "burst_index": index,
                    "event_type": episode.event_type,
                    "start_s": episode.start_s,
                    "end_s": episode.end_s,
                    "duration_s": episode.duration_s,
                    "slice_count": episode.slice_count,
                    "output_track_ids": list(
                        episode.output_track_ids
                    ),
                }
            )

    return rows


def recovery_rows(
    stream: str,
    annotations: list[AnnotationInterval],
    slices: Iterable[ClassifiedSlice],
    stable_duration_s: float,
) -> list[dict[str, object]]:
    episodes = build_absence_recovery_episodes(
        annotations,
        slices,
        stable_duration_s=stable_duration_s,
    )

    rows: list[dict[str, object]] = []

    for index, episode in enumerate(episodes, start=1):
        row = asdict(episode)
        row["stream"] = stream
        row["recovery_index"] = index
        rows.append(row)

    return rows


def state_rows(
    status_samples: Iterable[StatusSample],
    end_s: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    occupancy = compute_state_occupancy(
        status_samples,
        end_s=end_s,
    )

    rows = [
        {
            "stream": "tim_target_memory",
            "state": state,
            "duration_s": duration,
            "ratio": (
                duration / occupancy.total_duration_s
                if occupancy.total_duration_s > 0.0
                else None
            ),
            "availability": availability_text(
                occupancy.available
            ),
        }
        for state, duration in sorted(
            occupancy.duration_by_state_s.items()
        )
    ]

    return rows, asdict(occupancy)


def recovery_attempt_rows(
    metrics: Any,
) -> list[dict[str, object]]:
    if not metrics.recovery_attempts_available:
        return []

    return [
        {
            "stream": "tim_target_memory",
            "attempt_index": index,
            **asdict(attempt),
        }
        for index, attempt in enumerate(
            metrics.recovery_attempts,
            start=1,
        )
    ]


def memory_rows(metrics: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    if metrics.hard_negative_events_available:
        for action, count in sorted(
            metrics.hard_negative_action_counts.items()
        ):
            rows.append(
                {
                    "stream": "tim_target_memory",
                    "memory_family": "hard_negative",
                    "event": action,
                    "count": count,
                    "availability": "available",
                }
            )

    if metrics.positive_memory_events_available:
        rows.extend(
            [
                {
                    "stream": "tim_target_memory",
                    "memory_family": "positive_memory",
                    "event": "update",
                    "count": metrics.positive_memory_update_count,
                    "availability": "available",
                },
                {
                    "stream": "tim_target_memory",
                    "memory_family": "positive_memory",
                    "event": "bootstrap",
                    "count": metrics.positive_memory_bootstrap_count,
                    "availability": "available",
                },
            ]
        )

    return rows


def build_report(
    *,
    bag_path: Path,
    annotation_path: Path,
    annotations: list[AnnotationInterval],
    raw_slices: list[ClassifiedSlice],
    tim_slices: list[ClassifiedSlice],
    status_samples: list[StatusSample],
    raw_duration_row: dict[str, str],
    tim_duration_row: dict[str, str],
    timebase: str,
    step_s: float,
    max_output_age_s: float,
    stable_duration_s: float,
    time_origin_ns: int,
    raw_topic: str,
    tim_topic: str,
    status_topic: str,
) -> dict[str, object]:
    end_s = sequence_end_s(annotations)

    raw_episode_metrics = summarise_episode_metrics(raw_slices)
    tim_episode_metrics = summarise_episode_metrics(tim_slices)

    raw_recovery_rows = recovery_rows(
        "raw_target",
        annotations,
        raw_slices,
        stable_duration_s,
    )
    tim_recovery_rows = recovery_rows(
        "tim_target_memory",
        annotations,
        tim_slices,
        stable_duration_s,
    )

    status_recovery = summarise_status_recovery_metrics(
        tim_slices,
        status_samples,
        end_s=end_s,
    )
    memory_metrics = summarise_memory_event_metrics(
        tim_slices,
        status_samples,
    )
    states, occupancy = state_rows(
        status_samples,
        end_s=end_s,
    )
    schema_availability = status_schema_availability(
        status_samples
    )

    event_rows = (
        aggregate_event_rows("raw_target", raw_slices)
        + aggregate_event_rows(
            "tim_target_memory",
            tim_slices,
        )
    )
    bursts = (
        burst_rows("raw_target", raw_slices)
        + burst_rows("tim_target_memory", tim_slices)
    )
    recoveries = raw_recovery_rows + tim_recovery_rows
    attempts = recovery_attempt_rows(status_recovery)
    memories = memory_rows(memory_metrics)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "provenance": {
            "bag_path": str(bag_path),
            "annotation_path": str(annotation_path),
            "timebase": timebase,
            "time_origin_ns": int(time_origin_ns),
            "step_s": float(step_s),
            "max_output_age_s": float(max_output_age_s),
            "stable_recovery_duration_s": float(
                stable_duration_s
            ),
            "raw_topic": raw_topic,
            "tim_topic": tim_topic,
            "status_topic": status_topic,
        },
        "status_schema_availability": dict(
            sorted(schema_availability.items())
        ),
        "duration_metrics": {
            "raw_target": raw_duration_row,
            "tim_target_memory": tim_duration_row,
        },
        "episode_metrics": {
            "raw_target": asdict(raw_episode_metrics),
            "tim_target_memory": asdict(
                tim_episode_metrics
            ),
        },
        "status_recovery_metrics": asdict(
            status_recovery
        ),
        "state_occupancy": occupancy,
        "memory_event_metrics": asdict(memory_metrics),
        "event_rows": event_rows,
        "burst_rows": bursts,
        "recovery_rows": recoveries,
        "state_rows": states,
        "recovery_attempt_rows": attempts,
        "memory_rows": memories,
    }


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()

        for raw_row in rows:
            row = dict(raw_row)

            for key, value in list(row.items()):
                if isinstance(value, list):
                    row[key] = ";".join(
                        str(item) for item in value
                    )
                elif isinstance(value, tuple):
                    row[key] = ";".join(
                        str(item) for item in value
                    )
                elif value is None:
                    row[key] = ""
                elif isinstance(value, float):
                    row[key] = fmt_float(value)

            writer.writerow(row)


def summary_rows(
    report: dict[str, object],
) -> list[dict[str, object]]:
    duration_metrics = report["duration_metrics"]
    episode_metrics = report["episode_metrics"]
    status_recovery = report["status_recovery_metrics"]
    memory_metrics = report["memory_event_metrics"]
    occupancy = report["state_occupancy"]

    rows: list[dict[str, object]] = []

    for stream in ("raw_target", "tim_target_memory"):
        duration = duration_metrics[stream]
        episodes = episode_metrics[stream]

        row: dict[str, object] = {
            "stream": stream,
            **duration,
            **episodes,
        }

        if stream == "tim_target_memory":
            row.update(
                {
                    "recovery_attempts_availability": (
                        availability_text(
                            status_recovery[
                                "recovery_attempts_available"
                            ]
                        )
                    ),
                    "recovery_attempt_count": (
                        status_recovery[
                            "recovery_attempt_count"
                        ]
                    ),
                    "correct_candidate_suppressed_availability": (
                        availability_text(
                            status_recovery[
                                "correct_candidate_suppressed_available"
                            ]
                        )
                    ),
                    "correct_candidate_suppressed_duration_s": (
                        status_recovery[
                            "correct_candidate_suppressed_duration_s"
                        ]
                    ),
                    "state_occupancy_availability": (
                        availability_text(
                            occupancy["available"]
                        )
                    ),
                    "memory_contamination_count": (
                        memory_metrics[
                            "total_memory_contamination_count"
                        ]
                    ),
                }
            )
        else:
            row.update(
                {
                    "recovery_attempts_availability": "unavailable",
                    "recovery_attempt_count": "",
                    "correct_candidate_suppressed_availability": "unavailable",
                    "correct_candidate_suppressed_duration_s": "",
                    "state_occupancy_availability": "unavailable",
                    "memory_contamination_count": "",
                }
            )

        rows.append(row)

    return rows


def write_markdown(
    path: Path,
    report: dict[str, object],
) -> None:
    provenance = report["provenance"]
    duration = report["duration_metrics"]
    episodes = report["episode_metrics"]
    status_recovery = report["status_recovery_metrics"]
    memory = report["memory_event_metrics"]
    occupancy = report["state_occupancy"]
    recoveries = report["recovery_rows"]

    raw_recoveries = [
        row
        for row in recoveries
        if row["stream"] == "raw_target"
    ]
    tim_recoveries = [
        row
        for row in recoveries
        if row["stream"] == "tim_target_memory"
    ]

    def result_count(
        rows: list[dict[str, object]],
        result: str,
    ) -> int:
        return sum(
            row["result"] == result
            for row in rows
        )

    lines = [
        "# TIM-MARS Event and Recovery Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Bag: `{provenance['bag_path']}`",
        f"- Annotations: `{provenance['annotation_path']}`",
        f"- Timebase: `{provenance['timebase']}`",
        (
            "- Stable recovery persistence: "
            f"`{provenance['stable_recovery_duration_s']} s`"
        ),
        "",
        "## Selected-target summary",
        "",
        "| Metric | Raw | TIM-MARS |",
        "|---|---:|---:|",
        (
            "| Correct duration [s] | "
            f"{duration['raw_target']['correct_target_duration_s']} | "
            f"{duration['tim_target_memory']['correct_target_duration_s']} |"
        ),
        (
            "| Wrong duration [s] | "
            f"{duration['raw_target']['wrong_target_duration_s']} | "
            f"{duration['tim_target_memory']['wrong_target_duration_s']} |"
        ),
        (
            "| Lost duration [s] | "
            f"{duration['raw_target']['lost_target_duration_s']} | "
            f"{duration['tim_target_memory']['lost_target_duration_s']} |"
        ),
        (
            "| Wrong-target bursts | "
            f"{episodes['raw_target']['wrong_target_burst_count']} | "
            f"{episodes['tim_target_memory']['wrong_target_burst_count']} |"
        ),
        (
            "| Wrong handovers | "
            f"{episodes['raw_target']['wrong_handover_count']} | "
            f"{episodes['tim_target_memory']['wrong_handover_count']} |"
        ),
        (
            "| Longest wrong burst [s] | "
            f"{episodes['raw_target']['longest_wrong_target_burst_s']:.6f} | "
            f"{episodes['tim_target_memory']['longest_wrong_target_burst_s']:.6f} |"
        ),
        "",
        "## Physical-absence recovery",
        "",
        "| Result | Raw | TIM-MARS |",
        "|---|---:|---:|",
        (
            "| Success | "
            f"{result_count(raw_recoveries, 'success')} | "
            f"{result_count(tim_recoveries, 'success')} |"
        ),
        (
            "| Failure | "
            f"{result_count(raw_recoveries, 'failure')} | "
            f"{result_count(tim_recoveries, 'failure')} |"
        ),
        (
            "| Censored | "
            f"{result_count(raw_recoveries, 'censored')} | "
            f"{result_count(tim_recoveries, 'censored')} |"
        ),
        "",
        "## TIM status-derived metrics",
        "",
        (
            "- Recovery attempts: "
            f"`{status_recovery['recovery_attempt_count']}` "
            f"({availability_text(status_recovery['recovery_attempts_available'])})"
        ),
        (
            "- Correct-candidate-suppressed duration: "
            f"`{status_recovery['correct_candidate_suppressed_duration_s']:.6f} s` "
            f"({availability_text(status_recovery['correct_candidate_suppressed_available'])})"
        ),
        (
            "- State occupancy: "
            f"`{availability_text(occupancy['available'])}`"
        ),
        (
            "- Total memory contamination events: "
            f"`{memory['total_memory_contamination_count']}`"
        ),
        "",
        "## Scientific interpretation",
        "",
        "- Wrong-target output remains separate from LOST output.",
        "- Target absence is excluded from ordinary recovery latency.",
        "- Sequence-end recovery without stable correctness is censored.",
        "- Missing status fields are reported as unavailable, not inferred.",
        "- This report is evaluation-only and does not alter TIM-MARS policy.",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_report(
    out_dir: Path,
    report: dict[str, object],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summary_rows(report)
    write_csv(
        out_dir / "summary.csv",
        summary,
        [
            "stream",
            "correct_target_duration_s",
            "wrong_target_duration_s",
            "lost_target_duration_s",
            "target_not_visible_duration_s",
            "target_absent_but_output_valid_duration_s",
            "no_target_selected_duration_s",
            "visible_target_duration_s",
            "stale_output_duration_s",
            "correct_target_ratio",
            "wrong_target_ratio",
            "lost_target_ratio",
            "wrong_target_burst_count",
            "wrong_target_total_duration_s",
            "longest_wrong_target_burst_s",
            "wrong_handover_count",
            "target_absent_output_episode_count",
            "target_absent_output_total_duration_s",
            "longest_target_absent_output_episode_s",
            "recovery_attempts_availability",
            "recovery_attempt_count",
            "correct_candidate_suppressed_availability",
            "correct_candidate_suppressed_duration_s",
            "state_occupancy_availability",
            "memory_contamination_count",
        ],
    )

    write_csv(
        out_dir / "events.csv",
        report["event_rows"],
        [
            "stream",
            "event_type",
            "total_s",
            "correct_s",
            "wrong_s",
            "lost_s",
            "target_absent_output_s",
            "target_absent_clear_s",
            "no_target_selected_s",
            "stale_output_s",
        ],
    )

    write_csv(
        out_dir / "bursts.csv",
        report["burst_rows"],
        [
            "stream",
            "burst_type",
            "burst_index",
            "event_type",
            "start_s",
            "end_s",
            "duration_s",
            "slice_count",
            "output_track_ids",
        ],
    )

    write_csv(
        out_dir / "recovery_episodes.csv",
        report["recovery_rows"],
        [
            "stream",
            "recovery_index",
            "bag_name",
            "event_type",
            "disturbance_start_s",
            "disturbance_end_s",
            "first_eligible_recovery_s",
            "first_correct_output_s",
            "first_stable_correct_output_s",
            "first_correct_latency_s",
            "stable_correct_latency_s",
            "result",
            "wrong_target_duration_before_recovery_s",
            "lost_duration_before_recovery_s",
            "target_track_id_before_disturbance",
            "target_track_id_after_recovery",
            "recovery_identity",
            "stable_recovery_required_s",
        ],
    )

    write_csv(
        out_dir / "state_occupancy.csv",
        report["state_rows"],
        [
            "stream",
            "state",
            "duration_s",
            "ratio",
            "availability",
        ],
    )

    write_csv(
        out_dir / "recovery_attempts.csv",
        report["recovery_attempt_rows"],
        [
            "stream",
            "attempt_index",
            "candidate_track_id",
            "start_s",
            "end_s",
            "duration_s",
            "initial_state",
            "final_state",
            "sample_count",
        ],
    )

    write_csv(
        out_dir / "memory_events.csv",
        report["memory_rows"],
        [
            "stream",
            "memory_family",
            "event",
            "count",
            "availability",
        ],
    )

    write_markdown(
        out_dir / "summary.md",
        report,
    )


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name

    if bag_name == "metadata.yaml":
        bag_name = bag_path.parent.name

    safe_name = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        bag_name,
    )

    return (
        Path("reports")
        / "tim_event_recovery"
        / safe_name
    )


def parse_args(
    argv: Optional[list[str]] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic TIM-MARS event and recovery metrics."
        )
    )
    parser.add_argument("bag", type=Path)
    parser.add_argument(
        "--annotations",
        required=True,
        type=Path,
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--timebase",
        choices=["bag", "header"],
        default="header",
    )
    parser.add_argument(
        "--step-s",
        type=float,
        default=0.05,
    )
    parser.add_argument(
        "--max-output-age-s",
        type=float,
        default=DEFAULT_MAX_OUTPUT_AGE_S,
    )
    parser.add_argument(
        "--stable-recovery-duration-s",
        type=float,
        default=DEFAULT_STABLE_RECOVERY_S,
    )
    parser.add_argument(
        "--raw-topic",
        default=TARGET_TOPIC_RAW,
    )
    parser.add_argument(
        "--tim-topic",
        default=TARGET_TOPIC_TIM,
    )
    parser.add_argument(
        "--status-topic",
        default=DEFAULT_STATUS_TOPIC,
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.step_s <= 0.0 or not math.isfinite(args.step_s):
        raise ValueError(
            "--step-s must be finite and greater than zero"
        )

    if (
        args.stable_recovery_duration_s <= 0.0
        or not math.isfinite(
            args.stable_recovery_duration_s
        )
    ):
        raise ValueError(
            "--stable-recovery-duration-s must be finite "
            "and greater than zero"
        )

    annotations = load_annotations(args.annotations)

    bag_samples = read_evaluation_samples_from_bag(
        bag_path=args.bag,
        target_topics=[
            args.raw_topic,
            args.tim_topic,
        ],
        status_topics=[args.status_topic],
        timebase=args.timebase,
    )

    raw_samples = bag_samples.target_samples.get(
        args.raw_topic,
        [],
    )
    tim_samples = bag_samples.target_samples.get(
        args.tim_topic,
        [],
    )
    statuses = bag_samples.status_samples.get(
        args.status_topic,
        [],
    )

    raw_slices = classify_interval_slices(
        annotations,
        raw_samples,
        step_s=args.step_s,
        max_output_age_s=args.max_output_age_s,
    )
    tim_slices = classify_interval_slices(
        annotations,
        tim_samples,
        step_s=args.step_s,
        max_output_age_s=args.max_output_age_s,
    )

    raw_duration = stats_to_row(
        "raw_target",
        evaluate_stream(
            annotations,
            raw_samples,
            step_s=args.step_s,
            max_output_age_s=args.max_output_age_s,
        ),
    )
    tim_duration = stats_to_row(
        "tim_target_memory",
        evaluate_stream(
            annotations,
            tim_samples,
            step_s=args.step_s,
            max_output_age_s=args.max_output_age_s,
        ),
    )

    report = build_report(
        bag_path=args.bag,
        annotation_path=args.annotations,
        annotations=annotations,
        raw_slices=raw_slices,
        tim_slices=tim_slices,
        status_samples=statuses,
        raw_duration_row=raw_duration,
        tim_duration_row=tim_duration,
        timebase=args.timebase,
        step_s=args.step_s,
        max_output_age_s=args.max_output_age_s,
        stable_duration_s=(
            args.stable_recovery_duration_s
        ),
        time_origin_ns=bag_samples.time_origin_ns,
        raw_topic=args.raw_topic,
        tim_topic=args.tim_topic,
        status_topic=args.status_topic,
    )

    out_dir = (
        args.out_dir
        if args.out_dir is not None
        else default_report_dir(args.bag)
    )
    write_report(out_dir, report)

    for filename in (
        "report.json",
        "summary.csv",
        "events.csv",
        "bursts.csv",
        "recovery_episodes.csv",
        "state_occupancy.csv",
        "recovery_attempts.csv",
        "memory_events.csv",
        "summary.md",
    ):
        print(f"Wrote: {out_dir / filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
