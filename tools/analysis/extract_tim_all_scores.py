#!/usr/bin/env python3
"""Extract TIM-MARS all_scores from /target_memory_mars/status into a flat CSV."""

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
    parser.add_argument("--topic", default="/target_memory_mars/status")
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
            "control_mode": payload.get("control_mode"),
            "target_track_id": payload.get("target_track_id"),
            "visible": payload.get("visible"),
            "reacquired": payload.get("reacquired"),
            "quality": payload.get("quality"),
            "frames_since_seen": payload.get("frames_since_seen"),
            "reason": payload.get("reason"),
            "memory_update_frozen": payload.get("memory_update_frozen"),
            "memory_update_freeze_reason": payload.get("memory_update_freeze_reason"),
            "same_id_appearance_ambiguity": payload.get("same_id_appearance_ambiguity"),
            "appearance_margin_best_vs_second": payload.get("appearance_margin_best_vs_second"),
            "geometry_strength": payload.get("geometry_strength"),
            "risk_hard_negative": payload.get("risk_hard_negative"),
            "risk_absence": payload.get("risk_absence"),
            "risk_scene_ambiguity": payload.get("risk_scene_ambiguity"),
            "v4a_publish_allowed": payload.get("v4a_publish_allowed"),
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
                    "hard_negative_similarity": score.get("hard_negative_similarity"),
                    "hard_negative_margin": score.get("hard_negative_margin"),
                    "hard_negative_reject": score.get("hard_negative_reject"),
                    "ambiguous": score.get("ambiguous"),
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "t", "frame_id", "state", "control_mode", "target_track_id", "visible",
        "reacquired", "quality", "frames_since_seen", "reason",
        "memory_update_frozen", "memory_update_freeze_reason",
        "same_id_appearance_ambiguity", "appearance_margin_best_vs_second",
        "geometry_strength", "risk_hard_negative", "risk_absence",
        "risk_scene_ambiguity", "v4a_publish_allowed", "best_track_id",
        "rank", "score_track_id", "total", "iou", "distance", "scale",
        "confidence", "id_bonus", "appearance", "appearance_used",
        "appearance_raw", "appearance_gate_passed", "geometry_allows_appearance",
        "hard_negative_similarity", "hard_negative_margin",
        "hard_negative_reject", "ambiguous",
    ]

    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[ok] rows: {len(rows)}")
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
