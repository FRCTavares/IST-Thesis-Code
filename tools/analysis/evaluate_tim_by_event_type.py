#!/usr/bin/env python3
"""Evaluate raw/TIM correctness grouped by annotation event type.

This paper-facing helper deliberately reuses the authoritative selected-target
evaluator contract. Both output streams therefore share one image-header time
origin, one track-ID interpretation, and one interval sampling grid.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evaluate_tim_target_correctness import (  # noqa: E402
    AnnotationInterval,
    DEFAULT_MAX_OUTPUT_AGE_S,
    TARGET_TOPIC_RAW,
    TARGET_TOPIC_TIM,
    TargetSample,
    evaluate_stream as evaluate_authoritative_stream,
    load_annotations,
    make_time_grid,
    read_target_samples_from_bag,
    sample_at_time,
)


def evaluate_by_event_type(
    samples: list[TargetSample],
    intervals: Iterable[AnnotationInterval],
    step_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> dict[str, dict[str, float]]:
    """Apply the authoritative evaluator contract per event category."""
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for interval in intervals:
        event_type = interval.event_type.strip() or "unlabeled"
        label = interval.target_label.upper()
        grid = make_time_grid(interval, step_s)

        for index, time_s in enumerate(grid):
            if index < len(grid) - 1:
                duration_s = step_s
            else:
                duration_s = interval.end_s - time_s
                if duration_s <= 0.0:
                    duration_s = min(
                        step_s,
                        interval.duration_s,
                    )

            sample, freshness = sample_at_time(
                samples,
                time_s,
                max_output_age_s,
            )
            output_id = (
                sample.track_id
                if sample is not None and freshness.fresh
                else 0
            )
            stats = grouped[event_type]
            stats["total_s"] += duration_s
            if freshness.status == "stale_source":
                stats["stale_output_s"] += duration_s

            if label == "NO_TARGET_SELECTED":
                stats["no_target_selected_s"] += duration_s
                continue

            if (
                not interval.target_visible
                or label == "TARGET_NOT_VISIBLE"
            ):
                stats["target_not_visible_s"] += duration_s

                if output_id != 0:
                    stats[
                        "target_absent_but_output_s"
                    ] += duration_s

                continue

            stats["visible_s"] += duration_s

            if output_id == interval.correct_target_track_id:
                stats["correct_s"] += duration_s
            elif output_id == 0:
                stats["lost_s"] += duration_s
            else:
                stats["wrong_s"] += duration_s

    return {
        event_type: dict(values)
        for event_type, values in grouped.items()
    }


def rows_for_stream(
    stream: str,
    grouped: dict[str, dict[str, float]],
) -> list[dict[str, object]]:
    """Convert grouped duration statistics into stable CSV rows."""
    rows: list[dict[str, object]] = []

    for event_type in sorted(grouped):
        values = grouped[event_type]
        visible_s = values.get("visible_s", 0.0)
        correct_s = values.get("correct_s", 0.0)
        wrong_s = values.get("wrong_s", 0.0)
        lost_s = values.get("lost_s", 0.0)

        if visible_s > 0.0:
            correct_ratio = correct_s / visible_s
            wrong_ratio = wrong_s / visible_s
            lost_ratio = lost_s / visible_s
        else:
            correct_ratio = math.nan
            wrong_ratio = math.nan
            lost_ratio = math.nan

        rows.append(
            {
                "stream": stream,
                "event_type": event_type,
                "total_s": f"{values.get('total_s', 0.0):.3f}",
                "visible_s": f"{visible_s:.3f}",
                "correct_s": f"{correct_s:.3f}",
                "wrong_s": f"{wrong_s:.3f}",
                "lost_s": f"{lost_s:.3f}",
                "stale_output_s": (
                    f"{values.get('stale_output_s', 0.0):.3f}"
                ),
                "target_absent_but_output_s": (
                    f"{values.get(
                        'target_absent_but_output_s',
                        0.0,
                    ):.3f}"
                ),
                "target_not_visible_s": (
                    f"{values.get(
                        'target_not_visible_s',
                        0.0,
                    ):.3f}"
                ),
                "no_target_selected_s": (
                    f"{values.get(
                        'no_target_selected_s',
                        0.0,
                    ):.3f}"
                ),
                "correct_ratio": (
                    ""
                    if math.isnan(correct_ratio)
                    else f"{correct_ratio:.3f}"
                ),
                "wrong_ratio": (
                    ""
                    if math.isnan(wrong_ratio)
                    else f"{wrong_ratio:.3f}"
                ),
                "lost_ratio": (
                    ""
                    if math.isnan(lost_ratio)
                    else f"{lost_ratio:.3f}"
                ),
            }
        )

    return rows


def evaluate_bag(
    bag: Path,
    annotations_path: Path,
    step_s: float,
    timebase: str,
    raw_topic: str,
    tim_topic: str,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> list[dict[str, object]]:
    """Load both streams with one common origin and evaluate them."""
    intervals = load_annotations(annotations_path)
    samples = read_target_samples_from_bag(
        bag,
        topics=[raw_topic, tim_topic],
        timebase=timebase,
    )

    raw_grouped = evaluate_by_event_type(
        samples.get(raw_topic, []),
        intervals,
        step_s,
        max_output_age_s,
    )
    tim_grouped = evaluate_by_event_type(
        samples.get(tim_topic, []),
        intervals,
        step_s,
        max_output_age_s,
    )

    rows = (
        rows_for_stream("raw_target", raw_grouped)
        + rows_for_stream("tim_target_memory", tim_grouped)
    )
    for row in rows:
        row["max_output_age_s"] = f"{max_output_age_s:.3f}"
    return rows


def write_rows(
    output_path: Path,
    rows: list[dict[str, object]],
) -> None:
    """Write one deterministic event-level CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "stream",
        "event_type",
        "total_s",
        "visible_s",
        "correct_s",
        "wrong_s",
        "lost_s",
        "stale_output_s",
        "target_absent_but_output_s",
        "target_not_visible_s",
        "no_target_selected_s",
        "correct_ratio",
        "wrong_ratio",
        "lost_ratio",
        "max_output_age_s",
    ]

    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Parse the event-level evaluator command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument(
        "--annotations",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.05,
    )
    parser.add_argument(
        "--timebase",
        choices=["bag", "header"],
        default="header",
    )
    parser.add_argument(
        "--max-output-age-s",
        type=float,
        default=DEFAULT_MAX_OUTPUT_AGE_S,
    )
    parser.add_argument(
        "--raw-topic",
        default=TARGET_TOPIC_RAW,
    )
    parser.add_argument(
        "--tim-topic",
        default=TARGET_TOPIC_TIM,
    )
    return parser.parse_args()


def main() -> int:
    """Run event-level evaluation using the authoritative contract."""
    args = parse_args()

    rows = evaluate_bag(
        bag=args.bag,
        annotations_path=args.annotations,
        step_s=args.dt,
        timebase=args.timebase,
        raw_topic=args.raw_topic,
        tim_topic=args.tim_topic,
        max_output_age_s=args.max_output_age_s,
    )
    write_rows(args.out, rows)

    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
