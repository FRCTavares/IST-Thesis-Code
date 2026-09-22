#!/usr/bin/env python3
"""Compare retained #58 physical-v2 results with source-time-corrected results.

This is a reporting tool. It reads immutable historical JSON and separately
versioned corrected JSON; it does not run or alter the physical-v2 scorer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SEQUENCES = (
    "heldout_h01_exit_reentry",
    "heldout_h02_crossing",
    "heldout_h03_occlusion_distractor",
)
ARCHITECTURES = (
    "bytetrack_raw",
    "target_reid_090",
    "bytetrack_tim_mars",
    "deepsort_raw",
)
REPORT_NAME = {
    "bytetrack_raw": "raw_target.json",
    "target_reid_090": "raw_target.json",
    "bytetrack_tim_mars": "tim_target_memory.json",
    "deepsort_raw": "raw_target.json",
}
METRICS = (
    ("correct_target_output_duration_s", "duration_buckets", "s"),
    ("wrong_person_output_duration_s", "duration_buckets", "s"),
    ("identity_unresolved_duration_s", "duration_buckets", "s"),
    ("lost_or_suppressed_duration_s", "duration_buckets", "s"),
    ("target_absent_duration_s", "duration_buckets", "s"),
    ("target_absent_with_output_duration_s", "duration_buckets", "s"),
    ("reference_unavailable_duration_s", "duration_buckets", "s"),
    ("reference_gap_duration_s", "duration_buckets", "s"),
    ("reference_gap_with_output_duration_s", "duration_buckets", "s"),
    ("iou_duration_weighted_mean", "localisation", "fraction"),
    ("iou_median", "localisation", "fraction"),
    ("centre_error_px_duration_weighted_mean", "localisation", "px"),
    ("scored_duration_s", "localisation", "s"),
    ("n_samples", "localisation", "count"),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def format_value(value: int | float | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    return f"{value:.9f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", required=True, type=Path)
    parser.add_argument("--corrected", required=True, type=Path)
    parser.add_argument("--output-stem", required=True, type=Path)
    args = parser.parse_args()

    cells = []
    rows = []
    origins = {}
    for sequence in SEQUENCES:
        historical_cells = {
            cell["architecture_id"]: cell
            for cell in load(
                args.historical / "sequences" / sequence / "cells.json"
            )
        }
        corrected_sequence = args.corrected / (
            "h01_dc4c5c39" if sequence == SEQUENCES[0]
            else ("h02_dc4c5c39" if sequence == SEQUENCES[1]
                  else "h03_dc4c5c39")
        )
        sequence_origins = set()
        sequence_clocks = set()
        for architecture in ARCHITECTURES:
            old_path = (
                args.historical / "sequences" / sequence / "evaluation"
                / architecture / REPORT_NAME[architecture]
            )
            new_path = (
                corrected_sequence / architecture / REPORT_NAME[architecture]
            )
            old = load(old_path)
            new = load(new_path)
            assert old["reconciliation"]["ok"], old_path
            assert new["reconciliation"]["ok"], new_path
            assert old["physical_reference_sha256"] == new["physical_reference_sha256"]
            assert old["evaluation_window"] == new["evaluation_window"]
            assert old["total_evaluated_duration_s"] == new["total_evaluated_duration_s"]
            repair = new["timebase_repair"]
            assert repair["repair_version"] == "p058_source_time_repair_v1"
            assert new["evaluation_wrapper"] == "evaluate_physical_target_bbox_v2_source_time_repair.py"
            assert repair["source_time_origin_ns"] == historical_cells[
                architecture
            ]["bootstrap"]["reference_time_origin_ns"]
            sequence_origins.add(repair["source_time_origin_ns"])
            sequence_clocks.add(repair["source_time_origin_clock"])
            cell = {
                "sequence_id": sequence,
                "architecture_id": architecture,
                "historical_report": str(old_path),
                "historical_report_sha256": sha256_file(old_path),
                "corrected_report": str(new_path),
                "corrected_report_sha256": sha256_file(new_path),
                "reference_sha256": old["physical_reference_sha256"],
                "source_time_origin_ns": repair["source_time_origin_ns"],
                "source_time_origin_clock": repair["source_time_origin_clock"],
                "source_image_topic": repair["source_image_topic"],
                "source_bag_path": repair["source_bag_path"],
                "output_bag_path": repair["output_bag_path"],
                "output_read_stats": repair["output_read_stats"],
                "historical_reconciliation": old["reconciliation"],
                "corrected_reconciliation": new["reconciliation"],
                "metrics": {},
            }
            for metric, section, unit in METRICS:
                before = old[section][metric]
                after = new[section][metric]
                delta = None if before is None or after is None else after - before
                values = {"old": before, "corrected": after, "delta": delta, "unit": unit}
                cell["metrics"][metric] = values
                rows.append({
                    "sequence_id": sequence,
                    "architecture_id": architecture,
                    "metric": metric,
                    **values,
                })
            cells.append(cell)
        assert len(sequence_origins) == 1, (sequence, sequence_origins)
        assert len(sequence_clocks) == 1, (sequence, sequence_clocks)
        origins[sequence] = {
            "source_time_origin_ns": sequence_origins.pop(),
            "source_time_origin_clock": sequence_clocks.pop(),
        }

    assert len(cells) == 12
    assert len(rows) == 12 * len(METRICS)
    payload = {
        "schema_version": 1,
        "scope": "post-access source-time evaluator correctness repair",
        "historical_authority_commit": "dc4c5c39cfbe9911b63cb9757d01ca3de096f696",
        "historical_result_root": str(args.historical),
        "corrected_result_root": str(args.corrected),
        "delta_definition": "corrected minus old",
        "sequence_origins": origins,
        "cells": cells,
        "rows": rows,
    }
    stem = args.output_stem
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("sequence_id", "architecture_id", "metric", "old", "corrected", "delta", "unit"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# #58 source-time repair: old versus corrected physical-v2 metrics",
        "",
        "Post-access evaluator correctness repair; the 16 September evidence and physical-v2 scoring core are unchanged.",
        "Delta is corrected minus old. Times use seconds; IoU is a fraction and centre error is pixels.",
        "The companion JSON retains full precision, report hashes, source origins and output-read statistics.",
        "",
    ]
    for sequence in SEQUENCES:
        origin = origins[sequence]
        lines.extend([
            f"## {sequence}",
            "",
            f"Source origin: `{origin['source_time_origin_ns']}` ns from `{origin['source_time_origin_clock']}`.",
            "",
            "| Architecture | Topic | Messages | src_stamp_ns | header.stamp | Bag record | Duplicate replaced | Non-monotonic skipped |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for cell in cells:
            if cell["sequence_id"] != sequence:
                continue
            for topic, stats in cell["output_read_stats"].items():
                lines.append(
                    f"| {cell['architecture_id']} | {topic} "
                    f"| {stats['messages_seen']} | {stats['src_stamp_ns']} "
                    f"| {stats['header.stamp']} | {stats['bag_record_timestamp']} "
                    f"| {stats['duplicate_replaced']} | {stats['non_monotonic_skipped']} |"
                )
        lines.extend([
            "",
            "| Architecture | Metric | Old | Corrected | Delta |",
            "| --- | --- | ---: | ---: | ---: |",
        ])
        for row in rows:
            if row["sequence_id"] != sequence:
                continue
            lines.append(
                f"| {row['architecture_id']} | {row['metric']} ({row['unit']}) "
                f"| {format_value(row['old'])} | {format_value(row['corrected'])} "
                f"| {format_value(row['delta'])} |"
            )
        lines.append("")
    stem.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"cells": len(cells), "rows": len(rows), "origins": origins}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
