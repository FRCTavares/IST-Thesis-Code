#!/usr/bin/env python3
"""TIM-MARS state-occupancy and transition diagnostics for the ByteTrack
sensitivity experiment.

Parses ``/target_memory_mars/status`` (a JSON string stream) from a
deterministic TIM replay bag and reports, using only fields that actually
appear in the canonical status schema:

* time occupancy per reported state;
* state transition counts, including transitions into LOST and into
  REACQUIRED;
* target-authority changes, counted from ``selection_generation`` and
  ``target_track_id`` movement.

Durations use the interval between consecutive status messages; the final
message is credited the median inter-message interval.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def read_status_stream(bag: Path, status_topic: str) -> list[tuple[int, dict]]:
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag), storage_id="mcap"),
        ConverterOptions("cdr", "cdr"),
    )
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if status_topic not in types:
        raise SystemExit(f"no {status_topic} in {bag}")
    msg_cls = get_message(types[status_topic])
    out: list[tuple[int, dict]] = []
    while reader.has_next():
        topic, raw, ns = reader.read_next()
        if topic != status_topic:
            continue
        msg = deserialize_message(raw, msg_cls)
        try:
            payload = json.loads(msg.data)
        except Exception:
            payload = {}
        stamp = payload.get("track_timestamp_ns") or ns
        out.append((int(stamp), payload))
    out.sort(key=lambda item: item[0])
    return out


def analyse(bag: Path, status_topic: str) -> dict:
    stream = read_status_stream(bag, status_topic)
    if not stream:
        return {"ok": False, "error": "no status messages"}

    intervals = [
        (stream[i + 1][0] - stream[i][0]) / 1e9 for i in range(len(stream) - 1)
    ]
    positive = [d for d in intervals if d > 0]
    median_dt = statistics.median(positive) if positive else 0.0

    occupancy: Counter[str] = Counter()
    transitions = 0
    into_lost = 0
    into_reacquired = 0
    transition_pairs: Counter[str] = Counter()
    prev_state: str | None = None
    prev_generation = None
    prev_target_id = None
    authority_changes = 0
    states_seen: Counter[str] = Counter()

    for index, (_stamp, payload) in enumerate(stream):
        state = str(payload.get("state", "UNKNOWN")).upper()
        states_seen[state] += 1
        dt = intervals[index] if index < len(intervals) and intervals[index] > 0 else median_dt
        occupancy[state] += dt

        if prev_state is not None and state != prev_state:
            transitions += 1
            transition_pairs[f"{prev_state}->{state}"] += 1
            if state == "LOST":
                into_lost += 1
            if state == "REACQUIRED":
                into_reacquired += 1
        prev_state = state

        generation = payload.get("selection_generation")
        target_id = payload.get("target_track_id")
        if prev_generation is not None and generation is not None and generation != prev_generation:
            authority_changes += 1
        elif (
            prev_target_id not in (None, 0)
            and target_id not in (None, 0)
            and target_id != prev_target_id
        ):
            authority_changes += 1
        prev_generation = generation if generation is not None else prev_generation
        prev_target_id = target_id if target_id not in (None,) else prev_target_id

    total = sum(occupancy.values())
    occ_fraction = {
        state: round(value / total, 6) for state, value in sorted(occupancy.items())
    } if total > 0 else {}

    return {
        "ok": True,
        "status_topic": status_topic,
        "status_messages": len(stream),
        "median_status_interval_s": round(median_dt, 6),
        "approx_status_span_s": round(total, 6),
        "states_present": sorted(states_seen),
        "state_message_counts": dict(sorted(states_seen.items())),
        "state_occupancy_s": {k: round(v, 6) for k, v in sorted(occupancy.items())},
        "state_occupancy_fraction": occ_fraction,
        "transition_count": transitions,
        "transitions_into_lost": into_lost,
        "transitions_into_reacquired": into_reacquired,
        "transition_pairs": dict(sorted(transition_pairs.items())),
        "target_authority_change_count": authority_changes,
        "final_selection_generation": prev_generation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tim_bag", type=Path)
    parser.add_argument("--status-topic", default="/target_memory_mars/status")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = analyse(args.tim_bag, args.status_topic)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
