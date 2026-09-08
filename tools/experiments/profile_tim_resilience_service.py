#!/usr/bin/env python3
"""Measure offline Seq04 service demand without altering replay decisions.

This is a bounded service-time probe, not live latency or Issue #32 resource
characterization. The original semantic digest must remain identical.
"""

import argparse
import json
from pathlib import Path
import runpy
import shlex
import sys
from time import perf_counter_ns

import numpy as np

from thesis_bringup.tim_mars.runtime import TimMarsRuntime


ROOT = Path(__file__).resolve().parents[2]


def describe(values):
    return {
        "count": len(values), "total_ms": float(sum(values)),
        "mean_ms": float(np.mean(values)),
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
        "max_ms": float(max(values)),
    } if values else {"count": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=("baseline", "available_image_challenge"))
    args = parser.parse_args()
    original_bag = ROOT / f"bags/replay/tim_resilience_seq04_{args.candidate}_r1_20260907"
    original_metadata = json.loads((original_bag / "tim_replay_metadata.json").read_text())
    output = ROOT / f"bags/replay/tim_resilience_seq04_{args.candidate}_service_20260907"
    if output.exists():
        raise FileExistsError(output)
    command = shlex.split(original_metadata["command"])
    command[2] = str(output)
    original_process = TimMarsRuntime.process_tracks
    process_ms, appearance_ms, forced_ms, timestamps = [], [], [], []

    def measured_process(self, tracks):
        start = perf_counter_ns()
        result = original_process(self, tracks)
        process_ms.append((perf_counter_ns() - start) / 1e6)
        diagnostics = result.diagnostics
        timestamps.append(diagnostics.track_timestamp_ns)
        if diagnostics.appearance_backend_calls:
            appearance_ms.append(diagnostics.appearance_backend_wall_ms)
            if diagnostics.appearance_skip_reason == "fresh_identity_challenge":
                forced_ms.append(diagnostics.appearance_backend_wall_ms)
        return result

    TimMarsRuntime.process_tracks = measured_process
    sys.argv = command
    try:
        runpy.run_path(str(ROOT / command[0]), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise
    finally:
        TimMarsRuntime.process_tracks = original_process
    metadata = json.loads((output / "tim_replay_metadata.json").read_text())
    same = (metadata["determinism"]["generated_semantic_sha256"] ==
            original_metadata["determinism"]["generated_semantic_sha256"])
    duration = (timestamps[-1] - timestamps[0]) / 1e9
    result = {
        "candidate": args.candidate, "sequence": "seq04",
        "measurement": "offline_serial_service_time_not_live_latency",
        "semantic_digest_equal": same, "timeline_duration_s": duration,
        "runtime_service": describe(process_ms),
        "appearance_service": describe(appearance_ms),
        "forced_appearance_service": describe(forced_ms),
        "runtime_serial_service_fraction": sum(process_ms) / (1000 * duration),
        "appearance_serial_service_fraction": sum(appearance_ms) / (1000 * duration),
    }
    path = ROOT / f"reports/tim_resilience_20260907/service_{args.candidate}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not same:
        raise RuntimeError("profiling changed semantic output")


if __name__ == "__main__":
    main()
