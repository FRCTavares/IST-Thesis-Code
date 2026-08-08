#!/usr/bin/env python3
"""Validate a candidate Issue #58 physical-target annotation CSV before it
can flip a manifest cell from ``pending_annotation`` to ``available``.

Reuses tools/bag_annotation_ui/tim_ui_annotations.py's schema/normalization
loader rather than reimplementing CSV parsing. Adds Issue #58-specific
checks on top:

- source-bag association: fails closed if the annotation's ``bag_name``
  field does not reference the canonical source bag frozen for its
  sequence. This is exactly the check that would have caught the stale
  Seq03/Seq04 DeepSORT annotations (docs/data/annotations/
  june_hard_sequences/seq03_deepsort.csv, seq04_deepsort.csv -- both
  reference a different, ~2-minutes-earlier "image_raw"-only diagnostic
  capture, not the canonical full_pipeline bag) before they are ever
  trusted as evidence;
- tracker namespace: the file must be for exactly one tracker;
- interval continuity: intervals must be contiguous and non-overlapping;
- duration coverage: the annotated span must cover the paired replay bag's
  actual duration within tolerance, not stop short or run over;
- target-visible/absent semantics: every row's target_visible must be
  consistent with its event_type (mirrors the UI's own normalization
  rule, checked here rather than re-trusted).

Never auto-corrects an annotation. Reports problems; does not fix them.

Usage::

    validate_p058_annotation.py <csv_path> --sequence dev_june_seq04 \\
        --tracker deepsort --replay-bag <path>
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "bag_annotation_ui"))

from tim_ui_annotations import load_annotation_rows  # noqa: E402

# Substrings that MUST appear in a valid annotation's bag_name field for
# each sequence. June sequences use the exact canonical full_pipeline
# capture timestamp (positive allowlist, not a stale blocklist -- a new,
# still-wrong bag would also fail this, not just the two already known).
# May's annotations use a generic tracker-name label by established
# convention (no timestamp collision risk: only one source bag exists).
CANONICAL_SOURCE_PATTERNS: dict[str, list[str]] = {
    "dev_may_hard_reentry": ["sort", "deepsort", "2026-05-14"],
    "dev_june_seq01": ["2026-06-19__12-45-45"],
    "dev_june_seq03": ["2026-06-19__12-57-48"],
    "dev_june_seq04": ["2026-06-19__13-01-36"],
}

KNOWN_STALE_SOURCE_PATTERNS: dict[str, list[str]] = {
    "dev_june_seq03": ["2026-06-19__12-55-58"],
    "dev_june_seq04": ["2026-06-19__12-59-53"],
}


class AnnotationValidationError(ValueError):
    """A candidate annotation fails one or more Issue #58 checks."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def check_source_association(rows: list[dict[str, str]], sequence_id: str) -> list[str]:
    problems = []
    patterns = CANONICAL_SOURCE_PATTERNS.get(sequence_id)
    if patterns is None:
        problems.append(f"no known canonical source pattern registered for {sequence_id}")
        return problems

    stale_patterns = KNOWN_STALE_SOURCE_PATTERNS.get(sequence_id, [])
    for i, row in enumerate(rows):
        bag_name = row.get("bag_name", "")
        for stale in stale_patterns:
            if stale in bag_name:
                problems.append(
                    f"row {i}: bag_name references a KNOWN-STALE source bag "
                    f"({stale!r}); this is the wrong recording for {sequence_id}"
                )
        if not any(p in bag_name for p in patterns):
            problems.append(
                f"row {i}: bag_name {bag_name!r} does not reference the "
                f"canonical source for {sequence_id} (expected one of {patterns})"
            )
    return problems


def check_tracker_namespace(rows: list[dict[str, str]], tracker: str) -> list[str]:
    problems = []
    for i, row in enumerate(rows):
        bag_name = row.get("bag_name", "").lower()
        if tracker not in bag_name:
            problems.append(
                f"row {i}: bag_name does not mention tracker {tracker!r}: {row.get('bag_name')!r}"
            )
    return problems


def check_interval_continuity(rows: list[dict[str, str]]) -> list[str]:
    problems = []
    ordered = sorted(rows, key=lambda r: float(r["start_s"]))
    for i in range(1, len(ordered)):
        prev_end = float(ordered[i - 1]["end_s"])
        cur_start = float(ordered[i]["start_s"])
        if abs(cur_start - prev_end) > 1e-6:
            problems.append(
                f"gap or overlap between interval ending {prev_end}s and "
                f"interval starting {cur_start}s"
            )
    for i, row in enumerate(ordered):
        if float(row["end_s"]) <= float(row["start_s"]):
            problems.append(f"row {i}: end_s must be greater than start_s")
    return problems


def check_duration_coverage(
    rows: list[dict[str, str]], expected_duration_s: float, tolerance_s: float = 0.5
) -> list[str]:
    problems = []
    if not rows:
        return ["no rows"]
    ordered = sorted(rows, key=lambda r: float(r["start_s"]))
    first_start = float(ordered[0]["start_s"])
    last_end = float(ordered[-1]["end_s"])
    if abs(first_start - 0.0) > tolerance_s:
        problems.append(f"annotation does not start at t=0 (starts at {first_start}s)")
    if abs(last_end - expected_duration_s) > tolerance_s:
        problems.append(
            f"annotation covers {last_end}s, replay bag duration is "
            f"{expected_duration_s}s (tolerance {tolerance_s}s)"
        )
    return problems


def check_visibility_semantics(rows: list[dict[str, str]]) -> list[str]:
    problems = []
    for i, row in enumerate(rows):
        visible = row["target_visible"].strip().lower() == "true"
        event_type = row["event_type"]
        has_track_id = bool(row.get("correct_target_track_id", "").strip())
        if visible and not has_track_id:
            problems.append(f"row {i}: target_visible=true but no correct_target_track_id")
        if not visible and has_track_id:
            problems.append(f"row {i}: target_visible=false but correct_target_track_id is set")
        if not visible and event_type != "target_absent":
            problems.append(
                f"row {i}: target_visible=false but event_type={event_type!r}, "
                "expected target_absent"
            )
    return problems


def replay_bag_duration_s(replay_bag: Path) -> float:
    """Compute the /tracks stream's wall-clock duration from a replay bag,
    without importing rclpy at module scope (keeps --help usable without
    ROS sourced)."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(replay_bag), storage_id="mcap"),
        rosbag2_py.ConverterOptions("", ""),
    )
    topics = {t.name: t.type for t in reader.get_all_topics_and_types()}
    first_ts = None
    last_ts = None
    while reader.has_next():
        topic, data, t = reader.read_next()
        if topic == "/tracks":
            if first_ts is None:
                first_ts = t
            last_ts = t
    if first_ts is None or last_ts is None:
        raise ValueError(f"no /tracks messages found in {replay_bag}")
    return (last_ts - first_ts) / 1e9


def validate(
    csv_path: Path,
    sequence_id: str,
    tracker: str,
    replay_bag: Path | None = None,
) -> list[str]:
    """Return a list of problems (empty means the annotation passes)."""
    csv_path = Path(csv_path)
    if csv_path.is_absolute():
        csv_path = csv_path.relative_to(REPO_ROOT)
    _, rows = load_annotation_rows(str(csv_path), REPO_ROOT)

    problems: list[str] = []
    problems += check_source_association(rows, sequence_id)
    problems += check_tracker_namespace(rows, tracker)
    problems += check_interval_continuity(rows)
    problems += check_visibility_semantics(rows)

    if replay_bag is not None:
        duration = replay_bag_duration_s(replay_bag)
        problems += check_duration_coverage(rows, duration)

    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--sequence", required=True, choices=sorted(CANONICAL_SOURCE_PATTERNS))
    parser.add_argument("--tracker", required=True, choices=["sort", "deepsort"])
    parser.add_argument("--replay-bag", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    problems = validate(args.csv_path, args.sequence, args.tracker, args.replay_bag)
    if problems:
        print(f"[FAIL] {len(problems)} problem(s) in {args.csv_path}:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"[ok] {args.csv_path} passes all Issue #58 annotation checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
