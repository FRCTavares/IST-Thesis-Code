#!/usr/bin/env python3
"""Evaluate raw/TIM selected-target correctness grouped by annotation event_type.

This is a paper-facing helper for complex sequences where one bag contains
multiple behaviors: clean visibility, occlusion ambiguity, ID fragmentation,
target absence, and re-entry.

It assumes the same track-ID annotation convention used by
evaluate_tim_target_correctness.py.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


RAW_TOPIC = "/target"
TIM_TOPIC = "/target_memory_mars"


@dataclass(frozen=True)
class Interval:
    start_s: float
    end_s: float
    target_visible: bool
    correct_id: Optional[int]
    event_type: str


@dataclass
class TargetSample:
    t_s: float
    valid: bool
    track_id: int


def parse_bool(v: object) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def parse_id(v: object) -> Optional[int]:
    txt = str(v).strip()
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def load_annotations(path: Path) -> list[Interval]:
    rows: list[Interval] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"start_s", "end_s", "target_visible", "correct_target_track_id", "event_type"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"annotation CSV missing columns: {sorted(missing)}")

        for r in reader:
            rows.append(
                Interval(
                    start_s=float(r["start_s"]),
                    end_s=float(r["end_s"]),
                    target_visible=parse_bool(r["target_visible"]),
                    correct_id=parse_id(r["correct_target_track_id"]),
                    event_type=str(r.get("event_type", "")).strip() or "unlabeled",
                )
            )

    rows.sort(key=lambda x: x.start_s)
    return rows


def open_reader(bag: Path) -> rosbag2_py.SequentialReader:
    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap")
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    reader.open(storage_options, converter_options)
    return reader


def msg_stamp_ns(msg: object, fallback_ns: int) -> int:
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is not None:
        sec = int(getattr(stamp, "sec", 0))
        nsec = int(getattr(stamp, "nanosec", 0))
        if sec != 0 or nsec != 0:
            return sec * 1_000_000_000 + nsec

    src = getattr(msg, "src_stamp_ns", 0)
    try:
        src = int(src)
        if src > 0:
            return src
    except Exception:
        pass

    return int(fallback_ns)


def target_valid(msg: object) -> bool:
    tid = int(getattr(msg, "id", 0))
    w = float(getattr(msg, "w", 0.0))
    h = float(getattr(msg, "h", 0.0))
    score = float(getattr(msg, "score", 0.0))
    quality = float(getattr(msg, "quality", 0.0))
    return tid > 0 and w > 0.0 and h > 0.0 and (score > 0.0 or quality > 0.0)


def load_target_samples(bag: Path, topic: str) -> list[TargetSample]:
    reader = open_reader(bag)
    topic_types = {x.name: x.type for x in reader.get_all_topics_and_types()}

    if topic not in topic_types:
        return []

    msg_type = get_message(topic_types[topic])
    raw: list[tuple[int, bool, int]] = []

    while reader.has_next():
        name, data, t_ns = reader.read_next()
        if name != topic:
            continue
        msg = deserialize_message(data, msg_type)
        stamp_ns = msg_stamp_ns(msg, t_ns)
        raw.append((stamp_ns, target_valid(msg), int(getattr(msg, "id", 0))))

    if not raw:
        return []

    first_ns = raw[0][0]
    return [
        TargetSample(
            t_s=(stamp_ns - first_ns) / 1e9,
            valid=valid,
            track_id=track_id,
        )
        for stamp_ns, valid, track_id in raw
    ]


def latest_at(samples: list[TargetSample], t_s: float, start_idx: int) -> tuple[Optional[TargetSample], int]:
    idx = start_idx
    while idx + 1 < len(samples) and samples[idx + 1].t_s <= t_s:
        idx += 1

    if idx < len(samples) and samples[idx].t_s <= t_s:
        return samples[idx], idx
    return None, idx


def classify(sample: Optional[TargetSample], interval: Interval) -> str:
    if not interval.target_visible:
        if sample is not None and sample.valid:
            return "target_absent_but_output"
        return "target_not_visible"

    if sample is None or not sample.valid:
        return "lost"

    if interval.correct_id is not None and sample.track_id == interval.correct_id:
        return "correct"

    return "wrong"


def evaluate(samples: list[TargetSample], intervals: list[Interval], dt: float) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    if not samples:
        return out

    idx = 0

    for interval in intervals:
        t = interval.start_s
        while t < interval.end_s:
            step = min(dt, interval.end_s - t)
            sample, idx = latest_at(samples, t, idx)
            cls = classify(sample, interval)
            ev = interval.event_type

            out[ev][cls] += step
            out[ev]["total_s"] += step

            if interval.target_visible:
                out[ev]["visible_s"] += step
            else:
                out[ev]["not_visible_s"] += step

            t += step

    return out


def rows_for_stream(stream: str, grouped: dict[str, dict[str, float]]) -> list[dict[str, object]]:
    rows = []

    for ev in sorted(grouped):
        g = grouped[ev]
        visible = g.get("visible_s", 0.0)
        correct = g.get("correct", 0.0)
        wrong = g.get("wrong", 0.0)
        lost = g.get("lost", 0.0)

        if visible > 0:
            correct_ratio = correct / visible
            wrong_ratio = wrong / visible
            lost_ratio = lost / visible
        else:
            correct_ratio = math.nan
            wrong_ratio = math.nan
            lost_ratio = math.nan

        rows.append(
            {
                "stream": stream,
                "event_type": ev,
                "total_s": f"{g.get('total_s', 0.0):.3f}",
                "visible_s": f"{visible:.3f}",
                "correct_s": f"{correct:.3f}",
                "wrong_s": f"{wrong:.3f}",
                "lost_s": f"{lost:.3f}",
                "target_absent_but_output_s": f"{g.get('target_absent_but_output', 0.0):.3f}",
                "target_not_visible_s": f"{g.get('target_not_visible', 0.0):.3f}",
                "correct_ratio": "" if math.isnan(correct_ratio) else f"{correct_ratio:.3f}",
                "wrong_ratio": "" if math.isnan(wrong_ratio) else f"{wrong_ratio:.3f}",
                "lost_ratio": "" if math.isnan(lost_ratio) else f"{lost_ratio:.3f}",
            }
        )

    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bag", type=Path)
    ap.add_argument("--annotations", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dt", type=float, default=0.02)
    args = ap.parse_args()

    intervals = load_annotations(args.annotations)

    raw_samples = load_target_samples(args.bag, RAW_TOPIC)
    tim_samples = load_target_samples(args.bag, TIM_TOPIC)

    raw_grouped = evaluate(raw_samples, intervals, args.dt)
    tim_grouped = evaluate(tim_samples, intervals, args.dt)

    rows = rows_for_stream("raw_target", raw_grouped) + rows_for_stream("tim_target_memory", tim_grouped)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "stream",
                "event_type",
                "total_s",
                "visible_s",
                "correct_s",
                "wrong_s",
                "lost_s",
                "target_absent_but_output_s",
                "target_not_visible_s",
                "correct_ratio",
                "wrong_ratio",
                "lost_ratio",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
