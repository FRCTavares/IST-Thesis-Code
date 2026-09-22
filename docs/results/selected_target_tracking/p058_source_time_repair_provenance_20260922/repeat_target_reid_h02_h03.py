#!/usr/bin/env python3
"""Independently repeat historical Target-ReID and compare all ROS fields."""

import json
import os
import subprocess
import sys
from pathlib import Path


MAIN = Path("/home/francisco/Desktop/Thesis-Code")
HIST = Path("/home/francisco/Desktop/Thesis-Code-p058-repro-dc4c5c39")
RUN = HIST / "reports/p058_final_architecture_comparison/p058_timebase_repro_h02_h03_dc4c5c39_ros_env_20260922"
H01_RUN = HIST / "reports/p058_final_architecture_comparison/p058_timebase_repro_h01_dc4c5c39_20260921"
CHECKS = MAIN / "reports/p058_source_time_evaluator_repair/reproduction_checks"
PINNED = {
    "MKL_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "TF_DETERMINISTIC_OPS": "1",
    "TF_ENABLE_ONEDNN_OPTS": "0",
    "TF_NUM_INTEROP_THREADS": "1",
    "TF_NUM_INTRAOP_THREADS": "1",
}


def compare(sequence, run):
    sequence_root = run / "sequences" / sequence
    primary = sequence_root / "generated_bags/target_reid_090"
    repeat = sequence_root / "diagnostics/target_reid_repeat_1"
    cmd = [sys.executable, "/tmp/compare_target_reid_semantic.py", str(primary), str(repeat)]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    CHECKS.mkdir(parents=True, exist_ok=True)
    out = CHECKS / (sequence + "_target_reid_repeat.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"sequence": sequence, "count": payload["count_a"], "all_equal": payload["record_times_and_all_deserialised_fields_equal"], "check": str(out)}), flush=True)


def main():
    env = os.environ.copy()
    env.update(PINNED)
    for sequence in ("heldout_h02_crossing", "heldout_h03_occlusion_distractor"):
        root = RUN / "sequences" / sequence
        metadata = json.loads(
            (root / "generated_bags/target_reid_090.p058_target_reid.json").read_text()
        )
        repeat = root / "diagnostics/target_reid_repeat_1"
        if repeat.exists():
            raise RuntimeError(repeat)
        repeat.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(HIST / "tools/experiments/run_p058_target_reid_replay.py"),
            metadata["input_bag"],
            str(repeat),
            "--model", str(HIST / "models/reid/mars-small128.pb"),
            "--selected-track-id", str(metadata["selected_track_id"]),
            "--threshold", str(metadata["threshold"]),
            "--image-width", str(metadata["image_width"]),
            "--image-height", str(metadata["image_height"]),
            "--image-topic", metadata["image_topic"],
            "--tracks-topic", metadata["tracks_topic"],
            "--max-image-age-ms", str(metadata["max_image_age_ms"]),
        ]
        print(json.dumps({"sequence": sequence, "historical_command": command}), flush=True)
        subprocess.run(command, check=True, env=env, cwd=HIST)
        compare(sequence, RUN)
    compare("heldout_h01_exit_reentry", H01_RUN)


if __name__ == "__main__":
    main()
