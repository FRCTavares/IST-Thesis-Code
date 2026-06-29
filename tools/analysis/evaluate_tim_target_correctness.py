#!/usr/bin/env python3
"""Evaluate selected-target correctness for raw /target vs TIM-MARS /target_memory_mars.

First version:
- interval-based annotation
- track-ID based correctness
- compares raw /target and TIM-MARS /target_memory_mars
- computes correct / wrong / lost durations
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


TARGET_TOPIC_RAW = "/target"
TARGET_TOPIC_TIM = "/target_memory_mars"


@dataclass
class AnnotationInterval:
    bag_name: str
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int
    distractor_track_ids: str
    event_type: str
    notes: str

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass
class TargetSample:
    t_s: float
    track_id: int


@dataclass
class DurationStats:
    correct_target_duration_s: float = 0.0
    wrong_target_duration_s: float = 0.0
    lost_target_duration_s: float = 0.0
    target_not_visible_duration_s: float = 0.0
    target_absent_but_output_valid_duration_s: float = 0.0
    no_target_selected_duration_s: float = 0.0
    visible_target_duration_s: float = 0.0

    @property
    def correct_target_ratio(self) -> float:
        return safe_div(self.correct_target_duration_s, self.visible_target_duration_s)

    @property
    def wrong_target_ratio(self) -> float:
        return safe_div(self.wrong_target_duration_s, self.visible_target_duration_s)

    @property
    def lost_target_ratio(self) -> float:
        return safe_div(self.lost_target_duration_s, self.visible_target_duration_s)


def safe_div(a: float, b: float) -> float:
    if b <= 0.0:
        return float("nan")
    return a / b


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_int_or_zero(value: str) -> int:
    value = str(value).strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def load_annotations(path: Path) -> List[AnnotationInterval]:
    rows: List[AnnotationInterval] = []

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)

        required = {
            "bag_name",
            "start_s",
            "end_s",
            "target_label",
            "target_visible",
            "correct_target_track_id",
            "distractor_track_ids",
            "event_type",
            "notes",
        }

        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Annotation CSV is missing columns: {sorted(missing)}")

        for row in reader:
            rows.append(
                AnnotationInterval(
                    bag_name=row["bag_name"],
                    start_s=float(row["start_s"]),
                    end_s=float(row["end_s"]),
                    target_label=row["target_label"].strip(),
                    target_visible=parse_bool(row["target_visible"]),
                    correct_target_track_id=parse_int_or_zero(row["correct_target_track_id"]),
                    distractor_track_ids=row["distractor_track_ids"].strip(),
                    event_type=row["event_type"].strip(),
                    notes=row["notes"].strip(),
                )
            )

    rows.sort(key=lambda x: x.start_s)
    return rows


def import_rosbag_tools():
    try:
        from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except Exception as exc:
        raise RuntimeError(
            "Could not import ROS 2 bag tools. Source ROS first:\n"
            "  source /opt/ros/jazzy/setup.bash\n"
            "  source \"$THESIS_ROOT/ros2_ws/install/setup.bash\""
        ) from exc

    return SequentialReader, StorageOptions, ConverterOptions, deserialize_message, get_message


def find_track_id_field(msg: object) -> int:
    candidate_names = [
        "target_track_id",
        "track_id",
        "id",
        "target_id",
    ]

    for name in candidate_names:
        if hasattr(msg, name):
            try:
                return int(getattr(msg, name))
            except Exception:
                pass

    for nested_name in ["target", "track"]:
        if hasattr(msg, nested_name):
            nested = getattr(msg, nested_name)
            for name in candidate_names:
                if hasattr(nested, name):
                    try:
                        return int(getattr(nested, name))
                    except Exception:
                        pass

    return 0


def detect_storage_id(bag_path: Path) -> str:
    metadata_path = bag_path / "metadata.yaml"

    if metadata_path.exists():
        text = metadata_path.read_text(errors="ignore")
        if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
            return "mcap"
        if "storage_identifier: sqlite3" in text or "storage_id: sqlite3" in text:
            return "sqlite3"

    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"

    return "sqlite3"


def header_time_ns(msg: object) -> Optional[int]:
    if not hasattr(msg, "header"):
        return None

    header = getattr(msg, "header")
    if not hasattr(header, "stamp"):
        return None

    stamp = getattr(header, "stamp")

    try:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    except Exception:
        return None


def read_target_samples_from_bag(
    bag_path: Path,
    topics: Iterable[str],
    timebase: str,
) -> Dict[str, List[TargetSample]]:
    (
        SequentialReader,
        StorageOptions,
        ConverterOptions,
        deserialize_message,
        get_message,
    ) = import_rosbag_tools()

    reader = SequentialReader()
    storage_options = StorageOptions(uri=str(bag_path), storage_id=detect_storage_id(bag_path))
    converter_options = ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    reader.open(storage_options, converter_options)

    topic_types = {
        topic_metadata.name: topic_metadata.type
        for topic_metadata in reader.get_all_topics_and_types()
    }

    requested = set(topics)
    available = requested & set(topic_types.keys())

    if not available:
        raise RuntimeError(
            f"None of the requested topics were found in bag. "
            f"Requested={sorted(requested)}. "
            f"Available={sorted(topic_types.keys())}"
        )

    msg_types = {
        topic: get_message(topic_types[topic])
        for topic in available
    }

    if timebase not in {"bag", "header"}:
        raise ValueError(f"Unsupported timebase: {timebase}")

    samples: Dict[str, List[TargetSample]] = {topic: [] for topic in requested}
    first_time_ns: Optional[int] = None

    while reader.has_next():
        topic, data, t_ns = reader.read_next()

        if topic not in available:
            continue

        msg = deserialize_message(data, msg_types[topic])

        if timebase == "header":
            msg_time_ns = header_time_ns(msg)
            if msg_time_ns is None:
                continue
        else:
            msg_time_ns = t_ns

        if first_time_ns is None:
            first_time_ns = msg_time_ns

        track_id = find_track_id_field(msg)
        t_s = (msg_time_ns - first_time_ns) * 1e-9

        samples[topic].append(TargetSample(t_s=t_s, track_id=track_id))

    return samples


def sample_id_at_time(samples: List[TargetSample], t_s: float) -> int:
    if not samples:
        return 0

    if t_s < samples[0].t_s:
        return 0

    lo = 0
    hi = len(samples) - 1

    while lo <= hi:
        mid = (lo + hi) // 2
        if samples[mid].t_s <= t_s:
            lo = mid + 1
        else:
            hi = mid - 1

    return samples[max(0, hi)].track_id


def make_time_grid(interval: AnnotationInterval, step_s: float) -> List[float]:
    if interval.duration_s <= 0.0:
        return []

    n = max(1, int(math.ceil(interval.duration_s / step_s)))
    return [
        min(interval.end_s, interval.start_s + i * step_s)
        for i in range(n)
    ]


def evaluate_stream(
    annotations: List[AnnotationInterval],
    samples: List[TargetSample],
    step_s: float,
) -> DurationStats:
    stats = DurationStats()

    for interval in annotations:
        label = interval.target_label.upper()
        grid = make_time_grid(interval, step_s)

        if not grid:
            continue

        for idx, t_s in enumerate(grid):
            if idx < len(grid) - 1:
                dt = step_s
            else:
                dt = interval.end_s - t_s
                if dt <= 0:
                    dt = min(step_s, interval.duration_s)

            output_id = sample_id_at_time(samples, t_s)

            if label == "NO_TARGET_SELECTED":
                stats.no_target_selected_duration_s += dt
                continue

            if (not interval.target_visible) or label == "TARGET_NOT_VISIBLE":
                stats.target_not_visible_duration_s += dt
                if output_id != 0:
                    stats.target_absent_but_output_valid_duration_s += dt
                continue

            stats.visible_target_duration_s += dt

            if output_id == interval.correct_target_track_id:
                stats.correct_target_duration_s += dt
            elif output_id == 0:
                stats.lost_target_duration_s += dt
            else:
                stats.wrong_target_duration_s += dt

    return stats


def fmt_float(value: float) -> str:
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return f"{value:.3f}"


def stats_to_row(stream_name: str, stats: DurationStats) -> Dict[str, str]:
    return {
        "stream": stream_name,
        "correct_target_duration_s": fmt_float(stats.correct_target_duration_s),
        "wrong_target_duration_s": fmt_float(stats.wrong_target_duration_s),
        "lost_target_duration_s": fmt_float(stats.lost_target_duration_s),
        "target_not_visible_duration_s": fmt_float(stats.target_not_visible_duration_s),
        "target_absent_but_output_valid_duration_s": fmt_float(stats.target_absent_but_output_valid_duration_s),
        "no_target_selected_duration_s": fmt_float(stats.no_target_selected_duration_s),
        "visible_target_duration_s": fmt_float(stats.visible_target_duration_s),
        "correct_target_ratio": fmt_float(stats.correct_target_ratio),
        "wrong_target_ratio": fmt_float(stats.wrong_target_ratio),
        "lost_target_ratio": fmt_float(stats.lost_target_ratio),
    }


def write_summary_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
        ("target absent but output [s]", "target_absent_but_output_valid_duration_s"),
        ("target not visible [s]", "target_not_visible_duration_s"),
        ("visible target duration [s]", "visible_target_duration_s"),
        ("correct ratio", "correct_target_ratio"),
        ("wrong ratio", "wrong_target_ratio"),
        ("lost ratio", "lost_target_ratio"),
    ]

    by_stream = {row["stream"]: row for row in rows}
    raw = by_stream.get("raw_target", {})
    tim = by_stream.get("tim_target_memory", {})

    lines = []
    lines.append("# TIM Target Correctness Summary")
    lines.append("")
    lines.append(f"- Bag: `{bag_path}`")
    lines.append(f"- Annotations: `{annotation_path}`")
    lines.append(f"- Timebase: `{timebase}`")
    lines.append("")
    lines.append("## Main comparison")
    lines.append("")
    lines.append("| Metric | Raw /target | TIM-MARS /target_memory_mars |")
    lines.append("|---|---:|---:|")

    for label, key in metrics:
        lines.append(f"| {label} | {raw.get(key, 'nan')} | {tim.get(key, 'nan')} |")

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- Higher correct ratio is good.")
    lines.append("- Higher wrong ratio is bad.")
    lines.append("- Higher lost ratio is safer than wrong target if the system is uncertain, but still reduces following performance.")
    lines.append("- Valid target duration alone must not be used as the main success metric.")
    lines.append("- This evaluator is track-ID based. It is only valid when tracker IDs match the annotation stream.")
    lines.append("- For fresh tracker reruns where IDs may be renumbered, use bbox correctness or visual validation instead.")
    lines.append("")

    path.write_text("\n".join(lines))


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name
    if bag_name == "metadata.yaml" and bag_path.parent:
        bag_name = bag_path.parent.name

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", bag_name)
    return Path("reports") / "tim_target_correctness" / safe_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate selected-target correctness for raw /target and TIM-MARS /target_memory_mars."
    )
    parser.add_argument("bag_path", type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--step-s", type=float, default=0.05)
    parser.add_argument("--raw-topic", default=TARGET_TOPIC_RAW)
    parser.add_argument("--tim-topic", default=TARGET_TOPIC_TIM)
    parser.add_argument(
        "--timebase",
        choices=["bag", "header"],
        default="bag",
        help="Timestamp source for evaluation time. Use header for replay bags whose bag time is stretched.",
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

    raw_stats = evaluate_stream(
        annotations,
        samples=samples.get(args.raw_topic, []),
        step_s=args.step_s,
    )
    tim_stats = evaluate_stream(
        annotations,
        samples=samples.get(args.tim_topic, []),
        step_s=args.step_s,
    )

    rows = [
        stats_to_row("raw_target", raw_stats),
        stats_to_row("tim_target_memory", tim_stats),
    ]

    out_dir = args.out_dir or default_report_dir(args.bag_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_summary_csv(out_dir / "summary.csv", rows)
    write_summary_md(out_dir / "summary.md", args.bag_path, args.annotations, args.timebase, rows)

    print(f"Wrote: {out_dir / 'summary.md'}")
    print(f"Wrote: {out_dir / 'summary.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
