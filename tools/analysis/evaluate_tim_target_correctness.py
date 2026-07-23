#!/usr/bin/env python3
"""Evaluate raw and TIM-MARS selected-target correctness.

All evaluation semantics live in :mod:`tim_evaluation`. This file owns only
the report format and command-line interface while re-exporting the shared
symbols for compatibility with existing analysis scripts.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tim_evaluation import (  # noqa: E402,F401
    DEFAULT_MAX_OUTPUT_AGE_S,
    IMAGE_TOPICS_FOR_T0,
    TARGET_TOPIC_RAW,
    TARGET_TOPIC_TIM,
    AnnotationInterval,
    DurationStats,
    FreshnessResult,
    IntervalSlice,
    TargetSample,
    detect_storage_id,
    evaluate_stream,
    find_track_id_field,
    fmt_float,
    header_time_ns,
    import_rosbag_tools,
    iter_interval_slices,
    load_annotations,
    make_time_grid,
    parse_bool,
    parse_int_or_zero,
    read_target_samples_from_bag,
    safe_div,
    sample_at_time,
    sample_id_at_time,
    sample_output_id,
    stats_to_row,
    target_bbox_validity,
    validate_annotations,
)


def write_summary_csv(
    path: Path,
    rows: List[Dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())

    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(
    path: Path,
    bag_path: Path,
    annotation_path: Path,
    timebase: str,
    rows: List[Dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = [
        ("correct duration [s]", "correct_target_duration_s"),
        ("wrong duration [s]", "wrong_target_duration_s"),
        ("lost duration [s]", "lost_target_duration_s"),
        (
            "target absent but output [s]",
            "target_absent_but_output_valid_duration_s",
        ),
        (
            "target not visible [s]",
            "target_not_visible_duration_s",
        ),
        (
            "visible target duration [s]",
            "visible_target_duration_s",
        ),
        ("stale output duration [s]", "stale_output_duration_s"),
        ("correct ratio", "correct_target_ratio"),
        ("wrong ratio", "wrong_target_ratio"),
        ("lost ratio", "lost_target_ratio"),
    ]

    by_stream = {row["stream"]: row for row in rows}
    raw = by_stream.get("raw_target", {})
    tim = by_stream.get("tim_target_memory", {})
    lines = [
        "# TIM Target Correctness Summary",
        "",
        f"- Bag: `{bag_path}`",
        f"- Annotations: `{annotation_path}`",
        f"- Timebase: `{timebase}`",
        (
            "- Maximum output age: "
            f"`{rows[0].get('max_output_age_s', 'unknown')} s`"
        ),
        "",
        "## Main comparison",
        "",
        "| Metric | Raw /target | TIM-MARS /target_memory_mars |",
        "|---|---:|---:|",
    ]
    for label, key in metrics:
        lines.append(
            f"| {label} | {raw.get(key, 'nan')} | "
            f"{tim.get(key, 'nan')} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Higher correct ratio is good.",
            "- Higher wrong ratio is bad.",
            (
                "- Higher lost ratio is safer than wrong target if the "
                "system is uncertain, but still reduces following performance."
            ),
            (
                "- Valid target duration alone must not be used as the main "
                "success metric."
            ),
            (
                "- This evaluator is track-ID based. It is only valid when "
                "tracker IDs match the annotation stream."
            ),
            (
                "- For fresh tracker reruns where IDs may be renumbered, use "
                "bbox correctness or visual validation instead."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines))


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name
    if bag_name == "metadata.yaml" and bag_path.parent:
        bag_name = bag_path.parent.name
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", bag_name)
    return Path("reports") / "tim_target_correctness" / safe_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate raw and TIM-MARS selected-target correctness."
        )
    )
    parser.add_argument("bag_path", type=Path)
    parser.add_argument(
        "--annotations",
        required=True,
        type=Path,
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--step-s", type=float, default=0.05)
    parser.add_argument(
        "--max-output-age-s",
        type=float,
        default=DEFAULT_MAX_OUTPUT_AGE_S,
        help=(
            "Latest-preceding outputs older than this are classified lost."
        ),
    )
    parser.add_argument("--raw-topic", default=TARGET_TOPIC_RAW)
    parser.add_argument("--tim-topic", default=TARGET_TOPIC_TIM)
    parser.add_argument(
        "--timebase",
        choices=["bag", "header"],
        default="bag",
        help=(
            "Timestamp source. Use header for replay bags whose bag time "
            "is stretched."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    annotations = load_annotations(args.annotations)
    samples = read_target_samples_from_bag(
        args.bag_path,
        topics=[args.raw_topic, args.tim_topic],
        timebase=args.timebase,
    )
    rows = [
        stats_to_row(
            "raw_target",
            evaluate_stream(
                annotations,
                samples=samples.get(args.raw_topic, []),
                step_s=args.step_s,
                max_output_age_s=args.max_output_age_s,
            ),
        ),
        stats_to_row(
            "tim_target_memory",
            evaluate_stream(
                annotations,
                samples=samples.get(args.tim_topic, []),
                step_s=args.step_s,
                max_output_age_s=args.max_output_age_s,
            ),
        ),
    ]
    for row in rows:
        row["max_output_age_s"] = fmt_float(
            args.max_output_age_s
        )

    out_dir = args.out_dir or default_report_dir(args.bag_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_summary_csv(out_dir / "summary.csv", rows)
    write_summary_md(
        out_dir / "summary.md",
        args.bag_path,
        args.annotations,
        args.timebase,
        rows,
    )
    print(f"Wrote: {out_dir / 'summary.md'}")
    print(f"Wrote: {out_dir / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
