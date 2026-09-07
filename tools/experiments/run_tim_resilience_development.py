#!/usr/bin/env python3
"""Run the predeclared four-sequence TIM identity-resilience study."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from std_msgs.msg import String
import yaml


ROOT = Path(__file__).resolve().parents[2]
SEQUENCES = ("may", "seq01", "seq03", "seq04")
CANDIDATES = {
    "baseline": (False, False),
    "challenge": (True, False),
    "gallery_consensus": (False, True),
    "combined": (True, True),
}
CANONICAL = ROOT / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
CANONICAL_SHA = "0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0"
REPORTS = ROOT / "reports/tim_resilience_20260907"


def read_json(path):
    return json.loads(path.read_text())


def bag_path(sequence, candidate, repeat):
    return ROOT / f"bags/replay/tim_resilience_{sequence}_{candidate}_r{repeat}_20260907"


def retained_metadata(sequence):
    return read_json(ROOT / (
        f"bags/replay/p090_{sequence}_global_1c159a4e_2026_09_05/"
        "tim_replay_metadata.json"
    ))


def retained_report(sequence):
    return read_json(ROOT / (
        f"reports/p090_long_gap_global_reacquisition/{sequence}_global/"
        "tim_target_memory.json"
    ))


def run_logged(command, label):
    path = ROOT / "ros2_ws/log" / f"tim_resilience_{label}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def run_cell(sequence, candidate, repeat):
    output = bag_path(sequence, candidate, repeat)
    if output.exists():
        raise FileExistsError(output)
    params = yaml.safe_load(CANONICAL.read_text())
    challenge, consensus = CANDIDATES[candidate]
    values = params["target_memory_mars_node"]["ros__parameters"]
    if candidate != "baseline":
        values["same_id_fresh_challenge_enabled"] = challenge
        values["appearance_gallery_consensus_recovery_enabled"] = consensus
    config = REPORTS / f"{candidate}.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    if not config.exists():
        config.write_text(yaml.safe_dump(params, sort_keys=False))
    elif yaml.safe_load(config.read_text()) != params:
        raise ValueError(f"configuration changed: {config}")
    command = shlex.split(retained_metadata(sequence)["command"])
    command[2] = str(output)
    command[command.index("--config") + 1] = str(config)
    if "--overwrite" in command:
        command.remove("--overwrite")
    print(f"START {sequence} {candidate} r{repeat}", flush=True)
    run_logged([sys.executable, *command], f"{sequence}_{candidate}_r{repeat}")
    print(f"DONE {sequence} {candidate} r{repeat}", flush=True)


def workload(bag):
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
                rosbag2_py.ConverterOptions("", ""))
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/target_memory_mars/status"]))
    sums, reasons, states = Counter(), Counter(), Counter()
    first = last = None
    while reader.has_next():
        _, payload, stamp = reader.read_next()
        status = json.loads(deserialize_message(payload, String).data)
        first = stamp if first is None else first
        last = stamp
        sums["frames"] += 1
        for key in ("backend_calls", "backend_requested", "backend_valid",
                    "cache_hits", "cache_misses", "cache_invalidated",
                    "cache_expired", "cache_lookups"):
            sums[key] += status.get("appearance_" + key, 0)
        sums["encoded_frames"] += status.get("appearance_backend_calls", 0) > 0
        sums["forced_fresh_frames"] += status.get("appearance_skip_reason") == "fresh_identity_challenge"
        sums["positive_memory_update_frames"] += bool(status.get("positive_memory_updated"))
        if status.get("positive_memory_updated"):
            age = status.get("appearance_embedding_age_ms_by_track_id", {}).get(
                str(status.get("candidate_track_id")), 0)
            sums["cached_positive_memory_update_frames"] += age > 0
        reasons[status["reason"].split(":")[0]] += 1
        states[status["state"]] += 1
    duration = (last - first) / 1e9 if last is not None else 0
    return {
        **dict(sums), "timeline_duration_s": duration,
        "embeddings_per_s": sums["backend_valid"] / duration if duration else None,
        "candidates_per_invocation": sums["backend_requested"] / sums["backend_calls"] if sums["backend_calls"] else None,
        "encoded_frame_pct": 100 * sums["encoded_frames"] / sums["frames"] if sums["frames"] else None,
        "reasons": dict(reasons), "states": dict(states),
    }


def normalized(buckets):
    keys = ("correct_target_output", "wrong_person_output",
            "identity_unresolved", "lost_or_suppressed")
    present = sum(buckets[key + "_duration_s"] for key in keys)
    result = {"target_present_evaluable_duration_s": present}
    for key in keys:
        result[key + "_pct"] = 100 * buckets[key + "_duration_s"] / present if present else None
    published = present - buckets["lost_or_suppressed_duration_s"]
    result["publication_correctness_pct"] = 100 * buckets["correct_target_output_duration_s"] / published if published else None
    absent = buckets["target_absent_duration_s"]
    result["target_absent_with_output_pct"] = 100 * buckets["target_absent_with_output_duration_s"] / absent if absent else None
    return result


def summarize():
    cells, aggregates = {}, {}
    for candidate in CANDIDATES:
        total = Counter()
        for sequence in SEQUENCES:
            bag = bag_path(sequence, candidate, 1)
            metadata_path = bag / "tim_replay_metadata.json"
            if not metadata_path.is_file():
                continue
            old = retained_report(sequence)
            reference = ROOT / old["physical_reference_path"]
            if hashlib.sha256(reference.read_bytes()).hexdigest() != old["physical_reference_sha256"]:
                raise ValueError(f"reference changed: {sequence}")
            out = REPORTS / candidate / sequence
            run_logged([sys.executable, "tools/analysis/evaluate_physical_target_bbox_v2.py",
                        str(bag), "--physical-reference", str(reference),
                        "--out-dir", str(out)], f"evaluate_{candidate}_{sequence}")
            report = read_json(out / "tim_target_memory.json")
            metadata = read_json(metadata_path)
            expected = retained_metadata(sequence)["determinism"]["candidate_stream_sha256"]
            assert metadata["determinism"]["candidate_stream_sha256"] == expected
            buckets = report["duration_buckets"]
            repeat = bag_path(sequence, candidate, 2) / "tim_replay_metadata.json"
            repeat_equal = None
            if repeat.is_file():
                repeat_equal = (metadata["determinism"]["generated_semantic_sha256"] ==
                                read_json(repeat)["determinism"]["generated_semantic_sha256"])
            cells[f"{candidate}/{sequence}"] = {
                "duration_buckets": buckets, "normalized": normalized(buckets),
                "workload": workload(bag), "repeat_semantic_equal": repeat_equal,
                "candidate_stream_sha256": expected,
                "generated_semantic_sha256": metadata["determinism"]["generated_semantic_sha256"],
                "repository": metadata["repository"],
                "config_sha256": metadata["canonical_config"]["sha256"],
                "reference_sha256": old["physical_reference_sha256"],
                "retained_duration_buckets_equal": buckets == old["duration_buckets"],
            }
            total.update(buckets)
            print(candidate, sequence, {k: round(buckets[k + "_duration_s"], 6)
                  for k in ("correct_target_output", "wrong_person_output", "lost_or_suppressed")},
                  "repeat", repeat_equal, flush=True)
        if total:
            aggregates[candidate] = {"duration_buckets": dict(total), "normalized": normalized(total)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "summary.json").write_text(json.dumps({
        "protocol": "docs/results/selected_target_tracking/tim_resilience_methodology_20260907.md",
        "heldout_accessed": False, "cells": cells, "aggregates": aggregates,
    }, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=tuple(CANDIDATES), action="append")
    parser.add_argument("--repeat", type=int, choices=(1, 2), default=1)
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()
    if hashlib.sha256(CANONICAL.read_bytes()).hexdigest() != CANONICAL_SHA:
        raise ValueError("canonical configuration changed")
    for candidate in args.candidate or ():
        for sequence in SEQUENCES:
            run_cell(sequence, candidate, args.repeat)
    if args.summarize:
        summarize()


if __name__ == "__main__":
    main()
