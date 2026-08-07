#!/usr/bin/env python3
"""Aggregate the frozen first-phase sequences into one Issue #30 report.

External (DanceTrack/VisDrone) sequences are scored by
``run_external_sequence_report.py``'s frame-level outcome taxonomy. ROS 2
sequences use the existing Issue #26 event-and-recovery vocabulary
(``evaluate_tim_event_recovery.py``) -- a related but not identical
taxonomy, as documented in Slice 13 -- read from their already-generated
reports rather than recomputed here.

Sequences whose manifest entry has ``status: "excluded"`` (a pre-outcome
scope decision, e.g. domain relevance or capture cost -- never based on a
tracker or TIM-MARS result) are kept out of the primary aggregate counts
(``sequences``/``evaluated_count``/etc.) and reported separately under
``excluded_sequences`` with their manifest exclusion reasons, so the primary
Issue #30 result reflects only in-scope sequences while excluded ones remain
auditable.

This script does not run anything itself beyond reading already-generated
report.json files for external sequences (one per sequence, produced by
run_external_sequence_report.py) and the ROS 2 event-recovery reports. It is
a read-only aggregation and summary step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    ROOT / "docs" / "data" / "external_benchmark" / "sequence_manifest.json"
)

ROS2_EVENT_RECOVERY_REPORTS = {
    "ros2_internal_development_may_hard_reentry": (
        ROOT
        / "reports"
        / "p026_event_recovery_b50f914a_2026_08_05"
        / "may_hard_reentry"
        / "report.json"
    ),
    "ros2_internal_development_seq01_clean": (
        ROOT
        / "reports"
        / "p026_event_recovery_b50f914a_2026_08_05"
        / "seq01_clean"
        / "report.json"
    ),
    "ros2_internal_development_seq03_crossing": (
        ROOT
        / "artifacts"
        / "reports"
        / "p030_broader_sequences"
        / "seq03_crossing_bytetrack"
        / "report.json"
    ),
    "ros2_internal_development_seq04_occlusion": (
        ROOT
        / "artifacts"
        / "reports"
        / "p030_broader_sequences"
        / "seq04_occlusion_bytetrack"
        / "report.json"
    ),
}


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def summarize_ros2_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        return {"status": "missing_report", "path": str(report_path)}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    duration_rows = report.get("duration_metrics") or {}

    return {
        "status": "evaluated",
        "path": str(report_path),
        "vocabulary": "issue_26_event_recovery",
        "duration_metrics": duration_rows,
    }


def summarize_external_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        return {"status": "missing_report", "path": str(report_path)}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["vocabulary"] = "frame_level_outcome_taxonomy"
    return report


def summarize_sequence_report(
    entry: dict[str, Any], *, external_report_dir: Path
) -> dict[str, Any]:
    sequence_id = entry["id"]

    if entry["dataset"] == "ros2_internal":
        report_path = ROS2_EVENT_RECOVERY_REPORTS.get(sequence_id)
        return (
            summarize_ros2_report(report_path)
            if report_path is not None
            else {"status": "no_report_mapping"}
        )

    report_path = external_report_dir / f"{sequence_id}.json"
    return summarize_external_report(report_path)


def build_aggregate(
    *,
    manifest_path: Path,
    external_report_dir: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)

    sequences: list[dict[str, Any]] = []
    excluded_sequences: list[dict[str, Any]] = []

    for entry in manifest["sequences"]:
        sequence_id = entry["id"]
        summary = summarize_sequence_report(
            entry, external_report_dir=external_report_dir
        )

        if entry.get("status") == "excluded":
            excluded_sequences.append(
                {
                    "id": sequence_id,
                    "dataset": entry["dataset"],
                    "sequence_name": entry["sequence_name"],
                    "exclusions": entry.get("exclusions", []),
                    "report": summary,
                }
            )
            continue

        sequences.append(
            {
                "id": sequence_id,
                "dataset": entry["dataset"],
                "sequence_name": entry["sequence_name"],
                "report": summary,
            }
        )

    evaluated = [
        s for s in sequences if s["report"].get("status") == "evaluated"
    ]
    init_failures = [
        s
        for s in sequences
        if s["report"].get("status") == "initialization_failure"
    ]
    missing = [
        s
        for s in sequences
        if s["report"].get("status")
        not in ("evaluated", "initialization_failure")
    ]

    return {
        "manifest_status": manifest["status"],
        "manifest_frozen_date": manifest.get("frozen_date"),
        "total_sequences": len(sequences),
        "evaluated_count": len(evaluated),
        "initialization_failure_count": len(init_failures),
        "missing_report_count": len(missing),
        "excluded_count": len(excluded_sequences),
        "sequences": sequences,
        "excluded_sequences": excluded_sequences,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--external-report-dir",
        type=Path,
        default=(
            ROOT
            / "artifacts"
            / "reports"
            / "p030_broader_sequences"
            / "external_frame_reports"
        ),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    aggregate = build_aggregate(
        manifest_path=arguments.manifest,
        external_report_dir=arguments.external_report_dir,
    )

    rendered = json.dumps(aggregate, indent=2, default=str)

    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
