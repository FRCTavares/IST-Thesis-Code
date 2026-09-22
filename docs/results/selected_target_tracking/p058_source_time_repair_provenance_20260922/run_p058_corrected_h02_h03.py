#!/usr/bin/env python3
"""Evaluate verified historical H02/H03 bags on the source-time axis."""

import json
import subprocess
import sys
from pathlib import Path


MAIN = Path("/home/francisco/Desktop/Thesis-Code")
REPRO = Path(
    "/home/francisco/Desktop/Thesis-Code-p058-repro-dc4c5c39/"
    "reports/p058_final_architecture_comparison/"
    "p058_timebase_repro_h02_h03_dc4c5c39_ros_env_20260922"
)
OUT = MAIN / "reports/p058_source_time_evaluator_repair"
MAPPING = {
    "bytetrack_raw": ("bytetrack_fixed", "/target"),
    "target_reid_090": ("target_reid_090", "/target_reid"),
    "bytetrack_tim_mars": ("bytetrack_tim_mars", "/target_memory_mars"),
    "deepsort_raw": ("deepsort_fixed", "/target"),
}


def main():
    wrapper = MAIN / "tools/analysis/evaluate_physical_target_bbox_v2_source_time_repair.py"
    if not wrapper.is_file():
        raise RuntimeError(wrapper)
    executed = []
    for sequence, label in (
        ("heldout_h02_crossing", "h02_dc4c5c39"),
        ("heldout_h03_occlusion_distractor", "h03_dc4c5c39"),
    ):
        reference = MAIN / "docs/data/physical_target_references" / (sequence + ".json")
        ref = json.loads(reference.read_text())
        source = MAIN / ref["provenance"]["source_bag_path"]
        assert source.is_dir()
        for architecture, (bag_name, topic) in MAPPING.items():
            output_bag = REPRO / "sequences" / sequence / "generated_bags" / bag_name
            out_dir = OUT / label / architecture
            if not output_bag.is_dir() or out_dir.exists():
                raise RuntimeError((output_bag, out_dir))
            cmd = [
                sys.executable,
                str(wrapper),
                str(output_bag),
                "--source-bag", str(source),
                "--physical-reference", str(reference),
                "--out-dir", str(out_dir),
                "--raw-topic", topic,
                "--tim-topic", topic,
            ]
            print(json.dumps({"sequence": sequence, "architecture": architecture, "command": cmd}), flush=True)
            subprocess.run(cmd, check=True, cwd=MAIN)
            report_name = "tim_target_memory.json" if architecture == "bytetrack_tim_mars" else "raw_target.json"
            report = json.loads((out_dir / report_name).read_text())
            if not report["reconciliation"]["ok"]:
                raise RuntimeError((sequence, architecture, "reconciliation failed"))
            executed.append({
                "sequence": sequence,
                "architecture": architecture,
                "topic": topic,
                "output_bag": str(output_bag),
                "report": str(out_dir / report_name),
                "origin_ns": report["timebase_repair"]["source_time_origin_ns"],
                "origin_clock": report["timebase_repair"]["source_time_origin_clock"],
                "output_read_stats": report["timebase_repair"]["output_read_stats"],
                "reconciliation": report["reconciliation"],
            })
    path = OUT / "h02_h03_corrected_run.json"
    path.write_text(json.dumps(executed, indent=2) + "\n")
    print(json.dumps({"corrected_cells": len(executed), "run_log": str(path)}))


if __name__ == "__main__":
    main()
