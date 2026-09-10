#!/usr/bin/env python3
"""Integrity summary of the ``/control_ref/diagnostics`` topic (Issue #74).

This is a diagnostic / integrity helper, **not** the final #50/#74 scientific
analyser. It reads the recorded controller-decision diagnostics from a bag and
reports mode occupancy, reason counts, recovery-attempt bookkeeping, and one
hard safety invariant:

    recovery_active == true must never coincide with a non-zero translation
    command (command_vx / command_vy).

Exit code is non-zero if that invariant is violated, if no diagnostics were
found, or on an IO error.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TOPIC = "/control_ref/diagnostics"
TRANSLATION_EPS = 1e-6

_FIELDS = (
    "mode",
    "reason",
    "tim_state",
    "tim_control_mode",
    "selection_generation",
    "status_fresh",
    "target_fresh",
    "target_valid",
    "recovery_enabled",
    "recovery_active",
    "recovery_direction",
    "recovery_elapsed_s",
    "recovery_integrated_yaw_rad",
    "recovery_budget_remaining_rad",
    "recovery_max_integrated_yaw_rad",
    "recovery_max_duration_s",
    "last_trusted_valid",
    "last_trusted_age_s",
    "last_trusted_generation",
    "recovery_history_consumed",
    "command_vx",
    "command_vy",
    "command_yaw_z",
    "command_saturated_yaw",
)


def _stamp_ns(header: Any, fallback_ns: int) -> int:
    try:
        return int(header.stamp.sec) * 1_000_000_000 + int(header.stamp.nanosec)
    except AttributeError:
        return int(fallback_ns)


def read_diagnostics_stream(bag: Path, topic: str = TOPIC) -> list[dict[str, Any]]:
    from rclpy.serialization import deserialize_message
    from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
    from rosidl_runtime_py.utilities import get_message

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag), storage_id="mcap"),
        ConverterOptions("cdr", "cdr"),
    )
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if topic not in types:
        raise SystemExit(f"no {topic} in {bag}")
    msg_cls = get_message(types[topic])

    samples: list[dict[str, Any]] = []
    while reader.has_next():
        name, raw, bag_ns = reader.read_next()
        if name != topic:
            continue
        msg = deserialize_message(raw, msg_cls)
        record: dict[str, Any] = {
            "stamp_ns": _stamp_ns(getattr(msg, "header", None), bag_ns)
        }
        for field in _FIELDS:
            record[field] = getattr(msg, field)
        samples.append(record)
    samples.sort(key=lambda item: item["stamp_ns"])
    return samples


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"ok": False, "error": "no /control_ref/diagnostics samples"}

    stamps = [int(s["stamp_ns"]) for s in samples]
    intervals = [
        (stamps[i + 1] - stamps[i]) / 1e9 for i in range(len(stamps) - 1)
    ]
    positive = [d for d in intervals if d > 0]
    median_dt = statistics.median(positive) if positive else 0.0

    mode_occupancy: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    transition_pairs: Counter[str] = Counter()

    recovery_attempts = 0
    recovery_active_duration_s = 0.0
    prev_mode: str | None = None
    prev_recovery_active = False
    max_integrated_yaw = 0.0
    max_last_trusted_age = 0.0
    translation_violations: list[dict[str, Any]] = []

    for index, sample in enumerate(samples):
        mode = str(sample["mode"])
        reason = str(sample["reason"])
        dt = (
            intervals[index]
            if index < len(intervals) and intervals[index] > 0
            else median_dt
        )
        mode_occupancy[mode] += dt
        mode_counts[mode] += 1
        reason_counts[reason] += 1

        if prev_mode is not None and mode != prev_mode:
            transition_pairs[f"{prev_mode}->{mode}"] += 1
        prev_mode = mode

        active = bool(sample["recovery_active"])
        if active and not prev_recovery_active:
            recovery_attempts += 1
        if active:
            recovery_active_duration_s += dt
        prev_recovery_active = active

        max_integrated_yaw = max(
            max_integrated_yaw, float(sample["recovery_integrated_yaw_rad"])
        )
        age = float(sample["last_trusted_age_s"])
        if math.isfinite(age):
            max_last_trusted_age = max(max_last_trusted_age, age)

        vx = float(sample["command_vx"])
        vy = float(sample["command_vy"])
        if active and (abs(vx) > TRANSLATION_EPS or abs(vy) > TRANSLATION_EPS):
            translation_violations.append(
                {
                    "index": index,
                    "stamp_ns": int(sample["stamp_ns"]),
                    "mode": mode,
                    "reason": reason,
                    "command_vx": vx,
                    "command_vy": vy,
                    "command_yaw_z": float(sample["command_yaw_z"]),
                }
            )

    total = sum(mode_occupancy.values())
    safety_ok = not translation_violations

    return {
        "ok": True,
        "topic": TOPIC,
        "sample_count": len(samples),
        "median_sample_interval_s": round(median_dt, 6),
        "approx_span_s": round(total, 6),
        "mode_message_counts": dict(sorted(mode_counts.items())),
        "mode_occupancy_s": {
            k: round(v, 6) for k, v in sorted(mode_occupancy.items())
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "mode_transition_pairs": dict(sorted(transition_pairs.items())),
        "recovery_attempt_count": recovery_attempts,
        "recovery_active_duration_s": round(recovery_active_duration_s, 6),
        "max_recovery_integrated_yaw_rad": round(max_integrated_yaw, 9),
        "max_last_trusted_age_s": round(max_last_trusted_age, 6),
        "recovery_enabled_any": any(
            bool(s["recovery_enabled"]) for s in samples
        ),
        "safety_ok": safety_ok,
        "translation_during_recovery_violations": translation_violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    samples = read_diagnostics_stream(args.bag, args.topic)
    result = summarize(samples)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)

    if not result.get("ok"):
        return 1
    if not result.get("safety_ok"):
        print(
            "[error] recovery_active coincided with non-zero translation",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
