#!/usr/bin/env python3
"""Extract TIM all_scores from /target_memory/status into a flat CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--topic", default="/target_memory/status")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(args.bag), storage_id="mcap"),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if args.topic not in topic_types:
        raise SystemExit(f"topic not found: {args.topic}")

    msg_type = get_message(topic_types[args.topic])

    rows = []
    t0_ns = None

    while reader.has_next():
        topic, data, stamp_ns = reader.read_next()
        if topic != args.topic:
            continue

        if t0_ns is None:
            t0_ns = stamp_ns

        msg = deserialize_message(data, msg_type)

        try:
            payload = json.loads(msg.data)
        except Exception:
            continue

        t_s = (stamp_ns - t0_ns) / 1e9

        best = payload.get("best") or {}

        base = {
            "t": t_s,
            "frame_id": payload.get("frame_id"),
            "state": payload.get("state"),
            "target_track_id": payload.get("target_track_id"),
            "visible": payload.get("visible"),
            "reason": payload.get("reason"),
            "best_track_id": best.get("track_id"),
        }

        for rank, score in enumerate(payload.get("all_scores") or []):
            rows.append(
                {
                    **base,
                    "rank": rank,
                    "score_track_id": score.get("track_id"),
                    "total": score.get("total"),
                    "iou": score.get("iou"),
                    "distance": score.get("distance"),
                    "scale": score.get("scale"),
                    "confidence": score.get("confidence"),
                    "id_bonus": score.get("id_bonus"),
                    "appearance": score.get("appearance"),
                    "appearance_used": score.get("appearance_used"),
                    "appearance_raw": score.get("appearance_raw"),
                    "appearance_gate_passed": score.get("appearance_gate_passed"),
                    "geometry_allows_appearance": score.get("geometry_allows_appearance"),
                    "ambiguous": score.get("ambiguous"),
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "t",
        "frame_id",
        "state",
        "target_track_id",
        "visible",
        "reason",
        "best_track_id",
        "rank",
        "score_track_id",
        "total",
        "iou",
        "distance",
        "scale",
        "confidence",
        "id_bonus",
        "appearance",
        "appearance_used",
        "appearance_raw",
        "appearance_gate_passed",
        "geometry_allows_appearance",
        "ambiguous",
    ]

    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[ok] rows: {len(rows)}")
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
