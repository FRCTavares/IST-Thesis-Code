#!/usr/bin/env python3
"""Evaluate selected-target bbox correctness on a common /tracks clock.

This evaluator uses the annotated target ID only to find the reference bbox in
/tracks. Raw /target and TIM-MARS /target_memory_mars are sampled as latest
outputs at each /tracks timestamp, so both streams are scored on the same
timeline.

Use this as a spatial complement to track-ID correctness metrics.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


REPO_ROOT = Path(__file__).resolve().parents[2]
BRINGUP_SOURCE = REPO_ROOT / "ros2_ws" / "src" / "thesis_bringup"
if str(BRINGUP_SOURCE) not in sys.path:
    sys.path.insert(0, str(BRINGUP_SOURCE))

from thesis_bringup.freshness import (  # noqa: E402
    DEFAULT_MAX_OUTPUT_AGE_S,
    classify_relative_freshness,
)


@dataclass
class Interval:
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int


@dataclass
class TargetSample:
    t_s: float
    id: int
    box: tuple[float, float, float, float]


@dataclass
class TrackSample:
    t_s: float
    tracks: dict[int, tuple[float, float, float, float]]


@dataclass
class Stats:
    correct_target_duration_s: float = 0.0
    wrong_target_duration_s: float = 0.0
    lost_target_duration_s: float = 0.0
    target_not_visible_duration_s: float = 0.0
    target_absent_but_output_valid_duration_s: float = 0.0
    no_target_selected_duration_s: float = 0.0
    reference_missing_duration_s: float = 0.0
    visible_target_duration_s: float = 0.0
    stale_output_duration_s: float = 0.0

    @property
    def correct_target_ratio(self) -> float:
        return safe_div(self.correct_target_duration_s, self.visible_target_duration_s)

    @property
    def wrong_target_ratio(self) -> float:
        return safe_div(self.wrong_target_duration_s, self.visible_target_duration_s)

    @property
    def lost_target_ratio(self) -> float:
        return safe_div(self.lost_target_duration_s, self.visible_target_duration_s)

    @property
    def reference_missing_ratio(self) -> float:
        return safe_div(self.reference_missing_duration_s, self.visible_target_duration_s)


def safe_div(a: float, b: float) -> float:
    return a / b if b > 0 else 0.0


def parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y"}


def parse_int_or_zero(s: str) -> int:
    s = str(s).strip()
    return int(float(s)) if s else 0


def load_annotations(path: Path) -> list[Interval]:
    out: list[Interval] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            out.append(
                Interval(
                    start_s=float(row["start_s"]),
                    end_s=float(row["end_s"]),
                    target_label=row["target_label"].strip().upper(),
                    target_visible=parse_bool(row["target_visible"]),
                    correct_target_track_id=parse_int_or_zero(row["correct_target_track_id"]),
                )
            )
    return out


def interval_at(intervals: list[Interval], t_s: float) -> Interval | None:
    for interval in intervals:
        if interval.start_s <= t_s < interval.end_s:
            return interval
    return None


def bbox_valid(box: tuple[float, float, float, float] | None) -> bool:
    if box is None:
        return False
    _, _, w, h = box
    return w > 0.0 and h > 0.0


def cxcywh_to_xyxy(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    cx, cy, w, h = box
    return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = cxcywh_to_xyxy(a)
    bx1, by1, bx2, by2 = cxcywh_to_xyxy(b)

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter

    return inter / union if union > 0.0 else 0.0


def centre_distance_ratio(
    output_box: tuple[float, float, float, float],
    reference_box: tuple[float, float, float, float],
) -> float:
    out_cx, out_cy, _, _ = output_box
    ref_cx, ref_cy, _, ref_h = reference_box
    dx = out_cx - ref_cx
    dy = out_cy - ref_cy
    dist = (dx * dx + dy * dy) ** 0.5
    return dist / ref_h if ref_h > 0.0 else float("inf")


def bbox_matches_reference(
    output_box: tuple[float, float, float, float],
    reference_box: tuple[float, float, float, float],
    iou_threshold: float,
    centre_distance_threshold: float,
) -> bool:
    return (
        iou(output_box, reference_box) >= iou_threshold
        or centre_distance_ratio(output_box, reference_box) <= centre_distance_threshold
    )


def msg_box(msg: Any) -> tuple[float, float, float, float]:
    return float(msg.cx), float(msg.cy), float(msg.w), float(msg.h)


def read_bag(
    bag_path: Path,
    tracks_topic: str,
    raw_topic: str,
    tim_topic: str,
) -> tuple[list[TrackSample], list[TargetSample], list[TargetSample]]:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    required = [tracks_topic, raw_topic, tim_topic]
    missing = [topic for topic in required if topic not in topic_types]
    if missing:
        raise RuntimeError(f"Bag is missing required topics: {missing}")

    msg_types = {topic: get_message(topic_types[topic]) for topic in required}

    tracks: list[TrackSample] = []
    raw: list[TargetSample] = []
    tim: list[TargetSample] = []

    first_t: int | None = None

    while reader.has_next():
        topic, data, t = reader.read_next()

        if first_t is None:
            first_t = t

        if topic not in msg_types:
            continue

        t_s = (t - first_t) / 1e9
        msg = deserialize_message(data, msg_types[topic])

        if topic == tracks_topic:
            track_map = {int(tr.id): msg_box(tr) for tr in msg.tracks}
            tracks.append(TrackSample(t_s=t_s, tracks=track_map))
        elif topic == raw_topic:
            sample = TargetSample(t_s=t_s, id=int(msg.id), box=msg_box(msg))
            if raw and t_s < raw[-1].t_s:
                continue
            if raw and t_s == raw[-1].t_s:
                raw[-1] = sample
            else:
                raw.append(sample)
        elif topic == tim_topic:
            sample = TargetSample(t_s=t_s, id=int(msg.id), box=msg_box(msg))
            if tim and t_s < tim[-1].t_s:
                continue
            if tim and t_s == tim[-1].t_s:
                tim[-1] = sample
            else:
                tim.append(sample)

    return tracks, raw, tim


def latest_target_at(samples: list[TargetSample], t_s: float, index_hint: int) -> tuple[TargetSample | None, int]:
    if not samples:
        return None, index_hint

    i = min(max(index_hint, 0), len(samples) - 1)

    while i + 1 < len(samples) and samples[i + 1].t_s <= t_s:
        i += 1

    if samples[i].t_s <= t_s:
        return samples[i], i

    return None, i


def output_valid(sample: TargetSample | None) -> bool:
    return sample is not None and sample.id != 0 and bbox_valid(sample.box)


def score_on_tracks_clock(
    tracks: list[TrackSample],
    outputs: list[TargetSample],
    intervals: list[Interval],
    iou_threshold: float,
    centre_distance_threshold: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> Stats:
    stats = Stats()
    out_i = 0

    if len(tracks) < 2:
        return stats

    for i in range(len(tracks) - 1):
        tr_sample = tracks[i]
        next_tr = tracks[i + 1]
        t_s = tr_sample.t_s
        dt = max(0.0, next_tr.t_s - tr_sample.t_s)

        interval = interval_at(intervals, t_s)
        if interval is None:
            continue

        label = interval.target_label
        if label == "IGNORE":
            continue

        output, out_i = latest_target_at(outputs, t_s, out_i)
        freshness = classify_relative_freshness(
            now_s=t_s,
            source_time_s=None if output is None else output.t_s,
            max_age_s=max_output_age_s,
        )
        if freshness.status == "stale_source":
            stats.stale_output_duration_s += dt
        valid = freshness.fresh and output_valid(output)

        if label == "NO_TARGET_SELECTED":
            stats.no_target_selected_duration_s += dt
            continue

        if label == "TARGET_NOT_VISIBLE" or not interval.target_visible:
            stats.target_not_visible_duration_s += dt
            if valid:
                stats.target_absent_but_output_valid_duration_s += dt
            continue

        if label != "CORRECT_TARGET":
            continue

        stats.visible_target_duration_s += dt

        ref_box = tr_sample.tracks.get(interval.correct_target_track_id)
        if not bbox_valid(ref_box):
            stats.reference_missing_duration_s += dt
            continue

        if not valid or output is None:
            stats.lost_target_duration_s += dt
            continue

        if bbox_matches_reference(
            output.box,
            ref_box,
            iou_threshold=iou_threshold,
            centre_distance_threshold=centre_distance_threshold,
        ):
            stats.correct_target_duration_s += dt
        else:
            stats.wrong_target_duration_s += dt

    return stats


def stats_row(stream: str, stats: Stats) -> dict[str, str]:
    def f(x: float) -> str:
        return f"{x:.3f}"

    return {
        "stream": stream,
        "correct_target_duration_s": f(stats.correct_target_duration_s),
        "wrong_target_duration_s": f(stats.wrong_target_duration_s),
        "lost_target_duration_s": f(stats.lost_target_duration_s),
        "target_not_visible_duration_s": f(stats.target_not_visible_duration_s),
        "target_absent_but_output_valid_duration_s": f(stats.target_absent_but_output_valid_duration_s),
        "no_target_selected_duration_s": f(stats.no_target_selected_duration_s),
        "reference_missing_duration_s": f(stats.reference_missing_duration_s),
        "visible_target_duration_s": f(stats.visible_target_duration_s),
        "stale_output_duration_s": f(stats.stale_output_duration_s),
        "correct_target_ratio": f(stats.correct_target_ratio),
        "wrong_target_ratio": f(stats.wrong_target_ratio),
        "lost_target_ratio": f(stats.lost_target_ratio),
        "reference_missing_ratio": f(stats.reference_missing_ratio),
    }


def write_summary(
    out_dir: Path,
    rows: list[dict[str, str]],
    iou_threshold: float,
    centre_distance_threshold: float,
    max_output_age_s: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "summary.csv"
    fieldnames = list(rows[0].keys())

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_dir / "summary.md"
    lines = [
        "# Target bbox correctness summary",
        "",
        f"IoU threshold: `{iou_threshold:.3f}`",
        f"Centre-distance threshold: `{centre_distance_threshold:.3f}` reference heights",
        f"Maximum output age: `{max_output_age_s:.3f}` s",
        "",
        "| " + " | ".join(fieldnames) + " |",
        "| " + " | ".join(["---"] * len(fieldnames)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[k] for k in fieldnames) + " |")

    max_reference_missing_ratio = max(
        float(row.get("reference_missing_ratio", 0.0))
        for row in rows
    )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- Bbox correctness checks whether the published box overlaps the reference target box.")
    lines.append("- The annotation track ID is still used to locate the reference box inside /tracks.")
    lines.append("- If reference_missing_ratio is high, the run is only partially scored and should not be compared directly against fully scored runs.")

    if max_reference_missing_ratio >= 0.10:
        lines.append("")
        lines.append("## Warning")
        lines.append("")
        lines.append(
            f"- High reference_missing_ratio detected: {max_reference_missing_ratio:.3f}. "
            "This usually means tracker IDs changed relative to the annotation stream."
        )
        lines.append("- Treat correct/wrong/lost values as valid only over the scored subset of the replay.")

    md_path.write_text("\n".join(lines) + "\n")

    print(f"Wrote: {md_path}")
    print(f"Wrote: {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--centre-distance-threshold", type=float, default=0.5)
    parser.add_argument(
        "--max-output-age-s",
        type=float,
        default=DEFAULT_MAX_OUTPUT_AGE_S,
    )
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--raw-topic", default="/target")
    parser.add_argument("--tim-topic", default="/target_memory_mars")
    args = parser.parse_args()

    intervals = load_annotations(args.annotations)
    tracks, raw, tim = read_bag(args.bag, args.tracks_topic, args.raw_topic, args.tim_topic)

    rows = [
        stats_row(
            "raw_target",
            score_on_tracks_clock(
                tracks,
                raw,
                intervals,
                args.iou_threshold,
                args.centre_distance_threshold,
                args.max_output_age_s,
            ),
        ),
        stats_row(
            "tim_target_memory",
            score_on_tracks_clock(
                tracks,
                tim,
                intervals,
                args.iou_threshold,
                args.centre_distance_threshold,
                args.max_output_age_s,
            ),
        ),
    ]

    for row in rows:
        row["max_output_age_s"] = f"{args.max_output_age_s:.3f}"

    write_summary(
        args.out_dir,
        rows,
        args.iou_threshold,
        args.centre_distance_threshold,
        args.max_output_age_s,
    )


if __name__ == "__main__":
    main()
